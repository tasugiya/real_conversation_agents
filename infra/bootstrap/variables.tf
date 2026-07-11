variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "region" {
  type        = string
  description = "state用バケットのロケーション"
  default     = "us-central1"
}

variable "state_bucket_name" {
  type        = string
  description = "Terraform state用GCSバケット名（グローバルに一意な名前が必要）"
}

variable "github_repository" {
  type        = string
  description = "対象GitHubリポジトリ（owner/repo形式）。WIFのattribute conditionで限定する"
}
