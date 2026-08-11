# Monitoring perimetru — metryki i alerty.
#
# DLACZEGO to jest w tym repo, a nie „w monitoringu": perimetr bez alertu jest granicą, o której dowiesz się
# od użytkownika. Trzy rzeczy, które MUSZĄ mieć konsumenta:
#
#   1. naruszenia ENFORCED — ktoś jest właśnie blokowany. Jeśli to legalny ruch, to jest incydent i liczy się
#      każda minuta (break-glass). Alert page'ujący.
#   2. naruszenia DRY-RUN — nikt nie jest blokowany, ale ktoś zobaczy blokadę po promocji. Alert informacyjny,
#      bo bez niego raport tygodniowy jest jedynym sygnałem, a tydzień to długo przed promocją.
#   3. zmiana perimetru POZA pipeline'em — ktoś klikał w konsoli albo użył gcloud. Drift detection złapie to
#      w nocy; alert łapie od razu, a przy granicy bezpieczeństwa różnica ma znaczenie.
#
# ŚWIADOMY BRAK: alertu na „liczba członków spadła". Offboarding jest legalną operacją i wychodzi w PR-ze,
# a alert na normalną zmianę uczy tylko ignorowania alertów.

locals {
  monitoring_enabled = contains(keys(local.policy), "monitoring")
  # Atrapa z KOMPLETEM kluczy, nie `null`, gdy sekcji `monitoring` nie ma w policy.yaml. Samo `count = 0` nie
  # wystarcza: `terraform validate` sprawdza wyrażenia w atrybutach zasobu również wtedy, gdy nie powstanie ani
  # jedna instancja, a `null.project_id` jest twardym błędem. Efekt bez atrapy: repo bez monitoringu nie
  # przechodzi walidacji, czyli sekcja opisana w policy.yaml jako możliwa do pominięcia jest obowiązkowa.
  monitoring = local.monitoring_enabled ? local.policy.monitoring : {
    project_id            = ""
    notification_channels = []
    apply_service_account = ""
  }

  # Filtr wspólny dla obu metryk. `VpcServiceControlAuditMetadata` to typ, którym Google oznacza KAŻDE
  # naruszenie perimetru — niezależnie od usługi, której dotyczyło.
  vpcsc_audit_filter = join(" AND ", [
    "protoPayload.metadata.@type=\"type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata\"",
    "protoPayload.metadata.violationReason!=\"\"",
  ])
}

# --- 1. Metryka: naruszenia EGZEKWOWANE (ktoś jest blokowany TERAZ) ---------------------------------

resource "google_logging_metric" "vpcsc_violations_enforced" {
  count = local.monitoring_enabled ? 1 : 0

  project     = local.monitoring.project_id
  name        = "vpcsc/violations_enforced"
  description = "Naruszenia perimetru VPC-SC w trybie egzekwowanym — każde z nich to odrzucone wywołanie API."

  # NEGACJA, NIE `dryRun="false"` — pole `dryRun` w wpisie o odmowie EGZEKWOWANEJ NIE ISTNIEJE. Pojawia się
  # wyłącznie dla naruszeń dry-run, i wtedy ma wartość `true`. Zmierzone na żywej organizacji tuż po
  # pierwszej realnej odmowie: `google.storage.buckets.list` z `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER`
  # przyszedł BEZ pola `dryRun`, a to samo wywołanie sprzed promocji miało `dryRun=true`.
  #
  # `dryRun="false"` nie dopasowuje więc NICZEGO — nigdy, w żadnej organizacji. Metryka „ktoś jest blokowany
  # TERAZ" zostawała pusta dokładnie wtedy, gdy miała rosnąć, a alert zbudowany na niej nie odpalił ani razu.
  # Metryka, która nie liczy, jest gorsza od jej braku: brak widać, pustą metrykę bierze się za spokój.
  #
  # To jest jedyna metryka w tym pliku, która oznacza „coś się właśnie psuje".
  filter = "${local.vpcsc_audit_filter} AND NOT protoPayload.metadata.dryRun=\"true\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    # Etykiety pozwalają zawęzić alert do jednej dywizji bez tworzenia N metryk. Bez nich alert mówi
    # „coś jest blokowane w organizacji", co przy trzydziestu dywizjach jest bezużyteczne.
    labels {
      key         = "principal"
      description = "Tożsamość, której odmówiono (zwykle konto serwisowe)."
    }
    labels {
      key         = "method"
      description = "Metoda API, której dotyczyła odmowa."
    }
    labels {
      key         = "violation_reason"
      description = "NO_MATCHING_ACCESS_LEVEL / RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER / …"
    }
  }

  label_extractors = {
    principal        = "EXTRACT(protoPayload.authenticationInfo.principalEmail)"
    method           = "EXTRACT(protoPayload.methodName)"
    violation_reason = "EXTRACT(protoPayload.metadata.violationReason)"
  }
}

# --- 2. Metryka: naruszenia DRY-RUN (zapowiedź problemu, nie problem) ------------------------------

