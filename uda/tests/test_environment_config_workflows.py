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


def test_cluster_adgroup_add_uses_reusable_terraform_validation() -> None:
    jobs = _workflow("uda-dbx-cluster-adgroup-add.yml")["jobs"]
    validation = jobs["terraform_validation"]
    assert validation["uses"] == (
        "54Legacy-Rogers-PoC/54legacy-Resusable-Workflows/"
        ".github/workflows/platform-terraform-validation.yml@main"
    )
    assert validation["needs"] == ["validate_request"]
    assert validation["with"] == {
        "working-directory": "terraform/environments/dev",
        "terraform-version": "1.9.8",
        "fmt-recursive": True,
    }
    assert not {"steps", "runs-on", "outputs"} & validation.keys()
    assert "terraform_validation" in jobs["terraform_plan"]["needs"]
    assert "terraform_validation" in jobs["notification"]["needs"]
    assert not any(
        step.get("run", "").strip() == "terraform validate"
        for step in jobs["terraform_plan"].get("steps", [])
    )


def test_cluster_adgroup_add_uses_reusable_terraform_plan() -> None:
    jobs = _workflow("uda-dbx-cluster-adgroup-add.yml")["jobs"]
    plan = jobs["terraform_plan"]
    assert plan["uses"] == (
        "54Legacy-Rogers-PoC/54legacy-Resusable-Workflows/"
        ".github/workflows/platform-terraform-plan.yml@ba1cb62f63fafd15a83708e41d4915b2dd2297b8"
    )
    assert not {"steps", "runs-on", "outputs"} & plan.keys()
    assert plan["with"]["terraform-version"] == "1.9.8"
    assert plan["with"]["databricks-setup"] is True
    assert plan["with"]["environment-config-json"] == "${{ toJSON(needs.validate_request.outputs) }}"
    assert plan["with"]["generated-artifact"] == "uda-cluster-adgroup-generated"
    assert plan["with"]["tfstate-key-suffix"] == "cluster-adgroup"
    assert set(plan["secrets"]) == {
        "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID", "AZURE_TENANT_ID"
    }
    apply_steps = jobs["terraform_apply"]["steps"]
    download = next(step for step in apply_steps if step["name"] == "Download terraform plan artifact")
    assert download["with"]["name"] == "${{ needs.terraform_plan.outputs.plan-artifact }}"
    apply = next(step for step in apply_steps if step["name"] == "Terraform apply")
    assert apply["run"] == "terraform apply -auto-approve tfplan"
    assert "outputs.tf_plan_status" not in (WORKFLOW_DIR / "uda-dbx-cluster-adgroup-add.yml").read_text()