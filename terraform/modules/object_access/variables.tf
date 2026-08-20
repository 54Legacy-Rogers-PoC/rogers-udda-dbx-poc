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
}
