variable "aws_region" {
  description = "AWS region for resources and for the App Runner service."
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment name (used for tags)."
  type        = string
  default     = "dev"
}

variable "ecr_repository_name" {
  description = "ECR repository name for the application image."
  type        = string
  default     = "capstone-app-ecr"
}

variable "apprunner_service_name" {
  description = "AWS App Runner service name."
  type        = string
  default     = "capstone-app"
}

variable "container_port" {
  description = "Port the container listens on (must match Dockerfile EXPOSE / uvicorn)."
  type        = string
  default     = "8000"
}

variable "image_tag" {
  description = "Image tag App Runner should deploy from ECR."
  type        = string
  default     = "latest"
}

variable "apprunner_cpu" {
  description = "App Runner CPU (valid values per AWS docs, e.g. 256, 512, 1024, 2048)."
  type        = string
  default     = "256"
}

variable "apprunner_memory" {
  description = "App Runner memory in MB (must pair validly with CPU)."
  type        = string
  default     = "512"
}

variable "database_uri" {
  description = "MongoDB URI for the app (DATABASE_URI). Must start with mongodb:// or mongodb+srv:// and include a database name in the path."
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "Value for OPENAI_API_KEY on App Runner. Pass via TF_VAR_openai_api_key or terraform.tfvars."
  type        = string
  sensitive   = true
}

variable "clerk_secret_key" {
  description = "Value for CLERK_SECRET_KEY on App Runner. Pass via TF_VAR_clerk_secret_key or terraform.tfvars."
  type        = string
  sensitive   = true
}

variable "clerk_authorized_parties" {
  description = "Optional comma-separated origins for CLERK_AUTHORIZED_PARTIES (Clerk session JWT aud/azp checks)."
  type        = string
  default     = ""
  sensitive   = false
}

variable "clerk_jwt_key" {
  description = "Optional PEM public key for CLERK_JWT_KEY (Clerk networkless JWT verify)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "clerk_sync_secret" {
  description = "Optional shared secret for CLERK_SYNC_SECRET (verified-claims sync from the frontend)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "clerk_jwks_url" {
  description = "Optional CLERK_JWKS_URL (only set if the app reads it; otherwise leave empty)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "pushover_application_token" {
  description = "Optional PUSHOVER_APPLICATION_TOKEN for Pushover wallet alerts."
  type        = string
  default     = ""
  sensitive   = true
}

variable "next_public_api_url" {
  description = "Public API base URL for the browser (NEXT_PUBLIC_API_URL). Same-origin deploys can use the App Runner HTTPS URL with no trailing slash."
  type        = string
  default     = ""
  sensitive   = false
}

variable "next_public_clerk_publishable_key" {
  description = "Clerk publishable key for the Next bundle (NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY). Matches Docker build-arg; also set here if you want it present at runtime."
  type        = string
  default     = ""
  sensitive   = true
}

variable "langsmith_tracing" {
  description = "LANGSMITH_TRACING for the app (e.g. true). Optional. Set via TF_VAR_langsmith_tracing or terraform.tfvars."
  type        = string
  default     = ""
  sensitive   = false
}

variable "langsmith_endpoint" {
  description = "LANGSMITH_ENDPOINT (optional; self-hosted or regional LangSmith API URL)."
  type        = string
  default     = ""
  sensitive   = false
}

variable "langsmith_api_key" {
  description = "LANGSMITH_API_KEY for LangSmith tracing. Optional. Set via TF_VAR_langsmith_api_key or terraform.tfvars."
  type        = string
  default     = ""
  sensitive   = true
}

variable "langsmith_project" {
  description = "LANGSMITH_PROJECT (optional LangSmith project name)."
  type        = string
  default     = ""
  sensitive   = false
}

variable "runtime_environment_variables" {
  description = "Additional plain environment variables merged into the App Runner service (optional)."
  type        = map(string)
  default     = {}
}

variable "auto_deployments_enabled" {
  description = "When true, App Runner deploys on new image pushes to ECR."
  type        = bool
  default     = true
}
