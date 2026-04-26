terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

provider "azurerm" {
  subscription_id = var.platform.subscription_id
  features {}
}

provider "cloudflare" {
  # api_token is fetched from Key Vault when a custom domain is configured.
  api_token = local.has_custom_domain ? data.azurerm_key_vault_secret.cloudflare_api_token[0].value : null
}
