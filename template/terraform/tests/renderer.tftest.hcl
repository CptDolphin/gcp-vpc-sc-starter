# Natywne testy Terraforma dla renderera — uruchamiane BEZ dostępu do chmury.
#
# DLACZEGO obok selftestu w Pythonie: selftest sprawdza, że starter jako całość działa (install, bramki,
# workflows). Te testy sprawdzają JEDNĄ rzecz, której nie widać z zewnątrz: czy `locals.tf` poprawnie
# tłumaczy YAML na reguły. To jest jedyne miejsce w tym repo, gdzie mieszka logika — reszta to deklaracje.
#
# Testujemy na poziomie planu: `terraform test` z `command = plan`, `expect_failures` dla warunków, bez apply-testu
# (nie ma czego applikować bez organizacji).
#
#   terraform init -backend=false && terraform test
#
# UWAGA na `command = plan`: przy `manage_skeleton: false` i pustym katalogu members plan nie tworzy niczego,
# więc testy operują na `local.*` przez asercje na wyrażeniach, nie na atrybutach zasobów.

# --- 1. Reguła egzekwowana powstaje WYŁĄCZNIE dla członka `stage: enforced` --------------------------
#
# TU BYŁA ASERCJA „świeże repo ma zero reguł egzekwowanych" i BYŁ TO BŁĄD KATEGORII. Ten plik jedzie
# `install.sh` do repozytorium docelowego i tam wykonuje się na JEGO deklaracjach, a nie na przykładzie
# ze startera. Własność „zero enforced" jest prawdziwa dla świeżego szablonu i przestaje być prawdziwa
# w chwili, w której ktoś użyje produktu zgodnie z przeznaczeniem — czyli promuje pierwszego członka.
# Zmierzone na wdrożeniu: pierwsza legalna promocja zapaliła `validate` na czerwono i zablokowała sama
# siebie, a komunikat mówił „sprawdź stage w members/" przy `stage` ustawionym dokładnie tak, jak trzeba.
# Bramka, która blokuje jedyną operację, dla której system istnieje, nie chroni niczego — uczy obchodzenia.
#
# Własność świeżego szablonu ZOSTAJE, tylko tam, gdzie da się ją sprawdzić uczciwie: w selfteście, który
# instaluje szablon do katalogu tymczasowego i pyta `terraform console` o `local.ingress_rules_enforced`
# (test „swieze repo nie ma zadnej reguly egzekwowanej"). Tam „świeże" znaczy świeże.
#
# Tutaj zostaje niezmiennik, który jest prawdziwy ZAWSZE i łapie ten sam realny tryb awarii — regułę
# egzekwowaną, której nikt nie zamawiał: żadna reguła nie może wejść do konfiguracji egzekwowanej dla
# członka, który nie jest `enforced`.
run "enforced_tylko_dla_czlonka_enforced" {
  command = plan

  # Filtr `if r.scope == "profile"` NIE jest osłabieniem asercji, tylko warunkiem jej sensowności: po kolapsie
  # reguła baseline nie ma JEDNEGO właściciela (`member = null`), więc `local.members[r.member]` wywróciłby
  # test na indeksie, a nie na naruszeniu niezmiennika. Baseline pilnuje osobna, MOCNIEJSZA asercja niżej —
  # tam sprawdzamy komplet zasobów reguły zbiorczej, a nie etap pojedynczego członka.
  assert {
    condition = alltrue([
      for k, r in local.ingress_rules_enforced :
      local.members[r.member].stage == "enforced" if r.scope == "profile"
    ])
    error_message = "Reguła ingress trafiła do konfiguracji egzekwowanej dla członka, który nie jest w stage: enforced."
  }

  # Reguła baseline w konfiguracji EGZEKWOWANEJ obejmuje DOKŁADNIE członków `stage: enforced` — tylko że
  # od DEC-11 wyraża to `*` („dowolny zasób w TEJ konfiguracji"), a nie wyliczona lista. Zawężenie robi więc
  # sam perimetr: do `status.resources` wchodzą wyłącznie promowani (members.tf). Asercja pilnuje, żeby
  # renderer nie wrócił do listy — bo lista jest `ForceNew` i każda promocja replace'owałaby regułę wspólną.
  assert {
    condition = alltrue([
      for k, r in local.ingress_rules_enforced :
      length(r.resources) == 1 && r.resources[0] == "*"
      if r.scope == "baseline"
    ])
    error_message = "Reguła baseline w konfiguracji egzekwowanej nie celuje w `*` — wróciła lista zależna od członkostwa (ForceNew przy każdej promocji)."
  }

  # Egzekwowana reguła baseline powstaje TYLKO wtedy, gdy jest kogo autoryzować. Reguła z `*` w perimetrze
  # bez ani jednego promowanego członka nie autoryzowałaby niczego dziś, ale przy `manage_skeleton: false`
  # objęłaby pierwszy zasób dołożony do `status` spoza tego repo.
  assert {
    condition     = length(local.enforced_members) > 0 || length(local.baseline_rules_enforced) == 0
    error_message = "Reguła baseline jest w konfiguracji egzekwowanej mimo zera członków stage: enforced."
  }

  assert {
    condition = alltrue([
      for k, r in local.egress_rules_enforced : local.members[r.member].stage == "enforced"
    ])
    error_message = "Reguła egress trafiła do konfiguracji egzekwowanej dla członka, który nie jest w stage: enforced."
  }

  assert {
    condition = alltrue([
      for k, m in local.enforced_members : m.stage == "enforced"
    ])
    error_message = "local.enforced_members zawiera członka spoza stage: enforced."
  }
}

