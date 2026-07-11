# リアルな複数人英会話トレーニングエージェント 開発規則

## 目次

- [0. 文書情報](#0-文書情報)
- [1. 本ドキュメントの目的](#1-本ドキュメントの目的)
- [2. 開発方針](#2-開発方針)
- [3. リポジトリ構成規則](#3-リポジトリ構成規則)
- [4. ブランチ運用規則](#4-ブランチ運用規則)
- [5. 環境運用規則](#5-環境運用規則)
- [6. 開発フロー](#6-開発フロー)
- [7. Pull Request規則](#7-pull-request規則)
- [8. コーディング規則](#8-コーディング規則)
- [9. テスト規則](#9-テスト規則)
- [10. CI/CD規則](#10-cicd規則)
- [11. リリース規則](#11-リリース規則)
- [12. Secret・環境変数管理規則](#12-secret環境変数管理規則)
- [13. ログ・監視・障害対応規則](#13-ログ監視障害対応規則)
- [14. AI Agent開発規則](#14-ai-agent開発規則)
- [15. ドキュメント管理規則](#15-ドキュメント管理規則)
- [16. Issue・タスク管理規則](#16-issueタスク管理規則)
- [17. レビュー観点](#17-レビュー観点)
- [18. MVP期間中の例外方針](#18-mvp期間中の例外方針)
- [19. 未決定事項](#19-未決定事項)

---

## 0. 文書情報

| 項目   | 内容                                             |
| ---- | ---------------------------------------------- |
| 文書名  | リアルな複数人英会話トレーニングエージェント 開発規則                    |
| 版数   | v0.1                                           |
| 作成日  | 2026-07-09                                     |
| 対象   | 開発メンバー、レビュー担当、運用担当                             |
| 関連文書 | `docs/REQUIREMENTS_DEFINITION.md`, `docs/BASIC_DESIGN.md` |
| 目的   | 開発・レビュー・テスト・デプロイ・リリースに関する実務ルールを統一する            |

---

## 1. 本ドキュメントの目的

本ドキュメントは、開発作業を安全かつ再現可能に進めるための規則を定義する。

基本設計書が「システムをどう構成するか」を扱うのに対し、本ドキュメントは「チームがどう開発・検証・リリースするか」を扱う。

対象は以下である。

- ブランチ運用
- 環境運用
- Pull Request
- CI/CD
- テスト
- Secret管理
- リリース
- Agent設定の変更管理
- ドキュメント更新

---

## 2. 開発方針

### 2.1 基本方針

| ID      | 方針                                                       |
| ------- | -------------------------------------------------------- |
| DEV-001 | `main` は常にstg環境へデプロイ可能な状態を保つ。                            |
| DEV-002 | 本番相当のprod環境は、releaseブランチまたはGitHub Release / tagを起点に更新する。 |
| DEV-003 | 機能開発は原則として `feature/*` ブランチで行う。                          |
| DEV-004 | PRでは、少なくともlint、typecheck、build、必要なテストが通ることを確認する。         |
| DEV-005 | 外部APIに依存するテストはPRごとに多用せず、mockとstg実API検証を分ける。              |
| DEV-006 | prompt、persona、tool schemaもコードと同じくレビュー対象とする。             |
| DEV-007 | secretはリポジトリに含めない。                                       |
| DEV-008 | MVPでは速度を重視するが、動作再現性とデモ安定性を損なう変更は避ける。                     |

### 2.2 開発で優先すること

1. デモで安定して動くこと
2. 複数人会話体験が成立すること
3. ユーザー発話を遮らないこと
4. APIキーや会話ログを安全に扱うこと
5. 変更がレビュー可能であること
6. 失敗時に原因を追えること

---

## 3. リポジトリ構成規則

### 3.1 推奨構成

```text
real_conversation_agents/
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── COC.md
├── CHANGE_LOG.md
├── .env.example
├── .dockerignore
├── .gitignore
├── docs/
│   ├── README.md
│   ├── BASE_IDEA.md
│   ├── REQUIREMENTS_DEFINITION.md
│   ├── BASIC_DESIGN.md
│   ├── CONTRIBUTION.md
│   ├── DEVOPS.md
│   ├── asset/
│   │   ├── media/
│   │   └── mmd/
│   ├── frontend/          # frontend領域の詳細設計文書
│   ├── backend/           # api / agent領域の詳細設計文書
│   ├── infra/             # インフラ領域の詳細設計文書
│   └── decisions/         # ADR（未作成。今後追加）
├── frontend/               # 未作成。今後の実装で追加する → Firebase Hosting
│   ├── README.md
│   ├── src/
│   └── tests/
├── api/                    # 未作成。今後の実装で追加する → Cloud Run（単一サービス）
│   ├── README.md
│   ├── src/
│   │   ├── routes/
│   │   ├── middleware/
│   │   ├── services/
│   │   └── tasks/          # Cloud Tasksが叩く内部handler。別Workerサービスは作らない
│   └── tests/
├── agent/                  # 未作成。今後の実装で追加する → Vertex AI Agent Engine（独立デプロイ対象）
│   ├── README.md
│   ├── src/
│   ├── deploy.py
│   └── tests/
├── packages/               # 未作成。今後の実装で追加する
│   └── shared-schemas/     # WebSocket event / Topic Pack / Review の JSON Schema
├── infra/                  # 未作成（root直下）。今後の実装で追加する
│   ├── README.md
│   ├── bootstrap/          # 最初に人力で1回だけ実行（state用GCSバケット・WIF・SA作成）
│   └── terraform/
│       └── environments/
├── .github/                # 未作成。今後の実装で追加する
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
└── .pre-commit-config.yaml # 未作成。今後の実装で追加する
```

`worker/`ディレクトリは廃止した。Cloud TasksのターゲットはCloud Run API内の内部エンドポイント（`api/src/tasks/`）であり、独立したWorker Cloud Runサービスは設けない（`docs/infra/01_ARCHITECTURE.md` §7）。Agent Engineへデプロイする本体コードは、Cloud Run APIとは別のデプロイ対象であるため`agent/`をトップレベルに新設した（`docs/infra/01_ARCHITECTURE.md` §2）。

### 3.2 配置規則

| 対象             | 配置先                                        |
| -------------- | ------------------------------------------ |
| 画面・UIコンポーネント   | `frontend/src/`                            |
| フロントのテスト       | `frontend/tests/`                          |
| API endpoint   | `api/src/routes/`                          |
| API middleware | `api/src/middleware/`                      |
| API service    | `api/src/services/`                        |
| API test       | `api/tests/`                               |
| Cloud Tasksハンドラ | `api/src/tasks/`                          |
| Agent定義        | `agent/src/`                                |
| Agent test     | `agent/tests/`                              |
| 共通スキーマ        | `packages/shared-schemas/`                 |
| Terraform（継続apply対象） | `infra/terraform/environments/`      |
| Terraform（bootstrap専用） | `infra/bootstrap/`                   |
| 設計文書           | `docs/`                                    |
| 意思決定記録         | `docs/decisions/`                          |

### 3.3 禁止事項

- secretやAPI keyをリポジトリに置かない。
- `frontend/` から直接Gemini API secretを使わない。
- `api/` と `agent/` の責務を混在させすぎない。
- 設計意図が不明な大規模変更をPRに含めない。
- 一時ファイル、ログファイル、音声ファイルを誤ってcommitしない。

---

## 4. ブランチ運用規則

### 4.1 ブランチ一覧

| ブランチ | 役割 | デプロイ先・契機 |
|---|---|---|
| `feature/*` | 機能開発・修正 | PR（デプロイなし。lint/test/build＋terraform planのみ） |
| `dev` | 開発者向け統合確認。force push可 | `dev`へのpushで、変更対象のみdev環境へ自動デプロイ |
| `main` | prd環境の基準 | `main`へのPRマージで、変更対象のみprd環境へデプロイ（GitHub Environmentの承認ゲート必須） |
| `hotfix/*` | 緊急修正 | `main`へのPR経由でprdへ反映 |
| tag / GitHub Release | prdデプロイの記録 | prdデプロイジョブの最終ステップで自動作成（デプロイのトリガーではない） |

stg環境は当面設けない（`docs/infra/00_OVERVIEW.md` §6）。`release/*`ブランチは廃止し、リリース候補確認は`main`上で行う。

### 4.2 ブランチ運用

```text
feature/* → PR → dev または main
dev       → pushで自動デプロイ（dev環境）
main      → PRマージ＋承認ゲートでデプロイ（prd環境）
main上のprdデプロイ完了時 → tag / GitHub Releaseを自動生成（記録用）
```

詳細なパイプライン構成・パスフィルタは`docs/infra/04_DEPLOY.md`を正とする。

### 4.3 ブランチ命名

| 種別 | 例 |
|---|---|
| 機能追加 | `feature/conversation-ui` |
| API追加 | `feature/session-api` |
| Agent変更 | `feature/grammar-feedback-agent` |
| バグ修正 | `fix/mic-permission-error` |
| ドキュメント | `docs/basic-design-update` |
| インフラ | `infra/cloud-run-worker` |
| 緊急修正 | `hotfix/prod-connection-error` |

---

## 5. 環境運用規則

### 5.1 環境一覧

| 環境 | 用途 | 接続先 |
|---|---|---|
| local | 手元開発 | mock API / dev API |
| preview | PRごとの確認 | mock API / dev API |
| dev | 開発者向け統合確認 | dev API / dev DB |
| stg | リリース前確認 | stg API / stg DB |
| prod | デモ・本番相当 | prod API / prod DB |

### 5.2 API環境

| 環境 | Cloud Run service例 |
|---|---|
| dev | `real-conversation-api-dev` |
| stg | `real-conversation-api-stg` |
| prod | `real-conversation-api-prod` |

### 5.3 Frontend環境

| 環境 | 用途 |
|---|---|
| preview | PRごとのUI確認 |
| dev | api-devと接続した統合確認 |
| stg | api-stgと接続したリリース前確認 |
| prod | デモ・本番相当 |

### 5.4 Worker環境

| 環境 | Cloud Run service例 |
|---|---|
| dev | `real-conversation-worker-dev` |
| stg | `real-conversation-worker-stg` |
| prod | `real-conversation-worker-prod` |

---

## 6. 開発フロー

### 6.1 通常開発フロー

1. Issueを作成する。
2. `feature/*` ブランチを作成する。
3. 実装する。
4. localで必要なテストを実行する。
5. PRを作成する。
6. CI結果を確認する。
7. レビューを受ける。
8. 必要に応じてpreview / devで確認する。
9. mainへmergeする。
10. stgで統合確認する。
11. releaseへ進める。

### 6.2 API変更時の追加確認

APIのrequest / responseを変更する場合は、以下を確認する。

- frontendのAPI clientへの影響
- workerへの影響
- テストの更新
- `docs/backend/` 配下のAPI設計文書の更新
- backward compatibilityが必要かどうか
- stgでの疎通確認

### 6.3 Agent変更時の追加確認

Agentのprompt、persona、tool schema、model設定を変更する場合は、以下を確認する。

- 複数人会話の自然さ
- 英語で応答するか
- ユーザー発話を遮らないか
- 文法フィードバックが過度に断定的でないか
- token使用量・latencyが増えすぎていないか
- Agent behavior testが通るか

---

## 7. Pull Request規則

### 7.1 PR粒度

PRは、レビュー可能な単位に分割する。

望ましい単位：

- 1機能
- 1バグ修正
- 1画面
- 1API endpoint群
- 1Agent変更
- 1インフラ変更

避けるべきPR：

- frontend、api、worker、infra、docsをすべて含む巨大PR
- 目的が複数あるPR
- 動作確認が困難なPR
- 設計変更と実装変更が説明なく混在するPR

### 7.2 PRテンプレート

PRには以下を記載する。

```md
## 概要

## 変更内容

## 確認したこと
- [ ] lint
- [ ] typecheck
- [ ] unit test
- [ ] build
- [ ] mock E2E
- [ ] dev環境確認
- [ ] stg環境確認

## 影響範囲
- [ ] frontend
- [ ] api
- [ ] worker
- [ ] infra
- [ ] agent
- [ ] docs

## 外部API影響
- [ ] Gemini
- [ ] X API
- [ ] Cloud Tasks
- [ ] なし

## スクリーンショット / 動作確認メモ

## 関連Issue
```

### 7.3 Merge条件

原則として以下を満たすこと。

- CIが通っている。
- 重大なlint/type errorがない。
- 変更内容に対する最低限のテストがある。
- 影響するドキュメントが更新されている。
- secretを含んでいない。
- レビューで承認されている。

---

## 8. コーディング規則

### 8.1 共通

- 型を明示できる箇所は明示する。
- エラーを握りつぶさない。
- ログにはrequest_id / session_id / job_id等を含める。
- secretや個人情報をログ出力しない。
- 外部API呼び出しはservice層に閉じ込める。
- UIから外部AI APIを直接叩かない。

### 8.2 Frontend

- UIコンポーネントは責務を小さく分ける。
- API呼び出しはclient / hooksに分離する。
- 会話状態は型付きで扱う。
- マイク権限、接続中、エラー、再接続中などの状態を明示的に扱う。
- 吹き出し表示ではspeaker_id / speaker_nameを必ず扱う。

### 8.3 API

- endpoint層、service層、repository層を分ける。
- Gemini Live API連携は専用serviceに閉じ込める。
- Cloud Tasks投入は専用serviceに閉じ込める。
- 共通エラーハンドラを用意する。
- 外部API timeoutを設定する。
- request validationを行う。

### 8.4 Worker

- jobはidempotentに実装する。
- retryされても二重に重大な副作用が起きないようにする。
- job開始・成功・失敗をログに出す。
- 429 / timeout / temporary errorを区別する。
- 長時間処理はstatusを更新する。

### 8.5 Infra

- Terraformの変更はPRでレビューする。
- 環境ごとの差分を明示する。
- IAMは最小権限を基本とする。
- 手動作成したGCPリソースはdocsに記録し、可能な範囲でIaC化する。

---

## 9. テスト規則

### 9.1 テスト分類

| テスト | 対象 | 実行タイミング |
|---|---|---|
| lint | frontend / api / worker | local / PR CI |
| typecheck | frontend / api | local / PR CI |
| unit test | frontend / api / worker | local / PR CI |
| component test | frontend | local / PR CI |
| mock E2E | frontend中心 | PR CI |
| API integration test | api / worker | dev / stg |
| real E2E | frontend + api + worker + Gemini | stg |
| smoke test | prod | release後 |
| Agent behavior test | Agent設定 | PR CI / stg |

### 9.2 PRで必須とするテスト

MVP初期では、以下を必須ラインとする。

| 対象 | 必須 |
|---|---|
| frontend | lint、typecheck、build |
| api | lint、unit test、import check |
| worker | lint、unit test |
| docs | markdownの構文確認は任意 |
| infra | terraform fmt、terraform validate |

プロジェクトが安定したら、mock E2EとAgent behavior testをPR必須へ引き上げる。

### 9.3 フロントエンドテスト

PRでは、外部AI APIに接続しないmock E2Eを基本とする。

確認するフロー：

1. Setup画面が表示される。
2. 会話人数を選択できる。
3. トピックを選択または入力できる。
4. Conversation画面に遷移できる。
5. mock AI発話が吹き出し表示される。
6. mockユーザー発話が表示される。
7. 会話終了後Review画面に遷移できる。
8. mockフィードバックが表示される。

### 9.4 stgでの実API統合テスト

stgでは、実APIを用いて以下を確認する。

- マイク許可
- 音声入力
- Gemini Live API応答
- AI発話テキスト表示
- AI音声再生
- 会話ログ保存
- 会話終了
- フィードバック生成
- Review表示
- X API失敗時のfallback

### 9.5 Agent behavior test

Agent変更時は、少なくとも以下を確認する。

| ケース | 期待 |
|---|---|
| ユーザーが英語で挨拶する | AIが英語で自然に返す |
| 3人会話設定 | 2人以上のAI話者が登場する |
| ユーザーの文法ミス | 改善案が生成される |
| 難しいトピック | 英会話練習向けに簡単化される |
| 不適切な話題 | 安全な話題へ誘導する |
| AI発話が長すぎる | 短く会話的な応答になる |

---

## 10. CI/CD規則

### 10.1 CI方針

CIは、変更対象に応じて必要なjobを実行する。

| 変更対象 | 実行するCI |
|---|---|
| `frontend/**` | frontend lint / typecheck / build / test |
| `api/**` | api lint / test |
| `worker/**` | worker lint / test |
| `infra/**` | terraform fmt / validate |
| `docs/**` | docs check、必要に応じてリンク確認 |
| `packages/**` | 依存するfrontend / api / workerのテスト |

### 10.2 CD方針

| ブランチ / イベント | デプロイ先 |
|---|---|
| PR作成 | preview |
| `dev` push | dev |
| `main` push | stg |
| `release/*` | prod候補 |
| GitHub Release / tag | prod |

### 10.3 手動承認

prodへのデプロイは、原則として手動承認を挟む。

prodデプロイ前に確認すること：

- stgで主要フローが動作する。
- 重大エラーがない。
- APIキー・環境変数が正しい。
- DB migrationまたはschema変更の影響を確認した。
- fallbackモードが動く。
- デモ用固定トピックが利用可能である。

---

## 11. リリース規則

### 11.1 リリース単位

releaseはGitHub Releaseまたはtagで管理する。

tag例：

```text
v0.1.0
v0.2.0
v1.0.0
```

### 11.2 リリース手順

1. mainがstgで安定していることを確認する。
2. `release/vX.Y.Z` ブランチを作成する。
3. release candidateをstgまたはprod候補環境で確認する。
4. 重大な修正があればreleaseブランチへ反映する。
5. GitHub Releaseを作成する。
6. prodへデプロイする。
7. smoke testを実施する。
8. release noteを記録する。

### 11.3 リリースノート項目

```md
## Summary

## Added

## Changed

## Fixed

## Known Issues

## Verification
- [ ] stg E2E
- [ ] prod smoke test
```

### 11.4 rollback方針

prodで重大障害が発生した場合は、直前の安定revisionへrollbackする。rollback後、原因調査用のIssueを作成する。

---

## 12. Secret・環境変数管理規則

### 12.1 Secret管理

以下は絶対にGitにcommitしない。

- Gemini API key
- X API key / token
- GCP service account key
- OAuth secret
- DB password
- private key
- webhook secret

### 12.2 管理方法

| 対象 | 管理方法 |
|---|---|
| 本番secret | Secret Manager |
| dev / stg secret | Secret Managerの環境別secret |
| local開発用 | `.env.local` |
| サンプル | `.env.example` |

### 12.3 `.env.example`

`.env.example` には値を入れず、必要なキー名だけを記載する。

```env
GCP_PROJECT_ID=
GEMINI_API_KEY=
X_API_KEY=
DATABASE_URL=
```

### 12.4 ログ出力禁止

ログに以下を出力してはならない。

- API key
- access token
- refresh token
- service account key
- 音声データ本体
- 不要な個人情報
- 長すぎる会話全文

---

## 13. ログ・監視・障害対応規則

### 13.1 ログに含めるID

可能な限り以下を含める。

- `request_id`
- `session_id`
- `job_id`
- `speaker_id`
- `agent_name`
- `environment`
- `model_name`
- `error_type`

### 13.2 監視対象

| 対象 | 指標 |
|---|---|
| API | 5xx率、latency、request数 |
| Realtime | 接続数、切断数、応答開始遅延 |
| Gemini | 429、timeout、latency、token usage |
| Worker | job成功率、失敗率、retry数 |
| Frontend | 主要画面表示、エラーイベント |
| Cost | セッションあたり推定コスト |

### 13.3 障害対応

障害発生時は、以下の順で対応する。

1. 影響範囲を確認する。
2. stg / prodどちらの問題か確認する。
3. Cloud Loggingでエラーを確認する。
4. 外部API障害・rate limitの有無を確認する。
5. fallback可能な機能はfallbackする。
6. 必要に応じて直前revisionへrollbackする。
7. Issueに原因・対応・再発防止を記録する。

---

## 14. AI Agent開発規則

### 14.1 管理対象

以下はコードと同じくレビュー対象とする。

- system prompt
- persona prompt
- conversation policy
- grammar feedback prompt
- topic generation prompt
- tool schema
- model名
- temperature
- max output tokens
- safety方針
- Agent出力schema

### 14.2 Agent設定の配置

Agent EngineはCloud Run APIとは別のデプロイ対象であるため、`api/src/agents/`ではなくトップレベルの`agent/`配下に配置する（`docs/infra/01_ARCHITECTURE.md` §2）。

推奨配置：

```text
agent/src/
├── director/           # Conversation Director
├── personas/            # Persona Agent群
├── topic_pack_workflow/ # Topic Pack Workflow
├── scoring/              # Scoring Observer
├── hint/                  # Hint Generator
└── review/                # Review Agent

docs/
└── backend/
    └── 03_AGENT_ORCHESTRATION_DRAFT.md
```

promptをYAML等で外出しする場合：

```text
agent/src/prompts/
├── director.yaml
├── personas/
│   ├── alice.yaml
│   ├── ben.yaml
│   └── chloe.yaml
├── topic_pack_workflow.yaml
└── review.yaml
```

### 14.3 Agent変更時の必須確認

- 英語で応答する。
- 複数人会話感がある。
- ユーザーに発話機会を与える。
- AIが長く話しすぎない。
- 文法フィードバックが断定的すぎない。
- 不適切な話題を避ける。
- tool callの失敗時に壊れない。
- token使用量が極端に増えていない。

### 14.4 prompt変更PRの記載事項

promptやpersonaを変更するPRでは、以下を記載する。

```md
## Agent変更内容

## 変更理由

## 期待する振る舞い

## 確認した会話例

## 既知の懸念
```

---

## 15. ドキュメント管理規則

### 15.1 docs一覧

| 文書 | 内容 |
|---|---|
| `docs/BASE_IDEA.md` | ベースアイデア |
| `docs/REQUIREMENTS_DEFINITION.md` | 要件定義 |
| `docs/BASIC_DESIGN.md` | 基本設計 |
| `docs/CONTRIBUTION.md` | 開発規則（本書） |
| `docs/DEVOPS.md` | DevOps詳細 |
| `docs/backend/`（例: `api-design.md`、`agent-design.md`、`data-design.md`） | API・Worker・Agentの詳細設計 |
| `docs/frontend/` | フロントエンド詳細設計 |
| `docs/infra/`（例: `infra-design.md`） | インフラ詳細設計 |
| `docs/asset/`（`media/`、`mmd/`） | 図表・画像等 |
| `docs/decisions/ADR-*.md` | 重要な意思決定記録（未作成。今後追加） |

### 15.2 ADR

重要な技術選定・設計判断はADRとして残す。

ADR例：

- `ADR-001-frontend-framework.md`
- `ADR-002-backend-framework.md`
- `ADR-003-gemini-live-api-connection.md`
- `ADR-004-database-selection.md`
- `ADR-005-worker-separation.md`

ADRフォーマット：

```md
# ADR-XXX: タイトル

## Status
Proposed / Accepted / Superseded

## Context

## Decision

## Reason

## Consequences
```

### 15.3 ドキュメント更新ルール

以下に該当する場合、関連docsを更新する。

- API仕様が変わった。
- DB構造が変わった。
- Agent構成が変わった。
- インフラ構成が変わった。
- 開発フローが変わった。
- release手順が変わった。
- セキュリティ方針が変わった。

---

## 16. Issue・タスク管理規則

### 16.1 Issue種別

| 種別 | 例 |
|---|---|
| feature | 会話画面の実装 |
| bug | マイク権限エラー時に画面が固まる |
| docs | 基本設計書の更新 |
| infra | Cloud Run dev環境作成 |
| agent | Persona Agentのprompt修正 |
| test | mock E2E追加 |
| chore | lint設定更新 |

### 16.2 Issueテンプレート

実装は`.github/ISSUE_TEMPLATE/`配下のGitHub Issue Forms（YAML）で行う（`docs/DEVOPS.md` チケット節）。種別ごとに`1-feature.yml`〜`5-agent.yml`を用意し、以下の内容を項目として持たせる。

```md
## 目的

## 背景

## やること
- [ ]

## 完了条件
- [ ]

## 関連文書 / 関連PR
```

### 16.3 完了条件

Issueは、以下を満たしたときに完了とする。

- 実装がmergeされている。
- 必要なテストが通っている。
- 必要なドキュメントが更新されている。
- devまたはstgで動作確認済みである。
- 既知の残課題がIssue化されている。

---

## 17. レビュー観点

### 17.1 共通レビュー観点

- 要件に合っているか。
- 変更範囲が適切か。
- 既存機能を壊していないか。
- エラー処理があるか。
- テストがあるか。
- ログが適切か。
- secretを含んでいないか。
- ドキュメント更新が必要ないか。

### 17.2 Frontendレビュー観点

- ユーザーが迷わないUIか。
- マイク権限・接続中・エラー状態が表示されるか。
- speaker表示が正しいか。
- mockでテストできる設計か。
- API clientが適切に分離されているか。

### 17.3 APIレビュー観点

- endpointの責務が明確か。
- validationがあるか。
- 外部API失敗時の処理があるか。
- session_id / request_idが追跡可能か。
- リアルタイム処理と後処理が混ざりすぎていないか。

### 17.4 Workerレビュー観点

- jobがidempotentか。
- retry時に二重実行問題がないか。
- 失敗時のstatus更新があるか。
- 429 / timeoutを区別しているか。
- 長時間処理をリアルタイムAPI側に置いていないか。

### 17.5 Agentレビュー観点

- 複数人会話感があるか。
- AIが話しすぎないか。
- ユーザーに発話機会を与えるか。
- 文法フィードバックが自然か。
- 不適切な話題への安全化があるか。
- prompt変更の意図が明確か。

---

## 18. MVP期間中の例外方針

MVP期間中は、開発速度を優先して一部ルールを簡略化してよい。ただし、以下は例外なく守る。

### 18.1 必ず守ること

- secretをcommitしない。
- mainが完全に壊れた状態を放置しない。
- prodデプロイ前にstgで主要フローを確認する。
- Gemini / X API失敗時にアプリ全体が落ちないようにする。
- 音声データを無断で永続保存しない。
- Agent変更の意図をPRに書く。

### 18.2 MVPでは簡略化してよいこと

- Workerを最初から完全分離しない。
- Terraform化が間に合わないリソースを一時的に手動作成する。
- preview環境を最初から全PRで用意しない。
- Agent behavior testを最初は手動確認にする。
- stg / prodの完全分離を段階的に行う。

### 18.3 簡略化した場合の条件

簡略化した場合は、以下を行う。

- `docs/decisions/` に理由を残す。
- 後で対応するIssueを作る。
- デモ安定性に関わるものは優先的に解消する。

---

## 19. 未決定事項

### 19.1 解決済み

| TBD ID | 結論 |
|---|---|
| ~~TBD-DEV-001~~ | CIツールはGitHub Actionsに確定 |
| ~~TBD-DEV-003~~ | frontendのホスティング先はFirebase Hostingに確定 |
| ~~TBD-DEV-004~~ | APIの実装言語はFastAPI（Python）に確定 |
| ~~TBD-DEV-006~~ | Agent behavior testは`agent/**`変更時のみ自動実行することに確定（`docs/infra/04_DEPLOY.md` §1） |
| ~~TBD-DEV-007~~ | Terraform管理範囲は継続apply対象（`infra/terraform/environments/`）とbootstrap専用（`infra/bootstrap/`）に分離することで確定 |

### 19.2 未決定事項

| TBD ID      | 未決定事項                      | 備考                                         |
| ----------- | -------------------------- | ------------------------------------------ |
| TBD-DEV-002 | preview環境をPRごとに自動作成するか     | MVP初期は任意。mock E2Eで代替できるか要検討 |
| TBD-DEV-005 | test framework             | frontendはVitest / Playwright候補             |
| TBD-DEV-008 | prd承認ゲートの承認者               | GitHub Environmentのrequired reviewersに誰を設定するか、チーム内で決定 |
