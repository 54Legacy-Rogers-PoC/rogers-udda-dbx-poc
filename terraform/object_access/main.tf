module "object_access" {
  source = "../modules/object_access"

  providers = {
    databricks = databricks
  }

  object_access_records = var.object_access_records
}
