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


def _write_config(tmp_path: Path, *, sandbox_catalog: str = "edlbi_ss") -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "mapping.yaml").write_text(
        "config_files:\n  PRD: config/prd.yaml\n",
        encoding="utf-8",
    )
    (config_dir / "prd.yaml").write_text(
        "schema_creation:\n"
        f"  sandbox_catalog_name: {sandbox_catalog}\n"
        "  communitymart_catalog_name: edl_communitymart\n",
        encoding="utf-8",
    )
    validator.REPO_ROOT = tmp_path
    validator.MAPPING_FILE = config_dir / "mapping.yaml"


def test_environment_accepts_catalog_configuration(tmp_path: Path) -> None:
    _write_config(tmp_path)

    validator.validate_environment("PRD")


def test_environment_rejects_missing_required_setting(tmp_path: Path) -> None:
    _write_config(tmp_path, sandbox_catalog="")

    with pytest.raises(ValueError, match="sandbox_catalog_name"):
        validator.validate_environment("PRD")