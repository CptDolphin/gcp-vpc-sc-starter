# Tożsamości i uprawnienia dla repozytorium perimetru VPC-SC.
#
# KTO TO APPLIKUJE: zespół IAM / architekt z uprawnieniami org-admin — NIE pipeline perimetru.
# To jest kod, który NADAJE uprawnienia; gdyby applikowała go ta sama tożsamość, która z nich korzysta,
# mogłaby sama sobie je rozszerzyć. Stąd osobny katalog, osobny state i osobny właściciel.
#
# Co powstaje:
#   1. dwa konta serwisowe (plan = read-only, apply = jedyny zapisujący)
#   2. custom rola na organizacji — WĄSKA: update perimetru, BEZ create/delete
#   3. przypisania ról (member, nie binding — patrz komentarz niżej)
#   4. pula WIF + provider z attribute_condition (keyless z GitHub Actions)
#   5. IAM Deny na operacjach kasujących — twardy zakaz ponad rolami

# --- 1. konta serwisowe ---------------------------------------------------------------------------

resource "google_service_account" "plan" {
  project      = var.identity_project_id
  account_id   = "sa-vpcsc-plan"
  display_name = "VPC-SC perimeter — plan (read-only)"
  description  = "Uruchamiane przez KAŻDY pull request. Nie ma żadnego uprawnienia zapisującego."
}

resource "google_service_account" "apply" {
  project      = var.identity_project_id
  account_id   = "sa-vpcsc-apply"
  display_name = "VPC-SC perimeter — apply"
  description  = "Jedyna tożsamość modyfikująca zawartość perimetru. Wyłącznie z main + environment z reviewerami."
}

# --- 2. custom rola -------------------------------------------------------------------------------
# DLACZEGO nie predefiniowana roles/accesscontextmanager.policyEditor: daje read-write na politykach
# RAZEM z prawem usunięcia perimetru. Perimetr u nas już istnieje i ma istnieć dalej — potrzebujemy
# wyłącznie `update`. Zakres org-level jest wymuszony przez Google (uprawnienia ACM nie działają na
# folderze ani projekcie), więc zawężamy to, co da się zawęzić: zestaw operacji.

resource "google_organization_iam_custom_role" "perimeter_writer" {
  org_id      = var.org_id
  role_id     = "vpcScPerimeterWriter"
  title       = "VPC-SC perimeter writer (CI)"
  description = "Dokłada projekty i reguły do ISTNIEJĄCEGO perimetru. Bez tworzenia i kasowania perimetrów."
  stage       = "GA"

  permissions = [
    # odczyt polityki, w której żyje perimetr
    "accesscontextmanager.policies.get",
    "accesscontextmanager.policies.list",
    # odczyt stanu przed zmianą (refresh Terraform)
    "accesscontextmanager.servicePerimeters.get",
    "accesscontextmanager.servicePerimeters.list",
    # JEDYNE uprawnienie zapisujące na perimetrze (API: servicePerimeters.patch):
    # dodanie/usunięcie projektu oraz reguł ingress/egress
    "accesscontextmanager.servicePerimeters.update",
    # poziomy dostępu — warunki kontekstu (sieć korporacyjna, zarządzane urządzenie)
    "accesscontextmanager.accessLevels.get",
    "accesscontextmanager.accessLevels.list",
    "accesscontextmanager.accessLevels.create",
    "accesscontextmanager.accessLevels.update",
  ]

  # ŚWIADOMIE POMINIĘTE (nie dopisuj bez osobnej decyzji):
  #   accesscontextmanager.servicePerimeters.create   — perimetr już istnieje
  #   accesscontextmanager.servicePerimeters.delete   — kasowanie to ścieżka break-glass człowieka
  #   accesscontextmanager.accessLevels.delete        — usunięcie poziomu odcina wszystkich, którzy go używają
  #   accesscontextmanager.policies.*                 — polityka org-level nie jest naszym obiektem
}

