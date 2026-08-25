"""Generate Terraform tfvars JSON from parsed object access records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_PARSED_KEYS = {"record_count", "records"}


def _normalize(value: Any) -> str:
	if value is None:
		return ""
	return str(value).strip()


def _load_json(path: Path) -> dict[str, Any]:
	with path.open("r", encoding="utf-8") as handle:
		payload = json.load(handle)

	if not isinstance(payload, dict):
		raise ValueError("Parsed input must be a JSON object")

	missing = REQUIRED_PARSED_KEYS - set(payload.keys())
	if missing:
		raise ValueError(f"Parsed input missing required keys: {sorted(missing)}")

	records = payload.get("records")
	if not isinstance(records, list):
		raise ValueError("Parsed input key 'records' must be a list")

	return payload


def _terraform_record(record: dict[str, Any]) -> dict[str, Any]:
	return {
		"record_id": _normalize(record.get("record_id")),
		"activity": _normalize(record.get("activity")).upper(),
		"environment": _normalize(record.get("environment")).upper(),
		"access_for": _normalize(record.get("access_for")).lower(),
		"principal_name": _normalize(record.get("principal_name")),
		"object_type": _normalize(record.get("object_type")).upper(),
		"catalog": _normalize(record.get("catalog")),
		"schema": _normalize(record.get("schema")),
		"object_name": _normalize(record.get("object_name")),
		"folder_path": _normalize(record.get("folder_path")),
		"privilege": _normalize(record.get("privilege")).upper(),
		"justification": _normalize(record.get("justification")),
		"additional_information": _normalize(record.get("additional_information")),
		"row_number": int(record.get("row_number", 0) or 0),
	}


def build_tfvars_payload(parsed_payload: dict[str, Any]) -> dict[str, Any]:
	records = parsed_payload.get("records", [])
	terraform_records = [_terraform_record(record) for record in records]

	# Keep deterministic ordering for stable plans and easier diff reviews.
	terraform_records = sorted(
		terraform_records,
		key=lambda r: (
			r["environment"],
			r["activity"],
			r["access_for"],
			r["principal_name"],
			r["object_type"],
			r["catalog"],
			r["schema"],
			r["object_name"],
			r["folder_path"],
			r["privilege"],
			r["record_id"],
			r["row_number"],
		),
	)

	environments = sorted({r["environment"] for r in terraform_records if r["environment"]})
	if len(environments) > 1:
		raise ValueError(
			"Parsed records contain multiple environments. "
			f"Expected one environment, found: {environments}"
		)

	environment = environments[0] if environments else _normalize(parsed_payload.get("environment")).upper()
	activities = sorted({r["activity"] for r in terraform_records if r["activity"]})
	access_for_types = sorted({r["access_for"] for r in terraform_records if r["access_for"]})

	return {
		"request_id": _normalize(parsed_payload.get("request_id")),
		"environment": environment,
		"record_count": len(terraform_records),
		"activities": activities,
		"access_for_types": access_for_types,
		"object_access_records": terraform_records,
	}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Generate tfvars from parsed object access records")
	parser.add_argument("--input-json", required=True, help="Path to parsed template JSON")
	parser.add_argument("--output-json", required=True, help="Output tfvars JSON path")
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	input_json = Path(args.input_json).resolve()
	output_json = Path(args.output_json).resolve()

	try:
		parsed_payload = _load_json(input_json)
		tfvars_payload = build_tfvars_payload(parsed_payload)
	except Exception as exc:  # pylint: disable=broad-except
		print(f"tfvars generation failed: {exc}")
		return 1

	output_json.parent.mkdir(parents=True, exist_ok=True)
	output_json.write_text(json.dumps(tfvars_payload, indent=2) + "\n", encoding="utf-8")
	print(f"tfvars generated: {output_json}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
