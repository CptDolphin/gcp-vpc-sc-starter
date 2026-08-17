# Alerty na MASZYNERIĘ granicy — czyli na to, że sam mechanizm przestał działać.
#
# CZYM TO SIĘ RÓŻNI OD `monitoring.tf`, bo to nie jest podział na dwa pliki „żeby było krócej":
#   * `monitoring.tf` obserwuje RUCH przez granicę — kogo odrzucono, kto zmienił konfigurację. Źródłem są
#     audit-logi Google: powstają same, niezależnie od tego, czy nasz pipeline żyje.
#   * ten plik obserwuje NAS. Źródłem są metryki, które publikuje `tools/perimeter_watch.py` z workflowa
#     `watch.yml`. Jeśli maszyneria padnie, źródło milknie — i właśnie dlatego pierwszy alert niżej ma
#     warunek na BRAK danych, a nie tylko na złą wartość.
#
# CZTERY OBJAWY, KTÓRE MUSZĄ KOGOŚ OBUDZIĆ, i jedno zdanie „kto to odczuwa" przy każdym:
#   1. `apply` nie doszedł  — dywizja usłyszała „zrobione", a jej projekt nie jest w granicy;
#   2. budżet atrybutów     — następny wniosek odbije się od API przy apply, czyli onboarding staje;
#   3. dryf                 — ktoś zmienił granicę poza Gitem: albo incydent, albo obejście procesu;
#   4. członek po terminie  — wpis, którego nikt nie promuje ani nie usuwa, to martwy dostęp.
#
# GDZIE TE ALERTY ŻYJĄ I CO SIĘ Z NIMI STANIE, GDY PROJEKT MONITORINGU TRAFI DO ŚRODKA GRANICY.
# Stoją w `monitoring.project_id` — tam, gdzie stan Terraform i pula WIF. To jest ŚWIADOMY wybór z jednym
# znanym kosztem: monitoring po tej samej stronie granicy co maszyneria potrafi zamilknąć razem z nią.
# Rozkład na cztery przypadki (a nie ogólne „no to trzeba osobny projekt"):
#   * alerty z `monitoring.tf` (odmowy, zmiana poza pipeline'em) czytają AUDIT-LOGI. Te powstają po stronie
#     Google i granica ich nie zatrzymuje — działają dalej;
#   * alerty z tego pliku czytają metryki pisane Z GITHUBA, czyli spoza granicy. Gdy projekt monitoringu
#     znajdzie się wewnątrz konfiguracji egzekwowanej, a `monitoring.googleapis.com` będzie na liście
#     `restricted_services`, ten zapis zostanie ODRZUCONY — i wtedy MILCZĄ TRZY Z CZTERECH (budżet, dryf,
#     wygaśnięcia), bo ich warunkiem jest ZŁA WARTOŚĆ, a złej wartości nikt nie dostarczy;
#   * CZWARTY — `vpcsc_apply_stale` — ODPALI, bo jego drugi warunek to BRAK danych. To nie jest fałszywy
#     alarm: w tym samym momencie apply też nie działa (Terraform zapisuje stan do GCS wewnątrz granicy),
#     więc „nie umiem potwierdzić, że Git == chmura" jest wtedy prawdą, a nie artefaktem;
#   * czego ŻADEN alert w tym pliku nie pokrywa: skasowanie projektu monitoringu albo wyłączenie mu
#     billingu. Wtedy nie ma czego ewaluować i nie odpali NIC — również `condition_absent`, bo warunek
#     o braku danych też potrzebuje żywego silnika ewaluacji. TĘ LUKĘ ZAMYKA PIĄTA WARSTWA, POZA TYM
#     PLIKIEM I POZA TĄ ORGANIZACJĄ: `watch.yml` wysyła po udanej publikacji metryk heartbeat do
#     dead-man's-switcha u zewnętrznego dostawcy, a ten alarmuje sam, gdy sygnał ustanie. Okno ciszy jest
#     ZWIĄZANE z `watchdog_absent_seconds` (3 h = trzy przebiegi). UWAGA NA OBIETNICĘ: to jest PRÓG,
#     nie czas do alertu. Zmierzone na realnej, nieplanowanej ciszy trwającej dobę: od ostatniej udanej
#     publikacji do pierwszego incydentu minęły CZTERY GODZINY I JEDNA MINUTA — do progu dochodzi kubełek
#     `alignment_period` (1 h) i opóźnienie ewaluacji `condition_absent`. Powrót jest szybki: incydenty
#     zamknęły się ~3,5 min po pierwszej udanej publikacji. Ustawiając check u dostawcy DMS licz więc
#     4 h, a nie 3 — i nie skracaj tego przez podniesienie progu: zmierzony NATURALNY poślizg
#     harmonogramu (cron godzinowy) sięga 2 h 24 min, czyli 80 % zapasu przed fałszywym alarmem już
#     dziś jest zjedzone. Szybsza detekcja to decyzja o KADENCJI i torze pomiaru, nie o pokrętle progu.
#     Procedura, triage i test negatywny:
#     `docs/7-alerty.md#dms-zewnetrzny`. Warstwa jest OPCJONALNA z konstrukcji — bez sekretu
#     `DMS_PING_URL` `watch` chodzi dalej, tylko głośno melduje, że jest nieuzbrojona.
# WNIOSEK, KTÓRY TRZEBA ZAPISAĆ PRZED WŁĄCZENIEM GRANICY WOKÓŁ TEGO PROJEKTU: albo `monitoring.project_id`
# zostaje poza konfiguracją egzekwowaną, albo dostaje regułę ingress dopuszczającą zapis metryk z CI.
# Wybór jest decyzją architekta, ale MUSI być świadomy — dlatego stoi tutaj, a nie w README.

