import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class ValidationError(Exception):
    pass


@dataclass
class RequestContext:
    request_id: str
    platform: str
    request_type: str
    environment: str
    activity_type: str
    service_account_type: str
    service_account_name: str
    service_account_owner: str
    attached_to_ad_group: bool | None
    ad_group_name: str
    cluster_name: str
    cluster_id: str
    cluster_permission_level: str
    subscription: str
    resource_group_name: str
    workspace_name: str
    cluster_type: str
    cluster_owner: str
    cluster_scoa_department_name: str
    cluster_scoa_department_number: str
    department_scoa_number: str
    department_scoa_name: str
    justification: str
    additional_information: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def map_environment(raw_environment: str, config: dict[str, Any]) -> str:
    # Translate user-facing environment names to deployment codes (for example, Development -> DEV).
    mapping = config.get("environment_mapping", {})
    if raw_environment in mapping:
        return mapping[raw_environment]

    raise ValidationError(f"Unsupported environment value: {raw_environment}")


def normalize_activity(raw_activity: str) -> str:
    # Accept common separators/casing and normalize everything to canonical workflow tokens.
    token = raw_activity.strip().lower().replace("-", "_").replace(" ", "_")
    token = token.replace("/", "_")

    aliases = {
        "create": "CREATE",
        "delete": "DELETE",
        "add_to_cluster": "ADD_TO_CLUSTER",
        "remove_from_cluster": "REMOVE_FROM_CLUSTER",
        "change_ownership": "CHANGE_OWNERSHIP",
    }

    if token not in aliases:
        allowed = ", ".join(sorted(aliases.keys()))
        raise ValidationError(f"Unsupported activity_type '{raw_activity}'. Allowed values: {allowed}")

    return aliases[token]


def parse_bool(raw_value: Any, field_name: str) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        token = raw_value.strip().lower()
        if token in {"true", "yes", "y", "1"}:
            return True
        if token in {"false", "no", "n", "0"}:
            return False
    raise ValidationError(f"Field {field_name} must be a boolean value")


def get_required(request: dict[str, Any], field: str) -> str:
    value = request.get(field)
    if value is None:
        raise ValidationError(f"Missing required field in request YAML: {field}")
    value_text = str(value).strip()
    if not value_text:
        raise ValidationError(f"Missing required field in request YAML: {field}")
    return value_text


def parse_request(request: dict[str, Any], config: dict[str, Any]) -> RequestContext:
    required = [
        "request_id",
        "platform",
        "request_type",
        "environment",
        "activity_type",
        "service_account_type",
        "service_account_name",
        "service_account_owner",
        "justification",
    ]
    for field in required:
        get_required(request, field)

    activity_type = normalize_activity(str(request["activity_type"]))

    attached_to_ad_group: bool | None = None
    if "attached_to_ad_group" in request and request.get("attached_to_ad_group") is not None:
        attached_to_ad_group = parse_bool(request.get("attached_to_ad_group"), "attached_to_ad_group")

    ad_group_name = str(request.get("ad_group_name", "")).strip()
    cluster_name = str(request.get("cluster_name", "")).strip()
    cluster_id = str(request.get("cluster_id", "")).strip()
    # Default cluster permission when omitted so request samples remain concise.
    cluster_permission_level = str(request.get("cluster_permission_level", "CAN_ATTACH_TO")).strip().upper()

    if activity_type == "CREATE":
        if attached_to_ad_group is None:
            raise ValidationError("Field attached_to_ad_group is required for CREATE activity")
        if attached_to_ad_group and not ad_group_name:
            raise ValidationError("Field ad_group_name is required when attached_to_ad_group is true")
        if not attached_to_ad_group and not cluster_name:
            raise ValidationError("Field cluster_name is required when attached_to_ad_group is false")

    if activity_type in {"ADD_TO_CLUSTER", "REMOVE_FROM_CLUSTER"} and not cluster_name:
        raise ValidationError(f"Field cluster_name is required for {activity_type} activity")

    allowed_cluster_permission_levels = {"CAN_ATTACH_TO", "CAN_RESTART", "CAN_MANAGE"}
    if cluster_permission_level not in allowed_cluster_permission_levels:
        allowed_levels = ", ".join(sorted(allowed_cluster_permission_levels))
        raise ValidationError(
            f"Unsupported cluster_permission_level '{cluster_permission_level}'. Allowed values: {allowed_levels}"
        )

    return RequestContext(
        request_id=str(request["request_id"]).strip(),
        platform=str(request["platform"]).strip().lower(),
        request_type=str(request["request_type"]).strip().lower(),
        environment=map_environment(str(request["environment"]).strip(), config),
        activity_type=activity_type,
        service_account_type=str(request["service_account_type"]).strip(),
        service_account_name=str(request["service_account_name"]).strip(),
        service_account_owner=str(request["service_account_owner"]).strip(),
        attached_to_ad_group=attached_to_ad_group,
        ad_group_name=ad_group_name,
        cluster_name=cluster_name,
        cluster_id=cluster_id,
        cluster_permission_level=cluster_permission_level,
        subscription=str(request.get("subscription", "")).strip(),
        resource_group_name=str(request.get("resource_group_name", "")).strip(),
        workspace_name=str(request.get("workspace_name", "")).strip(),
        cluster_type=str(request.get("cluster_type", "")).strip(),
        cluster_owner=str(request.get("cluster_owner", "")).strip(),
        cluster_scoa_department_name=str(request.get("cluster_scoa_department_name", "")).strip(),
        cluster_scoa_department_number=str(request.get("cluster_scoa_department_number", "")).strip(),
        department_scoa_number=str(request.get("department_scoa_number", "")).strip(),
        department_scoa_name=str(request.get("department_scoa_name", "")).strip(),
        justification=str(request.get("justification", "")).strip(),
        additional_information=str(request.get("additional_information", "")).strip(),
    )


