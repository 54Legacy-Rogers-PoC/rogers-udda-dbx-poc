terraform {
  required_version = ">= 1.6.0"

  # Backend settings are injected at workflow runtime so state can be isolated
  # per DDD without hardcoding storage details in the repo.
  backend "azurerm" {}

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.50"
    }
  }
}

# The workflows populate these variables from Azure Key Vault before running any
# Terraform commands.
provider "databricks" {
  host                      = var.databricks_host
  azure_client_id           = var.databricks_client_id
  azure_client_secret       = var.databricks_client_secret
  azure_tenant_id           = var.databricks_tenant_id
  azure_workspace_resource_id = var.databricks_workspace_resource_id != "" ? var.databricks_workspace_resource_id : null
}
