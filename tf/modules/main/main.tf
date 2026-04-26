# Read the platform's terraform state to get ACR, ACE, KV, and other platform
# identifiers without needing them as inputs/secrets.
module "read_core" {
  source = "git@github.com:affolterNET/affolterNET-Cloud-HelperModules.git//read-state?ref=main"
  state = {
    state_rg        = var.platform.state_rg
    state_storage   = var.platform.state_storage
    state_container = var.platform.state_container
    state_map_key   = "platform"
    dest_key        = "${var.basics.environment}_core"
  }
}

locals {
  acr_config = module.read_core.state.platform_outputs.acr_config
  cae_config = module.read_core.state.platform_outputs.cae_config
  keyvault   = module.read_core.state.bootstrap_outputs.keyvault

  has_custom_domain = var.custom_domain != null && var.custom_domain != ""
}

# acr_config from platform state has {name, rg_name, identity_id, ...} but no
# `id`. Look up the ACR by name+rg to get its resource ID for the role
# assignment scope.
data "azurerm_container_registry" "acr" {
  name                = local.acr_config.name
  resource_group_name = local.acr_config.rg_name
}

# Cloudflare credentials (read from platform KV; only fetched when custom domain is on).
data "azurerm_key_vault_secret" "cloudflare_api_token" {
  count        = local.has_custom_domain ? 1 : 0
  name         = var.cloudflare_token_secret_name
  key_vault_id = local.keyvault.id
}

data "azurerm_key_vault_secret" "cloudflare_zone_id" {
  count        = local.has_custom_domain ? 1 : 0
  name         = var.cloudflare_zone_id_secret_name
  key_vault_id = local.keyvault.id
}

# --- Project-owned resources ---------------------------------------------------

resource "azurerm_resource_group" "app" {
  name     = "${var.basics.base_name}-${var.basics.environment}-rg"
  location = var.platform.location
}

# Storage account name must be globally unique, ≤24 chars, alphanumeric only.
resource "azurerm_storage_account" "data" {
  name                     = lower(replace("${var.basics.base_name}data${var.basics.environment}", "-", ""))
  resource_group_name      = azurerm_resource_group.app.name
  location                 = azurerm_resource_group.app.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  min_tls_version          = "TLS1_2"
}

resource "azurerm_storage_share" "data" {
  name               = "repo-data"
  storage_account_id = azurerm_storage_account.data.id
  quota              = 5
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "${var.basics.base_name}-id"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = data.azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_container_app_environment_storage" "data" {
  name                         = "${var.basics.base_name}-data"
  container_app_environment_id = local.cae_config.id
  account_name                 = azurerm_storage_account.data.name
  share_name                   = azurerm_storage_share.data.name
  access_key                   = azurerm_storage_account.data.primary_access_key
  access_mode                  = "ReadOnly"
}

# --- Container App via the shared module ---------------------------------------

module "container_app" {
  source = "git@github.com:affolterNET/affolterNET-Cloud-ContainerApp.git//tf?ref=main"

  container_app_name           = var.basics.base_name
  resource_group_name          = azurerm_resource_group.app.name
  container_app_environment_id = local.cae_config.id
  keyvault_id                  = local.keyvault.id

  identity_config = {
    type = "UserAssigned"
    user_assigned_identities = {
      acr = azurerm_user_assigned_identity.app.id
    }
  }

  registry_config = {
    server   = "${local.acr_config.name}.azurecr.io"
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
        name   = var.basics.base_name
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

# --- Custom domain (DNS + hostname bind), conditional --------------------------

module "cloudflare" {
  count  = local.has_custom_domain ? 1 : 0
  source = "git@github.com:affolterNET/affolterNET-Cloud-HelperModules.git//cloudflare?ref=main"

  cloudflare = {
    zone_id         = data.azurerm_key_vault_secret.cloudflare_zone_id[0].value
    api_token       = data.azurerm_key_vault_secret.cloudflare_api_token[0].value
    domain_name     = var.custom_domain
    fqdn            = module.container_app.cfg.fqdn
    verification_id = module.container_app.cfg.custom_domain_verification_id
  }

  depends_on = [module.container_app]
}

module "custom_domain" {
  count  = local.has_custom_domain ? 1 : 0
  source = "git@github.com:affolterNET/affolterNET-Cloud-HelperModules.git//custom-domain?ref=main"

  container_app = {
    name            = module.container_app.cfg.name
    domain_name     = var.custom_domain
    fqdn            = module.container_app.cfg.fqdn
    verification_id = module.container_app.cfg.custom_domain_verification_id
    environment_id  = local.cae_config.id
    resource_group  = azurerm_resource_group.app.name
  }

  depends_on = [module.cloudflare]
}
