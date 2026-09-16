from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest
import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "uda" / "scripts" / "object-access" / "validate_live_access.py"
    spec = importlib.util.spec_from_file_location("validate_live_access", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def test_extract_live_keys_from_unity_catalog_payload() -> None:
    payload = {
        "catalog": "edl_prod",
        "schema": "vw_schema",
        "table": "vw_b",
        "privilege_assignments": [{
            "principal": "user:abeer@54legacy.com",
            "privileges": ["SELECT"],
        }],
    }

    result = validator._extract_live_keys(payload, "VIEW")

    assert result == {"VIEW|edl_prod|vw_schema|vw_b|abeer@54legacy.com|SELECT"}


def test_manifest_keys_match_live_grant_identity() -> None:
    manifest = {
        "object_access_records": [{
            "object_type": "VIEW",
            "catalog_name": "edl_prod",
            "schema_name": "vw_schema",
            "object_name": "vw_b",
            "principal_name": "Abeer@54Legacy.com",
            "privilege": "SELECT",
        }]
    }

    assert validator._manifest_keys(manifest) == {"VIEW|edl_prod|vw_schema|vw_b|abeer@54legacy.com|SELECT"}


def test_get_databricks_token_uses_workspace_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("DB_OAUTH_CLIENT_SECRET", "oauth-secret")
    captured: dict[str, object] = {}

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json() -> dict[str, str]:
            return {"access_token": "workspace-token"}

    def fake_post(url: str, **kwargs: object) -> Response:
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(validator.requests, "post", fake_post)

    token = validator.get_databricks_token("https://adb-example.azuredatabricks.net/")

    assert token == "workspace-token"
    assert captured == {
        "url": "https://adb-example.azuredatabricks.net/oidc/v1/token",
        "auth": ("client-id", "oauth-secret"),
        "data": {"grant_type": "client_credentials", "scope": "all-apis"},
        "timeout": 60,
    }


def test_fetch_databricks_grants_uses_singular_securable_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    requested_urls: list[str] = []

    class Response:
        status_code = 404
        text = ""

    def fake_get(url: str, **_kwargs: object) -> Response:
        requested_urls.append(url)
        return Response()

    monkeypatch.setattr(validator.requests, "get", fake_get)
    records = [
        {"object_type": "CATALOG", "catalog_name": "edl_prod"},
        {"object_type": "SCHEMA", "catalog_name": "edl_prod", "schema_name": "vw_schema"},
        {
            "object_type": "VIEW",
            "catalog_name": "edl_prod",
            "schema_name": "vw_schema",
            "object_name": "employee_data",
        },
    ]

    validator._fetch_databricks_grants("https://adb-example.azuredatabricks.net", "token", records)

    assert requested_urls == [
        "https://adb-example.azuredatabricks.net/api/2.1/unity-catalog/permissions/catalog/edl_prod",
        "https://adb-example.azuredatabricks.net/api/2.1/unity-catalog/permissions/schema/edl_prod.vw_schema",
        "https://adb-example.azuredatabricks.net/api/2.1/unity-catalog/permissions/table/edl_prod.vw_schema.employee_data",
    ]


def test_fetch_databricks_grants_preserves_requested_object_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "privilege_assignments": [{
                    "principal": "user:abeer@54legacy.com",
                    "privileges": ["SELECT"],
                }]
            }

    monkeypatch.setattr(validator.requests, "get", lambda *_args, **_kwargs: Response())
    records = [{
        "object_type": "VIEW",
        "catalog_name": "edl_prod",
        "schema_name": "vw_schema",
        "object_name": "employee_data",
    }]

    live = validator._fetch_databricks_grants(
        "https://adb-example.azuredatabricks.net", "token", records
    )

    assert live == {"VIEW|edl_prod|vw_schema|employee_data|abeer@54legacy.com|SELECT"}


def test_object_access_workflow_moves_validate_to_post_job() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    workflow_path = repo_root / ".github" / "workflows" / "uda-dbx-object-access.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    plan_steps = workflow["jobs"]["plan-object-access"]["steps"]
    assert all(step.get("name") != "Validate live Databricks access vs manifest" for step in plan_steps)

    post_job = workflow["jobs"]["post-validate-object-access"]
    validate_run = next(
        step for step in post_job["steps"] if step.get("name") == "Validate live Databricks access vs request"
    )["run"]

    assert 'if [ "${REQUEST_ACTIVITY:-}" = "REMOVE" ]; then' in validate_run
    assert 'Skipping live validation for REMOVE request because the grant is expected to be absent after revoke.' in validate_run
    assert '--manifest-json "$REQUEST_TFVARS_JSON"' in validate_run
