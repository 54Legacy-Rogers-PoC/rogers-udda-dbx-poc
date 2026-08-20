terraform {
  required_version = ">= 1.6.0"


backend "azurerm" {}

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.50"
    }
  }
}

provider "databricks" {
  host = var.databricks_host

  # Prefer PAT auth when available; otherwise fall back to Azure SP auth.
  token = var.databricks_token != "" ? var.databricks_token : null

  azure_client_id           = var.databricks_token == "" ? var.databricks_client_id : null
  azure_client_secret       = var.databricks_token == "" ? var.databricks_client_secret : null
  azure_tenant_id           = var.databricks_token == "" ? var.databricks_tenant_id : null
  azure_workspace_resource_id = var.databricks_workspace_resource_id != "" ? var.databricks_workspace_resource_id : null
}
