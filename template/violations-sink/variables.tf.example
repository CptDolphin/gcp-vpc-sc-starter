variable "org_id" {
  description = "Numer organizacji GCP. Sink MUSI być org-level: wpis o naruszeniu VPC-SC powstaje w projekcie-właścicielu zasobu, więc sink projektowy widziałby wyłącznie własny projekt."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{6,20}$", var.org_id))
    error_message = "org_id to sam numer (bez prefiksu organizations/)."
  }
}

variable "sink_project_id" {
  description = "Projekt, w którym powstaje kubełek docelowy. MUSI być projektem płaszczyzny sterowania POZA perimetrem — kubełek wewnątrz granicy odcinałby raport od dowodu dokładnie w chwili pierwszej promocji."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.sink_project_id))
    error_message = "sink_project_id to ID projektu (6-30 znaków), nie jego numer."
  }
}

variable "bucket_id" {
  description = "Nazwa kubełka logów. Nie używaj `_Default`/`_Required` — te są zarządzane przez Google i mają własną retencję."
  type        = string
  default     = "vpcsc-violations"

  validation {
    condition     = can(regex("^[a-z][a-z0-9._-]{2,99}$", var.bucket_id)) && !startswith(var.bucket_id, "_")
    error_message = "bucket_id: małe litery/cyfry/._- , nie zaczyna się od podkreślnika (te nazwy są zarezerwowane przez Google)."
  }
}

variable "bucket_location" {
  description = "Lokalizacja kubełka logów. ZMIERZONE 2026-08-11: organizacja ma `constraints/gcp.resourceLocations = in:eu-locations`, więc `global` jest ODRZUCANE przez org policy przy tworzeniu."
  type        = string
  default     = "eu"

  validation {
    # `global` przechodzi walidację składniową, ale w organizacji z ograniczeniem lokalizacji zasobów pada
    # dopiero na apply, komunikatem o polityce — a nie o tym, że wybrano złą wartość. Lepiej odrzucić tutaj.
    condition     = var.bucket_location != ""
    error_message = "bucket_location nie może być puste (np. `eu`, `europe-west1`, `global`)."
  }
}

variable "retention_days" {
  description = "Retencja kubełka. 30 dni = SUFIT DARMOWY Cloud Logging (ponad 30 dni kosztuje 0,01 USD/GiB/mies.) i z zapasem pokrywa okno bramki promocji (dry_run_min_days + clean_window_days z policy.yaml)."
  type        = number
  default     = 30

  validation {
    # Poniżej okna bramki kubełek cicho urywa dowód: raport za 14 dni czytałby kubełek trzymający mniej.
    # 28 = dry_run_min_days (14) + clean_window_days (14) z baseline'u; niżej nie ma sensu nawet w labie.
    # Te dwie liczby zyja w `perimeter/policy.yaml` i tu ich NIE POWTARZAMY jako literalow — powtorzona
    # liczba rozjezdza sie z deklaracja w ciszy, i dokladnie tak powstal #2083. Prog nizej jest
    # SUFITEM bezpieczenstwa, nie kopia deklaracji: ma byc z zapasem wiekszy, nie rowny.
    condition     = var.retention_days >= 21 && var.retention_days <= 3650
    error_message = "retention_days: 21-3650. Poniżej 21 kubełek nie pokrywa okna promocji, czyli dowód urywa się przed bramką."
  }
}

variable "report_service_account" {
  description = "Konto, którym `violations-report.yml` czyta dowód. Dostaje `logging.viewAccessor` WYŁĄCZNIE na widoku tego kubełka — nie na projekcie i nie na organizacji."
  type        = string

  validation {
    condition     = can(regex("^[^@]+@[^@]+\\.iam\\.gserviceaccount\\.com$", var.report_service_account))
    error_message = "report_service_account to sam e-mail konta serwisowego, bez prefiksu `serviceAccount:`."
  }
}

variable "watch_reader_service_account" {
  description = "Konto, którym `watch.yml` LICZY metryki naruszeń i zmian konfiguracji (krok `measure`, czyli `PLAN_SERVICE_ACCOUNT`). Dostaje `logging.viewAccessor` na obu widokach tego kubełka. PUSTE = obserwator nie czyta logów i alerty „ruch odrzucony” oraz „konfiguracja zmieniona poza pipeline'em” zostają bez producenta — degradacja bezpieczna i JAWNA (martwy-człowiek na brak punktu strzela), a nie cicha."
  type        = string
  default     = ""

  validation {
    condition = var.watch_reader_service_account == "" || can(
      regex("^[^@]+@[^@]+\\.iam\\.gserviceaccount\\.com$", var.watch_reader_service_account)
    )
    error_message = "watch_reader_service_account to sam e-mail konta serwisowego, bez prefiksu `serviceAccount:` (albo puste)."
  }
}

variable "network_bucket_suffix" {
  description = "Sufiks kubełka na zdarzenia sterujące Compute (utworzenie sieci VPC i maszyny). OSOBNY kubełek, nie osobny widok w kubełku naruszeń — filtr widoku wolno oprzeć WYŁĄCZNIE na źródle logu, typie zasobu, polach apphub, etykietach użytkownika i identyfikatorze logu (zmierzone: `Error 400: Invalid view filter`), a wpisy ACM i wpisy Compute mają TEN SAM identyfikator logu (`activity`). Rozłączności nie da się więc uzyskać w jednym kubełku bez zawężenia działającego widoku `-config`, czyli bez ryzyka dla licznika `config_changed_outside_pipeline`."
  type        = string
  default     = "-networks"

  validation {
    condition     = can(regex("^[a-z0-9._-]{1,40}$", var.network_bucket_suffix))
    error_message = "network_bucket_suffix: małe litery/cyfry/._- , 1-40 znaków (dokleja się do bucket_id)."
  }
}

variable "network_window_detector" {
  description = "Czy zbierać zdarzenia sterujące Compute do wykrywania okna „świeża sieć w członku egzekwowanym” (DEC-32). `false` = drugi sink, kubełek i widok NIE powstają, a obserwator nie ma czego liczyć — metryka `network_window_workload` znika, a jej martwy-człowiek NIE strzela, bo polityka alertu też się wtedy nie tworzy. Wyłączaj świadomie: okno trwa minuty i nie zostawia ŻADNEGO śladu ruchu, więc bez tego strumienia nie ma po czym poznać, że ktoś wstawił obciążenie do sieci sprzed chwili."
  type        = bool
  default     = true
}

variable "violations_reader_principals" {
  description = "Kto POZA pipeline'em raportu może czytać surowy strumień odmów (`user:`/`group:`). Świadomie WĘŻSZE niż krąg czytelników raportu: raport mówi „ten członek ma N naruszeń”, a kubełek pokazuje całej organizacji, kto próbuje sięgać gdzie. Pusta lista jest poprawnym ustawieniem."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for p in var.violations_reader_principals : can(regex("^(user|group):", p))])
    error_message = "Dozwolone wyłącznie `user:` i `group:`. Konto serwisowe raportu ma własną zmienną; inne konta maszynowe wymagają osobnej decyzji."
  }
}
