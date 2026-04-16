# ------------------------------------------------------------------------------
# Terraform Configuration
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Remote state backend — uncomment after initial `terraform apply` creates the bucket,
  # then run `terraform init -migrate-state` to migrate local state to S3.
  #
  # backend "s3" {
  #   bucket         = "claude-simulator-prod-terraform-state"
  #   key            = "terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "claude-simulator-prod-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  common_tags = var.tags
}

# ------------------------------------------------------------------------------
# State Backend (S3 + DynamoDB)
# ------------------------------------------------------------------------------

module "state" {
  source = "./modules/state"

  project_name = var.project_name
  environment  = var.environment
  tags         = local.common_tags
}

# ------------------------------------------------------------------------------
# Networking (VPC, Subnets, NAT, Security Groups)
# ------------------------------------------------------------------------------

module "networking" {
  source = "./modules/networking"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  tags               = local.common_tags
}

# ------------------------------------------------------------------------------
# EKS Cluster
# ------------------------------------------------------------------------------

module "eks" {
  source = "./modules/eks"

  project_name          = var.project_name
  environment           = var.environment
  cluster_version       = var.eks_cluster_version
  private_subnet_ids    = module.networking.private_subnet_ids
  eks_security_group_id = module.networking.eks_security_group_id
  node_instance_type    = var.eks_node_instance_type
  node_min_size         = var.eks_node_min_size
  node_max_size         = var.eks_node_max_size
  node_desired_size     = var.eks_node_desired_size
  tags                  = local.common_tags
}

# ------------------------------------------------------------------------------
# RDS PostgreSQL (pgvector)
# ------------------------------------------------------------------------------

module "rds" {
  source = "./modules/rds"

  project_name          = var.project_name
  environment           = var.environment
  private_subnet_ids    = module.networking.private_subnet_ids
  rds_security_group_id = module.networking.rds_security_group_id
  db_name               = var.db_name
  db_username           = var.db_username
  db_password           = var.db_password
  tags                  = local.common_tags
}

# ------------------------------------------------------------------------------
# ECR Repositories
# ------------------------------------------------------------------------------

module "ecr" {
  source = "./modules/ecr"

  project_name          = var.project_name
  environment           = var.environment
  image_retention_count = var.ecr_image_retention_count
  tags                  = local.common_tags
}

# ------------------------------------------------------------------------------
# ALB (Application Load Balancer)
# ------------------------------------------------------------------------------

module "alb" {
  source = "./modules/alb"

  project_name      = var.project_name
  environment       = var.environment
  vpc_id            = module.networking.vpc_id
  public_subnet_ids = module.networking.public_subnet_ids
  domain_name       = var.domain_name
  tags              = local.common_tags
}

# ------------------------------------------------------------------------------
# IAM (IRSA Roles, CI/CD Role, Node Role)
# ------------------------------------------------------------------------------

module "iam" {
  source = "./modules/iam"

  project_name     = var.project_name
  environment      = var.environment
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url
  ecr_repository_arns = [
    module.ecr.frontend_repository_arn,
    module.ecr.backend_repository_arn,
  ]
  eks_cluster_name = module.eks.cluster_name
  github_repo      = var.github_repo
  tags             = local.common_tags
}

# ------------------------------------------------------------------------------
# SES (Email Identity)
# ------------------------------------------------------------------------------

module "ses" {
  source = "./modules/ses"

  project_name = var.project_name
  environment  = var.environment
  sender_email = var.sender_email
  tags         = local.common_tags
}
