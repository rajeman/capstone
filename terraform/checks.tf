check "app_runner_required_env" {
  assert {
    condition     = var.database_uri != ""
    error_message = "Set database_uri (e.g. export TF_VAR_database_uri='mongodb+srv://.../dbname')."
  }

  assert {
    condition     = var.clerk_secret_key != ""
    error_message = "Set clerk_secret_key (e.g. export TF_VAR_clerk_secret_key=...)."
  }

  assert {
    condition     = var.openai_api_key != ""
    error_message = "Set openai_api_key (e.g. export TF_VAR_openai_api_key=...)."
  }
}
