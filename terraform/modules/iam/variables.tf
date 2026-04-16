variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "claude-simulator"
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider for IRSA"
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the EKS OIDC provider (without https:// prefix)"
  type        = string
}

variable "app_namespace" {
  description = "Kubernetes namespace for the application"
  type        = string
  default     = "claude-simulator"
}

variable "backend_service_account" {
  description = "Kubernetes service account name for the backend"
  type        = string
  default     = "backend"
}

variable "ecr_repository_arns" {
  description = "List of ECR repository ARNs for access policies"
  type        = list(string)
}

variable "eks_cluster_name" {
  description = "Name of the EKS cluster (for CI/CD role scoping)"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format for OIDC federation"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
