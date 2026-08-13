#!/usr/bin/env bash
# Rozpakowuje starter perimetru VPC-SC z template/ do docelowego repo, nadając plikom właściwe nazwy.
#
# DLACZEGO SZABLONY SĄ MARTWE: w template/ nie ma ANI JEDNEGO pliku-kropki, żadnego `.github/` i żadnego
# żywego `.tf`. Gdyby były, część z nich DZIAŁAŁABY tutaj: pre-commit tego repo puszcza `terraform_validate`
# na każdym `*.tf`, git czyta zagnieżdżone `.gitattributes`, mise `.tool-versions`. Sufiks `.example` +
# katalog `github/` (bez kropki) sprawiają, że to zwykły tekst — dopóki ten skrypt świadomie go nie
# rozpakuje gdzie indziej.
#
#   ./install.sh /sciezka/do/repo                 # kopiuje wszystko, nie nadpisuje istniejących
#   ./install.sh /sciezka/do/repo --force          # nadpisuje
#   ./install.sh /sciezka --dry-run                # tylko pokaż mapowanie
#   ./install.sh /sciezka --only validate.yml      # JEDEN plik — wdrożenie etapami (docs/1-wdrozenie.md)
#   ./install.sh /sciezka --zachowaj-przyklad      # NIE czyść członka przykładowego (używa tego selftest)
set -euo pipefail

DRY=0
FORCE=0
ONLY=""
TARGET=""
# Materiał przykładowy (członek + jego zgoda na egress) zostaje TYLKO dla selftestu startera — patrz
# blok „CZŁONEK PRZYKŁADOWY NIE JEDZIE DO WDROŻENIA" niżej. Wdrożenie nigdy nie używa tej flagi.
ZACHOWAJ_PRZYKLAD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --zachowaj-przyklad) ZACHOWAJ_PRZYKLAD=1 ;;
    --force)   FORCE=1 ;;
    --only)    shift; ONLY="${1:-}"; [ -n "$ONLY" ] || { echo "--only wymaga wzorca nazwy" >&2; exit 2; } ;;
    -*)        echo "nieznany argument: $1" >&2; exit 2 ;;
    *)         TARGET="$1" ;;
  esac
  shift
done

[ -n "$TARGET" ] || { echo "użycie: $0 <katalog-docelowy> [--force] [--dry-run] [--only WZORZEC]" >&2; exit 2; }
STARTER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$STARTER/template"
# DOKUMENTACJA JEDZIE RAZEM Z KODEM. Treść alertu produkcyjnego (`monitoring.tf`), komunikat `::error::`
# z bramki `validate` i nagłówki narzędzi odsyłają do `docs/3-runbook-…` i `docs/0-decyzje.md`. Gdyby
# `install.sh` kopiował sam `template/`, każdy z tych odsyłaczy wskazywałby w docelowym repo na pustkę —
# czyli alert o 3:00 kierowałby do procedury, której tam nie ma. Jedno źródło, zero kopii do zsynchronizowania.
DOCS="$STARTER/docs"
# AGENTS.md jedzie tą samą drogą: opisuje niezmienniki i placeholdery, więc jest potrzebny TAM, gdzie
# ktoś realnie zmienia konfigurację, a nie w katalogu, z którego się kopiuje.
AGENTS="$STARTER/AGENTS.md"
# `examples/` ŚWIADOMIE NIE JEST TU WYMIENIONE — i to nie jest przeoczenie.
#
# `examples/division-repo/` to materiał dla repozytorium DYWIZJI, czyli drugiej strony granicy. Docelowe
# repo tego skryptu jest repozytorium PERIMETRU. Skopiowanie tam przykładu dałoby dwa konkretne szkody,
# nie tylko bałagan: (a) `examples/division-repo/github/workflows/vpc-sc-request.yml` zmapowałby się na
# `.github/workflows/` i stałby się ŻYWYM workflowem, który wysyła `repository_dispatch` do repozytorium
# perimetru — czyli do samego siebie; (b) `vpc-sc/request.yaml` wyglądałby w repo perimetru na deklarację
# członka, którą ktoś zapomniał przenieść do `perimeter/members/`.
#
# Przykład zostaje więc w starterze i kopiuje go RĘCZNIE zespół dywizji, do SWOJEGO repozytorium —
# razem z dodaniem kropki do `github/`. Guard w selfteście pilnuje, że `examples/` nie ląduje w celu.
[ -d "$SRC" ] || { echo "brak katalogu template/ obok skryptu" >&2; exit 1; }
[ -d "$DOCS" ] || { echo "brak katalogu docs/ obok skryptu" >&2; exit 1; }
[ -f "$AGENTS" ] || { echo "brak AGENTS.md obok skryptu" >&2; exit 1; }
[ -d "$TARGET" ] || { echo "katalog docelowy nie istnieje: $TARGET" >&2; exit 1; }

