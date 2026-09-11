from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "uda" / "scripts" / "object-access" / "merge_active_grants.py"
    spec = importlib.util.spec_from_file_location("merge_active_grants", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


merger = _load_module()


def _record(object_name: str, activity: str = "ADD", principal: str = "abeer@54legacy.com") -> dict:
    return {
        "record_id": f"record-{object_name}",
        "activity": activity,
        "environment": "PRD",
        "access_for": "ad_group",
        "principal_name": principal,
        "object_type": "VIEW",
        "catalog": "edl_prod",
        "schema": "vw_schema",
        "object_name": object_name,
        "folder_path": "",
        "privilege": "SELECT",
        "row_number": 1,
    }


def _payload(*records: dict) -> dict:
    return {"request_id": "RITM1", "environment": "PRD", "object_access_records": list(records)}


def test_add_preserves_existing_different_key() -> None:
    manifest = _payload(_record("vw_b"))
    request = _payload(_record("vw_vvvvv"))

    result = merger.merge_active_grants(request, manifest, {})

    assert [record["object_name"] for record in result["object_access_records"]] == ["vw_b", "vw_vvvvv"]
    assert result["record_count"] == 2


def test_remove_deletes_only_exact_key() -> None:
    manifest = _payload(_record("vw_b"), _record("vw_vvvvv"))
    request = _payload(_record("vw_b", activity="REMOVE"))

    result = merger.merge_active_grants(request, manifest, {})

    assert [record["object_name"] for record in result["object_access_records"]] == ["vw_vvvvv"]


def test_state_bootstrap_preserves_managed_grant() -> None:
    state = {
        "values": {
            "root_module": {
                "child_modules": [
                    {
                        "resources": [
                            {
                                "type": "databricks_grant",
                                "index": "PRD|ad_group|abeer@54legacy.com|VIEW|edl_prod|vw_schema|vw_b|SELECT",
                            }
                        ]
                    }
                ]
            }
        }
    }

    result = merger.merge_active_grants(_payload(_record("vw_vvvvv")), {}, state)

    assert [record["object_name"] for record in result["object_access_records"]] == ["vw_b", "vw_vvvvv"]