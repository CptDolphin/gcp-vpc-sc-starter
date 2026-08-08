#!/usr/bin/env bash
# Uruchamia dwa apply RÓWNOLEGLE na dwóch niezależnych stanach i klasyfikuje, CO się właściwie stało.
#
# Równoległość jest istotą eksperymentu: przy wykonaniu sekwencyjnym (A kończy, B czyta świeży stan) obie
# reguły przetrwają ZAWSZE — i taki przebieg nie mówi nic o bezpieczeństwie modelu.
#
# NAJWAŻNIEJSZE W TYM SKRYPCIE — werdykt rozróżnia trzy wyniki, nie dwa. Poprzednia wersja liczyła wyłącznie
# „czy w API są dwie reguły" i każdy inny stan raportowała jako UTRATĘ. W połączeniu z fikcyjną tożsamością
# wpisaną na sztywno (ACM odrzuca nieistniejące konta) dawało to eksperyment, który ZAWSZE potwierdzał tezę:
# oba applye padały na walidacji, w API nie było żadnej reguły, werdykt brzmiał „reguły giną". Materiał
# zbudowany z wyobrażenia o zachowaniu systemu potwierdza wyobrażenie, nie system (Issue #1904).
set -euo pipefail

: "${TF_VAR_policy_id:?ustaw TF_VAR_policy_id (gcloud access-context-manager policies list --organization=<ORG>)}"
: "${TF_VAR_perimeter_name:?ustaw TF_VAR_perimeter_name — użyj perimetru TESTOWEGO}"
# Dwa RÓŻNE, ISTNIEJĄCE konta serwisowe. ACM waliduje istnienie tożsamości i odrzuca całą zmianę
# (`invalid or non-existent`) — konto zmyślone zamienia eksperyment o współbieżności w test walidacji.
: "${IDENTITY_A:?ustaw IDENTITY_A na ISTNIEJĄCE konto, np. serviceAccount:sa-a@prj.iam.gserviceaccount.com}"
: "${IDENTITY_B:?ustaw IDENTITY_B na ISTNIEJĄCE konto (inne niż IDENTITY_A)}"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runs="${1:-1}"

# Szablony są martwe (.example) — rozpakowujemy je do katalogu roboczego.
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
for n in a b; do
  mkdir -p "$work/state-$n"
  cp "$here/state-$n/main.tf.example" "$work/state-$n/main.tf"
  terraform -chdir="$work/state-$n" init -input=false >/dev/null
done

cicha_utrata=0     # oba applye OK, a reguły brakuje — JEDYNY wynik potwierdzający tezę o cichym nadpisaniu
konflikt_glosny=0  # apply padł na eTagu — API odrzuciło przegranego, nic nie zniknęło niezauważenie
bez_nalozenia=0    # oba OK, obie reguły — przebieg nie trafił w okno wyścigu
nierozstrzygniete=0 # apply padł z INNEGO powodu (np. brak uprawnień, zła tożsamość) — przebieg nic nie mierzy

for i in $(seq 1 "$runs"); do
  echo "== przebieg $i/$runs =="

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
  echo "   apply A rc=$rc_a, apply B rc=$rc_b"
  [ "$rc_a" -ne 0 ] && tail -3 "$work/a.log" | sed 's/^/     A: /'
  [ "$rc_b" -ne 0 ] && tail -3 "$work/b.log" | sed 's/^/     B: /'

  # ŹRÓDŁEM PRAWDY jest API, nie state — state każdego z nich twierdzi, że jego reguła istnieje.
  found=$(gcloud access-context-manager perimeters describe "$TF_VAR_perimeter_name" \
    --policy="$TF_VAR_policy_id" --format=json 2>/dev/null \
    | python3 -c "
import json,sys
d=json.load(sys.stdin)
rules=d.get('spec',{}).get('ingressPolicies',[]) or []
print(sum(1 for r in rules if str(r.get('title','')).startswith('race-test-')))" || echo "?")
  echo "   reguł race-test-* w API: $found"

  # Klasyfikacja. Kolejność ma znaczenie: „apply padł" sprawdzamy PRZED liczbą reguł, bo brak reguły po
  # nieudanym apply jest oczekiwany i nie dowodzi niczego o współbieżności.
  if [ "$rc_a" -eq 0 ] && [ "$rc_b" -eq 0 ]; then
    if [ "$found" = "2" ]; then
      echo "   WYNIK: bez nałożenia w czasie — oba apply OK, obie reguły obecne"
      bez_nalozenia=$((bez_nalozenia + 1))
    else
      echo "   WYNIK: CICHA UTRATA — oba apply zgłosiły sukces, a reguł jest $found"
      cicha_utrata=$((cicha_utrata + 1))
    fi
  elif grep -qi "etag" "$work/a.log" "$work/b.log"; then
    echo "   WYNIK: konflikt GŁOŚNY — przegrany apply padł na eTagu, zwycięzca zapisał swoją regułę"
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
echo "PODSUMOWANIE z $runs przebiegów:"
echo "  cicha utrata reguły:   $cicha_utrata"
echo "  konflikt głośny (eTag): $konflikt_glosny"
echo "  bez nałożenia:          $bez_nalozenia"
echo "  nierozstrzygnięte:      $nierozstrzygniete"
echo

if [ "$nierozstrzygniete" -gt 0 ]; then
  echo "UWAGA: $nierozstrzygniete przebiegów padło z powodu niezwiązanego ze współbieżnością (uprawnienia?"
  echo "nieistniejące konto? zły perimetr?). Napraw to i powtórz — inaczej ten przebieg NIE JEST pomiarem."
fi

if [ "$cicha_utrata" -gt 0 ]; then
  echo "TEZA POTWIERDZONA: równoległe applye potrafią zgubić regułę BEZ BŁĘDU. Sam retry nie wystarczy —"
  echo "trzeba weryfikować stan po każdym apply. Model 'każde repo aplikuje' jest wykluczony."
  exit 1
fi

if [ "$konflikt_glosny" -gt 0 ]; then
  echo "TEZA O CICHEJ UTRACIE OBALONA: ACM ma optymistyczną kontrolę współbieżności na eTagach — przegrany"
  echo "apply pada GŁOŚNO, nic nie znika niezauważenie. Single-flight zostaje słuszny, ale argumentem jest"
  echo "NIEZAWODNOŚĆ (co drugi merge losowo pada i wymaga ponowienia), nie utrata danych. Przy eTagu retry"
  echo "pomaga — przy cichej utracie by nie pomógł, i to jest praktyczna różnica."
  exit 0
fi

echo "Żaden przebieg nie trafił w okno wyścigu. To NIE jest dowód bezpieczeństwa — powtórz: ./run.sh 10"
