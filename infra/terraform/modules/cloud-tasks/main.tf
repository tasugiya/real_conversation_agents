# X API/Topic Pack生成を非同期化するためのCloud Tasksキュー。
# ターゲットはCloud Run APIと同一サービス内の内部エンドポイントであり、
# 独立したWorkerサービスは作らない（docs/infra/01_ARCHITECTURE.md §5）。

resource "google_cloud_tasks_queue" "this" {
  name     = var.queue_name
  project  = var.project_id
  location = var.location

  rate_limits {
    max_concurrent_dispatches = var.max_concurrent_dispatches
    max_dispatches_per_second = var.max_dispatches_per_second
  }

  retry_config {
    max_attempts = var.max_attempts
  }
}
