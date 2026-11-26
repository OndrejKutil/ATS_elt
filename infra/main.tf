terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 8.0" }
  }
}

variable "project_id" {
  type = string
}

provider "google" {
  project               = var.project_id
  region                = "us-central1"
  billing_project       = var.project_id
  user_project_override = true
}

resource "google_storage_bucket" "raw" {
  name                        = "${var.project_id}-raw"
  location                    = "US-CENTRAL1"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_bigquery_dataset" "ats" {
  dataset_id                 = "ats"
  location                   = "US-CENTRAL1"
  delete_contents_on_destroy = false
}

resource "google_service_account" "pipeline" {
  account_id   = "ats-pipeline"
  display_name = "ATS pipeline (Raspberry Pi)"
}

resource "google_storage_bucket_iam_member" "pipeline_raw" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_bigquery_dataset_iam_member" "pipeline_ats" {
  dataset_id = google_bigquery_dataset.ats.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_service" "orgpolicy" {
  service            = "orgpolicy.googleapis.com"
  disable_on_destroy = false
}

resource "google_org_policy_policy" "allow_sa_keys" {
  name   = "projects/${var.project_id}/policies/iam.disableServiceAccountKeyCreation"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "FALSE"
    }
  }

  depends_on = [google_project_service.orgpolicy]
}