################################################################
# Dev Environment
# This is the root Terraform configuration that wires together
# all the modules to create a complete environment.
################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state - commented out for initial local development.
  # Uncomment after creating the S3 bucket and DynamoDB table.
  #
  # backend "s3" {
  #   bucket         = "clouddeploy-tf-state"
  #   key            = "dev/terraform.tfstate"
  #   region         = "ca-central-1"
  #   dynamodb_table = "clouddeploy-tf-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "dev"
      ManagedBy   = "Terraform"
    }
  }
}

locals {
  common_tags = {
    Project     = var.project_name
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}

# ----------------------------------------------------------------
# Networking
# ----------------------------------------------------------------
module "networking" {
  source = "../../modules/networking"

  project_name         = var.project_name
  vpc_cidr             = "10.0.0.0/16"
  availability_zones   = var.availability_zones
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24"]
  tags                 = local.common_tags
}

# ----------------------------------------------------------------
# Secrets
# ----------------------------------------------------------------
module "secrets" {
  source = "../../modules/secrets"

  project_name = var.project_name
  db_password  = var.db_password
  tags         = local.common_tags
}

# ----------------------------------------------------------------
# IAM
# ----------------------------------------------------------------
module "iam" {
  source = "../../modules/iam"

  project_name = var.project_name
  secret_arns  = [module.secrets.db_password_secret_arn]
  tags         = local.common_tags
}

# ----------------------------------------------------------------
# ECS (created before RDS to get the ECS security group ID)
# ----------------------------------------------------------------
module "ecs" {
  source = "../../modules/ecs"

  project_name            = var.project_name
  aws_region              = var.aws_region
  vpc_id                  = module.networking.vpc_id
  public_subnet_ids       = module.networking.public_subnet_ids
  private_subnet_ids      = module.networking.private_subnet_ids
  task_execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn           = module.iam.task_role_arn
  db_username             = "clouddeploy"
  db_host                 = module.rds.db_host
  db_port                 = module.rds.db_port
  db_name                 = module.rds.db_name
  db_password_secret_arn  = module.secrets.db_password_secret_arn
  desired_count           = 2
  tags                    = local.common_tags
}

# ----------------------------------------------------------------
# RDS
# ----------------------------------------------------------------
module "rds" {
  source = "../../modules/rds"

  project_name               = var.project_name
  vpc_id                     = module.networking.vpc_id
  private_subnet_ids         = module.networking.private_subnet_ids
  ecs_task_security_group_id = module.ecs.ecs_task_security_group_id
  db_password                = var.db_password
  multi_az                   = false # Set true in prod
  tags                       = local.common_tags
}
