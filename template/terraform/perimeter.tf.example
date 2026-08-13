# Szkielet perimetru + access levels. Szkielet niesie WYŁĄCZNIE baseline (usługi objęte granicą).
# Członkostwo i reguły dokładają zasoby granularne (members.tf, rules.tf) — patrz `ignore_changes` niżej.

resource "google_access_context_manager_access_level" "level" {
  for_each = local.access_levels

  parent      = "accessPolicies/${local.policy_id}"
  name        = "accessPolicies/${local.policy_id}/accessLevels/${each.key}"
  title       = each.value.title
  description = "Managed by the VPC-SC perimeter repository. Do not edit in the console."

  # `basic` i `custom` WYKLUCZAJĄ się wzajemnie — poziom ma albo warunki deklaratywne, albo wyrażenie CEL.
  # Renderujemy `basic` tylko wtedy, gdy poziom nie deklaruje `custom_expression`.
  dynamic "basic" {
    for_each = contains(keys(each.value), "custom_expression") ? [] : [1]
    content {
      # Domyślne AND: warunki muszą być spełnione ŁĄCZNIE. Przy OR lista warunków staje się alternatywą
      # („albo korpo-IP, albo urządzenie"), co jest słabszą polityką i trudną do zauważenia w review.
      combining_function = lookup(each.value, "combining_function", "AND")

      # WARUNEK BEZPOŚREDNI renderuje się TYLKO wtedy, gdy poziom deklaruje choć jeden jego atrybut.
      #
      # Blok statyczny (bez `dynamic`) wysyłał do API warunek `{}` także dla poziomu złożonego wyłącznie
      # z `required_access_levels` — a API odrzuca PUSTY warunek komunikatem
      # `Error 400: AccessLevel definition has a trivial condition.` (raw REST, zmierzone 2026-08-11).
      # Przez ten kształt materiał twierdził, że „kompozycja bez własnego warunku jest odrzucana przez API".
      # NIEPRAWDA: ten sam poziom wysłany do ACM z pominięciem tego renderera (`{"basic":{"conditions":
      # [{"requiredAccessLevels":[...]}]}}`) POWSTAJE bez błędu. Ograniczenie było NASZE, nie Google'a —
      # i blokowało `corp_network AND corp_managed_device`, czyli najmocniejszy wariant dostępu człowieka.
      dynamic "conditions" {
        for_each = anytrue([
          contains(keys(each.value), "ip_subnetworks"),
          contains(keys(each.value), "members"),
          contains(keys(each.value), "regions"),
          contains(keys(each.value), "negate"),
          contains(keys(each.value), "device_policy"),
        ]) ? [1] : []
        content {
          ip_subnetworks = lookup(each.value, "ip_subnetworks", null)
          # Tożsamości: grupy i konta serwisowe. Bez tego poziom mówi tylko „z tej sieci".
          members = lookup(each.value, "members", null)
          # Kody ISO 3166-1 alfa-2 — tanie ucięcie szumu, nie zabezpieczenie (VPN to omija).
          regions = lookup(each.value, "regions", null)
          # `negate` odwraca sens CAŁEGO warunku — patrz ostrzeżenie w access-levels/corp.yaml.
          negate = lookup(each.value, "negate", null)

          dynamic "device_policy" {
            for_each = contains(keys(each.value), "device_policy") ? [each.value.device_policy] : []
            content {
              require_screen_lock              = lookup(device_policy.value, "require_screen_lock", null)
              require_corp_owned               = lookup(device_policy.value, "require_corp_owned", null)
              require_admin_approval           = lookup(device_policy.value, "require_admin_approval", null)
              allowed_encryption_statuses      = lookup(device_policy.value, "allowed_encryption_statuses", null)
              allowed_device_management_levels = lookup(device_policy.value, "allowed_device_management_levels", null)

              dynamic "os_constraints" {
                for_each = lookup(device_policy.value, "os_constraints", [])
                content {
                  os_type                    = os_constraints.value.os_type
                  minimum_version            = lookup(os_constraints.value, "minimum_version", null)
                  require_verified_chrome_os = lookup(os_constraints.value, "require_verified_chrome_os", null)
                }
              }
            }
          }
        }
      }

      # Kompozycja: poziom zbudowany z innych poziomów. Renderujemy pełne nazwy, bo API nie przyjmuje skrótów
      # (ten sam błąd co przy access levels w regułach — plan przechodzi, apply pada).
      dynamic "conditions" {
        for_each = length(lookup(each.value, "required_access_levels", [])) > 0 ? [1] : []
        content {
          required_access_levels = [
            for lvl in each.value.required_access_levels :
            "accessPolicies/${local.policy_id}/accessLevels/${lvl}"
          ]
        }
      }
    }
  }

  # Wyrażenie CEL — wyłącznie gdy warunki `basic` nie wystarczają. Trudniejsze do zaudytowania, więc
  # traktujemy jak wyjątek, nie jak alternatywę pierwszego wyboru.
  dynamic "custom" {
    for_each = contains(keys(each.value), "custom_expression") ? [1] : []
    content {
      expr {
        expression = each.value.custom_expression
      }
    }
  }

  lifecycle {
    # Poziom nie może być jednocześnie `basic` i `custom` — API odrzuci to komunikatem o konflikcie pól,
    # ale wtedy jesteśmy już w połowie apply. Precondition zatrzymuje to na planie.
    precondition {
      condition = !(contains(keys(each.value), "custom_expression") && anytrue([
        contains(keys(each.value), "ip_subnetworks"),
        contains(keys(each.value), "members"),
        contains(keys(each.value), "regions"),
        contains(keys(each.value), "device_policy"),
        contains(keys(each.value), "required_access_levels"),
      ]))
      error_message = "Access level ${each.key}: `custom_expression` wyklucza się z warunkami basic (ip_subnetworks/members/regions/device_policy/required_access_levels). Wybierz jedno."
    }

    # Poziom, który nie deklaruje ŻADNEGO warunku, renderuje się na `basic {}` bez ani jednego `conditions`
    # — czyli obiekt, który nie sprawdza niczego. Do 2026-08 ratował nas przed nim przypadek: statyczny blok
    # `conditions` zawsze coś wysyłał, więc API odrzucało to jako `trivial condition`. Po naprawie tamtego
    # kształtu ten przypadek nie ma już żadnej bariery poniżej, więc bariera musi stać tutaj — na planie,
    # z nazwą poziomu w komunikacie, a nie w odpowiedzi API o „trywialnym warunku" bez wskazania winowajcy.
    precondition {
      condition = anytrue([
        contains(keys(each.value), "ip_subnetworks"),
        contains(keys(each.value), "members"),
        contains(keys(each.value), "regions"),
        contains(keys(each.value), "device_policy"),
        contains(keys(each.value), "required_access_levels"),
        contains(keys(each.value), "custom_expression"),
      ])
      error_message = "Access level ${each.key}: brak jakiegokolwiek warunku — poziom bez warunku nie ogranicza niczego. Dodaj ip_subnetworks/members/regions/device_policy/required_access_levels albo custom_expression."
    }

    # `combining_function: OR` = ALTERNATYWA warunków. Diff jest jednosłowny i wygląda kosmetycznie, a
    # polityka po nim jest SŁABSZA: poziom `region PL/DE ORAZ korpo-sieć` zamienia się w `region PL/DE ALBO
    # korpo-sieć`, czyli przepuszcza dowolny adres z regionu. ZMIERZONE na żywym ACM: API przyjmuje taką
    # zmianę bez ostrzeżenia (`combiningFunction: OR` wraca w odpowiedzi 200), więc jedyne miejsce, gdzie
    # ktokolwiek może to zauważyć, jest PRZED apply.
    #
    # Dlaczego opt-in tekstem, a nie zakaz: „korpo-sieć ALBO zarządzane urządzenie" to poprawny i częsty
    # wymóg (laptop w domu na zarządzanym sprzęcie). Zakaz wypchnąłby ten wzorzec do `custom_expression`,
    # czyli w miejsce trudniejsze do audytu. Wymóg `or_reason` zamienia jednosłowny diff w zdanie
    # o osłabieniu — recenzent czyta powód, a nie domyśla się intencji.
    precondition {
      condition     = lookup(each.value, "combining_function", "AND") != "OR" || length(lookup(each.value, "or_reason", "")) >= 20
      error_message = "Access level ${each.key}: `combining_function: OR` czyni z warunków ALTERNATYWĘ (słabsza polityka). Dopisz `or_reason` (min. 20 znaków) wyjaśniające, dlaczego alternatywa jest tu zamierzona."
    }

    # OR bez drugiego warunku nie robi NIC — `combiningFunction` łączy warunki między sobą, a atrybuty
    # wewnątrz jednego warunku i tak są zawsze ANDowane. Poziom z jednym warunkiem i `OR` w deklaracji
    # wygląda w pliku jak decyzja, a jest nieporozumieniem; przy dołożeniu drugiego warunku ożywa jako
    # osłabienie, którego nikt świadomie nie wprowadził. Renderer produkuje dziś dokładnie dwa warunki:
    # bezpośredni (gdy są atrybuty) i kompozycyjny (gdy jest `required_access_levels`).
    precondition {
      condition = lookup(each.value, "combining_function", "AND") != "OR" || (
        anytrue([
          contains(keys(each.value), "ip_subnetworks"),
          contains(keys(each.value), "members"),
          contains(keys(each.value), "regions"),
          contains(keys(each.value), "negate"),
          contains(keys(each.value), "device_policy"),
        ]) && length(lookup(each.value, "required_access_levels", [])) > 0
      )
      error_message = "Access level ${each.key}: `combining_function: OR` przy jednym warunku nie zmienia niczego (OR łączy warunki, nie atrybuty w jednym warunku). Usuń je albo dołóż drugi warunek."
    }

    # --- UZBROJENIE: pięć barier na jeden defekt „poziom wygląda na gotowy i nie wpuszcza nikogo" ---
    #
    # Nazwa `armed` jest CZĘŚCIĄ mechanizmu, nie ozdobą: bramka nie umie orzec, czy zakres jest
    # prawdziwy (tego z konfiguracji orzec się NIE DA), umie za to wymusić, żeby ktoś to powiedział
    # wprost i podpisał datą. Rozróżnienie „świadomy placeholder" vs „niedokończona robota" jest całą
    # treścią tej kontroli — bo jedno i drugie renderuje się na identyczny obiekt w ACM.

    # 1. Zakresy wyłącznie dokumentacyjne = poziom, którego nikt nie spełni. Musi to powiedzieć.
    precondition {
      condition = !(
        length(lookup(each.value, "ip_subnetworks", [])) > 0 &&
        alltrue([
          for c in lookup(each.value, "ip_subnetworks", []) :
          anytrue([for p in local.documentation_prefixes : startswith(lower(c), p)])
        ])
      ) || lookup(each.value, "armed", true) == false
      error_message = "Access level ${each.key}: wszystkie `ip_subnetworks` to zakresy DOKUMENTACYJNE (RFC 5737 / RFC 3849) — nie ma ich żaden host, więc ten poziom nie autoryzuje nikogo. Podmień je na własne (wtedy `armed: true` + `source_of_truth` + `reviewed`) albo zadeklaruj `armed: false` z `unarmed_reason`."
    }

    # 2. Nieuzbrojenie bez powodu jest nieodróżnialne od zapomnianego pliku.
    precondition {
      condition     = lookup(each.value, "armed", true) || length(lookup(each.value, "unarmed_reason", "")) >= 30
      error_message = "Access level ${each.key}: `armed: false` wymaga `unarmed_reason` (min. 30 znaków) — inaczej nie da się odróżnić decyzji od niedokończonej konfiguracji."
    }

    # 3. NIEOSIĄGALNOŚĆ DZIEDZICZY SIĘ PRZEZ `AND`. Kompozycja bez własnych zakresów IP wypada z każdego
    #    „przeglądu zakresów", a nie wpuszcza nikogo, bo wymaga poziomu, którego nikt nie spełnia. Warunek
    #    jest LOKALNY (rodzic vs jego bezpośrednie dzieci) i domyka się indukcyjnie: skoro każdy rodzic
    #    nieuzbrojonego dziecka sam musi być nieuzbrojony, to żaden łańcuch kompozycji tego nie przemyci.
    #    HCL nie ma rekurencji, więc domknięcie przechodnie liczone wprost byłoby tu albo niepełne,
    #    albo rozwinięte na sztywną głębokość — indukcja jest i pełna, i czytelna w komunikacie.
    precondition {
      condition = lookup(each.value, "armed", true) == false || alltrue([
        for lvl in lookup(each.value, "required_access_levels", []) :
        lookup(lookup(local.access_levels, lvl, {}), "armed", true)
      ])
      error_message = "Access level ${each.key}: `armed: true`, ale składnik z `required_access_levels` jest nieuzbrojony. `AND` wymaga OBU warunków, więc ta kompozycja też nie wpuszcza nikogo — oznacz ją `armed: false` z `unarmed_reason` albo uzbrój składnik."
    }

    # 4. FAIL-CLOSED TAM, GDZIE TO KOSZTUJE: poziom nieuzbrojony referowany przez konfigurację
    #    EGZEKWOWANĄ. W dry-run niedokończona konfiguracja jest na miejscu — po to jest dry-run.
    #    W konfiguracji, która realnie blokuje, reguła oparta na takim poziomie nie autoryzuje nikogo,
    #    a wygląda w konsoli na obecną. Furtka istnieje (bo „ta reguła świadomie dziś nie wpuszcza
    #    nikogo" bywa poprawnym stanem etapu wdrożenia), ale WYGASA — zapis bez daty zostaje na zawsze.
    precondition {
      condition = lookup(each.value, "armed", true) || !contains(
        local.access_levels_referenced_by_enforced,
        "accessPolicies/${local.policy_id}/accessLevels/${each.key}"
        ) || timecmp(
        "${lookup(each.value, "unarmed_accepted_until", "1970-01-01")}T23:59:59Z", plantimestamp()
      ) > 0
      error_message = "Access level ${each.key}: jest NIEUZBROJONY, a referuje go reguła w konfiguracji EGZEKWOWANEJ — ta reguła nie autoryzuje dziś nikogo. Uzbrój poziom albo dopisz `unarmed_accepted_until: RRRR-MM-DD` (data w przyszłości) jako świadomy, wygasający zapis."
    }

    # 5. ATESTACJA ZAKRESU: skąd wartość i kiedy potwierdzona. Bez tego „zakres jest aktualny" jest
    #    zdaniem bez autora i bez daty — a zakres, który przestał pasować, wygląda identycznie jak
    #    działający. Zegar jest twardy TYLKO dla poziomów stojących w konfiguracji egzekwowanej: tam
    #    cisza kosztuje odcięcie ludzi, a w dry-run kosztuje ostrzeżenie.
    precondition {
      condition = !(lookup(each.value, "armed", true) && length(lookup(each.value, "ip_subnetworks", [])) > 0) || (
        length(lookup(each.value, "source_of_truth", "")) >= 10 && length(lookup(each.value, "reviewed", "")) > 0
      )
      error_message = "Access level ${each.key}: uzbrojony poziom z `ip_subnetworks` wymaga `source_of_truth` (skąd zakres: firewall/NAT/VPN/CMDB) i `reviewed` (kiedy sieć to potwierdziła)."
    }

    precondition {
      condition = !(
        lookup(each.value, "armed", true) &&
        length(lookup(each.value, "ip_subnetworks", [])) > 0 &&
        contains(local.access_levels_referenced_by_enforced, "accessPolicies/${local.policy_id}/accessLevels/${each.key}")
        ) || timecmp(
        timeadd(
          "${lookup(each.value, "reviewed", "1970-01-01")}T00:00:00Z",
          "${lookup(each.value, "review_interval_days", local.access_level_review_default_days) * 24}h"
        ),
        plantimestamp()
      ) > 0
      error_message = "Access level ${each.key}: atestacja zakresu (`reviewed`) jest przeterminowana, a poziom stoi w konfiguracji EGZEKWOWANEJ. Potwierdź zakres z zespołem sieciowym i podnieś `reviewed` — albo wydłuż `review_interval_days`, jeśli to świadoma decyzja."
    }
  }
}

