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
  description = "Firestoreデータベース名（マルチデータベースでdev/prodを分離）。4〜63文字必要なため'dev'単体は不可"
  default     = "dev-db"
}

variable "secret_ids" {
  type        = list(string)
  description = "作成するSecret Manager上のシークレット名一覧（docs/infra/02_PARAMS_DEF.md §4）。単一プロジェクト内でdev/prodが同じシークレット名を取り合わないよう環境サフィックスを付ける"
  default = [
    "shared-auth-username-dev",
    "shared-auth-password-hash-dev",
    "token-signing-secret-dev",
    "x-api-bearer-token-dev",
    "app-check-debug-token-dev",
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
  description = "許可するfrontendオリジン（Firebase HostingのURL）"
  default     = ""
}

variable "app_check_enforcement_mode" {
  type    = string
  default = "monitor"
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
  default     = 20
}
