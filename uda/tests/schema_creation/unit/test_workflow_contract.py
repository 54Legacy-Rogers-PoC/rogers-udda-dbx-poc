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


def test_pull_requests_run_plan_but_never_apply_or_mutate_state() -> None:
    workflow = _workflow()
    plan_job = workflow["jobs"]["plan-schema-creation"]
    assert "github.event_name != 'pull_request'" not in plan_job["if"]

    steps = {step.get("name"): step for step in plan_job["steps"]}
    assert "Terraform plan" in steps
    assert "inputs.reset_shared_state" in steps["Terraform plan"]["if"]
    for name in (
        "Back up Terraform state before migration",
        "Terraform apply",
    ):
        condition = steps[name]["if"]
        assert "github.event_name == 'push'" in condition
        assert "inputs.run_apply" in condition

    assert "Ensure sandbox ADLS container exists" not in steps


def test_workflow_has_no_removal_override_and_rejects_delete_actions() -> None:
    workflow = _workflow()
    dispatch_inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert "allow_destroy" not in dispatch_inputs

    steps = workflow["jobs"]["plan-schema-creation"]["steps"]
    policy_step = next(step for step in steps if step.get("name") == "Enforce create-or-update-only plan")
    run_text = policy_step["run"]
    assert 'index("delete")' in run_text
    assert "ALLOW_DESTROY" not in run_text
    assert "allow_destroy" not in run_text
    assert 'if [ "$removal_count" -gt 0 ]' in run_text


def test_deployment_is_main_only_and_uses_protected_environment() -> None:
    workflow = _workflow()
    assert workflow[True]["push"]["branches"] == ["main"]
    environment = workflow["jobs"]["plan-schema-creation"]["environment"]
    assert "schema-creation-plan" in environment
    assert "schema-creation-production" in environment


def test_local_validation_runs_before_cloud_setup() -> None:
    steps = _workflow()["jobs"]["plan-schema-creation"]["steps"]
    names = [step.get("name") for step in steps]
    assert names.index("Validate deployment environment") < names.index("Setup Azure and Databricks")


def test_schema_plan_uses_shared_backend_state() -> None:
    steps = _workflow()["jobs"]["plan-schema-creation"]["steps"]
    step_by_name = {step.get("name"): step for step in steps}

    setup_step = step_by_name["Setup Azure and Databricks"]
    assert setup_step["with"]["tfstate_key_suffix"] == "schema-creation"
    assert "tfstate_key_override" not in setup_step["with"]
    assert "Compute request backend key" not in step_by_name


def test_shared_setup_masks_keyvault_databricks_secret() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    action_text = (repo_root / ".github" / "workflows" / "setup-dbxtf-env" / "action.yml").read_text(
        encoding="utf-8"
    )

    mask_position = action_text.index('echo "::add-mask::$DBX_CLIENT_SECRET"')
    export_position = action_text.index('echo "TF_VAR_databricks_client_secret=$DBX_CLIENT_SECRET"')
    assert mask_position < export_position


def test_schema_workflow_uses_repo_root_paths_for_plan_files() -> None:
    workflow = _workflow()
    plan_step = next(
        step for job in workflow["jobs"].values() for step in job["steps"] if step.get("name") == "Terraform plan"
    )
    run_text = plan_step["run"]

    assert '-var-file="$GITHUB_WORKSPACE/$TFVARS_JSON"' in run_text
    assert '-out="$GITHUB_WORKSPACE/$TFPLAN_BIN"' in run_text
    assert 'target_args+=("-target=$address")' in run_text
    assert '"${target_args[@]}"' in run_text
    assert "../../$TFVARS_JSON" not in run_text
    assert "../../$TFPLAN_BIN" not in run_text


def test_schema_workflow_targets_only_current_request_keys() -> None:
    workflow = _workflow()
    plan_job = workflow["jobs"]["plan-schema-creation"]
    steps = {step.get("name"): step for step in plan_job["steps"]}
    generate_run = steps["Generate request tfvars"]["run"]
    targets_run = steps["Build request Terraform targets"]["run"]

    assert "--existing-request-ids-file" not in generate_run
    assert "--requests-directory" not in generate_run
    assert "schema_creation_requests | keys[]" in targets_run
    assert "communitymart_ad_group_catalog" in targets_run
    assert "Forget state for deleted request sources" not in steps
    assert "Migrate legacy schema state address" not in steps
    assert "Migrate shared community mart catalog grants" not in steps

    normal_steps = [
        step for step in plan_job["steps"] if step.get("name") != "Empty shared schema Terraform state"
    ]
    workflow_run_text = "\n".join(str(step.get("run", "")) for step in normal_steps)
    assert "terraform -chdir=\"$TF_WORKDIR\" state mv" not in workflow_run_text
    assert "terraform -chdir=\"$TF_WORKDIR\" state rm" not in workflow_run_text


def test_manual_reset_backs_up_and_empties_shared_state_without_destroying_resources() -> None:
    workflow = _workflow()
    dispatch_inputs = workflow[True]["workflow_dispatch"]["inputs"]
    plan_job = workflow["jobs"]["plan-schema-creation"]
    steps = plan_job["steps"]
    step_by_name = {step.get("name"): step for step in steps}

    assert dispatch_inputs["reset_shared_state"]["default"] is False
    backup_step = step_by_name["Back up Terraform state before migration"]
    reset_step = step_by_name["Empty shared schema Terraform state"]
    assert steps.index(backup_step) < steps.index(reset_step)
    assert "workflow_dispatch" in reset_step["if"]
    assert "inputs.reset_shared_state" in reset_step["if"]
    assert "state rm" in reset_step["run"]
    assert "state list" in reset_step["run"]
    assert "destroy" not in reset_step["run"]

    for name in ("Generate request tfvars", "Build request Terraform targets", "Terraform plan"):
        assert "inputs.reset_shared_state" in step_by_name[name]["if"]
    assert "inputs.reset_shared_state" in step_by_name["Terraform apply"]["if"]
    assert "inputs.reset_shared_state" in workflow["jobs"]["post-validate-schema-creation"]["if"]


def test_schema_workflow_discovers_added_request_files_only() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    collector = (repo_root / "uda" / "scripts" / "schema-creation" / "collect_request_files.sh").read_text(
        encoding="utf-8"
    )

    assert "--diff-filter=A " in collector
    assert "--diff-filter=AM " not in collector


def test_communitymart_catalog_grants_are_owned_once_at_root() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    root_main = (repo_root / "terraform" / "environments" / "dev" / "main.tf").read_text(encoding="utf-8")
    module_main = (repo_root / "terraform" / "modules" / "schema_creation" / "main.tf").read_text(
        encoding="utf-8"
    )

    assert 'resource "databricks_grant" "communitymart_ad_group_catalog"' in root_main
    assert '"${jsondecode(encoded).catalog}|${jsondecode(encoded).principal}"' in root_main
    assert 'resource "databricks_grant" "communitymart_ad_group_catalog"' not in module_main


def test_schema_module_uses_managed_storage_and_retires_external_locations() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    module_main = (repo_root / "terraform" / "modules" / "schema_creation" / "main.tf").read_text(
        encoding="utf-8"
    )

    assert "storage_root =" not in module_main
    assert module_main.count("ignore_changes        = [storage_root]") == 2
    assert 'resource "databricks_external_location"' not in module_main
    assert 'resource "databricks_grants" "sandbox_external_location_access"' not in module_main
    assert "from = databricks_external_location.sandbox" in module_main
    assert "destroy = false" in module_main


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
