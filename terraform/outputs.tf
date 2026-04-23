output "ecr_repository_url" {
  description = "ECR repository URL (docker push target without tag)."
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_arn" {
  description = "ECR repository ARN."
  value       = aws_ecr_repository.app.arn
}

output "apprunner_service_id" {
  description = "App Runner service ID."
  value       = aws_apprunner_service.app.service_id
}

output "apprunner_service_arn" {
  description = "App Runner service ARN."
  value       = aws_apprunner_service.app.arn
}

output "apprunner_service_url" {
  description = "Default public URL for the App Runner service."
  value       = "https://${aws_apprunner_service.app.service_url}"
}
