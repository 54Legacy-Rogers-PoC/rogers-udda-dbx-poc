from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import yaml


def _load_validator_module():
	repo_root = Path(__file__).resolve().parents[4]
	script_path = repo_root / "uda" / "scripts" / "object-access" / "validate_request.py"
	spec = importlib.util.spec_from_file_location("validate_request", script_path)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = module
	spec.loader.exec_module(module)
	return module


validator = _load_validator_module()


def _valid_payload() -> dict[str, str]:
	return {
		"request_id": "RITM123456",
		"platform": "databricks",
		"request_type": "object_access",
		"environment": "PRD",
		"activity_type": "ADD",
		"access_for": "ad_group",
		"ad_group_name": "DTB_FINANCE_ANALYTICS",
		"service_account_name": "",
		"template_file": "ObjectAccessTemplate.xlsx",
		"justification": "Required analytics access",
	}


def _write_yaml(path: Path, payload: dict[str, str]) -> None:
	path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _error_codes(errors) -> set[str]:
	return {err.code for err in errors}


def test_valid_request_passes(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()
	(attachments_dir / "ObjectAccessTemplate.xlsx").write_text("", encoding="utf-8")

	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, _valid_payload())

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert errors == []


def test_missing_required_field_returns_yml_002(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()
	(attachments_dir / "ObjectAccessTemplate.xlsx").write_text("", encoding="utf-8")

	payload = _valid_payload()
	payload.pop("environment")
	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, payload)

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert "YML-002" in _error_codes(errors)


def test_invalid_environment_returns_yml_003(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()
	(attachments_dir / "ObjectAccessTemplate.xlsx").write_text("", encoding="utf-8")

	payload = _valid_payload()
	payload["environment"] = "PRODUCTION"
	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, payload)

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert "YML-003" in _error_codes(errors)


def test_bad_request_id_format_returns_yml_004(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()
	(attachments_dir / "ObjectAccessTemplate.xlsx").write_text("", encoding="utf-8")

	payload = _valid_payload()
	payload["request_id"] = "REQ123"
	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, payload)

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert "YML-004" in _error_codes(errors)


def test_request_id_filename_mismatch_returns_yml_005(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()
	(attachments_dir / "ObjectAccessTemplate.xlsx").write_text("", encoding="utf-8")

	payload = _valid_payload()
	payload["request_id"] = "RITM999999"
	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, payload)

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert "YML-005" in _error_codes(errors)


def test_conditional_rule_returns_yml_006(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()
	(attachments_dir / "ObjectAccessTemplate.xlsx").write_text("", encoding="utf-8")

	payload = _valid_payload()
	payload["access_for"] = "service_account"
	payload["service_account_name"] = ""
	payload["ad_group_name"] = "DTB_FINANCE_ANALYTICS"
	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, payload)

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert "YML-006" in _error_codes(errors)


def test_non_xlsx_template_returns_yml_007(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()

	payload = _valid_payload()
	payload["template_file"] = "ObjectAccessTemplate.csv"
	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, payload)

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert "YML-007" in _error_codes(errors)


def test_missing_template_returns_yml_008(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()

	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, _valid_payload())

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert "YML-008" in _error_codes(errors)


def test_xls_template_extension_is_accepted(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()
	(attachments_dir / "ObjectAccessTemplate.xls").write_text("", encoding="utf-8")

	payload = _valid_payload()
	payload["template_file"] = "ObjectAccessTemplate.xls"
	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, payload)

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert errors == []


def test_blank_justification_returns_yml_009(tmp_path: Path) -> None:
	attachments_dir = tmp_path / "attachments"
	attachments_dir.mkdir()
	(attachments_dir / "ObjectAccessTemplate.xlsx").write_text("", encoding="utf-8")

	payload = _valid_payload()
	payload["justification"] = "   "
	request_file = tmp_path / "RITM123456.yaml"
	_write_yaml(request_file, payload)

	errors = validator.validate_request_file(request_file, attachments_dir)
	assert "YML-009" in _error_codes(errors)
