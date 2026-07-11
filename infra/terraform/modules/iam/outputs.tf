output "api_sa_email" {
  value = google_service_account.api.email
}

output "agent_engine_sa_email" {
  value = google_service_account.agent_engine.email
}

output "cloud_tasks_invoker_sa_email" {
  value = google_service_account.cloud_tasks_invoker.email
}
