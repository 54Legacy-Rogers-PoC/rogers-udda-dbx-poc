"""Generate Terraform tfvars JSON from normalized schema-creation request payload."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_KEYS = {
    "request_id",
    "environment",
    "sandbox_mode",
    "sandbox_owner_name",
    "assignment_group",
}

# Keep this list aligned with the future schema-creation Terraform root variables.
DECLARED_TFVARS_KEYS = [
    "request_id",
    "environment",
    "sandbox_mode",
    "sandbox_schema_name",
    "sandbox_owner_name",
    "create_communitymart_schema",
    "communitymart_schema_name",
    "communitymart_owner_name",
    "justification",
    "additional_information",
    "assignment_group",
    "epdg_ticket_url",
    "governance_approval_required",
    "ad_approval_required",
]


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
        "databricks_host",
        "databricks_token",
        "databricks_client_id",
        "databricks_client_secret",
        "databricks_tenant_id",
    }
    missing_relevant = [k for k in missing_keys if k not in ignored_missing]

    if missing_relevant:
        raise ValueError(f"Terraform variables missing from generated tfvars: {missing_relevant}")


def _prune_to_declared_vars(tfvars_payload: dict[str, Any], variables_file: Path) -> dict[str, Any]:
    declared_vars = _extract_terraform_variable_names(variables_file)
    return {k: v for k, v in tfvars_payload.items() if k in declared_vars}


def build_tfvars_payload(normalized_payload: dict[str, Any]) -> dict[str, Any]:
    tfvars_payload: dict[str, Any] = {}

    for key in DECLARED_TFVARS_KEYS:
        value = normalized_payload.get(key)
        if key in {"create_communitymart_schema", "governance_approval_required", "ad_approval_required"}:
            tfvars_payload[key] = _to_bool(value)
        else:
            tfvars_payload[key] = _normalize(value)

    return tfvars_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate tfvars from normalized schema-creation payload")
    parser.add_argument("--input-json", required=True, help="Path to normalized JSON input")
    parser.add_argument("--output-json", required=True, help="Output tfvars JSON path")
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
        tfvars_payload = build_tfvars_payload(normalized_payload)
        tfvars_payload = _prune_to_declared_vars(tfvars_payload, variables_file)
        _validate_contract_with_terraform(tfvars_payload, variables_file)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"tfvars generation failed: {exc}", file=sys.stderr)
        return 1

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(tfvars_payload, indent=2) + "\n", encoding="utf-8")
    print(f"tfvars generated: {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
