#!/usr/bin/env python3
"""Guard against destroying a grant whose identity key is not in the current request."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _record_key(record: dict[str, Any]) -> str:
    env = _normalize(record.get("environment")).upper()
    access_for = _normalize(record.get("access_for") or record.get("principal_type")).lower()
    principal_name = _normalize(record.get("principal_name")).lower()
    obj_type = _normalize(record.get("object_type")).upper()
    catalog = _normalize(record.get("catalog_name") or record.get("catalog")).lower()
    schema = _normalize(record.get("schema_name") or record.get("schema")).lower()
    object_name = _normalize(record.get("object_name")).lower()
    privilege = _normalize(record.get("privilege")).upper()
    return f"{env}|{access_for}|{principal_name}|{obj_type}|{catalog}|{schema}|{object_name}|{privilege}"


def _resource_key_from_address(address: str) -> str:
    match = re.search(r'\["(.*)"\]$', address)
    if not match:
        return ""
    return match.group(1)


def _current_exact_keys(tfvars_payload: dict[str, Any]) -> set[str]:
    records = tfvars_payload.get("object_access_records", [])
    if not isinstance(records, list):
        return set()
    keys: set[str] = set()
    for record in records:
        if isinstance(record, dict):
            keys.add(_record_key(record))
    return keys


def _destroyed_resource_keys(plan_payload: dict[str, Any]) -> list[str]:
    resource_changes = plan_payload.get("resource_changes", [])
    if not isinstance(resource_changes, list):
        return []

    destroyed: list[str] = []
    for change in resource_changes:
        if not isinstance(change, dict):
            continue
        actions = change.get("change", {}).get("actions", []) if isinstance(change.get("change"), dict) else []
        if not isinstance(actions, list):
            continue
        if "delete" not in actions and "delete_then_create" not in actions:
            continue

        address = _normalize(change.get("address"))
        key = _resource_key_from_address(address)
        if key:
            destroyed.append(key)
    return destroyed


def disallowed_destroy_keys(tfvars_payload: dict[str, Any], plan_payload: dict[str, Any]) -> list[str]:
    valid_keys = _current_exact_keys(tfvars_payload)
    destroyed = _destroyed_resource_keys(plan_payload)
    return [key for key in destroyed if key not in valid_keys]


def _destroyed_addresses(plan_payload: dict[str, Any]) -> list[str]:
    resource_changes = plan_payload.get("resource_changes", [])
    if not isinstance(resource_changes, list):
        return []

    addresses: list[str] = []
    for change in resource_changes:
        if not isinstance(change, dict):
            continue
        actions = change.get("change", {}).get("actions", []) if isinstance(change.get("change"), dict) else []
        if not isinstance(actions, list):
            continue
        if "delete" not in actions and "delete_then_create" not in actions:
            continue
        address = _normalize(change.get("address"))
        if address:
            addresses.append(address)
    return addresses


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Block destroy actions for resources whose exact key is not in the request")
    parser.add_argument("--tfvars-json", required=True, help="Current request tfvars JSON")
    parser.add_argument("--plan-json", required=True, help="Terraform plan JSON")
    parser.add_argument("--state-rm", action="store_true", help="Detach mismatched state entries so only new grants are created")
    parser.add_argument("--working-dir", default=".", help="Terraform working directory for state rm")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tfvars_path = Path(args.tfvars_json)
    plan_path = Path(args.plan_json)

    try:
        with tfvars_path.open("r", encoding="utf-8") as handle:
            tfvars_payload = json.load(handle)
        with plan_path.open("r", encoding="utf-8") as handle:
            plan_payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Exact-match guard failed to read JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(tfvars_payload, dict) or not isinstance(plan_payload, dict):
        print("Exact-match guard requires object JSON payloads", file=sys.stderr)
        return 2

    blocked = disallowed_destroy_keys(tfvars_payload, plan_payload)
    if blocked:
        print("Exact-match destroy guard found unsafe destroy actions:", file=sys.stderr)
        for key in blocked:
            print(f" - {key}", file=sys.stderr)

        if args.state_rm:
            print("Removing mismatched state entries to preserve the current grant set while allowing new grants to be added.", file=sys.stderr)
            for address in _destroyed_addresses(plan_payload):
                key = _resource_key_from_address(address)
                if key and key in blocked:
                    print(f"Terraform state rm {address}", file=sys.stderr)
                    import subprocess
                    result = subprocess.run(["terraform", "-chdir=" + args.working_dir, "state", "rm", address], capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"Removed stale state entry: {address}", file=sys.stderr)
                    else:
                        print(result.stdout, file=sys.stderr)
                        print(result.stderr, file=sys.stderr)
                        print(f"Failed to remove stale state entry: {address}", file=sys.stderr)
            print("Unsafe destroy actions were detached from state; new grants may be added without destroying the old mismatched resource.", file=sys.stderr)
            return 0

        print("No destroy will be applied unless the full exact identity key is present in the current request.", file=sys.stderr)
        return 1

    print("Exact-match destroy guard passed: all destroy actions match current exact keys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
