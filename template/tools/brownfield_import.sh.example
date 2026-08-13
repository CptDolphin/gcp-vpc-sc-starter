#!/usr/bin/env bash
# Przejęcie ISTNIEJĄCEGO perimetru pod zarządzanie Terraforma — z bramką, która nie pozwala tego zepsuć.
#
# DLACZEGO skryptem: procedura ma cztery kroki, z których jeden (kolejność) decyduje o tym, czy nadpiszemy
# cudzą konfigurację. Ręcznie łatwo zrobić import PRZED sprawdzeniem policy.yaml — a wtedy pierwszy apply
# wyrównuje żywy perimetr do treści repo, czyli wyłącza ochronę usług, których nie znaliśmy.
#
# Skrypt NIE APPLIKUJE. Kończy się na planie i na jednoznacznym komunikacie: pusty plan = można iść dalej,
# niepusty = zatrzymaj się i przeczytaj różnicę.
#
#   ./tools/brownfield_import.sh --policy-id 123456789 --perimeter ai_core
#   ./tools/brownfield_import.sh --policy-id 123456789 --perimeter ai_core --write-import
set -euo pipefail

POLICY_ID="" PERIMETER="" WRITE_IMPORT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --policy-id) shift; POLICY_ID="${1:-}" ;;
    --perimeter) shift; PERIMETER="${1:-}" ;;
    --write-import) WRITE_IMPORT=1 ;;
    *) echo "nieznany argument: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$POLICY_ID" ] && [ -n "$PERIMETER" ] || {
  echo "użycie: $0 --policy-id <numer> --perimeter <nazwa> [--write-import]" >&2; exit 2; }

step() { printf '\n== %s ==\n' "$1"; }

# --- 1. Czy policy.yaml opisuje rzeczywistość? ------------------------------------------------------
# To jest bramka. Jeśli tu są różnice, import jest przedwczesny — nie dlatego, że „lepiej sprawdzić",
# a dlatego, że apply po imporcie wyrówna chmurę do repo.
step "1/4 · porównanie policy.yaml z żywym perimetrem"

# NARZĘDZIE MUSI DAĆ SIĘ URUCHOMIĆ, ZANIM UWIERZYMY W JEGO WERDYKT.
# Do 2026-08-13 ten wrapper brał KAŻDY niezerowy kod wyjścia za „są różnice". Skutek zmierzony na żywo
# (A6): `perimeter_to_policy.py` NIE PARSOWAŁ SIĘ (SyntaxError — polski cudzysłów zamknięty znakiem
# ASCII), a operator dostawał wiarygodnie wyglądający komunikat „STOP — policy.yaml NIE opisuje
# rzeczywistości". Taka pomyłka nie kończy się nigdy: poprawiasz policy.yaml, uruchamiasz ponownie
# i dostajesz ten sam werdykt, bo werdykt nie pochodził z porównania.
if ! python3 -m py_compile tools/perimeter_to_policy.py 2>/tmp/a6_compile.err; then
  echo >&2
  echo "AWARIA — tools/perimeter_to_policy.py nie daje się skompilować. To NIE jest werdykt o policy.yaml." >&2
  cat /tmp/a6_compile.err >&2
  exit 3
fi

set +e
python3 tools/perimeter_to_policy.py --policy-id "$POLICY_ID" --perimeter "$PERIMETER" --diff
diff_rc=$?
set -e

# 2 = nie udało się porównać (gcloud padł, brak perimetru, brak uprawnienia). To awaria, nie różnica.
if [ "$diff_rc" -ge 2 ]; then
  echo >&2
  echo "AWARIA — nie udało się ODCZYTAĆ perimetru, więc nie wiadomo, czy policy.yaml go opisuje." >&2
  echo "Przeczytaj komunikat wyżej: 403 z braku uprawnienia, brak perimetru i odmowa VPC-SC wyglądają" >&2
  echo "tak samo w kodzie wyjścia, a wymagają trzech różnych reakcji." >&2
  exit 3
fi

if [ "$diff_rc" -ne 0 ]; then
  # Podpowiedź cytuje ARGUMENTY, z którymi skrypt został wywołany (stąd heredoc bez cudzysłowów).
  # Wcześniej stała tu nazwa perimetru z NASZEGO wdrożenia — na cudzej organizacji podpowiadała opis
  # niewłaściwego obiektu, czyli kierowała operatora dokładnie tam, gdzie nie chciał patrzeć.
  cat >&2 <<STOP

