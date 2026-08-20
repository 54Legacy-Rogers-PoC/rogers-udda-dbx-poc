output "object_access_routing_summary" {
  description = "Counts of routed object access records for quick plan-time sanity checks."
  value = {
    total_records          = length(local.normalized_records)
    add_records            = length(local.add_records)
    remove_records         = length(local.remove_records)
    add_catalog_records    = length(local.add_catalog_records)
    add_schema_records     = length(local.add_schema_records)
    add_view_records       = length(local.add_view_records)
    add_folder_records     = length(local.add_folder_records)
    remove_catalog_records = length(local.remove_catalog_records)
    remove_schema_records  = length(local.remove_schema_records)
    remove_view_records    = length(local.remove_view_records)
    remove_folder_records  = length(local.remove_folder_records)
  }
}

output "catalog_access_summary" {
  description = "Summary of catalog access records routed for add/remove activities."
  value = {
    add_records_count    = length(local.catalog_add_record_map)
    remove_records_count = length(local.catalog_remove_record_map)
    remove_records = [
      for r in values(local.catalog_remove_record_map) : {
        record_id      = r.record_id
        row_number     = r.row_number
        principal_name = r.principal_name
        catalog_name   = r.catalog
        privilege      = r.privilege
      }
    ]
  }
}

output "schema_access_summary" {
  description = "Summary of schema access records routed for add/remove activities."
  value = {
    add_records_count    = length(local.schema_add_record_map)
    remove_records_count = length(local.schema_remove_record_map)
    remove_records = [
      for r in values(local.schema_remove_record_map) : {
        record_id      = r.record_id
        row_number     = r.row_number
        principal_name = r.principal_name
        schema_name    = format("%s.%s", r.catalog, r.schema)
        privilege      = r.privilege
      }
    ]
  }
}

output "view_access_summary" {
  description = "Summary of view access records routed for add/remove activities."
  value = {
    add_records_count    = length(local.view_add_record_map)
    remove_records_count = length(local.view_remove_record_map)
    remove_records = [
      for r in values(local.view_remove_record_map) : {
        record_id      = r.record_id
        row_number     = r.row_number
        principal_name = r.principal_name
        view_name      = format("%s.%s.%s", r.catalog, r.schema, r.object_name)
        privilege      = r.privilege
      }
    ]
  }
}

output "folder_access_summary" {
  description = "Summary of folder access records routed for add/remove activities."
  value = {
    add_records_count    = length(local.add_folder_records)
    remove_records_count = length(local.folder_remove_record_map)
    remove_records = [
      for r in values(local.folder_remove_record_map) : {
        record_id      = r.record_id
        row_number     = r.row_number
        principal_name = r.principal_name
        folder_path    = r.folder_path
        privilege      = r.privilege
      }
    ]
  }
}
