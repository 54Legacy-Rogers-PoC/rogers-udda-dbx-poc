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
    assert "if" not in steps["Terraform plan"]
    condition = steps["Terraform apply"]["if"]
    assert "github.event_name == 'push'" in condition
    assert "inputs.run_apply" in condition

    assert "Ensure sandbox ADLS container exists" not in steps
    assert "Back up Terraform state before migration" not in steps


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
    assert "Plan contains changes outside the current request targets" in run_text
    assert 'change["address"] == target' in run_text


def test_deployment_is_main_only_and_uses_protected_environment() -> None:
    workflow = _workflow()
    assert workflow[True]["push"]["branches"] == ["main"]
    expected_paths = {
        "requests/schema-creation/dev/**",
        "requests/schema-creation/qa/**",
        "requests/schema-creation/prd/**",
    }
    assert set(workflow[True]["push"]["paths"]) == expected_paths
    assert set(workflow[True]["pull_request"]["paths"]) == expected_paths
    environment = workflow["jobs"]["plan-schema-creation"]["environment"]
    assert "schema-creation-{0}-plan" in environment
    assert "matrix.deployment_environment" in environment
    post_environment = workflow["jobs"]["post-validate-schema-creation"]["environment"]
    assert "schema-creation-{0}" in post_environment
    assert "matrix.deployment_environment" in post_environment


def test_local_validation_runs_before_cloud_setup() -> None:
    steps = _workflow()["jobs"]["plan-schema-creation"]["steps"]
    names = [step.get("name") for step in steps]
    assert names.index("Validate deployment environment") < names.index("Setup Azure and Databricks")
    validation_step = next(step for step in steps if step.get("name") == "Validate deployment environment")
    assert '--expected-environment "$EXPECTED_ENVIRONMENT_CODE"' in validation_step["run"]
    assert '--github-output "$GITHUB_OUTPUT"' in validation_step["run"]


def test_schema_jobs_use_environment_scoped_shared_backend_state() -> None:
    workflow = _workflow()
    plan_steps = workflow["jobs"]["plan-schema-creation"]["steps"]
    post_steps = workflow["jobs"]["post-validate-schema-creation"]["steps"]

    plan_setup = next(step for step in plan_steps if step.get("name") == "Setup Azure and Databricks")
    post_setup = next(step for step in post_steps if step.get("name") == "Setup Azure and Databricks")

    assert plan_setup["with"]["tfstate_key_suffix"] == "${{ matrix.tfstate_key_suffix }}"
    assert post_setup["with"]["tfstate_key_suffix"] == "${{ matrix.tfstate_key_suffix }}"
    assert plan_setup["with"]["keyvault_name"] == "${{ steps.environment_config.outputs.keyvault_name }}"
    assert post_setup["with"]["keyvault_name"] == "${{ steps.environment_config.outputs.keyvault_name }}"
    assert "${{ secrets.KEYVAULT_NAME }}" not in str(workflow)
    configured_secret_inputs = {
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
    assert configured_secret_inputs <= plan_setup["with"].keys()
    assert configured_secret_inputs <= post_setup["with"].keys()
    assert "tfstate_key_override" not in plan_setup["with"]
    assert "tfstate_key_override" not in post_setup["with"]
    plan_env = workflow["jobs"]["plan-schema-creation"]["env"]
    assert plan_env["REQUESTS_DIRECTORY"] == "requests/schema-creation/${{ matrix.deployment_environment }}"
    assert plan_env["EXPECTED_ENVIRONMENT_CODE"] == "${{ matrix.environment_code }}"


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
    generate_run = steps["Generate shared-state tfvars"]["run"]
    targets_run = steps["Build request Terraform targets"]["run"]

    assert "--existing-request-ids-file" in generate_run
    assert '--requests-directory "$REQUESTS_DIRECTORY"' in generate_run
    assert '--current-targets-json "$CURRENT_TARGETS_JSON"' in generate_run
    assert 'keys[] | "module.schema_creation' in targets_run
    assert '"$CURRENT_TARGETS_JSON"' in targets_run
    assert "communitymart_ad_group_catalog" in targets_run
    assert "Forget state for deleted request sources" not in steps
    assert "Migrate legacy schema state address" not in steps
    assert "Migrate shared community mart catalog grants" not in steps

    workflow_run_text = "\n".join(str(step.get("run", "")) for step in plan_job["steps"])
    assert "terraform -chdir=\"$TF_WORKDIR\" state mv" not in workflow_run_text
    assert "terraform -chdir=\"$TF_WORKDIR\" state rm" not in workflow_run_text


def test_schema_workflow_discovers_added_request_files_only_without_rejecting_other_changes() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    collector = (repo_root / "uda" / "scripts" / "schema-creation" / "collect_request_files.sh").read_text(
        encoding="utf-8"
    )

    assert "--diff-filter=A " in collector
    assert "--diff-filter=AM " not in collector
    assert "--diff-filter=MD " not in collector
    assert "Existing schema requests are immutable" not in collector
    assert 'git log --format=%H -n 1 "$BASE_SHA_EVENT" -- "$changed"' in collector
    assert "Skipping restored request path" in collector
    assert "requests/schema-creation/qa" in collector
    assert "requests/schema-creation/prd" in collector
    assert '"schema-creation-v2-dev"' in collector
    assert '"schema-creation-v2-qa"' in collector
    assert '"schema-creation-v2"' in collector
    assert r'\"deployment_environment\"' in collector
    assert r'\"environment_code\"' in collector
    assert r'\"tfstate_key_suffix\"' in collector
    assert "printf '%s|%s|%s\\n'" in collector


def test_schema_workflow_has_no_obsolete_state_backup_or_artifact_download() -> None:
    workflow = _workflow()
    plan_steps = workflow["jobs"]["plan-schema-creation"]["steps"]
    plan_names = [step.get("name") for step in plan_steps]
    post_names = [step.get("name") for step in workflow["jobs"]["post-validate-schema-creation"]["steps"]]

    assert "Back up Terraform state before migration" not in plan_names
    assert "Download plan artifacts" not in post_names
    publish_step = next(step for step in plan_steps if step.get("name") == "Publish plan outputs")
    assert "!${{ steps.prep_paths.outputs.output_dir }}/schema-creation.tfplan" in publish_step["with"]["path"]


def test_communitymart_catalog_grants_are_owned_once_at_root() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    root_main = (repo_root / "terraform" / "environments" / "dev" / "main.tf").read_text(encoding="utf-8")
    module_main = (repo_root / "terraform" / "modules" / "schema_creation" / "main.tf").read_text(
        encoding="utf-8"
    )

    assert 'resource "databricks_grant" "communitymart_ad_group_catalog"' in root_main
    assert '"${jsondecode(encoded).catalog}|${jsondecode(encoded).principal}"' in root_main
    assert "prevent_destroy = true" in root_main
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
