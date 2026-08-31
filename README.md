# Rogers UDA Databricks Access POC

This repository implements Request-as-Code workflows for Databricks access operations in UDA.

## DDD Documentation

DDD-specific documentation is now maintained in each request folder:

- DDD-DBX-01 Service Account Lifecycle: `uda/requests/service-account/README.md`
- DDD-DBX-02 Object Access Management: `uda/requests/object-access/README.md`
- DDD-DBX-04 Cluster AD Group ADD: `uda/requests/cluster-adgroup-add/README.md`
- DDD-DBX-04 Cluster AD Group REMOVE: `uda/requests/cluster-adgroup-remove/README.md`

## Repository Structure

```
# High-level repository layout
.github/
  actions/
    setup-dbxtf-env/
  workflows/
    uda-dbx-object-access.yml
    uda-dbx-service-account.yml
    uda-dbx-cluster-adgroup-add.yml
    uda-dbx-cluster-adgroup-remove.yml
terraform/
uda/
  attachments/
  config/
  docs/
  requests/
    object-access/
    service-account/
    cluster-adgroup-add/
    cluster-adgroup-remove/
  scripts/
  templates/
  tests/
```

## Workflow Behavior

- Workflows validate request artifacts and generate `generated/terraform.auto.tfvars.json`.
- Terraform plan runs for valid requests.
- Terraform apply runs only for `workflow_dispatch` with `auto_apply=true`.
- Push-triggered runs are plan-only.

## Shared Secrets and Backend

GitHub Actions expects repository secrets for Azure login:

- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_TENANT_ID`
- `KEYVAULT_NAME`

GitHub Actions requester-email notification secrets:

- `NOTIFY_SMTP_SERVER`
- `NOTIFY_SMTP_PORT`
- `NOTIFY_SMTP_USERNAME`
- `NOTIFY_SMTP_PASSWORD`
- `NOTIFY_FROM_EMAIL`

Key Vault must provide Databricks and Terraform backend secrets consumed by `.github/actions/setup-dbxtf-env/action.yml`.

## Local Execution

```powershell
# Run the local helper script from repository root
./uda/scripts/run_local.ps1
```

## Testing

```powershell
# Install parser/test dependencies, then run all tests
pip install -r uda/scripts/requirements.txt
pytest uda/tests -q
```

## Governance Controls

- Pull requests are mandatory.
- Minimum one approval is required.
- Branch protection and merge controls are required.
- Direct commits to `main` are prohibited.
