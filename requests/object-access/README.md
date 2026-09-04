# DDD-DBX-02 Object Access Management

## Scope
This folder contains Request-as-Code YAML files for Databricks object-level access management.

## Paths
- Requests: `requests/object-access/`
- Attachments: `uda/attachments/object-access/`
- Template columns: `uda/templates/ObjectAccessTemplate.columns.md`
- Workflow: `.github/workflows/uda-dbx-object-access.yml`
- Parser: `uda/scripts/process_request.py`

## Supported Activities
- `ADD`
- `REMOVE`

Use separate requests for ADD and REMOVE. A single request cannot mix both activities.

## Supported Object Types
- `catalog`
- `schema`
- `view`
- `folder`

## Required Request Fields
- `request_id`
- `platform` (`databricks`)
- `request_type` (`object_access`)
- `environment` (`Production`, `QA/Test`, `Development`)
- `activity_type` (`ADD` or `REMOVE`)
- `access_for` (`ad_group` or `service_account`)
- `ad_group_name` or `service_account_name`
- `template_file`

If a template row has blank `Activity`, request-level `activity_type` is used.

## Samples
- `requests/object-access/dev/RITMDEV0001.yaml`
- `requests/object-access/dev/RITMDEV0002.yaml`

## Execution Behavior
- Plan runs for valid requests.
- Apply runs only for `workflow_dispatch` with `auto_apply=true`.
- Push-triggered runs are plan-only.
- On completion, workflow sends email to the configured distribution list when the Key Vault notification secrets are present.

## Defaults
- Duplicate template records fail the request.
- Invalid rows fail the request.
- Processing is fail-fast.
- `max_records` default is `1000` (configurable in `uda/config/environments.yaml`).
