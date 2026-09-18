from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "uda" / "scripts" / "schema-creation" / "generate_tfvars.py"
    spec = importlib.util.spec_from_file_location("schema_generate_tfvars", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generator = _load_module()


def _normalized(request_id: str, schema: str) -> dict[str, object]:
    return {
        "request_id": request_id,
        "environment": "PRD",
        "sandbox_mode": "new",
        "sandbox_schema_name": schema,
        "sandbox_owner_name": "owner@example.com",
        "create_communitymart_schema": False,
        "communitymart_schema_name": "",
        "communitymart_owner_name": "",
        "ad_group_name": "group@example.com",
        "justification": "test",
        "additional_information": "",
        "assignment_group": "RSO-EDA CLOUD DEPLOYMENT",
        "epdg_ticket_url": "",
        "governance_approval_required": False,
        "ad_approval_required": False,
    }


def test_build_shared_payload_preserves_existing_request(tmp_path: Path) -> None:
    existing = _normalized("RITM-OLD", "slfsrv_old_schema")
    current = _normalized("RITM-NEW", "slfsrv_new_schema")
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    (requests_dir / "old.json").write_text(json.dumps(existing), encoding="utf-8")

    payload = generator.build_shared_tfvars_payload(
        current,
        existing_request_ids={"RITM-OLD"},
        requests_directory=requests_dir,
    )

    assert set(payload["schema_creation_requests"]) == {"RITM-OLD", "RITM-NEW"}
    assert payload["schema_creation_requests"]["RITM-OLD"]["sandbox_schema_name"] == "slfsrv_old_schema"


def test_build_shared_payload_fails_when_state_request_has_no_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="RITM-MISSING"):
        generator.build_shared_tfvars_payload(
            _normalized("RITM-NEW", "slfsrv_new_schema"),
            existing_request_ids={"RITM-MISSING"},
            requests_directory=tmp_path,
        )


def test_build_shared_payload_rejects_mixed_environments(tmp_path: Path) -> None:
    existing = _normalized("RITM-OLD", "slfsrv_old_schema")
    existing["environment"] = "DEV"
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    (requests_dir / "old.json").write_text(json.dumps(existing), encoding="utf-8")

    with pytest.raises(ValueError, match="cannot mix environments"):
        generator.build_shared_tfvars_payload(
            _normalized("RITM-NEW", "slfsrv_new_schema"),
            existing_request_ids={"RITM-OLD"},
            requests_directory=requests_dir,
        )
