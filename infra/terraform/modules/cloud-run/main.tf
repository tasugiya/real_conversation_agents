# Cloud Run APIサービスの枠を管理する。
# コンテナイメージはCI（docs/infra/04_DEPLOY.md §5.2）が更新するため、
# lifecycle.ignore_changesでTerraform管理外にする。

resource "google_cloud_run_v2_service" "this" {
  name        = var.service_name
  project     = var.project_id
  location    = var.region
  ingress     = var.ingress
  iap_enabled = var.iap_enabled

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    max_instance_request_concurrency = var.concurrency
    timeout                          = "${var.timeout_seconds}s"

    containers {
      image = var.image

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count    = var.allow_unauthenticated ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
