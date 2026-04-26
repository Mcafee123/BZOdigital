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