resource "google_logging_metric" "vpcsc_violations_dry_run" {
  count = local.monitoring_enabled ? 1 : 0

  project     = local.monitoring.project_id
  name        = "vpcsc/violations_dry_run"
  description = "Naruszenia w trybie dry-run — wywołania, które przestaną działać po promocji do enforced."

  filter = "${local.vpcsc_audit_filter} AND protoPayload.metadata.dryRun=\"true\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "principal"
      description = "Tożsamość, która naruszyłaby perimetr po promocji."
    }
  }

  label_extractors = {
    principal = "EXTRACT(protoPayload.authenticationInfo.principalEmail)"
  }
}

# --- 3. Alert: ruch produkcyjny jest blokowany -----------------------------------------------------
# To jedyny alert w tym pliku, który powinien budzić człowieka.

resource "google_monitoring_alert_policy" "vpcsc_enforced_denials" {
  count = local.monitoring_enabled ? 1 : 0

  project      = local.monitoring.project_id
  display_name = "VPC-SC: ruch odrzucony w trybie egzekwowanym"
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "naruszenia enforced w ostatnich 5 minutach"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"logging.googleapis.com/user/vpcsc/violations_enforced\"",
        "resource.type=\"global\"",
      ])
      comparison = "COMPARISON_GT"
      # Próg 0 z oknem 5 min: przy granicy bezpieczeństwa JEDNA odmowa legalnego ruchu jest już incydentem.
      # Nie uśredniamy — chcemy wiedzieć o pierwszej, nie o dwudziestej.
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_DELTA"
        # Grupujemy po tożsamości: jedna dywizja z problemem nie zalewa alertem całej organizacji,
        # a przy okazji widać w tytule, kogo dotyczy.
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["metric.label.principal"]
      }
    }
  }

  # OBA KANAŁY (`alerts.tf`), bo w chwili odpalenia nie wiadomo, czy to awaria, czy zadziałała kontrola —
  # a pierwszym krokiem runbooka jest właśnie to rozstrzygnąć. Wcześniej stała tu goła lista z `policy.yaml`,
  # która na żywym wdrożeniu była PUSTA: polityka istniała, incydent się otwierał, i nie szedł do nikogo.
  notification_channels = local.kanal_oba

  # Każdy alert critical MUSI nieść procedurę — inaczej o 3:00 ktoś zgaduje. Alert bez runbooka to
  # pół rozwiązania: budzi człowieka i zostawia go z pytaniem, co teraz.
  documentation {
    mime_type = "text/markdown"
    subject   = "VPC-SC odrzuca ruch — sprawdź, czy to legalny przepływ"
    content   = <<-DOC
      Perimetr odrzucił wywołanie API w trybie **egzekwowanym**. To znaczy, że jakiś workload właśnie nie
      działa — albo że ktoś próbował wynieść dane i granica zadziałała. Rozstrzygnięcie, które to z tych
      dwóch, jest treścią tego alertu.

      **1. Ustal, co zostało odrzucone**

      ```
      gcloud logging read 'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"
        AND NOT protoPayload.metadata.dryRun="true"' --project=PROJEKT_CZLONKA --freshness=1h \
        --format='table(protoPayload.authenticationInfo.principalEmail, protoPayload.methodName,
                        protoPayload.metadata.violationReason, resource.labels.project_id)'
      ```

      Dwie rzeczy, na ktorych ten odczyt lamie sie najczesciej — obie ZMIERZONE:
      wpis o odmowie EGZEKWOWANEJ **nie ma pola `dryRun`** (pojawia sie tylko przy dry-run, z wartoscia
      `true`), wiec filtr `dryRun="false"` nie zwraca nigdy niczego; oraz wpis lezy w logu **projektu
      czlonkowskiego**, a nie organizacji — `--organization` na tym samym filtrze zwraca 0.

      **2. Zinterpretuj `violationReason`**

      - `NO_MATCHING_ACCESS_LEVEL` — tożsamość jest znana, ale kontekst nie (zła sieć, brak device-trust).
        Zwykle: ktoś pracuje spoza VPN albo workload zmienił podsieć.
      - `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER` — cel wywołania leży poza granicą. Zwykle: nowy projekt,
        którego nikt nie dołączył, albo brakująca reguła egress.

      **3. Zdecyduj**

      - **legalny przepływ** → `break-glass.yml` (demote członka do dry-run, 2 approverów, auto-postmortem),
        a potem profil pokrywający ten wzorzec i świeże okno obserwacji;
      - **nielegalny** → to nie jest awaria, to zadziałała granica. Zgłoś do security i **nie** dodawaj reguły.

      Pełna procedura: `docs/3-runbook-promocja-i-break-glass.md` §B.
    DOC

    links {
      display_name = "runbook"
      url          = "${local.runbook}#odmowa-w-trybie-egzekwowanym"
    }
  }
}