# --- 2. Promocja jest ADDYTYWNA: dry-run zawiera wszystko, co egzekwowane ---------------------------
#
# To fundament DEC-6: dry-run zawiera WSZYSTKICH, więc zmiana `stage` tylko dokłada zasób enforced i nie
# ma momentu, w którym projekt nie należy do żadnej konfiguracji.
#
# POPRZEDNIA WERSJA TEGO TESTU PORÓWNYWAŁA DWA RÓŻNE ZBIORY i przez to nie sprawdzała niczego, co
# deklarowała: `ingress_rules_all` to alias na reguły Z PROFILI, a `ingress_rules_enforced` filtruje
# `ingress_rules_effective`, czyli profile PLUS baseline. Przy pierwszej promocji dało to `2 >= 3` → false
# i test padał na własnym błędzie, a nie na naruszeniu niezmiennika. Zbiór, który realnie ląduje
# w konfiguracji dry-run (zasób `..._dry_run_ingress_policy`), to `ingress_rules_effective` — i to jego
# trzeba porównywać. Sprawdzamy przez KLUCZE, nie przez liczności: równa liczność przy rozjechanych
# kluczach wygląda tak samo jak zgodność.
run "promocja_jest_addytywna" {
  command = plan

  assert {
    condition = alltrue([
      for k, _ in local.ingress_rules_enforced : contains(keys(local.ingress_rules_effective), k)
    ])
    error_message = "Reguła ingress jest w konfiguracji egzekwowanej, ale nie ma jej w dry-run — promocja przestała być addytywna."
  }

  assert {
    condition = alltrue([
      for k, _ in local.egress_rules_enforced : contains(keys(local.egress_rules_all), k)
    ])
    error_message = "Reguła egress jest w konfiguracji egzekwowanej, ale nie ma jej w dry-run — promocja przestała być addytywna."
  }

  assert {
    condition     = length(local.ingress_rules_effective) >= length(local.ingress_rules_enforced)
    error_message = "Konfiguracja dry-run musi zawierać co najmniej to, co egzekwowana."
  }

  assert {
    condition     = length(local.members) > 0
    error_message = "Brak członków do przetestowania — przykładowy wpis zniknął z perimeter/projects.yaml."
  }
}

# --- 2b. KLUCZ CZŁONKA = `<dywizja>-<project_id>` ---------------------------------------------------
#
# Ta asercja jest ZAMKIEM NA ADRESY W STANIE, a nie sprawdzeniem logiki — i dlatego jest trywialnie
# prawdziwa dla dzisiejszego renderera. O to chodzi: klucz `for_each` JEST adresem zasobu w stanie
# Terraform, a granularne reguły ACM nie mają aktualizacji w miejscu w wariancie dry-run (DEC-11), więc
# przeadresowanie to `destroy` + `create` na żywej granicy. Przy pliku na projekt ten ciąg brała nazwa
# pliku; po przejściu na `perimeter/projects.yaml` (DEC-12) bierze go treść wpisu — i dokładnie dlatego
# migracja nie miała w planie ani jednego `destroy`.
#
# Test padnie w chwili, w której ktoś „uprości" klucz do samego `project_id` albo dołoży do niego
# środowisko. To jest zmiana, którą wolno zrobić — ale z `moved{}` i świadomie, a nie w przelocie.
run "klucz_czlonka_pochodzi_z_dywizji_i_projektu" {
  command = plan

  assert {
    condition = alltrue([
      for k, m in local.members : k == "${m.division}-${m.project_id}"
    ])
    error_message = "Klucz członka przestał być `<dywizja>-<project_id>` — to jest adres zasobu w stanie; zmiana wymaga `moved{}`, inaczej plan skasuje i odtworzy reguły ACM."
  }
}

