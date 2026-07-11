variable "project_id" {
  type        = string
  description = "GCPプロジェクトID"
}

variable "secret_ids" {
  type        = list(string)
  description = "作成するシークレット名一覧（docs/infra/02_PARAMS_DEF.md §4参照）"
}

variable "accessor_service_accounts" {
  type        = list(string)
  description = "roles/secretmanager.secretAccessorを付与するService Accountのメールアドレス一覧"
  default     = []
}
