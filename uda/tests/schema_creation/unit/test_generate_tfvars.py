from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

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

    assert set(payload["schema_creation_requests"]) == {
        "PRD|edlbi_ss|slfsrv_old_schema",
        "PRD|edlbi_ss|slfsrv_new_schema",
    }
    old_target = payload["schema_creation_requests"]["PRD|edlbi_ss|slfsrv_old_schema"]
    assert old_target["request_id"] == "RITM-OLD"
    assert old_target["target_type"] == "sandbox"


def test_build_shared_payload_allows_duplicate_request_ids_for_distinct_state_targets(tmp_path: Path) -> None:
    first = _normalized("RITM-DUPLICATE", "slfsrv_first")
    second = _normalized("RITM-DUPLICATE", "slfsrv_second")
    current = _normalized("RITM-NEW", "slfsrv_new")
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    (requests_dir / "first.json").write_text(json.dumps(first), encoding="utf-8")
    (requests_dir / "second.json").write_text(json.dumps(second), encoding="utf-8")

    payload = generator.build_shared_tfvars_payload(
        current,
        existing_request_ids={"PRD|edlbi_ss|slfsrv_first", "PRD|edlbi_ss|slfsrv_second"},
        requests_directory=requests_dir,
    )

    assert set(payload["schema_creation_requests"]) == {
        "PRD|edlbi_ss|slfsrv_first",
        "PRD|edlbi_ss|slfsrv_second",
        "PRD|edlbi_ss|slfsrv_new",
    }


def test_build_shared_payload_rejects_ambiguous_legacy_request_id(tmp_path: Path) -> None:
    first = _normalized("RITM-DUPLICATE", "slfsrv_first")
    second = _normalized("RITM-DUPLICATE", "slfsrv_second")
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    (requests_dir / "first.json").write_text(json.dumps(first), encoding="utf-8")
    (requests_dir / "second.json").write_text(json.dumps(second), encoding="utf-8")

    with pytest.raises(ValueError, match="Legacy state request ID RITM-DUPLICATE has multiple request sources"):
        generator.build_shared_tfvars_payload(
            _normalized("RITM-NEW", "slfsrv_new"),
            existing_request_ids={"RITM-DUPLICATE"},
            requests_directory=requests_dir,
        )


def test_build_shared_payload_detaches_state_when_request_source_was_deleted(tmp_path: Path) -> None:
    orphaned_state_keys: list[str] = []

    payload = generator.build_shared_tfvars_payload(
        _normalized("RITM-NEW", "slfsrv_new_schema"),
        existing_request_ids={"PRD|edl_communitymart|vw_deleted"},
        requests_directory=tmp_path,
        orphaned_state_keys=orphaned_state_keys,
    )

    assert orphaned_state_keys == ["PRD|edl_communitymart|vw_deleted"]
    assert set(payload["schema_creation_requests"]) == {"PRD|edlbi_ss|slfsrv_new_schema"}


def test_build_shared_payload_rejects_missing_state_source_by_default(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="vw_deleted"):
        generator.build_shared_tfvars_payload(
            _normalized("RITM-NEW", "slfsrv_new_schema"),
            existing_request_ids={"PRD|edl_communitymart|vw_deleted"},
            requests_directory=tmp_path,
        )


def test_cli_rejects_missing_state_source_without_orphan_output(tmp_path: Path) -> None:
    current = _normalized("RITM-NEW", "slfsrv_new_schema")
    input_json = tmp_path / "input.json"
    output_json = tmp_path / "output.json"
    state_keys = tmp_path / "state-keys.txt"
    variables_file = Path(__file__).resolve().parents[4] / "terraform" / "environments" / "dev" / "variables.tf"
    input_json.write_text(json.dumps(current), encoding="utf-8")
    state_keys.write_text("PRD|edl_communitymart|vw_deleted\n", encoding="utf-8")

    argv = [
        "generate_tfvars.py",
        "--input-json",
        str(input_json),
        "--output-json",
        str(output_json),
        "--existing-request-ids-file",
        str(state_keys),
        "--requests-directory",
        str(tmp_path),
        "--terraform-variables-file",
        str(variables_file),
    ]
    with patch.object(sys, "argv", argv):
        assert generator.main() == 1

    assert not output_json.exists()


def test_render_orphaned_state_keys_is_sorted_and_deduplicated() -> None:
    rendered = generator.render_orphaned_state_keys(
        ["PRD|edlbi_ss|slfsrv_deleted", "PRD|edl_communitymart|vw_deleted", "PRD|edlbi_ss|slfsrv_deleted"]
    )

    assert rendered.splitlines() == [
        "PRD|edl_communitymart|vw_deleted",
        "PRD|edlbi_ss|slfsrv_deleted",
    ]


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


def test_duplicate_schema_error_provides_actionable_summary(tmp_path: Path) -> None:
    existing = _normalized("RITM78067", "slfsrv_data_reporting")
    current = _normalized("RITM7806789", "slfsrv_data_reporting")
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    (requests_dir / "existing.json").write_text(json.dumps(existing), encoding="utf-8")

    with pytest.raises(generator.DuplicateSchemaTargetError) as captured:
        generator.build_shared_tfvars_payload(
            current,
            existing_request_ids={"RITM78067"},
            requests_directory=requests_dir,
        )

    assert captured.value.markdown() == "\n".join(
        [
            "## Schema Request Rejected",
            "",
            "- Request: RITM7806789",
            "- Schema: edlbi_ss.slfsrv_data_reporting",
            "- Existing owner: RITM78067",
            "- Status: Duplicate schema target",
            "- Action: Choose a unique schema name or submit an object-access request",
        ]
    )