# --- 2a. Reguła baseline MUSI mieć źródło — inaczej nie autoryzuje niczego ---------------------------
#
# ZMIERZONE na żywym ACM: reguła baseline bez ani jednego `sources` stała w konfiguracji dry-run osiem
# minut, a wywołanie dokładnie tej tożsamości na dokładnie tej metodzie i tak wygenerowało naruszenie
# z `violationReason: NO_MATCHING_ACCESS_LEVEL`. `ingress_from` bez źródła jest dla API regułą, która nie
# pasuje do niczego — a wygląda w konsoli i w planie na obecną.
#
# Skutek dotyczy dokładnie tych przepływów, dla których baseline istnieje (skaner, raport naruszeń), więc
# ochrona znikała w momencie, w którym zaczynała być potrzebna: przy pierwszej promocji.
run "baseline_ma_zrodlo" {
  command = plan

  assert {
    condition = alltrue([
      for k, r in local.baseline_rules_all : length(r.access_levels) > 0
    ])
    error_message = "Reguła baseline bez ani jednego źródła (`sources`) nie autoryzuje niczego — API czyta ją jako NO_MATCHING_ACCESS_LEVEL."
  }

  # Kontrola anty-tautologiczna: gdyby baseline zniknął z policy.yaml, asercja wyżej przechodziłaby na
  # pustym zbiorze i nie badała niczego. Materiał startera deklaruje baseline, więc tu musi ich być >0.
  assert {
    condition     = length(local.baseline_rules_all) > 0
    error_message = "Brak reguł baseline do przetestowania — asercja o źródłach byłaby pusta."
  }

  # Reguła z jawnym `allow_without_access_level` renderuje się jako „dowolne pochodzenie sieciowe" (`*`),
  # a nie jako nazwa access levelu. To jedyny kształt, który API honoruje dla autoryzacji samą tożsamością.
  assert {
    condition = alltrue(flatten([
      for r in local.baseline_ingress : [
        for k, br in local.baseline_rules_all :
        # Porównanie przez długość i element, nie `== ["*"]`: literał jest krotką, a wyrenderowana wartość
        # przychodzi z wyrażenia warunkowego, więc równość na całych kolekcjach potrafi wywrócić się na
        # typie (tuple vs list) przy identycznej treści — czyli test padałby na czymś innym, niż bada.
        length(br.access_levels) == 1 && br.access_levels[0] == "*"
        if br.title == "baseline--${r.title}"
      ] if lookup(r, "allow_without_access_level", false) && length(lookup(r, "access_levels", [])) == 0
    ]))
    error_message = "Reguła baseline z allow_without_access_level nie wyrenderowała źródła `*`."
  }
}

# --- 3. Renderowanie profili: liczba reguł = suma reguł z profili wskazanych przez członków ----------
run "renderer_liczy_reguly_z_profili" {
  command = plan

  assert {
    condition = length(local.ingress_rules_all) == sum([
      for mkey, m in local.members : sum([
        for p in m.profiles : length(lookup(local.profiles[p.name], "ingress", []))
      ])
    ])
    error_message = "Liczba wyrenderowanych reguł ingress nie zgadza się z sumą reguł z profili członków."
  }
}

# --- 4. Egress nie powstaje z pustej listy celów ----------------------------------------------------
# Bezpieczna degradacja: pusty cel MUSI dać brak reguły, nie regułę bez zasobów (taka reguła w API jest
# odrzucana albo — gorzej — interpretowana szeroko).
# UWAGA na kształt warunku: cel bywa WEWNĘTRZNY (`resources`, projekty GCP) albo ZEWNĘTRZNY
# (`external_resources`, BigQuery Omni). Test wymagający niepustych `resources` odrzucałby poprawną regułę
# czysto zewnętrzną — liczy się suma obu list, nie jedna z nich.
run "egress_bez_celow_nie_powstaje" {
  command = plan

  assert {
    condition = alltrue([
      for k, r in local.egress_rules_all : length(r.resources) + length(r.external_resources) > 0
    ])
    error_message = "Wyrenderowano regułę egress bez ani jednego celu — pusty cel musi dawać BRAK reguły."
  }
}

