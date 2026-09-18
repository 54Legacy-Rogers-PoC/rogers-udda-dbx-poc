from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "uda" / "scripts" / "schema-creation" / "validate_environment_config.py"
    spec = importlib.util.spec_from_file_location("schema_validate_environment_config", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def _write_config(tmp_path: Path, *, storage_account: str, credential: str) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "mapping.yaml").write_text(
        "config_files:\n  PRD: config/prd.yaml\n",
        encoding="utf-8",
    )
    (config_dir / "prd.yaml").write_text(
        "schema_creation:\n"
        "  sandbox_catalog_name: edlbi_ss\n"
        "  communitymart_catalog_name: edl_communitymart\n"
        f"  sandbox_storage_account_name: {storage_account}\n"
        f"  communitymart_storage_account_name: {storage_account}\n"
        "  communitymart_container_name: edl-community-mart\n"
        "  communitymart_storage_prefix: edl_community_mart\n"
        f"  sandbox_storage_credential_name: {credential}\n",
        encoding="utf-8",
    )
    validator.REPO_ROOT = tmp_path
    validator.MAPPING_FILE = config_dir / "mapping.yaml"


def test_production_accepts_configured_storage_values_regardless_of_name(tmp_path: Path) -> None:
    _write_config(tmp_path, storage_account="stadbdev", credential="adb-dev-cred")

    validator.validate_environment("PRD")


def test_production_accepts_distinct_production_storage_values(tmp_path: Path) -> None:
    _write_config(tmp_path, storage_account="stadbprd", credential="adb-prd-cred")

    validator.validate_environment("PRD")


def test_environment_rejects_missing_required_setting(tmp_path: Path) -> None:
    _write_config(tmp_path, storage_account="", credential="adb-dev-cred")

    with pytest.raises(ValueError, match="storage_account_name"):
        validator.validate_environment("PRD")