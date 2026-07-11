terraform {
  required_version = ">= 1.6.0"
}

variable "urp_bucket_name" { type = string }

resource "aws_s3_bucket" "urp_physical_chunks" {
  bucket = var.urp_bucket_name
}

output "chunk_bucket" {
  value = aws_s3_bucket.urp_physical_chunks.bucket
}
