from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import yaml

openpyxl = __import__("openpyxl")


def _load_generator_module():
	repo_root = Path(__file__).resolve().parents[4]
	script_path = repo_root / "uda" / "scripts" / "object-access" / "generate_request_yaml.py"
	spec = importlib.util.spec_from_file_location("generate_request_yaml", script_path)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = module
	spec.loader.exec_module(module)
	return module


generator = _load_generator_module()


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


def _write_template(path: Path, row: list[str]) -> None:
	workbook = openpyxl.Workbook()
	sheet = workbook.active
	sheet.title = "ObjectAccess"
	sheet.append(HEADERS)
	sheet.append(row)
	workbook.save(path)


def _write_two_sheet_template(path: Path) -> None:
	workbook = openpyxl.Workbook()
	request_sheet = workbook.active
	request_sheet.title = "RequestInfo"
	request_sheet.append(["Form Items", "Form Item Description", "Requestor Entry Info", "Ref Document"])
	request_sheet.append(["Request Date", "", "2026-08-24", ""])
	request_sheet.append(["Requestor Name", "", "Furqan Majeed", ""])
	request_sheet.append(["Requestor Department SCOA", "", "ABC", ""])
	request_sheet.append(["Requestor Department", "", "DEF", ""])
	request_sheet.append(["Request Type", "", "Add objects", ""])
	request_sheet.append(["Environment", "", "Prod", ""])
	request_sheet.append([
		"DTB AD Group Name (only for individual direct access to databricks)",
		"",
		"DTB_FINANCE_ANALYTICS",
		"",
	])
	request_sheet.append([
		"Detailed justification for an data access",
		"",
		"Quarterly close analytics access",
		"",
	])
	request_sheet.append([
		"Group Owner Director/Sr Manager Approval Message",
		"",
		"Approved by business owner",
		"",
	])
	request_sheet.append(["Group Owner Approval Date", "", "2026-08-24", ""])

	object_sheet = workbook.create_sheet("ObjectAccess")
	object_sheet.append(HEADERS)
	object_sheet.append(
		[
			"OA-0001",
			"",
			"",
			"",
			"",
			"SCHEMA",
			"fin_prd",
			"gl",
			"",
			"",
			"USE_SCHEMA",
			"",
			"",
		]
	)

	workbook.save(path)


def test_build_payload_from_template_row() -> None:
	row = {
		"Environment": "PRD",
		"Activity": "ADD",
		"Access_For": "ad_group",
		"Principal_Name": "DTB_FINANCE_ANALYTICS",
		"Justification": "Finance close process",
	}

	payload = generator._build_payload(  # pylint: disable=protected-access
		request_id="RITM123456",
		template_file_name="ObjectAccessTemplate.xlsx",
		request_info={},
		first_row=row,
		platform="databricks",
		request_type="object_access",
		environment="",
		activity_type="",
		access_for="",
		ad_group_name="",
		service_account_name="",
		justification="",
		additional_information="",
	)

	assert payload["environment"] == "PRD"
	assert payload["activity_type"] == "ADD"
	assert payload["access_for"] == "ad_group"
	assert payload["ad_group_name"] == "DTB_FINANCE_ANALYTICS"
	assert payload["service_account_name"] == ""


def test_cli_overrides_template_values(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	output_file = tmp_path / "RITM987654.yaml"

	_write_template(
		template_file,
		[
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
			"Original justification",
			"",
		],
	)

	argv_backup = sys.argv
	try:
		sys.argv = [
			"generate_request_yaml.py",
			"--request-id",
			"RITM987654",
			"--template-file",
			str(template_file),
			"--output-file",
			str(output_file),
			"--environment",
			"QA",
			"--activity-type",
			"REMOVE",
			"--access-for",
			"service_account",
			"--service-account-name",
			"svc_data_pipeline",
			"--justification",
			"Quarterly access cleanup",
		]
		result = generator.main()
	finally:
		sys.argv = argv_backup

	assert result == 0
	loaded = yaml.safe_load(output_file.read_text(encoding="utf-8"))
	assert loaded["request_id"] == "RITM987654"
	assert loaded["environment"] == "QA"
	assert loaded["activity_type"] == "REMOVE"
	assert loaded["access_for"] == "service_account"
	assert loaded["service_account_name"] == "svc_data_pipeline"
	assert loaded["ad_group_name"] == ""


def test_request_info_sheet_populates_yaml(tmp_path: Path) -> None:
	template_file = tmp_path / "ObjectAccessTemplate.xlsx"
	output_file = tmp_path / "RITM123456.yaml"
	_write_two_sheet_template(template_file)

	argv_backup = sys.argv
	try:
		sys.argv = [
			"generate_request_yaml.py",
			"--request-id",
			"RITM123456",
			"--template-file",
			str(template_file),
			"--request-sheet-name",
			"RequestInfo",
			"--sheet-name",
			"ObjectAccess",
			"--output-file",
			str(output_file),
		]
		result = generator.main()
	finally:
		sys.argv = argv_backup

	assert result == 0
	loaded = yaml.safe_load(output_file.read_text(encoding="utf-8"))
	assert loaded["environment"] == "PRD"
	assert loaded["activity_type"] == "ADD"
	assert loaded["access_for"] == "ad_group"
	assert loaded["ad_group_name"] == "DTB_FINANCE_ANALYTICS"
	assert loaded["justification"] == "Quarterly close analytics access"
	assert loaded["request_date"] == "2026-08-24"
	assert loaded["requestor_name"] == "Furqan Majeed"
	assert loaded["requestor_department_scoa"] == "ABC"
	assert loaded["requestor_department"] == "DEF"
	assert loaded["group_owner_approval_message"] == "Approved by business owner"
	assert loaded["group_owner_approval_date"] == "2026-08-24"