locals {
  alerting_path = "${local.perimeter_dir}/alerting.yaml"

  # BRAK PLIKU = BRAK ALERTÓW, ale metryki z `monitoring.tf` zostają. Bezpieczna degradacja: wdrożenie bez
  # ustalonego dyżuru dostaje pomiar bez fikcji, że ktoś na niego patrzy. Atrapa z KOMPLETEM kluczy (a nie
  # `null`) z tego samego powodu, co w `monitoring.tf`: `terraform validate` sprawdza wyrażenia w atrybutach
  # także wtedy, gdy `count = 0` i nie powstanie ani jedna instancja.
  alerting_enabled = local.monitoring_enabled && fileexists(local.alerting_path)

  # `merge(ATRAPA, PLIK)`, A NIE `warunek ? PLIK : ATRAPA` — i to jest poprawka wymuszona pomiarem.
  #
  # Konstrukcja warunkowa wymagała, żeby OBIE gałęzie miały IDENTYCZNY zestaw kluczy najwyższego poziomu.
  # Dopóki plik miał dokładnie te klucze co atrapa, działało. Ale klucz OPCJONALNY łamie to w OBIE strony
  # naraz i nie da się tego uratować doborem atrapy — zmierzone na `violations_source`:
  #   * jest w pliku, nie ma w atrapie  -> „Inconsistent conditional result types"
  #   * jest w atrapie, nie ma w pliku  -> ten sam błąd, tylko z odwróconymi rolami
  # Do tego komunikat wskazuje `channels`/`machine`, czyli miejsce bez związku z przyczyną, więc następna
  # osoba szuka błędu w kanale maszynowym.
  #
  # `merge` bierze SUMĘ kluczy i nie żąda zgodności typów, a `try` wokół `file()` załatwia brak pliku.
  # Wartości z pliku wygrywają z atrapą, więc zachowanie przy włączonych alertach jest bez zmian; przy
  # wyłączonych zostaje komplet pustych kluczy, dokładnie jak dotąd. Klucz opcjonalny wolno teraz dodać
  # do schematu bez dotykania tego wyrażenia — a to była dotąd mina na każdą kolejną zmianę.
  alerting = merge({
    schema_version = 1
    channels = {
      capacity = { email = "" }
      security = { email = "" }
    }
    # `machine` NIE wchodzi do atrapy: jest OPCJONALNY, a `try` niżej i tak go nie wymaga. Atrapa opisuje
    # klucze OBOWIĄZKOWE. Od czasu `merge` nie jest to już wymóg techniczny, tylko dokumentacyjny: atrapa
    # ma czytać się jak lista tego, bez czego alerting nie ma sensu.
    thresholds = {
      attribute_budget_percent = 70
      days_to_limit_warning    = 90
      days_to_limit_critical   = 30
      apply_pending_seconds    = 3600
      watchdog_absent_seconds  = 10800
      drift_persist_seconds    = 3600
    }
    runbook_base_url = ""
    # Atrapa `violations_source` jest tu po to, żeby `local.zrodlo_naruszen` miał co czytać, gdy pliku
    # nie ma w ogóle. Pusty `project_id` znaczy „brak źródła" i zeruje `naruszenia_count`.
    violations_source = {
      project_id = ""
    }
    # BEZ `warunek ? ... : {}` wokół dekodu — to był ten sam błąd w nowym przebraniu: gałąź `{}` też jest
    # obiektem o INNYM zestawie kluczy niż zdekodowany plik. `try` sam w sobie nie uzgadnia typów (zwraca
    # to, co się powiodło), więc wystarcza i za brak pliku, i za jego niepoprawność. Bramką „czy alerty
    # w ogóle powstają" jest `alert_count`, a nie kształt tego wyrażenia.
  }, try(yamldecode(file(local.alerting_path)), {}))

  alert_count = local.alerting_enabled ? 1 : 0
  progi       = local.alerting.thresholds

  # ŹRÓDŁO ODMÓW I ZMIAN KONFIGURACJI. Dzięki `merge` wyżej czyta się to zwyczajnie: brak sekcji w pliku
  # znaczy pusty `project_id` z atrapy, czyli „brak źródła".
  #
  # Ten jeden `!= ""` decyduje o istnieniu DWÓCH polityk alertu, i to jest wybór między dwoma złami.
  # Bez sekcji `violations_source` nie ma kto publikować metryk odmów i zmian ACM — a polityka bez
  # producenta nie milczy, tylko chodzi WIECZNIE na martwym-człowieku. Stały fałszywy alarm uczy
  # dyżurnego klikać „potwierdź” na całej kategorii, w której siedzi jedyny alert mówiący „ktoś jest
  # blokowany TERAZ”. Brak alertu jest gorszy niż alert, ale LEPSZY niż alert, który zawsze kłamie —
  # i jest widoczny: `docs/7-alerty.md` nazywa wtedy oba sygnały jako niewdrożone.
  zrodlo_naruszen  = try(local.alerting.violations_source.project_id, "")
  naruszenia_count = local.alerting_enabled && local.zrodlo_naruszen != "" ? 1 : 0

  # DETEKTOR OKNA ŚWIEŻEJ SIECI (DEC-32) ma WŁASNY warunek istnienia, a nie `naruszenia_count`, i to
  # jest ta sama zasada, co wyżej: polityka bez producenta chodzi wiecznie na martwym-człowieku. Jego
  # producent potrzebuje TRZECIEGO widoku — z osobnego kubełka, z osobnym grantem — więc może go zabraknąć
  # także wtedy, gdy widoki naruszeń i zmian ACM są skonfigurowane (np. wdrożenie z `network_window_detector
  # = false` w stacku sinka). Wspólny licznik tworzyłby wtedy alert, którego nikt nie zasila.
  zrodlo_sieci = try(local.alerting.violations_source.network_view, "")
  sieci_count  = local.naruszenia_count > 0 && local.zrodlo_sieci != "" ? 1 : 0

  # Runbook jest KONFIGURACJĄ, bo docelowe repozytorium ma inny adres niż starter. Kotwice (`#…`) są stałe
  # i pilnuje ich selftest — alert wskazujący na nieistniejącą kotwicę ląduje na początku dokumentu, czyli
  # o 3:00 daje spis treści zamiast procedury.
  runbook = "${local.alerting.runbook_base_url}/7-alerty.md"

  # NAZWY METRYK W JEDNYM MIEJSCU. Drugi ich egzemplarz jest w `tools/perimeter_watch.py` (producent) —
  # rozjazd tych dwóch list to alert na metrykę, której nikt nie pisze, czyli cisza wyglądająca na spokój.
  # Selftest porównuje oba pliki i to jest jedyna bramka, która ten rozjazd łapie.
  metryka = {
    apply_pending  = "custom.googleapis.com/vpcsc/apply_pending_seconds"
    budzet_procent = "custom.googleapis.com/vpcsc/attribute_budget_percent"
    budzet_dni     = "custom.googleapis.com/vpcsc/attribute_budget_days_to_limit"
    dryf           = "custom.googleapis.com/vpcsc/drift_resources"
    wygasli        = "custom.googleapis.com/vpcsc/members_expired"

    # TRZY PONIŻSZE SĄ `custom.`, A NIE `logging.googleapis.com/user/` — I TO JEST ISTOTA POPRAWKI #2000.
    # Stały tu wcześniej metryki log-based i miały ZERO serii przy realnych zdarzeniach, bo metryka
    # log-based liczy wyłącznie wpisy PRZYJĘTE przez Log Router swojego projektu, a te wpisy powstają
    # w logu projektu członkowskiego (naruszenia) albo organizacji (zmiany ACM) i docierają tutaj
    # SINKIEM — czyli do magazynu, nie na wejście. Zmierzone parą kontrolną, szczegóły w `monitoring.tf`.
    # Producentem jest `watch.yml`, ten sam, który od pierwszego dnia ma dane na czterech metrykach wyżej.
    naruszenia_enforced   = "custom.googleapis.com/vpcsc/violations_enforced"
    naruszenia_dry_run    = "custom.googleapis.com/vpcsc/violations_dry_run"
    zmiany_poza_pipelinem = "custom.googleapis.com/vpcsc/config_changed_outside_pipeline"

    # OKNO ŚWIEŻEJ SIECI (DEC-32). `sieci_egzekwowane` jest publikowana i CELOWO nie ma polityki alertu:
    # utworzenie sieci VPC w projekcie członkowskim jest czynnością legalną i częstą, więc alert na nią
    # byłby szumem — a wyciszony szum zabiera ze sobą sygnał, który siedzi w tej samej kategorii. Alert
    # stoi wyłącznie na `sieci_z_obciazeniem`, czyli na złamaniu kolejności: obciążenie w sieci, która
    # jeszcze nie jest dla granicy „wewnątrz".
    sieci_egzekwowane   = "custom.googleapis.com/vpcsc/network_inserts_enforced"
    sieci_z_obciazeniem = "custom.googleapis.com/vpcsc/network_window_workload"

    # MARTWY CZŁONEK GRANICY (DEC-42). JEDNA metryka i DWIE serie po etykiecie `state`, bo „stanu nie
    # odczytano" jest innym zdaniem o świecie niż „stan jest inny niż ACTIVE". Zlanie ich w jedną liczbę
    # zamieniałoby ślepotę w rozpoznanie — a to jest dokładnie ten tryb awarii, który ta metryka tropi.
    czlonkowie_nieaktywni = "custom.googleapis.com/vpcsc/members_not_active"
  }

  # Kanały: lista z `policy.yaml` (kanały założone poza tym repo) PLUS kanał zarządzany tutaj. Konkatenacja,
  # a nie podmiana — wdrożenie, które ma już własny PagerDuty, nie traci go przez włączenie tego pliku.
  kanal_pojemnosc = local.alerting_enabled ? concat(
    local.monitoring.notification_channels,
    [google_monitoring_notification_channel.capacity[0].id],
    local.ma_kanal_maszynowy ? [google_monitoring_notification_channel.machine[0].id] : [],
  ) : local.monitoring.notification_channels

  # KANAŁ MASZYNOWY (Pub/Sub) — opcjonalny, dokładany do OBU list. Nie budzi nikogo: odpowiada na pytanie
  # „czym udowodnić, że alert odpalił". Cloud Monitoring nie ma publicznego API do listowania incydentów
  # (`/v3/projects/X/incidents` → 404 `Method not found`, sprawdzone), więc bez niego jedynym dowodem
  # zadziałania alertu jest wiadomość w cudzej skrzynce — czyli nic, co da się sprawdzić automatem.
  # Temat tworzy `iam-bootstrap` (stack człowieka) razem z prawem publikacji dla agenta powiadomień;
  # ten stack tworzy WYŁĄCZNIE kanał, więc rola CI nie rośnie o ani jedno uprawnienie do Pub/Suba.
  kanal_maszynowy    = try([local.alerting.channels.machine.pubsub_topic], [])
  ma_kanal_maszynowy = local.alerting_enabled && length(local.kanal_maszynowy) > 0

  kanal_bezpieczenstwo = local.alerting_enabled ? concat(
    local.monitoring.notification_channels,
    [google_monitoring_notification_channel.security[0].id],
    local.ma_kanal_maszynowy ? [google_monitoring_notification_channel.machine[0].id] : [],
  ) : local.monitoring.notification_channels

  # OBA KANAŁY — wyłącznie dla odmowy w trybie egzekwowanym (`monitoring.tf`). To jedyny alert w tym
  # systemie, przy którym w chwili odpalenia NIE DA SIĘ powiedzieć, czy to awaria (legalny przepływ
  # zablokowany), czy sukces kontroli (próba wyniesienia danych) — pierwszym krokiem runbooka jest
  # właśnie to rozstrzygnąć. Wysłanie go tylko do jednego odbiorcy znaczy, że w połowie przypadków
  # rozstrzyga go osoba, która nie ma jak podjąć decyzji. `distinct`, bo obie listy niosą kanały
  # z `policy.yaml` i bez tego trafiłyby tam dwa razy.
  kanal_oba = distinct(concat(local.kanal_pojemnosc, local.kanal_bezpieczenstwo))
}

