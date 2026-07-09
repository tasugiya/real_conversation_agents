# docs/infra 概要

## この配下の位置づけ

`docs/infra/`は、GCP上に本システムを「どう配線するか」を扱う詳細設計書群である。API・Agentの論理設計（何を作るか）は`docs/backend/`、画面設計は`docs/frontend/`に書く。図表は`docs/asset/`に集約する。

## ファイル一覧

| ファイル | 内容 | 主な読者 |
|---|---|---|
| [`01_ARCHITECTURE.md`](./01_ARCHITECTURE.md) | 全体構成、ネットワーク境界、コンポーネント責務、環境（dev/prd）ごとの違い | 全員（最初に読む） |
| [`02_PARAMS_DEF.md`](./02_PARAMS_DEF.md) | GCPプロジェクト・リージョン・命名規則・環境変数・Terraform variables | 実装担当 |
| [`03_SECURITY.md`](./03_SECURITY.md) | IAM権限表、Organization Policy、Cloud Armor、VPC Service Controls見送り理由 | インフラ・セキュリティ担当 |
| [`04_DEPLOY.md`](./04_DEPLOY.md) | CI/CDパイプライン、Terraform適用、Agent Engineデプロイ、release手順 | 実装担当・リリース担当 |

## 全体構成の要約

- Frontend: React（Vite）+ Tailwind CSS、**Firebase Hosting**でホスト
- API: **FastAPI**（Cloud Run）。password認証を行う薄いゲートウェイで、Agentの実行はしない
- Agent: ADKで実装し、**Vertex AI Agent Engine**にデプロイ。Gemini Live APIとの双方向ストリーミング保持とセッション永続化をAgent Engineに委譲する
- DB: **Firestore**。TTLポリシーでセッションクリーンアップを自動化
- **Worker / Cloud Tasksは採用しない**。会話後フィードバック・要約はAPIからAgent Engineへの同期呼び出しで完結させる
- 環境戦略: **dev / prdから開始**し、必要ならstgを後日追加。prdはGitHub Release / tagを起点にデプロイ
- prdのみExternal Application Load Balancer + Cloud Armorを配置し、devはローカル開発を優先してCloud Run標準URLを直接公開する
- **Cloud VPNは採用しない**。IAM設定ミスへの多層防御はOrganization Policy（Domain Restricted Sharing）とCloud Run ingress制限で行う

## 読む順序の目安

1. `01_ARCHITECTURE.md`で全体像とdev/prdの違いを把握する
2. 実装に着手する際、命名やパラメータが必要になったら`02_PARAMS_DEF.md`を参照する
3. IAM権限やセキュリティ関連の意思決定を確認したい場合は`03_SECURITY.md`
4. 実際にデプロイ・リリース作業を行う際は`04_DEPLOY.md`

## 未決定事項の集約

各ファイルの「未決定事項」セクションに散らばっているTBDのうち、優先度が高いもの。

| TBD | 内容 | 詳細 |
|---|---|---|
| リージョン確定 | Agent Engine / Live API bidi streamingが使えるリージョンの調査・確定 | `01_ARCHITECTURE.md` TBD-INF-011、`02_PARAMS_DEF.md` §4 |
| GCPプロジェクトID確定 | 新規作成か既存流用か | `02_PARAMS_DEF.md` TBD-PARAM-001 |
| devのOrg Policy例外実装方法 | Cloud Run Invoker IAM check無効化 vs ポリシー例外 | `03_SECURITY.md` TBD-SEC-001 |
| Agent Engineデプロイ方式 | SDK経由 vs curlベース | `04_DEPLOY.md` TBD-DEPLOY-001 |
