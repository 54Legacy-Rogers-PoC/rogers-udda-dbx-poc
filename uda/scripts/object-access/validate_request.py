"""Validate Databricks object access request YAML files.

This script validates request metadata before template parsing and Terraform stages.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
	import yaml
except ImportError as exc:  # pragma: no cover - runtime environment dependency
	raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from exc


REQUEST_ID_REGEX = re.compile(r"^RITM[0-9]+$")
REQUIRED_FIELDS = (
	"request_id",
	"platform",
	"request_type",
	"environment",
	"activity_type",
	"access_for",
	"template_file",
	"justification",
)
ALLOWED_ENVIRONMENTS = {"DEV", "QA", "PRD"}
ALLOWED_ACTIVITY_TYPES = {"ADD", "REMOVE", "REVOKE"}
ALLOWED_ACCESS_FOR = {"ad_group", "service_account"}


@dataclass
class ValidationError:
	code: str
	field: str
	message: str
 


def _is_blank(value: Any) -> bool:
	if value is None:
		return True
	if isinstance(value, str):
		return value.strip() == ""
	return False


def _load_yaml(file_path: Path) -> dict[str, Any]:
	with file_path.open("r", encoding="utf-8") as handle:
		loaded = yaml.safe_load(handle)

	if loaded is None:
		return {}
	if not isinstance(loaded, dict):
		raise ValueError("YAML root must be a mapping of key/value pairs")
	return loaded


def _validate_required_fields(payload: dict[str, Any]) -> list[ValidationError]:
	errors: list[ValidationError] = []
	for field in REQUIRED_FIELDS:
		if field not in payload or _is_blank(payload.get(field)):
			errors.append(
				ValidationError(
					code="YML-002",
					field=field,
					message=f"Missing or empty required field: {field}",
				)
			)
	return errors


def _validate_enums(payload: dict[str, Any]) -> list[ValidationError]:
	errors: list[ValidationError] = []

	environment = payload.get("environment")
	if not _is_blank(environment) and environment not in ALLOWED_ENVIRONMENTS:
		errors.append(
			ValidationError(
				code="YML-003",
				field="environment",
				message=(
					"Invalid environment value. "
					f"Expected one of: {sorted(ALLOWED_ENVIRONMENTS)}"
				),
			)
		)

	activity_type = payload.get("activity_type")
	if not _is_blank(activity_type) and activity_type not in ALLOWED_ACTIVITY_TYPES:
		errors.append(
			ValidationError(
				code="YML-003",
				field="activity_type",
				message=(
					"Invalid activity_type value. "
					f"Expected one of: {sorted(ALLOWED_ACTIVITY_TYPES)}"
				),
			)
		)

	access_for = payload.get("access_for")
	if not _is_blank(access_for) and access_for not in ALLOWED_ACCESS_FOR:
		errors.append(
			ValidationError(
				code="YML-003",
				field="access_for",
				message=(
					"Invalid access_for value. "
					f"Expected one of: {sorted(ALLOWED_ACCESS_FOR)}"
				),
			)
		)

	return errors


def _validate_platform_and_request_type(payload: dict[str, Any]) -> list[ValidationError]:
	errors: list[ValidationError] = []

	if not _is_blank(payload.get("platform")) and payload.get("platform") != "databricks":
		errors.append(
			ValidationError(
				code="YML-010",
				field="platform",
				message="Unsupported platform. Expected: databricks",
			)
		)

	if not _is_blank(payload.get("request_type")) and payload.get("request_type") != "object_access":
		errors.append(
			ValidationError(
				code="YML-010",
				field="request_type",
				message="Unsupported request_type. Expected: object_access",
			)
		)

	return errors


def _validate_request_id_and_filename(payload: dict[str, Any], file_path: Path) -> list[ValidationError]:
	errors: list[ValidationError] = []
	request_id = payload.get("request_id")

	if not _is_blank(request_id) and not REQUEST_ID_REGEX.match(str(request_id)):
		errors.append(
			ValidationError(
				code="YML-004",
				field="request_id",
				message="Invalid request_id format. Expected pattern: RITM<digits>",
			)
		)

	file_stem = file_path.stem
	if not _is_blank(request_id) and str(request_id) != file_stem:
		errors.append(
			ValidationError(
				code="YML-005",
				field="request_id",
				message=(
					"request_id does not match filename. "
					f"request_id={request_id}, filename={file_stem}.yaml"
				),
			)
		)

	return errors


def _validate_conditional_fields(payload: dict[str, Any]) -> list[ValidationError]:
	errors: list[ValidationError] = []
	access_for = payload.get("access_for")
	ad_group_name = payload.get("ad_group_name")
	service_account_name = payload.get("service_account_name")

	if access_for == "ad_group":
		if _is_blank(ad_group_name):
			errors.append(
				ValidationError(
					code="YML-006",
					field="ad_group_name",
					message="ad_group_name is required when access_for=ad_group",
				)
			)
		if not _is_blank(service_account_name):
			errors.append(
				ValidationError(
					code="YML-006",
					field="service_account_name",
					message="service_account_name must be empty when access_for=ad_group",
				)
			)

	if access_for == "service_account":
		if _is_blank(service_account_name):
			errors.append(
				ValidationError(
					code="YML-006",
					field="service_account_name",
					message="service_account_name is required when access_for=service_account",
				)
			)
		if not _is_blank(ad_group_name):
			errors.append(
				ValidationError(
					code="YML-006",
					field="ad_group_name",
					message="ad_group_name must be empty when access_for=service_account",
				)
			)

	return errors


def _validate_template_file(payload: dict[str, Any], attachments_dir: Path) -> list[ValidationError]:
	errors: list[ValidationError] = []
	template_file = payload.get("template_file")

	if _is_blank(template_file):
		return errors

	template_name = str(template_file)
	if not template_name.lower().endswith(".xlsx"):
		errors.append(
			ValidationError(
				code="YML-007",
				field="template_file",
				message="template_file must have .xlsx extension",
			)
		)
		return errors

	template_path = attachments_dir / template_name
	if not template_path.exists():
		errors.append(
			ValidationError(
				code="YML-008",
				field="template_file",
				message=f"Referenced template file not found: {template_path}",
			)
		)

	return errors


def _validate_justification(payload: dict[str, Any]) -> list[ValidationError]:
	justification = payload.get("justification")
	if _is_blank(justification):
		return [
			ValidationError(
				code="YML-009",
				field="justification",
				message="justification must not be blank",
			)
		]
	return []


def validate_request_file(file_path: Path, attachments_dir: Path) -> list[ValidationError]:
	try:
		payload = _load_yaml(file_path)
	except Exception as exc:  # pylint: disable=broad-except
		return [
			ValidationError(
				code="YML-001",
				field="file",
				message=f"YAML parsing failed: {exc}",
			)
		]

	errors: list[ValidationError] = []
	errors.extend(_validate_required_fields(payload))
	errors.extend(_validate_platform_and_request_type(payload))
	errors.extend(_validate_enums(payload))
	errors.extend(_validate_request_id_and_filename(payload, file_path))
	errors.extend(_validate_conditional_fields(payload))
	errors.extend(_validate_template_file(payload, attachments_dir))
	errors.extend(_validate_justification(payload))
	return errors


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Validate UDA object access request YAML")
	parser.add_argument("--request-file", required=True, help="Path to request YAML file")
	parser.add_argument(
		"--attachments-dir",
		default="uda/attachments/object-access",
		help="Directory where template attachments are stored",
	)
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	request_file = Path(args.request_file).resolve()
	attachments_dir = Path(args.attachments_dir).resolve()

	errors = validate_request_file(file_path=request_file, attachments_dir=attachments_dir)
	if errors:
		print("Validation failed.")
		for error in errors:
			print(f"- [{error.code}] {error.field}: {error.message}")
		return 1

	print("Validation successful.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
