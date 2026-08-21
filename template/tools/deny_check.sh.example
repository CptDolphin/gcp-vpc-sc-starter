#!/usr/bin/env bash
# Czy guardrail perimetru — polityka IAM Deny z `iam-bootstrap/main.tf` §5b — ISTNIEJE.
#
# TRZY WERDYKTY, NIGDY DWA. To jest cały powód, dla którego ten plik istnieje, i jedyna rzecz, której
# nie robi surowe wywołanie API:
#
#   HTTP 200  ISTNIEJE     → skrypt wypisuje treść polityki. Wypisuje ją ZAWSZE, także przy „OK”, bo
#                            polityka bez `deniedPermissions` istnieje i nie zabrania niczego — a to
#                            wygląda w każdym raporcie „czy jest?” dokładnie tak samo jak działający zakaz.
#   HTTP 404  NIE MA       → to jest WYNIK, nie awaria narzędzia. Warstwa opisana w architekturze nigdy
#                            nie powstała albo została skasowana.
#   HTTP 403  NIE WIADOMO  → brak `iam.denypolicies.get`. Ten stan NIE JEST „nie ma” i nie wolno go tak
#                            zaraportować. `iam.denypolicies.*` nie należy do żadnej roli org-admina, więc
#                            jest to stan DOMYŚLNY dla kogoś, komu nikt nie nadał roli do odczytu —
#                            i najczęstsza przyczyna zdania „guardrail chyba stoi”.
#
# DLACZEGO KOD HTTP, A NIE `gcloud iam policies get`. gcloud oba nierozstrzygające przypadki pokazuje jako
# czerwony `ERROR:` z długim zdaniem; różnicę niesie słowo w środku komunikatu. Tu różnica między „nie ma”
# a „nie widzę” jest CAŁĄ treścią odpowiedzi, więc bierzemy ją z liczby, a nie z tekstu, który dostawca
# może przeredagować. Poświadczenia i tak pochodzą z gcloud — to nie jest osobny kanał uwierzytelniania.
#
# Kody wyjścia (rozłączne, do użycia w bramkach):
#   0 = istnieje    1 = NIE MA    2 = nie wiadomo (brak uprawnienia)    3 = błąd wywołania/API
#
# Uprawnienie: `iam.denypolicies.get` — w tym starterze rola własna `vpcScDenyReader`
# (`iam-bootstrap/main.tf` §5a). Predefiniowany zamiennik: `roles/iam.denyReviewer`.
#
# NAZWY OBIEKTÓW ORG-LEVEL SĄ WEJŚCIEM, NIE STAŁĄ — i to jest część werdyktu, nie kosmetyka. Rola odczytu
# i polityka deny są obiektami org-level, więc druga instancja toru w tej samej organizacji (próba
# generalna, pilot obok produkcji, DR) różnicuje je `org_resource_suffix`. Nazwa wpisana tu na sztywno
# zamienia się wtedy w dwie różne awarie: w podpowiedzi przy `403` — w polecenie nadania roli, KTÓREJ
# NIE MA (a czyta je ktoś, kto właśnie ustalił, że nie wie nic o guardrailu, więc nie ma czym tej
# podpowiedzi zweryfikować); w `--name` — w stabilne „NIE MA” na działającej polityce.
#
# Skrypt nie ma jak tych nazw ODCZYTAĆ bez poświadczeń, a przy `403` poświadczeń z definicji brakuje:
# w drzewie repozytorium nazwa roli nie stoi dosłownie ani razu (`main.tf` ma interpolację, `outputs.tf`
# wartość wyliczaną), a jedyne dosłowne źródło — state i API — wymaga dokładnie tego dostępu, którego
# nie ma. Dlatego obie nazwy są WEJŚCIEM z wartością kanoniczną jako domyślną, skrypt wypisuje TĘ,
# KTÓREJ UŻYŁ, i mówi wprost, kiedy tylko ją założył. Doklejanie sufiksu w tym pliku byłoby TRZECIĄ kopią
# schematu nazewniczego — dwie już są w `main.tf` i RÓŻNIĄ SIĘ separatorem (`role_id` nie dopuszcza
# myślnika, nazwa polityki deny nie dopuszcza wielkich liter).
set -euo pipefail

export CLOUDSDK_CORE_DISABLE_PROMPTS=1

ORG_ID=""
# Wartości KANONICZNE, czyli te z `org_resource_suffix` pustym. `ROLA_Z_WEJSCIA` niesie coś innego niż
# sama nazwa: czy skrypt tę nazwę DOSTAŁ, czy tylko założył — bo wypisać ją jako nazwę TEGO wdrożenia
# wolno mu wyłącznie w pierwszym wypadku.
NAZWA="vpcsc-ci-no-destroy"
ROLA="vpcScDenyReader"
ROLA_Z_WEJSCIA=0

uzycie() {
  cat >&2 <<'POMOC'
użycie: deny_check.sh --org <ORG_ID> [--name <nazwa-polityki>] [--reader-role <role_id>]

  --org          numer organizacji Google Cloud (attachment point polityki deny)
  --name         nazwa polityki; domyślnie `vpcsc-ci-no-destroy` — musi zgadzać się z
                 `local.deny_policy_name` w iam-bootstrap/main.tf, inaczej dostaniesz stabilne
                 „NIE MA” na działającym guardrailu
  --reader-role  `role_id` roli odczytu warstwy deny; domyślnie `vpcScDenyReader`. Wchodzi WYŁĄCZNIE
                 do podpowiedzi przy `403` — niczego nie sprawdza i niczego nie nadaje

OBIE te nazwy są org-level i OBIE zmienia `org_resource_suffix` (druga instancja toru w tej samej
organizacji), a każdą INNYM schematem: `role_id` bez separatora, nazwa polityki z myślnikiem. Dlatego
ten skrypt żadnej z nich nie SKŁADA — bierze je z wejścia i wypisuje dokładnie to, czego użył.
Nazwę tego wdrożenia dają: `iam-bootstrap/main.tf` §5a (`role_id`) i §5b (`local.deny_policy_name`)
albo — po apply — output `deny_reader_role_id`.
POMOC
  exit 3
}

