# DevOps

## DevOps とは

AWS によれば、

>DevOps is the combination of cultural philosophies, engineering practices, and tools which increase an organization's ability to deliver applications and services at high velocity and better quality. Over time, several essential practices have emerged when adopting DevOps: continuous integration (CI), continuous delivery (CD), Infrastructure as Code (IaC), and monitoring and logging.

>This paper highlights AWS capabilities that help you accelerate your DevOps journey, and how AWS services can help remove the undifferentiated heavy lifting associated with DevOps adaptation. It also describes how to build a continuous integration and delivery capability without managing servers or build nodes, and how to use IaC to provision and manage your cloud resources in a consistent and repeatable manner.
>- Continuous integration: A software development practice where developers regularly merge their code changes into a central repository, after which automated builds and tests are run.
>- Continuous delivery: A software development practice where code changes are automatically built, tested, and prepared for a release to production.
>- Infrastructure as Code: A practice in which infrastructure is provisioned and managed using code and software development techniques, such as version control, and continuous integration.
>- Monitoring and logging: Enables organizations to see how application and infrastructure performance impacts the experience of their product's end user.
>- Communication and collaboration: Practices are established to bring the teams closer and by building workflows and distributing the responsibilities for DevOps.
>- Security: Should be a cross cutting concern. Your continuous integration and continuous delivery (CI/CD) pipelines and related services should be safeguarded and proper access control permissions should be set up.

>An examination of each of these principles reveals a close connection to the offerings available from AWS.

また、Google Clould においては、

>Google CloudのDORA(DevOps Research and Assessment)チームが、実証研究に基づいて具体的な能力(capability)のリストを出しています。3カテゴリに分かれます。
>技術的能力:クラウドインフラストラクチャ、コードの保守性、継続的デリバリー、継続的インテグレーション、テスト自動化、データベース変更管理、デプロイ自動化、ツール選択のチームへの権限委譲、疎結合アーキテクチャ、モニタリングとオブザーバビリティ、セキュリティのシフトレフト、テストデータ管理、トランクベース開発、バージョン管理
>プロセス的能力:顧客フィードバック、ビジネス判断に活かすモニタリング、能動的な障害通知、変更承認プロセスの簡素化、チームの実験、バリューストリームにおける作業の可視性、ビジュアルマネジメント、仕掛り作業の制限、小さいバッチでの作業
>文化的能力:生成的な組織文化、仕事の満足度、学習文化、変革的リーダーシップ

と言われる。

---

## 目的

本プロジェクトにおけるDevOpsの目的は以下の3点である。

1. ハッカソンのデモ・審査で確実に動作すること（安定性優先）
2. Gemini Live API/Agent Engine等の従量課金サービスの濫用・コスト爆発を防ぐこと
3. モノレポの変更（frontend/api/agent/infra）を誰が見ても追跡でき、影響範囲を判断できること

---

## 開発環境

環境一覧（dev/prd）の詳細は`docs/infra/00_OVERVIEW.md` §6を正とする。要点のみ記載する。

| 環境 | 用途 | ブランチ |
|---|---|---|
| local | 手元開発 | - |
| dev | 開発者向け統合確認（ブラウザの実UIとして利用） | `dev`（force push可） |
| prd | デモ・審査対応 | `main`（PR経由のみ） |

stg環境は当面設けない。dev環境のアクセス制御（IAM認証＋IAP＋password認証の三層）は`docs/infra/03_SECURITY.md` §3を参照。

---

## CI/CD

パイプライン構成、パスフィルタによる差分デプロイ、ブランチ・環境マッピングの詳細は`docs/infra/04_DEPLOY.md`を正とする。

要点:
- モノレポの変更は影響を受けた対象（frontend/api/agent/infra）だけをビルド・デプロイする（affected-only）
- `dorny/paths-filter`による変更検出job＋条件付き後続jobを1つのworkflowにまとめる
- PRはデプロイしない（lint/test/build＋terraform planのみ）。`dev`push＝自動デプロイ、`main`マージ＝承認ゲート付きデプロイ

---

## テスト

### いつ回すか・自動化するか

