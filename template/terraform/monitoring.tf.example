# Monitoring perimetru — alerty na to, co się psuje po cichu.
#
# DLACZEGO to jest w tym repo, a nie „w monitoringu": perimetr bez alertu jest granicą, o której dowiesz się
# od użytkownika. Dwie rzeczy, które MUSZĄ mieć konsumenta:
#
#   1. naruszenia ENFORCED — ktoś jest właśnie blokowany. Jeśli to legalny ruch, to jest incydent i liczy się
#      każda minuta (break-glass). Alert page'ujący.
#   2. zmiana perimetru POZA pipeline'em — ktoś klikał w konsoli albo użył gcloud. Drift detection złapie to
#      w nocy; alert łapie od razu, a przy granicy bezpieczeństwa różnica ma znaczenie.
#
# ŚWIADOMY BRAK 1: alertu na „liczba członków spadła". Offboarding jest legalną operacją i wychodzi w PR-ze,
# a alert na normalną zmianę uczy tylko ignorowania alertów.
#
# ŚWIADOMY BRAK 2: alertu na naruszenia DRY-RUN. Metryka jest publikowana (widać ją na wykresie i czyta ją
# bramka promocji), ale POLITYKI ALERTU nie ma i to jest decyzja, nie przeoczenie: naruszenie dry-run znaczy
# „ktoś ZOSTAŁBY zablokowany po promocji", czyli nikt nie jest blokowany teraz. Jego konsumentem jest raport
# tygodniowy i bramka promocji — obie ścieżki działają w tempie, w którym ta informacja jest użyteczna.
# Alert budzący na to, co się nie dzieje, uczy ignorowania kategorii, w której siedzi punkt 1.
#
# ======================================================================================================
# DLACZEGO TU NIE MA ANI JEDNEJ METRYKI LOG-BASED — ZMIERZONE, #2000
# ======================================================================================================
# Do 2026-08-12 punkty 1 i 2 stały na `google_logging_metric` w projekcie monitoringu. Obie metryki miały
# poprawny filtr (pułapka `dryRun="false"` z #1941 była już naprawiona), obie ISTNIAŁY jako deskryptor,
# obie były podpięte pod polityki alertu — i obie miały ZERO serii przy realnych zdarzeniach. Alert „ruch
# odrzucony w trybie egzekwowanym" nie odpalił ani razu przy czterech realnych odmowach egzekwowanych.
#
# Przyczyna, rozstrzygnięta parą kontrolną, a nie dokumentacją:
#
#   KONTROLA A (czy maszyneria w tym projekcie w ogóle działa): metryka log-based w projekcie
#   administracyjnym + 5 wpisów ZAPISANYCH do tego projektu (`gcloud logging write`)
#     -> 1 seria, 5 punktów, widoczne po ~6 minutach.
#
#   KONTROLA B (czy liczy wpisy przyniesione przez sink): ta sama maszyneria, ta sama chwila, realna odmowa
#   egzekwowana na projekcie członkowskim, potwierdzona w kubełku sinka tego samego projektu
#   (`vpcServiceControlsUniqueIdentifier` zgodny z komunikatem błędu API)
#     -> 0 serii, 0 punktów.
#
# WNIOSEK: metryka log-based liczy wyłącznie wpisy PRZYJĘTE (ingest) przez Log Router swojego projektu.
# Sink jest MAGAZYNEM, nie wejściem — wpis dostarczony do kubełka w tym samym projekcie NIE jest liczony,
# i żadne przeniesienie kubełka tego nie zmieni. Naruszenia VPC-SC powstają w logu projektu-właściciela
# zasobu (członka), a zmiany ACM — w logu ORGANIZACJI (`_Required`). Metryki log-based istnieją zaś
# WYŁĄCZNIE per projekt: `gcloud logging metrics` nie ma flagi `--organization`, a API zna tylko
# `projects.metrics`. Dla obu tych sygnałów log-based metryka jest więc STRUKTURALNIE niezdolna do
# liczenia, w każdym projekcie i przy każdej konfiguracji sinka.
#
# Dlatego oba sygnały jadą torem, o którym WIADOMO, że działa (cztery metryki `watch.yml` mają dane od
# pierwszego dnia): obserwator czyta widoki sinka i publikuje `custom.googleapis.com/vpcsc/*`.
#
# CENA, POWIEDZIANA WPROST: producent chodzi z kadencją `watch.yml` (domyślnie godzinną), więc wykrycie
# odmowy trwa do jednego cyklu zamiast ~minuty. To jest realna strata MTTD i akceptujemy ją świadomie,
# bo alternatywą nie jest szybszy alert, tylko BRAK alertu — metryka, która nie może policzyć, nie ma
# czasu reakcji, ma zero. Kto chce minut, musi zbudować konsumenta zdarzeniowego (sink -> Pub/Sub ->
# funkcja); to jest osobna decyzja i osobny koszt, nie efekt uboczny tej poprawki.
#
# CZEGO NIE WOLNO TU PRZYWRÓCIĆ: `google_logging_metric` na naruszenia albo na ACM. Wygląda poprawnie,
# przechodzi `validate`, tworzy się bez błędu i NIE LICZY NIGDY. Pusta metryka jest gorsza od jej braku:
# brak widać, a pustą bierze się za spokój.

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
}

