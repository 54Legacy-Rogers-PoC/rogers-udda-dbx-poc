from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_generator_module():
	repo_root = Path(__file__).resolve().parents[4]
	script_path = repo_root / "uda" / "scripts" / "object-access" / "generate_tfvars.py"
	spec = importlib.util.spec_from_file_location("generate_tfvars", script_path)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = module
	spec.loader.exec_module(module)
	return module


generator = _load_generator_module()


def _parsed_payload(records: list[dict]) -> dict:
	return {
		"request_id": "RITM123456",
		"record_count": len(records),
		"records": records,
	}


def _record(**overrides):
	base = {
		"record_id": "OA-0001",
		"activity": "ADD",
		"environment": "PRD",
		"access_for": "ad_group",
		"principal_name": "DTB_FINANCE_ANALYTICS",
		"object_type": "SCHEMA",
		"catalog": "fin_prd",
		"schema": "gl",
		"object_name": "",
		"folder_path": "",
		"privilege": "USE_SCHEMA",
		"justification": "Finance reporting access",
		"additional_information": "",
		"row_number": 2,
	}
	base.update(overrides)
	return base


def test_build_tfvars_payload_valid_mapping() -> None:
	payload = _parsed_payload([_record()])

	result = generator.build_tfvars_payload(payload)

	assert result["request_id"] == "RITM123456"
	assert result["environment"] == "PRD"
	assert result["record_count"] == 1
	assert result["activities"] == ["ADD"]
	assert result["access_for_types"] == ["ad_group"]
	assert result["object_access_records"][0]["principal_name"] == "DTB_FINANCE_ANALYTICS"


def test_build_tfvars_payload_deterministic_ordering() -> None:
	first = _record(record_id="OA-0002", object_type="VIEW", schema="sales", object_name="v_daily", privilege="SELECT")
	second = _record(record_id="OA-0001", object_type="SCHEMA", schema="gl", privilege="USE_SCHEMA")
	payload = _parsed_payload([first, second])

	result = generator.build_tfvars_payload(payload)

	ordered_ids = [r["record_id"] for r in result["object_access_records"]]
	assert ordered_ids == ["OA-0001", "OA-0002"]


def test_build_tfvars_payload_mixed_activities_preserved() -> None:
	add_row = _record(record_id="OA-0001", activity="ADD")
	remove_row = _record(record_id="OA-0002", activity="REMOVE")
	payload = _parsed_payload([add_row, remove_row])

	result = generator.build_tfvars_payload(payload)

	assert result["activities"] == ["ADD", "REMOVE"]


def test_build_tfvars_payload_optional_fields_normalized() -> None:
	row = _record(additional_information=None, folder_path=None, object_name=None)
	payload = _parsed_payload([row])

	result = generator.build_tfvars_payload(payload)
	out = result["object_access_records"][0]

	assert out["additional_information"] == ""
	assert out["folder_path"] == ""
	assert out["object_name"] == ""


def test_build_tfvars_payload_multiple_environments_fail() -> None:
	prd = _record(record_id="OA-0001", environment="PRD")
	qa = _record(record_id="OA-0002", environment="QA")
	payload = _parsed_payload([prd, qa])

	with pytest.raises(ValueError, match="multiple environments"):
		generator.build_tfvars_payload(payload)


def test_load_json_validates_required_shape(tmp_path: Path) -> None:
	input_json = tmp_path / "parsed.json"
	input_json.write_text(json.dumps({"request_id": "R1", "records": []}), encoding="utf-8")

	with pytest.raises(ValueError, match="missing required keys"):
		generator._load_json(input_json)
