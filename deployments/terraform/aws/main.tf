terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }

  backend "s3" {}
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "bucket_name" {
  type = string
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "urp_backend" {
  bucket = var.bucket_name
}

resource "aws_kms_key" "urp" {
  description             = "URP envelope encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_s3_bucket_public_access_block" "urp_backend" {
  bucket                  = aws_s3_bucket.urp_backend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "urp_backend" {
  bucket = aws_s3_bucket.urp_backend.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "urp_backend" {
  bucket = aws_s3_bucket.urp_backend.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.urp.arn
    }
  }
}

output "urp_platform_contract" {
  value = {
    object_backend  = aws_s3_bucket.urp_backend.bucket
    manifest_store  = "rds-postgresql"
    kms_backend     = aws_kms_key.urp.arn
    deployment_mode = "eks-or-ecs"
  }
}
