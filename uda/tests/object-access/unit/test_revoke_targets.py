from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_module(script_name: str):
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "uda" / "scripts" / "object-access" / script_name
    spec = importlib.util.spec_from_file_location(script_name.removesuffix(".py"), script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


targets = _load_module("build_revoke_targets.py")


def _record(object_type: str) -> dict[str, str]:
    return {
        "activity": "REMOVE",
        "environment": "DEV",
        "access_for": "ad_group",
        "principal_name": "Team",
        "object_type": object_type,
        "catalog": "catalog_a",
        "schema": "schema_a",
        "object_name": "view_a",
        "privilege": "SELECT",
    }


def test_catalog_revoke_address_uses_grouped_resource_key() -> None:
    target, _ = targets._build_target(_record("CATALOG"))

    assert target.endswith('["DEV|ad_group|team|CATALOG|catalog_a||"]')


def test_schema_revoke_address_uses_grouped_resource_key() -> None:
    target, _ = targets._build_target(_record("SCHEMA"))

    assert target.endswith('["DEV|ad_group|team|SCHEMA|catalog_a|schema_a|"]')


def test_view_revoke_address_uses_grouped_resource_key() -> None:
    target, _ = targets._build_target(_record("VIEW"))

    assert target.endswith('["DEV|ad_group|team|VIEW|catalog_a|schema_a|view_a"]')


def test_duplicate_privilege_removals_produce_one_resource_target() -> None:
    first = _record("VIEW")
    second = {**first, "privilege": "MODIFY"}

    assert len(targets.build_revoke_targets({"object_access_records": [first, second]})) == 1