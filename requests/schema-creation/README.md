# Schema request promotion

Add schema requests to the directory matching the target environment:

- `dev`: `environment: Development`
- `qa`: `environment: QA/Test`
- `prd`: `environment: Production`

Each environment uses its own shared Terraform state and GitHub Environment. Push and pull-request runs process newly added request files only; modifications and deletions are ignored. Promote an approved request by adding the corresponding environment-specific request file to the next directory.

| Request directory | GitHub Environment | Shared state suffix |
| --- | --- | --- |
| `dev` | `schema-creation-dev` | `schema-creation-v2-dev` |
| `qa` | `schema-creation-qa` | `schema-creation-v2-qa` |
| `prd` | `schema-creation-prd` | `schema-creation-v2` |

Pull requests use the matching `schema-creation-<environment>-plan` GitHub Environment. Configure the Azure login secrets in each GitHub Environment before promoting requests. The workflow reads the Key Vault name and Key Vault secret names from the matching file under `uda/config/environments`.

The environment files contain identifiers only. Store Databricks credentials and Terraform backend values in Azure Key Vault, never in repository configuration.