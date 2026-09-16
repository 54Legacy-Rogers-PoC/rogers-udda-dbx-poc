#!/usr/bin/env python3
"""Validate the live Databricks cluster permission state against the requested manifest."""

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


def _principal_name(value: Any) -> str:
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


def _permission_values(assignment: dict[str, Any]) -> list[str]:
    values: list[str] = []

    permission_level = assignment.get("permission_level")
    if isinstance(permission_level, str):
        values.append(permission_level)
    elif permission_level is not None:
        values.append(str(permission_level))

    all_permissions = assignment.get("all_permissions")
    if isinstance(all_permissions, list):
        for item in all_permissions:
            if isinstance(item, dict):
                item_level = item.get("permission_level")
                if item_level is not None:
                    values.append(str(item_level))

    return values


def _access_control_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        entries = payload.get("access_control_list")
        if isinstance(entries, list):
            return [item for item in entries if isinstance(item, dict)]
    return []


def _get_databricks_token(host: str) -> str:
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
        raise RuntimeError("Missing Databricks OAuth settings: DB_OAUTH_CLIENT_ID / DB_OAUTH_CLIENT_SECRET")

    token_url = f"{host.rstrip('/')}/oidc/v1/token"
    response = requests.post(
        token_url,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials", "scope": "all-apis"},
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Databricks OAuth token acquisition failed: {response.status_code} {response.text}")

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("AAD token response did not include an access_token")
    return token


def _fetch_cluster_permissions(host: str, token: str, cluster_id: str) -> dict[str, Any]:
    url = f"{host.rstrip('/')}/api/2.0/permissions/clusters/{cluster_id}"
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if response.status_code == 404:
        raise RuntimeError(f"Cluster permissions not found for cluster_id={cluster_id}")
    if response.status_code != 200:
        raise RuntimeError(f"Cluster permissions query failed: {response.status_code} {response.text}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected cluster permissions response payload")
    return payload


def _has_expected_permission(payload: dict[str, Any], group_name: str, permission_level: str) -> bool:
    desired_group = _principal_name(group_name)
    desired_level = _normalize(permission_level).upper()

    for entry in _access_control_entries(payload):
        current_group = _principal_name(entry.get("group_name") or entry.get("principal_name") or entry.get("user_name"))
        if current_group != desired_group:
            continue
        current_levels = {_normalize(value).upper() for value in _permission_values(entry)}
        if desired_level in current_levels:
            return True
    return False


def validate_manifest(manifest_payload: dict[str, Any], databricks_host: str, databricks_token: str) -> int:
    cluster_id = _normalize(manifest_payload.get("cluster_id") or manifest_payload.get("cluster_name"))
    ad_group_name = _normalize(manifest_payload.get("ad_group_name"))
    permission_level = _normalize(manifest_payload.get("cluster_permission_level") or "CAN_ATTACH_TO").upper()
    activity_type = _normalize(manifest_payload.get("activity_type") or "ADD").upper()

    if not cluster_id or not ad_group_name:
        print("Manifest is missing cluster_id/cluster_name or ad_group_name.", file=sys.stderr)
        return 2

    try:
        token = databricks_token or _get_databricks_token(databricks_host)
        payload = _fetch_cluster_permissions(databricks_host, token, cluster_id)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Databricks validation failed: {exc}", file=sys.stderr)
        return 2

    has_permission = _has_expected_permission(payload, ad_group_name, permission_level)

    if activity_type == "REMOVE":
        if not has_permission:
            print("Live Databricks cluster permissions are absent as expected for this REMOVE request.")
            return 0
        print(
            f"Validation failed because {ad_group_name} still has {permission_level} on cluster {cluster_id}.",
            file=sys.stderr,
        )
        return 1

    if has_permission:
        print(
            f"Live Databricks cluster permissions include {ad_group_name} with {permission_level} on cluster {cluster_id}."
        )
        return 0

    print(
        f"Validation failed because {ad_group_name} does not have {permission_level} on cluster {cluster_id}.",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Databricks live cluster permissions against the request")
    parser.add_argument("--request-metadata-json", required=True)
    parser.add_argument("--databricks-host", required=True)
    parser.add_argument("--databricks-token", default="")
    args = parser.parse_args()

    metadata_path = Path(args.request_metadata_json)
    try:
        manifest_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Unable to read request metadata JSON: {exc}", file=sys.stderr)
        return 2

    return validate_manifest(manifest_payload, args.databricks_host, args.databricks_token)


if __name__ == "__main__":
    raise SystemExit(main())