| テスト種別 | 実行タイミング | 自動化 | 理由 |
|---|---|---|---|
| lint / typecheck / build | PR（変更対象のみ） | 必須 | 高速・無料 |
| frontend unit / component test | PR（frontend変更時） | 必須 | 高速・mock中心 |
| mock E2E | PR（frontend変更時） | 必須 | 外部API接続なし、安定して速い |
| api unit test | PR（api変更時） | 必須 | mock中心 |
| api integration test | PR（api変更時） | 必須 | Firestoreエミュレータ使用、実費用なし |
| Agent behavior test | `agent/**`変更時のみ | 必須（agentパス限定） | 実Gemini呼び出しでコスト・時間がかかるため、agent変更時だけ課す |
| real E2E | dev環境デプロイ後 | 自動（post-deployジョブ） | 実費用が発生するためPRでは回さない |
| smoke test | prdデプロイ直後 | 自動（cd.ymlの最終ステップ） | ヘルスチェック＋主要画面疎通のみ |
| terraform plan | PR（infra変更時） | 必須 | 差分レビュー自体がテスト |

### 何を・どこに・どんな基準で追加するか

| 変更内容 | 追加必須テスト |
|---|---|
| 新規APIエンドポイント | unit test（service層）＋ integration test（route層） |
| 新規UIコンポーネント／画面状態 | component test（loading/error/success等の表示状態を網羅） |
| 新規画面遷移 | mock E2Eシナリオに追加 |
| Agent prompt/persona/tool schema変更 | 該当behavior testケース追加または期待値更新＋会話サンプルをPRに記載 |
| WebSocket event / Firestoreスキーマ変更 | integration testでデータ形状検証、`packages/shared-schemas/`更新 |
| Terraform変更 | `plan`差分のレビュー |

厳密なカバレッジ%目標は設けず、「重要な経路にテストがあるか」をPRレビューで判断する定性基準とする（デモ安定性優先の既存方針と整合）。

---

## IaC

Terraformの運用（bootstrapと継続的applyの分離、ディレクトリ構成）の詳細は`docs/infra/04_DEPLOY.md` §4・`docs/infra/01_ARCHITECTURE.md` §2を正とする。

要点:
- state用GCSバケット・WIF・SAの初回作成（`infra/bootstrap/`）のみ人力実行。以降は`infra/terraform/environments/{dev,prod}`をCIが自動でplan/applyする
- Terraform 1.10以降、GCSバックエンドはネイティブに状態ロックが効くため追加の仕組みは不要
- Agent Engineの実コードやCloud Runのコンテナイメージなど、頻繁に変わるものはTerraform管理外にし、周辺のIAM/SAのみTerraformが管理する

---

## pre-commit

対象は`api/`・`agent/`（Python）。フロントエンドのlint/formatはfrontend側のツールチェイン（ESLint/Prettier等）に委ねる。

```yaml
# .pre-commit-config.yaml（リポジトリroot、filesでapi/agentのみ対象に絞る）
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.x
    hooks:
      - id: ruff
        args: [--fix]
        files: ^(api|agent)/
      - id: ruff-format
        files: ^(api|agent)/

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.x
    hooks:
      - id: mypy
        files: ^(api|agent)/

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.x
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.x
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key
```

補足:
- ruffのlint（`--fix`）→ruff-formatの順で実行する。
- `detect-secrets`は初回に`detect-secrets scan > .secrets.baseline`でベースライン作成が必要。
- ローカルのpre-commitは`--no-verify`で回避可能なため、CI（ci.yml）側でも`pre-commit run --all-files`を再実行し、バイパスされた変更を弾く安全網にする。
- mypyが将来重くなった場合は、pre-commitから外してCI専任にする選択肢を残す。

---

## リリース

詳細は`docs/infra/04_DEPLOY.md` §6を正とする。

要点:
- デプロイのトリガーは`main`マージ＋GitHub Environmentの承認ゲートであり、gitタグはトリガーではなく記録として扱う
- prdデプロイジョブの最終ステップで`gh release create --generate-notes`によりタグ・リリースノートを自動作成する
- ロールバック手段はコンポーネントごとに異なる（Cloud Runはトラフィック分割、Firebase Hostingはリリース履歴、Agent Engineは直前コミットの再デプロイ）。詳細は`docs/infra/04_DEPLOY.md` §7

