output "request_summary" {
  description = "Normalized schema-creation request values used by Terraform."
  value = {
    request_id                   = local.request_id
    environment                  = local.environment
    sandbox_mode                 = local.sandbox_mode
    sandbox_owner_name           = local.sandbox_owner_name
    assignment_group             = local.assignment_group
    governance_approval_required = var.governance_approval_required
    ad_approval_required         = var.ad_approval_required
  }
}

output "schema_targets" {
  description = "Schema targets derived from request flags."
  value       = local.request_targets
}

output "schema_creation_result" {
  description = "Planned or created schema fully-qualified names and enablement flags."
  value = {
    sandbox_enabled = local.sandbox_mode == "new"
    sandbox_fqn     = local.sandbox_mode == "new" ? format("%s.%s", local.sandbox_catalog_name, local.sandbox_schema_name) : ""

    communitymart_enabled = local.create_communitymart_schema
    communitymart_fqn     = local.create_communitymart_schema ? format("%s.%s", local.communitymart_catalog_name, local.communitymart_schema_name) : ""
  }
}