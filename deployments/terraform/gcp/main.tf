terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }

  backend "gcs" {}
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_storage_bucket" "urp" {
  name                        = "${var.project_id}-urp-platform"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning {
    enabled = true
  }
}

resource "google_kms_key_ring" "urp" {
  name     = "urp-platform"
  location = var.region
}

resource "google_kms_crypto_key" "urp" {
  name            = "urp-envelope"
  key_ring        = google_kms_key_ring.urp.id
  rotation_period = "7776000s"
}

# Platform contract: production deployments wire this to Cloud SQL Postgres,
# Cloud Storage, Cloud KMS, and GKE/Cloud Run through environment-specific modules.
output "urp_platform_contract" {
  value = {
    object_backend  = google_storage_bucket.urp.name
    kms_backend     = google_kms_crypto_key.urp.id
    manifest_store  = "cloud-sql-postgres"
    deployment_mode = "gke-or-cloud-run"
  }
}
