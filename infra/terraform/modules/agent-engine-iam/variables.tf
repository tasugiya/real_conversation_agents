variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "project_number" {
  type        = string
  description = "GCPプロジェクト番号（Google管理のVertex AI Reasoning Engineサービスエージェント識別に使う）"
}

variable "agent_engine_sa_email" {
  type        = string
  description = "modules/iamで作成したagent-engine-saのメールアドレス"
}