# --- 3. przypisania ról ---------------------------------------------------------------------------
# UWAGA, NAJGROŹNIEJSZY FOOTGUN W TYM PLIKU: używamy `google_organization_iam_member`, NIGDY
# `google_organization_iam_binding`. Binding jest AUTHORITATIVE dla całej roli na organizacji — przejąłby
# ją i przy pierwszym apply usunął wszystkie inne przypisania tej roli w firmie. `member` dokłada jedno
# przypisanie i tylko je usuwa przy destroy.

locals {
  plan_org_roles = [
    "roles/accesscontextmanager.policyReader", # odczyt perimetru do terraform plan
    "roles/cloudasset.viewer",                 # pre-flight: czy projekt istnieje, czy nie jest w innym perimetrze
    "roles/compute.networkViewer",             # pre-flight: Private Google Access na podsieciach
    "roles/dns.reader",                        # pre-flight: strefa DNS kierująca googleapis.com na restricted VIP
    # Metryki i alerty perimetru (terraform/monitoring.tf) są w stanie, więc `plan` MUSI umieć je odczytać —
    # inaczej odświeżenie stanu pada na `Error when reading MonitoringAlertPolicy`, mimo że konto nic nie
    # zmienia. `viewer`, nie `editor`: czytanie do planu, zapisywanie zostaje przy `apply`. (Issue #1904)
    "roles/monitoring.viewer",
  ]
}

resource "google_organization_iam_member" "plan" {
  for_each = toset(local.plan_org_roles)

  org_id = var.org_id
  role   = each.value
  member = "serviceAccount:${google_service_account.plan.email}"
}

resource "google_organization_iam_member" "apply_perimeter_writer" {
  org_id = var.org_id
  role   = google_organization_iam_custom_role.perimeter_writer.id
  member = "serviceAccount:${google_service_account.apply.email}"
}

# Raport naruszeń dry-run czyta audit-logi. Opcjonalne, ale bez tego nie da się UDOWODNIĆ, że okno
# obserwacji było czyste — a wtedy promocja do enforced jest zgadywaniem.
resource "google_organization_iam_member" "plan_logging_viewer" {
  count = var.grant_logging_viewer ? 1 : 0

  org_id = var.org_id
  role   = "roles/logging.viewer"
  member = "serviceAccount:${google_service_account.plan.email}"
}

# Listowanie bucketa stanu — BEZ warunku, i to jest konieczne, nie niedopatrzenie.
#
# Backend GCS Terraforma przy każdym `init`/`plan` woła `storage.objects.list`, żeby wyliczyć workspace'y.
# Zasobem tego wywołania jest BUCKET, nie obiekt — więc warunek `resource.name.startsWith(".../objects/...")`
# z bindingu niżej NIGDY na nie nie pasuje i pipeline pada na:
#
#   Failed to get existing workspaces: googleapi: Error 403: ... does not have storage.objects.list access
#
# Zmierzone na żywym wdrożeniu (Issue #1904): least-privilege zawężony wyłącznie do prefiksu obiektów
# uniemożliwiał uruchomienie pipeline'u, który ten stack ma obsługiwać. `legacyBucketReader` daje dokładnie
# dwie rzeczy — `storage.buckets.get` i `storage.objects.list` — i ANI JEDNEGO prawa do treści obiektów.
# Zawężenie do prefiksu zostaje tam, gdzie realnie chroni: przy odczycie i zapisie stanu (binding niżej).
resource "google_storage_bucket_iam_member" "state_list" {
  for_each = {
    plan  = google_service_account.plan.email
    apply = google_service_account.apply.email
  }

  bucket = var.state_bucket
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${each.value}"
}

