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
#   5. IAM Deny na operacjach zmieniających BYT granicy (kasowanie + tworzenie) — zakaz ponad rolami

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

# TRZECIA TOŻSAMOŚĆ, I JEDYNY POWÓD, DLA KTÓREGO ISTNIEJE: obserwator (`watch.yml`) musi ZAPISAĆ metrykę,
# a konto `plan` nie może mieć ANI JEDNEGO uprawnienia zapisującego — to niezmiennik tego stacku, nie
# szczegół. Konto `plan` może impersonować KAŻDY pull request; gdyby dostało `timeSeries.create`, autor
# dowolnego PR-a opublikowałby „budżet 5%, zaległość apply 0" i uciszył wszystkie alerty naraz, nie
# dotykając ani granicy, ani repozytorium.
#
# ZAKRES JEST CELOWO ŚMIESZNIE MAŁY: jedno uprawnienie w jednym projekcie. To konto nie czyta perimetru,
# nie czyta stanu Terraforma i nie czyta kontraktu — przejęte, potrafi wyłącznie KŁAMAĆ O TELEMETRII.
# To jest realne ryzyko (fałszywy spokój), ale o rząd wielkości mniejsze niż zapis do granicy, i dlatego
# stoi po tej stronie podziału.
resource "google_service_account" "watch" {
  count = var.monitoring_project_id == "" ? 0 : 1

  project      = var.identity_project_id
  account_id   = "sa-vpcsc-watch"
  display_name = "VPC-SC perimeter — watch (telemetria)"
  description  = "Publikuje metryki obserwatora granicy. Jedyne uprawnienie: monitoring.timeSeries.create w projekcie monitoringu."
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
    # `delete` NA POZIOMACH JEST TU OD 2026-08-13 (DEC-37) — i to jest ODWRÓCENIE wcześniejszej decyzji,
    # więc należy mu się powód, a nie sam wpis.
    #
    # Poprzedni komentarz brzmiał „usunięcie poziomu odcina wszystkich, którzy go używają". To zdanie jest
    # prawdziwe i JEDNOCZEŚNIE nie opisuje niczego, czego brak `delete` broni — bo tę własność wymuszają
    # dziś dwie inne warstwy, obie węższe: bramka OPA (DEC-33) odrzuca plan kasujący poziom, który PO
    # ZMIANIE nadal jest referowany, a samo API odmawia takiego kasowania komunikatem `you must first
    # remove the reference`. Rola nie musi więc powtarzać zakazu, który stoi piętro niżej.
    #
    # ROZSTRZYGAJĄCA ASYMETRIA: ta sama rola ma `accessLevels.update`. Przejęta tożsamość, która przepisze
    # `corp_network` na `0.0.0.0/0`, POSZERZA granicę dla KAŻDEJ reguły referującej ten poziom — cicho,
    # bez zmiany kształtu perimetru i bez zniknięcia obiektu. `delete` jest od tego SŁABSZE: API nie pozwoli
    # skasować poziomu używanego, a poziom nieużywany nie autoryzuje nikogo. Odmawianie `delete` przy
    # nadanym `update` nie kupuje bezpieczeństwa, kupuje wyłącznie stan CZĘŚCIOWO ZASTOSOWANY na końcu
    # każdego offboardingu dywizji, która przyszła z własnym poziomem (zmierzone: apply padał na OSTATNIM
    # kroku, po tym jak członek i reguła już zniknęły z granicy).
    #
    # KOSZT BRAKU: limit access leveli jest na ORGANIZACJĘ (500), nie na politykę. Katalog, który może tylko
    # rosnąć, jest wyciekiem pojemności org-plane, a nie bałaganem w nazewnictwie.
    #
    # RESIDUAL, ŚWIADOMY: zakres ACM jest org-level (wymuszony przez Google), więc to uprawnienie sięga
    # każdego NIEREFEROWANEGO poziomu w polityce organizacji — także cudzego. Warstwa IAM Deny go NIE
    # obejmuje (zmierzone Policy Troubleshooter v3: `accessLevels.delete` → allow NOT_GRANTED,
    # deny NOT_DENIED — jedna warstwa, nie dwie). Poziomy tego repozytorium są odtwarzalne z `perimeter/
    # access-levels/` jednym apply, bo `create` rola ma; cudze — nie są.
    "accesscontextmanager.accessLevels.delete",
  ]

  # ŚWIADOMIE POMINIĘTE (nie dopisuj bez osobnej decyzji):
  #   accesscontextmanager.servicePerimeters.create   — patrz DEC-37: to NIE jest „perimetr już istnieje",
  #                                                     tylko „granicy nie tworzy tożsamość automatyczna".
  #                                                     Odtworzenie perimetru po utracie ma UDOKUMENTOWANY
  #                                                     krok człowieka (docs/3-runbook-…, część D) i jest
  #                                                     dodatkowo zabronione w warstwie Deny niżej.
  #   accesscontextmanager.servicePerimeters.delete   — kasowanie to ścieżka break-glass człowieka
  #   accesscontextmanager.policies.*                 — polityka org-level nie jest naszym obiektem
}

