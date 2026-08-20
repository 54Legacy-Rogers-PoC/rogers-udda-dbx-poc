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
