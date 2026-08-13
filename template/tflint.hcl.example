# Statyczna analiza HCL — warstwa między `terraform validate` (składnia + typy) a `terraform test`
# (semantyka renderera). tflint łapie to, czego żadna z nich nie widzi: martwe zmienne, brakujące wersje
# providerów, nieaktualne konstrukcje, literówki w atrybutach zasobów Google.
#
# DLACZEGO to jest osobna bramka, a nie „validate wystarczy": `validate` przechodzi na konfiguracji, która
# ma zadeklarowaną i nigdy nieużywaną zmienną albo brakujący pin providera. W repo zarządzającym granicą
# bezpieczeństwa organizacji obie te rzeczy są realnym ryzykiem — pierwsza to martwy knob, o którym ktoś
# pomyśli, że działa, druga to ciche podbicie majora providera na obiekcie org-plane.
#
# URUCHOMIENIE — `--config` z BEZWZGLĘDNĄ ścieżką jest obowiązkowe:
#
#     tflint --init
#     tflint --chdir=terraform       --config="$PWD/.tflint.hcl" --minimum-failure-severity=notice
#     tflint --chdir=iam-bootstrap   --config="$PWD/.tflint.hcl" --minimum-failure-severity=notice
#     tflint --chdir=violations-sink --config="$PWD/.tflint.hcl" --minimum-failure-severity=notice
#
# Lista jest po JEDNYM wierszu na stack i ma być kompletna — pilnuje tego selftest, który wyprowadza
# stacki z drzewa repozytorium, a nie z tej listy (DEC-34). Stack pominięty tutaj i w `validate.yml`
# nie jest „jeszcze nieobjęty": jest katalogiem z HCL-em, którego nie czyta żadna bramka.
#
# PUŁAPKA, która nas złapała przy wdrażaniu: `--chdir=X` szuka `.tflint.hcl` w katalogu **X**, nie w tym, z
# którego uruchomiono polecenie. Bez `--config` ten plik jest cicho ignorowany — tflint działa wtedy na
# domyślnym presecie, bez pluginu google i bez reguł niżej. Wynik jest zielony i nic nie znaczy. Dokładnie ten
# sam tryb awarii co bramka, która SKIPuje się bez narzędzia: wygląda na sprawdzone, nie było sprawdzone.
# Dlatego guard w selfteście sprawdza, że CI przekazuje `--config`, a nie tylko że krok „tflint" istnieje.

plugin "terraform" {
  enabled = true
  # Zestaw rekomendowany zamiast domyślnego: dokłada m.in. wymóg pinowania wersji providerów
  # i konwencje nazewnicze. To repozytorium jest oddawane innemu zespołowi, więc styl ma
  # być egzekwowany, nie sugerowany.
  preset = "recommended"
}

plugin "google" {
  enabled = true
  version = "0.35.0"
  source  = "github.com/terraform-linters/tflint-ruleset-google"
}

# Nazewnictwo bez myślników w blokach Terraforma — parytet z ograniczeniem API Access Context Managera
# (short_name obiektu: litera, dalej alfanumeryczne i `_`). Jedna konwencja w plikach i w chmurze.
rule "terraform_naming_convention" {
  enabled = true
  format  = "snake_case"
}

# Komentarz nagłówkowy w każdym pliku jest w tym repo obowiązkowy (styl: WHY, nie WHAT), ale tego tflint nie
# sprawdzi — dlatego reguła o dokumentacji zmiennych, która pilnuje przynajmniej ich opisów.
rule "terraform_documented_variables" {
  enabled = true
}

rule "terraform_documented_outputs" {
  enabled = true
}

# ŚWIADOMIE WYŁĄCZONE: `terraform_module_version` (nie używamy modułów zewnętrznych — cała logika jest tu,
# renderer to locals) oraz `terraform_required_version` poza stackiem perimetru byłoby duplikatem — pin jest
# w `versions.tf` każdego stacku i sprawdza go `terraform_required_providers`.
rule "terraform_module_version" {
  enabled = false
}
