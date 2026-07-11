variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "location" {
  type        = string
  description = "キューのロケーション（GCP_REGIONと揃える）"
}

variable "queue_name" {
  type        = string
  description = "キュー名（例: topic-pack-generation）"
  default     = "topic-pack-generation"
}

variable "max_concurrent_dispatches" {
  type        = number
  description = "同時dispatch数上限。X API/Geminiのレート制限に合わせて設定"
  default     = 5
}

variable "max_dispatches_per_second" {
  type        = number
  description = "秒あたりdispatch数上限"
  default     = 2
}

variable "max_attempts" {
  type        = number
  description = "リトライ回数上限"
  default     = 5
}
