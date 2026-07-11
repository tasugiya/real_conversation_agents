# infra/bootstrap/

## これは何か

Terraformがstateを保存するGCSバケット自体を、そのバックエンド設定で管理しようとすると循環（鶏と卵問題）が生じる。また、GitHub Actionsが使うWorkload Identity Federationという信頼関係を、GitHub Actions自身に作らせるのはセキュリティ上望ましくない。

そのため、このディレクトリだけは**人力で1回だけ実行する**。CI/CD（`.github/workflows/`）には絶対に組み込まない。

詳細な設計判断は`docs/infra/04_DEPLOY.md` §4を参照。

## 実行前に確認すること

1. `terraform.tfvars`の`project_id`が本当に使ってよいプロジェクトか
2. `state_bucket_name`がグローバルに一意な名前か（GCSバケット名は全世界で一意である必要がある）
3. `github_repository`が実際のリポジトリと一致しているか
4. 実行するGoogleアカウントが対象プロジェクトのOwner/Editor相当の権限を持っているか

## 実行手順

```bash
cd infra/bootstrap

# 1. 初回はローカルstateで実行する
terraform init
terraform plan
terraform apply

# 2. 出力値を確認する
terraform output

# 3. 作成されたバケットへ、このbootstrap自身のstateを移行する
#    （ローカルにのみ残さず、チームで後から参照・変更できるようにするため）
cat > backend_migrate.tf <<'EOF'
terraform {
  backend "gcs" {
    bucket = "<terraform outputのstate_bucket_nameの値>"
    prefix = "terraform/state/bootstrap"
  }
}
EOF

terraform init -migrate-state
rm backend_migrate.tf   # migrate後は不要（設定はbackend.tf相当として別途正式に残す場合はそちらへ）
```

## 実行後にやること

1. `terraform output`の値を、以下に反映する。
   - `infra/terraform/environments/dev/backend.tf`・`infra/terraform/environments/prod/backend.tf`の`bucket`
   - `infra/terraform/environments/dev/terraform.tfvars`・`infra/terraform/environments/prod/terraform.tfvars`の`github_actions_deploy_sa_email`
   - GitHub repositoryの Settings > Secrets and variables > Actions に、`GCP_WORKLOAD_IDENTITY_PROVIDER`・`GCP_SERVICE_ACCOUNT_EMAIL`（terraform-sa用）・`GCP_DEPLOY_SERVICE_ACCOUNT_EMAIL`（github-actions-deploy-sa用）などの値を登録する（`docs/infra/02_PARAMS_DEF.md` §13）
2. GitHub repositoryの Settings > Environments で`dev`・`prd`を作成し、`prd`にrequired reviewersを設定する
3. これ以降、`infra/terraform/environments/{dev,prod}`はCI（`.github/workflows/cd.yml`）が自動でplan/applyする