while [ $# -gt 0 ]; do
  case "$1" in
    --org)  shift; ORG_ID="${1:-}" ;;
    --name) shift; NAZWA="${1:-}" ;;
    --reader-role) shift; ROLA="${1:-}"; ROLA_Z_WEJSCIA=1 ;;
    -h|--help) uzycie ;;
    *) echo "nieznany argument: $1" >&2; uzycie ;;
  esac
  shift
done

[ -n "$ORG_ID" ] || uzycie
case "$ORG_ID" in *[!0-9]*) echo "--org przyjmuje NUMER organizacji, nie nazwę domeny: $ORG_ID" >&2; exit 3 ;; esac

# Pusta wartość nie jest „domyślną”: `--name ""` pyta o INNY zasób, a jego `404` nie jest werdyktem
# o polityce; `--reader-role ""` daje podpowiedź o roli bez identyfikatora. Oba wyglądają jak wynik.
[ -n "$NAZWA" ] || { echo "--name nie przyjmuje pustej wartości" >&2; exit 3; }
[ -n "$ROLA" ]  || { echo "--reader-role nie przyjmuje pustej wartości" >&2; exit 3; }
# `--reader-role` to sam `role_id`. Pełna ścieżka sklejałaby się w podpowiedzi z prefiksem w drugą kopię.
case "$ROLA" in */*) echo "--reader-role przyjmuje sam role_id (np. vpcScDenyReader), nie ścieżkę: $ROLA" >&2; exit 3 ;; esac

TOKEN="$(gcloud auth print-access-token)" || { echo "brak poświadczeń gcloud (gcloud auth login)" >&2; exit 3; }

# Attachment point jedzie w ścieżce URL zakodowany (%2F), tak samo jak w `parent` zasobu Terraforma.
PUNKT="cloudresourcemanager.googleapis.com%2Forganizations%2F${ORG_ID}"
ODP="$(mktemp)"
trap 'rm -f "$ODP"' EXIT

KOD="$(curl -sS -o "$ODP" -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://iam.googleapis.com/v2/policies/${PUNKT}/denypolicies/${NAZWA}")"

case "$KOD" in
  200)
    echo "ISTNIEJE: polityka deny '${NAZWA}' na organizacji ${ORG_ID}."
    echo "Przeczytaj reguły — polityka bez deniedPermissions istnieje i nie zabrania NICZEGO:"
    cat "$ODP"
    exit 0
    ;;
  404)
    echo "NIE MA: polityka deny '${NAZWA}' nie istnieje na organizacji ${ORG_ID}."
    echo "To jest odczytany stan faktyczny, nie brak dostępu — guardrail nie chroni dziś niczego."
    echo "WARUNEK TEGO WERDYKTU: '${NAZWA}' to nazwa polityki Z TEGO wdrożenia. Niepusty org_resource_suffix"
    echo "ją zmienia (patrz --name w pomocy) — a wtedy to samo zdanie dostaniesz na DZIAŁAJĄCYM guardrailu."
    echo "Utworzenie wymaga roles/iam.denyAdmin (jedyna rola z iam.denypolicies.create; roli własnej z tym"
    echo "uprawnieniem zbudować się NIE DA) i apply w iam-bootstrap/ z manage_deny_policy = true."
    exit 1
    ;;
  403)
    echo "NIE WIADOMO: brak uprawnienia iam.denypolicies.get na organizacji ${ORG_ID}." >&2
    echo "TO NIE ZNACZY, ŻE POLITYKI NIE MA — API zwraca 403 także wtedy, gdy istnieje." >&2
    echo "Nadaj rolę odczytu i powtórz:" >&2
    echo "  gcloud organizations add-iam-policy-binding ${ORG_ID} \\" >&2
    echo "    --member='user:TWOJ_ADRES' --role='organizations/${ORG_ID}/roles/${ROLA}'" >&2
    if [ "$ROLA_Z_WEJSCIA" -eq 0 ]; then
      # Nazwa nie została odczytana, tylko założona — i milczenie o tym jest gorsze niż brak podpowiedzi:
      # nadanie nieistniejącej roli kończy się `INVALID_ARGUMENT`, a pierwsza hipoteza brzmi wtedy
      # „mam za mało uprawnień”, nie „skrypt podał złą nazwę”.
      echo "UWAGA: to nazwa KANONICZNA — skrypt jej nie odczytał, tylko przyjął domyślną." >&2
      echo "Wdrożenie z niepustym org_resource_suffix ma tę rolę Z SUFIKSEM; jej nazwę daje" >&2
      echo "iam-bootstrap/main.tf §5a (role_id) albo output deny_reader_role_id — podaj ją --reader-role." >&2
    fi
    exit 2
    ;;
  *)
    echo "BŁĄD: nieoczekiwana odpowiedź API (HTTP ${KOD})." >&2
    cat "$ODP" >&2
    exit 3
    ;;
esac
