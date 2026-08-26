#!/usr/bin/env bash
set -euo pipefail

is_excel() {
  case "${1,,}" in
    *.xlsx|*.xlsm|*.xls) return 0 ;;
    *) return 1 ;;
  esac
}

if [[ "${GITHUB_EVENT_NAME}" == "workflow_dispatch" ]]; then
  template_files_raw="${TEMPLATE_FILES_INPUT:-}"
  single_template="${TEMPLATE_FILE_INPUT:-}"

  if [[ -n "$template_files_raw" ]]; then
    mapfile -t requested_templates < <(printf '%s\n' "$template_files_raw" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed '/^$/d' | awk '!seen[$0]++')
  elif [[ -n "$single_template" ]]; then
    requested_templates=("$single_template")
  else
    echo "workflow_dispatch requires template_file or template_files input." >&2
    exit 1
  fi

  if [[ "${#requested_templates[@]}" -eq 0 ]]; then
    echo "No template files found for workflow_dispatch." >&2
    exit 1
  fi

  valid_templates=()
  for f in "${requested_templates[@]}"; do
    if [[ ! -f "$f" ]]; then
      echo "Requested template not found: $f" >&2
      exit 1
    fi
    if ! is_excel "$f"; then
      echo "Unsupported template extension (expected .xlsx/.xlsm/.xls): $f" >&2
      exit 1
    fi
    valid_templates+=("$f")
  done

  matrix_json="$(python -c "import json,sys; print(json.dumps({'include':[{'template_file':f} for f in sys.argv[1:] if f]}))" "${valid_templates[@]}")"
  echo "has_templates=true" >> "$GITHUB_OUTPUT"
  echo "matrix=$matrix_json" >> "$GITHUB_OUTPUT"
  exit 0
fi

base_sha="${BASE_SHA_EVENT:-}"
head_sha="${HEAD_SHA_EVENT:-}"

if [[ -z "$head_sha" ]]; then
  head_sha="$(git rev-parse HEAD)"
fi

if [[ -z "$base_sha" || "$base_sha" == "0000000000000000000000000000000000000000" ]]; then
  base_sha="$(git rev-parse HEAD~1)"
fi

mapfile -t changed_templates < <(git diff --name-only --diff-filter=A "$base_sha" "$head_sha" -- "uda/attachments/object-access/*")

existing_templates=()
for f in "${changed_templates[@]}"; do
  if [[ -f "$f" ]] && is_excel "$f"; then
    existing_templates+=("$f")
  fi
done

if [[ "${#existing_templates[@]}" -eq 0 ]]; then
  echo "has_templates=false" >> "$GITHUB_OUTPUT"
  echo 'matrix={"include":[]}' >> "$GITHUB_OUTPUT"
  exit 0
fi

matrix_json="$(python -c "import json,sys; print(json.dumps({'include':[{'template_file':f} for f in sys.argv[1:] if f]}))" "${existing_templates[@]}")"
echo "has_templates=true" >> "$GITHUB_OUTPUT"
echo "matrix=$matrix_json" >> "$GITHUB_OUTPUT"
