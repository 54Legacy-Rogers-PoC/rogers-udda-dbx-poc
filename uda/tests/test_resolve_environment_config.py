from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "uda" / "scripts" / "resolve_environment_config.py"
    spec = importlib.util.spec_from_file_location("resolve_environment_config", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


resolver = _load_module()


def _write_config(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    environment_dir = config_dir / "environments"
    environment_dir.mkdir(parents=True)
    (config_dir / "mapping.yaml").write_text(
        "aliases:\n  Production: PRD\nconfig_files:\n  PRD: config/environments/prd.yaml\n",
        encoding="utf-8",
    )
    (environment_dir / "prd.yaml").write_text(
        "code: PRD\n"
        "azure:\n  keyvault_name: kv-prd\n"
        "keyvault_secrets:\n"
        + "".join(f"  {key}: {key.upper().replace('_', '-')}\n" for key in resolver.KEYVAULT_SECRET_KEYS),
        encoding="utf-8",
    )
    resolver.REPO_ROOT = tmp_path
    resolver.MAPPING_FILE = config_dir / "mapping.yaml"


def test_resolves_alias_and_writes_github_outputs(tmp_path: Path) -> None:
    _write_config(tmp_path)
    output = tmp_path / "github-output.txt"

    code, config = resolver.resolve_environment("Production", "PRD")
    resolver.write_github_outputs(code, config, output)

    values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    assert values["environment_code"] == "PRD"
    assert values["deployment_environment"] == "prd"
    assert values["keyvault_name"] == "kv-prd"
    assert values["databricks_host_secret_name"] == "DATABRICKS-HOST"


def test_reads_environment_from_request_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path)
    request = tmp_path / "request.json"
    output = tmp_path / "github-output.txt"
    request.write_text(json.dumps({"environment": "Production"}), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["resolve_environment_config.py", "--request-json", str(request), "--github-output", str(output)],
    )

    assert resolver.main() == 0
    assert "keyvault_name=kv-prd" in output.read_text(encoding="utf-8")


def test_rejects_environment_mismatch(tmp_path: Path) -> None:
    _write_config(tmp_path)

    with pytest.raises(ValueError, match="does not match its QA request directory"):
        resolver.resolve_environment("Production", "QA")