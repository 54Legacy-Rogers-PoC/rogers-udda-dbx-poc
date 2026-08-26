"""Build import tfvars JSON for REMOVE/REVOKE rows.

Copies rows with REMOVE/REVOKE activity and rewrites activity to ADD so terraform
import can map to existing add-resource addresses.
"""

from __future__ import annotations

import argparse
import json
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


def main() -> int:
    args = parse_args()
    src = Path(args.input_json).resolve()
    dst = Path(args.output_json).resolve()
    count = build_import_tfvars(src, dst)
    print(f"Import tfvars written: {dst}")
    print(f"Import target rows: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
