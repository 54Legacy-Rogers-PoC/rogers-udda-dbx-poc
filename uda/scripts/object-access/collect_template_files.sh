#!/usr/bin/env bash
set -euo pipefail

is_excel() {
  case "${1,,}" in
    *.xlsx|*.xlsm|*.xls) return 0 ;;
    *) return 1 ;;
  esac
}

is_request_yaml() {
  case "${1,,}" in
    requests/object-access/*/*.yml|requests/object-access/*/*.yaml) return 0 ;;
    *) return 1 ;;
  esac
}

extract_template_from_request() {
  local request_file="$1"
  python - "$request_file" <<'PY'
import re
import sys

path = sys.argv[1]
template = ""
with open(path, "r", encoding="utf-8") as f:
    for raw in f:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^template_file\s*:\s*(.+)$", line)
        if m:
            template = m.group(1).strip().strip('"').strip("'")
            break
print(template)
PY
}

resolve_template_path() {
  local request_file="$1"
  local template_value="$2"

  if [[ -z "$template_value" ]]; then
    echo "Request missing template_file: $request_file" >&2
    return 1
  fi

  if [[ -f "$template_value" ]]; then
    printf '%s' "$template_value"
    return 0
  fi

  local request_dir
  request_dir="$(dirname "$request_file")"
  if [[ -f "$request_dir/$template_value" ]]; then
    printf '%s' "$request_dir/$template_value"
    return 0
  fi

  if [[ -f "uda/attachments/object-access/$template_value" ]]; then
    printf '%s' "uda/attachments/object-access/$template_value"
    return 0
  fi

  echo "Unable to resolve template_file '$template_value' from request $request_file" >&2
  return 1
}

if [[ "${GITHUB_EVENT_NAME}" == "workflow_dispatch" ]]; then
  request_files_raw="${REQUEST_FILES_INPUT:-}"
  single_request="${REQUEST_FILE_INPUT:-}"

  if [[ -n "$request_files_raw" ]]; then
    mapfile -t requested_requests < <(printf '%s\n' "$request_files_raw" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed '/^$/d' | awk '!seen[$0]++')
  elif [[ -n "$single_request" ]]; then
    requested_requests=("$single_request")
  else
    echo "workflow_dispatch requires request_file or request_files input." >&2
    exit 1
  fi

  if [[ "${#requested_requests[@]}" -eq 0 ]]; then
    echo "No request files found for workflow_dispatch." >&2
    exit 1
  fi

  valid_templates=()
  for r in "${requested_requests[@]}"; do
    if [[ ! -f "$r" ]]; then
      echo "Requested request file not found: $r" >&2
      exit 1
    fi
    if ! is_request_yaml "$r"; then
      echo "Unsupported request path (expected requests/object-access/<env>/*.yml|*.yaml): $r" >&2
      exit 1
    fi

    template_value="$(extract_template_from_request "$r")"
    resolved_template="$(resolve_template_path "$r" "$template_value")"
    if ! is_excel "$resolved_template"; then
      echo "Unsupported template extension (expected .xlsx/.xlsm/.xls): $resolved_template" >&2
      exit 1
    fi
    valid_templates+=("$resolved_template")
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

mapfile -t changed_items < <(git diff --name-only --diff-filter=A "$base_sha" "$head_sha" -- "uda/attachments/object-access/*" "requests/object-access/*/*")

existing_templates=()
for f in "${changed_items[@]}"; do
  if [[ -f "$f" ]] && is_excel "$f"; then
    existing_templates+=("$f")
    continue
  fi

  if [[ -f "$f" ]] && is_request_yaml "$f"; then
    template_value="$(extract_template_from_request "$f")"
    resolved_template="$(resolve_template_path "$f" "$template_value")"
    if is_excel "$resolved_template"; then
      existing_templates+=("$resolved_template")
    fi
  fi
done

if [[ "${#existing_templates[@]}" -gt 0 ]]; then
  mapfile -t existing_templates < <(printf '%s\n' "${existing_templates[@]}" | awk '!seen[$0]++')
fi

if [[ "${#existing_templates[@]}" -eq 0 ]]; then
  echo "has_templates=false" >> "$GITHUB_OUTPUT"
  echo 'matrix={"include":[]}' >> "$GITHUB_OUTPUT"
  exit 0
fi

matrix_json="$(python -c "import json,sys; print(json.dumps({'include':[{'template_file':f} for f in sys.argv[1:] if f]}))" "${existing_templates[@]}")"
echo "has_templates=true" >> "$GITHUB_OUTPUT"
echo "matrix=$matrix_json" >> "$GITHUB_OUTPUT"
