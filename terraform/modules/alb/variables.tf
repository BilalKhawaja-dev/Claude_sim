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

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for the ALB"
  type        = list(string)
}

variable "domain_name" {
  description = "Domain name for the self-signed TLS certificate"
  type        = string
  default     = "claude-simulator.local"
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
