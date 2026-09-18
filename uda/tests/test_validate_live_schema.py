from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "uda" / "scripts" / "schema-creation" / "validate_live_schema.py"
    spec = importlib.util.spec_from_file_location("validate_live_schema", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def test_build_targets_uses_environment_catalogs() -> None:
    payload = {
        "environment": "PRD",
        "sandbox_mode": "new",
        "sandbox_schema_name": "slfsrv_manoj_basemarketing",
        "sandbox_owner_name": "furqan@54legacy.com",
        "ad_group_name": "analytics@example.com",
        "create_communitymart_schema": True,
        "communitymart_schema_name": "finance",
        "communitymart_owner_name": "owner@54legacy.com",
    }
    config = {
        "sandbox_catalog_name": "edlbi_ss",
        "communitymart_catalog_name": "edl_communitymart",
        "sandbox_storage_account_name": "stadbdev",
        "communitymart_storage_account_name": "stadbdev",
        "communitymart_container_name": "edl-community-mart",
        "communitymart_storage_prefix": "edl_community_mart",
        "sandbox_storage_credential_name": "adb-dev-cred",
    }

    targets = validator._build_targets(payload, config)

    assert [(target.kind, target.catalog, target.schema) for target in targets] == [
        ("sandbox", "edlbi_ss", "slfsrv_manoj_basemarketing"),
        ("communitymart", "edl_communitymart", "finance"),
    ]
    assert targets[0].principal == "analytics@example.com"
    assert targets[0].schema_privileges == frozenset({"ALL_PRIVILEGES"})
    assert targets[0].catalog_privileges == frozenset()
    assert targets[1].principal == "analytics@example.com"
    assert targets[1].schema_privileges == frozenset({"USE_SCHEMA"})
    assert targets[1].catalog_privileges == frozenset({"USE_CATALOG"})


def test_has_privileges_requires_all_expected_values() -> None:
    assignments = {
        "privilege_assignments": [
            {"principal": "owner@54legacy.com", "privileges": ["READ FILES", "WRITE FILES"]}
        ]
    }

    assert validator._has_privileges(assignments, "owner@54legacy.com", {"READ FILES"})
    assert not validator._has_privileges(
        assignments,
        "owner@54legacy.com",
        {"READ FILES", "WRITE FILES", "MANAGE"},
    )


def test_all_privileges_satisfies_narrower_schema_permission() -> None:
    assignments = {
        "privilege_assignments": [
            {"principal": "owner@54legacy.com", "privileges": ["ALL_PRIVILEGES"]}
        ]
    }

    assert validator._has_privileges(assignments, "owner@54legacy.com", {"USE_SCHEMA"})


def test_validate_checks_both_schema_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "environment": "PRD",
        "sandbox_mode": "new",
        "sandbox_schema_name": "sandbox_schema",
        "sandbox_owner_name": "sandbox-owner@example.com",
        "ad_group_name": "analytics@example.com",
        "create_communitymart_schema": True,
        "communitymart_schema_name": "mart_schema",
        "communitymart_owner_name": "mart-owner@example.com",
    }
    config = {
        "sandbox_catalog_name": "sandbox_catalog",
        "communitymart_catalog_name": "mart_catalog",
        "sandbox_storage_account_name": "storage",
        "communitymart_storage_account_name": "storage",
        "communitymart_container_name": "mart",
        "communitymart_storage_prefix": "schemas",
        "sandbox_storage_credential_name": "credential",
    }
    checked: list[str] = []

    monkeypatch.setattr(validator, "_load_json", lambda _path: payload)
    monkeypatch.setattr(validator, "_load_schema_config", lambda _environment: config)
    monkeypatch.setattr(validator, "_get_token", lambda _host: "token")
    monkeypatch.setattr(
        validator,
        "_validate_target",
        lambda _host, _token, target: checked.append(target.kind) or [],
    )

    assert validator.validate_request("request.json", "https://adb.example.net") == 0
    assert checked == ["sandbox", "communitymart"]


def test_validate_writes_failed_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = {
        "environment": "PRD",
        "sandbox_mode": "new",
        "sandbox_schema_name": "sandbox_schema",
        "sandbox_owner_name": "owner@example.com",
        "ad_group_name": "analytics@example.com",
        "create_communitymart_schema": False,
    }
    config = {
        "sandbox_catalog_name": "sandbox_catalog",
        "sandbox_storage_account_name": "storage",
        "sandbox_storage_credential_name": "credential",
    }
    report = tmp_path / "validation.json"

    monkeypatch.setattr(validator, "_load_json", lambda _path: payload)
    monkeypatch.setattr(validator, "_load_schema_config", lambda _environment: config)
    monkeypatch.setattr(validator, "_get_token", lambda _host: "token")
    monkeypatch.setattr(
        validator,
        "_validate_target",
        lambda *_args: ["Schema sandbox_catalog.sandbox_schema does not exist"],
    )

    assert validator.validate_request("request.json", "https://adb.example.net", str(report)) == 1
    assert json.loads(report.read_text(encoding="utf-8")) == {
        "status": "failed",
        "targets": ["sandbox_catalog.sandbox_schema"],
        "errors": ["Schema sandbox_catalog.sandbox_schema does not exist"],
    }


def test_validate_sandbox_target_checks_schema_and_ad_group_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    target = validator.SchemaTarget(
        kind="sandbox",
        catalog="edlbi_ss",
        schema="slfsrv_manoj_basemarketing",
        principal="analytics@example.com",
        schema_privileges=frozenset({"ALL_PRIVILEGES"}),
        catalog_privileges=frozenset(),
    )
    responses = {
        "/api/2.1/unity-catalog/schemas/edlbi_ss.slfsrv_manoj_basemarketing": {},
        "/api/2.1/unity-catalog/permissions/schema/edlbi_ss.slfsrv_manoj_basemarketing": {
            "privilege_assignments": [
                {"principal": target.principal, "privileges": ["ALL_PRIVILEGES"]}
            ]
        },
    }
    requested_paths: list[str] = []

    def fake_get_resource(_host: str, _token: str, path: str, _description: str):
        requested_paths.append(path)
        return responses[path]

    monkeypatch.setattr(validator, "_get_resource", fake_get_resource)

    assert validator._validate_target(
        "https://adb.example.net",
        "token",
        target,
    ) == []
    assert requested_paths == list(responses)


def test_validate_communitymart_checks_schema_and_catalog_grants(monkeypatch: pytest.MonkeyPatch) -> None:
    target = validator.SchemaTarget(
        kind="communitymart",
        catalog="edl_communitymart",
        schema="vw_reporting",
        principal="analytics@example.com",
        schema_privileges=frozenset({"USE_SCHEMA"}),
        catalog_privileges=frozenset({"USE_CATALOG"}),
    )
    responses = {
        "/api/2.1/unity-catalog/schemas/edl_communitymart.vw_reporting": {},
        "/api/2.1/unity-catalog/permissions/schema/edl_communitymart.vw_reporting": {
            "privilege_assignments": [
                {"principal": target.principal, "privileges": ["USE_SCHEMA"]}
            ]
        },
        "/api/2.1/unity-catalog/permissions/catalog/edl_communitymart": {
            "privilege_assignments": [
                {"principal": target.principal, "privileges": ["USE_CATALOG"]}
            ]
        },
    }

    monkeypatch.setattr(
        validator,
        "_get_resource",
        lambda _host, _token, path, _description: responses[path],
    )

    assert validator._validate_target("https://adb.example.net", "token", target) == []
