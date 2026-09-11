#!/usr/bin/env python3
"""Merge an object-access request into the persistent active-grants manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _normalize(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _key(record: dict[str, Any]) -> str:
    return "|".join(
        [
            _normalize(record.get("environment")).upper(),
            _normalize(record.get("access_for") or record.get("principal_type")).lower(),
            _normalize(record.get("principal_name")).lower(),
            _normalize(record.get("object_type")).upper(),
            _normalize(record.get("catalog_name") or record.get("catalog")).lower(),
            _normalize(record.get("schema_name") or record.get("schema")).lower(),
            _normalize(record.get("object_name")).lower(),
            _normalize(record.get("privilege")).upper(),
        ]
    )


def _active_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    normalized["activity"] = "ADD"
    normalized["environment"] = _normalize(record.get("environment")).upper()
    normalized["access_for"] = _normalize(record.get("access_for") or record.get("principal_type")).lower()
    normalized["principal_name"] = _normalize(record.get("principal_name")).lower()
    normalized["object_type"] = _normalize(record.get("object_type")).upper()
    normalized["catalog"] = _normalize(record.get("catalog_name") or record.get("catalog")).lower()
    normalized["schema"] = _normalize(record.get("schema_name") or record.get("schema")).lower()
    normalized["object_name"] = _normalize(record.get("object_name")).lower()
    normalized["privilege"] = _normalize(record.get("privilege")).upper()
    return normalized


def _state_records(state_payload: dict[str, Any]) -> list[dict[str, Any]]:
    values = state_payload.get("values", {})
    root = values.get("root_module", {}) if isinstance(values, dict) else {}
    modules = [root]
    modules.extend(root.get("child_modules", []) if isinstance(root, dict) else [])
    records: list[dict[str, Any]] = []

    for module in modules:
        if not isinstance(module, dict):
            continue
        for resource in module.get("resources", []):
            if not isinstance(resource, dict) or resource.get("type") != "databricks_grant":
                continue
            key = _normalize(resource.get("index"))
            parts = key.split("|")
            if len(parts) != 8:
                continue
            env, access_for, principal, object_type, catalog, schema, object_name, privilege = parts
            records.append(
                {
                    "record_id": f"state-{key}",
                    "activity": "ADD",
                    "environment": env,
                    "access_for": access_for,
                    "principal_name": principal,
                    "object_type": object_type,
                    "catalog": catalog,
                    "schema": schema,
                    "object_name": object_name,
                    "folder_path": "",
                    "privilege": privilege,
                    "privileges": [privilege],
                    "justification": "Recovered from Terraform state",
                    "additional_information": "",
                    "row_number": 0,
                }
            )
    return records


def merge_active_grants(
    request_payload: dict[str, Any],
    manifest_payload: dict[str, Any],
    state_payload: dict[str, Any],
) -> dict[str, Any]:
    active: dict[str, dict[str, Any]] = {}
    for source in (manifest_payload.get("object_access_records", []), _state_records(state_payload)):
        if not isinstance(source, list):
            continue
        for record in source:
            if isinstance(record, dict):
                active[_key(record)] = _active_record(record)

    request_records = request_payload.get("object_access_records", [])
    if not isinstance(request_records, list):
        raise ValueError("Request object_access_records must be a list")

    for record in request_records:
        if not isinstance(record, dict):
            continue
        key = _key(record)
        activity = _normalize(record.get("activity")).upper()
        if activity == "ADD":
            active[key] = _active_record(record)
        elif activity in {"REMOVE", "REVOKE"}:
            active.pop(key, None)
        else:
            raise ValueError(f"Unsupported object-access activity: {activity}")

    records = [active[key] for key in sorted(active)]
    environments = sorted({_normalize(record.get("environment")).upper() for record in records if record.get("environment")})
    return {
        "request_id": _normalize(request_payload.get("request_id")),
        "environment": environments[0] if len(environments) == 1 else _normalize(request_payload.get("environment")).upper(),
        "record_count": len(records),
        "activities": ["ADD"] if records else [],
        "access_for_types": sorted({_normalize(record.get("access_for")).lower() for record in records if record.get("access_for")}),
        "object_access_records": records,
    }


def _load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge a request into the persistent active-grants manifest")
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--manifest-json", required=True)
    parser.add_argument("--state-json", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    result = merge_active_grants(
        _load_optional(Path(args.request_json)),
        _load_optional(Path(args.manifest_json)),
        _load_optional(Path(args.state_json)),
    )
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Active grants manifest written: {output}")
    print(f"Active grant count: {result['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())