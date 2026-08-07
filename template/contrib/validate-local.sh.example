#!/usr/bin/env bash
# Waliduje deklarację członka W REPOZYTORIUM ZESPOŁU, zanim cokolwiek zostanie wysłane.
#
# DLACZEGO lokalnie, skoro monorepo i tak sprawdzi to jeszcze raz: błąd znaleziony u siebie kosztuje minutę,
# a ten sam błąd w cudzym repozytorium kosztuje rundę komunikacji między zespołami.
#
# DLACZEGO na paczce bramek + kontrakcie, a nie na submodule: submodule dałby zespołowi CAŁE repozytorium
# perimetru — razem z members/ wszystkich dywizji i waszymi zakresami IP z access-levels/. Do zwalidowania
# jednego swojego pliku potrzebuje tylko REGUŁ (schemas + policy, z paczki) i LISTY DOSTĘPNYCH OPCJI
# (profile, access levels — z kontraktu). Ani jedno, ani drugie nie mówi mu, kto jest w perimetrze.
#
#   ./validate-local.sh --member vpc-sc/prj-example-vertex-prod.yaml \
#       --gates ./gates --contract ./contract.json
set -euo pipefail

MEMBER="" GATES="./gates" CONTRACT="./contract.json"
while [ $# -gt 0 ]; do
  case "$1" in
    --member) shift; MEMBER="${1:-}" ;;
    --gates) shift; GATES="${1:-}" ;;
    --contract) shift; CONTRACT="${1:-}" ;;
    *) echo "nieznany argument: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$MEMBER" ] || { echo "użycie: $0 --member <plik.yaml> [--gates <kat>] [--contract <plik>]" >&2; exit 2; }
[ -f "$MEMBER" ] || { echo "nie ma pliku: $MEMBER" >&2; exit 1; }
[ -d "$GATES/schemas" ] || { echo "brak $GATES/schemas — pobierz paczkę bramek (release gates-*)" >&2; exit 1; }
[ -f "$CONTRACT" ] || { echo "brak kontraktu: $CONTRACT — pobierz z bucketa kontraktów" >&2; exit 1; }

fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }
problem() { note "BŁĄD" "$1"; fail=$((fail + 1)); }

echo "== schema =="
check-jsonschema --schemafile "$GATES/schemas/member.schema.json" "$MEMBER" && note "OK" "struktura pliku"

echo "== zgodność z kontraktem =="
# Te trzy sprawdzenia dają zespołowi odpowiedź „czy to w ogóle ma sens" bez żadnego dostępu do perimetru.
python3 - "$MEMBER" "$CONTRACT" <<'PY' || fail=$((fail + 1))
import json, sys, yaml

member = yaml.safe_load(open(sys.argv[1]))
contract = json.load(open(sys.argv[2]))
problems = []

profiles = {p["name"]: p for p in contract["profiles"]}
levels = set(contract["access_levels"])

for entry in member.get("profiles", []):
    name = entry["name"]
    profile = profiles.get(name)
    if profile is None:
        problems.append(f"profil {name!r} nie istnieje w katalogu (dostępne: {', '.join(sorted(profiles))})")
        continue
    # Parametry: profil deklaruje, czego wymaga — brak wartości renderuje się na pustą listę tożsamości,
    # czyli regułę, która nikogo nie autoryzuje. Lepiej dowiedzieć się teraz niż po promocji.
    missing = [p for p in profile["parameters"] if p not in entry.get("params", {})]
    if missing:
        problems.append(f"profil {name!r} wymaga parametrów: {', '.join(missing)}")
    unknown = [k for k in entry.get("params", {}) if k not in profile["parameters"]]
    if unknown:
        problems.append(f"profil {name!r}: nieznane parametry (literówka?): {', '.join(unknown)}")
    # Access levels wskazywane przez członka muszą istnieć — nazwy bierzemy z kontraktu, nie zgadujemy.
    for key, values in entry.get("params", {}).items():
        if "access_level" in key:
            for v in values:
                if v not in levels:
                    problems.append(f"access level {v!r} nie istnieje (dostępne: {', '.join(sorted(levels))})")

