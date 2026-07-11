output "cloud_run_api_url" {
  value = module.cloud_run_api.service_url
}

output "firestore_database_id" {
  value = module.firestore.database_id
}

output "artifact_registry_repository_url" {
  value = module.artifact_registry.repository_url
}

output "cloud_tasks_queue_name" {
  value = module.cloud_tasks.queue_name
}

output "api_sa_email" {
  value = module.iam.api_sa_email
}

output "agent_engine_sa_email" {
  value = module.iam.agent_engine_sa_email
}
