from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import yaml

openpyxl = __import__("openpyxl")


def _load_validator_module():
	repo_root = Path(__file__).resolve().parents[4]
	script_path = repo_root / "uda" / "scripts" / "object-access" / "validate_template.py"
	spec = importlib.util.spec_from_file_location("validate_template", script_path)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = module
	spec.loader.exec_module(module)
	return module


validator = _load_validator_module()


HEADERS = [
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
	"Additional_Information",
]


def _valid_row() -> list[str]:
	return [
		"OA-0001",
		"ADD",
		"PRD",
		"ad_group",
		"DTB_FINANCE_ANALYTICS",
		"SCHEMA",
		"fin_prd",
		"gl",
		"",
		"",
		"USE_SCHEMA",
		"Finance reporting access",
		"",
	]


def _write_template(path: Path, rows: list[list[str]], headers: list[str] | None = None, sheet_name: str = "ObjectAccess") -> None:
	workbook = openpyxl.Workbook()
	sheet = workbook.active
	sheet.title = sheet_name

	for value in (headers or HEADERS):
		sheet.append([value])

	# Rebuild proper header row explicitly to avoid row-wise append confusion.
	sheet.delete_rows(1, sheet.max_row)
	sheet.append(headers or HEADERS)

	for row in rows:
		sheet.append(row)

	workbook.save(path)


def _write_request(path: Path) -> None:
	payload = {
		"request_id": "RITM123456",
		"platform": "databricks",
		"request_type": "object_access",
		"environment": "PRD",
		"activity_type": "ADD",
		"access_for": "ad_group",
		"ad_group_name": "DTB_FINANCE_ANALYTICS",
		"template_file": "ObjectAccessTemplate.xlsx",
		"justification": "Business need",
	}
	path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _error_codes(errors) -> set[str]:
	return {err.code for err in errors}


def test_valid_template_passes(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	request_file = tmp_path / "RITM123456.yaml"
	_write_template(template_file, [_valid_row()])
	_write_request(request_file)

	errors = validator.validate_template_file(template_file=template_file, request_file=request_file)
	assert errors == []


def test_missing_sheet_returns_tpl_002(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	_write_template(template_file, [_valid_row()], sheet_name="Sheet1")

	errors = validator.validate_template_file(template_file=template_file)
	assert "TPL-002" in _error_codes(errors)


def test_missing_privilege_column_is_allowed_when_inferable(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	bad_headers = [h for h in HEADERS if h != "Privilege"]
	row = _valid_row()
	row.pop(10)
	_write_template(template_file, [row], headers=bad_headers)

	errors = validator.validate_template_file(template_file=template_file)
	assert errors == []


def test_invalid_enum_returns_tpl_004(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	row = _valid_row()
	row[5] = "TABLE"
	_write_template(template_file, [row])

	errors = validator.validate_template_file(template_file=template_file)
	assert "TPL-004" in _error_codes(errors)


def test_conditional_violation_returns_tpl_005(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	row = _valid_row()
	row[5] = "VIEW"
	row[8] = ""
	_write_template(template_file, [row])

	errors = validator.validate_template_file(template_file=template_file)
	assert "TPL-005" in _error_codes(errors)


def test_duplicate_rows_return_tpl_006(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	row = _valid_row()
	_write_template(template_file, [row, row])

	errors = validator.validate_template_file(template_file=template_file)
	assert "TPL-006" in _error_codes(errors)


def test_invalid_privilege_returns_tpl_007(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	row = _valid_row()
	row[5] = "VIEW"
	row[8] = "v_monthly_close"
	row[10] = "WRITE"
	_write_template(template_file, [row])

	errors = validator.validate_template_file(template_file=template_file)
	assert "TPL-007" in _error_codes(errors)


def test_request_mismatch_returns_tpl_008(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	request_file = tmp_path / "RITM123456.yaml"
	row = _valid_row()
	row[2] = "QA"
	_write_template(template_file, [row])
	_write_request(request_file)

	errors = validator.validate_template_file(template_file=template_file, request_file=request_file)
	assert "TPL-008" in _error_codes(errors)


def test_max_rows_returns_tpl_009(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	_write_template(template_file, [_valid_row(), _valid_row()])

	errors = validator.validate_template_file(template_file=template_file, max_rows=1)
	assert "TPL-009" in _error_codes(errors)


def test_blank_mandatory_returns_tpl_010(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	row = _valid_row()
	row[4] = ""
	_write_template(template_file, [row])

	errors = validator.validate_template_file(template_file=template_file)
	assert "TPL-010" in _error_codes(errors)
