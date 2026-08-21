import importlib.util
from pathlib import Path


def _load_module():
    script_path = Path(__file__).parents[1] / "scripts" / "manage_cluster_service_account_access.py"
    spec = importlib.util.spec_from_file_location("manage_cluster_service_account_access", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = _load_module()
build_updated_acl = module.build_updated_acl


def test_build_updated_acl_add_preserves_others_and_sets_target():
    existing = [
        {"group_name": "DTB_DATA", "permission_level": "CAN_ATTACH_TO"},
        {"service_principal_name": "svc_old", "permission_level": "CAN_MANAGE"},
    ]

    updated = build_updated_acl(
        existing_acl=existing,
        activity="ADD_TO_CLUSTER",
        service_account_name="svc_new",
        permission_level="CAN_RESTART",
    )

    assert any(e.get("group_name") == "DTB_DATA" for e in updated)
    assert any(e.get("service_principal_name") == "svc_old" for e in updated)
    assert any(
        e.get("service_principal_name") == "svc_new" and e.get("permission_level") == "CAN_RESTART"
        for e in updated
    )


def test_build_updated_acl_remove_only_target():
    existing = [
        {"group_name": "DTB_DATA", "permission_level": "CAN_ATTACH_TO"},
        {"service_principal_name": "svc_remove", "permission_level": "CAN_ATTACH_TO"},
        {"service_principal_name": "svc_keep", "permission_level": "CAN_MANAGE"},
    ]

    updated = build_updated_acl(
        existing_acl=existing,
        activity="REMOVE_FROM_CLUSTER",
        service_account_name="svc_remove",
        permission_level="CAN_ATTACH_TO",
    )

    assert any(e.get("group_name") == "DTB_DATA" for e in updated)
    assert any(e.get("service_principal_name") == "svc_keep" for e in updated)
    assert not any(e.get("service_principal_name") == "svc_remove" for e in updated)
