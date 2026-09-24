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
  [[ "$p" == requests/schema-creation/dev/*.yml || "$p" == requests/schema-creation/dev/*.yaml ||
     "$p" == requests/schema-creation/qa/*.yml || "$p" == requests/schema-creation/qa/*.yaml ||
     "$p" == requests/schema-creation/prd/*.yml || "$p" == requests/schema-creation/prd/*.yaml ]] || return 0

  if [ -f "$p" ]; then
    REQUESTS+=("$p")
    return 0
  fi

  local dir="${p%/*}"
  local stem="${p%.*}"
  for candidate in "$stem.yml" "$stem.yaml"; do
    if [ -f "$candidate" ]; then
      REQUESTS+=("$candidate")
      return 0
    fi
  done

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
  # Push/PR runs process newly added requests only.
  if [ -n "${BASE_SHA_EVENT:-}" ] && [ -n "${HEAD_SHA_EVENT:-}" ]; then
    while IFS= read -r changed; do
      if git log --format=%H -n 1 "$BASE_SHA_EVENT" -- "$changed" | grep -q .; then
        echo "Skipping restored request path that already exists in Git history: $changed"
        continue
      fi
      add_request "$changed"
    done < <(git diff --name-only --diff-filter=A "$BASE_SHA_EVENT" "$HEAD_SHA_EVENT" -- requests/schema-creation/dev requests/schema-creation/qa requests/schema-creation/prd || true)
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

request_environment() {
  case "$1" in
    requests/schema-creation/dev/*) printf '%s|%s|%s\n' "dev" "DEV" "schema-creation-v2-dev" ;;
    requests/schema-creation/qa/*) printf '%s|%s|%s\n' "qa" "QA" "schema-creation-v2-qa" ;;
    requests/schema-creation/prd/*) printf '%s|%s|%s\n' "prd" "PRD" "schema-creation-v2" ;;
    *) echo "Unsupported schema request path: $1" >&2; return 1 ;;
  esac
}

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
  IFS='|' read -r deployment_environment environment_code tfstate_key_suffix < <(request_environment "$rf")
  matrix_json+="{\"request_file\":\"$escaped\",\"deployment_environment\":\"$deployment_environment\",\"environment_code\":\"$environment_code\",\"tfstate_key_suffix\":\"$tfstate_key_suffix\"}"
done
matrix_json+="]}"

echo "has_requests=true" >> "$GITHUB_OUTPUT"
echo "matrix=$matrix_json" >> "$GITHUB_OUTPUT"