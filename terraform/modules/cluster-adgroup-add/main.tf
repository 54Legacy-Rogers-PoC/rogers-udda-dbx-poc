# ADD requests grant the requested cluster permission level to the target AD
# group.
resource "databricks_permissions" "cluster_ad_group_add" {
  for_each = var.add_records

  cluster_id = each.value.cluster_id

  access_control {
    group_name       = each.value.ad_group_name
    permission_level = each.value.permission_level
  }
}