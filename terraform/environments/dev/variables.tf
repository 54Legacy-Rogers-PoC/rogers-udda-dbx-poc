# Shared request metadata is surfaced as outputs for workflow summaries and
# downstream execution tracking.
variable "request_id" {
  description = "Request ID from the Request-as-Code YAML"
  type        = string
}

variable "environment" {
  description = "Target environment code (DEV, QA, PRD)"
  type        = string
}

variable "object_access_records" {
  description = "Object-level access records parsed from the Excel template"
  type = list(object({
    row_id         = string
    activity       = string
    object_type    = string
    principal_type = string
    principal_name = string
    catalog_name   = optional(string)
    schema_name    = optional(string)
    object_name    = optional(string)
    folder_path    = optional(string)
    privileges     = list(string)
    justification  = string
  }))
}

# DDD-DBX-01 sends cluster actions separately from object access so the root
# module can dispatch them to the matching child module.
variable "service_account_cluster_access_records" {
  description = "Service-account cluster access actions parsed from the request artifact"
  type = list(object({
    row_id                = string
    activity              = string
    service_account_name  = string
    cluster_name          = string
    cluster_id            = string
    permission_level      = string
  }))
  default = []
}

# DDD-DBX-04 uses the same pattern as service-account cluster access but targets
# AD groups instead of service principals.
variable "cluster_ad_group_access_records" {
  description = "Cluster AD group access actions parsed from the request artifact"
  type = list(object({
    row_id           = string
    activity         = string
    ad_group_name    = string
    cluster_name     = string
    cluster_id       = string
    permission_level = string
  }))
  default = []
}

# Authentication inputs are injected at runtime from Azure Key Vault.
variable "databricks_host" {
  description = "Databricks workspace host"
  type        = string
  sensitive   = true
  default     = ""
}

variable "databricks_client_id" {
  description = "Databricks service principal client ID"
  type        = string
  sensitive   = true
  default     = ""
}

variable "databricks_client_secret" {
  description = "Databricks service principal client secret"
  type        = string
  sensitive   = true
  default     = ""
}

variable "databricks_tenant_id" {
  description = "Azure tenant ID"
  type        = string
  sensitive   = true
  default     = ""
}

variable "databricks_workspace_resource_id" {
  description = "Azure Databricks workspace resource ID (optional for Azure SP auth)"
  type        = string
  default     = ""
}
