from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "uda" / "scripts" / "schema-creation" / "migrate_schema_state_keys.py"
    spec = importlib.util.spec_from_file_location("schema_migrate_state_keys", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_module()


def _targets() -> dict[str, dict[str, str]]:
    return {
        "PRD|edlbi_ss|slfsrv_example": {
            "request_id": "RITM123",
            "target_type": "sandbox",
        },
        "PRD|edl_communitymart|vw_example": {
            "request_id": "RITM123",
            "target_type": "communitymart",
        },
    }


def test_build_state_moves_splits_request_resources_by_schema_target() -> None:
    addresses = [
        'module.schema_creation["RITM123"].databricks_schema.sandbox[0]',
        'module.schema_creation["RITM123"].databricks_grant.sandbox_owner[0]',
        'module.schema_creation["RITM123"].databricks_schema.communitymart[0]',
        'module.schema_creation["RITM123"].databricks_grant.communitymart_owner[0]',
    ]

    moves = migration.build_state_moves(addresses, _targets())

    assert moves == [
        (
            'module.schema_creation["RITM123"].databricks_schema.sandbox[0]',
            'module.schema_creation["PRD|edlbi_ss|slfsrv_example"].databricks_schema.sandbox[0]',
        ),
        (
            'module.schema_creation["RITM123"].databricks_grant.sandbox_owner[0]',
            'module.schema_creation["PRD|edlbi_ss|slfsrv_example"].databricks_grant.sandbox_owner[0]',
        ),
        (
            'module.schema_creation["RITM123"].databricks_schema.communitymart[0]',
            'module.schema_creation["PRD|edl_communitymart|vw_example"].databricks_schema.communitymart[0]',
        ),
        (
            'module.schema_creation["RITM123"].databricks_grant.communitymart_owner[0]',
            'module.schema_creation["PRD|edl_communitymart|vw_example"].databricks_grant.communitymart_owner[0]',
        ),
    ]


def test_build_state_moves_ignores_already_migrated_target_keys() -> None:
    addresses = ['module.schema_creation["PRD|edlbi_ss|slfsrv_example"].databricks_schema.sandbox[0]']

    assert migration.build_state_moves(addresses, _targets()) == []


def test_render_moved_blocks_creates_declarative_terraform_migration() -> None:
    moves = [
        (
            'module.schema_creation["RITM123"].databricks_schema.sandbox[0]',
            'module.schema_creation["PRD|edlbi_ss|slfsrv_example"].databricks_schema.sandbox[0]',
        )
    ]

    rendered = migration.render_moved_blocks(moves)

    assert 'from = module.schema_creation["RITM123"].databricks_schema.sandbox[0]' in rendered
    assert 'to   = module.schema_creation["PRD|edlbi_ss|slfsrv_example"].databricks_schema.sandbox[0]' in rendered


def test_build_state_moves_fails_for_unknown_request_resource() -> None:
    addresses = ['module.schema_creation["RITM123"].databricks_grant.unexpected[0]']

    with pytest.raises(ValueError, match="Unsupported resource"):
        migration.build_state_moves(addresses, _targets())
