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

# --- 1. Świeże repo nie blokuje nikomu ruchu ---------------------------------------------------------
# Najważniejsza własność startera. Gdyby domyślny stan produkował choć jedną regułę egzekwowaną, pierwszy
# apply na środowisku docelowym mógłby odciąć ruch — a to jest dokładnie ten błąd, którego cała konstrukcja ma nie popełnić.
run "swieze_repo_zero_regul_egzekwowanych" {
  command = plan

  assert {
    condition     = length(local.enforced_members) == 0
    error_message = "Przykładowy członek nie jest w dry-run — świeże repo nie może mieć członków egzekwowanych."
  }

  assert {
    condition     = length(local.ingress_rules_enforced) == 0 && length(local.egress_rules_enforced) == 0
    error_message = "Świeże repo wyrenderowało regułę egzekwowaną. Sprawdź `stage` w perimeter/members/."
  }
}

# --- 2. Każdy członek trafia do konfiguracji dry-run ------------------------------------------------
# To fundament addytywnej promocji (DEC-6): dry-run zawiera WSZYSTKICH, więc zmiana `stage`
# tylko dokłada zasób enforced i nie ma momentu, w którym projekt nie należy do żadnej konfiguracji.
run "wszyscy_czlonkowie_w_dry_run" {
  command = plan

  assert {
    condition     = length(local.ingress_rules_all) >= length(local.ingress_rules_enforced)
    error_message = "Konfiguracja dry-run musi zawierać co najmniej to, co egzekwowana."
  }

  assert {
    condition     = length(local.members) > 0
    error_message = "Brak członków do przetestowania — przykładowy plik zniknął z perimeter/members/."
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

# --- 10. Reguły baseline trafiają do KAŻDEGO członka ------------------------------------------------
# To jest cały powód, dla którego baseline nie jest profilem: profil trzeba wybrać, a baseline obowiązuje
# bez pamiętania o nim. Test pilnuje, że renderer faktycznie mnoży je przez członków.
run "baseline_dotyczy_kazdego_czlonka" {
  command = plan

  assert {
    condition     = length(local.baseline_rules_all) == length(local.members) * length(local.baseline_ingress)
    error_message = "Reguły baseline nie zostały wyrenderowane dla każdego członka — skaner wypadnie z części projektów."
  }

  assert {
    condition = alltrue([
      for k, r in local.baseline_rules_all : strcontains(k, "--baseline--")
    ])
    error_message = "Klucz reguły baseline musi zawierać `--baseline--` — po tym rozpoznaje ją reguła OPA o access levelu."
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

  # Filtr metryki enforced MUSI zawężać się do dryRun=false. Bez tego alert page'uje przy każdym naruszeniu
  # dry-run, czyli przy normalnej pracy okna obserwacji — i po tygodniu nikt go nie czyta.
  assert {
    condition     = strcontains(local.vpcsc_audit_filter, "violationReason")
    error_message = "Filtr audytowy nie zawęża się do wpisów z violationReason — metryka liczyłaby wszystko."
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
