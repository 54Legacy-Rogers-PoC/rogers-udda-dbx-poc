variable "request_id" {
  description = "Request identifier from Request-as-Code YAML (e.g., RITM123456)."
  type        = string
}

variable "environment" {
  description = "Target deployment environment for schema request."
  type        = string
}

variable "sandbox_mode" {
  description = "Sandbox action mode: new or existing."
  type        = string
}

variable "sandbox_schema_name" {
  description = "Sandbox schema name."
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
  description = "Business justification for request."
  type        = string
  default     = ""
}

variable "additional_information" {
  description = "Additional details from requester."
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