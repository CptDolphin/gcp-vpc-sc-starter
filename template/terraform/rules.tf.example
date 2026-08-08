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
          for_each = operations.value.methods
          content {
            method = method_selectors.value
          }
        }
      }
    }
  }

  # Reguła bierze access level po NAZWIE (string z YAML), a nie przez adres zasobu, więc Terraform nie widzi
  # tu żadnej zależności i przy `destroy` może skasować poziom PRZED regułą, która go referuje. API odrzuca
  # to wprost: `you must first remove the reference`. Zmierzone na żywym ACM 2026-08-07 (#1904) — trafia
  # każdy offboarding członka, którego reguła używa access levelu.
  depends_on = [google_access_context_manager_access_level.level]
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
          for_each = operations.value.methods
          content {
            method = method_selectors.value
          }
        }
      }
    }
  }

  # Reguła egzekwowana musi zależeć od członkostwa egzekwowanego: reguła bez projektu w konfiguracji nie
  # ma czego autoryzować, a odwrotna kolejność (projekt bez reguł) odcina ruch na czas między zasobami.
  # Access level — patrz komentarz przy wariancie dry-run: nazwa ze stringa nie tworzy krawędzi w grafie,
  # więc bez tej pozycji `destroy` kasuje poziom, gdy reguła jeszcze go referuje.
  depends_on = [
    google_access_context_manager_service_perimeter_resource.member,
    google_access_context_manager_access_level.level,
  ]
}

resource "google_access_context_manager_service_perimeter_dry_run_egress_policy" "rule" {
  for_each = local.egress_rules_all

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
          for_each = operations.value.methods
          content {
            method = method_selectors.value
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
          for_each = operations.value.methods
          content {
            method = method_selectors.value
          }
        }
      }
    }
  }

  depends_on = [google_access_context_manager_service_perimeter_resource.member]
}
