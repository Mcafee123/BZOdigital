output "container_app_id" {
  value = azurerm_container_app.main.id
}

output "container_app_fqdn" {
  value       = try(azurerm_container_app.main.ingress[0].fqdn, null)
  description = "Public ingress FQDN of the Container App."
}

output "identity_principal_id" {
  value = azurerm_user_assigned_identity.app.principal_id
}

output "custom_domain_verification_id" {
  value       = azurerm_container_app.main.custom_domain_verification_id
  description = "Use this when binding the custom domain to the Container App as the asuid TXT record value (the cloudflare module already does this when custom_domain is set)."
}

output "custom_domain_fqdn" {
  value       = var.custom_domain
  description = "The custom domain configured (null when DNS isn't being managed by this module)."
}