# --- 3. przypisania ról ---------------------------------------------------------------------------
# UWAGA, NAJGROŹNIEJSZY FOOTGUN W TYM PLIKU: używamy `google_organization_iam_member`, NIGDY
# `google_organization_iam_binding`. Binding jest AUTHORITATIVE dla całej roli na organizacji — przejąłby
# ją i przy pierwszym apply usunął wszystkie inne przypisania tej roli w firmie. `member` dokłada jedno
# przypisanie i tylko je usuwa przy destroy.

locals {
  # KANAL MASZYNOWY ZA FLAGA — dokladnie tak samo jak warstwa IAM Deny nizej, i z dwoch powodow.
  # (1) To jest sciezka WYPROWADZENIA DANYCH: temat Pub/Sub z prawem publikacji dla agenta chmury.
  #     Wdrozenie, ktore go nie chce, ma go NIE MIEC, a nie „miec i nie uzywac".
  # (2) Zasoby `google_project_service` i `google_project_service_identity` WYMAGAJA POSWIADCZEN JUZ NA
  #     ETAPIE `plan` (provider konfiguruje sie leniwie, a te dwa zasoby go budza). Reszta tego stacku
  #     planuje sie BEZ poswiadczen — i to jest wlasnosc, ktorej pilnuje selftest, bo dzieki niej bramka
  #     na pull requescie nie potrzebuje dostepu do chmury. Domyslnie wylaczone = niezmiennik zostaje.
  zarzadza_tematem_alertow = (var.monitoring_project_id != "" && var.manage_alert_topic) ? 1 : 0

  # TA LISTA JEST TOŻSAMOŚCIĄ BRAMKI PRE-FLIGHTU, nie tylko planu (DEC-24) — bramka pyta kontem `plan`
  # na OBU torach, także na ścieżce apply, bo konto `apply` nie ma ani jednej z tych ról, a dokładanie ich
  # powiększyłoby zbiór uprawnień, których brak ZATRZYMUJE jedyną drogę wdrożenia. Zdjęcie którejkolwiek
  # z trzech pozycji poniżej zatrzymuje więc onboarding, i to fail-closed — czyli głośno, ale zatrzymuje.
  plan_org_roles = [
    # Niesie także `resourcemanager.projects.get/list` — czyli checki 1 i 2 pre-flightu (projekt istnieje
    # i jest ACTIVE, numer zgodny z ID, brak kolizji z cudzą konfiguracją egzekwowaną).
    "roles/accesscontextmanager.policyReader", # odczyt perimetru do terraform plan + pre-flight 1 i 2
    # NIE dla pre-flightu, mimo że tak tu stało: skrypt nie woła Cloud Asset Inventory ani razu (zmierzone).
    # DWAJ KONSUMENCI, OBAJ NIEOCZYWIŚCI — stąd ten komentarz, żeby porządkowanie ról nie zdjęło pozycji
    # „bo nikt jej nie używa":
    #   * KONTROLA POZYTYWNA SONDY GRANICY — `gcloud asset search-all-resources` jest w niej wywołaniem
    #     usługi SPOZA `restricted_services`, które ma przejść ZAWSZE. Bez niej sonda nie odróżnia
    #     „granica odmówiła" od „nie miałem prawa zapytać", czyli jej negatyw przestaje być falsyfikowalny;
    #   * DETEKTOR MARTWEGO CZŁONKA (DEC-42) — obserwator pyta tym samym uprawnieniem o `state` wszystkich
    #     projektów organizacji JEDNYM wywołaniem. To jedyna warstwa widząca, że projekt członka przestał
    #     istnieć; jej alternatywą było `resourcemanager.projects.get`, czyli NOWE nadanie na organizacji.
    # Zdjęcie tej roli nie wywala apply — gasi dwa sygnały, każdy fail-closed (sonda: brak werdyktu;
    # detektor: brak punktów i `condition_absent` polityki).
    "roles/cloudasset.viewer",     # sonda granicy + detektor martwego członka (NIE pre-flight)
    "roles/compute.networkViewer", # pre-flight 3: Private Google Access na podsieciach
    "roles/dns.reader",            # pre-flight 4: strefa DNS kierująca googleapis.com na restricted VIP
    # Metryki i alerty perimetru (terraform/monitoring.tf) są w stanie, więc `plan` MUSI umieć je odczytać —
    # inaczej odświeżenie stanu pada na `Error when reading MonitoringAlertPolicy`, mimo że konto nic nie
    # zmienia. `viewer`, nie `editor`: czytanie do planu, zapisywanie zostaje przy `apply`. (Issue #1904)
    "roles/monitoring.viewer",
  ]

  # Nazwa polityki deny (sekcja 5b) mieszka TUTAJ, a nie przy zasobie, bo używa jej też polecenie
  # weryfikacyjne z `outputs.tf`. Rozjazd tych dwóch miejsc dałby operatorowi komendę pytającą o politykę
  # o innej nazwie niż ta, którą stack tworzy — czyli stabilne `NOT_FOUND` na działającym guardrailu.
  deny_policy_name = "vpcsc-ci-no-destroy"
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

# --- 3c. monitoring perimetru ----------------------------------------------------------------------
# `terraform/monitoring.tf` w repo perimetru tworzy trzy `google_logging_metric` i dwie
# `google_monitoring_alert_policy` w projekcie `monitoring.project_id`. Zarządza nimi konto APPLY — i do
# tego dnia nie miało do nich ŻADNEGO prawa, nawet odczytu.
#
# DLACZEGO TO WYWRACAŁO APPLY, A NIE PLAN. `terraform apply` zaczyna od ODŚWIEŻENIA stanu, czyli musi
# PRZECZYTAĆ wszystko, czym zarządza — także zasoby, których w danym przebiegu nie zmienia. Konto plan
# czytało je „przypadkiem", bo ma org-level `monitoring.viewer` i `logging.viewer`; konto apply miało
# wyłącznie custom rolę na perimetrze i storage. Efekt: `plan` zielony, `apply` czerwony na
# `Error 403: Permission 'logging.logMetrics.get' denied` — zawsze, przy każdej zmianie, także takiej,
# która monitoringu w ogóle nie dotyka. To ten sam tryb awarii co przy `contract_reader_plan` wyżej
# (refresh czyta obiekt kontraktu), tylko po drugiej stronie granicy plan/apply.
#
# DLACZEGO CUSTOM ROLA, A NIE `roles/monitoring.editor` + `roles/logging.configWriter`: ta para daje
# na całym projekcie m.in. tworzenie SINKÓW logów, kubełków i uprawnień do nich — czyli ścieżkę
# wyprowadzenia logów gdzie indziej, o którą nikt nie prosił. Bierzemy dokładnie dwa typy zasobów, które
# ten stack oddaje pipeline'owi, i nic poza nimi. Ta sama zasada, co przy `vpcScPerimeterWriter`.
#
# DLACZEGO Z `delete`, skoro przy perimetrze świadomie go NIE MA: to nie jest ta sama decyzja. Metryka
# i alert są ODTWARZALNE z kodu tego repozytorium jednym apply, a część zmian pola `metric_descriptor`
# provider realizuje jako replace (destroy+create) — bez `delete` legalna zmiana konfiguracji alertu
# zatrzymywałaby się w połowie. Perimetru odtworzyć się nie da, bo `servicePerimeters.create` świadomie
# nie należy do żadnej roli tego pipeline'u; skasowanie granicy jest ścieżką człowieka i tak zostaje.
resource "google_project_iam_custom_role" "monitoring_writer" {
  count = var.monitoring_project_id == "" ? 0 : 1

  project     = var.monitoring_project_id
  role_id     = "vpcScMonitoringWriter"
  title       = "VPC-SC perimeter monitoring writer (CI)"
  description = "Pełny cykl życia metryk logowych i polityk alertów perimetru w JEDNYM projekcie. Bez sinków, kubełków i IAM."
  stage       = "GA"

  permissions = [
    # `get`/`list` są tu równie obowiązkowe jak zapis — bez nich pada REFRESH, czyli apply nie dochodzi
    # nawet do miejsca, w którym cokolwiek zmienia.
    "logging.logMetrics.get",
    "logging.logMetrics.list",
    "logging.logMetrics.create",
    "logging.logMetrics.update",
    "logging.logMetrics.delete",
    "monitoring.alertPolicies.get",
    "monitoring.alertPolicies.list",
    "monitoring.alertPolicies.create",
    "monitoring.alertPolicies.update",
    "monitoring.alertPolicies.delete",
    # KANAŁY POWIADOMIEŃ — dołożone razem z `terraform/alerts.tf`. Bez nich powtórzyłby się DOKŁADNIE ten
    # sam tryb awarii, który ta sekcja opisuje piętro wyżej: `plan` zielony (konto plan czyta je org-level
    # rolą `monitoring.viewer`), `apply` czerwony na odświeżeniu, przy KAŻDEJ zmianie — także takiej, która
    # kanałów nie dotyka. Zasada, która z tego wynika i którą trzeba stosować przy każdym nowym zasobie:
    # konto `apply` zaczyna od REFRESHU, więc musi UMIEĆ PRZECZYTAĆ wszystko, czym zarządza.
    "monitoring.notificationChannels.get",
    "monitoring.notificationChannels.list",
    "monitoring.notificationChannels.create",
    "monitoring.notificationChannels.update",
    "monitoring.notificationChannels.delete",
    # DESKRYPTORY METRYK WŁASNYCH (`custom.googleapis.com/vpcsc/*`) — deklarowane w `terraform/alerts.tf`,
    # żeby `condition_absent` miało co obserwować od chwili apply, a nie dopiero od pierwszego zapisu.
    # `update` NIE ISTNIEJE w tym API (deskryptor zmienia się przez delete+create), więc go tu nie ma.
    "monitoring.metricDescriptors.get",
    "monitoring.metricDescriptors.list",
    "monitoring.metricDescriptors.create",
    "monitoring.metricDescriptors.delete",
  ]
}

# --- 3d. telemetria obserwatora ---------------------------------------------------------------------
# `roles/monitoring.metricWriter` zamiast roli własnej — i to jest wyjątek od zasady „własna, wąska rola"
# stosowanej wyżej, więc wymaga uzasadnienia. Rola predefiniowana niesie tu DOKŁADNIE to, czego potrzeba
# do zapisu punktu metryki (`timeSeries.create` + deskryptory + typy zasobów) i ani jednego uprawnienia
# odczytu: konto `watch` nie zobaczy nawet tego, co samo napisało. Rola własna byłaby jej kopią pod inną
# nazwą, a każda kopia jest czymś, co można zapomnieć zaktualizować.
resource "google_project_iam_member" "watch_metric_writer" {
  count = var.monitoring_project_id == "" ? 0 : 1

  project = var.monitoring_project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.watch[0].email}"
}

