"""Parse Databricks object access template into normalized records.

This script converts ObjectAccess worksheet rows into a consistent JSON structure
used by tfvars generation and Terraform provisioning stages.
"""

from __future__ import annotations

import argparse
import json
import os
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
	from template_common import (  # pylint: disable=import-error
		COMPACT_REQUIRED_COLUMNS,
		HEADER_ALIASES,
		REQUIRED_COLUMNS,
		extract_headers_and_start_row,
		header_key,
		load_workbook_compat,
		merge_context,
		normalize,
		normalize_environment,
		read_workbook_context,
		select_required_columns,
	)
except ImportError as exc:  # pragma: no cover - runtime dependency
	raise SystemExit("Shared helpers are missing. Ensure template_common.py is present.") from exc

def _normalize_activity(value: str) -> str:
	mapped = {
		"ADD": "ADD",
		"ADD OBJECT": "ADD",
		"ADD OBJECTS": "ADD",
		"REMOVE": "REMOVE",
		"REMOVE OBJECT": "REMOVE",
		"REMOVE OBJECTS": "REMOVE",
		"REVOKE": "REMOVE",
	}
	upper = value.upper()
	return mapped.get(upper, upper)


def _is_blank(value: Any) -> bool:
	return normalize(value) == ""


def _default_privilege(object_type: str) -> str:
	defaults = {
		"CATALOG": "USE_CATALOG",
		"SCHEMA": "USE_SCHEMA",
		"VIEW": "SELECT",
		"FOLDER": "READ",
	}
	return defaults.get(object_type.upper(), "")


def _canonical_headers(raw_headers: list[str]) -> list[str]:
	canonical_headers: list[str] = []
	header_alias_keys: dict[str, set[str]] = {
		canonical: {header_key(alias) for alias in aliases}
		for canonical, aliases in HEADER_ALIASES.items()
	}

	for header in raw_headers:
		if header == "":
			canonical_headers.append("")
			continue

		mapped = None
		normalized_header = header_key(header)
		for canonical, aliases in HEADER_ALIASES.items():
			if normalized_header in header_alias_keys[canonical]:
				mapped = canonical
				break

		canonical_headers.append(mapped or header)

	return canonical_headers


def _read_request_context(request_file: Path | None) -> dict[str, str]:
	if request_file is None:
		return {}

	with request_file.open("r", encoding="utf-8") as handle:
		payload = yaml.safe_load(handle)

	if not isinstance(payload, dict):
		return {}

	access_for = normalize(payload.get("access_for")).lower()
	principal_name = ""
	if access_for == "ad_group":
		principal_name = normalize(payload.get("ad_group_name"))
	elif access_for == "service_account":
		principal_name = normalize(payload.get("service_account_name"))

	return {
		"request_id": normalize(payload.get("request_id")),
		"environment": normalize(payload.get("environment")).upper(),
		"access_for": access_for,
		"activity_type": normalize(payload.get("activity_type")).upper(),
		"principal_name": principal_name,
		"justification": normalize(payload.get("justification")),
	}


def _read_workbook_context(template_file: Path) -> dict[str, str]:
	context = read_workbook_context(template_file, _normalize_activity, swallow_errors=False)
	return {
		"environment": context.get("environment", ""),
		"access_for": context.get("access_for", ""),
		"activity_type": context.get("activity_type", ""),
		"principal_name": context.get("principal_name", ""),
	}


def _load_rows(template_file: Path, sheet_name: str) -> tuple[list[dict[str, Any]], list[str]]:
	if not template_file.exists():
		raise FileNotFoundError(f"Template file not found: {template_file}")

	workbook, tmp_path = load_workbook_compat(template_file)
	try:
		if sheet_name not in workbook.sheetnames:
			raise ValueError(f"Worksheet not found: {sheet_name}")

		sheet = workbook[sheet_name]
		headers, min_row = extract_headers_and_start_row(sheet, _canonical_headers)
		required_columns = select_required_columns(headers, COMPACT_REQUIRED_COLUMNS, REQUIRED_COLUMNS)
		missing = [column for column in required_columns if column not in headers]
		if missing:
			raise ValueError(f"Missing required columns: {', '.join(missing)}")

		rows: list[dict[str, Any]] = []
		for row_idx, row_values in enumerate(sheet.iter_rows(min_row=min_row, values_only=True), start=min_row):
			row_dict = {headers[i]: row_values[i] if i < len(row_values) else None for i in range(len(headers))}
			if all(_is_blank(v) for v in row_dict.values()):
				continue
			row_dict["_row"] = row_idx
			rows.append(row_dict)

		return rows, headers
	finally:
		if tmp_path:
			try:
				os.unlink(tmp_path)
			except OSError:
				pass


