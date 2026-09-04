# Each input map is already normalized and filtered by the root module.
variable "catalog_records" {
  description = "Normalized catalog-level access records keyed by row id"
  type = map(object({
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

variable "schema_records" {
  description = "Normalized schema-level access records keyed by row id"
  type = map(object({
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

variable "view_records" {
  description = "Normalized view-level access records keyed by row id"
  type = map(object({
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

variable "folder_records" {
  description = "Normalized folder-level access records keyed by row id"
  type = map(object({
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