# リアルな複数人英会話トレーニングエージェント インフラ概要

## 目次

- [0. 文書情報](#0-文書情報)
- [1. 本書の目的・対象読者](#1-本書の目的対象読者)
- [2. 関連文書](#2-関連文書)
- [3. インフラ設計の基本方針](#3-インフラ設計の基本方針)
- [4. プロジェクト構成方針](#4-プロジェクト構成方針)
- [5. リージョン方針](#5-リージョン方針)
- [6. 環境一覧](#6-環境一覧)
- [7. 未決定事項](#7-未決定事項)

---

## 0. 文書情報

| 項目 | 内容 |
|---|---|
| 文書名 | リアルな複数人英会話トレーニングエージェント インフラ概要 |
| 版数 | v0.2 |
| 作成日 | 2026-07-11 |
| 前提文書 | `docs/BASIC_DESIGN.md`、`docs/backend/01_USER_EXPERIENCE_DRAFT.md`〜`03_AGENT_ORCHESTRATION_DRAFT.md` |
| 位置づけ | インフラ設計（`docs/infra/`配下）全体の入口。詳細な構成・パラメータ・セキュリティ・デプロイ手順は`01_ARCHITECTURE.md`〜`04_DEPLOY.md`を正とする |
| 更新方針 | `_internal/real_conversation_agents_infra_architecture.md`にあったWorker/Cloud Tasks常時稼働/ALB/API Gateway/Cloud Armor前提の旧草案は、本ドキュメント群の内容に置き換えられている。旧草案は参照しないこと |

---

## 1. 本書の目的・対象読者

本書は、GCP上でこのシステムを構築・運用するためのインフラ方針の全体像を示す。詳細な構成図、設定パラメータ、セキュリティ設計、CI/CD・デプロイ手順は、それぞれ`01_ARCHITECTURE.md`〜`04_DEPLOY.md`に譲る。

対象読者は、開発メンバー、インフラ担当、セキュリティ設計担当である。

本書が扱わない内容は以下の通り。

- 個別コンポーネントの詳細構成（→ `01_ARCHITECTURE.md`）
- 環境変数・Secret一覧（→ `02_PARAMS_DEF.md`）
- 認証・認可・IAMの詳細（→ `03_SECURITY.md`）
- CI/CDパイプライン、Terraform運用手順（→ `04_DEPLOY.md`）
- ブランチ運用・PR規則・テスト規則などの開発プロセス（→ `docs/CONTRIBUTION.md`、`docs/DEVOPS.md`）

---

## 2. 関連文書

| 文書 | 内容 |
|---|---|
| `docs/infra/01_ARCHITECTURE.md` | 全体構成図、コンポーネント別設計、採用しなかった構成とその理由 |
| `docs/infra/02_PARAMS_DEF.md` | 環境変数・Secret・Terraform変数の一覧 |
| `docs/infra/03_SECURITY.md` | 認証・認可・IAM・レート制限・データ保護 |
| `docs/infra/04_DEPLOY.md` | CI/CDパイプライン、Terraform bootstrap、リリース・ロールバック |
| `docs/DEVOPS.md` | テスト戦略、pre-commit、ドキュメント管理、チケット運用、分野別機能追加手順 |
| `docs/CONTRIBUTION.md` | ブランチ運用、PR規則、コーディング規則 |

---

## 3. インフラ設計の基本方針

| ID | 方針 | 説明 |
|---|---|---|
| INF-001 | 独自ドメインを取得しない | Firebase Hosting・Cloud Runの標準ドメイン（Google管理TLS込み）で運用する。ALBのGoogle管理SSL証明書はドメイン所有が前提のため、ALBは採用しない |
| INF-002 | 公開入口をアプリ層の認証に寄せる | Cloud Armor・API Gatewayを採用しない代わりに、Firebase App Check・password認証・アプリ層rate limitで防御する |
| INF-003 | Agent実行はマネージドサービスに委譲する | セッション状態の保持をVertex AI Agent Engineに任せ、Redis等の自前セッションストアを持たない |
| INF-004 | リアルタイム会話経路はCloud Runが中継する | フロントエンドからAgent Engineへの直接接続は行わない（認証方式・秘密情報保護の理由。詳細は`01_ARCHITECTURE.md` §7） |
| INF-005 | 会話本体と非同期処理を分離する | X API呼び出し・Topic Pack生成はCloud Tasks経由の非同期処理とし、会話のリアルタイム経路とは独立させる |
| INF-006 | SecretはSecret Managerで一元管理する | APIキー・署名鍵・password等をリポジトリやフロントエンドに置かない |
| INF-007 | CI/CDはkeyless認証を用いる | GitHub ActionsからGCPへはWorkload Identity Federationを利用し、長期Service Account Keyを持たない |
| INF-008 | 過剰なネットワーク境界化を避ける | Organizationが存在しないためVPC Service Controlsは採用できない。VPCも現時点で対象リソースが無いため導入しない |
| INF-009 | コスト濫用を防ぐ | Cloud Run同時実行数・Cloud Tasksキューのレート制御・Cloud Billing予算アラートの多層で防御する |

---

## 4. プロジェクト構成方針

- GCPプロジェクトは**単一プロジェクト**とする。Organization配下ではない個人プロジェクトのため、複数プロジェクトに分割するとIAM・課金の紐付けを手動で管理するコストが増える。
- dev/prdの分離は、単一プロジェクト内でのリソース名サフィックス（例: `real-conv-api-dev` / `real-conv-api-prd`）と、**Firestoreのマルチデータベース機能**（1プロジェクト内で複数の名前付きデータベースを持てる。2024年からGA）による論理分離で行う。
- Organizationが存在しないため、VPC Service Controlsは技術的に選択肢から除外する（サービス境界はOrganizationレベルのリソースとしてのみ構成可能）。

---

## 5. リージョン方針

| 項目 | 方針 |
|---|---|
| 既定リージョン | `us-central1` |
| 理由 | Gemini Live API / Vertex AI Agent Engineの機能・クォータの実績が厚い |
| `asia-northeast1`（東京）について | Agent Platform API自体は提供されているが、Gemini Live APIは"Single Zone Provisioned Throughput"のみのサポートとなっており、通常のオンデマンド従量課金クォータで問題なく使えるかは未検証。採用する場合は事前に実機検証すること |
| 対応 | MVPでは`us-central1`をデフォルトとし、レイテンシ上の問題が実際に体感される場合のみ`asia-northeast1`への切り替えを再検討する |

---

## 6. 環境一覧

| 環境 | 用途 | ブランチ | デプロイ契機 |
|---|---|---|---|
| local | 手元開発 | - | - |
| dev | 開発者向け統合確認（ブラウザの実UIとして利用） | `dev`（force push可） | `dev`へのpush |
| prd | デモ・審査対応 | `main`（PR経由のみ） | `main`へのPRマージ＋承認ゲート |

stg環境は当面設けない。必要になった時点で追加する（`docs/BASIC_DESIGN.md` §5.1と整合）。

---

## 7. 未決定事項

| TBD ID | 内容 | 判断観点 |
|---|---|---|
| TBD-OV-001 | `asia-northeast1`採用可否の最終確認 | Gemini Live APIのProvisioned Throughput要件がハッカソン規模の利用で問題にならないか実機検証 |
| TBD-OV-002 | dev環境のIAP for Cloud Run設定詳細 | ブラウザOAuthハンドシェイクの設定手順、`03_SECURITY.md`で詳細化 |
