module "main" {
  source = "../../modules/main"

  platform      = var.platform
  basics        = var.basics
  image_name    = var.image_name
  custom_domain = var.custom_domain
}

output "container_app_fqdn" {
  value = module.main.container_app_fqdn
}

output "resource_group_name" {
  value = module.main.resource_group_name
}

output "storage_account_name" {
  value = module.main.storage_account_name
}

output "file_share_name" {
  value = module.main.file_share_name
}
