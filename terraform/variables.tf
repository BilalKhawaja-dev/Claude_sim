# ------------------------------------------------------------------------------
# Root Variables
# ------------------------------------------------------------------------------

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

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones to use for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "claude_simulator"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "claude_admin"
}

variable "db_password" {
  description = "Master password for the RDS instance (min 8 characters)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 8
    error_message = "RDS master password must be at least 8 characters."
  }
}

variable "sender_email" {
  description = "Email address to verify for sending session summaries via SES"
  type        = string
}

variable "domain_name" {
  description = "Domain name for the self-signed TLS certificate"
  type        = string
  default     = "claude-simulator.local"
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format for CI/CD OIDC federation"
  type        = string
}

variable "eks_cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.30"
}

variable "eks_node_instance_type" {
  description = "EC2 instance type for EKS managed node group"
  type        = string
  default     = "t3.medium"
}

variable "eks_node_min_size" {
  description = "Minimum number of nodes in the EKS managed node group"
  type        = number
  default     = 2
}

variable "eks_node_max_size" {
  description = "Maximum number of nodes in the EKS managed node group"
  type        = number
  default     = 4
}

variable "eks_node_desired_size" {
  description = "Desired number of nodes in the EKS managed node group"
  type        = number
  default     = 2
}

variable "ecr_image_retention_count" {
  description = "Number of images to retain per ECR repository"
  type        = number
  default     = 10
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
