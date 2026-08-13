#!/usr/bin/env bash
# Uruchamia dwa apply RÓWNOLEGLE na dwóch niezależnych stanach i klasyfikuje, CO się właściwie stało.
#
# Równoległość jest istotą eksperymentu: przy wykonaniu sekwencyjnym (A kończy, B czyta świeży stan) obie
# reguły przetrwają ZAWSZE — i taki przebieg nie mówi nic o bezpieczeństwie modelu. Dlatego wykonanie
# sekwencyjne jest tu osobnym trybem (`SEKWENCYJNIE=1`) i pełni rolę KONTROLI ANTY-TAUTOLOGICZNEJ: jeśli
# scenariusz nie daje kompletu reguł nawet bez współbieżności, to zepsuty jest eksperyment, a nie API.
#
# NAJWAŻNIEJSZE W TYM SKRYPCIE — werdykt czytamy z TREŚCI komunikatu API i ze STANU KOŃCOWEGO perimetru,
# nigdy z kodu wyjścia ani z obecności słowa w całym logu. Ten eksperyment potknął się o to DWA RAZY,
# za każdym razem potwierdzając tezę, którą miał sprawdzać:
#
#   1. (#1904) tożsamości były wpisane na sztywno na fikcyjne konta. ACM odrzuca nieistniejące konta, więc
#      OBA applye padały na walidacji, w API nie było żadnej reguły, a werdykt — liczący wyłącznie „czy są
#      dwie reguły" — brzmiał „reguły giną". Naprawa: `IDENTITY_A`/`IDENTITY_B` jako parametry.
#   2. (#1949) naprawiona wersja rozpoznawała konflikt eTagu przez `grep -i etag` po CAŁYM logu apply.
#      Plan Terraforma drukuje atrybut wyliczany `+ etag = (known after apply)` — więc wzorzec pasował
#      ZAWSZE, przy każdej awarii z dowolnego powodu. Kategoria „nierozstrzygnięte", dodana w #1904 właśnie
#      po to, żeby awaria środowiska nie udawała pomiaru, była NIEOSIĄGALNA. Pierwszy przebieg na żywo padł
#      na `403 SERVICE_DISABLED` (ADC bez quota project) i został zaraportowany jako „konflikt eTag 1/1"
#      przy ZERZE reguł w API. Naprawa: wzorzec biegnie po WYCIĄGNIĘTYM komunikacie API, nie po logu.
#
# Morał obu potknięć jest ten sam: narzędzie zbudowane z wyobrażenia o zachowaniu systemu potwierdza
# wyobrażenie, nie system. Każdy werdykt tego skryptu ma być odtwarzalny z `perimeters describe`.
set -euo pipefail

: "${TF_VAR_policy_id:?ustaw TF_VAR_policy_id (gcloud access-context-manager policies list --organization=<ORG>)}"
: "${TF_VAR_perimeter_name:?ustaw TF_VAR_perimeter_name — użyj perimetru TESTOWEGO}"
# Dwa RÓŻNE, ISTNIEJĄCE konta serwisowe. ACM waliduje istnienie tożsamości i odrzuca całą zmianę
# (`invalid or non-existent`) — konto zmyślone zamienia eksperyment o współbieżności w test walidacji.
: "${IDENTITY_A:?ustaw IDENTITY_A na ISTNIEJĄCE konto, np. serviceAccount:sa-a@prj.iam.gserviceaccount.com}"
: "${IDENTITY_B:?ustaw IDENTITY_B na ISTNIEJĄCE konto (inne niż IDENTITY_A)}"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runs="${1:-1}"
sekwencyjnie="${SEKWENCYJNIE:-0}"   # 1 = kontrola anty-tautologiczna: A kończy, DOPIERO POTEM rusza B

# Szablony są martwe (.example) — rozpakowujemy je do katalogu roboczego.
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
for n in a b; do
  mkdir -p "$work/state-$n"
  cp "$here/state-$n/main.tf.example" "$work/state-$n/main.tf"
  terraform -chdir="$work/state-$n" init -input=false >/dev/null
done

