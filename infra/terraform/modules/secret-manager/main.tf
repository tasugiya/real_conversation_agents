# SecretはSecret Managerで一元管理する（docs/infra/03_SECURITY.md §5）。
# シークレットの値そのものはTerraformで投入しない（コード管理・stateへの平文混入を避けるため）。
# 値は手動またはCIのsecretローテーション手順で別途設定する。

resource "google_secret_manager_secret" "this" {
  for_each  = toset(var.secret_ids)
  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }
}

locals {
  accessor_pairs = {
    for pair in setproduct(var.secret_ids, var.accessor_service_accounts) :
    "${pair[0]}__${pair[1]}" => {
      secret_id = pair[0]
      member    = pair[1]
    }
  }
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each  = local.accessor_pairs
  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value.secret_id].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.member}"
}
