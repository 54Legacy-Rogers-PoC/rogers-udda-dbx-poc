locals {
  request_id = trimspace(var.request_id)
  environment = upper(trimspace(var.environment))
  sandbox_mode = lower(trimspace(var.sandbox_mode))

  # Keep catalog defaults explicit until catalog selection is added to request payload.
  sandbox_catalog_name = "edlbi_ss"
  communitymart_catalog_name = "edl_communitymart"
  sandbox_storage_account_host = "stadbdev.dfs.core.windows.net"
  communitymart_storage_base = "abfss://edl-community-mart@stadbdev.dfs.core.windows.net/edl_community_mart"

  sandbox_schema_name = lower(trimspace(var.sandbox_schema_name))
  sandbox_schema_parts = split("_", local.sandbox_schema_name)
  sandbox_container_suffix = length(local.sandbox_schema_parts) > 2 ? join("-", slice(local.sandbox_schema_parts, 1, length(local.sandbox_schema_parts) - 1)) : replace(local.sandbox_schema_name, "_", "-")
  sandbox_storage_container = format("sandbox-%s", local.sandbox_container_suffix)
  sandbox_environment_label = local.environment == "QA" ? "qa" : "dev"
  sandbox_external_location_name = format("el_%s__%s__at__%s__rw", local.sandbox_environment_label, local.sandbox_storage_container, replace(local.sandbox_storage_account_host, ".dfs.core.windows.net", ""))
  sandbox_storage_credential_name = "adb-dev-cred"
  sandbox_external_location_url = format("abfss://%s@%s/", local.sandbox_storage_container, local.sandbox_storage_account_host)
  sandbox_storage_root = format("abfss://%s@%s/%s", local.sandbox_storage_container, local.sandbox_storage_account_host, local.sandbox_schema_name)
  sandbox_owner_name = lower(trimspace(var.sandbox_owner_name))

  create_communitymart_schema = var.create_communitymart_schema
  communitymart_schema_name = lower(trimspace(var.communitymart_schema_name))
  communitymart_owner_name = lower(trimspace(var.communitymart_owner_name))

  justification = trimspace(var.justification)
  additional_information = trimspace(var.additional_information)
  assignment_group = trimspace(var.assignment_group)
  epdg_ticket_url = trimspace(var.epdg_ticket_url)

  sandbox_schema_required = local.sandbox_mode == "new"
  sandbox_schema_valid = !local.sandbox_schema_required || local.sandbox_schema_name != ""

  communitymart_schema_valid = !local.create_communitymart_schema || local.communitymart_schema_name != ""
  communitymart_owner_valid = !local.create_communitymart_schema || local.communitymart_owner_name != ""

  request_targets = concat(
    [
      {
        type    = "sandbox"
        enabled = local.sandbox_mode == "new"
        name    = local.sandbox_schema_name
        owner   = local.sandbox_owner_name
      }
    ],
    [
      {
        type    = "communitymart"
        enabled = local.create_communitymart_schema
        name    = local.communitymart_schema_name
        owner   = local.communitymart_owner_name
      }
    ]
  )
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

resource "databricks_schema" "sandbox" {
  count = local.sandbox_mode == "new" ? 1 : 0

  depends_on = [
    databricks_external_location.sandbox,
  ]

  catalog_name = local.sandbox_catalog_name
  name         = local.sandbox_schema_name
  storage_root = local.sandbox_storage_root
  comment      = format("Schema created from request %s", local.request_id)

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
  }
}

resource "databricks_external_location" "sandbox" {
  count = local.sandbox_mode == "new" ? 1 : 0

  name            = local.sandbox_external_location_name
  url             = local.sandbox_external_location_url
  credential_name = local.sandbox_storage_credential_name
  read_only       = false
  comment         = "Managed by UDA schema workflow"

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
  }
}

resource "databricks_grant" "sandbox_owner" {
  count = local.sandbox_mode == "new" ? 1 : 0

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

resource "databricks_schema" "communitymart" {
  count = local.create_communitymart_schema ? 1 : 0

  catalog_name = local.communitymart_catalog_name
  name         = local.communitymart_schema_name
  storage_root = format("%s/%s", local.communitymart_storage_base, local.communitymart_schema_name)
  comment      = format("Community mart schema created from request %s", local.request_id)

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
  }
}

resource "databricks_grant" "communitymart_owner" {
  count = local.create_communitymart_schema ? 1 : 0

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
