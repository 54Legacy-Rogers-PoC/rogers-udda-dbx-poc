# Normalize mixed request payloads once at the root, then hand filtered maps to
# focused child modules.
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

  service_account_cluster_access_records = {
    for r in var.service_account_cluster_access_records : r.row_id => merge(r, {
      activity = upper(r.activity)
    })
  }

  service_account_cluster_add_records = {
    for key, r in local.service_account_cluster_access_records : key => r
    if r.activity == "ADD_TO_CLUSTER"
  }

  service_account_cluster_remove_records = {
    for key, r in local.service_account_cluster_access_records : key => r
    if r.activity == "REMOVE_FROM_CLUSTER"
  }

  cluster_ad_group_access_records = {
    for r in var.cluster_ad_group_access_records : r.row_id => merge(r, {
      activity = upper(r.activity)
    })
  }

  cluster_ad_group_add_records = {
    for key, r in local.cluster_ad_group_access_records : key => r
    if r.activity == "ADD"
  }

  cluster_ad_group_remove_records = {
    for key, r in local.cluster_ad_group_access_records : key => r
    if r.activity == "REMOVE"
  }
}

# Object-level permissions stay grouped together because they share the same
# request shape but target different Databricks securables.
module "object_access" {
  source = "../../modules/object-access"

  catalog_records = local.catalog_records
  schema_records  = local.schema_records
  view_records    = local.view_records
  folder_records  = local.folder_records
}

# Service-account cluster access is isolated from object access so DDD-DBX-01
# can evolve independently.
module "service_account_cluster" {
  source = "../../modules/service_account"

  add_records    = local.service_account_cluster_add_records
  remove_records = local.service_account_cluster_remove_records
}

# AD group cluster ADD access is isolated so it mirrors the dedicated ADD
# workflow and keeps Terraform addresses activity-specific.
module "cluster_ad_group_add" {
  source = "../../modules/cluster-adgroup-add"

  add_records = local.cluster_ad_group_add_records
}

# AD group cluster REMOVE access is isolated so it mirrors the dedicated REMOVE
# workflow and avoids mixing both activity types inside one child module.
module "cluster_ad_group_remove" {
  source = "../../modules/cluster-adgroup-remove"

  remove_records = local.cluster_ad_group_remove_records
}

# Schema creation runs through the same root stack pattern as the other DDD
# workflows and is enabled only for schema-creation requests.
module "schema_creation" {
  count = var.schema_creation_enabled ? 1 : 0

  source = "../../modules/schema_creation"

  request_id                             = var.request_id
  environment                            = var.environment
  sandbox_mode                           = var.sandbox_mode
  sandbox_schema_name                    = var.sandbox_schema_name
  sandbox_owner_name                     = var.sandbox_owner_name
  default_external_location_rw_principals = var.default_external_location_rw_principals
  create_communitymart_schema            = var.create_communitymart_schema
  communitymart_schema_name              = var.communitymart_schema_name
  communitymart_owner_name               = var.communitymart_owner_name
  justification                          = var.justification
  additional_information                 = var.additional_information
  assignment_group                       = var.assignment_group
  epdg_ticket_url                        = var.epdg_ticket_url
  governance_approval_required           = var.governance_approval_required
  ad_approval_required                   = var.ad_approval_required
}
