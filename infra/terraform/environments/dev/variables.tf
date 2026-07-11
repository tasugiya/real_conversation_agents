variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "region" {
  type        = string
  description = "デプロイ先リージョン（asia-northeast1採用可否はdocs/infra/00_OVERVIEW.md §5を参照）"
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "環境名"
  default     = "dev"
}

variable "firestore_database_id" {
  type        = string
  description = "Firestoreデータベース名（マルチデータベースでdev/prodを分離）"
  default     = "dev"
}

variable "secret_ids" {
  type        = list(string)
  description = "作成するSecret Manager上のシークレット名一覧（docs/infra/02_PARAMS_DEF.md §4）"
  default = [
    "shared-auth-username",
    "shared-auth-password-hash",
    "token-signing-secret",
    "x-api-bearer-token",
    "app-check-debug-token",
  ]
}

variable "tasks_max_concurrent_dispatches" {
  type    = number
  default = 5
}

variable "tasks_max_dispatches_per_second" {
  type    = number
  default = 2
}

variable "cloud_run_min_instances" {
  type    = number
  default = 0
}

variable "cloud_run_max_instances" {
  type    = number
  default = 2
}

variable "cloud_run_concurrency" {
  type    = number
  default = 20
}

variable "cloud_run_timeout_seconds" {
  type    = number
  default = 3600
}

variable "cloud_run_allow_unauthenticated" {
  type        = bool
  description = "devはIAM認証を要求するためfalse固定（docs/infra/03_SECURITY.md §3）"
  default     = false
}

variable "dev_invoker_members" {
  type        = list(string)
  description = "dev環境のCloud Run APIをIAM認証で叩ける開発者。'user:xxx@example.com'形式で列挙する"
  default     = []
}

variable "github_actions_deploy_sa_email" {
  type        = string
  description = "infra/bootstrap/で作成した共有github-actions-deploy-saのメールアドレス（bootstrap実行後に値を埋める）"
}
