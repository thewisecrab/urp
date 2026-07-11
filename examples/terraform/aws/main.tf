terraform {
  required_version = ">= 1.5.0"
}
variable "bucket_name" {
  type = string
}
resource "aws_s3_bucket" "urp_backend" {
  bucket = var.bucket_name
}
resource "aws_s3_bucket_versioning" "urp_backend" {
  bucket = aws_s3_bucket.urp_backend.id
  versioning_configuration {
    status = "Enabled"
  }
}
