variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "environment" {
  type        = string
  description = "環境名（dev/prd）。Service Account名のサフィックスに使う"
}