# --- 5. Klucze for_each są deterministyczne i zawierają wszystkie trzy wymiary -----------------------
# Niestabilny klucz = przenumerowanie cudzych zasobów przy dodaniu członka i fałszywe replace'y w planie.
run "klucze_for_each_zawieraja_trzy_wymiary" {
  command = plan

  assert {
    condition = alltrue([
      for k, r in local.ingress_rules_all : length(split("--", k)) == 3
    ])
    error_message = "Klucz reguły musi mieć postać <członek>--<profil>--<tytuł>; inaczej dodanie członka przenumeruje cudze zasoby."
  }

  assert {
    condition = alltrue([
      for k, r in local.ingress_rules_all : startswith(r.title, r.member)
    ])
    error_message = "Tytuł reguły musi zaczynać się od nazwy członka — inaczej nie da się jej przypisać do właściciela w konsoli."
  }
}

# --- 6. Reguły ingress celują WYŁĄCZNIE w projekt swojego członka -----------------------------------
# Reguła jednej dywizji nie może obejmować projektu innej. Profil dopuszcza tylko `to: member_project`,
# ale to test pilnuje, że renderer faktycznie to respektuje.
run "ingress_celuje_w_projekt_wlasnego_czlonka" {
  command = plan

  assert {
    condition = alltrue([
      for k, r in local.ingress_rules_all :
      r.resources == ["projects/${local.members[r.member].project_number}"]
    ])
    error_message = "Reguła ingress wskazuje inny projekt niż projekt swojego członka."
  }
}

# --- 7. Access levels renderują się na pełne nazwy w polityce ----------------------------------------
# Skrócona nazwa (`corp_network` zamiast `accessPolicies/<id>/accessLevels/corp_network`) jest przyjmowana
# przez plan i odrzucana przez API — czyli błąd, który wychodzi dopiero na apply.
run "access_levels_maja_pelne_nazwy" {
  command = plan

  assert {
    condition = alltrue(flatten([
      for k, r in local.ingress_rules_all : [
        for al in r.access_levels : startswith(al, "accessPolicies/")
      ]
    ]))
    error_message = "Access level w regule musi być pełną nazwą accessPolicies/<id>/accessLevels/<nazwa>."
  }
}

# --- 8. Baseline chroni Vertex AI -------------------------------------------------------------------
run "baseline_zawiera_aiplatform" {
  command = plan

  assert {
    condition     = contains(local.restricted_services, "aiplatform.googleapis.com")
    error_message = "Baseline bez aiplatform.googleapis.com — perimetr nie chroniłby Vertex AI (DEC-1)."
  }

  assert {
    condition     = length(setsubtract(local.accessible_services, local.restricted_services)) == 0
    error_message = "vpc_accessible_services zawiera usługę spoza restricted_services — pod-skopowana lista cicho psuje bootstrap workloadów."
  }
}

# --- 9. Kontrakt nie wynosi tożsamości ani reguł ----------------------------------------------------
# Ten sam warunek pilnuje selftest po stronie tekstu pliku; tutaj sprawdzamy WYRENDEROWANĄ treść, czyli to,
# co realnie poleci do bucketa.
run "kontrakt_nie_zawiera_tozsamosci_ani_regul" {
  command = plan

  assert {
    condition = alltrue([
      for m in local.contract_document.members :
      length(setsubtract(keys(m), ["division", "project_id", "stage"])) == 0
    ])
    error_message = "Sekcja members w kontrakcie ma pola poza division/project_id/stage — kontrakt wynosi dane."
  }

  assert {
    condition = alltrue([
      for p in local.contract_document.profiles :
      length(setsubtract(keys(p), ["name", "risk", "summary", "parameters", "has_egress"])) == 0
    ])
    error_message = "Sekcja profiles w kontrakcie ma pola poza interfejsem profilu — nie publikujemy treści reguł."
  }

  assert {
    condition = alltrue([
      for al in local.contract_document.access_levels : !strcontains(al, "/")
    ])
    error_message = "Kontrakt publikuje pełne ścieżki access levels zamiast samych nazw."
  }
}