# Rola idzie WYŁĄCZNIE do konta apply. Konto plan czyta te zasoby rolami read-only na organizacji
# i musi zostać bez ani jednego uprawnienia zapisującego — to niezmiennik całego stacku, nie szczegół.
resource "google_project_iam_member" "apply_monitoring" {
  count = var.monitoring_project_id == "" ? 0 : 1

  project = var.monitoring_project_id
  role    = google_project_iam_custom_role.monitoring_writer[0].id
  member  = "serviceAccount:${google_service_account.apply.email}"
}

# --- 3e. kanal maszynowy alertow (Pub/Sub) --------------------------------------------------------
# DLACZEGO TO STOI W STACKU CZLOWIEKA, A NIE W REPO PERIMETRU. Temat Pub/Sub to sciezka WYPROWADZENIA
# DANYCH: kto moze go utworzyc i nadac na nim prawo publikacji, ten moze zbudowac kanal wynoszacy
# telemetrie gdzie indziej. Rola `vpcScMonitoringWriter` swiadomie nie ma ani sinkow, ani kubelkow, ani
# IAM — i Pub/Sub do niej nie wchodzi z tego samego powodu. Pipeline perimetru tworzy WYLACZNIE `kanal`
# wskazujacy na ten temat (`notificationChannels.create`, ktore juz ma), a temat i grant dostaje gotowe.
#
# PO CO TEN KANAL W OGOLE, skoro nikogo nie budzi: Cloud Monitoring NIE MA publicznego API do listowania
# incydentow (`GET /v3/projects/<p>/incidents` odpowiada `404 Method not found` — sprawdzone). Bez kanalu
# maszynowego jedynym dowodem, ze alert odpalil, jest wiadomosc w cudzej skrzynce albo zrzut z konsoli —
# czyli nic, co da sie zapisac w runbooku i sprawdzic automatem. Wiadomosc Pub/Sub niesie pelny obiekt
# incydentu (`incident.state`, polityka, warunek, zaobserwowana wartosc). Drugie, trwale zastosowanie:
# to jest wejscie dla SIEM-u — alerty granicy ida tam ta sama droga co reszta telemetrii bezpieczenstwa.
# API Pub/Suba bywa WYLACZONE w projekcie, ktory dotad go nie uzywal — i wtedy `terraform apply` pada na
# `SERVICE_DISABLED`, wskazujac link do konsoli (zmierzone na wdrozeniu). Wlaczamy je tutaj, zeby wdrozenie
# od zera nie wymagalo ani jednego kliknięcia. `disable_on_destroy = false`: `terraform destroy` tego stacku
# NIE MA prawa wylaczac uslugi, z ktorej moze korzystac cokolwiek innego w tym projekcie.
resource "google_project_service" "pubsub" {
  count = local.zarzadza_tematem_alertow

  project            = var.monitoring_project_id
  service            = "pubsub.googleapis.com"
  disable_on_destroy = false
}

