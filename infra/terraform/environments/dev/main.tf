terraform {
  required_version = ">= 1.10"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "this" {
  project_id = var.project_id
}

module "iam" {
  source      = "../../modules/iam"
  project_id  = var.project_id
  environment = var.environment
}

module "agent_engine_iam" {
  source                = "../../modules/agent-engine-iam"
  project_id            = var.project_id
  project_number        = data.google_project.this.number
  agent_engine_sa_email = module.iam.agent_engine_sa_email
}

module "artifact_registry" {
  source        = "../../modules/artifact-registry"
  project_id    = var.project_id
  location      = var.region
  repository_id = "real-conv-agents-${var.environment}"
}

module "firestore" {
  source      = "../../modules/firestore"
  project_id  = var.project_id
  database_id = var.firestore_database_id
  location_id = var.region
}

module "secret_manager" {
  source     = "../../modules/secret-manager"
  project_id = var.project_id
  secret_ids = var.secret_ids
  accessor_service_accounts = [
    module.iam.api_sa_email,
    module.iam.agent_engine_sa_email,
  ]
}

module "cloud_tasks" {
  source                    = "../../modules/cloud-tasks"
  project_id                = var.project_id
  location                  = var.region
  queue_name                = "topic-pack-generation-${var.environment}"
  max_concurrent_dispatches = var.tasks_max_concurrent_dispatches
  max_dispatches_per_second = var.tasks_max_dispatches_per_second
}

module "cloud_run_api" {
  source                = "../../modules/cloud-run"
  project_id            = var.project_id
  region                = var.region
  service_name          = "real-conv-api-${var.environment}"
  service_account_email = module.iam.api_sa_email
  min_instance_count    = var.cloud_run_min_instances
  max_instance_count    = var.cloud_run_max_instances
  concurrency           = var.cloud_run_concurrency
  timeout_seconds       = var.cloud_run_timeout_seconds
  allow_unauthenticated = var.cloud_run_allow_unauthenticated

  env_vars = {
    GCP_PROJECT_ID               = var.project_id
    GCP_REGION                   = var.region
    ENVIRONMENT                  = var.environment
    FIRESTORE_DATABASE_ID        = var.firestore_database_id
    AGENT_ENGINE_RESOURCE_NAME   = var.agent_engine_resource_name
    CLOUD_TASKS_QUEUE_NAME       = module.cloud_tasks.queue_name
    CLOUD_TASKS_INVOKER_SA_EMAIL = module.iam.cloud_tasks_invoker_sa_email
    FIREBASE_PROJECT_ID          = var.firebase_project_id
    CORS_ALLOWED_ORIGINS         = var.cors_allowed_origins
    APP_CHECK_ENFORCEMENT_MODE   = var.app_check_enforcement_mode
    AUTH_TOKEN_TTL_SECONDS       = tostring(var.auth_token_ttl_seconds)
    STREAM_TICKET_TTL_SECONDS    = tostring(var.stream_ticket_ttl_seconds)
    RATE_LIMIT_PER_IP_PER_MINUTE = tostring(var.rate_limit_per_ip_per_minute)
    CLOUD_RUN_MAX_INSTANCES      = tostring(var.cloud_run_max_instances)
  }
}

# Cloud TasksがこのCloud Run APIサービス内の内部エンドポイントを呼べるようにする
# （循環参照を避けるため、iam/cloud-runモジュールの外側であるここで付与する）
resource "google_cloud_run_v2_service_iam_member" "tasks_invoker" {
  project  = var.project_id
  location = var.region
  name     = module.cloud_run_api.service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.iam.cloud_tasks_invoker_sa_email}"
}

# dev環境はauthentication required（allow_unauthenticated=false）のため、
# 指定した開発者にのみroles/run.invokerを付与する（docs/infra/03_SECURITY.md §3）。
resource "google_cloud_run_v2_service_iam_member" "dev_invokers" {
  for_each = toset(var.dev_invoker_members)
  project  = var.project_id
  location = var.region
  name     = module.cloud_run_api.service_name
  role     = "roles/run.invoker"
  member   = each.value
}

# bootstrap作成の共有github-actions-deploy-saが、dev環境のapi-sa/agent-engine-saを
# actAsしてデプロイできるようにする。
resource "google_service_account_iam_member" "gha_act_as_api" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${module.iam.api_sa_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.github_actions_deploy_sa_email}"
}

resource "google_service_account_iam_member" "gha_act_as_agent_engine" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${module.iam.agent_engine_sa_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.github_actions_deploy_sa_email}"
}

# agent_engines.create()/update()はInline Source Deploymentでも
# vertexai.init(staging_bucket=...)を要求するため、ビルド成果物の一時置き場を用意する。
resource "google_storage_bucket" "agent_staging" {
  name                        = "${var.project_id}-agent-staging-${var.environment}"
  project                     = var.project_id
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "agent_staging_gha_deploy" {
  bucket = google_storage_bucket.agent_staging.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${var.github_actions_deploy_sa_email}"
}

resource "google_storage_bucket_iam_member" "agent_staging_agent_engine" {
  bucket = google_storage_bucket.agent_staging.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${module.iam.agent_engine_sa_email}"
}
