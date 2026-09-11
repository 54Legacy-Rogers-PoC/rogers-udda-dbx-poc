#!/usr/bin/env python3
"""Build Terraform revoke target rows for REMOVE/REVOKE object-access requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def _normalize(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _build_target(record: dict) -> tuple[str, str] | None:
    activity = _normalize(record.get("activity")).upper()
    if activity not in {"REMOVE", "REVOKE"}:
        return None

    obj_type = _normalize(record.get("object_type")).upper()
    env = _normalize(record.get("environment")).upper()
    access_for = _normalize(record.get("access_for") or record.get("principal_type")).lower()
    principal_name = _normalize(record.get("principal_name"))
    principal_key = principal_name.lower()
    catalog = _normalize(record.get("catalog_name") or record.get("catalog")).lower()
    schema = _normalize(record.get("schema_name") or record.get("schema")).lower()
    object_name = _normalize(record.get("object_name")).lower()
    privilege = _normalize(record.get("privilege")).upper()

    if obj_type == "CATALOG":
        target = f'module.object_access.databricks_grant.catalog_add["{env}|{access_for}|{principal_key}|CATALOG|{catalog}|{privilege}"]'
        import_id = f"catalog/{catalog}/{principal_name}"
    elif obj_type == "SCHEMA":
        target = f'module.object_access.databricks_grant.schema_add["{env}|{access_for}|{principal_key}|SCHEMA|{catalog}|{schema}|{privilege}"]'
        import_id = f"schema/{catalog}.{schema}/{principal_name}"
    elif obj_type == "VIEW":
        target = f'module.object_access.databricks_grant.view_add["{env}|{access_for}|{principal_key}|VIEW|{catalog}|{schema}|{object_name}|{privilege}"]'
        import_id = f"table/{catalog}.{schema}.{object_name}/{principal_name}"
    else:
        return None

    return target, import_id


def build_revoke_targets(payload: dict) -> list[str]:
    rows: list[str] = []
    for record in payload.get("object_access_records", []):
        built = _build_target(record)
        if built is not None:
            target, import_id = built
            rows.append(f"{target}\t{import_id}")
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Terraform revoke targets for REMOVE/REVOKE rows")
    parser.add_argument("--input-json", required=True, help="Path to object-access auto tfvars JSON")
    parser.add_argument("--output-tsv", required=True, help="Path to write revoke targets TSV")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_json)
    output_path = Path(args.output_tsv)

    try:
        with input_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to read input JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(payload, dict):
        print("Input JSON root must be an object", file=sys.stderr)
        return 2

    rows = build_revoke_targets(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(f"{row}\n")

    print(f"Revoke targets written: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