STOP — policy.yaml NIE opisuje rzeczywistości.

Nie importuj. Najpierw przenieś różnice DO PLIKU (kierunek: rzeczywistość → repo):

    python3 tools/perimeter_to_policy.py --policy-id $POLICY_ID --perimeter $PERIMETER > /tmp/live.yaml
    # przepisz restricted_services i perimeter.name z /tmp/live.yaml do perimeter/policy.yaml

Potem uruchom ten skrypt ponownie. Różnica, którą zignorujesz teraz, wróci jako apply zmieniający zakres
ochrony usług, o których nikt nie wiedział.
STOP
  exit 1
fi

# --- 2. Blok import (deklaratywny, widoczny w planie) -----------------------------------------------
# Bloki `import {}` (Terraform >= 1.5) są lepsze od `terraform import` z CLI, bo widać je w PLANIE —
# reviewer zobaczy „import + 0 changes" zamiast musieć wierzyć, że ktoś uruchomił właściwą komendę.
step "2/4 · blok import"
IMPORT_FILE="terraform/zz_import_generated.tf"
IMPORT_BODY=$(cat <<EOF
# WYGENEROWANY przez tools/brownfield_import.sh — plik JEDNORAZOWY.
#
# Po udanym apply Terraform ma perimetr w stanie i ten plik jest już zbędny: USUŃ GO w tym samym PR-ze,
# którym przełączasz manage_skeleton na true. Zostawiony blok import nie szkodzi (jest idempotentny), ale
# sugeruje następnej osobie, że import wciąż jest do zrobienia.
import {
  to = google_access_context_manager_service_perimeter.this[0]
  id = "accessPolicies/$POLICY_ID/servicePerimeters/$PERIMETER"
}
EOF
)
if [ "$WRITE_IMPORT" -eq 1 ]; then
  printf '%s\n' "$IMPORT_BODY" > "$IMPORT_FILE"
  echo "  zapisano $IMPORT_FILE"
else
  echo "  (dry-run — plik NIE został zapisany; dodaj --write-import)"
  printf '%s\n' "$IMPORT_BODY" | sed 's/^/  | /'
  echo
  echo "  Pamiętaj też o przełączeniu perimeter.manage_skeleton na true w perimeter/policy.yaml —"
  echo "  bez tego zasób ma count = 0 i import nie ma czego zaimportować."
  exit 0
fi

# --- 3. Plan --------------------------------------------------------------------------------------
step "3/4 · terraform plan (nic nie jest applikowane)"
terraform -chdir=terraform init -input=false >/dev/null
set +e
terraform -chdir=terraform plan -input=false -detailed-exitcode -no-color -out=/tmp/brownfield.tfplan
code=$?
set -e

# --- 4. Interpretacja ------------------------------------------------------------------------------
step "4/4 · wynik"
case "$code" in
  0)
    cat <<'OK'
  PUSTY PLAN — dokładnie ten wynik chcesz zobaczyć.

  policy.yaml opisuje rzeczywistość, a import wprowadzi perimetr do stanu bez żadnej zmiany w chmurze.
  Możesz applikować:

      terraform -chdir=terraform apply /tmp/brownfield.tfplan

  Po apply: usuń terraform/zz_import_generated.tf w tym samym PR-ze.
OK
    ;;
  2)
    cat >&2 <<'DIFF'
  PLAN NIE JEST PUSTY — nie applikuj.

  Import sam z siebie nie zmienia chmury, ale apply z tym planem TAK. Każda pozycja w planie to zmiana,
  której nikt nie zamawiał — najczęściej lista `restricted_services` albo `vpc_accessible_services`
  wyrównywana do treści repo.

  Przeczytaj plan pozycja po pozycji i przenieś brakujące wartości DO policy.yaml, aż plan będzie pusty.
  „Zaakceptuję tę jedną zmianę" jest tu równoznaczne z „zmienię zakres ochrony produkcji bez ticketu".
DIFF
    exit 2
    ;;
  *)
    echo "  plan zakończył się błędem (kod $code) — to nie jest różnica, to awaria. Przeczytaj output wyżej." >&2
    exit 1
    ;;
esac
