# Vertex AI Agent Engine（Reasoning Engine）実行に必要な追加IAMのみを扱う。
# Agent本体のコードやReasoning Engineリソース自体はTerraform管理外とし、
# agent/deploy.py（agent_engines.create/update）がInline Source Deploymentで扱う
# （docs/infra/04_DEPLOY.md §5.3）。

# Google管理のVertex AI Reasoning Engineサービスエージェントに、
# 実行対象プロジェクト内のリソースへアクセスする権限を付与する。
resource "google_project_iam_member" "reasoning_engine_service_agent" {
  project = var.project_id
  role    = "roles/aiplatform.reasoningEngineServiceAgent"
  member  = "serviceAccount:service-${var.project_number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}

# agent-engine-saがVertex AI上でモデル呼び出し・Reasoning Engine管理を行うための権限。
# 基本的なaiplatform.userはmodules/iamで付与済みのため、ここでは追加のnotebook/tool用権限のみ扱う。
resource "google_project_iam_member" "agent_engine_service_usage" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${var.agent_engine_sa_email}"
}
