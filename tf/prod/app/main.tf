module "main" {
  source = "../../modules/main"

  app_name                       = var.app_name
  resource_group_name            = var.resource_group_name
  container_app_environment_id   = var.container_app_environment_id
  acr_login_server               = var.acr_login_server
  acr_id                         = var.acr_id
  image_name                     = var.image_name
  storage_account_name           = var.storage_account_name
  storage_account_resource_group = var.storage_account_resource_group
  file_share_name                = var.file_share_name
}

output "container_app_fqdn" {
  value = module.main.container_app_fqdn
}
