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
    cluster_name: str
    cluster_id: str
    cluster_permission_level: str
    ad_group_name: str
    subscription: str
    resource_group_name: str
    databricks_workspace_name: str
    cluster_type: str
    cluster_owner: str
    cluster_department_name: str
    cluster_department_number: str
    justification: str
    additional_information: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def map_environment(raw_environment: str, config: dict[str, Any]) -> str:
    mapping = config.get("environment_mapping", {})
    if raw_environment in mapping:
        return mapping[raw_environment]

    raise ValidationError(f"Unsupported environment value: {raw_environment}")


def normalize_activity(raw_activity: str) -> str:
    token = raw_activity.strip().upper()
    if token not in {"ADD", "REMOVE"}:
        raise ValidationError("activity_type must be ADD or REMOVE")
    return token


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
        "cluster_name",
        "ad_group_name",
        "justification",
    ]
    for field in required:
        get_required(request, field)

    permission_level = str(request.get("cluster_permission_level", "CAN_ATTACH_TO")).strip().upper()
    allowed_permission_levels = {"CAN_ATTACH_TO", "CAN_RESTART", "CAN_MANAGE"}
    if permission_level not in allowed_permission_levels:
        allowed_values = ", ".join(sorted(allowed_permission_levels))
        raise ValidationError(
            f"Unsupported cluster_permission_level '{permission_level}'. Allowed values: {allowed_values}"
        )

    return RequestContext(
        request_id=str(request["request_id"]).strip(),
        platform=str(request["platform"]).strip().lower(),
        request_type=str(request["request_type"]).strip().lower(),
        environment=map_environment(str(request["environment"]).strip(), config),
        activity_type=normalize_activity(str(request["activity_type"])),
        cluster_name=str(request["cluster_name"]).strip(),
        cluster_id=str(request.get("cluster_id", "")).strip(),
        cluster_permission_level=permission_level,
        ad_group_name=str(request["ad_group_name"]).strip(),
        subscription=str(request.get("subscription", "")).strip(),
        resource_group_name=str(request.get("resource_group_name", "")).strip(),
        databricks_workspace_name=str(request.get("databricks_workspace_name", "")).strip(),
        cluster_type=str(request.get("cluster_type", "")).strip(),
        cluster_owner=str(request.get("cluster_owner", "")).strip(),
        cluster_department_name=str(request.get("cluster_department_name", "")).strip(),
        cluster_department_number=str(request.get("cluster_department_number", "")).strip(),
        justification=str(request.get("justification", "")).strip(),
        additional_information=str(request.get("additional_information", "")).strip(),
    )


def build_cluster_ad_group_records(context: RequestContext) -> list[dict[str, Any]]:
    resolved_cluster_id = context.cluster_id or context.cluster_name
    return [
        {
            "row_id": f"{context.request_id}-00001",
            "activity": context.activity_type,
            "ad_group_name": context.ad_group_name,
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
    parser = argparse.ArgumentParser(description="Process UDA Databricks cluster AD group requests")
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
    if context.request_type != "cluster_ad_group":
        raise ValidationError("request_type must be cluster_ad_group")

    cluster_records = build_cluster_ad_group_records(context)

    terraform_vars = {
        "request_id": context.request_id,
        "environment": context.environment,
        "object_access_records": [],
        "service_account_cluster_access_records": [],
        "cluster_ad_group_access_records": cluster_records,
    }
    terraform_vars_file = output_dir / "terraform.auto.tfvars.json"
    write_json(terraform_vars_file, terraform_vars)

    metadata = {
        "request_id": context.request_id,
        "environment": context.environment,
        "activity_type": context.activity_type,
        "cluster_name": context.cluster_name,
        "cluster_id": context.cluster_id,
        "ad_group_name": context.ad_group_name,
        "cluster_permission_level": context.cluster_permission_level,
        "record_count": len(cluster_records),
        "terraform_vars_file": str(terraform_vars_file),
    }
    write_json(output_dir / "request_metadata.json", metadata)

    execution_log = {
        "request_id": context.request_id,
        "environment": context.environment,
        "activity_type": context.activity_type,
        "cluster_name": context.cluster_name,
        "ad_group_name": context.ad_group_name,
        "workflow_start_time": started_at,
        "workflow_end_time": utc_now(),
        "execution_status": "SUCCESS",
    }
    write_json(output_dir / "execution_log.json", execution_log)


if __name__ == "__main__":
    try:
        main()
    except ValidationError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
