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
  default     = "prod"
}

variable "firestore_database_id" {
  type        = string
  description = "Firestoreデータベース名（マルチデータベースでdev/prodを分離。prodは既定データベースを使用）"
  default     = "(default)"
}

variable "secret_ids" {
  type        = list(string)
  description = "作成するSecret Manager上のシークレット名一覧（docs/infra/02_PARAMS_DEF.md §4）"
  default = [
    "shared-auth-username",
    "shared-auth-password-hash",
    "token-signing-secret",
    "x-api-bearer-token",
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
  type        = number
  description = "コールドスタート回避のため1を既定とする"
  default     = 1
}

variable "cloud_run_max_instances" {
  type    = number
  default = 4
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
  description = "prdは一般公開のためtrue固定。App Check＋password＋rate limitで防御する（docs/infra/03_SECURITY.md §3）"
  default     = true
}

variable "github_actions_deploy_sa_email" {
  type        = string
  description = "infra/bootstrap/で作成した共有github-actions-deploy-saのメールアドレス（bootstrap実行後に値を埋める）"
}
