terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = "us-central1"
}

# Provider-specific environment variables
locals {
  provider_env_vars = var.ecommerce_provider == "shopify" ? {
    "SHOPIFY_SHOP_URL"     = var.shop_url
    "SHOPIFY_ACCESS_TOKEN" = var.access_token
  } : var.ecommerce_provider == "woocommerce" ? {
    "WOOCOMMERCE_URL"         = var.shop_url
    "WOOCOMMERCE_API_KEY"     = var.access_token
    "WOOCOMMERCE_API_SECRET"  = lookup(var.provider_config, "api_secret", "")
  } : {}
}

# Customer-specific admin API
resource "google_cloud_run_service" "customer_admin_api" {
  name     = "admin-api-${var.business_id}"
  location = "us-central1"
  project  = var.project_id

  template {
    spec {
      containers {
        # Use the known image name
        image = "gcr.io/${var.project_id}/admin-api"
        
        # Core configuration
        env {
          name  = "BUSINESS_ID"
          value = var.business_id
        }
        
        env {
          name  = "INTEGRATION_MODE"
          value = var.ecommerce_provider
        }
        
        env {
          name  = "SEARCH_PROVIDER"
          value = "elasticsearch"
        }
        
        # Google Cloud configuration
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        
        env {
          name  = "GOOGLE_CLOUD_LOCATION"
          value = "us-central1"
        }
        
        env {
          name  = "GOOGLE_GENAI_USE_VERTEXAI"
          value = "1"
        }
        
        # Provider-specific configuration
        dynamic "env" {
          for_each = local.provider_env_vars
          content {
            name  = env.key
            value = env.value
          }
        }
        
        # Shared Elasticsearch configuration
        env {
          name  = "ELASTICSEARCH_URL"
          value = "http://34.171.135.203:9200"
        }
        env {
          name  = "ELASTICSEARCH_USER"
          value = "elastic"
        }
        env {
          name  = "ELASTICSEARCH_PASSWORD"
          value = "elastic-mvp-2024"
        }
        env {
          name  = "ELASTICSEARCH_VERIFY_CERTS"
          value = "false"
        }
      }
    }
  }
}

# Customer-specific agent
resource "google_cloud_run_service" "customer_agent" {
  name     = "customer-agent-${var.business_id}"
  location = "us-central1"
  project  = var.project_id

  template {
    spec {
      containers {
        # Use the known image name - note this is different from admin-api
        image = "gcr.io/${var.project_id}/customer-service-agent"
        
        # Core configuration
        env {
          name  = "BUSINESS_ID"
          value = var.business_id
        }
        env {
          name  = "INTEGRATION_MODE"
          value = var.ecommerce_provider
        }
        env {
          name  = "SEARCH_PROVIDER"
          value = "elasticsearch"
        }
        
        # Google Cloud configuration
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        
        env {
          name  = "GOOGLE_CLOUD_LOCATION"
          value = "us-central1"
        }
        
        env {
          name  = "GOOGLE_GENAI_USE_VERTEXAI"
          value = "1"
        }
        
        # Provider-specific configuration
        dynamic "env" {
          for_each = local.provider_env_vars
          content {
            name  = env.key
            value = env.value
          }
        }
        
        # Shared Elasticsearch configuration
        env {
          name  = "ELASTICSEARCH_URL"
          value = "http://34.171.135.203:9200"
        }
        env {
          name  = "ELASTICSEARCH_USER"
          value = "elastic"
        }
        env {
          name  = "ELASTICSEARCH_PASSWORD"
          value = "elastic-mvp-2024"
        }
        env {
          name  = "ELASTICSEARCH_VERIFY_CERTS"
          value = "false"
        }
      }
    }
  }
}

# Make services publicly accessible
resource "google_cloud_run_service_iam_binding" "admin_api_public" {
  location = google_cloud_run_service.customer_admin_api.location
  project  = google_cloud_run_service.customer_admin_api.project
  service  = google_cloud_run_service.customer_admin_api.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}

resource "google_cloud_run_service_iam_binding" "agent_public" {
  location = google_cloud_run_service.customer_agent.location
  project  = google_cloud_run_service.customer_agent.project
  service  = google_cloud_run_service.customer_agent.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}