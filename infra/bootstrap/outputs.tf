output "state_bucket_name" {
  value = google_storage_bucket.tfstate.name
}

output "terraform_sa_email" {
  value = google_service_account.terraform.email
}

output "github_actions_deploy_sa_email" {
  value = google_service_account.github_actions_deploy.email
}

output "workload_identity_provider" {
  description = "GitHub Actions側でgoogle-github-actions/authのworkload_identity_providerに設定する値"
  value       = module.wif.workload_identity_provider
}
