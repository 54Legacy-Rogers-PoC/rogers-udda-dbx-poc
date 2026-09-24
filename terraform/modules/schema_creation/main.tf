locals {
  target_type             = lower(trimspace(var.target_type))
  request_id              = trimspace(var.request_id)
  environment             = upper(trimspace(var.environment))
  sandbox_mode            = lower(trimspace(var.sandbox_mode))
  environment_mapping     = yamldecode(file("${path.module}/../../../uda/config/environment-mapping.yaml"))
  environment_config_path = try(local.environment_mapping.config_files[local.environment], "")
  environment_config      = yamldecode(file("${path.module}/../../../${local.environment_config_path}"))
  schema_creation_config  = try(local.environment_config.schema_creation, {})

  sandbox_catalog_name       = trimspace(local.schema_creation_config.sandbox_catalog_name)
  communitymart_catalog_name = trimspace(local.schema_creation_config.communitymart_catalog_name)

  sandbox_schema_name = lower(trimspace(var.sandbox_schema_name))
  sandbox_owner_name  = lower(trimspace(var.sandbox_owner_name))

  create_communitymart_schema = var.create_communitymart_schema
  communitymart_schema_name   = lower(trimspace(var.communitymart_schema_name))
  communitymart_owner_name    = lower(trimspace(var.communitymart_owner_name))
  ad_group_name               = lower(trimspace(var.ad_group_name))

  justification          = trimspace(var.justification)
  additional_information = trimspace(var.additional_information)
  assignment_group       = trimspace(var.assignment_group)
  epdg_ticket_url        = trimspace(var.epdg_ticket_url)

  manage_sandbox          = local.target_type == "sandbox" && local.sandbox_mode == "new"
  manage_communitymart    = local.target_type == "communitymart" && local.create_communitymart_schema
  sandbox_schema_required = local.manage_sandbox
  sandbox_schema_valid    = !local.sandbox_schema_required || local.sandbox_schema_name != ""

  communitymart_schema_valid = !local.manage_communitymart || local.communitymart_schema_name != ""
  communitymart_owner_valid  = !local.manage_communitymart || local.communitymart_owner_name != ""
  ad_group_valid             = local.ad_group_name != ""

  request_targets = concat(
    [
      {
        type    = "sandbox"
        enabled = local.manage_sandbox
        name    = local.sandbox_schema_name
        owner   = local.sandbox_owner_name
      }
    ],
    [
      {
        type    = "communitymart"
        enabled = local.manage_communitymart
        name    = local.communitymart_schema_name
        owner   = local.communitymart_owner_name
      }
    ]
  )

  schema_creation_config_valid = alltrue([
    local.environment_config_path != "",
    local.sandbox_catalog_name != "",
    local.communitymart_catalog_name != "",
  ])
}

check "sandbox_schema_name_required_for_new_mode" {
  assert {
    condition     = local.sandbox_schema_valid
    error_message = "sandbox_schema_name must be provided when sandbox_mode is new."
  }
}

check "communitymart_schema_name_required_when_enabled" {
  assert {
    condition     = local.communitymart_schema_valid
    error_message = "communitymart_schema_name must be provided when create_communitymart_schema is true."
  }
}

check "communitymart_owner_required_when_enabled" {
  assert {
    condition     = local.communitymart_owner_valid
    error_message = "communitymart_owner_name must be provided when create_communitymart_schema is true."
  }
}

check "ad_group_required" {
  assert {
    condition     = local.ad_group_valid
    error_message = "ad_group_name must be provided for schema permissions."
  }
}

check "schema_creation_environment_config_complete" {
  assert {
    condition     = local.schema_creation_config_valid
    error_message = format("schema_creation environment config is incomplete for %s in %s.", local.environment, local.environment_config_path)
  }
}

resource "databricks_schema" "sandbox" {
  count = local.manage_sandbox ? 1 : 0

  catalog_name = local.sandbox_catalog_name
  name         = local.sandbox_schema_name
  comment      = format("Schema created from request %s", local.request_id)

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
    ignore_changes        = [storage_root]
  }
}

removed {
  from = databricks_external_location.sandbox
  lifecycle {
    destroy = false
  }
}

removed {
  from = databricks_grants.sandbox_external_location_access
  lifecycle {
    destroy = false
  }
}

resource "databricks_grant" "sandbox_owner" {
  count = local.manage_sandbox ? 1 : 0

  depends_on = [
    databricks_schema.sandbox,
  ]

  schema    = format("%s.%s", local.sandbox_catalog_name, local.sandbox_schema_name)
  principal = local.sandbox_owner_name
  privileges = [
    "ALL_PRIVILEGES",
  ]

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
  }
}

resource "databricks_grant" "sandbox_ad_group" {
  count = local.manage_sandbox && local.ad_group_name != local.sandbox_owner_name ? 1 : 0

  depends_on = [
    databricks_schema.sandbox,
  ]

  schema     = format("%s.%s", local.sandbox_catalog_name, local.sandbox_schema_name)
  principal  = local.ad_group_name
  privileges = ["ALL_PRIVILEGES"]
}

resource "databricks_schema" "communitymart" {
  count = local.manage_communitymart ? 1 : 0

  catalog_name = local.communitymart_catalog_name
  name         = local.communitymart_schema_name
  comment      = format("Community mart schema created from request %s", local.request_id)

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
    ignore_changes        = [storage_root]
  }
}

resource "databricks_grant" "communitymart_owner" {
  count = local.manage_communitymart ? 1 : 0

  depends_on = [
    databricks_schema.communitymart,
  ]

  schema    = format("%s.%s", local.communitymart_catalog_name, local.communitymart_schema_name)
  principal = local.communitymart_owner_name
  privileges = [
    "ALL_PRIVILEGES",
  ]

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
  }
}

resource "databricks_grant" "communitymart_ad_group_schema" {
  count = local.manage_communitymart && local.ad_group_name != local.communitymart_owner_name ? 1 : 0

  depends_on = [
    databricks_schema.communitymart,
  ]

  schema     = format("%s.%s", local.communitymart_catalog_name, local.communitymart_schema_name)
  principal  = local.ad_group_name
  privileges = ["USE_SCHEMA"]
}
