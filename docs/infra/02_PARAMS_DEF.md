# リアルな複数人英会話トレーニングエージェント 設定パラメータ定義書

## 目次

- [0. 文書情報](#0-文書情報)
- [1. リージョン・環境識別](#1-リージョン環境識別)
- [2. Frontend（Firebase Hosting / Vite envs）](#2-frontendfirebase-hosting--vite-envs)
- [3. API（Cloud Run）環境変数](#3-apicloud-run環境変数)
- [4. API向けSecret Manager格納値](#4-api向けsecret-manager格納値)
- [5. Cloud Tasks](#5-cloud-tasks)
- [6. Agent Engine（ADK）](#6-agent-engineadk)
- [7. Firestore](#7-firestore)
- [8. App Check](#8-app-check)
- [9. IAM / Service Account](#9-iam--service-account)
- [10. Workload Identity Federation / Artifact Registry](#10-workload-identity-federation--artifact-registry)
- [11. コスト管理・監視](#11-コスト管理監視)
- [12. Terraform変数](#12-terraform変数)
- [13. GitHub Actions Variables/Secrets](#13-github-actions-variablessecrets)

---

## 0. 文書情報

| 項目 | 内容 |
|---|---|
| 文書名 | リアルな複数人英会話トレーニングエージェント 設定パラメータ定義書 |
| 版数 | v0.1 |
| 作成日 | 2026-07-11 |
| 前提文書 | `docs/infra/00_OVERVIEW.md`、`docs/infra/01_ARCHITECTURE.md` |

---

## 1. リージョン・環境識別

| パラメータ | 種別 | dev例 | prd例 | 備考 |
|---|---|---|---|---|
| `GCP_PROJECT_ID` | 共通 | `real-conv-agents` | 同左 | 単一プロジェクト方針（`00_OVERVIEW.md` §4） |
| `GCP_REGION` | 共通 | `us-central1` | `us-central1` | `asia-northeast1`はGemini Live APIのProvisioned Throughput制約要検証（`00_OVERVIEW.md` §5） |
| `ENVIRONMENT` | env var | `dev` | `prd` | ログ・アプリ内分岐用 |

---

## 2. Frontend（Firebase Hosting / Vite envs）

| パラメータ | 種別 | 備考 |
|---|---|---|
| `VITE_API_BASE_URL` | build env | Cloud Run APIのrun.app URL（環境別） |
| `VITE_WS_BASE_URL` | build env | `wss://`エンドポイント |
| `VITE_FIREBASE_API_KEY` / `VITE_FIREBASE_AUTH_DOMAIN` / `VITE_FIREBASE_PROJECT_ID` / `VITE_FIREBASE_APP_ID` | build env | Firebase SDK設定（App Check用） |
| `VITE_RECAPTCHA_ENTERPRISE_SITE_KEY` | build env | 環境別（Hosting siteのドメインごとにキー登録） |
| `VITE_APP_CHECK_DEBUG_TOKEN` | local専用 | `.env.local`のみ。commit禁止 |
| `VITE_ENVIRONMENT` | build env | UI上のdev/prdバナー表示用 |
| `VITE_SESSION_MAX_DURATION_SECONDS` | build env | `600`。カウントダウンUI用 |
| `VITE_MIC_PERMISSION_HELP_URL` | build env | マイク権限エラー時の案内リンク（任意） |

---

## 3. API（Cloud Run）環境変数

| パラメータ | dev例 | prd例 | 備考 |
|---|---|---|---|
| `GCP_PROJECT_ID` / `GCP_REGION` / `ENVIRONMENT` | §1参照 | | |
| `PORT` | `8080` | `8080` | Cloud Run既定 |
| `AGENT_ENGINE_RESOURCE_NAME` | `projects/.../reasoningEngines/{dev_id}` | `.../{prd_id}` | agentデプロイ後にCI変数として注入 |
| `FIRESTORE_DATABASE_ID` | `dev` | `(default)` | マルチデータベースで分離 |
| `CORS_ALLOWED_ORIGINS` | dev Hosting URL | prd Hosting URL | |
| `AUTH_TOKEN_TTL_SECONDS` | `3600` | `3600` | password認証後の短期token |
| `STREAM_TICKET_TTL_SECONDS` | `60` | `60` | WebSocket接続用one-time ticket |
| `SESSION_MAX_DURATION_SECONDS` | `600` | `600` | MVP方針の10分上限 |
| `MAX_CONCURRENT_SESSIONS` | 小さめ（例`5`） | 審査時想定に合わせて調整 | 超過時429+Retry-After |
| `RATE_LIMIT_PER_IP_PER_MINUTE` | 厳しめ | 厳しめ | dev/prd共通で厳しめに統一（確定） |
| `CLOUD_RUN_MIN_INSTANCES` | `0` | `1`（コールドスタート回避） | deploy設定 |
| `CLOUD_RUN_MAX_INSTANCES` | 小さめ | コスト上限に応じて設定 | deploy設定 |
| `CLOUD_RUN_CONCURRENCY` | 要検証 | 同左 | WebSocket保持数に直結 |
| `CLOUD_RUN_REQUEST_TIMEOUT_SECONDS` | `3600` | `3600` | WebSocket用に長め（上限60分） |
| `APP_CHECK_ENFORCEMENT_MODE` | `monitor`（当初） | `enforce` | 段階導入 |
| `FIREBASE_PROJECT_ID` | | | App Checkトークン検証用 |
| `LOG_LEVEL` | `debug` | `info` | |

---

## 4. API向けSecret Manager格納値

| シークレット名 | 内容 | 備考 |
|---|---|---|
| `shared-auth-username` / `shared-auth-password-hash` | password認証 | 平文パスワードではなくハッシュを保存 |
| `token-signing-secret` | 短期token/stream ticket署名鍵 | 環境ごとに別値必須 |
| `x-api-bearer-token` | X API認証 | |
| `app-check-debug-token`（devのみ） | ローカル/CI用 | 本番では使わない |

---

## 5. Cloud Tasks

| パラメータ | 備考 |
|---|---|
| `TASKS_QUEUE_NAME` | 例: `topic-pack-generation` |
| `TASKS_QUEUE_LOCATION` | `GCP_REGION`と揃える |
| `TASKS_MAX_CONCURRENT_DISPATCHES` | X API/Geminiのレート制限に合わせて設定 |
| `TASKS_MAX_DISPATCHES_PER_SECOND` | 同上 |
| `TASKS_DISPATCH_DEADLINE_SECONDS` | 最大`1800`（30分上限） |
| `TASKS_INVOKER_SERVICE_ACCOUNT` | `cloud-tasks-invoker-sa` |

---

## 6. Agent Engine（ADK）

| パラメータ | 備考 |
|---|---|
| `AGENT_ENGINE_DISPLAY_NAME` | 環境ごとに命名（例: `real-conv-agent-dev`） |
| `AGENT_ENGINE_MIN_INSTANCES` / `MAX_INSTANCES` | `agent_engines.update()`のスケーリング設定 |
| `AGENT_ENGINE_SERVICE_ACCOUNT` | Firestore/Gemini/X APIへのアクセス権限を持つ専用SA |
| `LIVE_API_MODEL_NAME` | 使用するGeminiモデル名（Live対応モデル） |
| `PERSONA_VOICE_MAP` | Persona ID → voice_name の対応 |
| `SESSION_RESUMPTION_ENABLED` | `true`固定 |
| `BIDI_STREAM_TIMEOUT_SECONDS` | プラットフォーム既定は約600秒 |
| `TOPIC_PACK_GENERATION_TIMEOUT_SECONDS` | Cloud Tasksのdispatch_deadlineと整合 |
| `REVIEW_GENERATION_TIMEOUT_SECONDS` | 同期呼び出しのタイムアウト |
| `GOOGLE_SEARCH_GROUNDING_ENABLED` / `URL_CONTEXT_ENABLED` | Topic Pack Workflow用フラグ |

---

## 7. Firestore

| パラメータ | 備考 |
|---|---|
| `FIRESTORE_DATABASE_ID`（dev/prd別） | マルチデータベースで分離 |
| `FIRESTORE_TTL_HOURS` | `24`（session/review/topic_pack/display_events共通） |
| コレクション名 | `sessions` / `session_messages` / `reviews` / `topic_packs` / `display_events` / `jobs`（アプリ定数） |

---

## 8. App Check

| パラメータ | 備考 |
|---|---|
| `RECAPTCHA_ENTERPRISE_SITE_KEY`（dev/prd別） | Hosting siteドメインごとに発行 |
| `APP_CHECK_TOKEN_TTL` | 既定値のまま |
| `APP_CHECK_DEBUG_TOKEN_FROM_CI` | GitHub Actions secretsに保存 |

---

## 9. IAM / Service Account

| SA名 | 用途 |
|---|---|
| `api-sa` | Cloud Run API実行、Firestore/Secret Manager/Cloud Tasks/Agent Engine呼び出し |
| `agent-engine-sa` | Agent Engine実行、Firestore/Gemini/X API呼び出し |
| `cloud-tasks-invoker-sa` | Cloud TasksからAPI内部エンドポイントを呼ぶ専用 |
| `github-actions-deploy-sa` | frontend/api/agent/terraformのデプロイ用 |
| `terraform-sa` | Terraform実行用（bootstrap含む） |

---

## 10. Workload Identity Federation / Artifact Registry

| パラメータ | 備考 |
|---|---|
| `WIF_POOL_ID` / `WIF_PROVIDER_ID` | bootstrap時に作成 |
| `WIF_ATTRIBUTE_CONDITION` | 対象リポジトリに限定するcondition |
| `ARTIFACT_REGISTRY_REPO_NAME` / `ARTIFACT_REGISTRY_LOCATION` | コンテナイメージ格納先 |
| `IMAGE_TAG` | git SHAベース |

---

## 11. コスト管理・監視

| パラメータ | 備考 |
|---|---|
| `BILLING_BUDGET_AMOUNT` | 日次または月次上限額 |
| `BILLING_ALERT_THRESHOLDS` | 例: 50% / 80% / 100% |
| `MONITORING_NOTIFICATION_CHANNEL` | 通知先（メール等） |
| `LOG_RETENTION_DAYS` | Cloud Loggingの保持期間 |

---

## 12. Terraform変数

`environments/{dev,prod}/terraform.tfvars`に、インフラリソースの形を決める値（`project_id`, `region`, `environment`, Cloud Run scaling系, Firestoreデータベース設定, Cloud Tasksキュー設定, Secret Managerのシークレット名一覧, 予算アラート設定等）を集約する。アプリロジックに関わる値（`SESSION_MAX_DURATION_SECONDS`等）はTerraformからCloud Runの環境変数として注入する。

---

## 13. GitHub Actions Variables/Secrets

| 名前 | 種別 | 備考 |
|---|---|---|
| `GCP_PROJECT_ID` | Variable | 単一プロジェクト方針のためdev/prod共通の1値 |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Variable | WIFのフルリソースパス（`infra/bootstrap/`の出力） |
| `GCP_TERRAFORM_SERVICE_ACCOUNT_EMAIL` | Variable | `terraform-sa`のメールアドレス（`infra/bootstrap/`の出力）。ci.yml/cd.ymlのterraform plan/apply認証に使用 |
| `GCP_DEPLOY_SERVICE_ACCOUNT_EMAIL` | Variable | `github-actions-deploy-sa`のメールアドレス（`infra/bootstrap/`の出力）。frontend/api/agentデプロイの認証に使用 |
| `APP_CHECK_DEBUG_TOKEN_FROM_CI` | Secret | mock E2EやCIでのApp Check通過用 |
| `FIREBASE_PROJECT_ID` | Variable | |

### 13.1 terraform.tfvarsとCIの関係

`terraform.tfvars`は`.gitignore`で除外しローカル専用とする（`*.tfvars.example`のみcommitする）。CIはこの値をファイルではなく`TF_VAR_<変数名>`環境変数で渡す。

| Terraform変数 | CI側の環境変数 | 値の由来 |
|---|---|---|
| `project_id` | `TF_VAR_project_id` | `vars.GCP_PROJECT_ID` |
| `github_actions_deploy_sa_email` | `TF_VAR_github_actions_deploy_sa_email` | `vars.GCP_DEPLOY_SERVICE_ACCOUNT_EMAIL` |

その他の変数（`region`、`cloud_run_min_instances`等）は各`variables.tf`にdefaultを設定済みのため、CI・ローカルとも明示的な値指定は必須ではない。
