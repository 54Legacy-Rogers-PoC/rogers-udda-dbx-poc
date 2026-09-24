"""Validate schema deployment configuration before cloud resources are changed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
MAPPING_FILE = REPO_ROOT / "uda" / "config" / "environment-mapping.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return payload


def validate_environment(environment: str) -> None:
    mapping = _load_yaml(MAPPING_FILE)
    environment_code = environment.strip().upper()
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.request_json).read_text(encoding="utf-8"))
    validate_environment(str(payload.get("environment", "")))
    print(f"Deployment environment configuration is valid: {payload.get('environment')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())