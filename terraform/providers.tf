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
  host                = var.databricks_host
  azure_client_id     = var.databricks_client_id
  azure_client_secret = var.databricks_client_secret
  azure_tenant_id     = var.databricks_tenant_id
}