cicha_utrata=0      # apply zgłosił sukces, a jego reguły NIE MA w API — jedyny wynik potwierdzający tezę
konflikt_glosny=0   # API odrzuciło przegranego komunikatem o eTagu — nic nie zniknęło niezauważenie
bez_nalozenia=0     # oba OK, obie reguły — przebieg nie trafił w okno wyścigu
nierozstrzygniete=0 # apply padł z INNEGO powodu — przebieg nic nie mierzy

# Wyciąga z logu apply KOMUNIKAT API (bez kolorów, bez planu). Werdykt czytamy stąd i tylko stąd:
# `403 PERMISSION_DENIED`, `409 ABORTED` i konflikt eTagu mają w Terraformie ten sam kod wyjścia.
#
# Dwa wzorce, bo nie każdy błąd ACM ma kod HTTP w treści: `existing object was already found` (kolizja
# TYTUŁU reguły po sierocie z przerwanego apply) i `Provider produced inconsistent result after apply`
# przychodzą BEZ `Error NNN:`. Bez drugiego wzorca taki przebieg pokazywał pusty komunikat i wyglądał
# na awarię bez przyczyny.
#
# `|| true` na końcu: przebieg UDANY nie ma komunikatu błędu, więc `grep` nie trafia i pod `set -o pipefail`
# zwraca 1 — bez tego `set -e` ubijał skrypt na pierwszym ZIELONYM apply.
tresc_bledu() {
  local czysty
  czysty="$(sed -e 's/\x1b\[[0-9;]*m//g' -e 's/^[[:space:]]*│[[:space:]]*//' "$1")"
  grep -oE 'Error [0-9]{3}: .*' <<<"$czysty" | head -1 && return 0
  grep -E '^Error: ' <<<"$czysty" | head -1 || true
}

# Czy TEN komunikat to konflikt optymistycznej kontroli współbieżności? Świadomie wąsko: samo słowo
# „etag" nie wystarcza (patrz nagłówek), a `403` bywa mylone z `409` na poziomie kodu wyjścia.
czy_konflikt_etagu() {
  grep -qiE "etag provided.*does not match|Error 409|\bABORTED\b|\bFAILED_PRECONDITION\b" <<<"$1"
}

# ŹRÓDŁEM PRAWDY jest API, nie state — state każdego z nich twierdzi, że jego reguła istnieje.
# Nieudany ODCZYT musi dać sentinel `?`, nie pustkę: pustka jest nieodróżnialna od „reguły zniknęły"
# i zamieniłaby awarię sieci w dowód cichej utraty.
tytuly_w_api() {
  local json
  json="$(gcloud access-context-manager perimeters describe "$TF_VAR_perimeter_name" \
    --policy="$TF_VAR_policy_id" --format=json 2>/dev/null)" || { echo "?"; return 0; }
  python3 -c "
import json,sys
d=json.load(sys.stdin)
rules=d.get('spec',{}).get('ingressPolicies',[]) or []
print(' '.join(sorted(str(r.get('title','')) for r in rules if str(r.get('title','')).startswith('race-test-'))))" \
    <<<"$json" || echo "?"
}

# Sierota = reguła `race-test-*` została w API, a stanu Terraforma po niej nie ma (apply przerwany, `destroy`
# nieudany, poprzedni przebieg zabity). ACM pilnuje unikalności TYTUŁU, więc taka pozostałość BLOKUJE każde
# ponowienie komunikatem `existing object was already found`, a `terraform import` dla tych zasobów NIE
# ISTNIEJE. Bez tego kroku drugi i każdy następny przebieg mierzy własny brud, nie API.
# Kasujemy WYŁĄCZNIE `race-test-*` — `--clear-ingress-policies` zdjęłoby też cudze reguły z perimetru.
sprzataj_sieroty() {
  local obecne; obecne="$(tytuly_w_api)"
  [ -n "$obecne" ] && [ "$obecne" != "?" ] || return 0
  echo "   SPRZĄTANIE sierot z poprzedniego przebiegu: [$obecne]"
  # JSON, nie YAML: gcloud czyta ten plik parserem YAML, a JSON jest podzbiorem YAML-a — dzięki temu
  # eksperyment nie wymaga PyYAML-a, którego w świeżym środowisku zwykle nie ma.
  local yaml="$work/pozostale.yaml"
  gcloud access-context-manager perimeters describe "$TF_VAR_perimeter_name" \
    --policy="$TF_VAR_policy_id" --format=json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
rules=d.get('spec',{}).get('ingressPolicies',[]) or []
json.dump([r for r in rules if not str(r.get('title','')).startswith('race-test-')], sys.stdout)" >"$yaml"
  gcloud access-context-manager perimeters dry-run update "$TF_VAR_perimeter_name" \
    --policy="$TF_VAR_policy_id" --set-ingress-policies="$yaml" >/dev/null 2>&1 \
    || echo "   UWAGA: nie udało się usunąć sierot — kolejny przebieg padnie na kolizji tytułu"
}