# Stan Terraform. Warunek IAM zawęża dostęp do PREFIKSU, a nie do całego bucketa — jeśli trzymacie tam
# stany innych zespołów, tamte pozostają poza zasięgiem tych kont.
resource "google_storage_bucket_iam_member" "state" {
  for_each = {
    plan  = google_service_account.plan.email
    apply = google_service_account.apply.email
  }

  bucket = var.state_bucket
  # objectAdmin, nie objectViewer: backend GCS bierze BLOKADĘ stanu (tworzy i kasuje obiekt .tflock),
  # więc sam odczyt nie wystarcza nawet dla `plan`.
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${each.value}"

  condition {
    title      = "only-vpc-sc-state-prefix"
    expression = "resource.name.startsWith(\"projects/_/buckets/${var.state_bucket}/objects/${var.state_prefix}\")"
  }
}

# --- 3b. bucket kontraktów -------------------------------------------------------------------------
# Kontrakt to wąski JSON publikowany po apply (terraform/contract.tf w repo perimetru). Dwa ROZŁĄCZNE ACL
# to rdzeń tej konstrukcji:
#   writer  = sa-vpcsc-apply, tylko na prefiksie kontraktu — pisze swój plik, nie cudze;
#   reader  = konsumenci maszynowi, READ-ONLY — konsument nie może podmienić danych, którym ufa kolejny.
#
# Gdyby konsument mógł nadpisać kontrakt, dopisałby sobie projekt do allowed_projects i jego własna walidacja
# lokalna przestałaby cokolwiek znaczyć (bramki w repo perimetru by go zatrzymały, ale zobaczyłby „zielono"
# u siebie i zdziwił się dopiero po odrzuceniu).
#
# UWAGA na zakres: repozytoria dywizji NIE potrzebują już tego grantu. Kontrakt jedzie do nich jako asset
# release'u w repo perimetru — tą samą drogą co paczka bucketowych bramek i tym samym tokenem GitHuba
# (apply.yml, krok „apply + publikacja kontraktu"). `contract_reader_groups` zostaje wyłącznie dla
# konsumentów SPOZA GitHuba: jobów w GCP, skryptów operacyjnych, hurtowni. Pusta lista jest tu poprawnym,
# najczęstszym ustawieniem — a nie brakiem konfiguracji.

# Konto `plan` musi UMIEĆ ODCZYTAĆ opublikowany kontrakt — nie żeby go konsumować, tylko dlatego, że
# `terraform plan` odświeża stan, a w stanie siedzi `google_storage_bucket_object.contract`. Bez tego prawa
# każdy plan pada na `Error 403: Permission 'storage.objects.get' denied` na buckecie kontraktów, mimo że
# konto nie ma niczego zmieniać. Zmierzone na żywym wdrożeniu (Issue #1904).
resource "google_storage_bucket_iam_member" "contract_reader_plan" {
  count = var.contracts_bucket == "" ? 0 : 1

  bucket = var.contracts_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.plan.email}"

  condition {
    title      = "only-vpc-sc-contract-prefix"
    expression = "resource.name.startsWith(\"projects/_/buckets/${var.contracts_bucket}/objects/${var.contract_prefix}\")"
  }
}

resource "google_storage_bucket_iam_member" "contract_writer" {
  count = var.contracts_bucket == "" ? 0 : 1

  bucket = var.contracts_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.apply.email}"

  condition {
    title      = "only-vpc-sc-contract-prefix"
    expression = "resource.name.startsWith(\"projects/_/buckets/${var.contracts_bucket}/objects/${var.contract_prefix}\")"
  }
}

