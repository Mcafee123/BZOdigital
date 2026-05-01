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

# Allow the deploy SP (the one running terraform / azcopy in CI) to write to
# the share via OAuth, so the upload-data workflow doesn't need an account key
# or a SAS.
data "azurerm_client_config" "current" {}

resource "azurerm_role_assignment" "deploy_files" {
  scope                = azurerm_storage_account.data.id
  role_definition_name = "Storage File Data Privileged Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
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

  business_hours_scaling = var.business_hours_scaling

  identity_config = {
    type = "UserAssigned"
    user_assigned_identities = {
      acr = local.acr_config.identity_id
    }
  }

  registry_config = {
    server   = "${local.acr_config.name}.azurecr.io"
    identity = local.acr_config.identity_id
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
          { name = "DATA_PATH", value = "${var.mount_path}/data" },
        ]
        volume_mounts = [
          { name = "repo-data", path = var.mount_path },
        ]
      },
    ]
  }

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

# Apex domains (e.g. nupla.info) can't use --validation-method CNAME, which the
# shared custom-domain module hardcodes. Inline the hostname add + bind here
# with HTTP validation (works for apex via the CNAME-flattened A record).
resource "null_resource" "hostname_add" {
  count = local.has_custom_domain ? 1 : 0
  triggers = {
    domain   = var.custom_domain
    app_name = module.container_app.cfg.name
  }
  provisioner "local-exec" {
    command = <<-EOT
      set -e
      if az containerapp hostname list \
            --name "${module.container_app.cfg.name}" \
            --resource-group "${azurerm_resource_group.app.name}" \
            --query "[?name=='${var.custom_domain}'] | length(@)" -o tsv | grep -q '^0$'; then
        az containerapp hostname add \
          --name "${module.container_app.cfg.name}" \
          --resource-group "${azurerm_resource_group.app.name}" \
          --hostname "${var.custom_domain}"
      else
        echo "hostname ${var.custom_domain} already on ${module.container_app.cfg.name}"
      fi
    EOT
  }
  depends_on = [module.cloudflare]
}

resource "null_resource" "hostname_bind" {
  count = local.has_custom_domain ? 1 : 0
  triggers = {
    domain   = var.custom_domain
    app_name = module.container_app.cfg.name
  }
  provisioner "local-exec" {
    command = <<-EOT
      set -e
      bound=$(az containerapp hostname list \
        --name "${module.container_app.cfg.name}" \
        --resource-group "${azurerm_resource_group.app.name}" \
        --query "[?name=='${var.custom_domain}'].bindingType | [0]" -o tsv)
      if [ "$bound" = "SniEnabled" ]; then
        echo "${var.custom_domain} already SniEnabled"
        exit 0
      fi
      az containerapp hostname bind \
        --name "${module.container_app.cfg.name}" \
        --resource-group "${azurerm_resource_group.app.name}" \
        --hostname "${var.custom_domain}" \
        --environment "${local.cae_config.id}" \
        --validation-method HTTP
    EOT
  }
  depends_on = [null_resource.hostname_add]
}