for i in $(seq 1 "$runs"); do
  sprzataj_sieroty
  if [ "$sekwencyjnie" = "1" ]; then
    echo "== przebieg $i/$runs (KONTROLA: sekwencyjnie) =="
    rc_a=0; rc_b=0
    terraform -chdir="$work/state-a" apply -auto-approve -input=false -var "identity=$IDENTITY_A" \
      >"$work/a.log" 2>&1 || rc_a=$?
    terraform -chdir="$work/state-b" apply -auto-approve -input=false -var "identity=$IDENTITY_B" \
      >"$work/b.log" 2>&1 || rc_b=$?
  else
    echo "== przebieg $i/$runs (równolegle) =="
    # OBA W TŁE, bez żadnej synchronizacji — to jest cały punkt.
    terraform -chdir="$work/state-a" apply -auto-approve -input=false -var "identity=$IDENTITY_A" \
      >"$work/a.log" 2>&1 &
    pid_a=$!
    terraform -chdir="$work/state-b" apply -auto-approve -input=false -var "identity=$IDENTITY_B" \
      >"$work/b.log" 2>&1 &
    pid_b=$!
    rc_a=0; rc_b=0
    wait $pid_a || rc_a=$?
    wait $pid_b || rc_b=$?
  fi

  blad_a="$(tresc_bledu "$work/a.log")"; blad_b="$(tresc_bledu "$work/b.log")"
  echo "   apply A rc=$rc_a ${blad_a:+| ${blad_a:0:110}}"
  echo "   apply B rc=$rc_b ${blad_b:+| ${blad_b:0:110}}"

  w_api="$(tytuly_w_api)"
  echo "   reguły race-test-* w API: [${w_api:-}]"

  if [ "$w_api" = "?" ]; then
    # Bez odczytu stanu końcowego nie ma czego klasyfikować — patrz komentarz przy `tytuly_w_api`.
    echo "   WYNIK: NIEROZSTRZYGNIĘTE — nie udało się odczytać perimetru z API"
    nierozstrzygniete=$((nierozstrzygniete + 1))
    terraform -chdir="$work/state-a" destroy -auto-approve -input=false -var "identity=$IDENTITY_A" >/dev/null 2>&1 || true
    terraform -chdir="$work/state-b" destroy -auto-approve -input=false -var "identity=$IDENTITY_B" >/dev/null 2>&1 || true
    continue
  fi

  # KROK 1 — cicha utrata. Sprawdzana ZAWSZE i NIEZALEŻNIE od drugiej strony: „apply zgłosił sukces,
  # a jego reguły nie ma" jest dowodem nadpisania nawet wtedy, gdy druga strona padła. Poprzednia wersja
  # wymagała rc=0 po OBU stronach i przez to nie widziała najczęstszego kształtu nadpisania.
  #
  # `|| true` jest tu KONIECZNE: pod `set -e` łańcuch `[ ] && [[ ]] && przypisanie` kończy się kodem 1,
  # gdy reguła JEST obecna (czyli w przebiegu poprawnym) — i ubijał skrypt na pierwszej zdanej kontroli.
  brakuje=""
  { [ "$rc_a" -eq 0 ] && [[ " $w_api " != *" race-test-alpha "* ]] && brakuje="$brakuje race-test-alpha"; } || true
  { [ "$rc_b" -eq 0 ] && [[ " $w_api " != *" race-test-beta "* ]] && brakuje="$brakuje race-test-beta"; } || true

  if [ -n "$brakuje" ]; then
    echo "   WYNIK: CICHA UTRATA — apply zgłosił sukces, a w API NIE MA:$brakuje"
    cicha_utrata=$((cicha_utrata + 1))
  elif [ "$rc_a" -eq 0 ] && [ "$rc_b" -eq 0 ]; then
    echo "   WYNIK: bez nałożenia w czasie — oba apply OK, obie reguły obecne"
    bez_nalozenia=$((bez_nalozenia + 1))
  elif { [ "$rc_a" -ne 0 ] && czy_konflikt_etagu "$blad_a"; } || { [ "$rc_b" -ne 0 ] && czy_konflikt_etagu "$blad_b"; }; then
    echo "   WYNIK: konflikt GŁOŚNY — API odrzuciło przegranego na eTagu, zwycięzca zapisał swoją regułę"
    konflikt_glosny=$((konflikt_glosny + 1))
  else
    echo "   WYNIK: NIEROZSTRZYGNIĘTE — apply padł z innego powodu; ten przebieg nic nie mierzy"
    nierozstrzygniete=$((nierozstrzygniete + 1))
  fi

  # Sprzątanie przed kolejnym przebiegiem — sekwencyjnie, żeby destroy sam nie był eksperymentem.
  terraform -chdir="$work/state-a" destroy -auto-approve -input=false -var "identity=$IDENTITY_A" >/dev/null 2>&1 || true
  terraform -chdir="$work/state-b" destroy -auto-approve -input=false -var "identity=$IDENTITY_B" >/dev/null 2>&1 || true
