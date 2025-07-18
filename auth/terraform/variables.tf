variable "business_id" {
  description = "Unique business identifier"
  type        = string
}

variable "ecommerce_provider" {
  description = "E-commerce provider (shopify, woocommerce, etc.)"
  type        = string
  validation {
    condition = contains(["shopify", "woocommerce", "mock"], var.ecommerce_provider)
    error_message = "Provider must be one of: shopify, woocommerce, mock."
  }
}

variable "shop_url" {
  description = "Shop URL (provider-specific format)"
  type        = string
}

variable "access_token" {
  description = "Provider access token"
  type        = string
  sensitive   = true
}

variable "provider_config" {
  description = "Additional provider-specific configuration"
  type        = map(string)
  default     = {}
}

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "elite-coral-463917-b1"
}