# --- 10. Baseline: JEDNA reguła na tytuł, obejmująca KAŻDEGO członka --------------------------------
# Baseline nie jest profilem, bo profil trzeba wybrać, a baseline obowiązuje bez pamiętania o nim — i to się
# nie zmieniło. Zmienił się KSZTAŁT: zamiast `liczba_członków × liczba_reguł` zasobów powstaje `liczba_reguł`,
# a przynależność członka wyraża JEDNA POZYCJA w `ingress_to.resources`. Powód jest policzalny: przy starym
# kształcie baseline kosztował 21 atrybutów na członka przy limicie 6000 na konfigurację (sufit ~230 członków).
run "baseline_jest_jedna_regula_na_tytul" {
  command = plan

  assert {
    condition     = length(local.baseline_rules_all) == length(local.baseline_ingress)
    error_message = "Liczba reguł baseline zależy od liczby członków — kolaps się cofnął, a z nim sufit członków."
  }

  # NAJMOCNIEJSZA asercja tego runa i jednocześnie ANTY-TAUTOLOGIA odporna na liczbę członków: przy JEDNYM
  # członku „jedna reguła na tytuł" i „jedna reguła na członka × tytuł" dają tę samą LICZBĘ, więc sama
  # liczność niczego by nie rozstrzygała w materiale startera. Klucz rozstrzyga zawsze — stary kształt
  # wkładał w niego nazwę członka (`<członek>--baseline--<tytuł>`), nowy nie może jej zawierać.
  assert {
    condition = alltrue([
      for k, r in local.baseline_rules_all :
      alltrue([for mkey, _ in local.members : !strcontains(k, mkey)])
    ])
    error_message = "Klucz reguły baseline zawiera nazwę członka — reguła znów renderuje się per członek."
  }

  # Tytuł jest JEDNYM z warunków, po których bramka OPA rozpoznaje regułę baseline (drugim jest zgodność
  # tożsamości i operacji z `policy.yaml` — patrz `regula_odpowiada_baseline` w policy/perimeter.rego).
  # Rozjazd tytułu z `policy.yaml` nie wywala planu — po prostu wyjątek przestaje obowiązywać i legalna
  # reguła baseline zapala bramkę na `resources = ["*"]` oraz na braku access levelu.
  assert {
    condition = alltrue([
      for r in local.baseline_ingress :
      contains(keys(local.baseline_rules_all), "baseline--${r.title}")
    ])
    error_message = "Tytuł reguły baseline nie ma postaci `baseline--<tytuł z policy.yaml>` — bramka OPA jej nie rozpozna."
  }

  # --- 10a. REGUŁA BASELINE NIE ZALEŻY OD CZŁONKOSTWA -------------------------------------------------
  #
  # TEGO TESTU NIE BYŁO I DLATEGO DEFEKT PRZESZEDŁ. Po kolapsie (DEC-10) reguła baseline była jedna, ale jej
  # `ingress_to.resources` nadal rosło z każdym członkiem — a to pole jest `ForceNew`, więc KAŻDY wniosek
  # onboardingowy REPLACE'ował obie reguły baseline (zmierzone: `Plan: 4 to add, 1 to change, 2 to destroy`).
  # W konfiguracji egzekwowanej replace = okno bez reguły skanera i bez reguły raportu naruszeń dla
  # WSZYSTKICH promowanych naraz. Testy pilnowały KOMPLETNOŚCI listy i przez to utrwalały jej istnienie.
  #
  # Niezmiennik zapisany tak, żeby nie dało się go spełnić listą: cel reguły baseline to DOKŁADNIE jeden
  # element i jest nim `*`. Dodanie członka nie ma wtedy czego zmienić.
  assert {
    condition = alltrue([
      for k, r in local.baseline_rules_all :
      length(r.resources) == 1 && r.resources[0] == "*"
    ])
    error_message = "Reguła baseline celuje w listę projektów zamiast w `*` — każdy nowy członek będzie ją REPLACE'ował (ForceNew)."
  }

  # Asercja komplementarna: gdyby ktoś zostawił `*` i DOŁOŻYŁ do niego listę („na wszelki wypadek"), warunek
  # wyżej padłby na długości, a ten mówi wprost, czego w tym polu nie ma prawa być.
  assert {
    condition = alltrue(flatten([
      for k, r in local.baseline_rules_all : [
        for res in r.resources : !startswith(res, "projects/")
      ]
    ]))
    error_message = "Reguła baseline wymienia projekt po numerze — cel reguły znów zależy od członkostwa."
  }

  # ANTY-TAUTOLOGIA: obie asercje wyżej przechodzą trywialnie na pustej mapie. Materiał startera ma
  # baseline i ma członka, więc jeśli którejkolwiek z tych liczb nie ma, testy wyżej niczego nie zbadały.
  assert {
    condition     = length(local.baseline_rules_all) > 0 && length(local.members) > 0
    error_message = "Brak reguł baseline albo brak członków — asercje o kształcie celu byłyby puste."
  }

  # Zasoby renderują się z `ingress_rules_effective`, więc suma musi się zgadzać. Gdyby ktoś podmienił
  # for_each w rules.tf z powrotem na `ingress_rules_all`, baseline przestałby powstawać — cicho.
  assert {
    condition     = length(local.ingress_rules_effective) == length(local.ingress_rules_all) + length(local.baseline_rules_all)
    error_message = "ingress_rules_effective nie jest sumą reguł profilowych i baseline."
  }
}

