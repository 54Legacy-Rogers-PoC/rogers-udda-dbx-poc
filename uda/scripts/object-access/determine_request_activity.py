"""Determine normalized request activity from generated tfvars JSON.

Outputs one of: ADD, REMOVE, MIXED.
REVOKE is normalized to REMOVE.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VALID_SINGLE = {"ADD", "REMOVE"}


def determine_activity(tfvars_json: Path) -> str:
    payload = json.loads(tfvars_json.read_text(encoding="utf-8"))
    records = payload.get("object_access_records", [])

    activities = sorted(
        {
            str(record.get("activity", "")).strip().upper()
            for record in records
            if str(record.get("activity", "")).strip()
        }
    )

    if not activities:
        raise ValueError("No activity found in parsed template rows")

    normalized: set[str] = set()
    for activity in activities:
        if activity == "REVOKE":
            normalized.add("REMOVE")
        else:
            normalized.add(activity)

    if len(normalized) == 1:
        value = next(iter(normalized))
        if value in VALID_SINGLE:
            return value

    if normalized == {"ADD", "REMOVE"}:
        return "MIXED"

    raise ValueError(f"Unsupported activity combination in a single template. Found={sorted(normalized)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Determine request activity from tfvars JSON")
    parser.add_argument("--tfvars-json", required=True, help="Path to object-access.auto.tfvars.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = determine_activity(Path(args.tfvars_json).resolve())
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