# --- KANAŁY POWIADOMIEŃ ----------------------------------------------------------------------------
#
# DWA, NIE JEDEN. Alert pojemnościowy czyta się w godzinach pracy i planuje się wokół niego robotę; alert
# o zmianie granicy poza Gitem jest sygnałem, że ktoś obszedł proces. Jeden kanał na oba kończy się zawsze
# tak samo: odbiorca uczy się ignorować całą kategorię, bo dziewięć na dziesięć wiadomości nie wymaga
# reakcji — i przegapia dziesiątą.
#
# `verification_status` JEST W STANIE TERRAFORMA I NIE JEST DOWODEM NA NIC (DEC-28). Pole przychodzi puste,
# bo API go NIE ZWRACA: `verificationStatus` to enum proto3, a jego wartość domyślna
# `VERIFICATION_STATUS_UNSPECIFIED` nie serializuje się do odpowiedzi. Google opisuje tę wartość jako „stan
# nieznany, pominięty ALBO NIEADEKWATNY (kanały, które weryfikacji ani nie wspierają, ani nie wymagają)" —
# więc pusta wartość NIE ZNACZY „niezweryfikowany". Zmierzone na żywym API: jawna maska pola też go nie
# zwraca, a po `:sendVerificationCode` (HTTP 200) pole nadal nie istnieje, choć `UNVERIFIED` jest wartością
# niedomyślną i musiałaby się wtedy pojawić. Terraform tego pola nie ustawia i ustawić nie może —
# jest `output only` i „illegal to specify a non-default value in Create() or Update()".
#
# Tryb awarii, przed którym to ostrzeżenie miało chronić, JEST REALNY (polityka z kanałem, który nic nie
# dostarcza), tylko wykrywa się go inaczej — `python3 tools/kanaly_check.py --project <projekt>`: czy każda
# polityka `CRITICAL` ma kanał, którego doręczenie potwierdza maszyna. Doręczenie na skrzynkę potwierdza
# wyłącznie człowiek, po teście negatywnym z `docs/7-alerty.md`.

resource "google_monitoring_notification_channel" "capacity" {
  count = local.alert_count

  project      = local.monitoring.project_id
  display_name = "VPC-SC — pojemnosc i higiena granicy"
  description  = "Budżet atrybutów, członkowie po review_by, apply który nie doszedł. Odbiorca planuje wokół tego pracę, nie wstaje w nocy."
  type         = "email"

  labels = {
    email_address = local.alerting.channels.capacity.email
  }

  # `force_delete` świadomie NIE jest ustawione: kanał wpięty w politykę alertu ma się NIE dać skasować
  # jednym `terraform destroy`, bo to zostawia polityki bez odbiorcy i nic tego nie zgłasza.
}

resource "google_monitoring_notification_channel" "machine" {
  count = local.ma_kanal_maszynowy ? 1 : 0

  project      = local.monitoring.project_id
  display_name = "VPC-SC — kanal maszynowy (Pub/Sub)"
  description  = "Pelny obiekt incydentu na temat Pub/Sub. Dowod odpalenia alertu mozliwy do sprawdzenia automatem oraz wejscie dla SIEM-u. Nie budzi nikogo."
  type         = "pubsub"

  labels = {
    # `try(...)`, a nie `[0]` — DOKŁADNIE ten sam powód, co przy atrapie konfiguracji wyżej: `terraform
    # validate` sprawdza wyrażenia w atrybutach zasobu również wtedy, gdy `count = 0` i nie powstanie ani
    # jedna instancja. Indeks na pustej liście daje wtedy twardy błąd („the collection has no elements")
    # i wywraca walidację wdrożenia, które tego kanału świadomie nie ma. Zmierzone.
    topic = try(local.kanal_maszynowy[0], "")
  }
}

resource "google_monitoring_notification_channel" "security" {
  count = local.alert_count

  project      = local.monitoring.project_id
  display_name = "VPC-SC — granica bezpieczenstwa"
  description  = "Dryf granicy, zmiana poza pipeline'em, odmowa w trybie egzekwowanym. Sygnał obejścia procesu albo incydentu — inny odbiorca niż alerty pojemnościowe."
  type         = "email"

  labels = {
    email_address = local.alerting.channels.security.email
  }
}

# --- DESKRYPTORY METRYK ----------------------------------------------------------------------------
#
# DLACZEGO DEKLARUJEMY JE JAWNIE, skoro pierwszy zapis `timeSeries.create` i tak utworzyłby je sam:
#   * deskryptor utworzony automatycznie bierze typ i jednostkę Z PIERWSZEGO ZAPISU. Literówka w skrypcie
#     zostaje wtedy w organizacji na zawsze jako osobna metryka, a alert dalej patrzy na pustą;
#   * `condition_absent` (watchdog niżej) potrzebuje metryki, która ISTNIEJE. Deskryptor zadeklarowany
#     w Terraformie powstaje przy apply, czyli ZANIM cokolwiek zacznie pisać;
#   * to jest dokumentacja jednostek w miejscu, w którym patrzy się na wykres — `1` vs `s` vs `d` decyduje
#     o tym, czy oś ma sens.
#
# UWAGA NA `labels`: muszą zgadzać się CO DO KLUCZA z tym, co pisze `perimeter_watch.py`. Zapis z etykietą
# spoza deskryptora jest odrzucany przez API — a odrzucony zapis wygląda w Cloud Monitoring identycznie jak
# „nic się nie dzieje".

