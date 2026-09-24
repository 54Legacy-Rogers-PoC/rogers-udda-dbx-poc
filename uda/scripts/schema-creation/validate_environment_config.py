"""Validate schema deployment configuration before cloud resources are changed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
MAPPING_FILE = REPO_ROOT / "uda" / "config" / "environment-mapping.yaml"
KEYVAULT_SECRET_KEYS = (
    "databricks_host",
    "databricks_client_id",
    "databricks_client_secret",
    "databricks_tenant_id",
    "databricks_workspace_resource_id",
    "tfstate_resource_group",
    "tfstate_storage_account",
    "tfstate_container",
    "tfstate_key",
)
AZURE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return payload


def _required_name(value: Any, field: str) -> str:
    name = str(value or "").strip()
    if not name or name.startswith("<") or not AZURE_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid or missing {field}")
    return name


def validate_environment(environment: str, expected_environment: str = "") -> dict[str, Any]:
    mapping = _load_yaml(MAPPING_FILE)
    environment_code = environment.strip().upper()
    expected_code = expected_environment.strip().upper()
    if expected_code and environment_code != expected_code:
        raise ValueError(
            f"Request environment {environment_code} does not match its {expected_code} request directory"
        )
    config_path = str(mapping.get("config_files", {}).get(environment_code, "")).strip()
    if not config_path:
        raise ValueError(f"No environment configuration found for {environment_code}")

    config = _load_yaml(REPO_ROOT / config_path)
    schema_config = config.get("schema_creation")
    if not isinstance(schema_config, dict):
        raise ValueError(f"schema_creation configuration is missing for {environment_code}")

    required = {
        "sandbox_catalog_name",
        "communitymart_catalog_name",
    }
    missing = sorted(
        key
        for key in required
        if schema_config.get(key) is None or not str(schema_config.get(key)).strip()
    )
    if missing:
        raise ValueError(f"Missing schema_creation settings for {environment_code}: {', '.join(missing)}")

    azure_config = config.get("azure")
    if not isinstance(azure_config, dict):
        raise ValueError(f"azure configuration is missing for {environment_code}")
    _required_name(azure_config.get("keyvault_name"), "azure.keyvault_name")

    keyvault_secrets = config.get("keyvault_secrets")
    if not isinstance(keyvault_secrets, dict):
        raise ValueError(f"keyvault_secrets configuration is missing for {environment_code}")
    for key in KEYVAULT_SECRET_KEYS:
        _required_name(keyvault_secrets.get(key), f"keyvault_secrets.{key}")

    return config


def write_github_outputs(config: dict[str, Any], output_path: Path) -> None:
    azure_config = config["azure"]
    keyvault_secrets = config["keyvault_secrets"]
    outputs = {"keyvault_name": azure_config["keyvault_name"]}
    outputs.update({f"{key}_secret_name": keyvault_secrets[key] for key in KEYVAULT_SECRET_KEYS})
    with output_path.open("a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--expected-environment", default="")
    parser.add_argument("--github-output")
    args = parser.parse_args()
    payload = json.loads(Path(args.request_json).read_text(encoding="utf-8"))
    config = validate_environment(str(payload.get("environment", "")), args.expected_environment)
    if args.github_output:
        write_github_outputs(config, Path(args.github_output))
    print(f"Deployment environment configuration is valid: {payload.get('environment')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())