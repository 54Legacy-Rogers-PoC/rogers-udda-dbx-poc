#!/usr/bin/env bash
set -euo pipefail

# Collect request files from workflow inputs or from newly added request YAML files in a push/PR.

normalize_path() {
  local p="$1"
  p="${p#./}"
  printf '%s' "$p"
}

add_request() {
  local p
  p="$(normalize_path "$1")"
  [ -z "$p" ] && return 0
  [[ "$p" == requests/schema-creation/*/*.yml || "$p" == requests/schema-creation/*/*.yaml ]] || return 0
  REQUESTS+=("$p")
}

REQUESTS=()

if [ "${GITHUB_EVENT_NAME}" = "workflow_dispatch" ]; then
  # Manual runs accept either one file or a comma/newline separated list.
  add_request "${REQUEST_FILE_INPUT:-}"

  if [ -n "${REQUEST_FILES_INPUT:-}" ]; then
    while IFS= read -r raw; do
      raw="${raw//,/ }"
      for candidate in $raw; do
        add_request "$candidate"
      done
    done <<< "${REQUEST_FILES_INPUT}"
  fi
else
  # Push/PR runs only process files that were newly added in the diff.
  if [ -n "${BASE_SHA_EVENT:-}" ] && [ -n "${HEAD_SHA_EVENT:-}" ]; then
    while IFS= read -r changed; do
      add_request "$changed"
    done < <(git diff --name-only --diff-filter=A "$BASE_SHA_EVENT" "$HEAD_SHA_EVENT" || true)
  fi
fi

if [ "${#REQUESTS[@]}" -eq 0 ]; then
  echo "has_requests=false" >> "$GITHUB_OUTPUT"
  echo 'matrix={"include":[]}' >> "$GITHUB_OUTPUT"
  echo "No newly added schema request files found."
  exit 0
fi

declare -A seen=()
DEDUPED=()
for rf in "${REQUESTS[@]}"; do
  if [ -z "${seen[$rf]:-}" ]; then
    seen[$rf]=1
    DEDUPED+=("$rf")
  fi
done

for rf in "${DEDUPED[@]}"; do
  if [ ! -f "$rf" ]; then
    echo "Request file not found: $rf" >&2
    exit 1
  fi
done

# Emit a compact matrix payload so the workflow stays declarative.
matrix_json="{\"include\":["
first=true
for rf in "${DEDUPED[@]}"; do
  if [ "$first" = true ]; then
    first=false
  else
    matrix_json+="," 
  fi
  escaped="${rf//\"/\\\"}"
  matrix_json+="{\"request_file\":\"$escaped\"}"
done
matrix_json+="]}"

echo "has_requests=true" >> "$GITHUB_OUTPUT"
echo "matrix=$matrix_json" >> "$GITHUB_OUTPUT"