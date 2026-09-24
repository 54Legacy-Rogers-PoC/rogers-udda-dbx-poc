"""Generate Terraform tfvars JSON from normalized schema-creation request payload."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from normalize_request import normalize_payload  # pylint: disable=wrong-import-position

REQUIRED_KEYS = {
    "request_id",
    "environment",
    "sandbox_mode",
    "sandbox_owner_name",
    "assignment_group",
}

# Keep this list aligned with the future schema-creation Terraform root variables.
DECLARED_TFVARS_KEYS = [
    "schema_creation_enabled",
    "schema_creation_requests",
    "request_id",
    "environment",
    "sandbox_mode",
    "sandbox_schema_name",
    "sandbox_owner_name",
    "create_communitymart_schema",
    "communitymart_schema_name",
    "communitymart_owner_name",
    "ad_group_name",
    "justification",
    "additional_information",
    "assignment_group",
    "epdg_ticket_url",
    "governance_approval_required",
    "ad_approval_required",
]


class DuplicateSchemaTargetError(ValueError):
    """Raised when a new request targets a schema already owned in state."""

    def __init__(self, *, request_id: str, target: dict[str, Any], existing_request_id: str) -> None:
        self.request_id = request_id
        self.catalog = str(target["target_catalog"])
        self.schema = str(target["target_schema_name"])
        self.existing_request_id = existing_request_id
        super().__init__(f"{self.catalog}.{self.schema} is already owned by {existing_request_id}")

    def markdown(self) -> str:
        return "\n".join(
            [
                "## Schema Request Rejected",
                "",
                f"- Request: {self.request_id}",
                f"- Schema: {self.catalog}.{self.schema}",
                f"- Existing owner: {self.existing_request_id}",
                "- Status: Duplicate schema target",
                "- Action: Choose a unique schema name or submit an object-access request",
            ]
        )


def _normalize(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _normalize(value).lower() in {"1", "true", "yes", "y"}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Normalized input must be a JSON object")

    missing = sorted(k for k in REQUIRED_KEYS if _normalize(payload.get(k)) == "")
    if missing:
        raise ValueError(f"Normalized input missing required keys: {missing}")

    return payload


def _extract_terraform_variable_names(variables_file: Path) -> set[str]:
    content = variables_file.read_text(encoding="utf-8")
    matches = re.findall(r'variable\s+"([^"]+)"\s*\{', content)
    return set(matches)


def _validate_contract_with_terraform(tfvars_payload: dict[str, Any], variables_file: Path) -> None:
    declared_vars = _extract_terraform_variable_names(variables_file)
    if not declared_vars:
        raise ValueError(f"No Terraform variables found in: {variables_file}")

    payload_keys = set(tfvars_payload.keys())
    missing_keys = sorted(declared_vars - payload_keys)

    # Ignore provider auth variables in contract checks. They are injected by workflow env/secrets.
    ignored_missing = {
        "access_for_types",
        "activities",
        "cluster_ad_group_access_records",
        "databricks_host",
        "databricks_token",
        "databricks_client_id",
        "databricks_client_secret",
        "databricks_tenant_id",
        "databricks_workspace_resource_id",
        "object_access_records",
        "record_count",
        "service_account_cluster_access_records",
    }
    missing_relevant = [k for k in missing_keys if k not in ignored_missing]

    if missing_relevant:
        raise ValueError(f"Terraform variables missing from generated tfvars: {missing_relevant}")


def _prune_to_declared_vars(tfvars_payload: dict[str, Any], variables_file: Path) -> dict[str, Any]:
    declared_vars = _extract_terraform_variable_names(variables_file)
    return {k: v for k, v in tfvars_payload.items() if k in declared_vars}


def _build_request_values(normalized_payload: dict[str, Any]) -> dict[str, Any]:
    request_values: dict[str, Any] = {}
    for key in DECLARED_TFVARS_KEYS:
        if key in {"schema_creation_enabled", "schema_creation_requests"}:
            continue
        value = normalized_payload.get(key)
        if key in {"create_communitymart_schema", "governance_approval_required", "ad_approval_required"}:
            request_values[key] = _to_bool(value)
        else:
            request_values[key] = _normalize(value)

    return request_values


def _schema_catalogs(environment: str) -> dict[str, str]:
    mapping_path = REPO_ROOT / "uda" / "config" / "environment-mapping.yaml"
    mapping = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    config_path = _normalize(mapping.get("config_files", {}).get(environment.upper()))
    if not config_path:
        raise ValueError(f"No environment configuration found for {environment}")

    config = yaml.safe_load((REPO_ROOT / config_path).read_text(encoding="utf-8")) or {}
    schema_config = config.get("schema_creation") or {}
    catalogs = {
        "sandbox": _normalize(schema_config.get("sandbox_catalog_name")).lower(),
        "communitymart": _normalize(schema_config.get("communitymart_catalog_name")).lower(),
    }
    missing = sorted(target_type for target_type, catalog in catalogs.items() if not catalog)
    if missing:
        raise ValueError(f"Missing schema catalogs for {environment}: {', '.join(missing)}")
    return catalogs


def _build_schema_targets(normalized_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    values = _build_request_values(normalized_payload)
    environment = _normalize(values["environment"]).upper()
    catalogs = _schema_catalogs(environment)
    targets: dict[str, dict[str, Any]] = {}

    target_specs = [
        ("sandbox", values["sandbox_mode"] == "new", values["sandbox_schema_name"]),
        ("communitymart", values["create_communitymart_schema"], values["communitymart_schema_name"]),
    ]
    for target_type, enabled, schema_name in target_specs:
        if not enabled:
            continue
        catalog = catalogs[target_type]
        key = f"{environment}|{catalog}|{_normalize(schema_name).lower()}"
        targets[key] = {
            **values,
            "target_type": target_type,
            "target_catalog": catalog,
            "target_schema_name": _normalize(schema_name).lower(),
        }
    return targets


def _load_request_index(requests_directory: Path) -> dict[str, list[dict[str, Any]]]:
    request_index: dict[str, list[dict[str, Any]]] = {}
    paths = sorted(requests_directory.rglob("*.yml")) + sorted(requests_directory.rglob("*.yaml"))
    paths += sorted(requests_directory.rglob("*.json"))

    for path in paths:
        if path.suffix.lower() == ".json":
            normalized = _load_json(path)
        else:
            with path.open("r", encoding="utf-8") as handle:
                raw_payload = yaml.safe_load(handle)
            if not isinstance(raw_payload, dict):
                continue
            normalized = normalize_payload(raw_payload, path)

        request_id = _normalize(normalized.get("request_id"))
        if not request_id:
            continue
        request_index.setdefault(request_id, []).append(normalized)

    return request_index


def build_shared_tfvars_payload(
    current_payload: dict[str, Any],
    *,
    existing_request_ids: set[str],
    requests_directory: Path,
    orphaned_state_keys: list[str] | None = None,
) -> dict[str, Any]:
    current_values = _build_request_values(current_payload)
    current_request_id = current_values["request_id"]
    request_index = _load_request_index(requests_directory) if existing_request_ids else {}
    target_index: dict[str, list[dict[str, Any]]] = {}
    for requests in request_index.values():
        for normalized in requests:
            for key, target in _build_schema_targets(normalized).items():
                target_index.setdefault(key, []).append(target)

    request_map: dict[str, dict[str, Any]] = {}
    current_environment = _normalize(current_values["environment"]).upper()

    for state_key in sorted(existing_request_ids):
        if state_key == current_request_id:
            existing_targets = _build_schema_targets(current_payload)
        elif state_key in request_index:
            matches = request_index[state_key]
            if len(matches) != 1:
                raise ValueError(
                    f"Legacy state request ID {state_key} has multiple request sources; migrate the state address to a schema target key"
                )
            existing_targets = _build_schema_targets(matches[0])
        elif state_key in target_index:
            matches = target_index[state_key]
            if len(matches) != 1:
                owners = ", ".join(sorted(str(target["request_id"]) for target in matches))
                raise ValueError(f"State-backed schema target {state_key} has multiple request sources: {owners}")
            existing_targets = {state_key: matches[0]}
        else:
            if orphaned_state_keys is not None:
                orphaned_state_keys.append(state_key)
                continue
            raise ValueError(
                f"State-backed schema key {state_key} has no matching source under {requests_directory}"
            )

        for target_key, target in existing_targets.items():
            existing_environment = _normalize(target["environment"]).upper()
            if existing_environment != current_environment:
                raise ValueError(
                    "Shared schema state cannot mix environments: "
                    f"current request is {current_environment}, but {target['request_id']} is {existing_environment}"
                )
            existing = request_map.get(target_key)
            if existing is not None and existing["request_id"] != target["request_id"]:
                raise ValueError(
                    f"Schema target {target_key} is declared by both {existing['request_id']} and {target['request_id']}"
                )
            request_map[target_key] = target

    for target_key, target in _build_schema_targets(current_payload).items():
        existing = request_map.get(target_key)
        if existing is not None and existing["request_id"] != current_request_id:
            raise DuplicateSchemaTargetError(
                request_id=current_request_id,
                target=target,
                existing_request_id=str(existing["request_id"]),
            )
        request_map[target_key] = target
    return {
        "schema_creation_enabled": True,
        **current_values,
        "schema_creation_requests": request_map,
    }


def render_orphaned_state_keys(state_keys: list[str]) -> str:
    unique_keys = sorted(set(state_keys))
    return "" if not unique_keys else "\n".join(unique_keys) + "\n"


def build_tfvars_payload(normalized_payload: dict[str, Any]) -> dict[str, Any]:
    tfvars_payload: dict[str, Any] = {
        "schema_creation_enabled": True,
        **_build_request_values(normalized_payload),
    }

    tfvars_payload["schema_creation_requests"] = _build_schema_targets(normalized_payload)

    return tfvars_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate tfvars from normalized schema-creation payload")
    parser.add_argument("--input-json", required=True, help="Path to normalized JSON input")
    parser.add_argument("--output-json", required=True, help="Output tfvars JSON path")
    parser.add_argument(
        "--existing-request-ids-file",
        help="Optional file containing request IDs already managed in the shared Terraform state",
    )
    parser.add_argument(
        "--requests-directory",
        default="requests/schema-creation",
        help="Request source directory used to reconstruct state-backed request inputs",
    )
    parser.add_argument(
        "--orphaned-state-keys-file",
        help="Optional output file listing state keys whose request source was deleted",
    )
    parser.add_argument(
        "--current-targets-json",
        help="Optional output file containing only schema targets from the current request",
    )
    parser.add_argument(
        "--terraform-variables-file",
        default="terraform/variables.tf",
        help="Path to Terraform variables.tf used to validate tfvars contract",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_json = Path(args.input_json).resolve()
    output_json = Path(args.output_json).resolve()
    variables_file = Path(args.terraform_variables_file).resolve()

    try:
        normalized_payload = _load_json(input_json)
        orphaned_state_keys: list[str] | None = [] if args.orphaned_state_keys_file else None
        if args.existing_request_ids_file:
            ids_path = Path(args.existing_request_ids_file).resolve()
            existing_request_ids = {
                line.strip() for line in ids_path.read_text(encoding="utf-8").splitlines() if line.strip()
            }
            tfvars_payload = build_shared_tfvars_payload(
                normalized_payload,
                existing_request_ids=existing_request_ids,
                requests_directory=Path(args.requests_directory).resolve(),
                orphaned_state_keys=orphaned_state_keys,
            )
        else:
            tfvars_payload = build_tfvars_payload(normalized_payload)
        tfvars_payload = _prune_to_declared_vars(tfvars_payload, variables_file)
        _validate_contract_with_terraform(tfvars_payload, variables_file)
    except DuplicateSchemaTargetError as exc:
        message = exc.markdown()
        print(message, file=sys.stderr)
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with Path(summary_path).open("a", encoding="utf-8") as summary:
                summary.write(message + "\n")
        return 1
    except Exception as exc:  # pylint: disable=broad-except
        print(f"tfvars generation failed: {exc}", file=sys.stderr)
        return 1

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(tfvars_payload, indent=2) + "\n", encoding="utf-8")
    if args.current_targets_json:
        current_targets_file = Path(args.current_targets_json).resolve()
        current_targets_file.write_text(
            json.dumps(_build_schema_targets(normalized_payload), indent=2) + "\n",
            encoding="utf-8",
        )
    if args.orphaned_state_keys_file:
        assert orphaned_state_keys is not None
        orphaned_file = Path(args.orphaned_state_keys_file).resolve()
        orphaned_file.write_text(render_orphaned_state_keys(orphaned_state_keys), encoding="utf-8")
        for state_key in orphaned_state_keys:
            print(f"Request source deleted; state cleanup required for: {state_key}")
    print(f"tfvars generated: {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
