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
  value = {
    limit = local.policy.attribute_budget.limit_per_config
    # `ingress_rules_effective`, nie `ingress_rules_all`: baseline mnoży się przez liczbę członków, więc
    # przy trzydziestu dywizjach to on zużywa większość budżetu. Liczenie samych reguł profilowych dawało
    # tu wynik ZANIŻONY — czyli guard mówiłby „jest miejsce" dokładnie wtedy, gdy zaczyna go brakować.
    dry_run = sum(concat([0], [
      for k, r in merge(local.ingress_rules_effective, local.egress_rules_all) :
      length(r.identities) + length(lookup(r, "access_levels", [])) + length(r.resources)
      + length(lookup(r, "external_resources", []))
      + sum(concat([0], [for op in r.operations : 1 + length(op.methods)]))
    ]))
    enforced = sum(concat([0], [
      for k, r in merge(local.ingress_rules_enforced, local.egress_rules_enforced) :
      length(r.identities) + length(lookup(r, "access_levels", [])) + length(r.resources)
      + length(lookup(r, "external_resources", []))
      + sum(concat([0], [for op in r.operations : 1 + length(op.methods)]))
    ]))
  }
}
