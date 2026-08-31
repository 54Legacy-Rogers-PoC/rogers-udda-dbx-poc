import json
import subprocess
import sys
from pathlib import Path


def run_process_request(repo_root: Path, request_file: Path, config_file: Path, output_dir: Path):
    cmd = [
        sys.executable,
        str(repo_root / "uda" / "scripts" / "process_service_account_request.py"),
        "--request-file",
        str(request_file),
        "--config-file",
        str(config_file),
        "--output-dir",
        str(output_dir),
    ]
    return subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)


def seed_repo_layout(repo_root: Path):
    (repo_root / "uda" / "scripts").mkdir(parents=True)
    (repo_root / "uda" / "config").mkdir(parents=True)
    (repo_root / "uda" / "requests" / "service-account").mkdir(parents=True)

    source_script = Path(__file__).parents[1] / "scripts" / "process_service_account_request.py"
    source_config = Path(__file__).parents[1] / "config" / "environments.yaml"

    (repo_root / "uda" / "scripts" / "process_service_account_request.py").write_text(
        source_script.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo_root / "uda" / "config" / "environments.yaml").write_text(
        source_config.read_text(encoding="utf-8"), encoding="utf-8"
    )


def test_create_with_ad_group_success(tmp_path: Path):
    repo_root = tmp_path
    seed_repo_layout(repo_root)

    request_yaml = """request_id: RITMSA1001
platform: databricks
request_type: service_account
environment: Production
activity_type: create
requester_email: service.requestor@example.com
service_account_type: Business
service_account_name: SERV_SALES_SLS_ORA_DTB_PRD
service_account_owner: Data Platform Team
attached_to_ad_group: true
ad_group_name: DTB_FINANCE_ANALYTICS_PRD
justification: Finance reporting automation
"""
    request_path = repo_root / "uda" / "requests" / "service-account" / "RITMSA1001.yaml"
    request_path.write_text(request_yaml, encoding="utf-8")

    output_dir = repo_root / "generated"
    result = run_process_request(repo_root, request_path, repo_root / "uda" / "config" / "environments.yaml", output_dir)

    assert result.returncode == 0, result.stderr + result.stdout

    metadata = json.loads((output_dir / "request_metadata.json").read_text(encoding="utf-8"))
    assert metadata["activity_type"] == "CREATE"
    assert metadata["requester_email"] == "service.requestor@example.com"
    assert metadata["requires_terraform"] is False
    assert metadata["environment"] == "PRD"


def test_add_to_cluster_sets_requires_terraform(tmp_path: Path):
    repo_root = tmp_path
    seed_repo_layout(repo_root)

    request_yaml = """request_id: RITMSA1002
platform: databricks
request_type: service_account
environment: Development
activity_type: add_to_cluster
service_account_type: IT
service_account_name: SERV_DATA_FINANCE_PBI_DEV
service_account_owner: Analytics Team
cluster_name: FINANCE_ANALYTICS
justification: Grant cluster execution rights
"""
    request_path = repo_root / "uda" / "requests" / "service-account" / "RITMSA1002.yaml"
    request_path.write_text(request_yaml, encoding="utf-8")

    output_dir = repo_root / "generated"
    result = run_process_request(repo_root, request_path, repo_root / "uda" / "config" / "environments.yaml", output_dir)

    assert result.returncode == 0, result.stderr + result.stdout

    metadata = json.loads((output_dir / "request_metadata.json").read_text(encoding="utf-8"))
    tfvars = json.loads((output_dir / "terraform.auto.tfvars.json").read_text(encoding="utf-8"))
    assert metadata["activity_type"] == "ADD_TO_CLUSTER"
    assert metadata["requires_terraform"] is True
    assert metadata["cluster_name"] == "FINANCE_ANALYTICS"
    assert metadata["cluster_permission_level"] == "CAN_ATTACH_TO"
    assert len(tfvars["service_account_cluster_access_records"]) == 1
    assert tfvars["service_account_cluster_access_records"][0]["activity"] == "ADD_TO_CLUSTER"
    assert tfvars["service_account_cluster_access_records"][0]["cluster_id"] == "FINANCE_ANALYTICS"


def test_remove_from_cluster_builds_cluster_access_record(tmp_path: Path):
    repo_root = tmp_path
    seed_repo_layout(repo_root)

    request_yaml = """request_id: RITMSA1004
platform: databricks
request_type: service_account
environment: Development
activity_type: remove_from_cluster
service_account_type: IT
service_account_name: SERV_DATA_FINANCE_PBI_DEV
service_account_owner: Analytics Team
cluster_name: FINANCE_ANALYTICS
cluster_id: 0209-123456-abc123
cluster_permission_level: CAN_MANAGE
justification: Revoke cluster execution rights
"""
    request_path = repo_root / "uda" / "requests" / "service-account" / "RITMSA1004.yaml"
    request_path.write_text(request_yaml, encoding="utf-8")

    output_dir = repo_root / "generated"
    result = run_process_request(repo_root, request_path, repo_root / "uda" / "config" / "environments.yaml", output_dir)

    assert result.returncode == 0, result.stderr + result.stdout

    metadata = json.loads((output_dir / "request_metadata.json").read_text(encoding="utf-8"))
    tfvars = json.loads((output_dir / "terraform.auto.tfvars.json").read_text(encoding="utf-8"))
    assert metadata["activity_type"] == "REMOVE_FROM_CLUSTER"
    assert metadata["requires_terraform"] is True
    assert metadata["cluster_id"] == "0209-123456-abc123"
    assert metadata["cluster_permission_level"] == "CAN_MANAGE"
    assert len(tfvars["service_account_cluster_access_records"]) == 1
    assert tfvars["service_account_cluster_access_records"][0]["activity"] == "REMOVE_FROM_CLUSTER"
    assert tfvars["service_account_cluster_access_records"][0]["cluster_id"] == "0209-123456-abc123"


def test_add_to_ad_group_is_not_supported(tmp_path: Path):
    repo_root = tmp_path
    seed_repo_layout(repo_root)

    request_yaml = """request_id: RITMSA1003
platform: databricks
request_type: service_account
environment: QA/Test
activity_type: add_to_ad_group
service_account_type: Business
service_account_name: SERV_DATA_FINANCE_PBI_QA
service_account_owner: Analytics Team
justification: Align ownership and group mapping
"""
    request_path = repo_root / "uda" / "requests" / "service-account" / "RITMSA1003.yaml"
    request_path.write_text(request_yaml, encoding="utf-8")

    output_dir = repo_root / "generated"
    result = run_process_request(repo_root, request_path, repo_root / "uda" / "config" / "environments.yaml", output_dir)

    assert result.returncode != 0
    assert "Unsupported activity_type" in (result.stderr + result.stdout)


def test_remove_from_ad_group_is_not_supported(tmp_path: Path):
    repo_root = tmp_path
    seed_repo_layout(repo_root)

    request_yaml = """request_id: RITMSA1005
platform: databricks
request_type: service_account
environment: QA/Test
activity_type: remove_from_ad_group
service_account_type: Business
service_account_name: SERV_DATA_FINANCE_PBI_QA
service_account_owner: Analytics Team
justification: Decommission group mapping
"""
    request_path = repo_root / "uda" / "requests" / "service-account" / "RITMSA1005.yaml"
    request_path.write_text(request_yaml, encoding="utf-8")

    output_dir = repo_root / "generated"
    result = run_process_request(repo_root, request_path, repo_root / "uda" / "config" / "environments.yaml", output_dir)

    assert result.returncode != 0
    assert "Unsupported activity_type" in (result.stderr + result.stdout)
