"""Build import tfvars JSON for REMOVE/REVOKE rows.

Copies rows with REMOVE/REVOKE activity and rewrites activity to ADD so terraform
import can map to existing add-resource addresses.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_import_tfvars(src: Path, dst: Path) -> int:
    payload = json.loads(src.read_text(encoding="utf-8"))
    records = payload.get("object_access_records", [])

    import_records = []
    for record in records:
        activity = str(record.get("activity", "")).strip().upper()
        if activity in {"REMOVE", "REVOKE"}:
            rewritten = dict(record)
            rewritten["activity"] = "ADD"
            import_records.append(rewritten)

    payload["object_access_records"] = import_records
    dst.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(import_records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build import tfvars for REMOVE/REVOKE rows")
    parser.add_argument("--input-json", required=True, help="Path to object-access.auto.tfvars.json")
    parser.add_argument("--output-json", required=True, help="Path to object-access-import.auto.tfvars.json")
    return parser.parse_args()


def _resolve_repo_json_path(path_input: str, *, must_exist: bool) -> Path:
    repo_root = Path.cwd().resolve()
    raw_path = Path(path_input)
    resolved = (repo_root / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()

    if repo_root != resolved and repo_root not in resolved.parents:
        raise ValueError(f"Path escapes workspace root: {path_input}")
    if resolved.suffix.lower() != ".json":
        raise ValueError(f"Path must use .json extension: {path_input}")
    if must_exist and not resolved.is_file():
        raise ValueError(f"Input file not found: {path_input}")
    return resolved


def main() -> int:
    args = parse_args()
    try:
        src = _resolve_repo_json_path(args.input_json, must_exist=True)
        dst = _resolve_repo_json_path(args.output_json, must_exist=False)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    dst.parent.mkdir(parents=True, exist_ok=True)
    count = build_import_tfvars(src, dst)
    print(f"Import tfvars written: {dst}")
    print(f"Import target rows: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
