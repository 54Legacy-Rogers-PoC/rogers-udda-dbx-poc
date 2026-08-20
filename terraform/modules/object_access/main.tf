locals {
  normalized_records = [
    for r in var.object_access_records : {
      record_id      = trimspace(r.record_id)
      activity       = upper(trimspace(r.activity))
      environment    = upper(trimspace(r.environment))
      access_for     = lower(trimspace(r.access_for))
      principal_name = trimspace(r.principal_name)
      object_type    = upper(trimspace(r.object_type))
      catalog        = trimspace(r.catalog)
      schema         = trimspace(r.schema)
      object_name    = trimspace(r.object_name)
      folder_path    = trimspace(r.folder_path)
      privilege      = upper(trimspace(r.privilege))
      justification  = trimspace(r.justification)
      row_number     = r.row_number
    }
  ]

  add_records = [
    for r in local.normalized_records : r if r.activity == "ADD"
  ]

  remove_records = [
    for r in local.normalized_records : r if r.activity == "REMOVE"
  ]

  add_catalog_records = [
    for r in local.add_records : r if r.object_type == "CATALOG"
  ]
  add_schema_records = [
    for r in local.add_records : r if r.object_type == "SCHEMA"
  ]
  add_view_records = [
    for r in local.add_records : r if r.object_type == "VIEW"
  ]
  add_folder_records = [
    for r in local.add_records : r if r.object_type == "FOLDER"
  ]

  remove_catalog_records = [
    for r in local.remove_records : r if r.object_type == "CATALOG"
  ]
  remove_schema_records = [
    for r in local.remove_records : r if r.object_type == "SCHEMA"
  ]
  remove_view_records = [
    for r in local.remove_records : r if r.object_type == "VIEW"
  ]
  remove_folder_records = [
    for r in local.remove_records : r if r.object_type == "FOLDER"
  ]

  schema_add_record_map = {
    for r in local.add_schema_records :
    format("%s-%d", r.record_id, r.row_number) => r
  }
  schema_remove_record_map = {
    for r in local.remove_schema_records :
    format("%s-%d", r.record_id, r.row_number) => r
  }

  view_add_record_map = {
    for r in local.add_view_records :
    format("%s-%d", r.record_id, r.row_number) => r
  }
  view_remove_record_map = {
    for r in local.remove_view_records :
    format("%s-%d", r.record_id, r.row_number) => r
  }

  catalog_add_record_map = {
    for r in local.add_catalog_records :
    format("%s-%d", r.record_id, r.row_number) => r
  }
  catalog_remove_record_map = {
    for r in local.remove_catalog_records :
    format("%s-%d", r.record_id, r.row_number) => r
  }

  folder_remove_record_map = {
    for r in local.remove_folder_records :
    format("%s-%d", r.record_id, r.row_number) => r
  }
}

resource "databricks_grant" "catalog_add" {
  for_each = local.catalog_add_record_map

  catalog   = each.value.catalog
  principal = each.value.principal_name
  privileges = [
    each.value.privilege
  ]
}

resource "databricks_grant" "schema_add" {
  for_each = local.schema_add_record_map

  schema    = format("%s.%s", each.value.catalog, each.value.schema)
  principal = each.value.principal_name
  privileges = [
    each.value.privilege
  ]
}

resource "databricks_grant" "view_add" {
  for_each = local.view_add_record_map

  table     = format("%s.%s.%s", each.value.catalog, each.value.schema, each.value.object_name)
  principal = each.value.principal_name
  privileges = [
    each.value.privilege
  ]
}
