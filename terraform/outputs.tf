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