resource "google_pubsub_topic" "alerty" {
  count = local.zarzadza_tematem_alertow

  project = var.monitoring_project_id
  name    = var.alert_topic_name

  depends_on = [google_project_service.pubsub]
}

# Subskrypcja istnieje po to, zeby wiadomosci PRZETRWALY do momentu, w ktorym ktos po nie siegnie.
# Temat bez subskrypcji wyrzuca kazda wiadomosc natychmiast — dowod odpalenia alertu przepadalby dokladnie
# wtedy, gdy nikt nie patrzyl, czyli w jedynym przypadku, ktory ma znaczenie.
resource "google_pubsub_subscription" "alerty" {
  count = local.zarzadza_tematem_alertow

  project = var.monitoring_project_id
  name    = "${var.alert_topic_name}-ewidencja"
  topic   = google_pubsub_topic.alerty[0].id

  message_retention_duration = "604800s" # 7 dni
  retain_acked_messages      = true
  expiration_policy {
    ttl = "" # nigdy nie wygasa — subskrypcja bez ruchu przez 31 dni jest kasowana domyslnie
  }
}

# AGENT POWIADOMIEN TRZEBA WYWOLAC DO ISTNIENIA, ZANIM NADA MU SIE ROLE. Konto
# `service-<numer>@gcp-sa-monitoring-notification.iam.gserviceaccount.com` powstaje LENIWIE — dopoki nie
# istnieje, grant pada twardo: `Error 400: Service account … does not exist` (zmierzone na wdrozeniu).
#
# UWAGA NA NAZWE USLUGI: identity tworzy sie dla `monitoring.googleapis.com`, mimo ze POWSTAJACE konto
# nazywa sie `gcp-sa-monitoring-NOTIFICATION`. Intuicyjne `monitoring-notification.googleapis.com` NIE
# ISTNIEJE jako usluga (`SERVICE_CONFIG_NOT_FOUND_OR_PERMISSION_DENIED`) — sprawdzone, zeby nikt nie
# tracil na to czasu drugi raz.
resource "google_project_service_identity" "monitoring_notification" {
  count = local.zarzadza_tematem_alertow

  provider = google-beta
  project  = var.monitoring_project_id
  service  = "monitoring.googleapis.com"
}

