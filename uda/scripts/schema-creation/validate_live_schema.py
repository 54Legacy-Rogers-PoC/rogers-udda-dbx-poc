#!/usr/bin/env python3
"""Validate live Databricks resources created by a schema request."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
ENVIRONMENT_MAPPING_FILE = REPO_ROOT / "uda" / "config" / "environment-mapping.yaml"
DEFAULT_EXTERNAL_LOCATION_RW_PRINCIPALS = {"furqan@54legacy.com"}


@dataclass(frozen=True)
class SchemaTarget:
    kind: str
    catalog: str
    schema: str
    owner: str
    storage_root: str
    external_location_name: str = ""
    external_location_url: str = ""
    storage_credential_name: str = ""


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


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"YAML configuration must be an object: {path}")
    return payload


def _load_schema_config(environment: str) -> dict[str, Any]:
    mapping = _load_yaml(ENVIRONMENT_MAPPING_FILE)
    environment_code = _norm(environment).upper()
    config_path = _norm(mapping.get("config_files", {}).get(environment_code))
    if not config_path:
        raise ValueError(f"No environment configuration found for {environment_code}")

    environment_config = _load_yaml(REPO_ROOT / config_path)
    schema_config = environment_config.get("schema_creation")
    if not isinstance(schema_config, dict):
        raise ValueError(f"schema_creation configuration is missing for {environment_code}")
    return schema_config


def _sandbox_container(schema_name: str) -> str:
    parts = schema_name.split("_")
    suffix = "-".join(parts[1:-1]) if len(parts) > 2 else schema_name.replace("_", "-")
    return f"sandbox-{suffix}"


def _build_targets(payload: dict[str, Any], config: dict[str, Any]) -> list[SchemaTarget]:
    targets: list[SchemaTarget] = []
    environment = _norm(payload.get("environment")).lower()

    if _norm(payload.get("sandbox_mode")).lower() == "new":
        schema = _norm(payload.get("sandbox_schema_name")).lower()
        storage_account = _norm(config.get("sandbox_storage_account_name"))
        container = _sandbox_container(schema)
        targets.append(
            SchemaTarget(
                kind="sandbox",
                catalog=_norm(config.get("sandbox_catalog_name")),
                schema=schema,
                owner=_norm(payload.get("sandbox_owner_name")).lower(),
                storage_root=f"abfss://{container}@{storage_account}.dfs.core.windows.net/{schema}",
                external_location_name=f"el_{environment}__{container}__at__{storage_account}__rw",
                external_location_url=f"abfss://{container}@{storage_account}.dfs.core.windows.net/",
                storage_credential_name=_norm(config.get("sandbox_storage_credential_name")),
            )
        )

    if payload.get("create_communitymart_schema") is True:
        schema = _norm(payload.get("communitymart_schema_name")).lower()
        storage_account = _norm(config.get("communitymart_storage_account_name"))
        container = _norm(config.get("communitymart_container_name"))
        prefix = _norm(config.get("communitymart_storage_prefix")).strip("/")
        targets.append(
            SchemaTarget(
                kind="communitymart",
                catalog=_norm(config.get("communitymart_catalog_name")),
                schema=schema,
                owner=_norm(payload.get("communitymart_owner_name")).lower(),
                storage_root=f"abfss://{container}@{storage_account}.dfs.core.windows.net/{prefix}/{schema}",
            )
        )

    return targets


def _normalize_host(host: str) -> str:
    value = _norm(host).rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return value


def _get_token(host: str) -> str:
    host = _normalize_host(host)
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


def _get_resource(host: str, token: str, path: str, description: str) -> dict[str, Any] | None:
    response = requests.get(
        f"{_normalize_host(host)}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise RuntimeError(f"{description} failed: {response.status_code} {response.text}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{description} returned a non-object response")
    return payload


def _has_privileges(payload: dict[str, Any], principal: str, expected: set[str]) -> bool:
    assignments = payload.get("privilege_assignments") or payload.get("permissions") or []
    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue
        actual_principal = _norm(assignment.get("principal")).lower()
        privileges = assignment.get("privileges") or assignment.get("permission_level") or []
        if isinstance(privileges, str):
            privileges = [privileges]
        actual = {_norm(privilege).upper() for privilege in privileges}
        if actual_principal == principal.lower() and expected <= actual:
            return True
    return False


def _same_location(actual: Any, expected: str) -> bool:
    return _norm(actual).rstrip("/").lower() == expected.rstrip("/").lower()


def _validate_target(
    host: str,
    token: str,
    target: SchemaTarget,
    default_principals: set[str],
) -> list[str]:
    errors: list[str] = []
    full_name = f"{target.catalog}.{target.schema}"
    schema = _get_resource(
        host,
        token,
        f"/api/2.1/unity-catalog/schemas/{quote(full_name, safe='.')}",
        f"Schema lookup for {full_name}",
    )
    if schema is None:
        return [f"Schema {full_name} does not exist"]

    actual_storage_root = schema.get("storage_root") or schema.get("storage_location")
    if not _same_location(actual_storage_root, target.storage_root):
        errors.append(
            f"Schema {full_name} storage root mismatch: expected {target.storage_root}, "
            f"found {_norm(actual_storage_root) or '<empty>'}"
        )

    permissions = _get_resource(
        host,
        token,
        f"/api/2.1/unity-catalog/permissions/schema/{quote(full_name, safe='.')}",
        f"Schema permissions lookup for {full_name}",
    )
    if permissions is None or not _has_privileges(permissions, target.owner, {"ALL_PRIVILEGES"}):
        errors.append(f"Owner {target.owner} does not have ALL_PRIVILEGES on schema {full_name}")

    if target.kind != "sandbox":
        return errors

    location_name = quote(target.external_location_name, safe="")
    location = _get_resource(
        host,
        token,
        f"/api/2.1/unity-catalog/external-locations/{location_name}",
        f"External location lookup for {target.external_location_name}",
    )
    if location is None:
        errors.append(f"External location {target.external_location_name} does not exist")
        return errors

    if not _same_location(location.get("url"), target.external_location_url):
        errors.append(
            f"External location {target.external_location_name} URL mismatch: expected "
            f"{target.external_location_url}, found {_norm(location.get('url')) or '<empty>'}"
        )
    if _norm(location.get("credential_name")) != target.storage_credential_name:
        errors.append(
            f"External location {target.external_location_name} credential mismatch: expected "
            f"{target.storage_credential_name}, found {_norm(location.get('credential_name')) or '<empty>'}"
        )

    location_permissions = _get_resource(
        host,
        token,
        f"/api/2.1/unity-catalog/permissions/external-location/{location_name}",
        f"External location permissions lookup for {target.external_location_name}",
    )
    if location_permissions is None or not _has_privileges(
        location_permissions, target.owner, {"READ FILES", "WRITE FILES", "MANAGE"}
    ):
        errors.append(
            f"Owner {target.owner} does not have READ FILES, WRITE FILES, and MANAGE "
            f"on external location {target.external_location_name}"
        )
    for principal in sorted(default_principals - {target.owner}):
        if location_permissions is None or not _has_privileges(
            location_permissions, principal, {"READ FILES", "WRITE FILES"}
        ):
            errors.append(
                f"Default principal {principal} does not have READ FILES and WRITE FILES "
                f"on external location {target.external_location_name}"
            )
    return errors


def _write_report(
    output_json: str | None,
    status: str,
    targets: list[SchemaTarget],
    errors: list[str],
) -> None:
    if not output_json:
        return
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "status": status,
                "targets": [f"{target.catalog}.{target.schema}" for target in targets],
                "errors": errors,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def validate_request(request_json: str, host: str, output_json: str | None = None) -> int:
    payload = _load_json(request_json)
    config = _load_schema_config(_norm(payload.get("environment")))
    targets = _build_targets(payload, config)
    if not targets:
        errors = ["Request does not contain a schema creation target"]
        _write_report(output_json, "failed", targets, errors)
        print(f"Validation failed: {errors[0]}.", file=sys.stderr)
        return 1

    token = _get_token(host)
    errors: list[str] = []
    for target in targets:
        errors.extend(_validate_target(host, token, target, DEFAULT_EXTERNAL_LOCATION_RW_PRINCIPALS))

    if errors:
        _write_report(output_json, "failed", targets, errors)
        print("Databricks schema validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    validated = ", ".join(f"{target.catalog}.{target.schema}" for target in targets)
    _write_report(output_json, "validated", targets, [])
    print(f"Validation passed for live Databricks resources: {validated}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate live Databricks schema creation state")
    parser.add_argument("--request-json", required=True, help="Path to normalized request JSON")
    parser.add_argument("--databricks-host", required=True, help="Databricks workspace host")
    parser.add_argument("--output-json", help="Optional path for a structured validation report")
    args = parser.parse_args()
    try:
        return validate_request(args.request_json, args.databricks_host, args.output_json)
    except Exception as exc:  # pylint: disable=broad-except
        _write_report(args.output_json, "error", [], [str(exc)])
        print(f"Databricks validation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
