#!/usr/bin/env bash
# Uruchamia dwa apply RÓWNOLEGLE na dwóch niezależnych stanach i sprawdza, ile reguł faktycznie przetrwało.
#
# Równoległość jest istotą eksperymentu: przy wykonaniu sekwencyjnym (A kończy, B czyta świeży stan) obie
# reguły przetrwają ZAWSZE — i taki przebieg nie mówi nic o bezpieczeństwie modelu.
set -euo pipefail

: "${TF_VAR_policy_id:?ustaw TF_VAR_policy_id (gcloud access-context-manager policies list --organization=<ORG>)}"
: "${TF_VAR_perimeter_name:?ustaw TF_VAR_perimeter_name — użyj perimetru TESTOWEGO}"

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

lost=0
for i in $(seq 1 "$runs"); do
  echo "== przebieg $i/$runs =="

  # OBA W TŁE, bez żadnej synchronizacji — to jest cały punkt.
  terraform -chdir="$work/state-a" apply -auto-approve -input=false >"$work/a.log" 2>&1 &
  pid_a=$!
  terraform -chdir="$work/state-b" apply -auto-approve -input=false >"$work/b.log" 2>&1 &
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
  echo "   reguł race-test-* w API: $found (oczekiwane 2)"
  [ "$found" != "2" ] && lost=$((lost + 1))

  # Sprzątanie przed kolejnym przebiegiem — sekwencyjnie, żeby destroy sam nie był eksperymentem.
  terraform -chdir="$work/state-a" destroy -auto-approve -input=false >/dev/null 2>&1 || true
  terraform -chdir="$work/state-b" destroy -auto-approve -input=false >/dev/null 2>&1 || true
done

echo
echo "WYNIK: $lost / $runs przebiegów NIE miało obu reguł."
if [ "$lost" -gt 0 ]; then
  echo "Równoległe applye na wspólnym perimetrze GUBIĄ reguły — model 'każde repo aplikuje' jest wykluczony."
  exit 1
fi
echo "W tym przebiegu nic nie zginęło. To NIE jest dowód bezpieczeństwa — powtórz: ./run.sh 10"
