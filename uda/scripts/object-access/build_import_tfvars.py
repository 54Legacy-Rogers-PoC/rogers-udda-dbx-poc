"""Build import tfvars JSON for REMOVE/REVOKE rows.

Copies rows with REMOVE/REVOKE activity and rewrites activity to ADD so terraform
import can map to existing add-resource addresses.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ALLOWED_INPUT_NAME = "object-access.auto.tfvars.json"
ALLOWED_OUTPUT_NAME = "object-access-import.auto.tfvars.json"


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
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate input/output location and exit without writing output",
    )
    return parser.parse_args()


def _resolve_input_json() -> Path:
    src = Path.cwd() / ALLOWED_INPUT_NAME
    if not src.is_file():
        raise ValueError(f"Input file not found in current directory: {src}")
    return src.resolve()


def _derived_output_path(src: Path) -> Path:
    # Keep output naming deterministic and not user-controlled.
    return src.with_name(ALLOWED_OUTPUT_NAME)


def main() -> int:
    args = parse_args()
    try:
        src = _resolve_input_json()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    dst = _derived_output_path(src)
    if args.verify_only:
        print(f"Input validated: {src}")
        print(f"Output target: {dst}")
        return 0

    dst.parent.mkdir(parents=True, exist_ok=True)
    count = build_import_tfvars(src, dst)
    print(f"Import tfvars written: {dst}")
    print(f"Import target rows: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
