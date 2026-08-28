# DDD-DBX-04 Cluster AD Group Association Management

## Scope
This folder contains Request-as-Code YAML files for Databricks cluster AD group access changes.

## Paths
- Requests: `uda/requests/cluster-adgroup/`
- Workflow: `.github/workflows/uda-dbx-cluster-adgroup.yml`
- Parser: `uda/scripts/process_cluster_adgroup_request.py`

## Supported Activities
- `ADD`
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
- `activity_type` (`ADD` or `REMOVE`)
- `ad_group_name`
- `cluster_name`
- `cluster_id`
- `cluster_permission_level`

## Samples
- `uda/requests/cluster-adgroup/dev/RITMDEVAG0001.yaml`
- `uda/requests/cluster-adgroup/dev/RITMDEVAG0002.yaml`

## Execution Behavior
- Plan runs for valid requests.
- Apply runs only for `workflow_dispatch` with `auto_apply=true`.
- Push-triggered runs are plan-only.

## State Isolation
This workflow uses a dedicated Terraform state key suffix to avoid cross-workflow state drift with other DDD workflows.