# Czy ten projekt już jest w perimetrze? Kontrakt niesie trójkę dywizja/projekt/etap właśnie po to, żeby
# dało się to rozstrzygnąć TUTAJ. Bez tego zespół wysyła zgłoszenie, które repo perimetru i tak odrzuci
# (external-intake nie nadpisuje istniejącego wpisu) — a jeśli wpis jest już `enforced`, pytanie brzmi
# zupełnie inaczej: nie „jak dołączyć", tylko „co chcę zmienić w członku, który jest chroniony".
# Pusta lista jest dwuznaczna, więc czytamy flagę: przy `publish_members: false` tego sprawdzenia NIE MA,
# i trzeba to powiedzieć wprost zamiast zaliczać je jako zielone.
if contract.get("members_published", True):
    already = next((m for m in contract.get("members", []) if m["project_id"] == member["project_id"]), None)
    if already:
        problems.append(
            f"projekt {member['project_id']!r} jest już członkiem perimetru "
            f"(dywizja {already['division']}, stage: {already['stage']}) — to nie jest onboarding; "
            f"zmianę profili albo promocję zgłoś PR-em w repozytorium perimetru")
else:
    print("  UWAGA  kontrakt nie publikuje listy członków — nie sprawdzę, czy projekt już jest w perimetrze")

# Czy wolno mi wnioskować o ten projekt? Kopia informacyjna — decyzję podejmuje monorepo, ale odrzucenie
# tutaj oszczędza wysłania zgłoszenia, które i tak zostanie odrzucone.
repo = __import__("os").environ.get("GITHUB_REPOSITORY", "")
if repo:
    entry = next((c for c in contract.get("contributors", []) if c["repository"] == repo), None)
    if entry is None:
        problems.append(f"repozytorium {repo!r} nie ma wpisu w contributors — poproś sieć o dodanie")
    elif member["project_id"] not in entry["allowed_projects"]:
        problems.append(
            f"repozytorium {repo!r} nie ma projektu {member['project_id']!r} na liście dozwolonych "
            f"({', '.join(entry['allowed_projects'])})")
    elif entry["division"] != member["division"]:
        problems.append(f"repozytorium przypisane do dywizji {entry['division']!r}, a wpis deklaruje {member['division']!r}")

for p in problems:
    print(f"  BŁĄD   {p}")
sys.exit(1 if problems else 0)
PY
[ "$fail" -eq 0 ] && note "OK" "profile, parametry, access levels, uprawnienie do projektu i brak duplikatu członka"

echo "== reguły onboardingu (rego) =="
# Reguły potrzebują kontekstu (baseline, katalog profili, data), którego zespół nie ma. Budujemy minimalne
# wejście z kontraktu — to wystarcza dla reguł o kształcie i czasie, a nie wymaga dostępu do repo perimetru.
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
python3 - "$MEMBER" "$CONTRACT" > "$work/declarations.json" <<'PY'
import datetime, json, sys, yaml
member = yaml.safe_load(open(sys.argv[1]))
contract = json.load(open(sys.argv[2]))
name = f"{member['division']}-{member['project_id']}"
print(json.dumps({
    "policy": {
        "restricted_services": contract["restricted_services"],
        "onboarding": contract["onboarding"],
    },
    # Profile odtworzone z kontraktu: reguły sprawdzają nazwy i parametry, nie treść reguł.
    "profiles": {p["name"]: {"name": p["name"], "parameters": [{"name": x} for x in p["parameters"]]}
                 for p in contract["profiles"]},
    "members": {name: member},
    "contributors": contract.get("contributors", []),
    "today": datetime.date.today().isoformat(),
    # Zespół nie ma raportu naruszeń — a bez niego promocja do enforced i tak zostanie odrzucona.
    # To celowe: promocję robi monorepo, nie zgłoszenie z zewnątrz.
    "violations_last_window": {name: 0} if member.get("stage") == "dry-run" else {},
}))
PY
conftest test --policy "$GATES/policy" --namespace vpcsc.onboarding "$work/declarations.json"

if [ "$fail" -gt 0 ]; then
  echo
  echo "NIEZALICZONE ($fail błędów) — popraw plik przed wysłaniem zgłoszenia." >&2
  exit 1
fi

cat <<'DONE'

OK — deklaracja przejdzie bramki monorepo.

Sprawdzone jest to, co da się sprawdzić bez dostępu do perimetru. NIE sprawdzono:
  - pre-flightu sieciowego (Private Google Access, strefa DNS na restricted VIP) — robi to monorepo,
  - czy projekt nie należy już do INNEJ konfiguracji egzekwowanej (inny perimetr; to odczyt z żywego
    GCP — kontrakt odpowiada tylko za członkostwo w TYM perimetrze),
  - budżetu atrybutów po dodaniu twoich reguł (kontrakt pokazuje aktualne zużycie).
DONE
