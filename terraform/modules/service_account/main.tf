# ADD requests grant the requested cluster permission directly to the service
# principal.
resource "databricks_permissions" "service_account_cluster_add" {
  for_each = var.add_records

  cluster_id = each.value.cluster_id

  access_control {
    service_principal_name = each.value.service_account_name
    permission_level       = each.value.permission_level
  }
}

# REMOVE requests are modeled as their own resource set so add/remove runs stay
# isolated in Terraform state and workflow summaries.
resource "databricks_permissions" "service_account_cluster_remove" {
  for_each = var.remove_records

  cluster_id = each.value.cluster_id

  access_control {
    service_principal_name = each.value.service_account_name
    permission_level       = each.value.permission_level
  }
}