resource "google_monitoring_metric_descriptor" "apply_pending" {
  count = local.alert_count

  project      = local.monitoring.project_id
  type         = local.metryka.apply_pending
  display_name = "VPC-SC: sekundy od zmergowanej, niezastosowanej zmiany granicy"
  description  = "0 = konfiguracja w Git jest zastosowana. >0 = commit dotykający perimeter/ lub terraform/ czeka na udany przebieg apply."
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  unit         = "s"
}

resource "google_monitoring_metric_descriptor" "budzet_procent" {
  count = local.alert_count

  project      = local.monitoring.project_id
  type         = local.metryka.budzet_procent
  display_name = "VPC-SC: wykorzystanie budżetu atrybutów"
  description  = "Procent limitu atrybutów zużyty przez konfigurację. Limit jest NA KONFIGURACJĘ, więc `spec` i `status` mają własne serie."
  metric_kind  = "GAUGE"
  value_type   = "DOUBLE"
  unit         = "%"

  labels {
    key         = "config"
    value_type  = "STRING"
    description = "spec (dry-run) albo status (egzekwowana) — dwa NIEZALEŻNE budżety po 6000 atrybutów."
  }
}

resource "google_monitoring_metric_descriptor" "budzet_dni" {
  count = local.alert_count

  project      = local.monitoring.project_id
  type         = local.metryka.budzet_dni
  display_name = "VPC-SC: dni do wyczerpania budżetu atrybutów"
  description  = "(limit - użyte) / nachylenie z ostatnich 30 dni. Brak wzrostu albo za krótka historia => 3650 (wartość sentynelowa: nie da się prognozować, więc nie alarmujemy)."
  metric_kind  = "GAUGE"
  value_type   = "DOUBLE"
  unit         = "d"

  labels {
    key         = "config"
    value_type  = "STRING"
    description = "spec albo status."
  }
}

resource "google_monitoring_metric_descriptor" "dryf" {
  count = local.alert_count

  project      = local.monitoring.project_id
  type         = local.metryka.dryf
  display_name = "VPC-SC: zasoby rozjechane między Gitem a chmurą"
  description  = "Liczba zasobów, które `terraform plan` chce zmienić przy CZYSTYM repozytorium. Publikowana jako 0, gdy trwa niezastosowana zmiana z Gita — wtedy niepusty plan jest oczekiwany i mówi o nim alert `apply`."
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  unit         = "1"
}

resource "google_monitoring_metric_descriptor" "wygasli" {
  count = local.alert_count

  project      = local.monitoring.project_id
  type         = local.metryka.wygasli
  display_name = "VPC-SC: członkowie po dacie review_by"
  description  = "Liczba wpisów w perimeter/projects.yaml, których `review_by` już minął — dostęp, którego nikt nie potwierdził."
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  unit         = "1"
}

# --- MARTWY CZŁONEK GRANICY (DEC-42) ---------------------------------------------------------------
#
# Deskryptor stoi przy `alert_count`, a nie przy `naruszenia_count`, i to jest rozstrzygnięcie o źródle:
# producent tej liczby nie potrzebuje ŻADNEGO widoku sinka. Czyta żywą granicę (ACM) i jedno wywołanie
# Asset Inventory na organizację — czyli dokładnie te dwa uprawnienia, które konto planu już ma. Wdrożenie
# bez `violations_source` dostaje ten sygnał tak samo jak wdrożenie kompletne.
#
# ETYKIETA `state` MA ZBIÓR ZAMKNIĘTY (`not_active`, `unreadable`) i producent publikuje OBIE serie
# w każdym przebiegu, także z zerem. To jest warunek, żeby `condition_absent` niżej cokolwiek znaczył:
# seria, która powstaje i znika razem ze zdarzeniem, robi ze zdrowej ciszy nieodróżnialną awarię.
resource "google_monitoring_metric_descriptor" "czlonkowie_nieaktywni" {
  count = local.alert_count

  project      = local.monitoring.project_id
  type         = local.metryka.czlonkowie_nieaktywni
  display_name = "VPC-SC: członkowie granicy bez potwierdzonego stanu ACTIVE"
  description  = "Ilu członków perimetru (numery z `spec.resources` + `status.resources`) NIE MA potwierdzonego stanu ACTIVE. Etykieta `state` rozdziela werdykt od ślepoty: `not_active` = stan odczytany i inny niż ACTIVE, `unreadable` = stanu nie odczytano. BRAK punktu, a nie zero, znaczy „nie sprawdzono”."
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  unit         = "1"

  labels {
    key         = "state"
    value_type  = "STRING"
    description = "not_active (odczytany stan inny niż ACTIVE, np. DELETE_REQUESTED) albo unreadable (stanu NIE odczytano — nigdy nie znaczy OK)."
  }
}

# --- deskryptory metryk liczonych z WIDOKÓW SINKA (#2000) -------------------------------------------
# Powstają razem z politykami (`naruszenia_count`), a nie z całym alertingiem: bez sekcji `violations_source`
# nie ma producenta, więc deskryptor byłby pustym obiektem sugerującym pomiar, którego nikt nie robi.
#
# `GAUGE`, a nie `DELTA`: producent publikuje LICZBĘ ZDARZEŃ W OKNIE odczytaną wstecz z widoku, a nie
# przyrost od poprzedniego punktu. `DELTA` znaczyłoby, że Monitoring może te punkty sumować między sobą —
# a one się NAKŁADAJĄ (okno 5400 s przy kadencji 3600 s), więc suma zawyżałaby o część wspólną.

resource "google_monitoring_metric_descriptor" "naruszenia_enforced" {
  count = local.naruszenia_count

  project      = local.monitoring.project_id
  type         = local.metryka.naruszenia_enforced
  display_name = "VPC-SC: odmowy w trybie egzekwowanym"
  description  = "Liczba odmów EGZEKWOWANYCH w oknie obserwatora, liczona z widoku sinka. Publikowana także jako 0 — brak punktu znaczy awarię obserwatora, nie brak odmów."
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  unit         = "1"
}

resource "google_monitoring_metric_descriptor" "naruszenia_dry_run" {
  count = local.naruszenia_count

  project      = local.monitoring.project_id
  type         = local.metryka.naruszenia_dry_run
  display_name = "VPC-SC: naruszenia dry-run"
  description  = "Liczba naruszeń dry-run w oknie obserwatora — wywołania, które przestaną działać po promocji. ŚWIADOMIE bez polityki alertu: konsumentem jest raport tygodniowy i bramka promocji."
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  unit         = "1"
}

resource "google_monitoring_metric_descriptor" "zmiany_poza_pipelinem" {
  count = local.naruszenia_count

  project      = local.monitoring.project_id
  type         = local.metryka.zmiany_poza_pipelinem
  display_name = "VPC-SC: zmiany granicy poza pipeline'em"
  description  = "Liczba operacji ACM zmieniających granicę, wykonanych tożsamością INNĄ niż konto apply. Liczona z widoku Admin Activity w kubełku sinka — w logu organizacji, którego metryka log-based zobaczyć nie może."
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  unit         = "1"
}

