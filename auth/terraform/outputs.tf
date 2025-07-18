output "admin_api_url" {
  value = google_cloud_run_service.customer_admin_api.status[0].url
}

output "agent_url" {
  value = google_cloud_run_service.customer_agent.status[0].url
}

output "business_id" {
  value = var.business_id
}

output "ecommerce_provider" {
  value = var.ecommerce_provider
}