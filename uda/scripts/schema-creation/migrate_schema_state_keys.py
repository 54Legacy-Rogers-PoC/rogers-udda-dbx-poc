"""Move schema resources from request-keyed to schema-keyed module addresses."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

MODULE_ADDRESS = re.compile(r'^module\.schema_creation\["([^"]+)"\](\..+)$')
SANDBOX_RESOURCES = {
    ".databricks_schema.sandbox[0]",
    ".databricks_external_location.sandbox[0]",
    ".databricks_grants.sandbox_external_location_access[0]",
    ".databricks_grant.sandbox_owner[0]",
    ".databricks_grant.sandbox_ad_group[0]",
}
COMMUNITYMART_RESOURCES = {
    ".databricks_schema.communitymart[0]",
    ".databricks_grant.communitymart_owner[0]",
    ".databricks_grant.communitymart_ad_group_schema[0]",
}


def build_state_moves(state_addresses: list[str], targets: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    target_keys_by_request: dict[tuple[str, str], str] = {}
    request_ids = {str(target["request_id"]) for target in targets.values()}
    for target_key, target in targets.items():
        identity = (str(target["request_id"]), str(target["target_type"]))
        if identity in target_keys_by_request:
            raise ValueError(f"Multiple {identity[1]} targets found for request {identity[0]}")
        target_keys_by_request[identity] = target_key

    existing_addresses = set(state_addresses)
    moves: list[tuple[str, str]] = []
    for source in state_addresses:
        match = MODULE_ADDRESS.match(source)
        if match is None:
            continue
        module_key, suffix = match.groups()
        if module_key not in request_ids:
            continue

        if suffix in SANDBOX_RESOURCES:
            target_type = "sandbox"
        elif suffix in COMMUNITYMART_RESOURCES:
            target_type = "communitymart"
        else:
            raise ValueError(f"Unsupported resource in request-keyed schema state: {source}")

        target_key = target_keys_by_request.get((module_key, target_type))
        if target_key is None:
            raise ValueError(f"No {target_type} schema target found for state address {source}")
        destination = f'module.schema_creation["{target_key}"]{suffix}'
        if destination in existing_addresses:
            raise ValueError(f"State destination already exists: {destination}")
        moves.append((source, destination))

    return moves


def render_moved_blocks(moves: list[tuple[str, str]]) -> str:
    return "\n".join(
        f"moved {{\n  from = {source}\n  to   = {destination}\n}}\n"
        for source, destination in moves
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-addresses-file", required=True)
    parser.add_argument("--tfvars-json", required=True)
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args()

    tfvars = json.loads(Path(args.tfvars_json).read_text(encoding="utf-8"))
    targets = tfvars.get("schema_creation_requests")
    if not isinstance(targets, dict):
        raise ValueError("schema_creation_requests must be a map")

    state_addresses = Path(args.state_addresses_file).read_text(encoding="utf-8").splitlines()
    moves = build_state_moves(state_addresses, targets)
    output_file = Path(args.output_file).resolve()
    output_file.write_text(render_moved_blocks(moves), encoding="utf-8")
    if not moves:
        print("Request-keyed schema state is not present; migration is not required.")
        return 0

    for source, destination in moves:
        print(f"Planning state address move: {source} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
