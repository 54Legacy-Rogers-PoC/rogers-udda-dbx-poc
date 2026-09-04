#!/usr/bin/env bash
set -euo pipefail

# Derive the Terraform state key from the normalized request payload.

if [ -z "${NORMALIZED_JSON:-}" ] || [ ! -f "$NORMALIZED_JSON" ]; then
  echo "NORMALIZED_JSON must point to an existing normalized request file." >&2
  exit 1
fi

key_parts="$(python -c "import json,re,os; p=json.load(open(os.environ['NORMALIZED_JSON'],'r',encoding='utf-8')); s=lambda v: re.sub(r'[^A-Za-z0-9._-]','-',str(v or '').strip()); print(f'{s((p.get(\"environment\") or \"\").upper())}/{s(p.get(\"request_id\"))}-{s(p.get(\"communitymart_schema_name\") or \"na\")}-{s(p.get(\"sandbox_schema_name\") or \"na\")}')")"

TFSTATE_KEY_EFFECTIVE="schema-creation/${key_parts}.tfstate"
echo "TF_BACKEND_KEY=$TFSTATE_KEY_EFFECTIVE" >> "$GITHUB_ENV"
echo "TFSTATE_KEY=$TFSTATE_KEY_EFFECTIVE" >> "$GITHUB_ENV"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "tfstate_key=$TFSTATE_KEY_EFFECTIVE" >> "$GITHUB_OUTPUT"
fi
echo "Using computed backend key: $TFSTATE_KEY_EFFECTIVE"