# --- DESKRYPTORY OKNA ŚWIEŻEJ SIECI (DEC-32) -------------------------------------------------------
#
# TE DWA STOJĄ TU Z TEGO SAMEGO POWODU CO OSIEM WYŻEJ — ale zostały dołożone o jeden pull request
# później i ta różnica wywróciła odtworzenie po awarii. ZMIERZONE (apply `31679291426`, 2026-08-13):
# `Plan: 19 to add, 0 to change, 0 to destroy`, a na polityce okna
#
#   Error 404: Cannot find metric(s) that match type = "custom.googleapis.com/vpcsc/network_window_workload".
#   If a metric was created recently, it could take up to 10 minutes to become available.
#
# KOMUNIKAT KIERUJE W ZŁĄ STRONĘ i to jest połowa defektu: mówi o PROPAGACJI świeżo utworzonej metryki,
# a tej metryki nie było w ogóle. Odczyt z API tuż po awarii pokazał OSIEM deskryptorów
# `custom.googleapis.com/vpcsc/*` i ani jednego z tej pary. Bez deskryptora metryka własna powstaje
# dopiero przy PIERWSZYM zapisie punktu — czyli po pierwszym przebiegu obserwatora, który sam potrzebuje
# widoku z kubełka stawianego przez `violations-sink/`, czyli stack applikowany przez CZŁOWIEKA z org-level
# `roles/logging.configWriter`. Odtworzenie od zera w kolejności „repo perimetru najpierw" padało więc
# ZAWSZE, a `depends_on` przez granicę dwóch stanów Terraforma nie istnieje.
#
# NIEZMIENNIK, KTÓRY Z TEGO ZOSTAJE (DEC-35): polityka alertu i deskryptor jej metryki należą do TEGO
# SAMEGO stacku. Producent odpowiada za PUNKTY, nigdy za ISTNIENIE metryki. Bramka: selftest §alerty.
#
# DRUGI SKUTEK, GROŹNIEJSZY OD CZERWONEGO APPLY: bez deskryptora martwy-człowiek tej polityki
# (`condition_absent` w `monitoring.tf`) był MARTWY SAM. Metryka, do której nigdy nic nie napisano, nie
# jest „nieobecna" — jest NIEZNANA, a warunek na nieobecność nie odpala (ta sama własność, którą trzy
# akapity wyżej opisujemy jako powód deklarowania deskryptorów). Obserwator świadomie NIE publikuje zera,
# gdy nie ma czego policzyć (fail-closed), więc dokładnie ten przypadek, dla którego ten martwy-człowiek
# powstał — detektor bez źródła — dawał ciszę wyglądającą na „nikt nie łamie kolejności".

resource "google_monitoring_metric_descriptor" "sieci_egzekwowane" {
  count = local.sieci_count

  project      = local.monitoring.project_id
  type         = local.metryka.sieci_egzekwowane
  display_name = "VPC-SC: sieci VPC utworzone w członkach egzekwowanych"
  description  = "Liczba sieci VPC utworzonych w oknie obserwatora w projektach należących do konfiguracji EGZEKWOWANEJ. Kontekst dla licznika poniżej — ŚWIADOMIE bez polityki alertu, bo tworzenie sieci jest czynnością legalną i częstą."
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  unit         = "1"
}

resource "google_monitoring_metric_descriptor" "sieci_z_obciazeniem" {
  count = local.sieci_count

  project      = local.monitoring.project_id
  type         = local.metryka.sieci_z_obciazeniem
  display_name = "VPC-SC: obciążenie w sieci młodszej niż okno dojrzewania"
  description  = "Do ilu z tych sieci wstawiono maszynę PRZED upływem okna dojrzewania (złamanie kolejności z DEC-32). BRAK punktu, a nie zero, znaczy „detektor nie miał czego policzyć” — przejmuje to martwy-człowiek polityki."
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  unit         = "1"
}

# --- PROPAGACJA DESKRYPTORÓW ---------------------------------------------------------------------
#
# ZMIERZONE NA PIERWSZYM APPLY, nie przewidziane: dwie polityki odbiły się od API komunikatem
#
#   Error 404: Cannot find metric(s) that match type = "custom.googleapis.com/vpcsc/…".
#   If a metric was created recently, it could take up to 10 minutes to become available.
#
# mimo że Terraform utworzył te deskryptory chwilę wcześniej, W TYM SAMYM przebiegu. Cloud Monitoring
# potwierdza utworzenie deskryptora, zanim stanie się on widoczny dla walidacji polityk alertów — więc
# `depends_on` NIE WYSTARCZA: zależność jest spełniona, a zasób jeszcze nie istnieje dla konsumenta.
#
# Skutek bez tego bloku dotyczy WYŁĄCZNIE wdrożenia od zera i jest cichy w najgorszy sposób: część polityk
# powstaje, część nie, apply kończy się czerwono — a operator, który po prostu ponowi przebieg, dostanie
# zielono i nigdy się nie dowie, że pierwszy raz nie zadziałał. To jest dokładnie ta klasa błędu, którą
# ten plik ma tropić, tylko o piętro niżej.
#
# 120 s pokrywa przypadek zaobserwowany (deskryptory były widoczne po kilkudziesięciu sekundach). Google
# deklaruje do 10 minut — jeśli kiedyś trafi się gorszy przebieg, PONOWIENIE APPLY JEST BEZPIECZNE, bo
# deskryptory są już utworzone i `time_sleep` odczeka ponownie tylko przy pierwszym tworzeniu.
resource "time_sleep" "deskryptory_widoczne" {
  count = local.alert_count

  create_duration = "120s"

  depends_on = [
    google_monitoring_metric_descriptor.apply_pending,
    google_monitoring_metric_descriptor.budzet_procent,
    google_monitoring_metric_descriptor.budzet_dni,
    google_monitoring_metric_descriptor.dryf,
    google_monitoring_metric_descriptor.wygasli,
    google_monitoring_metric_descriptor.czlonkowie_nieaktywni,
    # Trzy deskryptory z widoków sinka. Listy `count = 0` są tu legalne i nic nie wnoszą, więc wdrożenie
    # bez `violations_source` czeka dokładnie tyle samo — a to jest właściwe: 120 s raz, przy pierwszym
    # apply, jest tańsze niż rozgałęzianie tego bloku.
    google_monitoring_metric_descriptor.naruszenia_enforced,
    google_monitoring_metric_descriptor.naruszenia_dry_run,
    google_monitoring_metric_descriptor.zmiany_poza_pipelinem,
    # Para okna świeżej sieci. Ma tu być z tego samego powodu co pozostałe, a nie „bo pasuje": to jej
    # brak wywrócił odtworzenie od zera (`31679291426`) — polityka okna czeka na `time_sleep`, więc bez
    # tych dwóch pozycji czekałaby na propagację deskryptorów, których nikt nie tworzy.
    google_monitoring_metric_descriptor.sieci_egzekwowane,
    google_monitoring_metric_descriptor.sieci_z_obciazeniem,
  ]
}

