# The root module pre-splits service-account cluster actions into add/remove
# maps before calling this module.
variable "add_records" {
  description = "Service-account cluster add records keyed by row id"
  type = map(object({
    row_id               = string
    activity             = string
    service_account_name = string
    cluster_name         = string
    cluster_id           = string
    permission_level     = string
  }))
}

variable "remove_records" {
  description = "Service-account cluster remove records keyed by row id"
  type = map(object({
    row_id               = string
    activity             = string
    service_account_name = string
    cluster_name         = string
    cluster_id           = string
    permission_level     = string
  }))
}