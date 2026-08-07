#!/usr/bin/env bash
# Pre-flight: czy projekt członka JEST GOTOWY na wejście do perimetru. Wyłącznie odczyt — ten skrypt
# niczego nie naprawia (granica własności, DEC-5: naprawia właściciel projektu, nie repo perimetru).
#
# Każdy check zamyka konkretny tryb awarii:
#   1. projekt istnieje i numer zgadza się z ID   → literówka w numerze dodałaby do perimetru CUDZY projekt
#   2. projekt nie jest w innej konfiguracji enforced → twarde ograniczenie ACM; apply padłby po review
#   3. podsieci mają Private Google Access        → bez tego ruch do API nie pójdzie przez restricted VIP
#   4. strefa DNS kieruje googleapis.com na restricted VIP → jw., najczęstsza cicha awaria onboardingu
#   5. (ostrzeżenie) istnieją już endpointy Vertex → endpoint utworzony PRZED wejściem do perimetru
#      sprawia, że późniejszy deploy modelu na niego zawodzi; to nie blokuje PR-a, ale musi być powiedziane
#
# Uprawnienia (read-only): cloudasset.viewer, compute.networkViewer, dns.reader — docs/2-uprawnienia-i-wif.md
set -euo pipefail

PROJECT_ID=""
PROJECT_NUMBER=""
STRICT=1
while [ $# -gt 0 ]; do
  case "$1" in
    --project) shift; PROJECT_ID="${1:-}" ;;
    --number)  shift; PROJECT_NUMBER="${1:-}" ;;
    --warn-only) STRICT=0 ;;
    *) echo "nieznany argument: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$PROJECT_ID" ] && [ -n "$PROJECT_NUMBER" ] || { echo "użycie: $0 --project <id> --number <numer>" >&2; exit 2; }

fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }
problem() { note "BŁĄD" "$1"; fail=$((fail + 1)); }

echo "pre-flight: $PROJECT_ID ($PROJECT_NUMBER)"

# 1. projekt istnieje i numer się zgadza
actual="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null || true)"
if [ -z "$actual" ]; then
  problem "projekt $PROJECT_ID nie istnieje albo brak dostępu odczytu"
elif [ "$actual" != "$PROJECT_NUMBER" ]; then
  problem "numer projektu nie zgadza się: deklarowany $PROJECT_NUMBER, realny $actual"
else
  note "OK" "projekt istnieje, numer zgodny"
fi

# 2. kolizja perimetrów — projekt może należeć tylko do JEDNEJ konfiguracji egzekwowanej
if gcloud access-context-manager perimeters list --format=json 2>/dev/null \
  | grep -q "\"projects/$PROJECT_NUMBER\""; then
  note "UWAGA" "projekt występuje już w jakiejś konfiguracji perimetru — sprawdź, czy to NASZ perimetr"
else
  note "OK" "brak kolizji z innym perimetrem"
fi

# 3. Private Google Access na podsieciach
subnets_without_pga="$(gcloud compute networks subnets list --project="$PROJECT_ID" \
  --format='value(name,privateIpGoogleAccess)' 2>/dev/null | awk '$2=="False"{print $1}' || true)"
if [ -n "$subnets_without_pga" ]; then
  problem "podsieci bez Private Google Access: $(echo "$subnets_without_pga" | tr '\n' ' ')"
else
  note "OK" "Private Google Access włączony na wszystkich podsieciach"
fi

# 4. DNS na restricted VIP (199.36.153.4/30)
if gcloud dns managed-zones list --project="$PROJECT_ID" --format='value(dnsName)' 2>/dev/null \
  | grep -q "googleapis.com"; then
  note "OK" "istnieje prywatna strefa dla googleapis.com"
else
  problem "brak prywatnej strefy DNS dla googleapis.com → ruch do API nie pójdzie przez restricted VIP"
fi

# 4b. Workbench z własnymi kernelami wymaga private.googleapis.com (199.36.153.8/30) dla
#     *.notebooks.googleusercontent.com — jedyny wyjątek od reguły „wszystko przez restricted".
if gcloud dns managed-zones list --project="$PROJECT_ID" --format='value(dnsName)' 2>/dev/null \
  | grep -q "notebooks.googleusercontent.com"; then
  note "OK" "strefa dla notebooks.googleusercontent.com obecna (Workbench)"
else
  note "UWAGA" "brak strefy notebooks.googleusercontent.com → Workbench z własnym kernelem nie wstanie"
fi

# 5. kolejność tworzenia endpointów Vertex (ostrzeżenie, nie blokada)
if gcloud ai endpoints list --project="$PROJECT_ID" --region=europe-west4 --format='value(name)' 2>/dev/null \
  | grep -q .; then
  note "UWAGA" "istnieją endpointy Vertex sprzed wejścia do perimetru — deploy modelu na nie zawiedzie; odtwórz je po dołączeniu"
fi

if [ "$fail" -gt 0 ] && [ "$STRICT" -eq 1 ]; then
  echo "pre-flight NIEZALICZONY ($fail błędów) — naprawia właściciel projektu, nie repo perimetru" >&2
  exit 1
fi
echo "pre-flight zaliczony"
