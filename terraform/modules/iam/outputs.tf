output "bedrock_access_role_arn" {
  description = "ARN of the IRSA role for Bedrock access"
  value       = aws_iam_role.bedrock_access.arn
}

output "ses_access_role_arn" {
  description = "ARN of the IRSA role for SES access"
  value       = aws_iam_role.ses_access.arn
}

output "ecr_access_role_arn" {
  description = "ARN of the IRSA role for ECR access"
  value       = aws_iam_role.ecr_access.arn
}

output "cicd_role_arn" {
  description = "ARN of the CI/CD OIDC role for GitHub Actions"
  value       = aws_iam_role.cicd.arn
}
