# ------------------------------------------------------------------------------
# State Backend Outputs
# ------------------------------------------------------------------------------

output "state_bucket_name" {
  description = "Name of the S3 bucket storing Terraform state"
  value       = module.state.bucket_name
}

output "state_dynamodb_table_name" {
  description = "Name of the DynamoDB table used for state locking"
  value       = module.state.dynamodb_table_name
}

# ------------------------------------------------------------------------------
# Networking Outputs
# ------------------------------------------------------------------------------

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

# ------------------------------------------------------------------------------
# EKS Outputs
# ------------------------------------------------------------------------------

output "eks_cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "Endpoint URL for the EKS cluster API server"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data for cluster authentication"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

# ------------------------------------------------------------------------------
# RDS Outputs
# ------------------------------------------------------------------------------

output "rds_endpoint" {
  description = "RDS instance endpoint (hostname)"
  value       = module.rds.endpoint
}

output "rds_port" {
  description = "RDS instance port"
  value       = module.rds.port
}

output "rds_database_name" {
  description = "Name of the PostgreSQL database"
  value       = module.rds.database_name
}

# ------------------------------------------------------------------------------
# ECR Outputs
# ------------------------------------------------------------------------------

output "ecr_frontend_repository_url" {
  description = "URL of the frontend ECR repository"
  value       = module.ecr.frontend_repository_url
}

output "ecr_backend_repository_url" {
  description = "URL of the backend ECR repository"
  value       = module.ecr.backend_repository_url
}

# ------------------------------------------------------------------------------
# ALB Outputs
# ------------------------------------------------------------------------------

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.alb.alb_dns_name
}

# ------------------------------------------------------------------------------
# IAM Outputs
# ------------------------------------------------------------------------------

output "bedrock_access_role_arn" {
  description = "ARN of the IRSA role for Bedrock access"
  value       = module.iam.bedrock_access_role_arn
}

output "ses_access_role_arn" {
  description = "ARN of the IRSA role for SES access"
  value       = module.iam.ses_access_role_arn
}

output "ecr_access_role_arn" {
  description = "ARN of the IRSA role for ECR access"
  value       = module.iam.ecr_access_role_arn
}

output "cicd_role_arn" {
  description = "ARN of the CI/CD OIDC role for GitHub Actions"
  value       = module.iam.cicd_role_arn
}

output "eks_node_role_arn" {
  description = "ARN of the EKS node IAM role"
  value       = module.eks.node_group_role_arn
}

# ------------------------------------------------------------------------------
# SES Outputs
# ------------------------------------------------------------------------------

output "ses_sender_email" {
  description = "The verified sender email address"
  value       = module.ses.sender_email
}
