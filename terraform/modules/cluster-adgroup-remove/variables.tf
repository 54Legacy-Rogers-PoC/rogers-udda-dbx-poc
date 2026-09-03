# The root module pre-splits AD group cluster REMOVE actions before invoking
# this module.
variable "remove_records" {
  description = "Cluster AD group remove records keyed by row id"
  type = map(object({
    row_id           = string
    activity         = string
    ad_group_name    = string
    cluster_name     = string
    cluster_id       = string
    permission_level = string
  }))
}