# Agent powiadomien Monitoringu musi miec prawo PUBLIKACJI na tym temacie. Bez tego kanal powstaje,
# konsola pokazuje go jako aktywny, a nie przychodzi ANI JEDNA wiadomosc — czyli kanal, ktory wyglada
# na uzbrojony i milczy. To ten sam ksztalt awarii co pusta lista `notificationChannels`.
resource "google_pubsub_topic_iam_member" "monitoring_publisher" {
  count = local.zarzadza_tematem_alertow

  project = var.monitoring_project_id
  topic   = google_pubsub_topic.alerty[0].name
  role    = "roles/pubsub.publisher"
  # Bierzemy adres Z ZASOBU, nie sklejamy go z numeru projektu: dzieki temu zaleznosc jest jawna, a grant
  # nie powstanie, zanim konto zaczne istniec.
  member = "serviceAccount:${google_project_service_identity.monitoring_notification[0].email}"
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

# apply: WYŁĄCZNIE token niosący environment `perimeter-apply`.
#
# CZEGO TU NIE MA, a bywa tu doczytywane: gałęzi. Warunek jest o JEDNYM atrybucie — nazwie environment —
# więc sam z siebie nie odróżnia gałęzi domyślnej od dowolnej innej. Token z pull requesta nie niesie tej
# nazwy tylko dopóty, dopóki żaden job na tamtym refie jej nie zadeklaruje; job z `environment:
# perimeter-apply` na gałęzi roboczej dostanie dokładnie ten sam token. Ref odcina dopiero POLITYKA GAŁĘZI
# environment (`deployment_branch_policy`) — ustawia ją `tools/bootstrap_github.sh` i to ona, a nie ten
# `principalSet`, jest zdaniem „perimetr zmienia się wyłącznie z gałęzi domyślnej".
#
# Wymagani recenzenci na tym environment to WARSTWA OSOBNA i płatna: gdy plan GitHuba jej nie ma, ta
# konstrukcja stoi dalej, ale bez pary oczu między merge'em a mutacją granicy. Nie zakładaj jej istnienia —
# skrypt bootstrapu czyta ją z API i odmawia zgłoszenia sukcesu, gdy jej nie ma.
resource "google_service_account_iam_member" "apply_wif" {
  service_account_id = google_service_account.apply.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.environment/${var.apply_environment}"
}

# break-glass: TA SAMA tożsamość, DRUGI environment — i bez tego wiązania procedura awaryjna nie działa
# wcale, wyglądając przy tym na gotową.
#
# ZMIERZONE przy pierwszym w historii uruchomieniu `break-glass.yml` (ćwiczenie na żywej granicy): job
# deklaruje `environment: break-glass`, więc jego token OIDC niesie `attribute.environment=break-glass`,
# a `principalSet` wyżej dopasowuje wyłącznie `perimeter-apply`. Wynik:
#
#     Failed to get existing workspaces: … status code 403:
#     "Permission 'iam.serviceAccounts.getAccessToken' denied on resource (or it may not exist)"
#
# — czyli droga awaryjna nie potrafiła nawet odczytać stanu, nie mówiąc o zapisie granicy. Workflow
# istniał, environment istniał, runbook opisywał kroki, `plan` był zielony. Bramka, której nie da się
# przejść, jest w tym gorsza od jej braku: wygląda na obecną dokładnie do momentu, w którym jest potrzebna.
#
# DLACZEGO TO SAMO KONTO, A NIE DRUGIE „awaryjne". Rozdział, który kupuje osobny environment, dotyczy
# ZATWIERDZAJĄCYCH (inny zestaw ludzi o 3:00), a nie uprawnień: obie drogi zapisują ten sam obiekt tym
# samym zestawem operacji. Drugie konto serwisowe byłoby drugim kompletem grantów, ról i wiązań, który
# rozjeżdża się cicho — a ujawnia to w incydencie, czyli w jedynym momencie, w którym nie ma czasu na
# diagnozę IAM. Jedno konto, dwa dopuszczone environmenty, jeden komplet grantów do utrzymania.
#
# CZEGO TO NIE POSZERZA. Zbiór refów zdolnych wybić tożsamość zapisującą pozostaje ten sam: oba
# environmenty mają `deployment_branch_policy` zawężoną do gałęzi domyślnej (ustawia i ODCZYTUJE ją
# `tools/bootstrap_github.sh`). Poszerza się zbiór WORKFLOWÓW — o ten jeden, który i tak miał to robić.
resource "google_service_account_iam_member" "break_glass_wif" {
  service_account_id = google_service_account.apply.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.environment/${var.break_glass_environment}"
}

# watch: WYŁĄCZNIE token z gałęzi domyślnej — czyli WĘŻEJ niż `plan`, mimo że to konto robi mniej.
#
# DLACZEGO NIE `attribute.repository` jak przy `plan`: tamten zbiór dopasowuje także token z pull requesta,
# a konto `watch` MA PRAWO ZAPISU (jednej rzeczy: punktu metryki). Wystarczyłoby to, żeby autor dowolnego
# PR-a — bez merge'a, bez review — opublikował „zaległość apply 0, budżet 5%" i uciszył cztery alerty
# naraz. `attribute.ref` z tokenu pull requesta ma postać `refs/pull/N/merge`, więc nie pasuje do
# `refs/heads/<gałąź domyślna>` i ta droga jest zamknięta atrybutem, a nie regulaminem.
resource "google_service_account_iam_member" "watch_wif" {
  count = var.monitoring_project_id == "" ? 0 : 1

  service_account_id = google_service_account.watch[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.ref/${var.watch_ref}"
}

# --- 5. warstwa IAM Deny ----------------------------------------------------------------------------
# DLACZEGO mimo wąskiej custom roli: role bywają podmieniane w pośpiechu („dajmy na chwilę policyEditor,
# żeby odblokować release"). Deny jest oceniane PRZED rolami i takiej podmiany nie da się nim obejść.
#
# CO TA WARSTWA POWTARZA ZA ROLĄ, A CO NIE — i dlaczego to nie jest redundancja (DEC-37). Zakazy tutaj mają
# pokrywać zdania o BYCIE granicy, których pominięcie w roli nie utrzyma po pierwszej eskalacji uprawnień:
# „CI nie kasuje perimetru" i „CI nie tworzy perimetru". Świadomie NIE MA tu `accessLevels.delete` ani
# `servicePerimeters.update` — te są rutyną pipeline'u i wpisanie ich zablokowałoby jedyną drogę wdrożenia.
# Warstwa Deny jest więc CIENKA celowo: im więcej w niej pozycji, tym częściej trzeba nadać
# `roles/iam.denyAdmin`, żeby cokolwiek zmienić — a każde takie nadanie jest samo w sobie ryzykiem.
#
# TA WARSTWA MA WŁASNY TRYB AWARII, KTÓRY NIE RZUCA BŁĘDU: jest niewidoczna dla właściciela tego stacku.
# `iam.denypolicies.*` nie należy do żadnej z ról org-admina, a API odpowiada na brak uprawnienia tym
# samym, czym na brak zasobu — `403 denypolicies.get denied` pada zarówno wtedy, gdy polityki nie ma, jak
# i wtedy, gdy jest, ale nie wolno jej zobaczyć. Terraform dostaje to samo `403`, więc `plan` pokazuje
# `1 to add` niezależnie od stanu faktycznego, a `import` nie przechodzi. Stack, którego właściciel nie
# umie odczytać własnego guardrailu, OPISUJE ochronę zamiast jej dawać.
#
# ZMIERZONA ASYMETRIA TEJ WARSTWY (przemiał wszystkich ról predefiniowanych przez `roles?view=FULL`
# + `gcloud iam list-testable-permissions` na organizacji):
#
#   iam.denypolicies.get / .list                → rola WŁASNA: TAK. Ról predefiniowanych z tym prawem: 12,
#                                                 najwęższa `roles/iam.denyReviewer` (dokładnie te dwa).
#   iam.denypolicies.create / .update / .delete → rola WŁASNA: NIE (`customRolesSupportLevel`
#                                                 = `NOT_SUPPORTED`). Ról predefiniowanych z tym prawem:
#                                                 DOKŁADNIE JEDNA — `roles/iam.denyAdmin`.
#
# Skutek, z którym trzeba świadomie coś zrobić, a nie odkryć go przy apply: ODCZYT tej warstwy da się
# zawęzić do minimum (5a), ZAPIS — nie. Kto ma nią zarządzać, dostaje `roles/iam.denyAdmin`, czyli prawo
# skasowania KAŻDEJ polityki deny w organizacji, także takiej, która chroni coś zupełnie innego i nie ma
# z tym repozytorium nic wspólnego. Dlatego zapis stoi za flagą (5b): wdrożenie, które tego grantu nie
# chce albo jeszcze go nie ma, wyłącza zasób ŚWIADOMIE i widzi to w kodzie — zamiast zostawiać deklarację,
# której nikt nigdy nie zastosował, wyglądającą w repo dokładnie tak samo jak warstwa wdrożona.

# --- 5a. kto może CZYTAĆ warstwę deny ---------------------------------------------------------------
# Rola WŁASNA, choć `roles/iam.denyReviewer` niesie dziś dokładnie te same dwa uprawnienia i nic ponadto.
# Powód nie jest kosmetyczny: to jest rola, na której opiera się ODPOWIEDŹ na pytanie „czy guardrail stoi",
# a treść roli predefiniowanej zmienia dostawca, bez naszego diffu. Dowód, że te role rosną, jest w tym
# samym pomiarze: `roles/iam.denyAdmin` niesie 11 uprawnień, z czego 6 spoza rodziny `denypolicies`
# (`cloudasset`, `policyanalyzer`, `policysimulator`). Rola własna kosztuje dwie linijki i jest widoczna
# w tym pliku; `roles/iam.denyReviewer` zostaje poprawnym zamiennikiem tam, gdzie organizacja zabrania
# ról własnych — wtedy podmienia się `role` w przypisaniu niżej i nic więcej.
resource "google_organization_iam_custom_role" "deny_reader" {
  org_id      = var.org_id
  role_id     = "vpcScDenyReader"
  title       = "VPC-SC deny policy reader"
  description = "Odczyt polityk IAM Deny na organizacji. Rozstrzyga, czy guardrail perimetru istnieje — bez prawa zmiany czegokolwiek."
  stage       = "GA"

  permissions = [
    "iam.denypolicies.get",
    "iam.denypolicies.list",
  ]

  # ŚWIADOMIE POMINIĘTE — i tu nie chodzi o powściągliwość, tylko o to, że Google na to nie pozwala:
  #   iam.denypolicies.create / .update / .delete  →  `customRolesSupportLevel = NOT_SUPPORTED`
  # Dopisanie ich tutaj nie da zapisu, tylko wywróci apply komunikatem o nieobsługiwanym uprawnieniu.
  # Zapis do tej warstwy niesie WYŁĄCZNIE `roles/iam.denyAdmin` — patrz `manage_deny_policy`.
}

# Odczyt jest funkcją audytu, więc principale są wejściem, nie stałą. Pusta lista jest dopuszczalna
# i domyślna, ale znaczy tyle, że nikt w organizacji nie odpowie na pytanie z nagłówka sekcji 5.
resource "google_organization_iam_member" "deny_reader" {
  for_each = toset(var.deny_reader_principals)

  org_id = var.org_id
  role   = google_organization_iam_custom_role.deny_reader.id
  member = each.value
}

# --- 5b. sama polityka -------------------------------------------------------------------------------

resource "google_iam_deny_policy" "vpcsc_guardrail" {
  # Wyłączenie jest ŚWIADOME i widoczne (`manage_deny_policy = false` w tfvars z komentarzem WHY), a nie
  # milczące. Alternatywa — zostawić zasób bez flagi u wdrożenia, które nie ma `roles/iam.denyAdmin` —
  # daje stan najgorszy z możliwych: `plan` w nieskończoność mówi „1 to add", nikt tego nie applikuje,
  # a diagram architektury i README dalej twierdzą, że warstwa stoi.
  count = var.manage_deny_policy ? 1 : 0

  provider = google-beta

  parent = urlencode("cloudresourcemanager.googleapis.com/organizations/${var.org_id}")
  # IDENTYFIKATOR ZOSTAJE `vpcsc-ci-no-destroy`, mimo że od DEC-37 polityka zabrania także TWORZENIA.
  # `name` jest w tym API niezmienne — zmiana nazwy to destroy+create, czyli okno bez guardrailu, i to
  # wykonane rolą `roles/iam.denyAdmin`, którą świadomie nadaje się na chwilę. Nazwa, która lekko kłamie,
  # jest tańsza niż okno bez ochrony; rozjazd nazwy z treścią nadrabia `display_name` i ten komentarz.
  name = local.deny_policy_name
  # LIMIT `display_name` TO 63 BAJTY, NIE ZNAKI — zmierzone na żywym API przy apply DEC-37:
  #   Error 400: The provided policy's display name length (75) is longer than the maximum allowed (63)
  # …przy napisie o 73 ZNAKACH. Różnicę robił jeden em-dash (3 bajty w UTF-8); polskie znaki diakrytyczne
  # kosztują po 2. Trzymamy się ASCII w tym jednym polu, żeby liczba znaków była tu równa liczbie bajtów.
  # Tryb awarii jest paskudny: rola aktualizuje się w tym samym apply POPRAWNIE, więc stan po błędzie jest
  # ROZJECHANY (rola nowa, Deny stare) i widać to wyłącznie w kolejnym planie.
  display_name = "VPC-SC CI: zakaz tworzenia i kasowania perimetru oraz polityki"

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
        # `servicePerimeters.create` DOŁOŻONE 2026-08-13 (DEC-37) — nie dlatego, że coś zaczęło je nadawać,
        # tylko dlatego, że NIC go nie zabraniało poza pominięciem w roli. Zmierzone Policy Troubleshooter v3
        # przed tą zmianą: allow ALLOW_ACCESS_STATE_NOT_GRANTED + deny DENY_ACCESS_STATE_NOT_DENIED — czyli
        # JEDNA warstwa. Cała racja bytu Deny to przeżycie podmiany roli w pośpiechu („dajmy na chwilę
        # policyEditor, żeby odblokować release"); zdanie „granicy nie tworzy tożsamość automatyczna" musi
        # więc stać w warstwie, która taką podmianę przeżywa, a nie wyłącznie w liście uprawnień roli.
        #
        # CO TO ŁAMIE, GDYBY KIEDYŚ MIAŁO ŁAMAĆ: odtworzenie perimetru pipeline'em. To jest ŚWIADOMY skutek,
        # nie efekt uboczny — odzysk ma krok człowieka opisany w docs/3-runbook-…, część D (komenda, czas,
        # tożsamość). Deny obejmuje WYŁĄCZNIE dwa konta CI, więc człowiek z org-adminem nie jest tym objęty
        # i droga odtworzeniowa stoi otworem.
        "accesscontextmanager.googleapis.com/servicePerimeters.create",
      ]
    }
  }
}
