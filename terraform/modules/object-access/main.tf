# Catalog grants are keyed by template row id so each requested change has a
# stable Terraform address.
resource "databricks_grant" "catalog_access" {
  for_each = var.catalog_records

  catalog    = each.value.catalog_name
  principal  = each.value.principal_name
  privileges = each.value.activity == "ADD" ? each.value.privileges : []
}

# Schema grants follow the same pattern but use catalog.schema addressing.
resource "databricks_grant" "schema_access" {
  for_each = var.schema_records

  schema     = "${each.value.catalog_name}.${each.value.schema_name}"
  principal  = each.value.principal_name
  privileges = each.value.activity == "ADD" ? each.value.privileges : []
}

# Views are granted through the Databricks table API using the fully qualified
# catalog.schema.object path.
resource "databricks_grant" "view_access" {
  for_each = var.view_records

  table      = "${each.value.catalog_name}.${each.value.schema_name}.${each.value.object_name}"
  principal  = each.value.principal_name
  privileges = each.value.activity == "ADD" ? each.value.privileges : []
}

# Folder permissions can target either AD groups or service accounts, so the
# access_control block sets only the relevant principal field.
resource "databricks_permissions" "folder_access" {
  for_each = var.folder_records

  directory_path = each.value.folder_path

  access_control {
    group_name             = each.value.principal_type == "ad_group" ? each.value.principal_name : null
    service_principal_name = each.value.principal_type == "service_account" ? each.value.principal_name : null
    permission_level       = each.value.activity == "ADD" ? each.value.privileges[0] : "CAN_READ"
  }
}