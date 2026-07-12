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
  description = "作成するSecret Manager上のシークレット名一覧（docs/infra/02_PARAMS_DEF.md §4）。単一プロジェクト内でdev/prodが同じシークレット名を取り合わないよう環境サフィックスを付ける"
  default = [
    "shared-auth-username-prod",
    "shared-auth-password-hash-prod",
    "token-signing-secret-prod",
    "x-api-bearer-token-prod",
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
  default = 5
}

variable "cloud_run_memory" {
  type    = string
  default = "8Gi"
}

variable "cloud_run_cpu" {
  type    = string
  default = "2"
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

variable "agent_engine_resource_name" {
  type        = string
  description = "agent/deploy.py（create）実行後に確定するAgent Engineのresource_name。以降はupdateで同じ値を使い続ける"
  default     = ""
}

variable "firebase_project_id" {
  type        = string
  description = "App Checkトークン検証に使うFirebaseプロジェクトID（通常はproject_idと同じ）"
  default     = ""
}

variable "cors_allowed_origins" {
  type        = string
  description = "許可するfrontendオリジン（Firebase HostingのURL、カンマ区切り。.web.app/.firebaseapp.comの両方を許可する）"
  default     = "https://real-conversation-agents.web.app,https://real-conversation-agents.firebaseapp.com"
}

variable "app_check_enforcement_mode" {
  type    = string
  default = "enforce"
}

variable "auth_token_ttl_seconds" {
  type    = number
  default = 3600
}

variable "stream_ticket_ttl_seconds" {
  type    = number
  default = 60
}

variable "rate_limit_per_ip_per_minute" {
  type        = number
  description = "Cloud Run 1インスタンスあたりの上限（docs/infra/03_SECURITY.md §7）"
  default     = 10
}
