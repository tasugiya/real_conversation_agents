# 環境ごとのService Account一覧（docs/infra/03_SECURITY.md §4、docs/infra/02_PARAMS_DEF.md §9）。
# terraform-saはinfra/bootstrap/で作成するため、ここには含めない。

resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "api-sa-${var.environment}"
  display_name = "Cloud Run API service account (${var.environment})"
}

resource "google_service_account" "agent_engine" {
  project      = var.project_id
  account_id   = "agent-engine-sa-${var.environment}"
  display_name = "Vertex AI Agent Engine service account (${var.environment})"
}

resource "google_service_account" "cloud_tasks_invoker" {
  project      = var.project_id
  account_id   = "tasks-invoker-sa-${var.environment}"
  display_name = "Cloud Tasks invoker service account (${var.environment})"
}

# github-actions-deploy-saはinfra/bootstrap/でプロジェクト共有の1つだけ作成する
# （docs/infra/02_PARAMS_DEF.md §9は環境別にしていない）。ここでは作らない。

# api-sa: Firestore/Secret Manager/Cloud Tasks/Agent Engine呼び出し
resource "google_project_iam_member" "api_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_cloudtasks_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# agent-engine-sa: Firestore/Secret Manager/Vertex AI利用
resource "google_project_iam_member" "agent_engine_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.agent_engine.email}"
}

resource "google_project_iam_member" "agent_engine_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.agent_engine.email}"
}

resource "google_project_iam_member" "agent_engine_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_engine.email}"
}

# 注意: github-actions-deploy-sa（bootstrap作成）がapi-sa/agent-engine-saをactAsする
# 権限（roles/iam.serviceAccountUser）は、環境ごとのenvironments/{dev,prod}/main.tf側で
# var.github_actions_deploy_sa_emailを使って付与する（このモジュールは環境非依存のため）。

# 注意: cloud_tasks_invoker_saへのroles/run.invoker（特定Cloud Runサービス単位）は
# 循環参照を避けるため、cloud-runモジュールを呼び出すenvironments/{dev,prod}/main.tf側で付与する。
