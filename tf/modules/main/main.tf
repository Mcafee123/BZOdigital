data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}

data "azurerm_storage_account" "data" {
  name                = var.storage_account_name
  resource_group_name = var.storage_account_resource_group
}

# User-assigned identity for the Container App. Owns AcrPull on the registry.
# Kept external because the shared Container App module doesn't manage identities.
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

# Azure File share registered with the Container App Environment.
# Kept external because the shared Container App module references storage by name only.
resource "azurerm_container_app_environment_storage" "data" {
  name                         = "${var.app_name}-data"
  container_app_environment_id = var.container_app_environment_id
  account_name                 = data.azurerm_storage_account.data.name
  share_name                   = var.file_share_name
  access_key                   = data.azurerm_storage_account.data.primary_access_key
  access_mode                  = "ReadOnly"
}

# Container App via the shared platform module.
module "container_app" {
  source = "git@github.com:affolterNET/affolterNET-Cloud-ContainerApp.git//tf?ref=main"

  container_app_name           = var.app_name
  resource_group_name          = data.azurerm_resource_group.main.name
  container_app_environment_id = var.container_app_environment_id
  keyvault_id                  = var.keyvault_id

  identity_config = {
    type = "UserAssigned"
    user_assigned_identities = {
      acr = azurerm_user_assigned_identity.app.id
    }
  }

  registry_config = {
    server   = var.acr_login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  ingress_config = {
    external_enabled = true
    target_port      = 8080
    transport        = "auto"
    traffic_weights = [
      { percentage = 100, latest_revision = true },
    ]
  }

  template_config = {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas
    volumes = [
      {
        name         = "repo-data"
        storage_name = azurerm_container_app_environment_storage.data.name
        storage_type = "AzureFile"
      },
    ]
    containers = [
      {
        name   = var.app_name
        image  = var.image_name
        cpu    = var.cpu
        memory = var.memory
        env = [
          { name = "DIFF_PATH", value = var.diff_path },
        ]
        volume_mounts = [
          { name = "repo-data", path = var.mount_path },
        ]
      },
    ]
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}

# DNS records for the custom domain (TXT asuid + CNAME) via the shared cloudflare module.
module "cloudflare" {
  count  = var.custom_domain != null ? 1 : 0
  source = "git@github.com:affolterNET/affolterNET-Cloud-HelperModules.git//cloudflare?ref=main"

  cloudflare = {
    zone_id         = var.cloudflare_zone_id
    api_token       = var.cloudflare_api_token
    domain_name     = var.custom_domain
    fqdn            = module.container_app.cfg.fqdn
    verification_id = module.container_app.cfg.custom_domain_verification_id
  }

  depends_on = [module.container_app]
}

# Hostname binding + managed cert via the shared custom-domain module.
# Runs add_hostname.sh + add_binding.sh, which wait for DNS propagation
# (dig @8.8.8.8, 20-min timeout) then call `az containerapp hostname add/bind`.
module "custom_domain" {
  count  = var.custom_domain != null ? 1 : 0
  source = "git@github.com:affolterNET/affolterNET-Cloud-HelperModules.git//custom-domain?ref=main"

  container_app = {
    name            = module.container_app.cfg.name
    domain_name     = var.custom_domain
    fqdn            = module.container_app.cfg.fqdn
    verification_id = module.container_app.cfg.custom_domain_verification_id
    environment_id  = var.container_app_environment_id
    resource_group  = data.azurerm_resource_group.main.name
  }

  depends_on = [module.cloudflare]
}
