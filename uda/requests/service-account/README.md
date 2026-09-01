# DDD-DBX-01 Service Account Lifecycle Management

## Scope
This folder contains Request-as-Code YAML files for Databricks service account lifecycle operations.

## Paths
- Requests: `uda/requests/service-account/`
- Workflow: `.github/workflows/uda-dbx-service-account.yml`
- Parser: `uda/scripts/process_service_account_request.py`

## Supported Activities
- `create`
- `delete`
- `add_to_cluster`
- `remove_from_cluster`
- `change_ownership`

AD group to cluster access changes are handled in DDD-DBX-04 under `uda/requests/cluster-adgroup-add/` and `uda/requests/cluster-adgroup-remove/`.

## Terraform-Required Activities
- `add_to_cluster`
- `remove_from_cluster`

For metadata-only activities, the workflow validates and writes governance payload artifacts without Terraform apply.

## Cluster Permission Levels
Use `cluster_permission_level` for cluster activities.

Allowed values:
- `CAN_ATTACH_TO`
- `CAN_RESTART`
- `CAN_MANAGE`

## Required Request Fields
Typical fields used by this DDD include:
- `request_id`
- `platform` (`databricks`)
- `request_type` (`service_account`)
- `environment` (`Production`, `QA/Test`, `Development`)
- `activity_type`
- `service_account_name`
- `service_account_owner`
- `cluster_name` and `cluster_id` (for cluster activities)
- `cluster_permission_level` (for cluster activities)

## Samples
- `uda/requests/service-account/dev/RITMDEVSA0001.yaml`
- `uda/requests/service-account/dev/RITMDEVSA0003.yaml`

## Execution Behavior
- Plan runs for valid requests.
- Apply runs only for `workflow_dispatch` with `auto_apply=true`.
- Push-triggered runs are plan-only.
- On completion, workflow sends email to the configured distribution list when `NOTIFY_*` and `NOTIFY_DL_EMAIL` secrets are present.

## Notes
- `cluster_id` is required for Databricks cluster permission resources.
- Principal identity must exist/sync in Databricks before permission apply can succeed.
