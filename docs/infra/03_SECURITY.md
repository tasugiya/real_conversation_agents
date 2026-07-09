# リアルな複数人英会話トレーニングエージェント セキュリティ設計書

## 目次

- [0. 文書情報](#0-文書情報)
- [1. 本書の目的](#1-本書の目的)
- [2. 多層防御の全体像](#2-多層防御の全体像)
- [3. Organization Policy（Domain Restricted Sharing）](#3-organization-policydomain-restricted-sharing)
- [4. IAM / Service Account 権限表](#4-iam--service-account-権限表)
- [5. Cloud Armor設計（prd限定）](#5-cloud-armor設計prd限定)
- [6. パスワード認証とネットワーク保護の関係](#6-パスワード認証とネットワーク保護の関係)
- [7. VPC Service Controls：見送りの判断根拠](#7-vpc-service-controls見送りの判断根拠)
- [8. Cloud VPNを採用しない理由](#8-cloud-vpnを採用しない理由)
- [9. 未決定事項](#9-未決定事項)
- [10. 参考資料](#10-参考資料)

---

## 0. 文書情報

| 項目 | 内容 |
|---|---|
| 文書名 | リアルな複数人英会話トレーニングエージェント セキュリティ設計書 |
| 版数 | v0.1 |
| 作成日 | 2026-07-09 |
| 関連文書 | `docs/infra/01_ARCHITECTURE.md`, `docs/infra/02_PARAMS_DEF.md` |
| 位置づけ | IAM・Organization Policy・Cloud Armor・VPC-SCなど、セキュリティ関連の意思決定と設定値を集約する。`01_ARCHITECTURE.md`からは本書への参照のみとし、詳細はここに一本化する。 |

---

## 1. 本書の目的

「IAM設定ミスによる意図しない公開を、運用ではなく仕組みで防ぐ」ことを目的に、以下を定義する。

- Organization Policyによる公開バインディングの禁止
- 各Service Accountに付与する最小権限
- Cloud Armorの防御ルール（prd限定）
- VPC Service Controlsを見送った理由と、再検討する条件
- Cloud VPNが適用対象にならない理由（記録として残す）

---

## 2. 多層防御の全体像

| レイヤ | 防御手段 | 対象 |
|---|---|---|
| ポリシー層 | Organization Policy（Domain Restricted Sharing） | 全リソース共通 |
| ネットワーク層（prdのみ） | Cloud Run ingress制限 + External ALB + Cloud Armor | API |
| ネットワーク層（dev） | なし（意図的に公開） | API |
| IAM層 | Service Account最小権限 | Firestore, Secret Manager, Agent Engine, API |
| アプリケーション層 | password認証、session token検証、入力バリデーション | API |

「VPNで内部通信を閉じたい」という当初の要求は、対象となるオンプレ/他VPCが存在しないため技術的に適用できない。代わりにポリシー層とIAM層で同等以上の効果を狙う（8章）。

---

## 3. Organization Policy（Domain Restricted Sharing）

### 3.1 採用するポリシー

`constraints/iam.allowedPolicyMemberDomains`（Domain Restricted Sharing）を有効化する。

効果：`allUsers` / `allAuthenticatedUsers` をIAMポリシーに追加しようとするAPI呼び出しそのものを拒否する（`412 Precondition Failed`）。運用担当者が誤って公開バインディングを付与しようとしても、ポリシーレベルで機械的に弾かれる。

適用範囲：プロジェクト全体（Firestore、Secret Manager、Vertex AI Agent Engine、Cloud Run全てに横断的に効く）。

### 3.2 devのCloud Run APIに対する例外

devのCloud Run APIは意図的に公開する必要があるため、Domain Restricted Sharingの一律適用では正常にデプロイできない可能性がある。以下のいずれかで対応する。

- Cloud Run側の「Invoker IAM check」を無効化する運用（Google公式に案内されている回避策）を、dev環境のみ適用する
- または、dev用Cloud RunサービスをOrganization Policyの適用除外（exception）に明示的に加える

どちらを採用するかはTerraform実装時に確定する（§9 TBD-SEC-001）。

### 3.3 導入手順（概要）

```bash
# 例: プロジェクト単位でDomain Restricted Sharingを有効化
gcloud resource-manager org-policies enable-enforce \
  constraints/iam.allowedPolicyMemberDomains \
  --project=<PROJECT_ID>
```

具体的な許可ドメイン・例外設定はTerraformの`org-policy`モジュール（`01_ARCHITECTURE.md` §18.2）で管理する。

---

## 4. IAM / Service Account 権限表

`02_PARAMS_DEF.md` §7のService Account一覧に対応する、実際のロールバインディング。

| Service Account | ロール | 付与理由 |
|---|---|---|
| `api-sa` | `roles/datastore.user`（Firestore） | セッション・発話ログの読み書き |
| `api-sa` | `roles/secretmanager.secretAccessor` | 共有password、session signing key、Gemini/Vertex AI設定の参照 |
| `api-sa` | `roles/aiplatform.user`（Agent Engine呼び出し用） | Agent Engineへのリクエスト中継 |
| `agent-engine-sa` | `roles/secretmanager.secretAccessor` | X API tokenの参照 |
| `agent-engine-sa` | `roles/datastore.user` | 必要に応じてgrammar_feedback/system_eventの書き込み |
| `agent-engine-sa` | （Vertex AI/Gemini呼び出し権限） | Agent Engine実行に必要な標準権限 |
| `github-actions-deploy-sa` | `roles/run.admin`, `roles/artifactregistry.writer`, `roles/iam.serviceAccountUser`（対象SAへのactAs） | Cloud Run / Agent Engineへのデプロイ |
| `terraform-sa` | IaC管理対象リソースへの`*.admin`系ロール（対象を絞り込む） | インフラのプロビジョニング |

### 4.1 最小権限の原則

- `agent-engine-sa`はデフォルトのCompute Engine SAを使わず、専用SAを明示的に指定する（Vertex AI Agent Engineのデプロイ時オプション）
- 広めの権限を一時的に付与した場合は`docs/decisions/`にADRとして理由を記録し、後で縮小する（`CONTRIBUTION.md` §18.3と整合）

### 4.2 Vertex AI系リソースの構造的な安全性

Cloud Runと異なり、Vertex AI API（Agent Engineを含む）には`allUsers`のような匿名アクセスを許可する概念自体が存在しない。呼び出しには常に有効なGoogle認証（OAuthトークン）が必要なため、「うっかりpublicにしてしまう」というCloud Run特有の事故パターンは構造的に起きにくい。ここで注意すべきは、特定のグループ/ドメインへの過剰な権限付与であり、これは3章のOrganization Policyでカバーする。

---

## 5. Cloud Armor設計（prd限定）

> devはALB/Cloud Armorを経由しないため、本章はprdのみに適用される（`01_ARCHITECTURE.md` §5, §7参照）。

### 5.1 配置

```text
Frontend (Firebase Hosting)
  ↓
External Application Load Balancer
  ↓
Cloud Armor
  ↓
Serverless NEG
  ↓
Cloud Run API (prd)
```

### 5.2 ルールセット

| ルール | 内容 | 優先度 |
|---|---|---|
| WAF preconfigured rules | XSS、SQLi等の代表的攻撃を検知・遮断 | High |
| rate limit `/api/session` | セッション作成の連打を抑制 | High |
| rate limit `/api/realtime` / `/ws` | Gemini Live APIセッション濫用を抑制 | High |
| rate limit `/api/feedback` | 会話終了時の同期フィードバック生成呼び出しの濫用を抑制 | Medium |
| 共有ヘッダー一致（簡易フィルタ） | 正規Frontendのみが送る固定ヘッダーを要求し、無差別botのpassword総当たりを一次フィルタする | Medium |
| block suspicious IP | 必要に応じて手動遮断 | Low |
| default allow | 通常リクエストを許可 | High |

**Serverless NEGをバックエンドとする場合、health checkリソースは設定できない**（Google Cloud仕様上非対応。Serverless NEGの死活監視はGoogle側が自動的に行う）。「health check allowlist」のようなルールは不要かつ設定不可能なため置かない。

### 5.3 WAFの限界

Cloud Armorは入口防御であり、アプリケーション側の入力検証・認証を代替しない。必ずアプリ側で以下を行う（`01_ARCHITECTURE.md` §7.4）。

- request schema validation、入力長制限
- session token検証（6章参照）
- CORS制御
- prompt injection対策、tool call schema validation（Agent Engine側）

---

## 6. パスワード認証とネットワーク保護の関係

| 層 | 何を守るか | 何を守らないか |
|---|---|---|
| Cloud Armor（prd） | 攻撃トラフィック、過剰アクセス、bot | password自体の正しさは検証しない |
| password認証（アプリ層） | 「正規利用者かどうか」の一次判定 | ネットワーク経路の閉域化はしない |
| Organization Policy | IAM経由での意図しない公開 | アプリケーションレベルの認可漏れ |

3つは役割が異なり、どれか1つで代替できない。dev環境はCloud Armorを持たないため、**password認証がほぼ唯一の防御**になる点を明確に認識しておく。

---

## 7. VPC Service Controls：見送りの判断根拠

### 7.1 技術的な対応状況

調査の結果、VPC-SCはFirestore・Secret Manager・**Vertex AI Agent Engineにも対応済み**であることを確認した（Agent Engineデプロイ時に、Reasoning Engine Service Agentから`storage.googleapis.com`・`artifactregistry.googleapis.com`へのingressルールを別途許可する必要がある、という制約付き）。技術的に「できない」わけではない。

### 7.2 見送る理由

- パーミッター設計・アクセスレベル設定・ローカル開発機からのアクセス例外設定など、設定コストがハッカソンMVPの規模に見合わない
- 誤設定時に「意図せずロックアウトする」リスクがあり、デモ安定性を優先する`CONTRIBUTION.md`付録Bの方針と相反する
- Organization Policy（3章）+ Cloud Run ingress制限（prd）で、想定される主要リスク（IAM誤設定による意図しない公開）は既にカバーできている

### 7.3 再検討する条件

- 審査・実運用で「データ境界の技術的証明」を明確に求められた場合
- prd環境限定で、時間に余裕がある場合（devには絶対に適用しない：開発体験を著しく損なうため）

---

## 8. Cloud VPNを採用しない理由

Cloud VPNは、オンプレミス環境や他のVPCとGCPのVPCをトンネル接続するための機能である。本システムには接続すべきオンプレミス環境・他VPCが存在しないため、**技術的に適用対象がない**。

「IAM設定ミスによる意図しない公開を防ぎたい」という当初の目的は、3章（Organization Policy）と`01_ARCHITECTURE.md` §16のCloud Run ingress制限で対応する。この整理はチーム内の議論記録として残す（今後同じ論点が再度上がった際に参照する）。

---

## 9. 未決定事項

| TBD ID | 内容 |
|---|---|
| TBD-SEC-001 | devのCloud Run APIに対するOrganization Policy例外の実装方法（Invoker IAM check無効化 vs ポリシー例外） |
| TBD-SEC-002 | `agent-engine-sa`に付与するVertex AI関連ロールの最終確定（`aiplatform.user`で十分か、カスタムロールが必要か） |
| TBD-SEC-003 | Cloud Armor rate limitの具体的な閾値（session作成連打・Live APIセッション濫用の許容値） |
| TBD-SEC-004 | 共有ヘッダー一致ルールで使うヘッダー名・値のローテーション方針 |

---

## 10. 参考資料

- Restrict identities with domain-restricted sharing  
  https://cloud.google.com/resource-manager/docs/organization-policy/restricting-domains

- VPC Service Controls supported products and limitations  
  https://docs.cloud.google.com/vpc-service-controls/docs/supported-products

- Managing access for deployed agents (Vertex AI Agent Engine)  
  https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/manage/access

- Backend services overview（Serverless NEGはhealth check非対応）  
  https://docs.cloud.google.com/load-balancing/docs/backend-service

- Cloud Armor security policy overview  
  https://docs.cloud.google.com/armor/docs/security-policy-overview
