terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 8.0" }
  }
}

variable "project_id" {
  type = string
}

provider "google" {
  project = var.project_id
  region  = "us-central1"
}

resource "google_storage_bucket" "raw" {
  name                        = "${var.project_id}-raw"
  location                    = "US-CENTRAL1"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}