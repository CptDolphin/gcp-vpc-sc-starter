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
# SKĄD WZIĄĆ OBA WEJŚCIA — jednym narzędziem i jednym tokenem, bez `gcloud` i bez konta w Google Cloud:
#
#   gh release download --repo ORG/gcp-vpc-sc --pattern gates.tar.gz --clobber && tar -xzf gates.tar.gz
#   gh release download contract --repo ORG/gcp-vpc-sc --pattern contract.json --clobber
#   ./validate-local.sh --member vpc-sc/prj-example-vertex-prod.yaml \
#       --gates ./gates --contract ./contract.json
#
# Kontrakt jest publikowany RÓWNIEŻ do bucketa (dla konsumentów maszynowych spoza GitHuba), z tego samego
# kroku apply co asset — więc obie kopie są tożsame i wybór drogi jest kwestią wygody, nie aktualności.
# Dla repozytorium dywizji droga przez release jest jedyną, która nie wymaga tożsamości w GCP.
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
[ -f "$CONTRACT" ] || { echo "brak kontraktu: $CONTRACT — pobierz: gh release download contract --repo <ORG>/<REPO> --pattern contract.json" >&2; exit 1; }

fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }
problem() { note "BŁĄD" "$1"; fail=$((fail + 1)); }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Deklaracja dywizji NIE JEST plikiem członka — jest od niego WĘŻSZA. Cztery pola (`stage`, `dry_run_since`,
# `review_by`, `change_ref`) wypełnia druga strona granicy: `stage` zawsze na `dry-run`, daty okna obserwacji
# z dnia przyjęcia wniosku, referencję zmiany ze zdarzenia, które ją przyniosło. Walidujemy więc KOPIĘ
# uzupełnioną dokładnie tak, jak uzupełni ją kanał wejściowy.
#
# DLACZEGO nie żądać tych pól od zespołu: musiałby wpisać u siebie wartości, których nie kontroluje —
# a wymyślone pola to dokładnie te, których nikt potem nie czyta. Przy `dry_run_since` jest gorzej niż
# nieporządek: data wsteczna od wnioskodawcy sprawia, że bramka promocji liczy okno obserwacji jako dawno
# minione, czyli kasuje pomiar, dla którego dwustopniowy onboarding istnieje.
#
# DLACZEGO to NIE jest poluzowanie schematu: plik członka po tamtej stronie nadal MUSI mieć komplet pól
# i nadal sprawdza go TA SAMA schema. Zmienia się wyłącznie to, KTO je wpisuje.
PELNY="$work/member.yaml"
python3 - "$MEMBER" "$PELNY" <<'UZUPELNIJ'
import datetime, os, sys, yaml

REVIEW_AFTER_DAYS = 180  # ta sama stała co w tools/render_member.py po stronie perimetru

deklaracja = yaml.safe_load(open(sys.argv[1])) or {}
dzis = datetime.date.today()
deklaracja["stage"] = "dry-run"  # nadpisujemy, nie setdefault: etap nigdy nie pochodzi od wnioskodawcy
deklaracja.setdefault("dry_run_since", dzis.isoformat())
deklaracja.setdefault("review_by", (dzis + datetime.timedelta(days=REVIEW_AFTER_DAYS)).isoformat())
deklaracja.setdefault("exceptions", [])

# `change_ref` W KSZTAŁCIE, jaki nada mu action — bo z tego pola reguła onboardingu wyciąga NAZWĘ
# REPOZYTORIUM i sprawdza, czy wolno mu wnioskować o ten projekt. Bez odtworzenia kształtu ta reguła
# nie miałaby czego ocenić i lokalna walidacja byłaby słabsza od tej po drugiej stronie.
#
# Poza CI zmiennej nie ma — i wtedy NIE zmyślamy referencji `pr:`. Zmyślona przepuszczałaby regułę
# „czy to repozytorium może" na podstawie repozytorium, którym tylko twierdzimy, że jesteśmy. Wariant
# `manual:` mówi wprost „pochodzenie nieznane", a rozstrzygnięcie zostawia pipeline'owi (i tak samo
# repo perimetru, które konfrontuje referencję z nadawcą dispatcha).
repo = os.environ.get("GITHUB_REPOSITORY", "")
if repo:
    deklaracja.setdefault("change_ref", f"pr:{repo}#0")
else:
    deklaracja.setdefault("change_ref", "manual:walidacja lokalna poza pipeline'em, pochodzenie nieznane")

yaml.safe_dump(deklaracja, open(sys.argv[2], "w"), sort_keys=False, allow_unicode=True)
UZUPELNIJ

echo "== schema =="
check-jsonschema --schemafile "$GATES/schemas/member.schema.json" "$PELNY" && note "OK" "struktura pliku"

echo "== zgodność z kontraktem =="
# Te trzy sprawdzenia dają zespołowi odpowiedź „czy to w ogóle ma sens" bez żadnego dostępu do perimetru.
python3 - "$PELNY" "$CONTRACT" <<'PY' || fail=$((fail + 1))
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
# Wejściem jest uzupełniona kopia: reguły oceniają członka, jakim on BĘDZIE po tamtej stronie granicy.
python3 - "$PELNY" "$CONTRACT" > "$work/declarations.json" <<'PY'
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
    # `members_list` obok mapy — po tamtej stronie granicy czyta ją bramka duplikatu, a osobna reguła
    # porównuje liczności obu. Bez tej linii lokalna walidacja padałaby na regule, której deklaracja
    # dywizji nie może naruszyć (jeden wpis nie bywa duplikatem sam ze sobą) — czyli zespół dostawałby
    # czerwone za cudzy plik. Z nią sprawdza DOKŁADNIE to samo wejście, które zobaczy monorepo.
    "members_list": [member],
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
