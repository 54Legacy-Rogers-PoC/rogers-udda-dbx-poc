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
        "azure:\n"
        "  keyvault_name: kv-udda-prd\n"
        "keyvault_secrets:\n"
        "  databricks_host: DATABRICKS-HOST\n"
        "  databricks_client_id: DATABRICKS-CLIENT-ID\n"
        "  databricks_client_secret: DATABRICKS-CLIENT-SECRET\n"
        "  databricks_tenant_id: DATABRICKS-TENANT-ID\n"
        "  databricks_workspace_resource_id: DATABRICKS-WORKSPACE-RESOURCE-ID\n"
        "  tfstate_resource_group: TFSTATE-RESOURCE-GROUP\n"
        "  tfstate_storage_account: TFSTATE-STORAGE-ACCOUNT\n"
        "  tfstate_container: TFSTATE-CONTAINER-DBX-UDA\n"
        "  tfstate_key: TFSTATE-KEY-DBX\n"
        "schema_creation:\n"
        f"  sandbox_catalog_name: {sandbox_catalog}\n"
        "  communitymart_catalog_name: edl_communitymart\n",
        encoding="utf-8",
    )
    validator.REPO_ROOT = tmp_path
    validator.MAPPING_FILE = config_dir / "mapping.yaml"


def test_environment_accepts_catalog_configuration(tmp_path: Path) -> None:
    _write_config(tmp_path)

    config = validator.validate_environment("PRD")

    assert config["azure"]["keyvault_name"] == "kv-udda-prd"


def test_environment_rejects_missing_required_setting(tmp_path: Path) -> None:
    _write_config(tmp_path, sandbox_catalog="")

    with pytest.raises(ValueError, match="sandbox_catalog_name"):
        validator.validate_environment("PRD")


def test_environment_rejects_request_directory_mismatch(tmp_path: Path) -> None:
    _write_config(tmp_path)

    with pytest.raises(ValueError, match="does not match its QA request directory"):
        validator.validate_environment("PRD", "QA")


def test_environment_writes_connection_metadata_to_github_output(tmp_path: Path) -> None:
    _write_config(tmp_path)
    output_path = tmp_path / "github-output.txt"

    config = validator.validate_environment("PRD")
    validator.write_github_outputs(config, output_path)

    outputs = dict(
        line.split("=", 1)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    )
    assert outputs["keyvault_name"] == "kv-udda-prd"
    assert outputs["databricks_host_secret_name"] == "DATABRICKS-HOST"
    assert outputs["tfstate_key_secret_name"] == "TFSTATE-KEY-DBX"