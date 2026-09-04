# Rogers UDA Databricks Access POC

This repository implements Request-as-Code workflows for Databricks access operations in UDA.

## DDD Documentation

DDD-specific documentation is now maintained in each request folder:

- DDD-DBX-01 Service Account Lifecycle: `requests/service-account/README.md`
- DDD-DBX-02 Object Access Management: `requests/object-access/README.md`
- DDD-DBX-04 Cluster AD Group ADD: `requests/cluster-adgroup-add/README.md`
- DDD-DBX-04 Cluster AD Group REMOVE: `requests/cluster-adgroup-remove/README.md`

## Repository Structure

```
# High-level repository layout
.github/
  workflows/
    send-dl-notification/
    setup-dbxtf-env/
    uda-dbx-object-access.yml
    uda-dbx-service-account.yml
    uda-dbx-cluster-adgroup-add.yml
    uda-dbx-cluster-adgroup-remove.yml
terraform/
  environments/
    dev/
      main.tf
      versions.tf
      variables.tf
      outputs.tf
  modules/
    object-access/
    cluster-adgroup-add/
    cluster-adgroup-remove/
    service_account/
uda/
  attachments/
  config/
  docs/
  scripts/
  templates/
  tests/
requests/
  object-access/
  service-account/
  cluster-adgroup-add/
  cluster-adgroup-remove/
  schema-creation/
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

Key Vault must provide Databricks, Terraform backend, and completion-notification secrets consumed by the workflows.

Notification secret names in Key Vault:

- `NOTIFY-SMTP-SERVER`
- `NOTIFY-SMTP-PORT`
- `NOTIFY-SMTP-USERNAME`
- `NOTIFY-SMTP-PASSWORD`
- `NOTIFY-FROM-EMAIL`
- `NOTIFY-DL-EMAIL`

Example to add the SMTP server secret to Key Vault:

```powershell
az keyvault secret set --vault-name <key-vault-name> --name NOTIFY-SMTP-SERVER --value <smtp-server-hostname>
```

Key Vault also provides Databricks and Terraform backend secrets consumed by `.github/workflows/setup-dbxtf-env/action.yml`.

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
