# state用GCSバケットはinfra/bootstrap/実行後に確定する。
# bucket名は実際のbootstrap出力に合わせて書き換えること（docs/infra/04_DEPLOY.md §4）。
# bootstrap未実行の間は `terraform init` はここで失敗する。

terraform {
  backend "gcs" {
    bucket = "REPLACE_WITH_BOOTSTRAP_STATE_BUCKET_NAME"
    prefix = "terraform/state/dev"
  }
}
