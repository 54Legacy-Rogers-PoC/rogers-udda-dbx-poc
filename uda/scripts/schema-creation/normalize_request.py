"""Normalize Databricks self-serve schema request YAML into internal JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from validate_request import validate_request_file  # pylint: disable=import-error
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise SystemExit("validate_request.py is required in the same folder") from exc

try:
    from request_common import (  # pylint: disable=import-error
        ENVIRONMENT_MAP,
        SANDBOX_MODE_MAP,
        as_dict,
        normalize,
        normalize_email,
        to_bool,
    )
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise SystemExit("request_common.py is required in the same folder") from exc


def _load_payload(request_file: Path) -> dict[str, Any]:
    with request_file.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Request YAML root must be a mapping/object")
    return payload


def normalize_payload(payload: dict[str, Any], request_file: Path) -> dict[str, Any]:
    governance = as_dict(payload, "governance")
    sandbox = as_dict(payload, "sandbox")
    communitymart = as_dict(payload, "communitymart")
    ad_group = as_dict(payload, "ad_group")
    metadata = as_dict(payload, "metadata")

    environment_raw = normalize(payload.get("environment"))
    environment = ENVIRONMENT_MAP.get(environment_raw.lower(), environment_raw.upper())

    sandbox_mode_raw = normalize(sandbox.get("selection"))
    sandbox_mode = SANDBOX_MODE_MAP.get(sandbox_mode_raw.lower(), sandbox_mode_raw.lower())

    create_communitymart_schema = to_bool(communitymart.get("create"))

    sandbox_owner = normalize_email(sandbox.get("owner_name"))
    ad_group_owner = normalize_email(ad_group.get("owner_name"))

    epdg_ticket_url = normalize(governance.get("epdg_ticket_url"))

    return {
        "request_id": normalize(payload.get("request_id")),
        "platform": normalize(payload.get("platform")).lower(),
        "request_type": normalize(payload.get("request_type")),
        "environment": environment,
        "sandbox_mode": sandbox_mode,
        "sandbox_schema_name": normalize(sandbox.get("schema_name")).lower(),
        "sandbox_owner_name": sandbox_owner,
        "ad_group_name": normalize(ad_group.get("name")),
        "ad_group_owner_name": ad_group_owner,
        "create_communitymart_schema": create_communitymart_schema,
        "communitymart_schema_name": normalize(communitymart.get("schema_name")).lower(),
        "communitymart_owner_name": normalize_email(communitymart.get("owner_name")),
        "justification": normalize(payload.get("justification")),
        "additional_information": normalize(payload.get("additional_information")),
        "assignment_group": normalize(payload.get("assignment_group")),
        "epdg_ticket_url": epdg_ticket_url,
        "governance_approval_required": epdg_ticket_url != "",
        "ad_approval_required": sandbox_owner != "" and ad_group_owner != "" and sandbox_owner != ad_group_owner,
        "submitted_by": normalize_email(metadata.get("submitted_by")),
        "submitted_at_utc": normalize(metadata.get("submitted_at_utc")),
        "source_request_file": request_file.as_posix(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize Databricks self-serve schema request YAML")
    parser.add_argument("--request-file", required=True, help="Path to request YAML file")
    parser.add_argument("--output-json", required=True, help="Path to normalized output JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request_file = Path(args.request_file).resolve()
    output_json = Path(args.output_json).resolve()

    validation_errors = validate_request_file(request_file)
    if validation_errors:
        print(f"Normalization blocked: validation failed for {request_file}", file=sys.stderr)
        for err in validation_errors:
            print(f"- [{err.code}] {err.field}: {err.message}", file=sys.stderr)
        return 1

    try:
        payload = _load_payload(request_file)
        normalized_payload = normalize_payload(payload, request_file)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Normalization failed: {exc}", file=sys.stderr)
        return 1

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(normalized_payload, indent=2) + "\n", encoding="utf-8")
    print(f"Normalized payload written: {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
