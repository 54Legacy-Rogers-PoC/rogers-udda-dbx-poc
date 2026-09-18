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
    assert "Publish validation outputs" in names

    validate_step = next(step for step in steps if step.get("name") == "Validate live Databricks schema state")
    assert '--output-json "$OUTPUT_DIR/schema-creation-status.json"' in validate_step["run"]


def test_schema_workflow_uses_shared_root_stack() -> None:
    workflow = _workflow()
    step_text = "\n".join(
        "\n".join(f"{step.get('name', '')}: {step.get('run', '')}" for step in job["steps"])
        for job in workflow["jobs"].values()
    )

    assert "terraform/schema_creation" not in step_text
    assert "terraform/modules/schema_creation" not in step_text
    assert '--terraform-variables-file terraform/environments/dev/variables.tf' in step_text
    assert 'terraform -chdir="$TF_WORKDIR" plan' in step_text
    assert "Terraform init" not in step_text


def test_schema_workflow_uses_repo_root_paths_for_plan_files() -> None:
    workflow = _workflow()
    plan_step = next(
        step for job in workflow["jobs"].values() for step in job["steps"] if step.get("name") == "Terraform plan"
    )
    run_text = plan_step["run"]

    assert '-var-file="$GITHUB_WORKSPACE/$TFVARS_JSON"' in run_text
    assert '-out="$GITHUB_WORKSPACE/$TFPLAN_BIN"' in run_text
    assert '-target="$TF_SCHEMA_TARGET"' in run_text
    assert "../../$TFVARS_JSON" not in run_text
    assert "../../$TFPLAN_BIN" not in run_text


def test_schema_workflow_migrates_legacy_module_address() -> None:
    workflow = _workflow()
    plan_job = workflow["jobs"]["plan-schema-creation"]
    migration_step = next(
        step for step in plan_job["steps"] if step.get("name") == "Migrate legacy schema state address"
    )

    assert "state mv" in migration_step["run"]
    assert "module.schema_creation[0]" in migration_step["run"]


def test_root_outputs_do_not_expand_all_schema_instances() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    outputs = (repo_root / "terraform" / "environments" / "dev" / "outputs.tf").read_text(
        encoding="utf-8"
    )

    assert "module.schema_creation" not in outputs


def test_schema_workflow_uses_repo_root_path_for_apply_file() -> None:
    workflow = _workflow()
    apply_step = next(
        step for job in workflow["jobs"].values() for step in job["steps"] if step.get("name") == "Terraform apply"
    )
    run_text = apply_step["run"]

    assert 'apply -lock-timeout=10m -auto-approve "$GITHUB_WORKSPACE/$TFPLAN_BIN"' in run_text
    assert '"../../$TFPLAN_BIN"' not in run_text