done

echo
echo "PODSUMOWANIE z $runs przebiegów ($([ "$sekwencyjnie" = "1" ] && echo "KONTROLA sekwencyjna" || echo "równolegle")):"
echo "  cicha utrata reguły:    $cicha_utrata"
echo "  konflikt głośny (eTag): $konflikt_glosny"
echo "  bez nałożenia:          $bez_nalozenia"
echo "  nierozstrzygnięte:      $nierozstrzygniete"
echo

if [ "$nierozstrzygniete" -gt 0 ]; then
  echo "UWAGA: $nierozstrzygniete przebiegów padło z powodu niezwiązanego ze współbieżnością (uprawnienia?"
  echo "brak quota project w ADC? limit tempa? zły perimetr?). Napraw to i powtórz — inaczej ten przebieg"
  echo "NIE JEST pomiarem. Treść komunikatu API jest wypisana wyżej przy każdym przebiegu."
fi

if [ "$sekwencyjnie" = "1" ]; then
  if [ "$bez_nalozenia" -eq "$runs" ]; then
    echo "KONTROLA ZDANA: bez współbieżności scenariusz daje KOMPLET reguł w $runs/$runs przebiegach."
    echo "Cokolwiek zgubi się w trybie równoległym, zgubi to wyścig — nie błąd w tym scenariuszu."
    exit 0
  fi
  echo "KONTROLA NIEZDANA: scenariusz gubi reguły nawet BEZ współbieżności. Wynik równoległy nie ma"
  echo "wartości dowodowej, dopóki ta kontrola nie jest zielona."
  exit 1
fi

if [ "$cicha_utrata" -gt 0 ]; then
  echo "TEZA POTWIERDZONA: równoległe applye potrafią zgubić regułę BEZ BŁĘDU. Sam retry nie wystarczy —"
  echo "trzeba weryfikować stan po każdym apply. Model 'każde repo aplikuje' jest wykluczony."
  exit 1
fi

if [ "$konflikt_glosny" -gt 0 ]; then
  echo "NA TEJ ŚCIEŻCE cichej utraty nie ma: przegrany apply pada GŁOŚNO na eTagu. UWAGA — to zdanie"
  echo "dotyczy ZASOBU, którym mierzyłeś. Warianty `..._dry_run_*` są ForceNew (każda zmiana = skasuj"
  echo "i utwórz) i zachowują się tak. Warianty EGZEKWOWANE mają `Update` w schemacie, idą ścieżką"
  echo "read-modify-write i tam cicha utrata ZMIERZONA jest (5/9 przebiegów z dwoma zielonymi apply)."
  echo "Nie uogólniaj wyniku jednej ścieżki na drugą — patrz README, §Wynik z organizacji labu."
  exit 0
fi

echo "Żaden przebieg nie trafił w okno wyścigu. To NIE jest dowód bezpieczeństwa — powtórz: ./run.sh 10"