# --- ALERT 1: `apply` nie doszedł ------------------------------------------------------------------
#
# KTO TO ODCZUWA: dywizja, która zmergowała wniosek i usłyszała „zrobione", a jej projekt nie jest
# w granicy — i każda następna decyzja o promocji liczy stan, którego w chmurze nie ma.
#
# DLACZEGO DWA WARUNKI, A NIE NASŁUCH NA „workflow failed". Tryby awarii są trzy i tylko pierwszy z nich
# generuje zdarzenie „nieudany przebieg":
#   (a) przebieg PADŁ            — jest zdarzenie, łapie je każde rozwiązanie;
#   (b) przebieg SIĘ NIE ODPALIŁ — nie ma ŻADNEGO zdarzenia. Zły filtr `paths`, wyłączone Actions, awaria
#       GitHuba, brak środków na minuty. Nasłuch nie ma czego usłyszeć;
#   (c) przebieg WISI            — zdarzenia też nie ma i nie będzie przez 6 godzin (limit joba), a przy
#       environment z wymaganym recenzentem — przez 30 dni.
# Wszystkie trzy dają ten sam OBJAW: minął czas, a zmiana z Gita nie jest w chmurze. Warunek jest więc
# o WIEKU niezastosowanej zmiany, nie o zdarzeniu — jedna reguła, trzy tryby. To jest dead-man's-switch:
# udany apply zeruje licznik, a alert pilnuje jego przeterminowania.
#
# DRUGI WARUNEK (BRAK DANYCH) DOMYKA CZWARTY TRYB, którego pierwszy nie widzi: zepsuł się sam obserwator.
# Bez niego martwy `watch.yml` daje wykres zamrożony na ostatniej dobrej wartości — czyli ciszę nie do
# odróżnienia od zdrowia. `condition_absent` ma jeden warunek konieczny, o którym trzeba wiedzieć: JEST
# ZNACZĄCY DOPIERO PO PIERWSZYM ZAPISIE. Metryka, do której nigdy nic nie napisano, nie jest „nieobecna" —
# jest nieznana, i alert nie odpali. Dlatego deskryptory wyżej powstają przy apply, a `watch.yml` ma
# wyzwalacz `workflow_run` na `apply`: pierwszy punkt pojawia się minuty po wdrożeniu, nie po godzinie.
resource "google_monitoring_alert_policy" "vpcsc_apply_stale" {
  count = local.alert_count

  depends_on = [time_sleep.deskryptory_widoczne]

  project      = local.monitoring.project_id
  display_name = "VPC-SC: zmiana granicy zmergowana i niezastosowana"
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "niezastosowana zmiana starsza niż próg"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.apply_pending}\"",
        "resource.type=\"global\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = local.progi.apply_pending_seconds
      # `60s`, a nie `0s` — i to jest OGRANICZENIE API, nie wybór. Pierwszy apply na żywej organizacji
      # odrzucił tę politykę:
      #   Error 400: Field alert_policy.conditions[0].condition_threshold.evaluation_missing_data had an
      #   invalid value of "EVALUATION_MISSING_DATA_INACTIVE": Conditions setting evaluation_missing_data
      #   must have a non-zero duration.
      # Czyli: JAWNE powiedzenie „brak danych nie jest przekroczeniem progu" wymaga niezerowego okna.
      # Wybór był między zerowym oknem a jawną obsługą braku danych — i drugie jest ważniejsze, bo bez
      # niego jeden spóźniony cron GitHuba dawałby alert o nieistniejącej zaległości. Koszt: minuta
      # opóźnienia na progu, który i tak wynosi godzinę. Próg nadal SAM JEST oknem czasowym (metryka
      # mierzy wiek), więc to okno nie dokłada drugiego progu — tylko spełnia warunek API.
      duration = "60s"

      # Brak danych NIE jest tu przekroczeniem progu — od tego jest warunek niżej, który mówi o czym innym
      # („nie wiem") i ma własne, dłuższe okno. Bez tego ustawienia jeden spóźniony cron GitHuba dawałby
      # alert o nieistniejącym zaległym apply.
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"

      aggregations {
        # Okno wyrównania >= kadencja publikacji (godzina). Krótsze okno daje puste kubełki między zapisami,
        # a warunek z pustym kubełkiem nigdy nie utrzyma się przez wymagany czas.
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  conditions {
    display_name = "obserwator granicy milczy"

    condition_absent {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.apply_pending}\"",
        "resource.type=\"global\"",
      ])
      duration = "${local.progi.watchdog_absent_seconds}s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = local.kanal_pojemnosc

  # 25 godzin, nie domyślne 7 dni: incydent, który sam się nie zamyka po naprawie, uczy zamykania ręcznego
  # — a wtedy następny, prawdziwy, ginie w tłumie starych. 25 h, bo musi przeżyć jedną dobę milczenia
  # obserwatora bez samozamknięcia w środku.
  alert_strategy {
    auto_close = "90000s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "VPC-SC: granica nie ma tego, co jest w Gicie"
    content   = <<-DOC
      Zmiana granicy jest w gałęzi domyślnej i **nie została zastosowana**, albo przestał działać obserwator.

      **Kto to odczuwa:** dywizja, która zmergowała wniosek i usłyszała „zrobione", a jej projekt nie jest
      w granicy; każda następna decyzja o promocji liczy stan, którego w chmurze nie ma.

      Który z dwóch warunków odpalił, widać w treści incydentu (`niezastosowana zmiana…` vs `obserwator
      granicy milczy`) — i to są DWIE RÓŻNE procedury.

      Pełna procedura: `docs/7-alerty.md`, sekcja „apply nie doszedł".
    DOC

    links {
      display_name = "runbook"
      url          = "${local.runbook}#apply-nie-doszedl"
    }
  }
}

# --- ALERT 2: budżet atrybutów, próg statyczny + prognoza ostrzegawcza -------------------------------
#
# KTO TO ODCZUWA: następna dywizja w kolejce. Przekroczenie 6000 atrybutów to odrzucenie z API przy
# `apply` — czyli wniosek przechodzi review, dostaje zgodę, a rozbija się na ostatnim kroku i onboarding
# staje do czasu konsolidacji profili albo decyzji o drugim perimetrze.
#
# DWA WYMIARY, BO ODPOWIADAJĄ NA DWA RÓŻNE PYTANIA:
#   * PRÓG STATYCZNY mówi GDZIE JESTEŚ. Ten sam PRÓG co bramka `attribute_budget.py` na pull requeście,
#     ale INNE ŹRÓDŁO liczby — i to jest istotne. Bramka liczy z DEKLARACJI (odpowiada na pytanie, czy
#     proponowana zmiana się zmieści; zmiany w chmurze jeszcze nie ma). Ten alert liczy z ŻYWEJ granicy
#     (`servicePerimeters.get`), bo odpowiada na pytanie, ile zostało W GRANICY. Liczba z deklaracji jest
#     ślepa na zdublowane reguły po nieudanym odzysku stanu, ręczne dopiski w konsoli i dryf — czyli
#     milczałaby dokładnie w tym scenariuszu, w którym sufit zostaje przekroczony bez niczyjej wiedzy.
#   * PROGNOZA mówi ILE MASZ CZASU. Przy +50 projektach na miesiąc jest ważniejsza: 65% z nachyleniem
#     200 atrybutów na tydzień jest gorsze niż 72% na płaskim wykresie, a próg statyczny widzi to odwrotnie.
#
# OSOBNO DLA `spec` I `status` — limit 6000 jest NA KONFIGURACJĘ, nie łączny. Jedna liczba dla obu myli
# w obie strony naraz: sumowanie zawyża (alarm przy dwóch zdrowych konfiguracjach), a maksimum ukrywa
# konfigurację, która właśnie się zapycha. Robi to `group_by_fields` na etykiecie `config`, a nie dwie
# polityki: dzięki temu incydent NIESIE W SOBIE, o którą konfigurację chodzi.
resource "google_monitoring_alert_policy" "vpcsc_attribute_budget" {
  count = local.alert_count

  depends_on = [time_sleep.deskryptory_widoczne]

  project      = local.monitoring.project_id
  display_name = "VPC-SC: budżet atrybutów perimetru"
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "wykorzystanie budżetu >= progu (per konfiguracja)"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.budzet_procent}\"",
        "resource.type=\"global\"",
      ])
      comparison              = "COMPARISON_GT"
      threshold_value         = local.progi.attribute_budget_percent
      duration                = "3600s"
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"

      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_MAX"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["metric.label.config"]
      }
    }
  }

  conditions {
    display_name = "prognoza wyczerpania < progu ostrzegawczego"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.budzet_dni}\"",
        "resource.type=\"global\"",
      ])
      # LT, nie GT: im mniej dni, tym gorzej. Producent publikuje 3650 przy braku wzrostu i przy zbyt
      # krótkiej historii — sentynela ma być SAFEJ strony, żeby świeże wdrożenie nie alarmowało o ścianie
      # wyliczonej z trzech punktów pomiarowych.
      comparison              = "COMPARISON_LT"
      threshold_value         = local.progi.days_to_limit_warning
      duration                = "3600s"
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"

      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_MIN"
        cross_series_reducer = "REDUCE_MIN"
        group_by_fields      = ["metric.label.config"]
      }
    }
  }

  notification_channels = local.kanal_pojemnosc

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "VPC-SC: kończy się budżet atrybutów"
    content   = <<-DOC
      Konfiguracja perimetru zbliża się do limitu **6000 atrybutów NA KONFIGURACJĘ** (`spec` i `status`
      mają osobne budżety). Etykieta `config` w incydencie mówi, która.

      **Kto to odczuwa:** następna dywizja w kolejce — przekroczenie limitu to odrzucenie z API przy
      `apply`, czyli wniosek z zatwierdzonym ticketem rozbija się na ostatnim kroku.

      Pełna procedura: `docs/7-alerty.md`, sekcja „budżet atrybutów".
    DOC

    links {
      display_name = "runbook"
      url          = "${local.runbook}#budzet-atrybutow"
    }
  }
}

