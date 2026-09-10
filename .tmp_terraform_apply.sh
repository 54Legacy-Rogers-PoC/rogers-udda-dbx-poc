set -euo pipefail

REMOVE_PHASE_SKIPPED="false"
if [ "$REQUEST_ACTIVITY" = "MIXED" ] && [ -f "$OUTPUT_DIR/remove-phase-skipped.flag" ]; then
  REMOVE_PHASE_SKIPPED="true"
  echo "REMOVE phase was skipped during planning for MIXED template."
fi

if [ "$REQUEST_ACTIVITY" = "MIXED" ] && [ "$REMOVE_PHASE_SKIPPED" = "true" ]; then
  echo "Skipping REMOVE apply phase and proceeding directly to ADD phase."
else
  if [ "$REQUEST_ACTIVITY" != "ADD" ]; then
    declare -a TARGETS=()
    declare -A TARGET_IMPORT_ID=()

    while IFS=$'\t' read -r target import_id; do
      if [ -z "$target" ] || [ -z "$import_id" ]; then
        continue
      fi
      TARGETS+=("$target")
      TARGET_IMPORT_ID["$target"]="$import_id"
    done < <(jq -r '.object_access_records[]
      | select((.activity | ascii_upcase) == "REMOVE")
      | if ((.object_type | ascii_upcase) == "CATALOG") then
          [
            "module.object_access.databricks_grant.catalog_add[\"\((.environment | ascii_upcase))|\((.access_for | ascii_downcase))|\((.principal_name | ascii_downcase))|CATALOG|\(.catalog)|\((.privilege | ascii_upcase))\"]",
            "catalog/\(.catalog)/\(.principal_name)"
          ]
        elif ((.object_type | ascii_upcase) == "SCHEMA") then
          [
            "module.object_access.databricks_grant.schema_add[\"\((.environment | ascii_upcase))|\((.access_for | ascii_downcase))|\((.principal_name | ascii_downcase))|SCHEMA|\(.catalog)|\(.schema)|\((.privilege | ascii_upcase))\"]",
            "schema/\(.catalog).\(.schema)/\(.principal_name)"
          ]
        elif ((.object_type | ascii_upcase) == "VIEW") then
          [
            "module.object_access.databricks_grant.view_add[\"\((.environment | ascii_upcase))|\((.access_for | ascii_downcase))|\((.principal_name | ascii_downcase))|VIEW|\(.catalog)|\(.schema)|\(.object_name)|\((.privilege | ascii_upcase))\"]",
            "table/\(.catalog).\(.schema).\(.object_name)/\(.principal_name)"
          ]
        else empty end
      | @tsv' "$TFVARS_JSON")

    if [ "${#TARGETS[@]}" -eq 0 ]; then
      echo "No revoke targets found for REMOVE/REVOKE template." >&2
      exit 1
    fi

    mapfile -t STATE_ADDRS < <(terraform -chdir=terraform state list || true)

    target_args=()
    missing_targets=()
    for t in "${TARGETS[@]}"; do
      if ! printf '%s\n' "${STATE_ADDRS[@]}" | grep -Fx -- "$t" >/dev/null; then
        import_id="${TARGET_IMPORT_ID[$t]:-}"
        if [ -n "$import_id" ]; then
          echo "Target not in state. Attempting import for revoke: $import_id"
          if terraform -chdir=terraform import -var-file="../$TFVARS_IMPORT_JSON" "$t" "$import_id"; then
            echo "Imported missing target into state: $t"
            target_args+=("-target=$t")
            continue
          else
            echo "Import failed for target: $t"
          fi
        fi
        missing_targets+=("$t")
        continue
      fi
      target_args+=("-target=$t")
    done

    if [ "${#missing_targets[@]}" -gt 0 ]; then
      echo "Skipping revoke targets not found in backend state ($TF_BACKEND_KEY):"
      printf ' - %s\n' "${missing_targets[@]}"
      echo "Continuing with targets that are present in state."
    fi

    if [ "${#target_args[@]}" -eq 0 ]; then
      if [ "$REQUEST_ACTIVITY" = "REMOVE" ]; then
        echo "REMOVE request failed: none of the requested revoke targets were present in state and import did not succeed." >&2
        exit 1
      fi

      echo "No REMOVE targets available for MIXED template. Skipping REMOVE phase and continuing to ADD phase."
    else
      terraform -chdir=terraform plan \
        -lock-timeout=10m \
        -destroy \
        -var-file="../$TFVARS_JSON" \
        "${target_args[@]}" \
        -out="../$TFPLAN_BIN"
      terraform -chdir=terraform apply -lock-timeout=10m -auto-approve "../$TFPLAN_BIN"

      if [ "$REQUEST_ACTIVITY" != "MIXED" ]; then
        exit 0
      fi
    fi
  else
    terraform -chdir=terraform plan \
      -lock-timeout=10m \
      -var-file="../$TFVARS_JSON" \
      -out="../$TFPLAN_BIN"
    terraform -chdir=terraform apply -lock-timeout=10m -auto-approve "../$TFPLAN_BIN"
    exit 0
  fi
fi

if [ "$REQUEST_ACTIVITY" = "MIXED" ]; then
  echo "Starting ADD phase for MIXED activity template..."
  terraform -chdir=terraform plan \
    -lock-timeout=10m \
    -var-file="../$TFVARS_JSON" \
    -out="../$TFPLAN_MIXED_ADD_BIN"
  terraform -chdir=terraform apply -lock-timeout=10m -auto-approve "../$TFPLAN_MIXED_ADD_BIN"
fi
