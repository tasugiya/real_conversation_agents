output "workload_identity_provider" {
  description = "google-github-actions/authのworkload_identity_providerに指定するフルリソース名"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "pool_name" {
  value = google_iam_workload_identity_pool.github.name
}
