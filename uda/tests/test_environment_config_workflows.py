from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
WORKFLOWS = (
    "uda-dbx-object-access.yml",
    "uda-dbx-schema-creation.yml",
    "uda-dbx-service-account.yml",
    "uda-dbx-cluster-adgroup-add.yml",
    "uda-dbx-cluster-adgroup-remove.yml",
)
CONFIGURED_SECRET_INPUTS = {
    "databricks_host_secret_name",
    "databricks_client_id_secret_name",
    "databricks_client_secret_secret_name",
    "databricks_tenant_id_secret_name",
    "databricks_workspace_resource_id_secret_name",
    "tfstate_resource_group_secret_name",
    "tfstate_storage_account_secret_name",
    "tfstate_container_secret_name",
    "tfstate_key_secret_name",
}


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOW_DIR / name).read_text(encoding="utf-8"))


def test_all_setup_calls_use_environment_config_outputs() -> None:
    for workflow_name in WORKFLOWS:
        workflow = _workflow(workflow_name)
        setup_steps = [
            step
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
            if step.get("uses") == "./.github/workflows/setup-dbxtf-env"
        ]
        assert setup_steps, workflow_name
        for step in setup_steps:
            inputs = step["with"]
            assert inputs["keyvault_name"] in {
                "${{ steps.environment_config.outputs.keyvault_name }}",
                "${{ needs.validate_request.outputs.keyvault_name }}",
            }
            assert CONFIGURED_SECRET_INPUTS <= inputs.keys()


def test_deployment_workflows_do_not_use_keyvault_name_secret() -> None:
    for workflow_name in WORKFLOWS:
        text = (WORKFLOW_DIR / workflow_name).read_text(encoding="utf-8")
        assert "secrets.KEYVAULT_NAME" not in text


def test_staged_workflows_resolve_config_during_validation() -> None:
    for workflow_name in (
        "uda-dbx-service-account.yml",
        "uda-dbx-cluster-adgroup-add.yml",
        "uda-dbx-cluster-adgroup-remove.yml",
    ):
        validate_job = _workflow(workflow_name)["jobs"]["validate_request"]
        resolver = next(step for step in validate_job["steps"] if step.get("id") == "environment_config")
        assert "uda/scripts/resolve_environment_config.py" in resolver["run"]
        assert validate_job["outputs"]["keyvault_name"] == "${{ steps.environment_config.outputs.keyvault_name }}"