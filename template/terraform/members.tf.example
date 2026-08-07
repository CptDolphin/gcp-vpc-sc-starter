# Członkostwo projektów. Jeden plik YAML → jeden (lub dwa) zasoby. Diff w PR pokazuje dokładnie tyle,
# ile wniosek zmienia — zamiast przepisania całego perimetru.

# KAŻDY członek trafia do konfiguracji dry-run, niezależnie od etapu. To ona odpowiada na pytanie
# „co by się zepsuło, gdyby ten projekt był chroniony" i zbiera naruszenia do raportu per członek.
resource "google_access_context_manager_service_perimeter_dry_run_resource" "member" {
  for_each = local.members

  perimeter_name = local.perimeter_full_name
  resource       = "projects/${each.value.project_number}"
}

# Do konfiguracji EGZEKWOWANEJ wchodzą tylko ci ze `stage: enforced`. Od tej chwili perimetr realnie
# blokuje ich ruch — dlatego zmiana tego pola wymaga osobnego PR-a i człowieka (DEC-4), a reguła OPA
# promotion_gate pilnuje, że okno dry-run było wystarczająco długie i czyste.
resource "google_access_context_manager_service_perimeter_resource" "member" {
  for_each = local.enforced_members

  perimeter_name = local.perimeter_full_name
  resource       = "projects/${each.value.project_number}"

  # Usunięcie projektu z perimetru to operacja, którą w incydencie wykonuje się świadomie (break-glass).
  # Domyślne DELETE jest tu właściwe — chcemy, by offboarding przez usunięcie pliku po prostu działał.
  deletion_policy = "DELETE"
}
