import json
import subprocess
import sys
from pathlib import Path


def run_invoke(payload_file: Path, status_file: Path, mode: str):
    cmd = [
        sys.executable,
        str(Path(__file__).parents[1] / "scripts" / "invoke_cm_writeback.py"),
        "--payload-file",
        str(payload_file),
        "--status-file",
        str(status_file),
        "--mode",
        mode,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_mock_mode_writes_success_status(tmp_path: Path):
    payload_file = tmp_path / "governance_payload.json"
    status_file = tmp_path / "cm_writeback_status.json"

    payload = {
        "request_id": "RITMSA2001",
        "activity_type": "CHANGE_OWNERSHIP",
    }
    payload_file.write_text(json.dumps(payload), encoding="utf-8")

    result = run_invoke(payload_file=payload_file, status_file=status_file, mode="mock")

    assert result.returncode == 0, result.stderr + result.stdout
    status = json.loads(status_file.read_text(encoding="utf-8"))
    assert status["cm_writeback_status"] == "SUCCESS"
    assert status["mode"] == "mock"
    assert status["request_id"] == "RITMSA2001"


def test_missing_payload_file_fails(tmp_path: Path):
    payload_file = tmp_path / "missing_payload.json"
    status_file = tmp_path / "cm_writeback_status.json"

    result = run_invoke(payload_file=payload_file, status_file=status_file, mode="mock")

    assert result.returncode != 0
    assert "Payload file not found" in (result.stderr + result.stdout)
