# REMOVE requests are kept separate to mirror the dedicated remove workflow and
# avoid mixing activity types in one Terraform slice.
resource "databricks_permissions" "cluster_ad_group_remove" {
  for_each = var.remove_records

  cluster_id = each.value.cluster_id

  access_control {
    group_name       = each.value.ad_group_name
    permission_level = each.value.permission_level
  }
}