# --- 11. Monitoring: alert bez procedury i bez odbiorcy jest atrapą ---------------------------------
# Każda reguła critical niesie runbook. Alert o 3:00 bez procedury to zgadywanie,
# a alert bez kanału powiadomień to wpis w konsoli, którego nikt nie zobaczy.
run "monitoring_alerty_maja_procedure" {
  command = plan

  assert {
    condition     = local.monitoring_enabled
    error_message = "Przykładowa policy.yaml nie ma sekcji monitoring — starter ma pokazywać monitoring, nie go pomijać."
  }

  # DWIE POLITYKI GRANICY MUSZĄ POWSTAĆ W PRZYKŁADZIE. Wcześniej stała tu asercja o kształcie filtra
  # metryki log-based — i mierzyła konstrukcję, która NIE MOGŁA LICZYĆ (#2000): metryka log-based widzi
  # wyłącznie wpisy przyjęte przez Log Router własnego projektu, a naruszenia powstają w logu członka,
  # zmiany ACM zaś w logu organizacji. Test pilnował więc poprawności czegoś strukturalnie martwego.
  # Dziś oba sygnały jadą z widoku sinka, a warunkiem ich istnienia jest sekcja `violations_source`.
  assert {
    condition     = local.naruszenia_count == 1
    error_message = "Przykładowy alerting.yaml nie ma sekcji violations_source — bez niej NIE POWSTAJĄ alerty o odmowie egzekwowanej i o zmianie konfiguracji poza pipelinem, czyli granica zostaje bez sygnału mówiącego, że ktoś jest blokowany TERAZ."
  }

  # Producent i konsument muszą mówić o tej samej metryce. Rozjazd = alert patrzący na metrykę, do której
  # nikt nie pisze, czyli cisza nie do odróżnienia od spokoju.
  assert {
    condition     = startswith(local.metryka.naruszenia_enforced, "custom.googleapis.com/vpcsc/")
    error_message = "Metryka odmów wróciła na tor log-based (`logging.googleapis.com/user/…`) — ta konstrukcja nie policzy NIGDY niczego, patrz nagłówek monitoring.tf."
  }
}