# --- ALERT 3: budżet atrybutów, prognoza KRYTYCZNA ---------------------------------------------------
#
# DLACZEGO OSOBNA POLITYKA, A NIE TRZECI WARUNEK W POPRZEDNIEJ: polityka ma JEDNĄ `severity`. Prognoza
# poniżej progu krytycznego to inna decyzja operacyjna niż „zbliżamy się" — na 30 dni nie ma już czasu
# na konsolidację profili w normalnym trybie, więc to musi być głośniejsze niż ostrzeżenie, które przyjdzie
# tym samym kanałem co comiesięczny raport.
resource "google_monitoring_alert_policy" "vpcsc_attribute_budget_exhaustion" {
  count = local.alert_count

  depends_on = [time_sleep.deskryptory_widoczne]

  project      = local.monitoring.project_id
  display_name = "VPC-SC: budżet atrybutów wyczerpie się w mniej niż próg krytyczny"
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "prognoza wyczerpania < progu krytycznego"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.budzet_dni}\"",
        "resource.type=\"global\"",
      ])
      comparison              = "COMPARISON_LT"
      threshold_value         = local.progi.days_to_limit_critical
      duration                = "3600s"
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"

      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_MIN"
        cross_series_reducer = "REDUCE_MIN"
        group_by_fields      = ["metric.label.config"]
      }
    }
  }

  notification_channels = local.kanal_pojemnosc

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "VPC-SC: budżet atrybutów kończy się w tym miesiącu"
    content   = <<-DOC
      Przy dzisiejszym tempie wzrostu konfiguracja `${"$"}{metric.label.config}` uderzy w limit 6000
      atrybutów w mniej niż próg krytyczny dni.

      **Kto to odczuwa:** onboarding staje CAŁKOWICIE w dniu przekroczenia — nie stopniowo. Do tego dnia
      trzeba skonsolidować profile albo podjąć decyzję o drugim perimetrze (kryterium rewizji z DEC-1),
      a jedno i drugie to praca na tygodnie, nie na godziny.

      Pełna procedura: `docs/7-alerty.md`, sekcja „budżet atrybutów".
    DOC

    links {
      display_name = "runbook"
      url          = "${local.runbook}#budzet-atrybutow"
    }
  }
}

# --- ALERT 4: dryf granicy --------------------------------------------------------------------------
#
# KTO TO ODCZUWA: właściciel granicy — Git przestał opisywać rzeczywistość, więc review, `git revert`
# i raport zgodności mówią o konfiguracji, której w chmurze nie ma.
#
# TO JEST DRUGA WARSTWA, NIE DUBLET `vpcsc_out_of_band_change` z `monitoring.tf`. Tamten czyta AUDIT-LOG:
# jest szybki (minuty) i mówi KTO, ale widzi wyłącznie to, co dopasuje jego filtr metod, i nie mówi nic
# o tym, czy zmianę już naprawiono. Ten czyta `terraform plan`: jest wolny (godzina), ale mówi CO SIĘ
# REALNIE ROZJECHAŁO i trwa aż do naprawy. Szybki alert bez wolnego znaczy „ktoś kliknął" i cisza; wolny
# bez szybkiego znaczy godzina zwłoki na sygnale bezpieczeństwa.
#
# ODRÓŻNIENIE ZMIANY SPOZA GITA OD OPÓŹNIENIA PROPAGACJI — dwa niezależne mechanizmy, bo pomyłka w tę
# stronę jest kosztowna (alert po każdym apply uczy dyżurnego ignorować go w tydzień):
#   1. PRODUCENT rozstrzyga to na wejściu: `perimeter_watch.py` publikuje tu 0, kiedy w Gicie stoi zmiana
#      jeszcze niezastosowana. Wtedy niepusty plan jest OCZEKIWANY i mówi o nim alert `apply`, nie ten.
#   2. KONSUMENT wymaga TRWANIA: `duration` z `alerting.yaml` (domyślnie 3600 s) przy zmierzonej propagacji
#      skutku ~20 s to margines 180x. Konfiguracja w ACM wraca natychmiast, skutek dochodzi ~20 s później —
#      reguła licząca różnicę w oknie krótszym niż propagacja strzelałaby po każdym apply.
resource "google_monitoring_alert_policy" "vpcsc_drift" {
  count = local.alert_count

  depends_on = [time_sleep.deskryptory_widoczne]

  project      = local.monitoring.project_id
  display_name = "VPC-SC: granica rozjechana z Gitem (dryf)"
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "niepusty plan na nietkniętym repozytorium, utrzymany przez próg"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.dryf}\"",
        "resource.type=\"global\"",
      ])
      comparison              = "COMPARISON_GT"
      threshold_value         = 0
      duration                = "${local.progi.drift_persist_seconds}s"
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = local.kanal_bezpieczenstwo

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "VPC-SC: ktoś zmienił granicę poza Gitem"
    content   = <<-DOC
      `terraform plan` na **nietkniętym** repozytorium nie jest pusty, a w Gicie nie ma niczego, co czekałoby
      na zastosowanie. Ktoś zmienił granicę poza pipeline'em: albo incydent, albo obejście procesu.

      **Kto to odczuwa:** właściciel granicy — od tej chwili Git nie opisuje rzeczywistości, więc review
      i `git revert` mówią o konfiguracji, której w chmurze nie ma.

      **Nie „naprawiaj" tego przez apply, zanim ustalisz KTO i CO zmienił.** Ślepy apply kasuje dowód
      i — jeśli zmiana była zasadna — cofa ją bez rozmowy z tym, kto ją wprowadził.

      Pełna procedura: `docs/7-alerty.md`, sekcja „dryf granicy".
    DOC

    links {
      display_name = "runbook"
      url          = "${local.runbook}#dryf-granicy"
    }
  }
}

# --- ALERT 5: członek po dacie review_by --------------------------------------------------------------
#
# KTO TO ODCZUWA: audyt i security — projekt jest w granicy na podstawie zgody, której nikt nie odnowił.
# Po `review_by` to jest martwy dostęp: nikt nie potwierdził, że jest potrzebny, i nikt go nie usunął.
#
# DLACZEGO ALERT, SKORO JEST `expiry-sweep.yml`. Sweeper chodzi RAZ W MIESIĄCU i otwiera pull requesta —
# czyli w najgorszym razie wpis żyje 29 dni po terminie, zanim ktokolwiek się dowie. Gorzej: sweeper, który
# przestał chodzić (zmieniony cron, wyłączone Actions, nieudany przebieg), nie zgłasza NICZEGO, a jego
# cisza wygląda dokładnie tak samo jak „nikt nie wygasł". Ten alert mierzy STAN, nie wykonanie zadania —
# więc świeci również wtedy, gdy zepsuł się sam sweeper. WARNING, nie CRITICAL: to jest dług do
# uporządkowania w godzinach pracy, a nie awaria.
#
# `duration = 3600s`, a nie doba — mimo że pierwszym odruchem jest „dajmy sweeperowi czas". Odruch jest zły
# z dwóch powodów: pull request sweepera i tak czeka na WŁAŚCICIELA projektu, czyli dni, a nie godziny, więc
# dłuższe okno niczego nie odfiltrowuje — tylko opóźnia ten sam sygnał. A okno dłuższe niż 24 h jest przy
# tym NIETESTOWALNE: Cloud Monitoring nie przyjmie punktów starszych niż doba, więc warunku z `for: 24h`
# nie da się odpalić sztucznie i zostaje deklaracją. Godzina wystarcza, żeby wykluczyć migotanie.
resource "google_monitoring_alert_policy" "vpcsc_members_expired" {
  count = local.alert_count

  depends_on = [time_sleep.deskryptory_widoczne]

  project      = local.monitoring.project_id
  display_name = "VPC-SC: członek granicy po dacie review_by"
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "co najmniej jeden wpis po terminie przez godzinę"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.wygasli}\"",
        "resource.type=\"global\"",
      ])
      comparison              = "COMPARISON_GT"
      threshold_value         = 0
      duration                = "3600s"
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = local.kanal_pojemnosc

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "VPC-SC: w granicy stoi projekt po terminie przeglądu"
    content   = <<-DOC
      Co najmniej jeden wpis w `perimeter/projects.yaml` ma `review_by` w przeszłości i nikt go nie
      potwierdził ani nie usunął.

      **Kto to odczuwa:** audyt i security — projekt korzysta z granicy na podstawie zgody, której nikt
      nie odnowił. Przy konfiguracji egzekwowanej to działa w drugą stronę: usunięcie wpisu ZDEJMUJE
      ochronę, więc offboarding jest zmianą bezpieczeństwa i idzie tą samą ścieżką co onboarding.

      Pełna procedura: `docs/7-alerty.md`, sekcja „członek po terminie".
    DOC

    links {
      display_name = "runbook"
      url          = "${local.runbook}#czlonek-po-terminie"
    }
  }
}

