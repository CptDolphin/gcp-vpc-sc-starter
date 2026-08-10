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
set -euo pipefail

export CLOUDSDK_CORE_DISABLE_PROMPTS=1

ORG_ID=""
NAZWA="vpcsc-ci-no-destroy"

uzycie() {
  cat >&2 <<'POMOC'
użycie: deny_check.sh --org <ORG_ID> [--name <nazwa-polityki>]

  --org   numer organizacji Google Cloud (attachment point polityki deny)
  --name  nazwa polityki; domyślnie `vpcsc-ci-no-destroy` — musi zgadzać się z `local.deny_policy_name`
          w iam-bootstrap/main.tf, inaczej dostaniesz stabilne „NIE MA” na działającym guardrailu
POMOC
  exit 3
}

while [ $# -gt 0 ]; do
  case "$1" in
    --org)  shift; ORG_ID="${1:-}" ;;
    --name) shift; NAZWA="${1:-}" ;;
    -h|--help) uzycie ;;
    *) echo "nieznany argument: $1" >&2; uzycie ;;
  esac
  shift
done

[ -n "$ORG_ID" ] || uzycie
case "$ORG_ID" in *[!0-9]*) echo "--org przyjmuje NUMER organizacji, nie nazwę domeny: $ORG_ID" >&2; exit 3 ;; esac

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
    echo "Utworzenie wymaga roles/iam.denyAdmin (jedyna rola z iam.denypolicies.create; roli własnej z tym"
    echo "uprawnieniem zbudować się NIE DA) i apply w iam-bootstrap/ z manage_deny_policy = true."
    exit 1
    ;;
  403)
    echo "NIE WIADOMO: brak uprawnienia iam.denypolicies.get na organizacji ${ORG_ID}." >&2
    echo "TO NIE ZNACZY, ŻE POLITYKI NIE MA — API zwraca 403 także wtedy, gdy istnieje." >&2
    echo "Nadaj rolę odczytu i powtórz:" >&2
    echo "  gcloud organizations add-iam-policy-binding ${ORG_ID} \\" >&2
    echo "    --member='user:TWOJ_ADRES' --role='organizations/${ORG_ID}/roles/vpcScDenyReader'" >&2
    exit 2
    ;;
  *)
    echo "BŁĄD: nieoczekiwana odpowiedź API (HTTP ${KOD})." >&2
    cat "$ODP" >&2
    exit 3
    ;;
esac
