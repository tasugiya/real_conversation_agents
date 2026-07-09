# リアルな複数人英会話トレーニングエージェント パラメータ定義書

## 目次

- [0. 文書情報](#0-文書情報)
- [1. 本書の目的](#1-本書の目的)
- [2. 命名規則](#2-命名規則)
- [3. GCPプロジェクト](#3-gcpプロジェクト)
- [4. リージョン](#4-リージョン)
- [5. Cloud Runサービス](#5-cloud-runサービス)
- [6. Vertex AI Agent Engine](#6-vertex-ai-agent-engine)
- [7. Service Account](#7-service-account)
- [8. Firestore](#8-firestore)
- [9. Secret Manager](#9-secret-manager)
- [10. 環境変数](#10-環境変数)
- [11. Terraform variables](#11-terraform-variables)
- [12. 未決定事項](#12-未決定事項)

---

## 0. 文書情報

| 項目 | 内容 |
|---|---|
| 文書名 | リアルな複数人英会話トレーニングエージェント パラメータ定義書 |
| 版数 | v0.1 |
| 作成日 | 2026-07-09 |
| 関連文書 | `docs/infra/01_ARCHITECTURE.md`, `docs/infra/03_SECURITY.md`, `docs/infra/04_DEPLOY.md` |
| 位置づけ | `01_ARCHITECTURE.md`で決定した構成の、具体的な命名・パラメータを定義する |

**本書時点では、実際のGCPプロジェクトID・リージョン等の値は未確定である。** 本書は命名規則とプレースホルダーを定義し、値が確定次第「12. 未決定事項」を解消していく形で更新する。

---

## 1. 本書の目的

`01_ARCHITECTURE.md`が「何を・どう繋ぐか」を定義するのに対し、本書は「実際に何と名付けるか」を定義する。Terraform実装、CI/CDパイプライン、手動セットアップ手順で、この命名規則を一貫して使用する。

---

## 2. 命名規則

### 2.1 基本パターン

```text
{project-prefix}-{component}-{env}
```

| 要素 | 内容 | 例 |
|---|---|---|
| `project-prefix` | プロジェクト共通の短縮名 | `real-conv` （仮。確定させる） |
| `component` | コンポーネント種別 | `api`, `fe`, `agent` 等 |
| `env` | 環境 | `dev`, `prd`（stg導入時は`stg`も追加） |

環境名は要件定義・基本設計・CONTRIBUTION.mdとの用語統一のため、**`prod`ではなく`prd`** を正式表記とする（既存ドキュメントに`prod`表記が残っている箇所は今後統一する。§12参照）。

### 2.2 リソース種別ごとの接頭辞

| リソース種別 | 接頭辞/パターン |
|---|---|
| Cloud Run service | `{project-prefix}-api-{env}` |
| Service Account | `{component}-sa`（環境はプロジェクト分離しないため付与しない。§3参照） |
| Secret Manager secret | `{component}-{secret-name}`（例: `api-shared-password`） |
| Firestore collection | 複数形・snake_case（例: `sessions`, `utterances`, `grammar_feedbacks`） |
| Cloud Armor security policy | `{project-prefix}-armor-{env}` |
| Workload Identity Pool | `{project-prefix}-github-pool` |

---

## 3. GCPプロジェクト

| 環境 | GCPプロジェクトID | 状態 |
|---|---|---|
| dev | `TBD` | 未確定 |
| prd | `TBD` | 未確定 |
| stg | （未使用。導入時に確定） | 未着手 |

`01_ARCHITECTURE.md` TBD-INF-010の結論に基づき、**dev/prdは単一プロジェクト＋リソース名サフィックスで開始**する方針。つまり上記2行は同一プロジェクトID（`TBD`）になる想定。プロジェクト分離が必要になった場合はここを更新する。

---

## 4. リージョン

| 用途 | リージョン | 状態 |
|---|---|---|
| Cloud Run（API） | `TBD`（例: `asia-northeast1`想定だが、Agent Engine/Live APIの対応リージョンに合わせて再確認要） | 未確定 |
| Vertex AI Agent Engine / Gemini Live API | `TBD` | 未確定（TBD-INF-011、要調査） |
| Firestore | Cloud Run/Agent Engineと同一リージョンに揃える | 未確定 |

**音声のレイテンシに直結するため、Agent Engine + Live API bidi streamingが利用可能なリージョンを先に確定し、他リソースをそれに合わせる順序で決定する。**

---

## 5. Cloud Runサービス

| 環境 | サービス名 | ingress |
|---|---|---|
| dev | `{project-prefix}-api-dev` | 標準（public） |
| prd | `{project-prefix}-api-prd` | `internal-and-cloud-load-balancing` |

Frontendは Firebase Hosting（静的ホスティング）のため、Cloud Runサービスとしては存在しない。

---

## 6. Vertex AI Agent Engine

| 環境 | Reasoning Engine 表示名（案） | 状態 |
|---|---|---|
| dev | `{project-prefix}-agent-dev` | 未作成 |
| prd | `{project-prefix}-agent-prd` | 未作成 |

デプロイ経路（GCSステージングバケット名等）は`04_DEPLOY.md`で定義する。

---

## 7. Service Account

`01_ARCHITECTURE.md` §11と対応。

| Service Account ID（案） | 用途 |
|---|---|
| `api-sa` | Cloud Run API実行ID |
| `agent-engine-sa` | Vertex AI Agent Engine実行ID |
| `github-actions-deploy-sa` | GitHub Actions deploy用 |
| `terraform-sa` | Terraform実行用 |
| `monitoring-sa` | 監視・通知連携用（必要になれば） |

権限（ロールバインディング）の詳細は`03_SECURITY.md`で定義する。

---

## 8. Firestore

| 項目 | 値 |
|---|---|
| モード | Native mode |
| データベースID | `(default)`を利用するか専用DBを作るかTBD |
| TTLフィールド名 | `expires_at`（統一） |

コレクション名・フィールド定義の詳細は`docs/backend/03_DATA_DESIGN.md`（別途執筆）で定義する。

---

## 9. Secret Manager

| Secret名（案） | 内容 | 参照元 |
|---|---|---|
| `api-shared-password` | password認証用の共有パスワード | `api-sa` |
| `api-session-signing-key` | session token（JWT等）署名鍵 | `api-sa` |
| `gemini-api-key` または Vertex AI関連設定 | Gemini / Vertex AI認証情報 | `api-sa`, `agent-engine-sa` |
| `x-api-token` | X APIトークン | `agent-engine-sa` |

---

## 10. 環境変数

`.env.example`（リポジトリroot）との整合を取る。値は入れず、キー名のみここでも一覧化する。

| 変数名 | 用途 | 対象 |
|---|---|---|
| `GCP_PROJECT_ID` | GCPプロジェクトID | API, Agent Engine |
| `GCP_REGION` | リージョン | API, Agent Engine |
| `ENVIRONMENT` | `dev` / `prd` / `stg` | API |
| `FIRESTORE_DATABASE_ID` | Firestoreデータベース識別子 | API |
| `AGENT_ENGINE_RESOURCE_NAME` | 呼び出し先Agent EngineのリソースID | API |
| `CORS_ALLOWED_ORIGINS` | 許可するFrontend origin（devは`http://localhost:*`を含む） | API |

---

## 11. Terraform variables

`infra/terraform/environments/{env}/terraform.tfvars`で定義する主要変数（値は環境ごとに異なる）。

| 変数名 | 内容 |
|---|---|
| `project_id` | GCPプロジェクトID |
| `region` | リージョン |
| `environment` | `dev` / `prd` |
| `enable_load_balancer` | prdのみ`true`（ALB/Cloud Armor/Serverless NEGを作成するかのスイッチ） |
| `api_service_name` | Cloud Runサービス名 |
| `agent_engine_display_name` | Agent Engine表示名 |

`enable_load_balancer`のようなフラグで、dev/prdの構成差分（ALB有無）をモジュール共通化しつつ切り替えられるようにする。

---

## 12. 未決定事項

| TBD ID | 内容 |
|---|---|
| TBD-PARAM-001 | GCPプロジェクトIDの確定（新規作成か、既存プロジェクトを利用するか） |
| TBD-PARAM-002 | リージョンの確定（Agent Engine / Live API対応状況の調査が前提、`01_ARCHITECTURE.md` TBD-INF-011） |
| TBD-PARAM-003 | `project-prefix`の確定（現在`real-conv`は仮称） |
| TBD-PARAM-004 | Firestoreデータベースを`(default)`にするか専用IDにするか |
| TBD-PARAM-005 | 既存ドキュメント内の`prod`表記を`prd`に統一するかどうか（表記揺れの解消） |

---

## 13. 参考資料

- `docs/infra/01_ARCHITECTURE.md`
- `.env.example`（リポジトリroot）
