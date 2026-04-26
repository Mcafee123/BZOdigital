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
