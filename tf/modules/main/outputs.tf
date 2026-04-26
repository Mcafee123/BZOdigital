output "container_app_name" {
  value = module.container_app.cfg.name
}

output "container_app_fqdn" {
  value       = module.container_app.cfg.fqdn
  description = "Default Azure Container App ingress FQDN."
}

output "custom_domain_fqdn" {
  value       = var.custom_domain
  description = "Configured custom hostname (null when DNS isn't being managed)."
}

output "custom_domain_verification_id" {
  value     = module.container_app.cfg.custom_domain_verification_id
  sensitive = true
}

output "resource_group_name" {
  value = azurerm_resource_group.app.name
}

output "storage_account_name" {
  value = azurerm_storage_account.data.name
}

output "file_share_name" {
  value = azurerm_storage_share.data.name
}

