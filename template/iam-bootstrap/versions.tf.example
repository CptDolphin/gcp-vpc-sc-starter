terraform {
  required_version = ">= 1.8, < 2.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    # google-beta TYLKO dla google_iam_deny_policy — ten zasób nie ma odpowiednika w GA.
    # Reszta stacku jedzie na providerze GA.
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.0"
    }
  }
}

provider "google" {}
provider "google-beta" {}
