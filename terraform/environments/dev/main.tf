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
