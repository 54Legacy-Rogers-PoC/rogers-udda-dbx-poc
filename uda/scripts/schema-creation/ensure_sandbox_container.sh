#!/usr/bin/env bash
set -euo pipefail

# Ensure the sandbox ADLS container exists before Terraform creates the external location.

if [ -z "${NORMALIZED_JSON:-}" ] || [ ! -f "$NORMALIZED_JSON" ]; then
  echo "NORMALIZED_JSON must point to an existing normalized request file." >&2
  exit 1
fi

if [ -z "${AZURE_SUBSCRIPTION_ID:-}" ]; then
  echo "AZURE_SUBSCRIPTION_ID is required." >&2
  exit 1
fi

eval "$({
python - <<'PY'
import json
import os
import shlex
import sys

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from exc

with open(os.environ["NORMALIZED_JSON"], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

with open("uda/config/environment-mapping.yaml", "r", encoding="utf-8") as handle:
    mapping = yaml.safe_load(handle) or {}

environment = str(payload.get("environment") or "").strip().upper()
config_path = str(((mapping.get("config_files") or {}).get(environment) or "")).strip()
if not config_path:
    raise SystemExit(f"No environment config mapping found for environment: {environment}")

with open(config_path, "r", encoding="utf-8") as handle:
    environment_config = yaml.safe_load(handle) or {}

schema_creation = environment_config.get("schema_creation") or {}
sandbox_mode = str(payload.get("sandbox_mode") or "").strip().lower()
sandbox_schema_name = str(payload.get("sandbox_schema_name") or "").strip().lower()
schema_parts = [part for part in sandbox_schema_name.split("_") if part]
sandbox_container_suffix = "-".join(schema_parts[1:-1]) if len(schema_parts) > 2 else sandbox_schema_name.replace("_", "-")

values = {
    "sandbox_mode": sandbox_mode,
    "sandbox_schema_name": sandbox_schema_name,
    "sandbox_storage_account": str(schema_creation.get("sandbox_storage_account_name") or "").strip(),
    "sandbox_container": f"sandbox-{sandbox_container_suffix}" if sandbox_schema_name else "",
}

for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY
})"

if [ "$sandbox_mode" != "new" ]; then
  echo "Sandbox mode is not new; skipping container check/create."
  exit 0
fi

if [ -z "$sandbox_schema_name" ]; then
  echo "sandbox_schema_name is required to derive sandbox container." >&2
  exit 1
fi

if [ -z "$sandbox_storage_account" ]; then
  echo "sandbox_storage_account is missing from environment config." >&2
  exit 1
fi

echo "Checking ADLS container: ${sandbox_container}"
set +e
exists="$(az storage container exists \
  --account-name "$sandbox_storage_account" \
  --name "$sandbox_container" \
  --auth-mode login \
  --query exists -o tsv 2>/tmp/sandbox_container_exists.err)"
exists_rc=$?
set -e

if [ "$exists_rc" -eq 0 ]; then
  if [ "$exists" = "true" ]; then
    echo "ADLS container already exists: ${sandbox_container}"
    exit 0
  fi

  echo "Creating ADLS container via data-plane: ${sandbox_container}"
  az storage container create \
    --account-name "$sandbox_storage_account" \
    --name "$sandbox_container" \
    --auth-mode login \
    --output none

  echo "ADLS container created via data-plane: ${sandbox_container}"
  exit 0
fi

echo "Data-plane check failed for ${sandbox_storage_account}/${sandbox_container}; falling back to ARM container ensure."
cat /tmp/sandbox_container_exists.err >&2 || true

storage_resource_group="$(az storage account show --name "$sandbox_storage_account" --query resourceGroup -o tsv)"
if [ -z "$storage_resource_group" ]; then
  echo "Unable to resolve resource group for storage account $sandbox_storage_account." >&2
  exit 1
fi

az rest \
  --method put \
  --url "https://management.azure.com/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${storage_resource_group}/providers/Microsoft.Storage/storageAccounts/${sandbox_storage_account}/blobServices/default/containers/${sandbox_container}?api-version=2023-05-01" \
  --headers "Content-Type=application/json" \
  --body '{"properties":{}}' \
  --output none

echo "ADLS container ensured via ARM: ${sandbox_container}"