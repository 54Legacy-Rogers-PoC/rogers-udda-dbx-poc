# Root outputs keep request context available to workflow stages even after the
# resources themselves are split into child modules.
output "request_id" {
  description = "Request ID processed by this execution"
  value       = var.request_id
}

output "environment" {
  description = "Environment processed by this execution"
  value       = var.environment
}

output "object_count" {
  description = "Number of object access records submitted"
  value       = length(var.object_access_records)
}

output "schema_request_summary" {
  description = "Schema-creation request summary when schema module is enabled"
  value       = try(module.schema_creation[0].request_summary, null)
}

output "schema_targets" {
  description = "Schema targets when schema module is enabled"
  value       = try(module.schema_creation[0].schema_targets, [])
}

output "schema_creation_result" {
  description = "Schema creation result when schema module is enabled"
  value       = try(module.schema_creation[0].schema_creation_result, null)
}
