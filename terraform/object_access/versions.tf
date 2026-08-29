terraform {
  required_version = ">= 1.6.0"

  backend "azurerm" {}

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.51"
    }
  }
}
