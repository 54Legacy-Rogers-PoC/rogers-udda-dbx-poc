# Normalize mixed request payloads once at the root, then hand filtered maps to
# focused child modules.
locals {
  normalized_records = [
    for r in var.object_access_records : {
      row_id = (
        try(r.row_id, "") != "" ? r.row_id :
        try(r.record_id, "") != "" ? r.record_id :
        tostring(try(r.row_number, 0))
      )
      resource_key = join("|", [
        upper(r.environment != null && r.environment != "" ? r.environment : ""),
        lower(r.access_for != null && r.access_for != "" ? r.access_for : (r.principal_type != null && r.principal_type != "" ? r.principal_type : "")),
        lower(r.principal_name != null && r.principal_name != "" ? r.principal_name : ""),
        upper(r.object_type != null && r.object_type != "" ? r.object_type : ""),
        lower(r.catalog_name != null && r.catalog_name != "" ? r.catalog_name : (r.catalog != null && r.catalog != "" ? r.catalog : "")),
        lower(r.schema_name != null && r.schema_name != "" ? r.schema_name : (r.schema != null && r.schema != "" ? r.schema : "")),
        lower(r.object_name != null && r.object_name != "" ? r.object_name : "")
      ])
      activity       = upper(try(r.activity, ""))
      object_type    = lower(try(r.object_type, ""))
      principal_type = r.principal_type != null && r.principal_type != "" ? r.principal_type : (r.access_for != null && r.access_for != "" ? r.access_for : "")
      principal_name = r.principal_name != null ? r.principal_name : ""
      catalog_name   = r.catalog_name != null && r.catalog_name != "" ? r.catalog_name : (r.catalog != null && r.catalog != "" ? r.catalog : "")
      schema_name    = r.schema_name != null && r.schema_name != "" ? r.schema_name : (r.schema != null && r.schema != "" ? r.schema : "")
      object_name    = r.object_name != null ? r.object_name : ""
      folder_path    = r.folder_path != null ? r.folder_path : ""
      privileges     = r.privileges != null ? r.privileges : (r.privilege != null && r.privilege != "" ? [r.privilege] : [])
      justification  = r.justification != null ? r.justification : ""
    }
  ]

  normalized_record_groups = {
    for r in local.normalized_records : r.resource_key => r...
  }

  grouped_records = {
    for key, records in local.normalized_record_groups : key => merge(records[0], {
      privileges = sort(distinct(flatten([for record in records : record.privileges])))
    })
  }

  catalog_records = {
    for key, r in local.grouped_records : key => r
    if r.resource_key != "" && r.object_type == "catalog"
  }

  schema_records = {
    for key, r in local.grouped_records : key => r
    if r.resource_key != "" && r.object_type == "schema"
  }

  view_records = {
    for key, r in local.grouped_records : key => r
    if r.resource_key != "" && r.object_type == "view"
  }

  folder_records = {
    for key, r in local.grouped_records : key => r
    if r.resource_key != "" && r.object_type == "folder"
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
  count  = 0
  source = "../../modules/service_account"

  add_records    = local.service_account_cluster_add_records
  remove_records = local.service_account_cluster_remove_records
}

# AD group cluster ADD access is isolated so it mirrors the dedicated ADD
# workflow and keeps Terraform addresses activity-specific.
module "cluster_ad_group_add" {
  count  = length(local.cluster_ad_group_add_records) > 0 ? 1 : 0
  source = "../../modules/cluster-adgroup-add"

  add_records = local.cluster_ad_group_add_records
}

# AD group cluster REMOVE access is isolated so it mirrors the dedicated REMOVE
# workflow and avoids mixing both activity types inside one child module.
module "cluster_ad_group_remove" {
  count  = length(local.cluster_ad_group_remove_records) > 0 ? 1 : 0
  source = "../../modules/cluster-adgroup-remove"

  remove_records = local.cluster_ad_group_remove_records
}

locals {
  schema_environment_mapping = yamldecode(file("${path.root}/../../../uda/config/environment-mapping.yaml"))
  communitymart_catalog_grant_specs = toset([
    for request in values(var.schema_creation_requests) : jsonencode({
      catalog = lower(trimspace(try(
        yamldecode(file("${path.root}/../../../${local.schema_environment_mapping.config_files[upper(trimspace(request.environment))]}")).schema_creation.communitymart_catalog_name,
        ""
      )))
      principal = lower(trimspace(request.ad_group_name))
    })
    if request.create_communitymart_schema && trimspace(request.ad_group_name) != ""
  ])
  communitymart_catalog_grants = {
    for encoded in local.communitymart_catalog_grant_specs :
    "${jsondecode(encoded).catalog}|${jsondecode(encoded).principal}" => jsondecode(encoded)
    if jsondecode(encoded).catalog != ""
  }
}

# Catalog traversal is shared by every schema request for the same AD group.
# Schema-specific permissions remain owned by each request module.
resource "databricks_grant" "communitymart_ad_group_catalog" {
  for_each = local.communitymart_catalog_grants

  catalog    = each.value.catalog
  principal  = each.value.principal
  privileges = ["USE_CATALOG"]

  lifecycle {
    prevent_destroy = true
  }
}

# Schema creation runs through the same root stack pattern as the other DDD
# workflows and is enabled only for schema-creation requests.
module "schema_creation" {
  for_each = var.schema_creation_enabled ? var.schema_creation_requests : {}

  source = "../../modules/schema_creation"

  target_type                  = each.value.target_type
  request_id                   = each.value.request_id
  environment                  = each.value.environment
  sandbox_mode                 = each.value.sandbox_mode
  sandbox_schema_name          = each.value.sandbox_schema_name
  sandbox_owner_name           = each.value.sandbox_owner_name
  create_communitymart_schema  = each.value.create_communitymart_schema
  communitymart_schema_name    = each.value.communitymart_schema_name
  communitymart_owner_name     = each.value.communitymart_owner_name
  ad_group_name                = each.value.ad_group_name
  justification                = each.value.justification
  additional_information       = each.value.additional_information
  assignment_group             = each.value.assignment_group
  epdg_ticket_url              = each.value.epdg_ticket_url
  governance_approval_required = each.value.governance_approval_required
  ad_approval_required         = each.value.ad_approval_required
}
