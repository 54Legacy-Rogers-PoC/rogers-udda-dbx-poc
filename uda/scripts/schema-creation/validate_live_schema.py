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


@dataclass(frozen=True)
class SchemaTarget:
    kind: str
    catalog: str
    schema: str
    principal: str
    schema_privileges: frozenset[str]
    catalog_privileges: frozenset[str]


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


def _build_targets(payload: dict[str, Any], config: dict[str, Any]) -> list[SchemaTarget]:
    targets: list[SchemaTarget] = []
    principal = _norm(payload.get("ad_group_name")).lower()

    if _norm(payload.get("sandbox_mode")).lower() == "new":
        targets.append(
            SchemaTarget(
                kind="sandbox",
                catalog=_norm(config.get("sandbox_catalog_name")),
                schema=_norm(payload.get("sandbox_schema_name")).lower(),
                principal=principal,
                schema_privileges=frozenset({"ALL_PRIVILEGES"}),
                catalog_privileges=frozenset(),
            )
        )

    if payload.get("create_communitymart_schema") is True:
        targets.append(
            SchemaTarget(
                kind="communitymart",
                catalog=_norm(config.get("communitymart_catalog_name")),
                schema=_norm(payload.get("communitymart_schema_name")).lower(),
                principal=principal,
                schema_privileges=frozenset({"USE_SCHEMA"}),
                catalog_privileges=frozenset({"USE_CATALOG"}),
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
        if actual_principal == principal.lower() and ("ALL_PRIVILEGES" in actual or expected <= actual):
            return True
    return False


def _validate_target(
    host: str,
    token: str,
    target: SchemaTarget,
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

    permissions = _get_resource(
        host,
        token,
        f"/api/2.1/unity-catalog/permissions/schema/{quote(full_name, safe='.')}",
        f"Schema permissions lookup for {full_name}",
    )
    if permissions is None or not _has_privileges(
        permissions, target.principal, set(target.schema_privileges)
    ):
        errors.append(
            f"AD group {target.principal} does not have {', '.join(sorted(target.schema_privileges))} "
            f"on schema {full_name}"
        )

    if target.catalog_privileges:
        catalog_permissions = _get_resource(
            host,
            token,
            f"/api/2.1/unity-catalog/permissions/catalog/{quote(target.catalog, safe='')}",
            f"Catalog permissions lookup for {target.catalog}",
        )
        if catalog_permissions is None or not _has_privileges(
            catalog_permissions, target.principal, set(target.catalog_privileges)
        ):
            errors.append(
                f"AD group {target.principal} does not have "
                f"{', '.join(sorted(target.catalog_privileges))} on catalog {target.catalog}"
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
        errors.extend(_validate_target(host, token, target))

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
