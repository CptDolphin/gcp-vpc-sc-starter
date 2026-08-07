# contrib/ — jak zespół zgłasza zmianę ze swojego repozytorium

Materiał dla **repozytorium dywizji**, nie dla repo perimetru. Trzy kroki, ~15 minut.

## Zasada

Twoje repozytorium **nie aplikuje** niczego w VPC-SC i **nie potrzebuje żadnych uprawnień w GCP**. Deklarujesz
u siebie, walidujesz u siebie, a repo perimetru otwiera z tego PR i stosuje zmianę jednym, wspólnym apply.

DLACZEGO tak, a nie „damy wam dostęp": Access Context Manager przepisuje całą politykę organizacji przy każdej
zmianie. Dwa repozytoria aplikujące równolegle nadpisują sobie reguły — w logach widać dwa poprawne `update`,
a reguła znika. Do tego każde takie repozytorium musiałoby dostać prawo zmiany granicy **całej firmy**, bo
uprawnień ACM nie da się zawęzić do folderu.

## Krok 1 — dwa dostępy, żadnego w GCP poza odczytem jednego pliku

| Co | Po co |
|---|---|
| `roles/storage.objectViewer` na prefiksie `vpc-sc/` w buckecie kontraktów | odczyt **jednego pliku JSON** (~4 KB) z listą dostępnych profili i twoich projektów |
| token GitHub App z `pull_requests: write` na repo perimetru | otwarcie PR |

**To wszystko.** Zero uprawnień do Access Context Managera, zero dostępu do stanu Terraform.

