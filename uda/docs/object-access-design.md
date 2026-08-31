# Databricks Object Access Management

## Purpose
This project implements Databricks Object Access Management for UDA using a Request-as-Code model.
Approved ESMT requests are represented as YAML plus an attached object access template and executed through GitHub Actions and Terraform.

## Supported Activities
- Add object access
- Remove object access
- AD group access
- Service account access

Policy: ADD and REMOVE must be submitted in separate requests.

## Supported Object Types
- Unity Catalog catalogs
- Unity Catalog schemas
- Views
- Folders

## Execution Model
1. Cloud administrator commits a request YAML under `uda/requests/object-access/`.
2. Cloud administrator commits the attached template under `uda/attachments/object-access/`.
3. GitHub Actions validates and parses records.
4. Parser emits `generated/terraform.auto.tfvars.json`.
5. Terraform validates, plans, and applies through Databricks provider.
6. Workflow publishes execution summary and logs.

## Security
- Databricks provider credentials are read from Azure Key Vault at runtime.
- No secrets are stored in source-controlled files.

## Governance
- Pull requests are mandatory before merge to `main`.
- Branch protection and at least one reviewer approval are required.
- Direct commits to `main` are prohibited.

## Open Decisions
- Maximum supported template row count per request.
- Final behavior for partial failures in bulk requests.
- Final list of Databricks object types in scope.