# --- 4. Alert: perimetr zmieniony poza pipeline'em --------------------------------------------------
# Drift detection (nightly) i tak to złapie. Ten alert łapie od razu — bo między „ktoś kliknął w konsoli"
# a „dowiadujemy się o tym rano" mieści się cała noc, a to jest granica bezpieczeństwa organizacji.

resource "google_logging_metric" "vpcsc_config_changed_outside_pipeline" {
  count = local.monitoring_enabled ? 1 : 0

  project     = local.monitoring.project_id
  name        = "vpcsc/config_changed_outside_pipeline"
  description = "Zmiany konfiguracji perimetru wykonane przez tożsamość INNĄ niż konto apply pipeline'u."

  # Wykluczamy WŁASNE konto apply — jego zmiany są oczekiwane. Wszystko inne jest sygnałem.
  filter = join(" AND ", [
    "protoPayload.serviceName=\"accesscontextmanager.googleapis.com\"",
    "protoPayload.methodName:(\"ServicePerimeter\" OR \"AccessLevel\" OR \"AccessPolicy\")",
    "NOT protoPayload.methodName:(\"Get\" OR \"List\")",
    "protoPayload.authenticationInfo.principalEmail!=\"${local.monitoring.apply_service_account}\"",
  ])

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "principal"
      description = "Kto zmienił konfigurację poza pipeline'em."
    }
    labels {
      key         = "method"
      description = "Jaka operacja (patch / create / delete)."
    }
  }

  label_extractors = {
    principal = "EXTRACT(protoPayload.authenticationInfo.principalEmail)"
    method    = "EXTRACT(protoPayload.methodName)"
  }
}

resource "google_monitoring_alert_policy" "vpcsc_out_of_band_change" {
  count = local.monitoring_enabled ? 1 : 0

  project      = local.monitoring.project_id
  display_name = "VPC-SC: konfiguracja zmieniona poza pipeline'em"
  combiner     = "OR"

  # PODNIESIONE Z `WARNING` DO `CRITICAL`. Powód nie jest kosmetyczny: `WARNING` znaczy „obejrzyj w godzinach
  # pracy", a to jest jedyny sygnał, który odróżnia zmianę granicy bezpieczeństwa wykonaną przez PROCES od
  # wykonanej przez CZŁOWIEKA z konsoli. Jeśli to drugie jest nieautoryzowane, każda godzina zwłoki to
  # godzina z otwartą granicą i skasowanym śladem. Wyjątkiem, którego ta zmiana nie psuje, jest szum:
  # własne konto apply jest z filtru metryki wykluczone, więc normalna praca pipeline'u nie odpala tego
  # alertu ANI RAZU (potwierdzone na wdrożeniu: metryka pusta przez cały okres, w którym apply chodził).
  severity = "CRITICAL"

  conditions {
    display_name = "zmiana przez tożsamość inną niż apply-SA"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"logging.googleapis.com/user/vpcsc/config_changed_outside_pipeline\"",
        "resource.type=\"global\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["metric.label.principal"]
      }
    }
  }

  # KANAŁ BEZPIECZEŃSTWA, nie pojemnościowy: to jest sygnał obejścia procesu, a nie informacja operacyjna.
  notification_channels = local.kanal_bezpieczenstwo

  documentation {
    mime_type = "text/markdown"
    subject   = "Ktoś zmienił perimetr poza pipeline'em"
    content   = <<-DOC
      Konfiguracja perimetru została zmieniona przez tożsamość **inną** niż konto apply. Możliwe przyczyny,
      od najbardziej do najmniej prawdopodobnej:

      1. **break-glass** — jeśli w ciągu ostatniej godziny ktoś uruchamiał procedurę awaryjną, to jest to ona
         (używa tego samego konta apply, ale przez `workflow_dispatch`, więc sprawdź, czy to nie inna tożsamość);
      2. **ręczna zmiana w konsoli** — ktoś „szybko poprawił". To jest dokładnie ten scenariusz, dla którego
         istnieje drift detection: git przestał opisywać rzeczywistość;
      3. **nieautoryzowana zmiana** — traktuj jako incydent bezpieczeństwa.

      **Nie „naprawiaj" tego przez apply.** Najpierw ustal, KTO i CO zmienił:

      ```
      gcloud logging read 'protoPayload.serviceName="accesscontextmanager.googleapis.com"
        AND NOT protoPayload.methodName:("Get" OR "List")' --organization=ORG_ID --freshness=2h \
        --format='table(timestamp, protoPayload.authenticationInfo.principalEmail, protoPayload.methodName)'
      ```

      Dopiero potem decyzja: przywrócić stan z gita (`git revert` nie pomoże — trzeba apply na niezmienionym
      repo) albo dopisać tę zmianę do repo, jeśli była zasadna. Wybór zależy od tego, czy zmiana miała sens —
      a nie od tego, co jest łatwiejsze.
    DOC

    links {
      display_name = "runbook"
      url          = "${local.runbook}#dryf-granicy"
    }
  }
}
