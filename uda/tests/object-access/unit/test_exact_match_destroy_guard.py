from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_guard_module():
    repo_root = Path(__file__).resolve().parents[4]
    script_path = repo_root / "uda" / "scripts" / "object-access" / "guard_exact_match_destroy.py"
    spec = importlib.util.spec_from_file_location("guard_exact_match_destroy", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guard = _load_guard_module()


def test_guard_allows_exact_key_destroy() -> None:
    tfvars = {
        "object_access_records": [
            {
                "environment": "PRD",
                "access_for": "ad_group",
                "principal_name": "abeer@54legacy.com",
                "object_type": "VIEW",
                "catalog_name": "edl_prod",
                "schema_name": "vw_schema",
                "object_name": "vw_vvvvv",
                "privilege": "SELECT",
            }
        ]
    }
    plan = {
        "resource_changes": [
            {
                "address": 'module.object_access.databricks_grant.view_add["PRD|ad_group|abeer@54legacy.com|VIEW|edl_prod|vw_schema|vw_vvvvv|SELECT"]',
                "change": {"actions": ["delete"]},
            }
        ]
    }

    assert guard.disallowed_destroy_keys(tfvars, plan) == []


def test_guard_blocks_different_key_destroy() -> None:
    tfvars = {
        "object_access_records": [
            {
                "environment": "PRD",
                "access_for": "ad_group",
                "principal_name": "abeer@54legacy.com",
                "object_type": "VIEW",
                "catalog_name": "edl_prod",
                "schema_name": "vw_schema",
                "object_name": "vw_vvvvv",
                "privilege": "SELECT",
            }
        ]
    }
    plan = {
        "resource_changes": [
            {
                "address": 'module.object_access.databricks_grant.view_add["PRD|ad_group|abeer@54legacy.com|VIEW|edl_prod|vw_schema|vw_b|SELECT"]',
                "change": {"actions": ["delete"]},
            }
        ]
    }

    assert guard.disallowed_destroy_keys(tfvars, plan) == ["PRD|ad_group|abeer@54legacy.com|VIEW|edl_prod|vw_schema|vw_b|SELECT"]


def test_guard_extracts_exact_key_for_address() -> None:
    address = 'module.object_access.databricks_grant.view_add["PRD|ad_group|abeer@54legacy.com|VIEW|edl_prod|vw_schema|vw_vvvvv|SELECT"]'
    assert guard._resource_key_from_address(address) == "PRD|ad_group|abeer@54legacy.com|VIEW|edl_prod|vw_schema|vw_vvvvv|SELECT"
