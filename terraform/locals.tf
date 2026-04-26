locals {
  runtime_environment_variables = merge(
    var.runtime_environment_variables,
    {
      DATABASE_URI                      = var.database_uri
      OPENAI_API_KEY                    = var.openai_api_key
      CLERK_SECRET_KEY                  = var.clerk_secret_key
      CLERK_JWKS_URL                    = var.clerk_jwks_url
      CLERK_AUTHORIZED_PARTIES          = var.clerk_authorized_parties
      CLERK_JWT_KEY                     = var.clerk_jwt_key
      CLERK_SYNC_SECRET                 = var.clerk_sync_secret
      PUSHOVER_APPLICATION_TOKEN        = var.pushover_application_token
      NEXT_PUBLIC_API_URL               = var.next_public_api_url
      NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = var.next_public_clerk_publishable_key
      LANGSMITH_TRACING                 = var.langsmith_tracing
      LANGSMITH_ENDPOINT                = var.langsmith_endpoint
      LANGSMITH_API_KEY                 = var.langsmith_api_key
      LANGSMITH_PROJECT                 = var.langsmith_project
    },
  )
}