# Mapowanie nazw: zdejmij `.example`; `github/` → `.github/`; plik na najwyższym poziomie dostaje kropkę
# (`tool-versions.example` → `.tool-versions`). Katalogi treści (perimeter/, terraform/, policy/, schemas/,
# tools/) zostają bez kropki — to normalne katalogi docelowego repo. Pliki z `docs/` startera lądują
# w `docs/` docelowego repo pod tą samą nazwą (nie mają sufiksu `.example` — to gotowa dokumentacja).
target_path() {
  local src="$1" rel
  case "$src" in
    "$DOCS"/*)  printf 'docs/%s' "${src#"$DOCS"/}"; return ;;
    "$AGENTS")  printf 'AGENTS.md'; return ;;
  esac
  rel="${src#"$SRC"/}"
  rel="${rel%.example}"
  case "$rel" in
    github/*) printf '.%s' "$rel" ;;
    */*)      printf '%s' "$rel" ;;
    *)        printf '.%s' "$rel" ;;
  esac
}

copied=0
skipped=0
matched=0
while IFS= read -r src; do
  # --only: wdrożenie etapami — jeden etap dokłada jedną bramkę, żeby przy czerwonym było wiadomo która.
  if [ -n "$ONLY" ] && [[ "$src" != *"$ONLY"* ]]; then continue; fi
  matched=$((matched + 1))
  dst="$TARGET/$(target_path "$src")"
  if [ -e "$dst" ] && [ "$FORCE" -eq 0 ]; then
    printf '  POMINIĘTE (istnieje): %s\n' "${dst#"$TARGET"/}"
    skipped=$((skipped + 1))
    continue
  fi
  printf '  %s  ->  %s\n' "${src#"$SRC"/}" "${dst#"$TARGET"/}"
  if [ "$DRY" -eq 0 ]; then
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    case "$dst" in *.sh|*/tools/*.py) chmod +x "$dst" ;; esac
  fi
  copied=$((copied + 1))
done < <(find "$SRC" "$DOCS" "$AGENTS" -type f | sort)

# Wzorzec, który do niczego nie pasuje, MUSI paść. Cichy sukces przy zerze skopiowanych plików to
# najgorszy wariant: myślisz, że etap wdrożony, a w repo nie ma nic.
if [ -n "$ONLY" ] && [ "$matched" -eq 0 ]; then
  echo "--only '$ONLY' nie pasuje do żadnego szablonu. Dostępne:" >&2
  find "$SRC" "$DOCS" "$AGENTS" -type f | sed -e "s|$SRC/|  |" -e "s|$STARTER/|  |" >&2
  exit 1
fi

if [ "$DRY" -eq 1 ]; then
  echo "-- dry-run: nic nie zapisano ($copied plików do skopiowania, $skipped pominiętych) --"
  exit 0
fi

echo "Skopiowano $copied plików (pominięto $skipped)."

# CZŁONEK PRZYKŁADOWY NIE JEDZIE DO WDROŻENIA — i to nie jest sprzątanie, tylko warunek wykonalności.
#
# `template/perimeter/projects.yaml.example` niesie ŻYWY wpis członka z `project_number: '000000000000'`,
# a `policy.yaml` — pokrywającą go zgodę w `egress_approvals`. Oba są tam CELOWO: bez nich selftest
# startera nie miałby na czym sprawdzić drogi zgody na egress (patrz komentarz nad `egress_approvals`).
# W REPOZYTORIUM PERIMETRU ta sama para jest jednak nie do przejścia w obie strony (zmierzone #2062,
# próba generalna, pierwsze realne rozpakowanie):
#   * zostawiona    → pierwszy `terraform apply` pada na API:
#       Invalid perimeter member: 'projects/000000000000'. Must be of the form 'projects/[1-9][0-9]{0,18}'
#   * sam wpis usunięty → bramka OPA `vpcsc.onboarding` odrzuca PR:
#       egress_approvals: zgoda wskazuje członka "example-division-prj-example-vertex-dev", którego nie ma
# Czyli świeżo rozpakowany starter nie dawał się ani zaapplikować, ani przepchnąć przez własne bramki,
# dopóki ktoś nie wyczyścił OBU miejsc naraz — a żaden krok procedury o tym nie mówił.
#
# Granica jest więc tutaj: przykład zostaje w STARTERZE (selftest ma swój materiał), a WDROŻENIE dostaje
# puste listy. Pierwszy członek wchodzi wnioskiem, przez bramki — czyli tak, jak ma wchodzić każdy.
if [ "$DRY" -eq 0 ] && [ -z "$ONLY" ] && [ "$ZACHOWAJ_PRZYKLAD" -eq 0 ]; then
  wyczyszczono=""
  if [ -f "$TARGET/perimeter/projects.yaml" ] && grep -q "project_number: '000000000000'" "$TARGET/perimeter/projects.yaml"; then
    printf 'schema_version: 1\n# Pierwszy członek wchodzi WNIOSKIEM (pull request), nie edycją tego pliku po rozpakowaniu.\n# Kształt wpisu: schemas/member.schema.json + docs/1-wdrozenie.md; przykład: starter, examples/.\nmembers: []\n' \
      > "$TARGET/perimeter/projects.yaml"
    wyczyszczono="$wyczyszczono perimeter/projects.yaml"
  fi
  if [ -f "$TARGET/perimeter/policy.yaml" ] && grep -q 'member: example-division-prj-example-vertex-dev' "$TARGET/perimeter/policy.yaml"; then
    python3 - "$TARGET/perimeter/policy.yaml" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
# Zgoda przykładowa idzie do komentarza (nie znika): jest jedynym w repo wzorcem wypełnionego wpisu,
# a bramka czyta wyłącznie treść aktywną. Kotwicą jest nagłówek sekcji, nie numer linii.
s = re.sub(r'^egress_approvals:\n(?:  [^\n]*\n|\n(?=  ))+',
           lambda m: 'egress_approvals: []\n# Wzorzec wypełnionej zgody (odkomentuj RAZEM z członkiem, którego dotyczy):\n'
                     + ''.join('#' + l + '\n' for l in m.group(0).splitlines()[1:]),
           s, count=1, flags=re.M)
open(p, 'w', encoding='utf-8').write(s)
PY
    wyczyszczono="$wyczyszczono perimeter/policy.yaml"
  fi
  [ -z "$wyczyszczono" ] || echo "Wyczyszczono materiał przykładowy (członek + jego zgoda na egress):$wyczyszczono"
fi
cat <<'NEXT'

Następne kroki w docelowym repo (kolejność ma znaczenie — patrz docs/1-wdrozenie.md):
  1. Podmień PLACEHOLDERY — pełna lista w docs/1-wdrozenie.md. Minimum, bez którego nic nie ruszy:
       perimeter/policy.yaml       org_id, access_policy_name, contract.bucket, contract.state_bucket,
                                   monitoring.project_id, konta w baseline_ingress, control_plane_projects
                                   (WYMAGANA sekcja: projekt administracyjny i NUMER projektu bucketa stanu)
       perimeter/policy.yaml       perimeter.name/title — to NIE jest placeholder, tylko przykład `ai_core`,
                                   a nazwa jest NIEZMIENNA po utworzeniu granicy. Podmień świadomie.
       terraform/versions.tf       bucket stanu   ORAZ  iam-bootstrap/versions.tf  (ten sam bucket,
                                   ROZŁĄCZNE prefiksy — inaczej pipeline pisze do stanu swoich uprawnień)
       .github/CODEOWNERS          @your-org/* → realne zespoły. DWA ROZŁĄCZNE zestawy: właściciel
                                   perimeter/policy.yaml musi mieć kogoś spoza właścicieli
                                   perimeter/projects.yaml (zgoda na egress ≠ wniosek; bramka to sprawdza)
     Zmienne repozytorium (WIF_PROVIDER, *_SERVICE_ACCOUNT, ORG_ID, MONITORING_PROJECT…) NIE są w plikach —
     ustawia je tools/bootstrap_github.sh i to on wypisuje, których brakuje.
  2. terraform -chdir=terraform init && terraform -chdir=terraform validate
  3. pre-commit install && pre-commit run --all-files
  4. Ustaw ochronę gałęzi + environment `perimeter-apply`: polityka gałęzi ograniczona do gałęzi domyślnej
     (działa na każdym planie) ORAZ required reviewers (funkcja płatna). Potem ODCZYTAJ oba z API — samo
     wysłanie ustawienia niczego nie dowodzi (`tools/bootstrap_github.sh` robi jedno i drugie).
  5. Perimetr powstaje PUSTY i w dry-run. Dopiero po pierwszym czystym oknie obserwacji promujesz członka
     do enforced — nigdy odwrotnie (docs/3-runbook-promocja-i-break-glass.md).
NEXT
