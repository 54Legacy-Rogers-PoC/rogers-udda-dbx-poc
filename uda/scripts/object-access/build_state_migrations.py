#!/usr/bin/env python3
"""Build state-move pairs for legacy privilege-specific grant addresses."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


ADDRESS_PATTERN = re.compile(
    r'^(module\.object_access\.databricks_grant\.(?:catalog_add|schema_add|view_add))\["([^"]+)"\]$'
)


def build_migrations(addresses: list[str]) -> list[tuple[str, str]]:
    migrations: list[tuple[str, str]] = []
    for address in addresses:
        normalized = address.strip()
        match = ADDRESS_PATTERN.match(normalized)
        if not match:
            continue
        parts = match.group(2).split("|")
        if len(parts) != 8:
            continue
        grouped_address = f'{match.group(1)}["{"|".join(parts[:7])}"]'
        migrations.append((normalized, grouped_address))
    return sorted(migrations)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Terraform grant state migration pairs")
    parser.add_argument("--state-list", required=True)
    parser.add_argument("--output-tsv", required=True)
    args = parser.parse_args()

    addresses = Path(args.state_list).read_text(encoding="utf-8").splitlines()
    migrations = build_migrations(addresses)
    output = Path(args.output_tsv)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(f"{old}\t{new}\n" for old, new in migrations), encoding="utf-8")
    print(f"Legacy grant state migrations found: {len(migrations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())