# --- 1. Alert: ruch produkcyjny jest blokowany -----------------------------------------------------
# To jedyny alert w tym pliku, który powinien budzić człowieka.

resource "google_monitoring_alert_policy" "vpcsc_enforced_denials" {
  # NIE `monitoring_enabled`: bez `violations_source` nie ma producenta, a polityka bez producenta
  # chodzi wiecznie na martwym-czlowieku. Uzasadnienie przy `naruszenia_count` w `alerts.tf`.
  count = local.naruszenia_count

  # Deskryptor metryki nie jest widoczny dla walidacji polityki od razu po utworzeniu (Error 404
  # `Cannot find metric(s)` na deskryptorze z TEGO SAMEGO przebiegu), a samo `depends_on` na
  # deskryptorze tego nie rozwiazuje: zaleznosc jest spelniona, a zasob jeszcze nie istnieje dla
  # konsumenta. Bez tego czekania wdrozenie OD ZERA konczy sie czesciowo, a ponowiony apply swieci
  # zielono i nikt sie nie dowiaduje, ze pierwszy raz nie zadzialal. Pomiar przy `time_sleep`.
  depends_on = [time_sleep.deskryptory_widoczne]

  project      = local.monitoring.project_id
  display_name = "VPC-SC: ruch odrzucony w trybie egzekwowanym"
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "odmowy egzekwowane w ostatnim oknie obserwatora"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.naruszenia_enforced}\"",
        "resource.type=\"global\"",
      ])
      comparison = "COMPARISON_GT"
      # Próg 0: przy granicy bezpieczeństwa JEDNA odmowa legalnego ruchu jest już incydentem. Nie
      # uśredniamy — chcemy wiedzieć o pierwszej, nie o dwudziestej.
      threshold_value = 0
      duration        = "0s"

      aggregations {
        # `3600s` + `ALIGN_MAX`, a nie `300s`: producent publikuje JEDEN punkt na przebieg `watch.yml`.
        # Okno krótsze od kadencji producenta daje przedziały bez punktu, czyli warunek, który gaśnie
        # i zapala się w rytm crona zamiast w rytm zdarzeń.
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
      # ŚWIADOMA STRATA: nie ma tu `group_by_fields = ["metric.label.principal"]`, które stało przy metryce
      # log-based. Metryka jest CELOWO bez etykiet i publikuje `0`, gdy odmów nie było — bo tylko wtedy
      # `condition_absent` niżej znaczy „producent padł". Z etykietą `principal` seria POWSTAJE i ZNIKA
      # razem z ruchem danej tożsamości, więc zdrowa cisza (brak odmów) byłaby nieodróżnialna od awarii
      # obserwatora i martwy-człowiek strzelałby non stop. Wybór jest więc między „alert mówi OD RAZU,
      # kogo dotyczy" a „cisza jest wiarygodna" — i drugie jest warte więcej, bo pierwsze odzyskuje się
      # jednym odczytem z runbooka, a wiarygodności ciszy nie odzyskuje się niczym.
    }
  }

  # MARTWY-CZŁOWIEK NA WŁASNYM PRODUCENCIE, a nie oparcie się o watchdoga `apply_pending_seconds`.
  # Powód jest konkretny: obie liczby publikuje ten sam job, ale z RÓŻNYCH źródeł — `apply_pending`
  # z API GitHuba, ta metryka z widoku sinka, za którym stoi osobny grant `logging.viewAccessor`.
  # Odebranie tego jednego grantu (albo skasowanie widoku) zatrzymuje WYŁĄCZNIE tę metrykę, a watchdog
  # oparty o `apply_pending` milczy dalej, bo jego własne źródło działa. Cisza znaczyłaby wtedy „brak
  # odmów", czyli dokładnie to, co ten alert ma wykluczyć.
  conditions {
    display_name = "obserwator przestał publikować liczbę odmów"

    condition_absent {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.naruszenia_enforced}\"",
        "resource.type=\"global\"",
      ])
      duration = "${local.progi.watchdog_absent_seconds}s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  # OBA KANAŁY (`alerts.tf`), bo w chwili odpalenia nie wiadomo, czy to awaria, czy zadziałała kontrola —
  # a pierwszym krokiem runbooka jest właśnie to rozstrzygnąć.
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

      **Jeśli alert mówi „obserwator przestał publikować"** — to nie jest odmowa, to jest UTRATA WZROKU.
      Sprawdź ostatni przebieg `watch.yml` i grant `logging.viewAccessor` konta planu na widoku naruszeń.
      Dopóki to trwa, „brak odmów" nie jest stwierdzeniem o świecie.

      **1. Ustal, co zostało odrzucone** — czytaj z WIDOKU SINKA, nie z projektu członka: po promocji log
      członka sam leży za granicą i odczyt z laptopa bywa odrzucany.

      ```
      gcloud logging read 'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"' \
        --project=<PROJEKT_ADM> --bucket=<KUBELEK> --location=<LOKALIZACJA> --view=<KUBELEK> --freshness=1h \
        --format='table(protoPayload.authenticationInfo.principalEmail, protoPayload.methodName,
                        protoPayload.metadata.violationReason, resource.labels.project_id)'
      ```

      Pułapka ZMIERZONA, nie wprowadzaj jej z powrotem: wpis o odmowie EGZEKWOWANEJ **nie ma pola
      `dryRun`** (pojawia się tylko przy dry-run, z wartością `true`), więc filtr `dryRun="false"` nie
      zwraca nigdy niczego. Odmowy egzekwowane to wpisy BEZ tego pola.

      **2. Zinterpretuj `violationReason`**

      - `NO_MATCHING_ACCESS_LEVEL` — tożsamość jest znana, ale kontekst nie (zła sieć, brak device-trust).
        Zwykle: ktoś pracuje spoza VPN albo workload zmienił podsieć.
      - `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER` — cel wywołania leży poza granicą. Zwykle: nowy projekt,
        którego nikt nie dołączył, albo brakująca reguła egress.

      **3. Zdecyduj**

      - **legalny przepływ** → `break-glass.yml` (demote członka do dry-run, auto-postmortem; czy czeka na
        zatwierdzenie, decyduje environment `break-glass` w TYM repozytorium — na planie bez wymaganych
        recenzentów rusza od razu, więc nie zakładaj pary oczu, sprawdź `gh api …/environments/break-glass`),
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

