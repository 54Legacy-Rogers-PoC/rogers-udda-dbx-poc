import json
import subprocess
import sys
from pathlib import Path


def run_process_request(repo_root: Path, request_file: Path, config_file: Path, output_dir: Path):
    cmd = [
        sys.executable,
        str(repo_root / "uda" / "scripts" / "process_request.py"),
        "--request-file",
        str(request_file),
        "--config-file",
        str(config_file),
        "--output-dir",
        str(output_dir),
    ]
    return subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)


def test_success_path(tmp_path: Path):
    repo_root = tmp_path

    (repo_root / "uda" / "scripts").mkdir(parents=True)
    (repo_root / "uda" / "config").mkdir(parents=True)
    (repo_root / "uda" / "attachments" / "object-access").mkdir(parents=True)
    (repo_root / "uda" / "requests" / "object-access").mkdir(parents=True)

    source_script = Path(__file__).parents[1] / "scripts" / "process_request.py"
    source_config = Path(__file__).parents[1] / "config" / "environments.yaml"

    (repo_root / "uda" / "scripts" / "process_request.py").write_text(
        source_script.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo_root / "uda" / "config" / "environments.yaml").write_text(
        source_config.read_text(encoding="utf-8"), encoding="utf-8"
    )

    request_yaml = """request_id: RITM999001
platform: databricks
request_type: object_access
environment: Production
activity_type: ADD
requester_email: object.requestor@example.com
access_for: ad_group
ad_group_name: DTB_DATA_ENG
template_file: ObjectAccessTemplate.csv
justification: Team access
"""
    (repo_root / "uda" / "requests" / "object-access" / "RITM999001.yaml").write_text(request_yaml, encoding="utf-8")

    template_csv = """Object Type,Activity,Catalog Name,Schema Name,Object Name,Folder Path,Privileges
catalog,ADD,finance_catalog,,,,USE_CATALOG
schema,ADD,finance_catalog,reporting,,,\"USE_SCHEMA,SELECT\"
"""
    (repo_root / "uda" / "attachments" / "object-access" / "ObjectAccessTemplate.csv").write_text(
        template_csv, encoding="utf-8"
    )

    output_dir = repo_root / "generated"

    result = run_process_request(
        repo_root=repo_root,
        request_file=repo_root / "uda" / "requests" / "object-access" / "RITM999001.yaml",
        config_file=repo_root / "uda" / "config" / "environments.yaml",
        output_dir=output_dir,
    )

    assert result.returncode == 0, result.stderr + result.stdout

    tfvars = json.loads((output_dir / "terraform.auto.tfvars.json").read_text(encoding="utf-8"))
    metadata = json.loads((output_dir / "request_metadata.json").read_text(encoding="utf-8"))

    assert tfvars["request_id"] == "RITM999001"
    assert tfvars["environment"] == "PRD"
    assert len(tfvars["object_access_records"]) == 2
    assert metadata["requester_email"] == "object.requestor@example.com"
    assert metadata["object_count"] == 2


def test_duplicate_row_fails(tmp_path: Path):
    repo_root = tmp_path

    (repo_root / "uda" / "scripts").mkdir(parents=True)
    (repo_root / "uda" / "config").mkdir(parents=True)
    (repo_root / "uda" / "attachments" / "object-access").mkdir(parents=True)
    (repo_root / "uda" / "requests" / "object-access").mkdir(parents=True)

    source_script = Path(__file__).parents[1] / "scripts" / "process_request.py"
    source_config = Path(__file__).parents[1] / "config" / "environments.yaml"

    (repo_root / "uda" / "scripts" / "process_request.py").write_text(
        source_script.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo_root / "uda" / "config" / "environments.yaml").write_text(
        source_config.read_text(encoding="utf-8"), encoding="utf-8"
    )

    request_yaml = """request_id: RITM999002
platform: databricks
request_type: object_access
environment: QA/Test
activity_type: ADD
access_for: service_account
service_account_name: svc_uda_dbx
template_file: ObjectAccessTemplate.csv
justification: Automation access
"""
    (repo_root / "uda" / "requests" / "object-access" / "RITM999002.yaml").write_text(request_yaml, encoding="utf-8")

    template_csv = """Object Type,Activity,Catalog Name,Schema Name,Object Name,Folder Path,Privileges
catalog,ADD,finance_catalog,,,,USE_CATALOG
catalog,ADD,finance_catalog,,,,USE_CATALOG
"""
    (repo_root / "uda" / "attachments" / "object-access" / "ObjectAccessTemplate.csv").write_text(
        template_csv, encoding="utf-8"
    )

    output_dir = repo_root / "generated"

    result = run_process_request(
        repo_root=repo_root,
        request_file=repo_root / "uda" / "requests" / "object-access" / "RITM999002.yaml",
        config_file=repo_root / "uda" / "config" / "environments.yaml",
        output_dir=output_dir,
    )

    assert result.returncode != 0
    assert "Duplicate template record detected" in (result.stderr + result.stdout)


def test_mixed_row_activity_fails(tmp_path: Path):
    repo_root = tmp_path

    (repo_root / "uda" / "scripts").mkdir(parents=True)
    (repo_root / "uda" / "config").mkdir(parents=True)
    (repo_root / "uda" / "attachments" / "object-access").mkdir(parents=True)
    (repo_root / "uda" / "requests" / "object-access").mkdir(parents=True)

    source_script = Path(__file__).parents[1] / "scripts" / "process_request.py"
    source_config = Path(__file__).parents[1] / "config" / "environments.yaml"

    (repo_root / "uda" / "scripts" / "process_request.py").write_text(
        source_script.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo_root / "uda" / "config" / "environments.yaml").write_text(
        source_config.read_text(encoding="utf-8"), encoding="utf-8"
    )

    request_yaml = """request_id: RITM999003
platform: databricks
request_type: object_access
environment: Development
activity_type: ADD
access_for: ad_group
ad_group_name: DTB_DATA_ENG
template_file: ObjectAccessTemplate.csv
justification: Team access
"""
    (repo_root / "uda" / "requests" / "object-access" / "RITM999003.yaml").write_text(request_yaml, encoding="utf-8")

    template_csv = """Object Type,Activity,Catalog Name,Schema Name,Object Name,Folder Path,Privileges
catalog,ADD,finance_catalog,,,,USE_CATALOG
schema,REMOVE,finance_catalog,reporting,,,USE_SCHEMA
"""
    (repo_root / "uda" / "attachments" / "object-access" / "ObjectAccessTemplate.csv").write_text(
        template_csv, encoding="utf-8"
    )

    output_dir = repo_root / "generated"

    result = run_process_request(
        repo_root=repo_root,
        request_file=repo_root / "uda" / "requests" / "object-access" / "RITM999003.yaml",
        config_file=repo_root / "uda" / "config" / "environments.yaml",
        output_dir=output_dir,
    )

    assert result.returncode != 0
    assert "Submit ADD and REMOVE in separate requests" in (result.stderr + result.stdout)
