# このディレクトリは人力で1回だけ実行する。CI/CDには絶対に組み込まない。
# 理由・実行手順の詳細はREADME.mdとdocs/infra/04_DEPLOY.md §4を参照。

terraform {
  required_version = ">= 1.10"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  # 初回はバックエンド未指定（ローカルstate）で実行する。
  # バケット作成後、README.mdの手順に従いGCSへstateを移行する。
}

provider "google" {
  project = var.project_id
}

# --- Terraform state用GCSバケット ---
resource "google_storage_bucket" "tfstate" {
  name                        = var.state_bucket_name
  project                     = var.project_id
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }
}

# --- Terraform実行用Service Account ---
resource "google_service_account" "terraform" {
  project      = var.project_id
  account_id   = "terraform-sa"
  display_name = "Terraform実行用Service Account"
}

resource "google_project_iam_member" "terraform_editor" {
  # MVPでは広めの権限を許容する。理由はdocs/decisions/へ記録し、後続で縮小する
  # （docs/CONTRIBUTION.md §18.3の例外方針）。
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.terraform.email}"
}

resource "google_project_iam_member" "terraform_resourcemanager_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform.email}"
}

resource "google_storage_bucket_iam_member" "terraform_state_admin" {
  bucket = google_storage_bucket.tfstate.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.terraform.email}"
}

# --- GitHub Actionsデプロイ用Service Account（frontend/api/agent共通の1つ） ---
resource "google_service_account" "github_actions_deploy" {
  project      = var.project_id
  account_id   = "gha-deploy-sa"
  display_name = "GitHub Actions deploy Service Account"
}

resource "google_project_iam_member" "gha_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.github_actions_deploy.email}"
}

resource "google_project_iam_member" "gha_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions_deploy.email}"
}

resource "google_project_iam_member" "gha_firebase_hosting_admin" {
  project = var.project_id
  role    = "roles/firebasehosting.admin"
  member  = "serviceAccount:${google_service_account.github_actions_deploy.email}"
}

resource "google_project_iam_member" "gha_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.github_actions_deploy.email}"
}

# --- Workload Identity Federation ---
# infra/terraform/modules/workload-identity-federationを、bootstrapからのみ呼び出す
# （docs/infra/01_ARCHITECTURE.md §2、モジュール内コメント参照）。
module "wif" {
  source                = "../terraform/modules/workload-identity-federation"
  project_id            = var.project_id
  github_repository     = var.github_repository
  service_account_name  = google_service_account.terraform.name
}

# terraform-sa用のimpersonationはmodule.wifが作成する。
# github-actions-deploy-sa用にも同じPoolへのimpersonationを追加で許可する。
resource "google_service_account_iam_member" "wif_impersonation_gha_deploy" {
  service_account_id = google_service_account.github_actions_deploy.name
  role                = "roles/iam.workloadIdentityUser"
  member              = "principalSet://iam.googleapis.com/${module.wif.pool_name}/attribute.repository/${var.github_repository}"
}
