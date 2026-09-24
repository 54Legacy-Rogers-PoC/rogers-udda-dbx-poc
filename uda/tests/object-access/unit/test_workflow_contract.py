from __future__ import annotations

from pathlib import Path

import yaml


def _workflow() -> dict:
    repo_root = Path(__file__).resolve().parents[4]
    workflow_path = repo_root / ".github" / "workflows" / "uda-dbx-object-access.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def test_state_mutations_only_run_for_apply_capable_events() -> None:
    steps = _workflow()["jobs"]["plan-object-access"]["steps"]
    for step_name in ("Migrate legacy grant state addresses", "Import unmanaged revoke targets"):
        step = next(item for item in steps if item.get("name") == step_name)
        condition = step.get("if", "")
        assert "github.event_name == 'push'" in condition
        assert "inputs.run_apply" in condition


def test_post_validation_precedes_manifest_persistence() -> None:
    steps = _workflow()["jobs"]["post-validate-object-access"]["steps"]
    names = [step.get("name") for step in steps]

    assert names.index("Validate live Databricks access vs request") < names.index("Persist active-grants manifest")


def test_artifact_download_uses_step_outputs() -> None:
    steps = _workflow()["jobs"]["post-validate-object-access"]["steps"]
    download = next(step for step in steps if step.get("name") == "Download plan artifacts")

    assert "steps.post_paths.outputs.request_id" in download["with"]["name"]
    assert download["with"]["path"] == "${{ steps.post_paths.outputs.output_dir }}"


def test_plan_and_validation_jobs_use_shared_databricks_setup_action() -> None:
    workflow = _workflow()
    action_reference = "./.github/workflows/setup-dbxtf-env"

    for job_name in ("plan-object-access", "post-validate-object-access"):
        steps = workflow["jobs"][job_name]["steps"]
        setup_steps = [step for step in steps if step.get("uses") == action_reference]
        assert len(setup_steps) == 1
        setup = setup_steps[0]
        assert setup["with"]["keyvault_name"] == "${{ steps.environment_config.outputs.keyvault_name }}"
        assert "${{ secrets.KEYVAULT_NAME }}" not in str(setup)
        assert not any(step.get("uses", "").startswith("azure/login@") for step in steps)


def test_environment_is_resolved_before_cloud_setup() -> None:
    workflow = _workflow()
    for job_name in ("plan-object-access", "post-validate-object-access"):
        steps = workflow["jobs"][job_name]["steps"]
        names = [step.get("name") for step in steps]
        assert names.index("Resolve environment configuration") < names.index("Setup Azure and Databricks")
        resolver = next(step for step in steps if step.get("name") == "Resolve environment configuration")
        assert "uda/scripts/resolve_environment_config.py" in resolver["run"]