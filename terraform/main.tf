locals {
  normalized_records = [
    for r in var.object_access_records : merge(r, {
      activity    = upper(r.activity)
      object_type = lower(r.object_type)
    })
  ]

  catalog_records = {
    for r in local.normalized_records : r.row_id => r
    if r.object_type == "catalog"
  }

  schema_records = {
    for r in local.normalized_records : r.row_id => r
    if r.object_type == "schema"
  }

  view_records = {
    for r in local.normalized_records : r.row_id => r
    if r.object_type == "view"
  }

  folder_records = {
    for r in local.normalized_records : r.row_id => r
    if r.object_type == "folder"
  }
}

resource "databricks_grant" "catalog_access" {
  for_each = local.catalog_records

  catalog    = each.value.catalog_name
  principal  = each.value.principal_name
  privileges = each.value.activity == "ADD" ? each.value.privileges : []
}

resource "databricks_grant" "schema_access" {
  for_each = local.schema_records

  schema     = "${each.value.catalog_name}.${each.value.schema_name}"
  principal  = each.value.principal_name
  privileges = each.value.activity == "ADD" ? each.value.privileges : []
}

resource "databricks_grant" "view_access" {
  for_each = local.view_records

  table      = "${each.value.catalog_name}.${each.value.schema_name}.${each.value.object_name}"
  principal  = each.value.principal_name
  privileges = each.value.activity == "ADD" ? each.value.privileges : []
}

resource "databricks_permissions" "folder_access" {
  for_each = local.folder_records

  directory_path = each.value.folder_path

  access_control {
    group_name       = each.value.principal_type == "ad_group" ? each.value.principal_name : null
    service_principal_name = each.value.principal_type == "service_account" ? each.value.principal_name : null
    permission_level = each.value.activity == "ADD" ? each.value.privileges[0] : "CAN_READ"
  }
}
