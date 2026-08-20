"""Validate Databricks object access Excel templates.

This script validates worksheet structure and row-level object access rules before
Terraform plan/apply execution.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
	import yaml
except ImportError as exc:  # pragma: no cover - runtime dependency
	raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from exc

try:
	from openpyxl import load_workbook
except ImportError as exc:  # pragma: no cover - runtime dependency
	raise SystemExit("openpyxl is required. Install with: pip install openpyxl") from exc


REQUIRED_COLUMNS = [
	"Record_ID",
	"Activity",
	"Environment",
	"Access_For",
	"Principal_Name",
	"Object_Type",
	"Catalog",
	"Schema",
	"Object_Name",
	"Folder_Path",
	"Privilege",
	"Justification",
]

OPTIONAL_COLUMNS = ["Additional_Information"]

ALLOWED_ACTIVITY = {"ADD", "REMOVE"}
ALLOWED_ENV = {"DEV", "QA", "PRD"}
ALLOWED_ACCESS_FOR = {"ad_group", "service_account"}
ALLOWED_OBJECT_TYPES = {"CATALOG", "SCHEMA", "VIEW", "FOLDER"}

ALLOWED_PRIVILEGES = {
	"CATALOG": {"USE_CATALOG"},
	"SCHEMA": {"USE_SCHEMA", "CREATE_TABLE", "CREATE_VIEW"},
	"VIEW": {"SELECT"},
	"FOLDER": {"READ", "WRITE", "READ_WRITE"},
}

DUPLICATE_FIELDS = [
	"Activity",
	"Environment",
	"Access_For",
	"Principal_Name",
	"Object_Type",
	"Catalog",
	"Schema",
	"Object_Name",
	"Folder_Path",
	"Privilege",
]


@dataclass
class ValidationError:
	code: str
	row: int
	field: str
	message: str


def _normalize(value: Any) -> str:
	if value is None:
		return ""
	return str(value).strip()


def _is_blank(value: Any) -> bool:
	return _normalize(value) == ""


def _read_request_context(request_file: Path | None) -> dict[str, str]:
	if request_file is None:
		return {}

	with request_file.open("r", encoding="utf-8") as handle:
		payload = yaml.safe_load(handle)

	if not isinstance(payload, dict):
		return {}

	return {
		"environment": _normalize(payload.get("environment")),
		"access_for": _normalize(payload.get("access_for")),
		"activity_type": _normalize(payload.get("activity_type")),
		"ad_group_name": _normalize(payload.get("ad_group_name")),
		"service_account_name": _normalize(payload.get("service_account_name")),
	}


def _load_rows(template_file: Path, sheet_name: str) -> tuple[list[dict[str, Any]], list[ValidationError]]:
	if not template_file.exists():
		return [], [
			ValidationError(
				code="TPL-001",
				row=0,
				field="template_file",
				message=f"Template file not found: {template_file}",
			)
		]

	try:
		workbook = load_workbook(filename=template_file, data_only=True)
	except Exception as exc:  # pylint: disable=broad-except
		return [], [
			ValidationError(
				code="TPL-001",
				row=0,
				field="template_file",
				message=f"Template file unreadable: {exc}",
			)
		]

	if sheet_name not in workbook.sheetnames:
		return [], [
			ValidationError(
				code="TPL-002",
				row=0,
				field="worksheet",
				message=f"Worksheet not found: {sheet_name}",
			)
		]

	sheet = workbook[sheet_name]
	header_cells = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
	headers = [_normalize(v) for v in (header_cells or [])]

	missing = [c for c in REQUIRED_COLUMNS if c not in headers]
	if missing:
		return [], [
			ValidationError(
				code="TPL-003",
				row=1,
				field="columns",
				message=f"Missing required columns: {', '.join(missing)}",
			)
		]

	records: list[dict[str, Any]] = []
	for row_idx, row_values in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
		row_dict = {headers[i]: row_values[i] if i < len(row_values) else None for i in range(len(headers))}
		# Ignore fully empty rows.
		if all(_is_blank(v) for v in row_dict.values()):
			continue
		row_dict["_row"] = row_idx
		records.append(row_dict)

	return records, []


def _validate_row_required(record: dict[str, Any], request_context: dict[str, str]) -> list[ValidationError]:
	errors: list[ValidationError] = []
	row_no = record["_row"]

	mandatory_fields = [
		"Record_ID",
		"Environment",
		"Access_For",
		"Principal_Name",
		"Object_Type",
		"Privilege",
		"Justification",
	]

	for field in mandatory_fields:
		if _is_blank(record.get(field)):
			errors.append(
				ValidationError(
					code="TPL-010",
					row=row_no,
					field=field,
					message=f"Mandatory field is blank: {field}",
				)
			)

	activity = _normalize(record.get("Activity"))
	if activity == "" and request_context.get("activity_type", "") == "":
		errors.append(
			ValidationError(
				code="TPL-010",
				row=row_no,
				field="Activity",
				message="Activity is blank and no request-level activity_type was provided",
			)
		)

	return errors


def _validate_row_enums(record: dict[str, Any], request_context: dict[str, str]) -> list[ValidationError]:
	errors: list[ValidationError] = []
	row_no = record["_row"]

	activity = _normalize(record.get("Activity"))
	if activity == "":
		activity = request_context.get("activity_type", "")
	if activity and activity.upper() not in ALLOWED_ACTIVITY:
		errors.append(
			ValidationError(
				code="TPL-004",
				row=row_no,
				field="Activity",
				message="Invalid Activity value",
			)
		)

	environment = _normalize(record.get("Environment")).upper()
	if environment and environment not in ALLOWED_ENV:
		errors.append(
			ValidationError(
				code="TPL-004",
				row=row_no,
				field="Environment",
				message="Invalid Environment value",
			)
		)

	access_for = _normalize(record.get("Access_For")).lower()
	if access_for and access_for not in ALLOWED_ACCESS_FOR:
		errors.append(
			ValidationError(
				code="TPL-004",
				row=row_no,
				field="Access_For",
				message="Invalid Access_For value",
			)
		)

	object_type = _normalize(record.get("Object_Type")).upper()
	if object_type and object_type not in ALLOWED_OBJECT_TYPES:
		errors.append(
			ValidationError(
				code="TPL-004",
				row=row_no,
				field="Object_Type",
				message="Invalid Object_Type value",
			)
		)

	return errors


def _validate_conditional_fields(record: dict[str, Any]) -> list[ValidationError]:
	errors: list[ValidationError] = []
	row_no = record["_row"]
	object_type = _normalize(record.get("Object_Type")).upper()

	catalog = _normalize(record.get("Catalog"))
	schema = _normalize(record.get("Schema"))
	object_name = _normalize(record.get("Object_Name"))
	folder_path = _normalize(record.get("Folder_Path"))

	if object_type == "CATALOG":
		if catalog == "" or schema or object_name or folder_path:
			errors.append(
				ValidationError(
					code="TPL-005",
					row=row_no,
					field="Object_Type",
					message="CATALOG requires Catalog and disallows Schema/Object_Name/Folder_Path",
				)
			)

	if object_type == "SCHEMA":
		if catalog == "" or schema == "" or object_name or folder_path:
			errors.append(
				ValidationError(
					code="TPL-005",
					row=row_no,
					field="Object_Type",
					message="SCHEMA requires Catalog and Schema and disallows Object_Name/Folder_Path",
				)
			)

	if object_type == "VIEW":
		if catalog == "" or schema == "" or object_name == "" or folder_path:
			errors.append(
				ValidationError(
					code="TPL-005",
					row=row_no,
					field="Object_Type",
					message="VIEW requires Catalog/Schema/Object_Name and disallows Folder_Path",
				)
			)

	if object_type == "FOLDER":
		if folder_path == "" or catalog or schema or object_name:
			errors.append(
				ValidationError(
					code="TPL-005",
					row=row_no,
					field="Object_Type",
					message="FOLDER requires Folder_Path and disallows Catalog/Schema/Object_Name",
				)
			)

	return errors


def _validate_privilege(record: dict[str, Any]) -> list[ValidationError]:
	row_no = record["_row"]
	object_type = _normalize(record.get("Object_Type")).upper()
	privilege = _normalize(record.get("Privilege")).upper()

	if object_type not in ALLOWED_PRIVILEGES:
		return []

	if privilege not in ALLOWED_PRIVILEGES[object_type]:
		return [
			ValidationError(
				code="TPL-007",
				row=row_no,
				field="Privilege",
				message=(
					f"Invalid privilege for {object_type}. "
					f"Allowed: {sorted(ALLOWED_PRIVILEGES[object_type])}"
				),
			)
		]

	return []


def _validate_cross_field_consistency(record: dict[str, Any], request_context: dict[str, str]) -> list[ValidationError]:
	errors: list[ValidationError] = []
	row_no = record["_row"]

	row_env = _normalize(record.get("Environment")).upper()
	row_access_for = _normalize(record.get("Access_For")).lower()
	row_principal = _normalize(record.get("Principal_Name"))

	expected_env = request_context.get("environment", "")
	expected_access_for = request_context.get("access_for", "")

	if expected_env and row_env and row_env != expected_env:
		errors.append(
			ValidationError(
				code="TPL-008",
				row=row_no,
				field="Environment",
				message=f"Row environment {row_env} does not match request environment {expected_env}",
			)
		)

	if expected_access_for and row_access_for and row_access_for != expected_access_for:
		errors.append(
			ValidationError(
				code="TPL-008",
				row=row_no,
				field="Access_For",
				message=(
					f"Row access_for {row_access_for} does not match "
					f"request access_for {expected_access_for}"
				),
			)
		)

	expected_principal = ""
	if expected_access_for == "ad_group":
		expected_principal = request_context.get("ad_group_name", "")
	elif expected_access_for == "service_account":
		expected_principal = request_context.get("service_account_name", "")

	if expected_principal and row_principal and row_principal != expected_principal:
		errors.append(
			ValidationError(
				code="TPL-008",
				row=row_no,
				field="Principal_Name",
				message=(
					f"Row principal {row_principal} does not match request principal "
					f"{expected_principal}"
				),
			)
		)

	return errors


def _validate_duplicates(records: list[dict[str, Any]], request_context: dict[str, str]) -> list[ValidationError]:
	errors: list[ValidationError] = []
	seen: dict[tuple[str, ...], int] = {}

	for record in records:
		activity = _normalize(record.get("Activity"))
		if activity == "":
			activity = request_context.get("activity_type", "")

		key_parts = []
		for field in DUPLICATE_FIELDS:
			if field == "Activity":
				key_parts.append(activity.upper())
			elif field == "Environment":
				key_parts.append(_normalize(record.get(field)).upper())
			elif field == "Access_For":
				key_parts.append(_normalize(record.get(field)).lower())
			elif field == "Object_Type":
				key_parts.append(_normalize(record.get(field)).upper())
			elif field == "Privilege":
				key_parts.append(_normalize(record.get(field)).upper())
			else:
				key_parts.append(_normalize(record.get(field)))

		key = tuple(key_parts)
		if key in seen:
			first_row = seen[key]
			errors.append(
				ValidationError(
					code="TPL-006",
					row=record["_row"],
					field="row",
					message=f"Duplicate row detected (first occurrence at row {first_row})",
				)
			)
		else:
			seen[key] = record["_row"]

	return errors


def validate_template_file(
	template_file: Path,
	request_file: Path | None = None,
	sheet_name: str = "ObjectAccess",
	max_rows: int = 1000,
) -> list[ValidationError]:
	request_context = _read_request_context(request_file)

	rows, load_errors = _load_rows(template_file, sheet_name)
	if load_errors:
		return load_errors

	errors: list[ValidationError] = []

	if len(rows) > max_rows:
		errors.append(
			ValidationError(
				code="TPL-009",
				row=0,
				field="row_count",
				message=f"Template contains {len(rows)} rows; max allowed is {max_rows}",
			)
		)

	for record in rows:
		errors.extend(_validate_row_required(record, request_context))
		errors.extend(_validate_row_enums(record, request_context))
		errors.extend(_validate_conditional_fields(record))
		errors.extend(_validate_privilege(record))
		errors.extend(_validate_cross_field_consistency(record, request_context))

	errors.extend(_validate_duplicates(rows, request_context))
	return errors


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Validate object access template workbook")
	parser.add_argument("--template-file", required=True, help="Path to ObjectAccessTemplate.xlsx")
	parser.add_argument("--request-file", help="Path to request YAML file for cross-field checks")
	parser.add_argument("--sheet-name", default="ObjectAccess", help="Worksheet name")
	parser.add_argument("--max-rows", default=1000, type=int, help="Maximum allowed data rows")
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	template_file = Path(args.template_file).resolve()
	request_file = Path(args.request_file).resolve() if args.request_file else None

	errors = validate_template_file(
		template_file=template_file,
		request_file=request_file,
		sheet_name=args.sheet_name,
		max_rows=args.max_rows,
	)

	if errors:
		print("Template validation failed.")
		for err in errors:
			print(f"- [{err.code}] row={err.row} field={err.field}: {err.message}")
		return 1

	print("Template validation successful.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
