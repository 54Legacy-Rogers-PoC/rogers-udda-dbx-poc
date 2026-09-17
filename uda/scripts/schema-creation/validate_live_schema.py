#!/usr/bin/env python3
"""Validate the live Databricks schema state against a normalized schema-creation request."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Normalized request JSON must be an object")
    return payload


def _get_token(host: str) -> str:
    client_id = _norm(
        os.getenv("DB_OAUTH_CLIENT_ID")
        or os.getenv("TF_VAR_databricks_client_id")
        or os.getenv("DATABRICKS_CLIENT_ID")
    )
    client_secret = _norm(
        os.getenv("DB_OAUTH_CLIENT_SECRET")
        or os.getenv("TF_VAR_databricks_client_secret")
        or os.getenv("DATABRICKS_CLIENT_SECRET")
    )
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing Databricks OAuth settings. Expected DB_OAUTH_CLIENT_ID / DB_OAUTH_CLIENT_SECRET "
            "or TF_VAR_databricks_client_id / TF_VAR_databricks_client_secret."
        )

    response = requests.post(
        f"{host.rstrip('/')}/oidc/v1/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials", "scope": "all-apis"},
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Databricks OAuth token acquisition failed: {response.status_code} {response.text}")

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Databricks token response did not include access_token")
    return token


def _schema_name(payload: dict[str, Any]) -> str:
    if payload.get("sandbox_mode") == "new":
        return _norm(payload.get("sandbox_schema_name"))
    if payload.get("sandbox_schema_name"):
        return _norm(payload.get("sandbox_schema_name"))
    return _norm(payload.get("communitymart_schema_name"))


def _catalog_name(payload: dict[str, Any]) -> str:
    # schema-creation requests are built around a single target catalog per environment.
    if payload.get("communitymart_schema_name"):
        return "main"
    return "main"


def _check_schema_exists(host: str, token: str, catalog: str, schema: str) -> bool:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{host.rstrip('/')}/api/2.1/unity-catalog/schemas/{catalog}.{schema}"
    response = requests.get(url, headers=headers, timeout=60)
    if response.status_code == 404:
        return False
    if response.status_code != 200:
        raise RuntimeError(f"Schema lookup failed for {catalog}.{schema}: {response.status_code} {response.text}")
    return True


def _check_permissions(host: str, token: str, catalog: str, schema: str, owner_name: str) -> bool:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{host.rstrip('/')}/api/2.1/unity-catalog/permissions/schema/{catalog}.{schema}"
    response = requests.get(url, headers=headers, timeout=60)
    if response.status_code == 404:
        return False
    if response.status_code != 200:
        raise RuntimeError(f"Permission lookup failed for {catalog}.{schema}: {response.status_code} {response.text}")

    payload = response.json()
    for item in payload.get("privilege_assignments", []) or []:
        principal = _norm(item.get("principal")).lower()
        if principal == owner_name.lower():
            return True

    for item in payload.get("permissions", []) or []:
        principal = _norm(item.get("principal")).lower()
        if principal == owner_name.lower():
            return True

    return False


def validate_request(request_json: str, host: str) -> int:
    payload = _load_json(request_json)
    catalog = _catalog_name(payload)
    schema = _schema_name(payload)
    if not schema:
        print("Validation failed: no target schema found in normalized request.", file=sys.stderr)
        return 1

    token = _get_token(host)
    if not _check_schema_exists(host, token, catalog, schema):
        print(f"Validation failed: schema {catalog}.{schema} does not exist in Databricks.", file=sys.stderr)
        return 1

    owner_name = _norm(payload.get("sandbox_owner_name") or payload.get("communitymart_owner_name"))
    if not owner_name:
        print("Validation failed: no owner_name available in normalized request.", file=sys.stderr)
        return 1

    if not _check_permissions(host, token, catalog, schema, owner_name):
        print(f"Validation failed: expected owner {owner_name} is not granted access to {catalog}.{schema}.", file=sys.stderr)
        return 1

    print(f"Validation passed: {catalog}.{schema} exists and is accessible to {owner_name}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate live Databricks schema creation state")
    parser.add_argument("--request-json", required=True, help="Path to normalized request JSON")
    parser.add_argument("--databricks-host", required=True, help="Databricks workspace host")
    return validate_request(args.request_json, args.databricks_host)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate live Databricks schema creation state")
    parser.add_argument("--request-json", required=True, help="Path to normalized request JSON")
    parser.add_argument("--databricks-host", required=True, help="Databricks workspace host")
    args = parser.parse_args()
    raise SystemExit(validate_request(args.request_json, args.databricks_host))
