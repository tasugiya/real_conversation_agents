variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "database_id" {
  type        = string
  description = "Firestoreデータベース名。dev/prdはマルチデータベース機能で分離する（例: dev, (default)）"
}

variable "location_id" {
  type        = string
  description = "Firestoreのロケーション"
  default     = "us-central1"
}

variable "delete_protection_state" {
  type        = string
  description = "削除保護。誤削除防止のためprdではDELETE_PROTECTION_ENABLEDを推奨"
  default     = "DELETE_PROTECTION_DISABLED"
}
