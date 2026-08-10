# Outputy służą narzędziom (raport naruszeń, guard budżetu) i człowiekowi czytającemu wynik apply.
# Nie eksportujemy nic wrażliwego — treść perimetru jest z definicji jawna wewnątrz organizacji.

output "perimeter_name" {
  description = "Pełna nazwa perimetru (accessPolicies/<id>/servicePerimeters/<name>)."
  value       = local.perimeter_full_name
}

output "members_enforced" {
  description = "Projekty w konfiguracji EGZEKWOWANEJ — te są realnie chronione i realnie blokowane."
  value       = sort([for k, m in local.enforced_members : m.project_id])
}

output "members_dry_run_only" {
  description = "Projekty istniejące wyłącznie w konfiguracji dry-run (w oknie obserwacji, jeszcze bez ochrony)."
  value       = sort([for k, m in local.members : m.project_id if m.stage != "enforced"])
}

# Zużycie budżetu atrybutów liczone zachowawczo: każda tożsamość, access level, zasób, usługa i metoda
# konsumuje jeden atrybut. Limit (6000) obowiązuje OSOBNO dla każdej konfiguracji, dlatego liczymy dwa razy.
# Guard w CI czyta ten output — dzięki temu ostrzeżenie pojawia się w PR, a nie dopiero w błędzie API.
output "attribute_estimate" {
  description = "Szacunek zużycia atrybutów per konfiguracja (dry-run i enforced) wobec limitu z policy.yaml."
  # Wyrażenie liczące siedzi w locals.tf (`attribute_usage_*`) i jest współdzielone z kontraktem — patrz
  # komentarz tam. Baseline mnoży się przez liczbę członków, więc przy trzydziestu dywizjach to on zużywa
  # większość budżetu; liczenie samych reguł profilowych dawało wynik ZANIŻONY, czyli guard mówiłby
  # „jest miejsce" dokładnie wtedy, gdy zaczyna go brakować.
  value = {
    limit    = local.policy.attribute_budget.limit_per_config
    dry_run  = local.attribute_usage_dry_run
    enforced = local.attribute_usage_enforced
  }
}
