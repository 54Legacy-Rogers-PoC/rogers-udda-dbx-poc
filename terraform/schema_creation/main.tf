module "schema_creation" {
  source = "../modules/schema_creation"

  request_id                   = var.request_id
  environment                  = var.environment
  sandbox_mode                 = var.sandbox_mode
  sandbox_schema_name          = var.sandbox_schema_name
  sandbox_owner_name           = var.sandbox_owner_name
  default_external_location_rw_principals = var.default_external_location_rw_principals
  create_communitymart_schema  = var.create_communitymart_schema
  communitymart_schema_name    = var.communitymart_schema_name
  communitymart_owner_name     = var.communitymart_owner_name
  justification                = var.justification
  additional_information       = var.additional_information
  assignment_group             = var.assignment_group
  epdg_ticket_url              = var.epdg_ticket_url
  governance_approval_required = var.governance_approval_required
  ad_approval_required         = var.ad_approval_required
}
