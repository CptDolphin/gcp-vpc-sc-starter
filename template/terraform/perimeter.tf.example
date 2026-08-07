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

      conditions {
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
  }
}

resource "google_access_context_manager_service_perimeter" "this" {
  # BROWNFIELD: gdy perimetr już istnieje i nie przejęliśmy go importem, ten zasób NIE powstaje
  # (perimeter.manage_skeleton = false w policy.yaml). Członkowie i reguły odwołują się wtedy do
  # perimetru po NAZWIE (local.perimeter_full_name), więc reszta modułu działa bez zmian.
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
    # teraz CICHO IGNOROWANE. Członkowie wchodzą przez pliki w perimeter/members/, nigdy tutaj.
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