def requires_terraform(activity_type: str) -> bool:
    # Only cluster permission activities require Terraform updates.
    return activity_type in {"ADD_TO_CLUSTER", "REMOVE_FROM_CLUSTER"}


def build_cluster_access_records(context: RequestContext) -> list[dict[str, Any]]:
    if context.activity_type not in {"ADD_TO_CLUSTER", "REMOVE_FROM_CLUSTER"}:
        return []

    # Prefer cluster_id for Databricks permissions resources, but keep legacy cluster_name fallback.
    resolved_cluster_id = context.cluster_id or context.cluster_name

    return [
        {
            "row_id": f"{context.request_id}-00001",
            "activity": context.activity_type,
            "service_account_name": context.service_account_name,
            "cluster_name": context.cluster_name,
            "cluster_id": resolved_cluster_id,
            "permission_level": context.cluster_permission_level,
        }
    ]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process UDA Databricks service account requests")
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--config-file", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    started_at = utc_now()

    request_file = Path(args.request_file)
    config_file = Path(args.config_file)
    output_dir = Path(args.output_dir)

    if not request_file.exists():
        raise ValidationError(f"Request file not found: {request_file}")
    if not config_file.exists():
        raise ValidationError(f"Config file not found: {config_file}")

    config = load_yaml(config_file)
    request_data = load_yaml(request_file)
    context = parse_request(request_data, config)

    if context.platform != "databricks":
        raise ValidationError("platform must be databricks")
    if context.request_type != "service_account":
        raise ValidationError("request_type must be service_account")

    terraform_required = requires_terraform(context.activity_type)
    cluster_access_records = build_cluster_access_records(context)

    # Keep a tfvars file present so downstream jobs can inspect request identity consistently.
    terraform_vars = {
        "request_id": context.request_id,
        "environment": context.environment,
        "object_access_records": [],
        "service_account_cluster_access_records": cluster_access_records,
    }
    tfvars_file = output_dir / "terraform.auto.tfvars.json"
    write_json(tfvars_file, terraform_vars)

    metadata = {
        "request_id": context.request_id,
        "platform": context.platform,
        "request_type": context.request_type,
        "environment": context.environment,
        "activity_type": context.activity_type,
        "service_account_type": context.service_account_type,
        "service_account_name": context.service_account_name,
        "service_account_owner": context.service_account_owner,
        "attached_to_ad_group": context.attached_to_ad_group,
        "ad_group_name": context.ad_group_name,
        "cluster_name": context.cluster_name,
        "cluster_id": context.cluster_id,
        "cluster_permission_level": context.cluster_permission_level,
        "requires_terraform": terraform_required,
        "terraform_vars_file": str(tfvars_file),
    }
    write_json(output_dir / "request_metadata.json", metadata)

    governance_payload = {
        # Keep payload shape aligned with downstream CM stored procedure contract.
        "platform": "Databricks",
        "service_account_name": context.service_account_name,
        "service_account_type": context.service_account_type,
        "environment": context.environment,
        "request_type": context.request_type,
        "activity_type": context.activity_type,
        "cluster_name": context.cluster_name,
        "databricks_workspace_name": context.workspace_name,
        "subscription": context.subscription,
        "resource_group_name": context.resource_group_name,
        "cluster_type": context.cluster_type,
        "cluster_owner": context.cluster_owner,
        "cluster_scoa_department_name": context.cluster_scoa_department_name,
        "cluster_scoa_department_number": context.cluster_scoa_department_number,
        "service_account_owner": context.service_account_owner,
        "department_scoa_number": context.department_scoa_number,
        "department_scoa_name": context.department_scoa_name,
        "justification": context.justification,
        "additional_information": context.additional_information,
        "request_id": context.request_id,
        "created_date": utc_now(),
        "provisioning_status": "PENDING",
        "cm_writeback_status": "PENDING",
    }
    write_json(output_dir / "governance_payload.json", governance_payload)

    execution_log = {
        "request_id": context.request_id,
        "service_account_name": context.service_account_name,
        "environment": context.environment,
        "activity_type": context.activity_type,
        "cluster_name": context.cluster_name,
        "workflow_start_time": started_at,
        "workflow_end_time": utc_now(),
        "execution_status": "SUCCESS",
        "requires_terraform": terraform_required,
    }
    write_json(output_dir / "execution_log.json", execution_log)


if __name__ == "__main__":
    try:
        main()
    except ValidationError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