# --- 2. Alert: perimetr zmieniony poza pipeline'em --------------------------------------------------
# Drift detection (nightly) i tak to złapie. Ten alert łapie od razu — bo między „ktoś kliknął w konsoli"
# a „dowiadujemy się o tym rano" mieści się cała noc, a to jest granica bezpieczeństwa organizacji.

resource "google_monitoring_alert_policy" "vpcsc_out_of_band_change" {
  count = local.naruszenia_count

  # Deskryptor metryki nie jest widoczny dla walidacji polityki od razu po utworzeniu (Error 404
  # `Cannot find metric(s)` na deskryptorze z TEGO SAMEGO przebiegu), a samo `depends_on` na
  # deskryptorze tego nie rozwiazuje: zaleznosc jest spelniona, a zasob jeszcze nie istnieje dla
  # konsumenta. Bez tego czekania wdrozenie OD ZERA konczy sie czesciowo, a ponowiony apply swieci
  # zielono i nikt sie nie dowiaduje, ze pierwszy raz nie zadzialal. Pomiar przy `time_sleep`.
  depends_on = [time_sleep.deskryptory_widoczne]

  project      = local.monitoring.project_id
  display_name = "VPC-SC: konfiguracja zmieniona poza pipeline'em"
  combiner     = "OR"

  # `CRITICAL`, nie `WARNING`: `WARNING` znaczy „obejrzyj w godzinach pracy", a to jest jedyny sygnał,
  # który odróżnia zmianę granicy bezpieczeństwa wykonaną przez PROCES od wykonanej przez CZŁOWIEKA
  # z konsoli. Jeśli to drugie jest nieautoryzowane, każda godzina zwłoki to godzina z otwartą granicą.
  # Szumu to nie robi: konto apply jest z liczenia wykluczone, więc normalna praca pipeline'u nie
  # podbija tej metryki ANI RAZU.
  severity = "CRITICAL"

  conditions {
    display_name = "zmiana ACM przez tożsamość inną niż apply-SA"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.zmiany_poza_pipelinem}\"",
        "resource.type=\"global\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  # Własny martwy-człowiek, z tego samego powodu co przy odmowach: ta metryka ma WŁASNY widok i WŁASNY
  # grant, więc może zamilknąć w pojedynkę. Cisza po cichu znaczyłaby „nikt nie tknął granicy".
  conditions {
    display_name = "obserwator przestał publikować zmiany konfiguracji"

    condition_absent {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.zmiany_poza_pipelinem}\"",
        "resource.type=\"global\"",
      ])
      duration = "${local.progi.watchdog_absent_seconds}s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
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

      **Nie „naprawiaj" tego przez apply.** Najpierw ustal, KTO i CO zmienił. Czytaj z WIDOKU SINKA —
      wpis leży w logu ORGANIZACJI (`_Required`), do którego zwykły operator nie ma dostępu, a sink jest
      jedyną drogą, którą ten wpis stamtąd wychodzi:

      ```
      gcloud logging read 'protoPayload.serviceName="accesscontextmanager.googleapis.com"' \
        --project=<PROJEKT_ADM> --bucket=<KUBELEK> --location=<LOKALIZACJA> --view=<KUBELEK>-config \
        --freshness=2h \
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

# --- 3. Alert: obciążenie trafiło do sieci, która jeszcze nie jest za granicą ------------------------
#
# CO TO JEST ZA OBJAW, opowiedziany od strony tego, kto go odczuwa. Świeża sieć VPC w projekcie będącym
# członkiem konfiguracji EGZEKWOWANEJ przez pierwsze minuty nie jest dla perimetru „wewnątrz": maszyna
# w niej wychodzi na zewnątrz granicy BEZ ODMOWY, a w stanie pośrednim czyta z wnętrza perimetru
# I wysyła na zewnątrz jednocześnie — czyli cała ścieżka eksfiltracji jest przejezdna od końca do końca.
# ZMIERZONE 3/3 (DEC-32): okno 3 m 53 s – 5 m 18 s od `networks.insert`, droga na zewnątrz otwarta do
# 4 m 56 s. Jednostką propagacji jest SIEĆ — maszyna w sieci dojrzałej jest poprawna od pierwszej sekundy.
#
# DLACZEGO ALERT LICZY PARĘ, A NIE SAME SIECI. Utworzenie sieci VPC w projekcie członkowskim jest
# czynnością LEGALNĄ, częstą i wykonywaną przez ludzi, którzy o VPC-SC nie muszą wiedzieć nic. Alert na
# każdą z nich mówiłby „obudź dyżurnego, bo dywizja pracuje" — a wyciszony alert zabiera ze sobą całą
# kategorię, w której siedzi jedyny sygnał o tym oknie. Objawem jest dopiero para: sieć młodsza niż okno
# dojrzewania ORAZ obciążenie wstawione do niej w tym oknie, czyli złamanie kolejności z DEC-32
# („twórz sieć przed obciążeniem, zostaw na ≥ 10 min, potwierdź sondą dwie kolejne rundy").
#
# TO NIE JEST KONTROLA PREWENCYJNA I NIE WOLNO JEJ ZA TAKĄ BRAĆ. Okno zamyka się w minutach, a producent
# chodzi z kadencją `watch.yml` (godzina) — alert PRZYCHODZI PO WSZYSTKIM. Jego wartość jest forensyczna:
# daje znacznik czasu i ogranicza, co mogło wyjść. Prewencją jest kolejność (procedura), nie ten alert.
# Zapisane tutaj, w treści polityki, żeby nikt nie odczytał obecności alertu jako zabezpieczenia.
#
# DLACZEGO W OGÓLE POTRZEBUJE SINKA. Ruch, który w oknie wychodzi, NIE ZOSTAWIA ŚLADU — 41 udanych
# przekroczeń granicy dało 0 wpisów audytowych, bo nic nie jest odrzucane, więc nie ma czego logować.
# Jedynym pewnym sygnałem jest zdarzenie STERUJĄCE (`v1.compute.networks.insert`, Admin Activity), a dla
# członka egzekwowanego jego log leży za granicą (`logging` jest usługą chronioną) i z laptopa się go nie
# przeczyta. Wynosi go sink — osobny, do osobnego kubełka, żeby nie ruszyć widoku zmian ACM.

resource "google_monitoring_alert_policy" "vpcsc_network_window_workload" {
  count = local.sieci_count

  # Ten sam powód co przy dwóch politykach wyżej: deskryptor metryki nie jest widoczny dla walidacji
  # polityki od razu po utworzeniu, a `depends_on` na samym deskryptorze tego nie rozwiązuje.
  depends_on = [time_sleep.deskryptory_widoczne]

  project      = local.monitoring.project_id
  display_name = "VPC-SC: obciążenie w sieci młodszej niż okno dojrzewania"
  combiner     = "OR"

  # `CRITICAL`, mimo że alert nie zdąży zapobiec. Severity opisuje WAGĘ ZDARZENIA, nie szybkość reakcji:
  # to jest jedyny sygnał, po którym da się w ogóle dowiedzieć, że istniało okno z przejezdną ścieżką
  # eksfiltracji, i jedyny, który pozwala je OGRANICZYĆ w czasie. Szumu nie robi, bo licznik zeruje się
  # przy zachowanej kolejności — sama sieć, bez obciążenia w oknie, nie podbija go ANI RAZU.
  severity = "CRITICAL"

  conditions {
    display_name = "maszyna uruchomiona w sieci sprzed mniej niż okna dojrzewania (członek egzekwowany)"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.sieci_z_obciazeniem}\"",
        "resource.type=\"global\"",
      ])
      comparison = "COMPARISON_GT"
      # Próg 0: jedno takie zdarzenie znaczy, że przez kilka minut istniała otwarta droga na zewnątrz
      # z maszyną w środku. Uśrednianie ukryłoby dokładnie ten przypadek, dla którego alert powstał.
      threshold_value = 0
      duration        = "0s"

      aggregations {
        # Jak przy pozostałych: producent publikuje JEDEN punkt na przebieg `watch.yml`, więc okno
        # wyrównania musi być >= kadencji, inaczej warunek gaśnie i zapala się w rytm crona.
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  # WŁASNY MARTWY-CZŁOWIEK, a nie oparcie się o watchdoga metryki odmów. Ta liczba ma WŁASNY kubełek,
  # WŁASNY sink i WŁASNY grant `logging.viewAccessor` — odebranie tego jednego grantu zatrzymuje wyłącznie
  # ją, a alerty odmów i zmian ACM milczą dalej, bo ich źródła żyją. Bez tego warunku cisza znaczyłaby
  # „nikt nie łamie kolejności", czyli dokładnie to, czego nie wolno założyć.
  conditions {
    display_name = "obserwator przestał publikować liczbę okien bez ochrony"

    condition_absent {
      filter = join(" AND ", [
        "metric.type=\"${local.metryka.sieci_z_obciazeniem}\"",
        "resource.type=\"global\"",
      ])
      duration = "${local.progi.watchdog_absent_seconds}s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  # KANAŁ BEZPIECZEŃSTWA: to jest sygnał o otwartej drodze eksfiltracji, a nie informacja pojemnościowa.
  notification_channels = local.kanal_bezpieczenstwo

  documentation {
    mime_type = "text/markdown"
    subject   = "Maszyna wystartowała w sieci, która nie była jeszcze za granicą"

    # Zdanie „kto i jak to odczuwa" stoi w pierwszym akapicie — wymóg dla każdej reguły CRITICAL.
    content = <<-DOC
      W projekcie będącym członkiem konfiguracji **egzekwowanej** powstała sieć VPC, a **w tej samej sieci
      i w oknie dojrzewania uruchomiono maszynę**. Przez pierwsze **3-5 minut** życia sieci perimetr nie
      uznaje jej za „wewnętrzną": ruch z tej maszyny **wychodzi poza granicę bez odmowy i bez ani jednego
      wpisu audytowego**, a w stanie pośrednim maszyna potrafi **jednocześnie** czytać dane z wnętrza
      perimetru i wysyłać je na zewnątrz.

      **Kto to odczuwa:** właściciel danych w tym projekcie — przez kilka minut jego dane mogły opuścić
      granicę, a granica tego **nie zarejestruje**. Nie odczuwa tego nikt w postaci awarii, i to jest
      najgorsza własność tego zdarzenia: bez tego alertu nie zostaje po nim ŻADEN ślad.

      **To NIE jest kontrola prewencyjna.** Okno zamknęło się, zanim ten alert powstał (obserwator chodzi
      co godzinę). Nie szukaj czegoś do zablokowania — ogranicz SKUTEK.

      **1. Ustal, która sieć i która maszyna.** Adnotacje przebiegu `watch.yml` niosą nazwy i liczbę sekund
      od utworzenia sieci. Niezależnie odczytasz to z widoku sinka:

      ```
      gcloud logging read 'protoPayload.methodName="v1.compute.networks.insert" OR protoPayload.methodName="v1.compute.instances.insert"' \
        --project=<PROJEKT_ADM> --bucket=<KUBELEK_SIECI> --location=<LOKALIZACJA> --view=<KUBELEK_SIECI> \
        --freshness=2h \
        --format='table(timestamp, resource.labels.project_id, protoPayload.methodName, protoPayload.resourceName)'
      ```

      Uwaga na dwa wpisy o tej samej `resourceName` (`operation.first` i `operation.last`) — to jedna
      operacja. Zero czasu okna to wpis WCZEŚNIEJSZY.

      **Adnotacja mówi, SKĄD wzięła się nazwa sieci — przeczytaj to, zanim ją zacytujesz (DEC-44).**
      Trzy możliwe stany, bo maszyna w sieci custom-mode nie niesie pola `network`, tylko `subnetwork`:

      * bez dopisku — sieć odczytana wprost z wpisu maszyny (sieć auto-mode). Nazwa jest faktem;
      * `siec odczytana z mapy podsiec->siec` — sieć wynika z podsieci maszyny i ze zdarzenia
        `subnetworks.insert` z tego samego okna. Nazwa jest faktem;
      * `[HIPOTEZA]` w tytule — mapy **nie było** (podsieć starsza niż okno odczytu albo strumień
        `subnetworks.insert` nie dotarł), więc maszyna została dopasowana fail-closed do każdej świeżej
        sieci w projekcie. Nazwa sieci **nie jest odczytem.** Rozstrzygnij podsiecią z adnotacji:

      ```
      gcloud compute networks subnets describe <PODSIEC> --project=<PROJEKT> --region=<REGION> \
        --format='value(network)'
      ```

      Inna sieć niż w alercie = fałszywy alarm (maszyna stała w sieci dojrzałej). `[HIPOTEZA]` przestała
      być stanem domyślnym i jest teraz sygnałem sama w sobie: jeśli pojawia się seryjnie, sprawdź, czy
      trzeci strumień w ogóle dociera (`subnetworks.insert` w widoku sinka) — sink, który nie dostarcza,
      wygląda dokładnie jak czyste okno.

      **2. Ogranicz, co mogło wyjść.** Okno trwa od utworzenia sieci do ~5 minut później (górna
      obserwacja 5 m 18 s; propagacja migocze, więc bierz górną, nie średnią). Pytanie brzmi: czy ta
      maszyna miała w tym czasie dostęp do czegokolwiek wrażliwego i czy cokolwiek wysyłała. **Nie szukaj
      tego w audit-logu VPC-SC — tam tego nie ma i nie będzie.** Szukaj po stronie workloadu: logi
      aplikacji, ruch wychodzący, uprawnienia konta maszyny.

      **3. Rozstrzygnij, czy to obejście procedury, czy jej brak.** DEC-32 wymaga: sieć powstaje
      **przed** obciążeniem, dojrzewa **≥ 10 minut**, a przed dopuszczeniem ruchu potwierdza się sondą
      **dwie kolejne** rundy z odmową wyjścia. Jeśli dywizja tej procedury nie zna — to jest luka
      w onboardingu, nie incydent tożsamościowy. Jeśli zna i pominęła — to jest obejście kontroli.

      **4. Nie „naprawiaj" tego org policy blokującą tworzenie sieci.** Alternatywa była rozważona
      i odrzucona (DEC-32): zamienia okno czterominutowe na trwałą blokadę czynności legalnej, a wyjątek
      od niej jest tą samą dziurą, tylko z podpisem.

      **Jeśli odpalił DRUGI warunek („obserwator przestał publikować") i stało się to po odtworzeniu
      środowiska od zera — najpierw sprawdź, czy stack sinka w ogóle stoi.** Ta liczba ma własny kubełek,
      własny sink i własny grant, a stawia je **`violations-sink/`** — katalog applikowany przez
      **CZŁOWIEKA** z org-level **`roles/logging.configWriter`**, nie przez pipeline perimetru (konto
      `apply` tego uprawnienia świadomie nie ma). Repo perimetru samo w sobie **nie odtworzy** tego
      strumienia i nie zgłosi jego braku inaczej niż tym alertem:

      ```
      cd violations-sink && terraform init && terraform apply   # tożsamość: człowiek, org-level configWriter
      ```

      Pełna procedura i pomiar: `docs/7-alerty.md#okno-swiezej-sieci`.
    DOC

    links {
      display_name = "runbook"
      url          = "${local.runbook}#okno-swiezej-sieci"
    }
  }
}
