"""Resolve non-secret Azure Key Vault metadata for a deployment environment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
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


def resolve_environment(environment: str, expected_environment: str = "") -> tuple[str, dict[str, Any]]:
    mapping = _load_yaml(MAPPING_FILE)
    aliases = mapping.get("aliases", {})
    raw_environment = environment.strip()
    environment_code = str(aliases.get(raw_environment, raw_environment)).strip().upper()
    expected_code = expected_environment.strip().upper()
    if expected_code and environment_code != expected_code:
        raise ValueError(
            f"Request environment {environment_code} does not match its {expected_code} request directory"
        )

    config_path = str(mapping.get("config_files", {}).get(environment_code, "")).strip()
    if not config_path:
        raise ValueError(f"No environment configuration found for {environment_code}")
    config = _load_yaml(REPO_ROOT / config_path)

    configured_code = str(config.get("code", "")).strip().upper()
    if configured_code != environment_code:
        raise ValueError(
            f"Environment configuration code {configured_code or '<missing>'} does not match {environment_code}"
        )

    azure_config = config.get("azure")
    if not isinstance(azure_config, dict):
        raise ValueError(f"azure configuration is missing for {environment_code}")
    _required_name(azure_config.get("keyvault_name"), "azure.keyvault_name")

    keyvault_secrets = config.get("keyvault_secrets")
    if not isinstance(keyvault_secrets, dict):
        raise ValueError(f"keyvault_secrets configuration is missing for {environment_code}")
    for key in KEYVAULT_SECRET_KEYS:
        _required_name(keyvault_secrets.get(key), f"keyvault_secrets.{key}")

    return environment_code, config


def write_github_outputs(environment_code: str, config: dict[str, Any], output_path: Path) -> None:
    keyvault_secrets = config["keyvault_secrets"]
    outputs = {
        "environment_code": environment_code,
        "deployment_environment": environment_code.lower(),
        "keyvault_name": config["azure"]["keyvault_name"],
    }
    outputs.update({f"{key}_secret_name": keyvault_secrets[key] for key in KEYVAULT_SECRET_KEYS})
    with output_path.open("a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--environment")
    source.add_argument("--request-json")
    parser.add_argument("--expected-environment", default="")
    parser.add_argument("--github-output")
    args = parser.parse_args()

    environment = args.environment
    if args.request_json:
        payload = json.loads(Path(args.request_json).read_text(encoding="utf-8"))
        environment = str(payload.get("environment", ""))

    environment_code, config = resolve_environment(str(environment), args.expected_environment)
    if args.github_output:
        write_github_outputs(environment_code, config, Path(args.github_output))
    print(f"Environment configuration resolved: {environment_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())