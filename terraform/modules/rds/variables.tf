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

variable "private_subnet_ids" {
  description = "List of private subnet IDs for the RDS subnet group"
  type        = list(string)
}

variable "rds_security_group_id" {
  description = "Security group ID for RDS (inbound only from EKS, from networking module)"
  type        = string
}

variable "db_name" {
  description = "Name of the PostgreSQL database to create"
  type        = string
  default     = "claude_simulator"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "claude_admin"
}

variable "db_password" {
  description = "Master password for the RDS instance"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
