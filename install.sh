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
set -euo pipefail

DRY=0
FORCE=0
ONLY=""
TARGET=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
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
cat <<'NEXT'

Następne kroki w docelowym repo (kolejność ma znaczenie — patrz docs/1-wdrozenie.md):
  1. Podmień PLACEHOLDERY: perimeter/policy.yaml (org_id, access_policy_name), .github/CODEOWNERS (@your-org/*),
     .github/workflows/*.yml (WIF_PROVIDER, TF_SA, BACKEND_BUCKET, SNOW_INSTANCE).
  2. terraform -chdir=terraform init && terraform -chdir=terraform validate
  3. pre-commit install && pre-commit run --all-files
  4. Ustaw ochronę gałęzi + environment `perimeter-apply`: polityka gałęzi ograniczona do gałęzi domyślnej
     (działa na każdym planie) ORAZ required reviewers (funkcja płatna). Potem ODCZYTAJ oba z API — samo
     wysłanie ustawienia niczego nie dowodzi (`tools/bootstrap_github.sh` robi jedno i drugie).
  5. Perimetr powstaje PUSTY i w dry-run. Dopiero po pierwszym czystym oknie obserwacji promujesz członka
     do enforced — nigdy odwrotnie (docs/3-runbook-promocja-i-break-glass.md).
NEXT
