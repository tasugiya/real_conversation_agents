terraform {
  backend "gcs" {
    bucket = "real-conversation-agents-tfstate"
    prefix = "terraform/state/dev"
  }
}
