# DDD-DBX-04 Cluster AD Group ADD

## Scope
This folder contains Request-as-Code YAML files for adding AD group access to Databricks clusters.

## Paths
- Requests: `requests/cluster-adgroup-add/`
- ADD workflow: `.github/workflows/uda-dbx-cluster-adgroup-add.yml`
- REMOVE workflow: `.github/workflows/uda-dbx-cluster-adgroup-remove.yml`
- Parser: `uda/scripts/cluster-adgroup/process_cluster_adgroup_request.py`

## Supported Activity
- `ADD`

## Cluster Permission Levels
Use `cluster_permission_level` in each request.

Allowed values:
- `CAN_ATTACH_TO`
- `CAN_RESTART`
- `CAN_MANAGE`

## Required Request Fields
- `request_id`
- `platform` (`databricks`)
- `request_type` (`cluster_adgroup`)
- `environment` (`Production`, `QA/Test`, `Development`)
- `activity_type` (`ADD`)
- `ad_group_name`
- `cluster_name`
- `cluster_id`
- `cluster_permission_level`

## Samples
- `requests/cluster-adgroup-add/dev/RITMDEVAG0001.yaml`

For REMOVE sample requests, use `requests/cluster-adgroup-remove/README.md`.

## Execution Behavior
- Plan runs for valid requests.
- Apply runs only for `workflow_dispatch` with `auto_apply=true`.
- Workflows are manual dispatch and activity-guarded:
  - Use ADD workflow for `activity_type: ADD`
  - Use REMOVE workflow for `activity_type: REMOVE`
- On completion, workflow sends email to the configured distribution list when the Key Vault notification secrets are present.

## State Isolation
This workflow uses a dedicated Terraform state key suffix to avoid cross-workflow state drift with other DDD workflows.