# --- 12. Egress do zasobów POZA Google Cloud --------------------------------------------------------
# Ta ścieżka jest testowana, bo przykładowy członek świadomie z niej korzysta. Kod egressu bez ani jednego
# członka byłby napisany i nieprzetestowany — czyli działałby pierwszy raz na produkcji.
run "egress_zewnetrzny_renderuje_sie_i_ma_poprawny_format" {
  command = plan

  # Liczba wyrenderowanych reguł z zasobem zewnętrznym MUSI się zgadzać z liczbą takich celów ZADEKLAROWANYCH
  # przez członków. Warunek był wcześniej zapisany jako „> 0" i mierzył nie renderer, lecz obecność
  # PRZYKŁADOWEGO członka: pierwsze prawdziwe wdrożenie (które przykłady kasuje i wstawia swoich członków)
  # dostawało czerwony test mówiący „profil przestał się renderować", choć nikt go po prostu nie używa.
  # Premisę liczymy z WEJŚCIA (deklaracje + profile), nigdy z wyjścia renderera — inaczej asercja brzmiałaby
  # „skoro nic nie powstało, to dobrze, że nic nie powstało" i nie badałaby niczego. Równość zamiast „> 0"
  # jest przy tym OSTRZEJSZA w obie strony: łapie i regułę zgubioną, i wymyśloną z niczego.
  assert {
    condition = length([
      for k, r in local.egress_rules_all : k if length(r.external_resources) > 0
      ]) == length(flatten([
        for mkey, m in local.members : [
          for p in m.profiles : [
            for rule in lookup(local.profiles[p.name], "egress", []) :
            rule.title if length(lookup(p.params, lookup(rule, "to_external_from", "__none__"), [])) > 0
          ]
        ]
    ]))
    error_message = "Liczba reguł egress z zasobem zewnętrznym nie zgadza się z liczbą celów zadeklarowanych przez członków — renderer gubi albo dokłada reguły."
  }

  # Format narzuca API: s3://BUCKET albo azure://ACCOUNT.blob.core.windows.net/CONTAINER. ARN przechodzi
  # plan i pada na apply, dlatego ten sam warunek pilnuje osobno bramka OPA na plikach.
  assert {
    condition = alltrue(flatten([
      for k, r in local.egress_rules_all : [
        for e in r.external_resources : startswith(e, "s3://") || startswith(e, "azure://")
      ]
    ]))
    error_message = "Zasób zewnętrzny w innym formacie niż s3:// / azure:// — API odrzuci to na apply."
  }

  # KSZTAŁT SELEKTORÓW przy zasobie zewnętrznym. ZMIERZONE na żywym ACM 2026-08-11: z ustawionym
  # `external_resources` API przyjmuje WYŁĄCZNIE selektory `permission` — `methods` kończy się
  # `Error 400: With 'external_resources' set, MethodSelector is only allowed to have permission`.
  # Profil `bq-omni-external-read` miał od dnia powstania `methods: [JobService.Query, JobService.InsertJob]`
  # i NIE DAŁ SIĘ ZAPLIKOWAĆ ANI RAZU; nikt tego nie widział, bo żaden członek go nie używał.
  #
  # Premisa liczona z WEJŚCIA (jak w asercji wyżej), żeby test nie brzmiał „skoro nic nie powstało, to dobrze".
  assert {
    condition = length([
      for k, r in local.egress_rules_all : k
      if length(r.external_resources) > 0 && alltrue([
        for op in r.operations : length(lookup(op, "permissions", [])) > 0 && length(lookup(op, "methods", [])) == 0
      ])
      ]) == length([
      for k, r in local.egress_rules_all : k if length(r.external_resources) > 0
    ])
    error_message = "Reguła egress z zasobem zewnętrznym używa selektorów `methods` — API przyjmuje tam wyłącznie `permissions` (Error 400: MethodSelector is only allowed to have permission)."
  }

  # `egress_from` NIE NIESIE ŹRÓDEŁ — i to jest decyzja, nie przeoczenie. API to potrafi
  # (`egressFrom.sources.accessLevel` + `sourceRestriction` są w schemacie providera 7.43.0), ale
  # `rules.tf` składa `egress_from` wyłącznie z `identities`. Dopóki tak jest, access level w regule egress
  # byłby CICHO GUBIONY: przed poprawką z 2026-08-11 `access_levels_from` w regule egress przechodziło
  # schemat i OPA, budżet atrybutów je LICZYŁ (53 → 54), a `egress_from.sources` w planie zostawało puste.
  # Ta asercja pilnuje, żeby nikt nie dołożył access levels do modelu egressu, nie tknąwszy renderera.
  assert {
    condition = alltrue([
      for k, r in local.egress_rules_all : length(lookup(r, "access_levels", [])) == 0
    ])
    error_message = "Reguła egress niesie access_levels, a renderer składa egress_from wyłącznie z identities — dopisz `sources` (i `source_restriction`) do rules.tf albo usuń pole."
  }

  # Cel wewnętrzny i zewnętrzny są ROZŁĄCZNE w naszym modelu (patrz nagłówek profilu): reguła bez ani jednego
  # celu nie może powstać, bo API interpretuje ją szerzej, niż wygląda.
  assert {
    condition = alltrue([
      for k, r in local.egress_rules_all : length(r.resources) + length(r.external_resources) > 0
    ])
    error_message = "Wyrenderowano regułę egress bez ani jednego celu (ani projektu, ani zasobu zewnętrznego)."
  }
}

