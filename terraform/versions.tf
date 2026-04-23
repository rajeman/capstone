terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "dev-terraform-tools"
    key    = "envs/dev/capstone.tfstate"
    region = "eu-west-1"
    # If the bucket lives in another region, run:
    # terraform init -backend-config="region=<bucket-region>"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "capstone"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