# --- ALERT 6: członek granicy, którego projekt nie jest ACTIVE (DEC-42) -------------------------------
#
# KTO TO ODCZUWA: security i każdy, kto podejmuje decyzję o promocji. Skasowanie projektu członka nie jest
# u nas zdarzeniem — projekty kasuje inny zespół, bez powiadomienia. Skutek natychmiastowy jest kosmetyczny
# (wpis wskazuje na numer, którego nie ma), skutek opóźniony jest groźny: naruszenia martwego członka
# spadają do zera, a zero jest DOWODEM „czystego okna", którego wymaga bramka promocji. Obcy zespół
# produkuje w ten sposób fałszywy dowód gotowości do egzekwowania.
#
# DLACZEGO TO NIE JEST BRAMKA NA PULL REQUEŚCIE. Rozstrzygnięte pomiarem: koszt pytania o każdego członka
# rósłby liniowo przy KAŻDYM wniosku, a bramka blokowałaby WŁASNE LEKARSTWO — jedyne wyjście z martwego
# wpisu prowadzi przez `plan` + `apply`, czyli przez te same przebiegi, które ta bramka by zatrzymała.
# Onboarding pokrywa pre-flight; ten alert pokrywa dokładnie jeden pozostały przypadek: projekt skasowany
# JUŻ PO wejściu do granicy.
#
# TRZY WARUNKI, BO SĄ TRZY RÓŻNE ZDANIA — i drugie z nich jest tym, przez które ten alert w ogóle powstał:
#   (a) `not_active` > 0 — WERDYKT: stan odczytany i inny niż ACTIVE. Ktoś kasuje projekt, który jest
#       w granicy. Wchodzimy w kroki offboardingu (`3-runbook…` §C) tego samego dnia;
#   (b) `unreadable` > 0 — ŚLEPOTA NA CZŁONKU: stanu NIE odczytano. To NIE jest potwierdzenie, że członek
#       żyje, więc nie wolno go zamieść pod „ACTIVE". Osobny warunek, bo osobna procedura;
#   (c) BRAK DANYCH — ślepota na całym detektorze: producent nie zdołał odczytać granicy albo Asset
#       Inventory i świadomie NIE opublikował zera. Bez tego warunku jego awaria wyglądałaby dokładnie
#       tak, jak zdrowie.
#
# `duration = 60s`, a nie godzina jak przy `review_by` — i to jest wybór, nie kopia. Stan cyklu życia
# projektu NIE MIGOCZE: `DELETE_REQUESTED` trwa 30 dni, więc dłuższe okno nie odfiltrowuje szumu, tylko
# dokłada opóźnienia do sygnału, którego całe znaczenie polega na czasie reakcji. Każda godzina zwłoki to
# godzina, w której bramka promocji może skonsumować fałszywe czyste okno. 60 s to MINIMUM API dla
# `evaluation_missing_data` (zerowe okno = `Error 400`), a realne opóźnienie wykrycia i tak wyznacza
# kadencja producenta (godzina), nie ten próg.
#
# WARNING, nie CRITICAL, i kanał BEZPIECZEŃSTWA, nie pojemnościowy. Nic nie jest w tej chwili blokowane
# ani zepsute — granica działa dalej, a soft-delete trwa 30 dni, więc jest czas na reakcję w godzinach
# pracy. CRITICAL wiszący tygodniami nauczyłby dyżurnego klikać „potwierdź" na kategorii, w której siedzi
# alert o odmowie egzekwowanej. Kanał bezpieczeństwa, bo to jest fałszowanie dowodu, a nie dług porządkowy.
resource "google_monitoring_alert_policy" "vpcsc_member_project_gone" {
  count = local.alert_count

  depends_on = [time_sleep.deskryptory_widoczne]

  project      = local.monitoring.project_id
  display_name = "VPC-SC: członek granicy bez potwierdzonego stanu ACTIVE"
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "co najmniej jeden członek ma stan inny niż ACTIVE"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.czlonkowie_nieaktywni}\"",
        "resource.type=\"global\"",
        "metric.labels.state=\"not_active\"",
      ])
      comparison              = "COMPARISON_GT"
      threshold_value         = 0
      duration                = "60s"
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  conditions {
    display_name = "stanu co najmniej jednego członka NIE odczytano"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.czlonkowie_nieaktywni}\"",
        "resource.type=\"global\"",
        "metric.labels.state=\"unreadable\"",
      ])
      comparison              = "COMPARISON_GT"
      threshold_value         = 0
      duration                = "60s"
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  conditions {
    display_name = "detektor żywotności członków milczy"

    # Martwy-człowiek TEJ metryki, a nie wspólny z `apply_pending`. Tryb awarii jest osobny: `watch.yml`
    # może chodzić i publikować komplet pozostałych liczb, a mimo to nie mieć odczytu Asset Inventory
    # (odebrany `cloudasset.viewer`, wyłączone `cloudasset.googleapis.com`, `403` na zakresie organizacji).
    # Producent świadomie nie publikuje wtedy zera — więc bez tego warunku jego ślepota jest ciszą.
    condition_absent {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.czlonkowie_nieaktywni}\"",
        "resource.type=\"global\"",
      ])
      duration = "${local.progi.watchdog_absent_seconds}s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = local.kanal_bezpieczenstwo

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    mime_type = "text/markdown"
    subject   = "VPC-SC: w granicy stoi członek, o którym nie wiadomo, że jego projekt żyje"
    content   = <<-DOC
      Co najmniej jeden numer z `spec.resources` albo `status.resources` należy do projektu, który **nie
      jest `ACTIVE`** — albo którego stanu **nie udało się odczytać**. Warunek, który się otworzył, mówi
      który z tych dwóch przypadków zachodzi; to są różne procedury i nie wolno ich mylić.

      **Kto to odczuwa:** security i decyzja o promocji. Naruszenia martwego członka spadają do zera,
      a zero jest dowodem „czystego okna" dla bramki promocji — czyli martwy wpis robi się z czasem coraz
      lepszym kandydatem do egzekwowania. `plan`, `apply`, dryf, `expiry-sweep` i pre-flight tego NIE widzą
      i widzieć nie mogą: Git i granica zgadzają się co do numeru, którego nie ma.

      Pełna procedura: `docs/7-alerty.md`, sekcja „martwy członek granicy".
    DOC

    links {
      display_name = "runbook"
      url          = "${local.runbook}#martwy-czlonek"
    }
  }
}