> **Dlaczego nie submodule?** Submodule dałby ci CAŁE repozytorium perimetru — razem z `perimeter/members/`
> (konta serwisowe i grupy wszystkich dywizji) i `perimeter/access-levels/` (korporacyjne zakresy IP).
> Do zwalidowania jednego swojego pliku potrzebujesz tylko **reguł** (paczka `gates.tar.gz` z release'u)
> i **listy dostępnych opcji** (kontrakt). Żadne z nich nie mówi ci, kto jest w perimetrze.

## Krok 2 — napisz deklarację

Jeden plik YAML u siebie, np. `vpc-sc/prj-example-vertex-prod.yaml`:

```yaml
schema_version: 1
division: example-division
project_id: prj-example-vertex-prod
project_number: "123456789012"
owner_group: grp-example-division-cloud@example.com
approved_by: net-approver@example.com
change_ref: "pr:PLACEHOLDER"        # nadpisze action — patrz niżej
stage: dry-run                       # i tak wymuszane po stronie perimetru
dry_run_since: "2026-07-29"
review_by: "2027-01-29"
profiles:
  - name: vertex-online-serving
    params:
      caller_identities: ["serviceAccount:sa-scoring@prj-example-app-prod.iam.gserviceaccount.com"]
      access_levels: ["corp_network"]
exceptions: []
```

Nie wymyślasz reguł ingress/egress — wybierasz **profil**. Listę dostępnych profili i wymaganych parametrów
masz w kontrakcie:

```bash
gcloud storage cat gs://ORG-tf-contracts/vpc-sc/contract.json | jq '.profiles'
```

Nie ma profilu na twój przypadek? To osobna rozmowa z zespołem sieciowym; trzeci taki sam wyjątek staje się
profilem.

## Krok 3 — workflow u siebie

Akcje w przykładzie są **przypięte SHA-em**, a wersja stoi w komentarzu. To nie jest ozdoba: ruchomy tag
(`@v4`, a zwłaszcza `@main`) jest mutowalną referencją — kto kontroluje tag, kontroluje kod uruchamiany z
waszym tokenem. Nasza akcja `contrib` też ma być przypięta do **SHA wydania**, nie do `main`; wydania
publikujemy razem z paczką bramek (`publish-gates.yml`), więc pin nie zostaje w tyle w nieskończoność.

```yaml
name: vpc-sc-request
on:
  pull_request:
    paths: ["vpc-sc/**"]

jobs:
  request:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0

      - uses: google-github-actions/auth@c200f3691d83b41bf9bbd8638997a462592937ed # v2.1.9
        # read-only na prefiksie kontraktu
        with:
          workload_identity_provider: ${{ vars.WIF_PROVIDER }}
          service_account: ${{ vars.CONTRACT_READER_SA }}

      - uses: actions/create-github-app-token@d72941d797fd3113feb6b93fd0dec494b13a2547 # v3.2.0
        id: app
        with:
          app-id: ${{ vars.VPCSC_APP_ID }}
          private-key: ${{ secrets.VPCSC_APP_KEY }}
          owner: ORG
          repositories: gcp-vpc-sc

      - uses: ORG/gcp-vpc-sc/contrib@<SHA_WYDANIA> # np. v1.4.0 — NIE @main
        with:
          member-file: vpc-sc/prj-example-vertex-prod.yaml
          perimeter-repo: ORG/gcp-vpc-sc
          contract-uri: gs://ORG-tf-contracts/vpc-sc/contract.json
          app-token: ${{ steps.app.outputs.token }}
          # gates-version: gates-2026.07.30-abc1234   # przypnij, jeśli chcesz powtarzalną walidację
```

`GITHUB_TOKEN` **nie zadziała** — jest zawężony do repozytorium, w którym powstał. Potrzebna jest GitHub App
zainstalowana na obu repozytoriach, z uprawnieniem `pull_requests: write` na repo perimetru i niczym więcej.

## Co się dzieje po twojej stronie granicy

1. Action waliduje plik lokalnie (schema + reguły onboardingu).
2. Wysyła zgłoszenie z `change_ref: pr:TWOJE-REPO#NUMER` — **ustawianym przez action**, nie przez ciebie;
   samodzielnie zadeklarowana referencja niczego by nie dowodziła.
3. Repo perimetru sprawdza, czy twoje repozytorium ma ten projekt na liście dozwolonych
   (`perimeter/contributors.yaml`) i czy dywizja się zgadza — po czym otwiera PR.
4. Zespół sieciowy zatwierdza, apply dodaje projekt do konfiguracji **dry-run**: nic nie jest blokowane
   i nic nie jest jeszcze chronione.
5. Po ~2 tygodniach dostajesz raport naruszeń, a promocja do stanu chronionego to osobny, ludzko zatwierdzony PR.

## Walidacja bez pipeline'u

```bash
gh release download --repo ORG/gcp-vpc-sc --pattern gates.tar.gz && tar -xzf gates.tar.gz
gcloud storage cat gs://ORG-tf-contracts/vpc-sc/contract.json > contract.json
./gates/validate-local.sh --member vpc-sc/prj-example-vertex-prod.yaml --gates ./gates --contract ./contract.json
```

Sprawdza: strukturę pliku, istnienie profilu, komplet parametrów, istnienie access levels, twoje uprawnienie
do projektu, **czy projekt nie jest już członkiem perimetru** i reguły onboardingu. **Nie sprawdza:**
pre-flightu sieciowego (Private Google Access, strefa DNS na restricted VIP) ani kolizji z **inną**
konfiguracją egzekwowaną (czyli innym perimetrem — to odczyt z żywego GCP) — jedno i drugie weryfikuje repo perimetru.

## Najczęstsze odrzucenia

| Komunikat | Co zrobić |
|---|---|
| `repozytorium … nie ma projektu … na liście dozwolonych` | poproś sieć o wpis w `contributors.yaml` (PR z approvalem) |
| `repozytorium jest przypisane do dywizji X, a wpis deklaruje Y` | zgłaszasz w cudzym imieniu — projekt powinien zgłosić jego właściciel |
| `projekt … jest już członkiem perimetru (… stage: …)` | to nie jest onboarding — projekt już jest w granicy. Zmiana profili albo promocja do `enforced` idzie PR-em na **istniejącym** pliku w repo perimetru; kanał zgłoszeniowy nie nadpisuje wpisów, bo zapisałby `stage: dry-run` na członku, który jest chroniony |
| `profil … nie istnieje` | literówka albo profil, którego nie ma; `jq '.profiles[].name' contract.json` |
| `access level … nie istnieje` | `jq '.access_levels' contract.json` — wskazujesz nazwę, nie zakres IP |
| `brak kontraktu` | nie masz dostępu do bucketa albo apply perimetru jeszcze nie przeszedł |
| `profil … wymaga parametru …` | profil deklaruje parametr, którego nie podałeś — parametry są w pliku profilu |
