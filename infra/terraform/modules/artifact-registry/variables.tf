variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "location" {
  type        = string
  description = "リポジトリのロケーション"
}

variable "repository_id" {
  type        = string
  description = "Artifact Registryリポジトリ名"
}

variable "format" {
  type        = string
  description = "リポジトリ形式"
  default     = "DOCKER"
}
