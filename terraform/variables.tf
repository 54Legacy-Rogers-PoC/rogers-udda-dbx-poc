variable "request_id" {
  description = "Request identifier from Request-as-Code YAML (e.g., RITM123456)."
  type        = string

  validation {
    condition     = can(regex("^RITM[0-9]+$", var.request_id))
    error_message = "request_id must match pattern RITM<digits>."
  }
}

variable "environment" {
  description = "Target deployment environment."
  type        = string

  validation {
    condition     = contains(["DEV", "QA", "PRD"], upper(var.environment))
    error_message = "environment must be one of DEV, QA, PRD."
  }
}

variable "object_access_records" {
  description = "Normalized object access records generated from template parsing."
  type = list(object({
    record_id              = string
    activity               = string
    environment            = string
    access_for             = string
    principal_name         = string
    object_type            = string
    catalog                = string
    schema                 = string
    object_name            = string
    folder_path            = string
    privilege              = string
    justification          = string
    additional_information = string
    row_number             = number
  }))

  validation {
    condition = alltrue([
      for r in var.object_access_records :
      contains(["ADD", "REMOVE"], upper(r.activity))
    ])
    error_message = "Each record activity must be ADD or REMOVE."
  }

  validation {
    condition = alltrue([
      for r in var.object_access_records :
      contains(["ad_group", "service_account"], lower(r.access_for))
    ])
    error_message = "Each record access_for must be ad_group or service_account."
  }

  validation {
    condition = alltrue([
      for r in var.object_access_records :
      contains(["CATALOG", "SCHEMA", "VIEW", "FOLDER"], upper(r.object_type))
    ])
    error_message = "Each record object_type must be CATALOG, SCHEMA, VIEW, or FOLDER."
  }

  validation {
    condition = alltrue([
      for r in var.object_access_records :
      upper(r.environment) == upper(var.environment)
    ])
    error_message = "Each record environment must match variable environment."
  }

  validation {
    condition = alltrue([
      for r in var.object_access_records :
      trimspace(r.principal_name) != ""
    ])
    error_message = "principal_name cannot be empty."
  }
}

variable "databricks_host" {
  description = "Databricks workspace host URL."
  type        = string
  sensitive   = true
}

variable "databricks_client_id" {
  description = "Databricks/Azure AD client ID for provider authentication."
  type        = string
  sensitive   = true
}

variable "databricks_client_secret" {
  description = "Databricks/Azure AD client secret for provider authentication."
  type        = string
  sensitive   = true
}

variable "databricks_tenant_id" {
  description = "Azure tenant ID used by Databricks provider authentication."
  type        = string
  sensitive   = true
}
