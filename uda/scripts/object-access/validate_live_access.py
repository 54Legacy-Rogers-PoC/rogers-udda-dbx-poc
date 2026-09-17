#!/usr/bin/env python3
"""Validate the live Databricks grant state against the desired manifest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _principal_key(value: Any) -> str:
    principal = _normalize(value).lower()
    for prefix in (
        "user:",
        "group:",
        "service_principal:",
        "serviceprincipal:",
        "spn:",
        "users:",
        "groups:",
        "service_principals:",
    ):
        if principal.startswith(prefix):
            principal = principal[len(prefix):]
    return principal


def _object_key(record: dict[str, Any]) -> str:
    object_type = _normalize(record.get("object_type") or record.get("object_type_upper")).upper()
    catalog = _normalize(record.get("catalog_name") or record.get("catalog")).lower()
    schema = _normalize(record.get("schema_name") or record.get("schema")).lower()
    object_name = _normalize(record.get("object_name")).lower()
    principal = _principal_key(record.get("principal_name"))
    privilege = _normalize(record.get("privilege")).upper()
    return f"{object_type}|{catalog}|{schema}|{object_name}|{principal}|{privilege}"


def _manifest_keys(manifest_payload: dict[str, Any]) -> set[str]:
    records = manifest_payload.get("object_access_records", [])
    if not isinstance(records, list):
        return set()
    return {_object_key(record) for record in records if isinstance(record, dict)}


def _iter_assignments(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    assignments = payload.get("privilege_assignments")
    if isinstance(assignments, list):
        return [item for item in assignments if isinstance(item, dict)]

    permissions = payload.get("permissions")
    if isinstance(permissions, list):
        return [item for item in permissions if isinstance(item, dict)]

    return [payload]


def _extract_live_keys(
    payload: Any,
    object_type: str,
    *,
    catalog_name: str = "",
    schema_name: str = "",
    requested_object_name: str = "",
) -> set[str]:
    live: set[str] = set()
    object_name = _normalize(requested_object_name or payload.get("name") or payload.get("table") or payload.get("schema") or payload.get("catalog")).lower()
    catalog = _normalize(catalog_name or payload.get("catalog_name") or payload.get("catalog")).lower()
    schema = _normalize(schema_name or payload.get("schema_name") or payload.get("schema")).lower()
    if "/" in object_name and object_type == "CATALOG":
        object_name = ""
    for assignment in _iter_assignments(payload):
        principal = _principal_key(assignment.get("principal") or assignment.get("group_name") or assignment.get("user_name") or assignment.get("service_principal_name"))
        privileges = assignment.get("privileges") or assignment.get("permission_level")
        if privileges is None:
            continue
        if isinstance(privileges, str):
            values = [privileges]
        elif isinstance(privileges, list):
            values = privileges
        else:
            values = [str(privileges)]

        for value in values:
            privilege = _normalize(value).upper()
            if not privilege:
                continue
            live.add(f"{object_type}|{catalog}|{schema}|{object_name}|{principal}|{privilege}")
    return live


def get_databricks_token(host: str) -> str:
    client_id = _normalize(
        os.getenv("DB_OAUTH_CLIENT_ID")
        or os.getenv("TF_VAR_databricks_client_id")
        or os.getenv("DATABRICKS_CLIENT_ID")
    )
    client_secret = _normalize(
        os.getenv("DB_OAUTH_CLIENT_SECRET")
        or os.getenv("TF_VAR_databricks_client_secret")
        or os.getenv("DATABRICKS_CLIENT_SECRET")
    )

    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing Databricks OAuth settings. Expected DB_OAUTH_CLIENT_ID / DB_OAUTH_CLIENT_SECRET "
            "or TF_VAR_databricks_client_id / TF_VAR_databricks_client_secret."
        )

    token_url = f"{host.rstrip('/')}/oidc/v1/token"
    payload = {
        "grant_type": "client_credentials",
        "scope": "all-apis",
    }

    response = requests.post(token_url, auth=(client_id, client_secret), data=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"Databricks OAuth token acquisition failed: {response.status_code} {response.text}")

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("AAD token response did not include an access_token")
    return token


def _fetch_databricks_grants(host: str, token: str, desired_records: list[dict[str, Any]]) -> set[str]:
    headers = {"Authorization": f"Bearer {token}"}
    live: set[str] = set()
    unique_catalogs: set[str] = set()
    unique_schemas: set[str] = set()
    unique_tables: dict[str, str] = {}

    for record in desired_records:
        if not isinstance(record, dict):
            continue
        object_type = _normalize(record.get("object_type")).upper()
        catalog = _normalize(record.get("catalog_name") or record.get("catalog")).lower()
        schema = _normalize(record.get("schema_name") or record.get("schema")).lower()
        object_name = _normalize(record.get("object_name")).lower()
        if object_type == "CATALOG" and catalog:
            unique_catalogs.add(catalog)
        elif object_type == "SCHEMA" and catalog and schema:
            unique_schemas.add(f"{catalog}.{schema}")
        elif object_type in {"VIEW", "TABLE"} and catalog and schema and object_name:
            unique_tables[f"{catalog}.{schema}.{object_name}"] = object_type

    for catalog in sorted(unique_catalogs):
        url = f"{host.rstrip('/')}/api/2.1/unity-catalog/permissions/catalog/{catalog}"
        response = requests.get(url, headers=headers, timeout=60)
        if response.status_code == 404:
            continue
        if response.status_code != 200:
            raise RuntimeError(f"Catalog permissions query failed for {catalog}: {response.status_code} {response.text}")
        live |= _extract_live_keys(response.json(), "CATALOG", catalog_name=catalog)

    for full_schema_name in sorted(unique_schemas):
        url = f"{host.rstrip('/')}/api/2.1/unity-catalog/permissions/schema/{full_schema_name}"
        response = requests.get(url, headers=headers, timeout=60)
        if response.status_code == 404:
            continue
        if response.status_code != 200:
            raise RuntimeError(f"Schema permissions query failed for {full_schema_name}: {response.status_code} {response.text}")
        payload = response.json()
        catalog, schema = full_schema_name.split(".", 1)
        live |= _extract_live_keys(payload, "SCHEMA", catalog_name=catalog, schema_name=schema)

    for full_table_name in sorted(unique_tables):
        url = f"{host.rstrip('/')}/api/2.1/unity-catalog/permissions/table/{full_table_name}"
        response = requests.get(url, headers=headers, timeout=60)
        if response.status_code == 404:
            continue
        if response.status_code != 200:
            raise RuntimeError(f"Table permissions query failed for {full_table_name}: {response.status_code} {response.text}")
        catalog, schema, object_name = full_table_name.split(".", 2)
        live |= _extract_live_keys(
            response.json(),
            unique_tables[full_table_name],
            catalog_name=catalog,
            schema_name=schema,
            requested_object_name=object_name,
        )

    return live


def validate_manifest(
    manifest_payload: dict[str, Any],
    databricks_host: str,
    databricks_token: str,
    *,
    fail_on_missing: bool = False,
    expect_absent: bool = False,
    respect_activity: bool = False,
) -> int:
    records = manifest_payload.get("object_access_records", [])
    if not isinstance(records, list):
        print("Manifest does not contain an object_access_records list.", file=sys.stderr)
        return 2

    desired = _manifest_keys(manifest_payload)
    try:
        token = databricks_token or get_databricks_token(databricks_host)
        live = _fetch_databricks_grants(databricks_host, token, records)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Databricks validation failed: {exc}", file=sys.stderr)
        return 2

    if expect_absent:
        remaining = sorted(desired & live)
        if not remaining:
            print("Live Databricks grants are absent as expected for this REMOVE request.")
            return 0
        for key in remaining:
            print(f"EXTRA|{key}")
        print("Validation failed because revoke targets are still present in Databricks.", file=sys.stderr)
        return 1

    if respect_activity:
        present_records = [
            record for record in records
            if isinstance(record, dict)
            and _normalize(record.get("activity") or "ADD").upper() == "ADD"
        ]
        absent_records = [
            record for record in records
            if isinstance(record, dict)
            and _normalize(record.get("activity")).upper() in {"REMOVE", "REVOKE"}
        ]
        expected_present = {_object_key(record) for record in present_records}
        expected_absent = {_object_key(record) for record in absent_records}
        missing = sorted(expected_present - live)
        remaining = sorted(expected_absent & live)
        for key in missing:
            print(f"MISSING|{key}")
        for key in remaining:
            print(f"EXTRA|{key}")
        if missing or remaining:
            print("Validation failed because the live grants do not match request activities.", file=sys.stderr)
            return 1
        print("Live Databricks grants match the requested ADD and REMOVE activities.")
        return 0

    missing = sorted(desired - live)
    extra = sorted(live - desired)

    if not missing and not extra:
        print("Live Databricks grants match the desired manifest exactly.")
        return 0

    for key in sorted(missing):
        print(f"MISSING|{key}")
    for key in sorted(extra):
        print(f"EXTRA|{key}")

    if fail_on_missing and missing:
        print("Validation failed because required grant keys are missing from Databricks.", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Databricks live grants against manifest")
    parser.add_argument("--manifest-json", required=True)
    parser.add_argument("--databricks-host", required=True)
    parser.add_argument("--databricks-token", default="")
    parser.add_argument("--fail-on-missing", action="store_true")
    parser.add_argument("--expect-absent", action="store_true")
    parser.add_argument("--respect-activity", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest_json)
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Unable to read manifest JSON: {exc}", file=sys.stderr)
        return 2

    return validate_manifest(
        manifest_payload,
        args.databricks_host,
        args.databricks_token,
        fail_on_missing=args.fail_on_missing,
        expect_absent=args.expect_absent,
        respect_activity=args.respect_activity,
    )


if __name__ == "__main__":
    raise SystemExit(main())
