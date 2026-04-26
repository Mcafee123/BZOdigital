variable "app_name" {
  type        = string
  description = "Name of the Container App."
  default     = "bzo-app"
}

variable "resource_group_name" {
  type        = string
  description = "Existing resource group that hosts the Container App."
}

variable "container_app_environment_id" {
  type        = string
  description = "Resource ID of an existing Azure Container Apps environment."
}

variable "acr_login_server" {
  type        = string
  description = "Container registry login server (e.g. example.azurecr.io)."
}

variable "acr_id" {
  type        = string
  description = "Resource ID of the Azure Container Registry."
}

variable "image_name" {
  type        = string
  description = "Full image reference including registry and tag."
}

variable "storage_account_name" {
  type        = string
  description = "Existing storage account that hosts the Azure File share with repo data."
}

variable "storage_account_resource_group" {
  type        = string
  description = "Resource group of the storage account."
}

variable "file_share_name" {
  type        = string
  description = "Azure File share name. Tree mirrors the repo (data/, app/data/, ...)."
}

variable "custom_domain" {
  type        = string
  default     = null
  description = "Optional custom hostname (e.g. bzo-app.example.com). When null, no Cloudflare records are created."
}

variable "cloudflare_api_token" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Cloudflare API token. Required only when custom_domain is set."
}

variable "cloudflare_zone_id" {
  type        = string
  default     = ""
  description = "Cloudflare zone ID that owns custom_domain. Required only when custom_domain is set."
}
