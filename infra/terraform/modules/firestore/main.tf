# Firestore Native modeデータベース。
# dev/prdはマルチデータベース機能（1プロジェクト内の名前付きデータベース）で分離する
# （docs/infra/00_OVERVIEW.md §4、docs/infra/01_ARCHITECTURE.md §3.4）。

resource "google_firestore_database" "this" {
  project                 = var.project_id
  name                    = var.database_id
  location_id             = var.location_id
  type                    = "FIRESTORE_NATIVE"
  delete_protection_state = var.delete_protection_state
}
