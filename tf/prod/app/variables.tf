variable "image_name" {
  type        = string
  description = "Full image reference (set by CI from build output)."
}

variable "custom_domain" {
  type        = string
  default     = "nupla.info"
  description = "Custom hostname. Set null to skip DNS + binding."
}