def _normalize_row(row: dict[str, Any], request_context: dict[str, str]) -> dict[str, Any]:
	row_activity = normalize(row.get("Activity")).upper()
	row_environment = normalize(row.get("Environment")).upper()
	row_access_for = normalize(row.get("Access_For")).lower()
	row_principal = normalize(row.get("Principal_Name"))

	activity = _normalize_activity(row_activity or request_context.get("activity_type", ""))
	environment = normalize_environment(row_environment or request_context.get("environment", ""))
	access_for = row_access_for or request_context.get("access_for", "")
	principal_name = row_principal or request_context.get("principal_name", "")
	catalog = normalize(row.get("Catalog"))
	schema = normalize(row.get("Schema"))
	object_name = normalize(row.get("Object_Name"))
	folder_path = normalize(row.get("Folder_Path"))

	object_type = normalize(row.get("Object_Type")).upper()
	if object_type == "":
		if folder_path != "":
			object_type = "FOLDER"
		elif object_name != "":
			object_type = "VIEW"
		elif schema != "":
			object_type = "SCHEMA"
		elif catalog != "":
			object_type = "CATALOG"

	privilege = normalize(row.get("Privilege")).upper() or _default_privilege(object_type)
	record_id = normalize(row.get("Record_ID")) or f"ROW-{row['_row']:04d}"
	justification = normalize(row.get("Justification")) or request_context.get("justification", "")

	return {
		"row_number": row["_row"],
		"record_id": record_id,
		"activity": activity,
		"environment": environment,
		"access_for": access_for,
		"principal_name": principal_name,
		"object_type": object_type,
		"catalog": catalog,
		"schema": schema,
		"object_name": object_name,
		"folder_path": folder_path,
		"privilege": privilege,
		"justification": justification,
		"additional_information": normalize(row.get("Additional_Information")),
	}


def parse_template_file(
	template_file: Path,
	request_file: Path | None = None,
	sheet_name: str = "ObjectAccess",
) -> dict[str, Any]:
	request_context = _read_request_context(request_file)
	workbook_context = _read_workbook_context(template_file)
	request_context = merge_context(request_context, workbook_context)
	rows, headers = _load_rows(template_file=template_file, sheet_name=sheet_name)
	records = [_normalize_row(row, request_context) for row in rows]
	request_id = request_context.get("request_id", "") or template_file.stem

	return {
		"request_id": request_id,
		"sheet_name": sheet_name,
		"header_columns": headers,
		"record_count": len(records),
		"records": records,
	}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Parse object access template workbook")
	parser.add_argument("--template-file", required=True, help="Path to ObjectAccessTemplate.xlsx")
	parser.add_argument("--request-file", help="Path to request YAML file")
	parser.add_argument("--sheet-name", default="ObjectAccess", help="Worksheet name")
	parser.add_argument("--output-file", help="Output JSON file path")
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	template_file = Path(args.template_file).resolve()
	request_file = Path(args.request_file).resolve() if args.request_file else None

	try:
		parsed = parse_template_file(
			template_file=template_file,
			request_file=request_file,
			sheet_name=args.sheet_name,
		)
	except Exception as exc:  # pylint: disable=broad-except
		print(f"Parse failed: {exc}")
		return 1

	json_payload = json.dumps(parsed, indent=2)
	if args.output_file:
		output_file = Path(args.output_file).resolve()
		output_file.parent.mkdir(parents=True, exist_ok=True)
		output_file.write_text(json_payload + "\n", encoding="utf-8")
		print(f"Parsed output written: {output_file}")
	else:
		print(json_payload)

	return 0


if __name__ == "__main__":
	sys.exit(main())
