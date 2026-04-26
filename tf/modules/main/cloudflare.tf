# Cloudflare DNS records for the Container App's custom domain.
# Conditional: only created when var.custom_domain is non-null.
#
# After these records exist and propagate, you still need to:
#   1. Bind the domain to the Container App (azurerm_container_app.custom_domain block,
#      or `az containerapp hostname bind ...`).
#   2. Provision a managed certificate (azurerm_container_app_environment_certificate
#      or `az containerapp hostname bind --validation-method CNAME ...`).
# This module deliberately stops at the DNS layer to keep the apply ordering simple.

resource "cloudflare_record" "verification" {
  count = var.custom_domain != null ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = "asuid.${var.custom_domain}"
  content = azurerm_container_app.main.custom_domain_verification_id
  type    = "TXT"
  ttl     = 1
  comment = "Azure Container App ${var.app_name} domain ownership"
}

resource "cloudflare_record" "cname" {
  count = var.custom_domain != null ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = var.custom_domain
  content = azurerm_container_app.main.ingress[0].fqdn
  type    = "CNAME"
  proxied = false
  ttl     = 1
  comment = "Azure Container App ${var.app_name} ingress"
}
