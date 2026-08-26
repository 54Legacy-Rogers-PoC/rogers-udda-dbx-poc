"""Build import tfvars JSON for REMOVE/REVOKE rows.

Copies rows with REMOVE/REVOKE activity and rewrites activity to ADD so terraform
import can map to existing add-resource addresses.
"""

from __future__ import annotations

import argparse
import json
import sys

INPUT_FILE_NAME = "object-access.auto.tfvars.json"
OUTPUT_FILE_NAME = "object-access-import.auto.tfvars.json"


def build_import_tfvars() -> int:
    payload = json.loads(open(INPUT_FILE_NAME, "r", encoding="utf-8").read())
    records = payload.get("object_access_records", [])

    import_records = []
    for record in records:
        activity = str(record.get("activity", "")).strip().upper()
        if activity in {"REMOVE", "REVOKE"}:
            rewritten = dict(record)
            rewritten["activity"] = "ADD"
            import_records.append(rewritten)

    payload["object_access_records"] = import_records
    with open(OUTPUT_FILE_NAME, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2))
    return len(import_records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build import tfvars for REMOVE/REVOKE rows")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate input/output location and exit without writing output",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        with open(INPUT_FILE_NAME, "r", encoding="utf-8"):
            pass
    except OSError as exc:
        print(f"Input file not found in current directory: {INPUT_FILE_NAME} ({exc})", file=sys.stderr)
        return 2

    if args.verify_only:
        print(f"Input validated: {INPUT_FILE_NAME}")
        print(f"Output target: {OUTPUT_FILE_NAME}")
        return 0

    count = build_import_tfvars()
    print(f"Import tfvars written: {OUTPUT_FILE_NAME}")
    print(f"Import target rows: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
