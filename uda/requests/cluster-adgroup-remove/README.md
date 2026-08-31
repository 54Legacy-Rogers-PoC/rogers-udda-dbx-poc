# DDD-DBX-04 Cluster AD Group REMOVE

## Scope
This folder contains Request-as-Code YAML files for removing AD group access from Databricks clusters.

## Paths
- Requests: `uda/requests/cluster-adgroup-remove/`
- REMOVE workflow: `.github/workflows/uda-dbx-cluster-adgroup-remove.yml`
- ADD workflow: `.github/workflows/uda-dbx-cluster-adgroup-add.yml`
- Parser: `uda/scripts/process_cluster_adgroup_request.py`

## Supported Activity
- `REMOVE`

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
- `activity_type` (`REMOVE`)
- `requester_email` (used for completion notification)
- `ad_group_name`
- `cluster_name`
- `cluster_id`
- `cluster_permission_level`

## Samples
- `uda/requests/cluster-adgroup-remove/dev/RITMDEVAG0002.yaml`

For ADD sample requests, use `uda/requests/cluster-adgroup-add/README.md`.

## Execution Behavior
- Plan runs for valid requests.
- Apply runs only for `workflow_dispatch` with `auto_apply=true`.
- Workflows are manual dispatch and activity-guarded:
  - Use REMOVE workflow for `activity_type: REMOVE`
  - Use ADD workflow for `activity_type: ADD`

## State Isolation
This workflow uses the dedicated DDD-DBX-04 Terraform state key suffix to avoid cross-workflow state drift.