resource "google_storage_bucket_iam_member" "contract_reader" {
  for_each = var.contracts_bucket == "" ? toset([]) : toset(var.contract_reader_groups)

  bucket = var.contracts_bucket
  # objectViewer, NIE objectAdmin: konsument czyta i nic więcej.
  role = "roles/storage.objectViewer"
  # Prefiks `group:` doklejamy TUTAJ, a zmienna przyjmuje sam adres (jej walidacja odrzuca wszystko
  # z dwukropkiem). Dzięki temu innego typu principala nie da się w tym wejściu nawet wyrazić: `allUsers`,
  # konto osoby czy `domain:` nie przechodzą, bo jedyne, co ten zasób potrafi zbudować, to grupa. Gdyby
  # prefiks wędrował w zmiennej, ta własność zniknęłaby i przed upublicznieniem kontraktu broniłby wyłącznie
  # tekstowy warunek walidacji.
  member = "group:${each.value}"

  condition {
    title      = "only-vpc-sc-contract-prefix"
    expression = "resource.name.startsWith(\"projects/_/buckets/${var.contracts_bucket}/objects/${var.contract_prefix}\")"
  }
}

# --- 4. Workload Identity Federation ---------------------------------------------------------------
# WIF to BRAMA, nie tożsamość: sam z siebie nie nadaje żadnych uprawnień. Decyduje, KTO może impersonować
# konta serwisowe powyżej — a to one mają role.

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.identity_project_id
  workload_identity_pool_id = var.wif_pool_id
  display_name              = "GitHub Actions"
  description               = "Federacja tożsamości dla repozytoriów GitHub Enterprise."
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.identity_project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = var.wif_provider_id
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"        = "assertion.sub"
    "attribute.repository"  = "assertion.repository"
    "attribute.ref"         = "assertion.ref"
    "attribute.event"       = "assertion.event_name"
    "attribute.environment" = "assertion.environment"
  }

  # NAJWAŻNIEJSZY GUARDRAIL CAŁEJ KONSTRUKCJI. Bez tego warunku (albo z `true`) DOWOLNY workflow w DOWOLNYM
  # repozytorium waszej organizacji GitHub wymienia swój token na dostęp do perimetru całej organizacji GCP.
  # To najczęstszy realny błąd konfiguracji WIF.
  attribute_condition = "assertion.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Kto może impersonować które konto — tu przebiega granica plan/apply.
#
# plan: każdy workflow z tego repozytorium (także z pull requesta) — dlatego to konto jest read-only.
resource "google_service_account_iam_member" "plan_wif" {
  service_account_id = google_service_account.plan.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# apply: WYŁĄCZNIE token niosący environment `perimeter-apply`. Token z pull requesta go nie ma, więc tą
# tożsamością nie da się posłużyć z PR-a — nawet gdyby ktoś dopisał ją do workflow.
# (Environment ma required reviewers, więc jest to jednocześnie bramka ludzka.)
resource "google_service_account_iam_member" "apply_wif" {
  service_account_id = google_service_account.apply.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.environment/${var.apply_environment}"
}

# --- 5. IAM Deny ------------------------------------------------------------------------------------
# DLACZEGO mimo wąskiej custom roli: role bywają podmieniane w pośpiechu („dajmy na chwilę policyEditor,
# żeby odblokować release"). Deny jest oceniane PRZED rolami i takiej podmiany nie da się nim obejść.

resource "google_iam_deny_policy" "vpcsc_guardrail" {
  provider = google-beta

  parent       = urlencode("cloudresourcemanager.googleapis.com/organizations/${var.org_id}")
  name         = "vpcsc-ci-no-destroy"
  display_name = "VPC-SC CI — zakaz kasowania perimetru i polityki"

  rules {
    deny_rule {
      # Format principala w polityce Deny jest INNY niż w allow ("serviceAccount:<email>"):
      # principal://iam.googleapis.com/projects/-/serviceAccounts/<email>  (zweryfikowane w docs providera).
      denied_principals = [
        "principal://iam.googleapis.com/projects/-/serviceAccounts/${google_service_account.plan.email}",
        "principal://iam.googleapis.com/projects/-/serviceAccounts/${google_service_account.apply.email}",
      ]
      denied_permissions = [
        "accesscontextmanager.googleapis.com/servicePerimeters.delete",
        "accesscontextmanager.googleapis.com/policies.delete",
      ]
    }
  }
}