# --- 13. Budżet atrybutów liczy baseline ------------------------------------------------------------
# Guard budżetu ma jeden obowiązek: nie kłamać w stronę „jest miejsce". Baseline mnoży się przez liczbę
# członków, więc pominięcie go zaniżałoby szacunek dokładnie tam, gdzie limit zaczyna boleć (30 dywizji).
run "budzet_liczy_reguly_baseline" {
  command = plan

  assert {
    condition     = output.attribute_estimate.dry_run >= output.attribute_estimate.enforced
    error_message = "Szacunek dla dry-run jest mniejszy niż dla enforced — dry-run zawiera wszystkich, więc to niemożliwe."
  }

  assert {
    condition     = output.attribute_estimate.dry_run > 0
    error_message = "Szacunek zużycia atrybutów wynosi zero przy niepustym repo — guard budżetu nic nie mierzy."
  }

  # ANTY-TAUTOLOGIA. Dwie asercje wyżej przechodzą TAKŻE wtedy, gdy baseline nie jest liczony — spełnia je
  # każdy dodatni szacunek, więc tytuł tego runa obiecywał więcej, niż sprawdzał. Ta porównuje szacunek
  # z tym samym rachunkiem policzonym po SAMYCH regułach profilowych (`ingress_rules_all`, bez baseline'u):
  # dopóki baseline jest doliczany, szacunek musi być ostro większy. Po podmianie `_effective` na `_all`
  # w locals.tf obie strony się zrównują i asercja pada — czyli test mierzy dokładnie tę pomyłkę.
  assert {
    condition = output.attribute_estimate.dry_run > sum(concat([0], [
      for k, r in merge(local.ingress_rules_all, local.egress_rules_all) :
      length(r.identities) + length(lookup(r, "access_levels", [])) + length(r.resources)
      + length(lookup(r, "external_resources", []))
      + sum(concat([0], [for op in r.operations : 1 + length(lookup(op, "methods", [])) + length(lookup(op, "permissions", []))]))
    ]))
    error_message = "Szacunek nie rośnie po doliczeniu reguł baseline — guard ich nie liczy, a API tak."
  }

  # Kontrakt i output MUSZĄ podawać tę samą liczbę. Rozjazd (kontrakt liczył dry-run bez baseline'u, a
  # enforced z baselinem) daje konsumentowi inny budżet niż ten, na którym pada guard CI.
  assert {
    condition = (local.contract_budget.used_dry_run == output.attribute_estimate.dry_run
    && local.contract_budget.used_enforced == output.attribute_estimate.enforced)
    error_message = "Budżet w kontrakcie różni się od `attribute_estimate` — dwie liczby na jedno pytanie."
  }
}

# --- 14. Access levels: kompozycja, tożsamości, regiony ---------------------------------------------
# Poziom składany z innych poziomów musi wskazywać PEŁNE nazwy — skrót przechodzi plan i pada na apply,
# czyli w połowie zmiany polityki produkcyjnej.
run "access_levels_kompozycja_i_warunki" {
  command = plan

  assert {
    condition = length([
      for name, al in local.access_levels : name if length(lookup(al, "required_access_levels", [])) > 0
    ]) > 0
    error_message = "Brak poziomu składanego z innych — przykład kompozycji zniknął z perimeter/access-levels/."
  }

  # Każdy poziom wskazywany w kompozycji musi istnieć w katalogu. Literówka daje tu błąd API, a nie planu.
  assert {
    condition = alltrue(flatten([
      for name, al in local.access_levels : [
        for req in lookup(al, "required_access_levels", []) : contains(keys(local.access_levels), req)
      ]
    ]))
    error_message = "Poziom wskazuje w required_access_levels nazwę, której nie ma w katalogu access-levels/."
  }

  # `basic` i `custom` wykluczają się wzajemnie — precondition w perimeter.tf pilnuje tego przy renderowaniu,
  # ten test pilnuje, że przykłady w repo tej zasady nie łamią.
  assert {
    condition = alltrue([
      for name, al in local.access_levels :
      !(contains(keys(al), "custom_expression") && anytrue([
        contains(keys(al), "ip_subnetworks"),
        contains(keys(al), "members"),
        contains(keys(al), "regions"),
        contains(keys(al), "device_policy"),
        contains(keys(al), "required_access_levels"),
      ]))
    ])
    error_message = "Poziom miesza custom_expression z warunkami basic — API odrzuci to jako konflikt pól."
  }
}
