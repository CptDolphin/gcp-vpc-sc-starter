# Piny narzędzi i providera dla repo perimetru.
#
# DLACZEGO >= 1.8: `terraform test` i provider-defined functions to floor całego stacku; niżej nie schodzimy.
# DLACZEGO ~> 7.0 dla google: zasoby Access Context Managera (perimetr, per-resource, per-rule oraz warianty
# dry-run) są stabilne w linii 7.x. Pinujemy MAJOR, bo perimetr to org-plane singleton — ciche breaking-change
# w providerze objawiłoby się na obiekcie o organizacyjnym blast-radiusie.

terraform {
  required_version = ">= 1.8, < 2.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    # `time` — WYŁĄCZNIE dla `time_sleep.deskryptory_widoczne` w `alerts.tf`. Cloud Monitoring potwierdza
    # utworzenie deskryptora metryki, ZANIM stanie się on widoczny dla walidacji polityk alertów (zmierzone:
    # `Error 404: Cannot find metric(s)` na deskryptorze utworzonym w tym samym apply). `depends_on` tego nie
    # rozwiązuje — zależność jest spełniona, a zasób jeszcze nie istnieje dla konsumenta. Provider jest
    # bezstanowy i nie dotyka żadnego API chmury; to jest opóźnienie, nie integracja.
    time = {
      source  = "hashicorp/time"
      version = "~> 0.13"
    }
  }

  # Backend GCS. Stan perimetru = stan granicy bezpieczeństwa: bucket z versioning + soft-delete,
  # BEZ retention-lock: stan jest nadpisywany przy każdym apply, a retencja WORM zabrania
  # skasowania poprzedniej wersji — backend przestaje działać po pierwszym zapisie.
  backend "gcs" {
    bucket = "<STATE_BUCKET>"
    prefix = "vpc-sc/perimeter"
  }
}

# Tożsamość: WIF keyless z GitHub Actions (impersonacja SA perimetru). Żadnych kluczy SA w repo ani w
# sekretach — provider bierze credentiale z tokenu OIDC wymienionego w workflow.
provider "google" {}
