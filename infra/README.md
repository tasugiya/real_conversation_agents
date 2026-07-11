# infra/

GCPリソースをTerraformで管理するディレクトリ。設計方針は`docs/infra/00_OVERVIEW.md`〜`04_DEPLOY.md`を正とする。

```text
infra/
├── bootstrap/    # 人力で1回だけ実行。state用GCSバケット・WIF・terraform-sa・github-actions-deploy-saを作成
└── terraform/
    ├── environments/
    │   ├── dev/  # CIが自動でplan/applyする
    │   └── prod/ # CIがplanし、承認ゲート後にapplyする
    └── modules/  # 環境間で共有するTerraformモジュール
```

- `bootstrap/`と`terraform/`は明確に役割が異なる。`bootstrap/`はCI/CDに組み込まない（詳細は`bootstrap/README.md`）。
- Agent Engineの実コード（`agent/`）やCloud Runのコンテナイメージは、ここでは管理しない。頻繁に変わるものはCIのデプロイステップに任せ、Terraformは実行環境・IAM・周辺リソースの枠だけを管理する（`docs/infra/04_DEPLOY.md` §5）。