---

## ドキュメント

- `_internal/`は個人の検討中メモ・ドラフトの置き場とし、確定した内容は`docs/`側へ反映する。`_internal/`配下のファイルの扱い（削除・保持）は都度判断する
- `docs/`配下は既存の`docs/CONTRIBUTION.md` §15.1の一覧構成を正とする
- API/DB/Agent/インフラ/開発フロー/セキュリティ方針が変わった場合は、関連する`docs/`配下の文書を同じPR内で更新する（PRテンプレートの「影響範囲」チェックリストと連動させる）
- 文書間の相互参照（例: `docs/BASIC_DESIGN.md`から`docs/backend/`配下への参照）にズレが生じた場合は、気づいた時点で修正する

---

## ログ・監視

`docs/infra/03_SECURITY.md`・`docs/infra/01_ARCHITECTURE.md`と整合させる。ログに含めるID（`request_id`/`session_id`/`job_id`等）、監視対象（API 5xx率、Gemini 429、Cloud Tasksキュー滞留等）は既存の`docs/CONTRIBUTION.md` §13を継続して正とする。

---

## チケット

### Issueテンプレート

GitHub Issue Forms（YAML）を`.github/ISSUE_TEMPLATE/`に用意する。種別は`docs/CONTRIBUTION.md` §16.1と対応させる。

```text
.github/ISSUE_TEMPLATE/
├── 1-feature.yml
├── 2-bug.yml
├── 3-docs.yml
├── 4-infra.yml
├── 5-agent.yml
└── config.yml   # blank_issues_enabled: false
```

各YAMLで`labels:`を設定し、起票時点で自動ラベル付けする。

### PRテンプレート

`docs/CONTRIBUTION.md` §7.2のドラフトをそのまま`.github/PULL_REQUEST_TEMPLATE.md`として配置する。

### Issue-ブランチ連携

GitHub純正機能で十分とし、独自の仕組みは導入しない。

- `gh issue develop <issue番号> --checkout`でその場でリンク済みブランチを作成できる
- PR本文に`Closes #123`（`Fixes`/`Resolves`も可）と書けば、マージ時に自動でIssueがクローズされる

**注意**: 自動クローズキーワードは、PRの対象ブランチがリポジトリの「デフォルトブランチ」（通常`main`）である場合にのみ機能する。`dev`向けのPRでは自動クローズされない（リンク表示はされる）。この非対称性はチームの運用メモとして共有し、カスタムActionでの統一は行わない。

---

## 機能追加

### バックエンド

1. `feature`または`infra`テンプレートでIssue作成
2. route/service/middleware層に責務を分離して実装（`api/src/`）
3. unit test（service層）＋ integration test（route層、Firestoreエミュレータ）追加
4. WebSocket event schema変更があれば`packages/shared-schemas/`更新
5. `docs/backend/`該当文書を更新
6. PR作成（`Closes #N`）

### エージェント

1. `agent`テンプレートでIssue作成
2. prompt/persona/tool schema変更（`agent/src/`）
3. 該当するAgent behavior testケースを追加・更新（CIは`agent/**`変更で自動実行）
4. 会話サンプル・期待する振る舞い・token使用量への影響をPR本文に記載
5. PR作成

### インフラ

1. `infra`テンプレートでIssue作成
2. `infra/terraform/modules`または`environments`を変更
3. ローカルで`terraform fmt`/`validate`/`plan`確認
4. PR作成 → CIの`plan`結果をレビュー
5. `main`マージ後、devは自動apply、prdは承認ゲート後にapply

### フロントエンド

1. `feature`テンプレートでIssue作成 → `gh issue develop`でブランチ作成
2. `frontend/src/`にコンポーネント実装
3. component test追加（表示状態を網羅）
4. 必要ならmock E2Eシナリオに追加
5. API clientの型・呼び出しを更新（`packages/shared-schemas/`変更があれば追従）
6. lint/typecheck/build確認 → PR作成（`Closes #N`）
