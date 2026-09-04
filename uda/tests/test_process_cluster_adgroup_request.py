import json
import subprocess
import sys
from pathlib import Path


def run_process_request(repo_root: Path, request_file: Path, config_file: Path, output_dir: Path):
    cmd = [
        sys.executable,
        str(repo_root / "uda" / "scripts" / "cluster-adgroup" / "process_cluster_adgroup_request.py"),
        "--request-file",
        str(request_file),
        "--config-file",
        str(config_file),
        "--output-dir",
        str(output_dir),
    ]
    return subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)


def seed_repo_layout(repo_root: Path):
    (repo_root / "uda" / "scripts" / "cluster-adgroup").mkdir(parents=True)
    (repo_root / "uda" / "config").mkdir(parents=True)
    (repo_root / "uda" / "requests" / "cluster-adgroup").mkdir(parents=True)

    source_script = Path(__file__).parents[1] / "scripts" / "cluster-adgroup" / "process_cluster_adgroup_request.py"
    source_config = Path(__file__).parents[1] / "config" / "environments.yaml"

    (repo_root / "uda" / "scripts" / "cluster-adgroup" / "process_cluster_adgroup_request.py").write_text(
        source_script.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo_root / "uda" / "config" / "environments.yaml").write_text(
        source_config.read_text(encoding="utf-8"), encoding="utf-8"
    )


def test_add_cluster_ad_group_success(tmp_path: Path):
    repo_root = tmp_path
    seed_repo_layout(repo_root)

    request_yaml = """request_id: RITMAG1001
platform: databricks
request_type: cluster_ad_group
environment: Development
activity_type: ADD
cluster_name: FINANCE_ANALYTICS_DEV
cluster_id: 0821-161748-z2lj0o0q
ad_group_name: az_dtb_dev_allwrk_it_edg_rdr_gg
justification: Associate AD group
"""
    request_path = repo_root / "uda" / "requests" / "cluster-adgroup" / "RITMAG1001.yaml"
    request_path.write_text(request_yaml, encoding="utf-8")

    output_dir = repo_root / "generated"
    result = run_process_request(repo_root, request_path, repo_root / "uda" / "config" / "environments.yaml", output_dir)

    assert result.returncode == 0, result.stderr + result.stdout

    tfvars = json.loads((output_dir / "terraform.auto.tfvars.json").read_text(encoding="utf-8"))
    metadata = json.loads((output_dir / "request_metadata.json").read_text(encoding="utf-8"))

    assert metadata["environment"] == "DEV"
    assert metadata["activity_type"] == "ADD"
    assert metadata["ad_group_name"] == "az_dtb_dev_allwrk_it_edg_rdr_gg"
    assert len(tfvars["cluster_ad_group_access_records"]) == 1
    assert tfvars["cluster_ad_group_access_records"][0]["cluster_id"] == "0821-161748-z2lj0o0q"


def test_invalid_activity_fails(tmp_path: Path):
    repo_root = tmp_path
    seed_repo_layout(repo_root)

    request_yaml = """request_id: RITMAG1002
platform: databricks
request_type: cluster_ad_group
environment: Development
activity_type: UPDATE
cluster_name: FINANCE_ANALYTICS_DEV
ad_group_name: az_dtb_dev_allwrk_it_edg_rdr_gg
justification: Invalid activity for test
"""
    request_path = repo_root / "uda" / "requests" / "cluster-adgroup" / "RITMAG1002.yaml"
    request_path.write_text(request_yaml, encoding="utf-8")

    output_dir = repo_root / "generated"
    result = run_process_request(repo_root, request_path, repo_root / "uda" / "config" / "environments.yaml", output_dir)

    assert result.returncode != 0
    assert "activity_type must be ADD or REMOVE" in (result.stderr + result.stdout)
