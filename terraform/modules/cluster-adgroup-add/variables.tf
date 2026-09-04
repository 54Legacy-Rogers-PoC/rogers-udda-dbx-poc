# The root module pre-splits AD group cluster ADD actions before invoking this
# module.
variable "add_records" {
  description = "Cluster AD group add records keyed by row id"
  type = map(object({
    row_id           = string
    activity         = string
    ad_group_name    = string
    cluster_name     = string
    cluster_id       = string
    permission_level = string
  }))
}