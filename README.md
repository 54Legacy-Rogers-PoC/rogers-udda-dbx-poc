# Rogers UDA Databricks Object Access POC

This repository implements DDD-DBX-02: Databricks Object Access Management for the Unified Data Access (UDA) framework.

Approved requests are converted into Request-as-Code artifacts and executed by GitHub Actions and Terraform against Databricks.

## Solution Overview

- Request metadata is stored in YAML under `uda/requests/object-access/`.
- Object-level access rows are stored in an attached template under `uda/attachments/object-access/`.
- A workflow validates request YAML and template structure.
- A parser script translates valid rows into `terraform.auto.tfvars.json`.
- Terraform validates, plans, and applies Databricks permissions.
- Execution summary and logs are published as workflow artifacts.

## Repository Structure

```
.github/
	workflows/
		uda-dbx-object-access.yml
terraform/
	providers.tf
	variables.tf
	main.tf
	outputs.tf
uda/
	attachments/
		object-access/
	requests/
		object-access/
	scripts/
	config/
	templates/
	tests/
	docs/
```

## Request-as-Code Example

Sample request: `uda/requests/object-access/dev/RITMDEV0001.yaml`

Key fields:

- `request_id`
- `platform` (`databricks`)
- `request_type` (`object_access`)
- `environment` (`Production`, `QA/Test`, `Development`)
- `activity_type` (`ADD` or `REMOVE`)
- `access_for` (`ad_group` or `service_account`)
- `ad_group_name` or `service_account_name`
- `template_file`

## Template Requirements

Template columns are documented in `uda/templates/ObjectAccessTemplate.columns.md`.

Supported object types:

- `catalog`
- `schema`
- `view`
- `folder`

Supported activities:

- `ADD`
- `REMOVE`

If the `Activity` column is blank on a row, request-level `activity_type` is used.

## Environment Mapping

Configured in `uda/config/environments.yaml`.

- `Production -> PRD`
- `QA/Test -> QA`
- `Development -> DEV`

## GitHub Actions Workflow

Workflow file: `.github/workflows/uda-dbx-object-access.yml`

`workflow_dispatch` inputs:

- `request_file`: request YAML path
- `auto_apply`: when true, runs terraform apply

Stages:

1. Repository checkout and artifact loading
2. Request validation
3. Template validation and parsing
4. Terraform init/validate/plan
5. Terraform apply (conditional + approval environment)
6. Notification and logging summary

## Azure Key Vault Secrets

Azure login in GitHub Actions uses these repository secrets:

- `AZURE_CLIENT_ID` (or `SPN-GHA-DBX-MANOJ-ID`)
- `AZURE_CLIENT_SECRET`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_TENANT_ID`
- `KEYVAULT_NAME`

The workflow reads these secrets at runtime:

- `DATABRICKS-HOST`
- `DATABRICKS-CLIENT-ID`
- `DATABRICKS-CLIENT-SECRET`
- `DATABRICKS-TENANT-ID`
- `DATABRICKS-WORKSPACE-RESOURCE-ID` (required)

The workflow also reads backend state configuration:

- `TFSTATE-RESOURCE-GROUP`
- `TFSTATE-STORAGE-ACCOUNT`
- `TFSTATE-CONTAINER-DBX-UDA`
- `TFSTATE-KEY`
- `TFSTATE-ACCESS-KEY` (optional fallback)

Backend auth behavior:

- If `TFSTATE-ACCESS-KEY` exists, Terraform backend uses `access_key` auth.
- If `TFSTATE-ACCESS-KEY` is absent, Terraform backend uses Azure AD auth (`use_azuread_auth=true`) and requires blob data permissions on the state container/account.

These values must be present in the key vault referenced by repository secret `KEYVAULT_NAME`.

## Local Execution

Run from repository root:

```powershell
./uda/scripts/run_local.ps1
```

Or run only parser:

```powershell
python uda/scripts/process_request.py --request-file uda/requests/object-access/dev/RITMDEV0001.yaml --config-file uda/config/environments.yaml --output-dir generated
```

## Testing

```powershell
pip install -r uda/scripts/requirements.txt
pytest uda/tests -q
```

## Governance Controls

- Pull requests are mandatory.
- Minimum one approval is required.
- Branch protection and merge controls are required.
- Direct commits to `main` are prohibited.

## Current Design Defaults

- Duplicate records in a template fail the request.
- Invalid rows fail the request.
- Processing is fail-fast to preserve traceability.
- `max_records` default is set to `1000` and can be changed in config.

## Open Decisions to Confirm

- Final max template row count.
- Partial-processing behavior for large requests.
- Mixed ADD/REMOVE behavior policy per template.
- Expanded Databricks object types beyond current baseline.
