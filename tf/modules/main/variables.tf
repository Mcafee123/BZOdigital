variable "app_name" {
  type        = string
  description = "Name of the Container App and the user-assigned identity prefix."
}

variable "resource_group_name" {
  type        = string
  description = "Existing resource group that will hold the Container App."
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
  description = "Resource ID of the Azure Container Registry, used to grant AcrPull to the app identity."
}

variable "image_name" {
  type        = string
  description = "Full image reference including registry and tag, e.g. example.azurecr.io/bzo-app:0.1.0-abc1234."
}

variable "diff_path" {
  type        = string
  description = "Path inside the container where the diff file lives."
  default     = "/mnt/repo/app/data/sample.diff"
}

variable "storage_account_name" {
  type        = string
  description = "Existing storage account that holds the Azure File share with repo data."
}

variable "storage_account_resource_group" {
  type        = string
  description = "Resource group of the storage account."
}

variable "file_share_name" {
  type        = string
  description = "Existing Azure File share whose tree mirrors the repo (data/, app/data/, ...)."
}

variable "mount_path" {
  type        = string
  description = "Path inside the container where the file share is mounted. Repo paths sit under this prefix."
  default     = "/mnt/repo"
}

variable "min_replicas" {
  type        = number
  default     = 1
}

variable "max_replicas" {
  type        = number
  default     = 3
}

variable "cpu" {
  type        = number
  default     = 0.25
}

variable "memory" {
  type        = string
  default     = "0.5Gi"
}
