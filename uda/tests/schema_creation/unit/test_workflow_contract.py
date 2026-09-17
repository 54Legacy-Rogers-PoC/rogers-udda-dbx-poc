from __future__ import annotations

from pathlib import Path

import yaml


def _workflow() -> dict:
    repo_root = Path(__file__).resolve().parents[4]
    workflow_path = repo_root / ".github" / "workflows" / "uda-dbx-schema-creation.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def test_post_validation_job_exists_and_runs_after_apply() -> None:
    workflow = _workflow()
    post_job = workflow["jobs"]["post-validate-schema-creation"]
    assert post_job["if"]
    assert "needs.plan-schema-creation" in post_job["if"]

    steps = post_job["steps"]
    names = [step.get("name") for step in steps]
    assert "Validate live Databricks schema state" in names
    assert "Persist schema creation status" in names
    assert names.index("Validate live Databricks schema state") < names.index("Persist schema creation status")


def test_schema_workflow_uses_real_terraform_module_path() -> None:
    workflow = _workflow()
    step_text = "\n".join(
        "\n".join(f"{step.get('name', '')}: {step.get('run', '')}" for step in job["steps"])
        for job in workflow["jobs"].values()
    )

    assert "terraform/schema_creation" not in step_text
    assert "terraform/modules/schema_creation" in step_text
    assert "--terraform-variables-file terraform/modules/schema_creation/variables.tf" in step_text


def test_schema_workflow_uses_repo_root_paths_for_plan_files() -> None:
    workflow = _workflow()
    plan_step = next(
        step for job in workflow["jobs"].values() for step in job["steps"] if step.get("name") == "Terraform plan"
    )
    run_text = plan_step["run"]

    assert '-var-file="$GITHUB_WORKSPACE/$TFVARS_JSON"' in run_text
    assert '-out="$GITHUB_WORKSPACE/$TFPLAN_BIN"' in run_text
    assert "../../$TFVARS_JSON" not in run_text
    assert "../../$TFPLAN_BIN" not in run_text


def test_schema_workflow_uses_repo_root_path_for_apply_file() -> None:
    workflow = _workflow()
    apply_step = next(
        step for job in workflow["jobs"].values() for step in job["steps"] if step.get("name") == "Terraform apply"
    )
    run_text = apply_step["run"]

    assert 'apply -lock-timeout=10m -auto-approve "$GITHUB_WORKSPACE/$TFPLAN_BIN"' in run_text
    assert '"../../$TFPLAN_BIN"' not in run_text
