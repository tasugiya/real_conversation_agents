variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "region" {
  type        = string
  description = "デプロイ先リージョン"
}

variable "service_name" {
  type        = string
  description = "Cloud Runサービス名"
}

variable "image" {
  type        = string
  description = "コンテナイメージ。CIが実アプリイメージへ更新するため、初期値はプレースホルダーでよい"
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "service_account_email" {
  type        = string
  description = "このCloud Runサービスの実行Service Account"
}

variable "env_vars" {
  type        = map(string)
  description = "環境変数（docs/infra/02_PARAMS_DEF.md参照）"
  default     = {}
}

variable "min_instance_count" {
  type        = number
  description = "最小インスタンス数"
  default     = 0
}

variable "max_instance_count" {
  type        = number
  description = "最大インスタンス数"
  default     = 2
}

variable "concurrency" {
  type        = number
  description = "1インスタンスあたりの最大同時リクエスト数（WebSocket保持数に直結）"
  default     = 20
}

variable "timeout_seconds" {
  type        = number
  description = "リクエストタイムアウト秒数（WebSocket用に長め。上限3600）"
  default     = 3600
}

variable "ingress" {
  type        = string
  description = "ingress設定"
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "allow_unauthenticated" {
  type        = bool
  description = "trueの場合allUsersにroles/run.invokerを付与する（prd想定）。devではfalseにしIAM認証を要求する"
  default     = false
}