resource "google_access_context_manager_service_perimeter" "this" {
  # BROWNFIELD: gdy perimetr już istnieje i nie przejęliśmy go importem, ten zasób NIE powstaje
  # (perimeter.manage_skeleton = false w policy.yaml). Członkowie i reguły odwołują się wtedy do
  # perimetru po NAZWIE (local.perimeter_full_name), więc reszta modułu działa bez zmian.
  #
  # WSZYSTKIE SZEŚĆ ZASOBÓW GRANULARNYCH (members.tf, rules.tf) niesie `depends_on` NA TEN ZASÓB — bo
  # odwołanie po nazwie nie tworzy krawędzi w grafie, a bez niej greenfieldowy apply puszcza szkielet
  # i jego zawartość równolegle i kończy się `Error 404: Service perimeter not found` (#2034).
  # Przy `count = 0` te krawędzie są bezkosztowe: wskazują zasób o pustym zbiorze instancji.
  count = local.manage_skeleton ? 1 : 0

  parent         = "accessPolicies/${local.policy_id}"
  name           = local.perimeter_full_name
  title          = local.policy.perimeter.title
  perimeter_type = "PERIMETER_TYPE_REGULAR"

  # Konfiguracja dry-run musi mieć WŁASNĄ treść, inaczej dziedziczy egzekwowaną — a wtedy nie da się mieć
  # członka istniejącego wyłącznie w dry-run, czyli nie da się etapować onboardingu (DEC-4).
  use_explicit_dry_run_spec = true

  # status = konfiguracja EGZEKWOWANA (ta realnie blokuje).
  status {
    restricted_services = local.restricted_services

    vpc_accessible_services {
      enable_restriction = local.policy.vpc_accessible_services.enable_restriction
      allowed_services   = local.accessible_services
    }
  }

  # spec = konfiguracja DRY-RUN (loguje, nie blokuje).
  spec {
    restricted_services = local.restricted_services

    vpc_accessible_services {
      enable_restriction = local.policy.vpc_accessible_services.enable_restriction
      allowed_services   = local.accessible_services
    }
  }

  lifecycle {
    # WYMAGANE przy zasobach granularnych. Bez tego szkielet i zasoby per-członek/per-reguła biją się o te
    # same listy: każdy apply usuwałby to, co dodał poprzedni (flapping granicy bezpieczeństwa).
    # KONSEKWENCJA, o której trzeba pamiętać: dopisanie projektu albo reguły WPROST do tego bloku jest od
    # teraz CICHO IGNOROWANE. Członkowie wchodzą przez wpisy w perimeter/projects.yaml, nigdy tutaj.
    ignore_changes = [
      status[0].resources,
      status[0].ingress_policies,
      status[0].egress_policies,
      spec[0].resources,
      spec[0].ingress_policies,
      spec[0].egress_policies,
    ]

    # Vertex AI jest powodem istnienia tego perimetru. Gdyby wypadł z baseline'u, perimetr dalej wyglądałby
    # w konsoli na włączony, chroniąc usługi, o które nikt nie prosił — najgorszy rodzaj awarii, bo niemy.
    precondition {
      condition     = contains(local.restricted_services, "aiplatform.googleapis.com")
      error_message = "Baseline musi zawierać aiplatform.googleapis.com — bez niego perimetr nie chroni Vertex AI (perimeter/policy.yaml)."
    }

    # Perimetr bez ani jednego członka egzekwowanego jest dopuszczalny (tak wygląda dzień pierwszy), ale
    # członek egzekwowany bez reguł ingress to prawie zawsze pomyłka: nikt nie dosięgnie jego API.
    precondition {
      condition     = length(local.enforced_members) == 0 || length(local.ingress_rules_enforced) > 0
      error_message = "Są członkowie w stage=enforced, ale zero reguł ingress w konfiguracji egzekwowanej — po apply odetniesz im dostęp."
    }
  }
}
