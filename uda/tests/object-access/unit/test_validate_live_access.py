from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


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
