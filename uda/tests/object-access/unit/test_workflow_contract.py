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