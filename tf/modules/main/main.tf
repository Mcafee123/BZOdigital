data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}

data "azurerm_storage_account" "data" {
  name                = var.storage_account_name
  resource_group_name = var.storage_account_resource_group
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "${var.app_name}-id"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_container_app_environment_storage" "data" {
  name                         = "${var.app_name}-data"
  container_app_environment_id = var.container_app_environment_id
  account_name                 = data.azurerm_storage_account.data.name
  share_name                   = var.file_share_name
  access_key                   = data.azurerm_storage_account.data.primary_access_key
  access_mode                  = "ReadOnly"
}

resource "azurerm_container_app" "main" {
  name                         = var.app_name
  resource_group_name          = data.azurerm_resource_group.main.name
  container_app_environment_id = var.container_app_environment_id
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = var.acr_login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    volume {
      name         = "repo-data"
      storage_type = "AzureFile"
      storage_name = azurerm_container_app_environment_storage.data.name
    }

    container {
      name   = var.app_name
      image  = var.image_name
      cpu    = var.cpu
      memory = var.memory

      env {
        name  = "DIFF_PATH"
        value = var.diff_path
      }

      volume_mounts {
        name = "repo-data"
        path = var.mount_path
      }
    }
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}

# DNS records for the custom domain (TXT asuid + CNAME).
# Uses the shared cloudflare helper module from affolterNET-Cloud-HelperModules.
module "cloudflare" {
  count  = var.custom_domain != null ? 1 : 0
  source = "git@github.com:affolterNET/affolterNET-Cloud-HelperModules.git//cloudflare?ref=main"

  cloudflare = {
    zone_id         = var.cloudflare_zone_id
    api_token       = var.cloudflare_api_token
    domain_name     = var.custom_domain
    fqdn            = azurerm_container_app.main.ingress[0].fqdn
    verification_id = azurerm_container_app.main.custom_domain_verification_id
  }

  depends_on = [azurerm_container_app.main]
}

# Hostname binding + managed cert via the shared custom-domain helper module.
# It runs add_hostname.sh + add_binding.sh, which wait for DNS propagation
# (dig @8.8.8.8 with 20-min timeout) before calling `az containerapp hostname add/bind`.
# Both scripts are idempotent.
module "custom_domain" {
  count  = var.custom_domain != null ? 1 : 0
  source = "git@github.com:affolterNET/affolterNET-Cloud-HelperModules.git//custom-domain?ref=main"

  container_app = {
    name            = azurerm_container_app.main.name
    domain_name     = var.custom_domain
    fqdn            = azurerm_container_app.main.ingress[0].fqdn
    verification_id = azurerm_container_app.main.custom_domain_verification_id
    environment_id  = var.container_app_environment_id
    resource_group  = data.azurerm_resource_group.main.name
  }

  depends_on = [module.cloudflare]
}
