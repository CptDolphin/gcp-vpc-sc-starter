# Reguły ingress/egress wyrenderowane z par (członek × profil). Każda reguła to osobny zasób, więc błąd
# w jednym wniosku wywraca własną regułę, a nie apply całego perimetru.

resource "google_access_context_manager_service_perimeter_dry_run_ingress_policy" "rule" {
  for_each = local.ingress_rules_effective

  perimeter = local.perimeter_full_name
  title     = each.value.title

  ingress_from {
    identities = each.value.identities

    dynamic "sources" {
      for_each = each.value.access_levels
      content {
        access_level = sources.value
      }
    }
  }

  ingress_to {
    resources = each.value.resources

    dynamic "operations" {
      for_each = each.value.operations
      content {
        service_name = operations.value.service

        dynamic "method_selectors" {
          for_each = lookup(operations.value, "methods", [])
          content {
            method = method_selectors.value
          }
        }

        dynamic "method_selectors" {
          for_each = lookup(operations.value, "permissions", [])
          content {
            permission = method_selectors.value
          }
        }
      }
    }
  }

  # Reguła bierze access level po NAZWIE (string z YAML), a nie przez adres zasobu, więc Terraform nie widzi
  # tu żadnej zależności i przy `destroy` może skasować poziom PRZED regułą, która go referuje. API odrzuca
  # to wprost: `you must first remove the reference`. Zmierzone na żywym ACM 2026-08-07 (#1904) — trafia
  # każdy offboarding członka, którego reguła używa access levelu.
  #
  # Perimetr wskazuje TA SAMA konstrukcja — string, nie atrybut — więc krawędź do szkieletu też musi być
  # jawna. Powód w całości: members.tf, zasób `…dry_run_resource.member` (#2034).
  depends_on = [
    google_access_context_manager_access_level.level,
    google_access_context_manager_service_perimeter.this,
  ]
}

resource "google_access_context_manager_service_perimeter_ingress_policy" "rule" {
  for_each = local.ingress_rules_enforced

  perimeter = local.perimeter_full_name
  title     = each.value.title

  ingress_from {
    identities = each.value.identities

    dynamic "sources" {
      for_each = each.value.access_levels
      content {
        access_level = sources.value
      }
    }
  }

  ingress_to {
    resources = each.value.resources

    dynamic "operations" {
      for_each = each.value.operations
      content {
        service_name = operations.value.service

        dynamic "method_selectors" {
          for_each = lookup(operations.value, "methods", [])
          content {
            method = method_selectors.value
          }
        }

        dynamic "method_selectors" {
          for_each = lookup(operations.value, "permissions", [])
          content {
            permission = method_selectors.value
          }
        }
      }
    }
  }

  # Reguła egzekwowana musi zależeć od członkostwa egzekwowanego: reguła bez projektu w konfiguracji nie
  # ma czego autoryzować, a odwrotna kolejność (projekt bez reguł) odcina ruch na czas między zasobami.
  # Access level — patrz komentarz przy wariancie dry-run: nazwa ze stringa nie tworzy krawędzi w grafie,
  # więc bez tej pozycji `destroy` kasuje poziom, gdy reguła jeszcze go referuje.
  # Szkielet stoi tu JAWNIE, choć droga do niego prowadzi już przez `…_resource.member`. Ta pozycja jest
  # w `terraform graph` NIEWIDOCZNA (redukcja przechodnia zjada krawędź implikowaną przez ścieżkę) i to
  # jest właśnie powód, dla którego ma tu być: gdy ktoś zdejmie krawędź do szkieletu z members.tf, ta
  # przejmuje kolejność zamiast zniknąć razem z nią. ZMIERZONE (#2034): usunięcie pozycji szkieletu
  # z `…_resource.member` odbiera grafowi jedną krawędź i DORYSOWUJE dwie — dokładnie tę i jej
  # odpowiednik przy egressie. Bez nich ten sam ruch zrywałby kolejność TRZEM zasobom, nie jednemu.
  depends_on = [
    google_access_context_manager_service_perimeter_resource.member,
    google_access_context_manager_access_level.level,
    google_access_context_manager_service_perimeter.this,
  ]
}

resource "google_access_context_manager_service_perimeter_dry_run_egress_policy" "rule" {
  for_each = local.egress_rules_all

  # Krawędź do szkieletu — powód w całości w members.tf, zasób `…dry_run_resource.member` (#2034).
  # Ten wariant był JEDYNYM zasobem granularnym bez ani jednego `depends_on`: nie referuje access levelu
  # (egress rozstrzyga tożsamość wołającego, nie kontekst sieci) ani członkostwa egzekwowanego, więc do
  # #2034 nie miał w grafie żadnej krawędzi wychodzącej i startował dokładnie razem ze szkieletem.
  depends_on = [google_access_context_manager_service_perimeter.this]

  perimeter = local.perimeter_full_name
  title     = each.value.title

  egress_from {
    identities = each.value.identities
  }

  egress_to {
    resources = each.value.resources
    # Tylko BigQuery Omni (patrz profil bq-omni-external-read). Pusta lista = pole nie ma wpływu, więc nie
    # trzeba go warunkować dynamikiem — a jawne pole pokazuje w planie, że reguła NIE wypuszcza nic na zewnątrz.
    external_resources = each.value.external_resources

    dynamic "operations" {
      for_each = each.value.operations
      content {
        service_name = operations.value.service

        dynamic "method_selectors" {
          for_each = lookup(operations.value, "methods", [])
          content {
            method = method_selectors.value
          }
        }

        dynamic "method_selectors" {
          for_each = lookup(operations.value, "permissions", [])
          content {
            permission = method_selectors.value
          }
        }
      }
    }
  }
}

resource "google_access_context_manager_service_perimeter_egress_policy" "rule" {
  for_each = local.egress_rules_enforced

  perimeter = local.perimeter_full_name
  title     = each.value.title

  egress_from {
    identities = each.value.identities
  }

  egress_to {
    resources = each.value.resources
    # Tylko BigQuery Omni (patrz profil bq-omni-external-read). Pusta lista = pole nie ma wpływu, więc nie
    # trzeba go warunkować dynamikiem — a jawne pole pokazuje w planie, że reguła NIE wypuszcza nic na zewnątrz.
    external_resources = each.value.external_resources

    dynamic "operations" {
      for_each = each.value.operations
      content {
        service_name = operations.value.service

        dynamic "method_selectors" {
          for_each = lookup(operations.value, "methods", [])
          content {
            method = method_selectors.value
          }
        }

        dynamic "method_selectors" {
          for_each = lookup(operations.value, "permissions", [])
          content {
            permission = method_selectors.value
          }
        }
      }
    }
  }

  # Szkielet jawnie, obok członkostwa — uzasadnienie przy regule ingress egzekwowanej wyżej: krawędź jest
  # dziś przechodnia (i przez to niewidoczna w `terraform graph`), ale przestaje być w chwili, w której
  # ktoś zmieni `depends_on` w members.tf (#2034).
  depends_on = [
    google_access_context_manager_service_perimeter_resource.member,
    google_access_context_manager_service_perimeter.this,
  ]
}
