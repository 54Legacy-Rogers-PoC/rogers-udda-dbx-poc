from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "uda" / "scripts" / "object-access" / "build_state_migrations.py"
    spec = importlib.util.spec_from_file_location("build_state_migrations", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migrations = _load_module()


def test_build_migrations_removes_only_legacy_privilege_segment() -> None:
    old = (
        'module.object_access.databricks_grant.view_add'
        '["DEV|ad_group|team|VIEW|catalog_a|schema_a|view_a|SELECT"]'
    )

    assert migrations.build_migrations([old]) == [
        (
            old,
            'module.object_access.databricks_grant.view_add'
            '["DEV|ad_group|team|VIEW|catalog_a|schema_a|view_a"]',
        )
    ]


def test_build_migrations_ignores_grouped_and_unrelated_addresses() -> None:
    addresses = [
        'module.object_access.databricks_grant.view_add["DEV|ad_group|team|VIEW|cat|sch|view"]',
        'module.schema_creation[0].databricks_schema.this',
    ]

    assert migrations.build_migrations(addresses) == []