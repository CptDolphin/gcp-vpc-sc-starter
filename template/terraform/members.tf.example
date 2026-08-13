# Członkostwo projektów. Jeden plik YAML → jeden (lub dwa) zasoby. Diff w PR pokazuje dokładnie tyle,
# ile wniosek zmienia — zamiast przepisania całego perimetru.

# KAŻDY członek trafia do konfiguracji dry-run, niezależnie od etapu. To ona odpowiada na pytanie
# „co by się zepsuło, gdyby ten projekt był chroniony" i zbiera naruszenia do raportu per członek.
resource "google_access_context_manager_service_perimeter_dry_run_resource" "member" {
  for_each = local.members

  perimeter_name = local.perimeter_full_name
  resource       = "projects/${each.value.project_number}"

  # KRAWĘDŹ DO SZKIELETU — powód tej pozycji jest KANONICZNY dla wszystkich sześciu zasobów granularnych
  # (dwa tutaj, cztery w rules.tf), dlatego stoi w całości w jednym miejscu, a tamte na nią wskazują.
  #
  # Zasób granularny wskazuje perimetr `local.perimeter_full_name` — STRINGIEM złożonym z YAML-a, a nie
  # atrybutem `google_access_context_manager_service_perimeter.this`. Terraform nie ma więc jak zobaczyć,
  # że jedno jest częścią drugiego: przy tworzeniu od zera puszcza szkielet i wszystkich członków/reguły
  # RÓWNOLEGLE (domyślne `-parallelism=10`), a ACM odpowiada wtedy `Error 404: Service perimeter not found`.
  #
  # ZMIERZONE 2026-08-13 (#2034, ćwiczenie DR na żywej granicy): po skasowaniu perimetru `apply.yml` dał
  # `Plan: 20 to add` i CZTERY takie 404 naraz; szkielet po tym przebiegu też nie istniał (`perimeters
  # describe` → `NOT_FOUND`), czyli pojedyncze „uruchom drugi raz" nie było wyjściem. Odzysk wymagał
  # człowieka z lokalnym Terraformem: `terraform apply -target=…service_perimeter.this` (12 s), po którym
  # pipeline domknął resztę bez błędu. To jest ta sama klasa defektu co przy access levelach (DEC-33):
  # referencja po nazwie nie tworzy krawędzi w grafie.
  #
  # BROWNFIELD (`manage_skeleton: false`) DZIAŁA DALEJ i to jest tu najważniejszy przypadek brzegowy.
  # `depends_on` celuje w ZASÓB, nie w jego instancję: przy `count = 0` zbiór instancji jest pusty, więc
  # nie ma na co czekać, a węzeł i tak stoi w grafie — czyli krawędź jest wtedy prawdziwa i bezkosztowna.
  # Wariant „referencja przez atrybut" (`one(google_…this[*].name)`) ODRZUCONY: w brownfieldzie dałby
  # `perimeter_name = null`, a w greenfieldzie `known after apply` na polu ForceNew.
  #
  # KIERUNEK PRZY NISZCZENIU jest dokładnie ten, którego chcemy: `depends_on` odwraca się przy `destroy`,
  # więc członkowie i reguły znikają PRZED szkieletem. Odwrotna kolejność to 404 na każdym z nich.
  #
  # CZYTAJĄC `terraform graph` NIE SZUKAJ SZEŚCIU KRAWĘDZI — narysowane są CZTERY. Wyjście tej komendy jest
  # po REDUKCJI PRZECHODNIEJ, więc krawędź implikowana przez istniejącą ścieżkę (reguła egzekwowana →
  # `…_resource.member` → szkielet) nie jest rysowana. Dlatego bramka w selfteście pyta o OSIĄGALNOŚĆ
  # (istnieje ścieżka), a nie o obecność krawędzi — asercja na krawędzi byłaby czerwona na kodzie poprawnym.
  depends_on = [google_access_context_manager_service_perimeter.this]
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

  # Krawędź do szkieletu — powód w całości przy wariancie dry-run wyżej (#2034).
  depends_on = [google_access_context_manager_service_perimeter.this]
}
