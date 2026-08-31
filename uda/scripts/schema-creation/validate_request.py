"""Validate Databricks self-serve schema request YAML payloads."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from request_common import (  # pylint: disable=import-error
        ALLOWED_ENVIRONMENTS,
        ALLOWED_SANDBOX_SELECTION,
        EXPECTED_ASSIGNMENT_GROUP,
        EXPECTED_PLATFORM,
        EXPECTED_REQUEST_TYPE,
        as_dict,
        normalize,
        to_bool,
    )
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise SystemExit("request_common.py is required in the same folder") from exc


@dataclass
class ValidationError:
    code: str
    field: str
    message: str


def _is_blank(value: Any) -> bool:
    return normalize(value) == ""


def _is_valid_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _require_non_blank(
    errors: list[ValidationError],
    payload: dict[str, Any],
    field: str,
    code: str = "SCR-001",
) -> None:
    if _is_blank(payload.get(field)):
        errors.append(ValidationError(code=code, field=field, message=f"Field is required: {field}"))


def _validate_top_level(payload: dict[str, Any], errors: list[ValidationError]) -> None:
    _require_non_blank(errors, payload, "request_id")
    _require_non_blank(errors, payload, "platform")
    _require_non_blank(errors, payload, "request_type")
    _require_non_blank(errors, payload, "environment")
    _require_non_blank(errors, payload, "justification")
    _require_non_blank(errors, payload, "assignment_group")

    platform = normalize(payload.get("platform"))
    if platform and platform != EXPECTED_PLATFORM:
        errors.append(
            ValidationError(
                code="SCR-002",
                field="platform",
                message=f"Unsupported platform: {platform}. Expected: {EXPECTED_PLATFORM}",
            )
        )

    request_type = normalize(payload.get("request_type"))
    if request_type and request_type != EXPECTED_REQUEST_TYPE:
        errors.append(
            ValidationError(
                code="SCR-003",
                field="request_type",
                message=f"Unsupported request_type: {request_type}. Expected: {EXPECTED_REQUEST_TYPE}",
            )
        )

    environment = normalize(payload.get("environment"))
    if environment and environment not in ALLOWED_ENVIRONMENTS:
        errors.append(
            ValidationError(
                code="SCR-004",
                field="environment",
                message=(
                    f"Invalid environment: {environment}. "
                    f"Allowed values: {', '.join(sorted(ALLOWED_ENVIRONMENTS))}"
                ),
            )
        )

    assignment_group = normalize(payload.get("assignment_group"))
    if assignment_group and assignment_group != EXPECTED_ASSIGNMENT_GROUP:
        errors.append(
            ValidationError(
                code="SCR-005",
                field="assignment_group",
                message=(
                    f"Invalid assignment_group: {assignment_group}. "
                    f"Expected: {EXPECTED_ASSIGNMENT_GROUP}"
                ),
            )
        )


def _validate_governance(payload: dict[str, Any], errors: list[ValidationError]) -> None:
    governance = as_dict(payload, "governance")
    epdg_ticket_url = normalize(governance.get("epdg_ticket_url"))
    if epdg_ticket_url and not _is_valid_url(epdg_ticket_url):
        errors.append(
            ValidationError(
                code="SCR-006",
                field="governance.epdg_ticket_url",
                message="EPDG ticket URL must start with http:// or https://",
            )
        )


def _validate_sandbox(payload: dict[str, Any], errors: list[ValidationError]) -> None:
    sandbox = as_dict(payload, "sandbox")
    sandbox_selection = normalize(sandbox.get("selection"))
    sandbox_schema_name = normalize(sandbox.get("schema_name"))
    sandbox_owner_name = normalize(sandbox.get("owner_name"))

    if _is_blank(sandbox_selection):
        errors.append(
            ValidationError(code="SCR-001", field="sandbox.selection", message="Field is required: sandbox.selection")
        )
    elif sandbox_selection not in ALLOWED_SANDBOX_SELECTION:
        errors.append(
            ValidationError(
                code="SCR-007",
                field="sandbox.selection",
                message=(
                    f"Invalid sandbox.selection: {sandbox_selection}. "
                    f"Allowed values: {', '.join(sorted(ALLOWED_SANDBOX_SELECTION))}"
                ),
            )
        )

    if _is_blank(sandbox_owner_name):
        errors.append(
            ValidationError(code="SCR-001", field="sandbox.owner_name", message="Field is required: sandbox.owner_name")
        )

    if sandbox_selection != "New Sandbox":
        return

    if _is_blank(sandbox_schema_name):
        errors.append(
            ValidationError(
                code="SCR-001",
                field="sandbox.schema_name",
                message="Field is required for New Sandbox: sandbox.schema_name",
            )
        )
    elif not re.fullmatch(r"slfsrv_[a-z0-9_]+", sandbox_schema_name):
        errors.append(
            ValidationError(
                code="SCR-008",
                field="sandbox.schema_name",
                message="sandbox.schema_name must match pattern: slfsrv_[a-z0-9_]+",
            )
        )


def _validate_communitymart(payload: dict[str, Any], errors: list[ValidationError]) -> None:
    communitymart = as_dict(payload, "communitymart")
    cm_create = to_bool(communitymart.get("create"))
    cm_schema_name = normalize(communitymart.get("schema_name"))
    cm_owner_name = normalize(communitymart.get("owner_name"))

    if not cm_create:
        return

    if _is_blank(cm_schema_name):
        errors.append(
            ValidationError(
                code="SCR-001",
                field="communitymart.schema_name",
                message="Field is required when communitymart.create is true: communitymart.schema_name",
            )
        )
    elif not re.fullmatch(r"vw_[a-z0-9_]+", cm_schema_name):
        errors.append(
            ValidationError(
                code="SCR-009",
                field="communitymart.schema_name",
                message="communitymart.schema_name must match pattern: vw_[a-z0-9_]+",
            )
        )

    if _is_blank(cm_owner_name):
        errors.append(
            ValidationError(
                code="SCR-001",
                field="communitymart.owner_name",
                message="Field is required when communitymart.create is true: communitymart.owner_name",
            )
        )


def _resolve_request_file_path(raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    resolved = (Path.cwd() / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError(f"request_file must be inside repository root: {REPO_ROOT}") from exc
    return resolved


def validate_request_payload(payload: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []

    _validate_top_level(payload, errors)
    _validate_governance(payload, errors)
    _validate_sandbox(payload, errors)
    _validate_communitymart(payload, errors)

    return errors


def validate_request_file(request_file: Path) -> list[ValidationError]:
    if not request_file.exists():
        return [
            ValidationError(
                code="SCR-000",
                field="request_file",
                message=f"Request file not found: {request_file}",
            )
        ]

    try:
        with request_file.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except Exception as exc:  # pylint: disable=broad-except
        return [
            ValidationError(
                code="SCR-000",
                field="request_file",
                message=f"Request file is unreadable: {exc}",
            )
        ]

    if not isinstance(payload, dict):
        return [
            ValidationError(
                code="SCR-000",
                field="request_file",
                message="Request YAML root must be a mapping/object",
            )
        ]

    return validate_request_payload(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Databricks self-serve schema request YAML")
    parser.add_argument("--request-file", required=True, help="Path to request YAML file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        request_file = _resolve_request_file_path(args.request_file)
    except ValueError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1

    errors = validate_request_file(request_file)
    if errors:
        print(f"Validation failed for {request_file} ({len(errors)} issue(s))", file=sys.stderr)
        for err in errors:
            print(f"- [{err.code}] {err.field}: {err.message}", file=sys.stderr)
        return 1

    print(f"Validation passed for {request_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
