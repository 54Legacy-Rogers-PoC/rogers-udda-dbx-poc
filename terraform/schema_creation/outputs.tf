output "request_summary" {
  description = "Normalized request summary emitted by schema_creation module."
  value       = module.schema_creation.request_summary
}

output "schema_targets" {
  description = "Planned schema targets emitted by schema_creation module."
  value       = module.schema_creation.schema_targets
}

output "schema_creation_result" {
  description = "Created/planned schema result emitted by schema_creation module."
  value       = module.schema_creation.schema_creation_result
}