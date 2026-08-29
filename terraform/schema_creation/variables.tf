variable "request_id" {
  description = "Request identifier from Request-as-Code YAML (e.g., RITM123456)."
  type        = string

  validation {
    condition     = can(regex("^RITM[0-9]+$", var.request_id))
    error_message = "request_id must match pattern RITM<digits>."
  }
}

variable "environment" {
  description = "Target deployment environment for schema request."
  type        = string

  validation {
    condition     = contains(["DEV", "QA", "PRD"], upper(var.environment))
    error_message = "environment must be one of DEV, QA, PRD."
  }
}

variable "sandbox_mode" {
  description = "Sandbox action mode: new or existing."
  type        = string

  validation {
    condition     = contains(["new", "existing"], lower(var.sandbox_mode))
    error_message = "sandbox_mode must be either new or existing."
  }
}

variable "sandbox_schema_name" {
  description = "Sandbox schema name (required for new sandbox mode)."
  type        = string
  default     = ""
}

variable "sandbox_owner_name" {
  description = "UPN/email of sandbox owner."
  type        = string
}

variable "ad_group_name" {
  description = "AAD group name to provision/associate."
  type        = string
}

variable "ad_group_owner_name" {
  description = "UPN/email of AAD group owner."
  type        = string
  default     = ""
}

variable "create_communitymart_schema" {
  description = "Whether to create a community mart schema."
  type        = bool
}

variable "communitymart_schema_name" {
  description = "Community mart schema name when enabled."
  type        = string
  default     = ""
}

variable "communitymart_owner_name" {
  description = "UPN/email of community mart schema owner when enabled."
  type        = string
  default     = ""
}

variable "justification" {
  description = "Business justification for the request."
  type        = string
  default     = ""
}

variable "additional_information" {
  description = "Additional metadata or approvals."
  type        = string
  default     = ""
}

variable "assignment_group" {
  description = "Owning assignment group."
  type        = string
}

variable "epdg_ticket_url" {
  description = "Governance ticket URL when applicable."
  type        = string
  default     = ""
}

variable "governance_approval_required" {
  description = "Whether governance approval is required."
  type        = bool
}

variable "ad_approval_required" {
  description = "Whether AD approval is required based on owner separation."
  type        = bool
}

variable "databricks_host" {
  description = "Databricks workspace host URL."
  type        = string
  sensitive   = true
}

variable "databricks_client_id" {
  description = "Databricks/Azure AD client ID for provider authentication."
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
}

variable "databricks_client_secret" {
  description = "Databricks/Azure AD client secret for provider authentication."
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
}

variable "databricks_tenant_id" {
  description = "Azure tenant ID used by Databricks provider authentication."
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
}