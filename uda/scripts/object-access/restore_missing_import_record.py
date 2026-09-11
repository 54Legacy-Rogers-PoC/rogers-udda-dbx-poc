#!/usr/bin/env python3
"""Restore a stale REMOVE row into the import tfvars payload as an ADD row.

This keeps the Terraform resource config aligned with the current state target so
an import can be retried when the original row was removed from the active config.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


def _normalize(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _target_key(record: dict) -> str:
    env = _normalize(record.get("environment")).upper()
    access_for = _normalize(record.get("access_for") or record.get("principal_type")).lower()
    principal_name = _normalize(record.get("principal_name")).lower()
    obj_type = _normalize(record.get("object_type")).upper()
    catalog = _normalize(record.get("catalog_name") or record.get("catalog")).lower()
    schema = _normalize(record.get("schema_name") or record.get("schema")).lower()
    object_name = _normalize(record.get("object_name")).lower()
    privilege = _normalize(record.get("privilege")).upper()
    return f"{env}|{access_for}|{principal_name}|{obj_type}|{catalog}|{schema}|{object_name}|{privilege}"


def _resource_address(record: dict) -> str:
    env = _normalize(record.get("environment")).upper()
    access_for = _normalize(record.get("access_for") or record.get("principal_type")).lower()
    principal_name = _normalize(record.get("principal_name")).lower()
    obj_type = _normalize(record.get("object_type")).upper()
    catalog = _normalize(record.get("catalog_name") or record.get("catalog")).lower()
    schema = _normalize(record.get("schema_name") or record.get("schema")).lower()
    object_name = _normalize(record.get("object_name")).lower()
    privilege = _normalize(record.get("privilege")).upper()

    if obj_type == "CATALOG":
        return f'module.object_access.databricks_grant.catalog_add["{env}|{access_for}|{principal_name}|CATALOG|{catalog}|{privilege}"]'
    if obj_type == "SCHEMA":
        return f'module.object_access.databricks_grant.schema_add["{env}|{access_for}|{principal_name}|SCHEMA|{catalog}|{schema}|{privilege}"]'
    if obj_type == "VIEW":
        return f'module.object_access.databricks_grant.view_add["{env}|{access_for}|{principal_name}|VIEW|{catalog}|{schema}|{object_name}|{privilege}"]'
    return ""


def _restore_record(payload: dict, target: str) -> bool:
    records = payload.get("object_access_records", [])
    if not isinstance(records, list):
        return False

    existing_targets = {_resource_address(r) for r in records if isinstance(r, dict)}
    if target in existing_targets:
        return True

    match = re.search(r'\["(.*)"\]$', target)
    if not match:
        return False

    normalized = match.group(1)
    parts = normalized.split("|")
    if len(parts) < 7:
        return False

    env, access_for, principal_name, obj_type, catalog, *rest = parts
    if obj_type == "VIEW":
        if len(rest) < 3:
            return False
        schema, object_name, privilege = rest[-3], rest[-2], rest[-1]
    elif obj_type == "SCHEMA":
        if len(rest) < 2:
            return False
        schema, privilege = rest[-2], rest[-1]
        object_name = ""
    elif obj_type == "CATALOG":
        if len(rest) < 1:
            return False
        privilege = rest[-1]
        schema = ""
        object_name = ""
    else:
        return False

    restored = {
        "record_id": f"restored-{env.lower()}-{principal_name}",
        "activity": "ADD",
        "environment": env,
        "access_for": access_for,
        "principal_type": access_for,
        "principal_name": principal_name,
        "object_type": obj_type.upper(),
        "catalog_name": catalog,
        "catalog": catalog,
        "schema_name": schema,
        "schema": schema,
        "object_name": object_name,
        "folder_path": "",
        "privilege": privilege,
        "privileges": [privilege],
        "justification": "Restored for stale revoke import recovery",
        "additional_information": "Recovered from stale import target",
        "row_number": 999999,
    }

    payload["object_access_records"] = records + [restored]
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a missing config entry for a stale Terraform import target")
    parser.add_argument("--input-json", required=True, help="Path to tfvars JSON")
    parser.add_argument("--output-json", required=True, help="Path to emit corrected tfvars JSON")
    parser.add_argument("--target", required=True, help="Terraform import target address to restore")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_json)
    output_path = Path(args.output_json)

    try:
        with input_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to read input JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(payload, dict):
        print("Input JSON root must be an object", file=sys.stderr)
        return 2

    changed = _restore_record(payload, args.target)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    print(f"Restored config entry for target: {args.target}")
    print(f"Record restored: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
