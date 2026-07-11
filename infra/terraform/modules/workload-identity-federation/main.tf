# GitHub ActionsがGCPへkeyless認証するためのWorkload Identity Federation。
#
# 注意: このモジュールはinfra/bootstrap/からのみ呼び出す。
# CIが使う認証の信頼関係そのものをCI自身に作らせないため
# （鶏卵問題・自己権限拡大の防止。docs/infra/04_DEPLOY.md §4）。

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = var.pool_id
  display_name              = "GitHub Actions Pool"
  description                = "GitHub ActionsからのOIDC federation用"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = var.provider_id
  display_name                       = "GitHub Actions Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  # 対象リポジトリに限定する（docs/infra/02_PARAMS_DEF.md §10）
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "wif_impersonation" {
  service_account_id = var.service_account_name
  role                = "roles/iam.workloadIdentityUser"
  member              = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
