variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "pool_id" {
  type        = string
  description = "Workload Identity Pool ID"
  default     = "github-actions-pool"
}

variable "provider_id" {
  type        = string
  description = "Workload Identity Pool Provider ID"
  default     = "github-actions-provider"
}

variable "github_repository" {
  type        = string
  description = "対象GitHubリポジトリ（owner/repo形式）。attribute conditionでこのリポジトリに限定する"
}

variable "service_account_name" {
  type        = string
  description = "impersonation対象Service Accountのフルリソース名（projects/{project}/serviceAccounts/{email}）"
}
