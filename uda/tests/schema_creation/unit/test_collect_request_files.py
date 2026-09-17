from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_workflow_dispatch_accepts_yaml_alias_for_existing_yml_file(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    request_dir = repo_root / "requests" / "schema-creation" / "dev"
    request_dir.mkdir(parents=True)
    request_file = request_dir / "RITM3434.yml"
    request_file.write_text("request_id: \"RITM3434\"\n", encoding="utf-8")

    source_script = Path(__file__).resolve().parents[4] / "uda" / "scripts" / "schema-creation" / "collect_request_files.sh"
    output_file = tmp_path / "github-output.txt"

    env = os.environ.copy()
    env["GITHUB_EVENT_NAME"] = "workflow_dispatch"
    env["REQUEST_FILE_INPUT"] = "requests/schema-creation/dev/RITM3434.yaml"
    env["REQUEST_FILES_INPUT"] = ""
    env["GITHUB_OUTPUT"] = str(output_file)

    script_text = source_script.read_text(encoding="utf-8").replace("\r\n", "\n")
    result = subprocess.run(
        ["bash", "-lc", script_text],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    output = output_file.read_text(encoding="utf-8")
    assert "has_requests=true" in output
    assert "RITM3434.yml" in output
