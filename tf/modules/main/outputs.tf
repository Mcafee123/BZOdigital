output "container_app_id" {
  value = module.container_app.cfg.name
}

output "container_app_fqdn" {
  value       = module.container_app.cfg.fqdn
  description = "Default Azure Container App ingress FQDN."
}

output "identity_principal_id" {
  value = azurerm_user_assigned_identity.app.principal_id
}

output "custom_domain_verification_id" {
  value       = module.container_app.cfg.custom_domain_verification_id
  description = "Used by the cloudflare module as the asuid TXT record value."
}

output "custom_domain_fqdn" {
  value       = var.custom_domain
  description = "The custom domain configured (null when DNS isn't being managed by this module)."
}
