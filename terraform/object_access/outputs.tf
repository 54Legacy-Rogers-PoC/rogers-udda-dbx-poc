output "object_access_routing_summary" {
  description = "Root-level routing summary from object_access module."
  value       = module.object_access.object_access_routing_summary
}

output "catalog_access_summary" {
  description = "Root-level catalog access summary from object_access module."
  value       = module.object_access.catalog_access_summary
}

output "schema_access_summary" {
  description = "Root-level schema access summary from object_access module."
  value       = module.object_access.schema_access_summary
}

output "view_access_summary" {
  description = "Root-level view access summary from object_access module."
  value       = module.object_access.view_access_summary
}

output "folder_access_summary" {
  description = "Root-level folder access summary from object_access module."
  value       = module.object_access.folder_access_summary
}
