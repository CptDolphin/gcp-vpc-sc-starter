# contrib/ — jak zespół zgłasza zmianę ze swojego repozytorium

Materiał dla **repozytorium dywizji**, nie dla repo perimetru. Trzy kroki, ~15 minut.

## Zasada

Twoje repozytorium **nie aplikuje** niczego w VPC-SC i **nie potrzebuje żadnych uprawnień w GCP** — ani
jednego konta serwisowego, ani jednej federacji tożsamości. Deklarujesz u siebie, walidujesz u siebie,
a repo perimetru otwiera z tego PR i stosuje zmianę jednym, wspólnym apply.

DLACZEGO tak, a nie „damy wam dostęp": Access Context Manager przepisuje całą politykę organizacji przy każdej
zmianie i pilnuje jej **eTagiem**. Dwa repozytoria aplikujące równolegle nie gubią reguł po cichu — przegrany
apply pada głośno na `Error 400: The eTag provided … does not match` (zmierzone: ~80-100% nałożonych w czasie
przebiegów). To nie jest pocieszające: znaczy, że przy dwóch mutatorach co drugi merge losowo się wywraca
i wymaga ponowienia, a rosnąca liczba dywizji tylko podnosi częstość kolizji. Do tego każde takie repozytorium
musiałoby dostać prawo zmiany granicy **całej firmy**, bo uprawnień ACM nie da się zawęzić do folderu.

## Krok 1 — jeden dostęp, i to na GitHubie

| Co | Po co |
|---|---|
| token GitHub App z **`Contents: Read-only`** na repo perimetru | pobranie **kontraktu** i **paczki bramek** — jedno i drugie jest assetem release'u, a release'y są zasobem `Contents` |
| token GitHub App z **`Actions: Read and write`** na repo perimetru | wysłanie zgłoszenia (`workflow_dispatch`); to uprawnienie URUCHAMIA workflow i **nie daje prawa zapisu kodu** — §„Zakres tokenu" niżej |

**To wszystko.** Zero uprawnień do Access Context Managera, zero dostępu do stanu Terraform, zero tożsamości
w Google Cloud.

> **Skąd bierze się kontrakt.** Repo perimetru publikuje go w dwóch miejscach z **jednego kroku apply**:
> do bucketa (dla konsumentów maszynowych spoza GitHuba) i jako asset release'u `contract` (dla ciebie).
> Wcześniej istniała tylko ta pierwsza droga i wymagała od ciebie tożsamości w GCP oraz grantu na buckecie —
> po to, żeby przeczytać 4 KB JSON-a. Asset czytasz tym samym tokenem, którym i tak pobierasz bramki, więc
> ta zmiana nie dokłada ani jednego uprawnienia. Obie kopie powstają z tego samego kroku apply i mają
> sprawdzane md5, więc pytanie „która jest aktualna" nie ma jak powstać.

> **Dlaczego nie submodule?** Submodule dałby ci CAŁE repozytorium perimetru — razem z `perimeter/members/`
> (konta serwisowe i grupy wszystkich dywizji) i `perimeter/access-levels/` (korporacyjne zakresy IP).
> Do zwalidowania jednego swojego pliku potrzebujesz tylko **reguł** (paczka `gates.tar.gz` z release'u)
> i **listy dostępnych opcji** (kontrakt). Żadne z nich nie mówi ci, kto jest w perimetrze.

## Krok 2 — napisz deklarację

Jeden plik YAML u siebie, np. `vpc-sc/request.yaml`:

```yaml
schema_version: 1
division: example-division
project_id: prj-example-vertex-prod
project_number: "123456789012"
owner_group: grp-example-division-cloud@example.com
approved_by: lead-example-division@example.com
profiles:
  - name: vertex-online-serving
    params:
      caller_identities: ["serviceAccount:sa-scoring@prj-example-app-prod.iam.gserviceaccount.com"]
      access_levels: ["corp_network"]
```

**Czterech pól nie ma tu celowo** — `stage`, `dry_run_since`, `review_by`, `change_ref` wypełnia strona
perimetru. `stage` zawsze na `dry-run` (inaczej jedno pole w pliku omijałoby całą dwustopniowość
onboardingu), daty okna obserwacji z dnia przyjęcia wniosku, a referencję zmiany z realnego zdarzenia.
Przy `dry_run_since` powód jest ostrzejszy niż porządek: **data wsteczna od wnioskodawcy sprawia, że
bramka promocji liczy okno jako dawno minione** — czyli kasuje pomiar, dla którego dwustopniowy
onboarding istnieje. Pole opisujące czas pomiaru nie może pochodzić od mierzonego.

Deklaracja jest więc WĘŻSZA niż plik członka w repo perimetru; `validate-local.sh` uzupełnia te pola
w kopii, dokładnie tak jak zrobi to kanał wejściowy, i dopiero tę kopię sprawdza schemą.

> Kompletne, gotowe do skopiowania repozytorium dywizji — razem z workflowem i tym plikiem —
> leży w starterze w `examples/division-repo/`.

Nie wymyślasz reguł ingress/egress — wybierasz **profil**. Listę dostępnych profili i wymaganych parametrów
masz w kontrakcie:

```bash
gh release download contract --repo ORG/gcp-vpc-sc --pattern contract.json --clobber
jq '.profiles' contract.json
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
          app-token: ${{ steps.app.outputs.token }}
          # gates-version: gates-2026.07.30-abc1234   # przypnij, jeśli chcesz powtarzalną walidację
```

`GITHUB_TOKEN` **nie zadziała** — jest zawężony do repozytorium, w którym powstał. Potrzebna jest GitHub App
zainstalowana na obu repozytoriach.

### Zakres tokenu — zmierzony, nie wywnioskowany

Skoro kanał kończy się pull requestem, wydaje się, że token potrzebuje `pull_requests: write`. Pomiar
(`GITHUB_TOKEN` z `permissions:` zawężonym per job — ten sam model uprawnień co instalacja Appa) mówi
odwrotnie, i to w obie strony:

| Uprawnienia tokenu | Wywołanie | HTTP |
|---|---|---|
| `contents: read` + `pull-requests: write` | `POST /repos/{o}/{r}/dispatches` | **403** `Resource not accessible by integration` |
| `contents: write` | `POST /repos/{o}/{r}/dispatches` | **204** |
| `actions: write` (bez `contents`) | `POST /repos/{o}/{r}/actions/workflows/{plik}/dispatches` | **204** |
| `contents: write` **bez** `actions` | `POST /repos/{o}/{r}/actions/workflows/{plik}/dispatches` | **403** |
| `contents: read` (bez niczego więcej) | `GET /repos/{o}/{r}/releases` + pobranie assetu | **200** |

Wiersze 3–4 są tu najważniejsze: **`actions` i `contents` są rozłączne w obie strony.** Token, który
potrafi uruchomić workflow przyjmujący zgłoszenia, **nie potrafi zapisać ani jednego bajtu** w repozytorium
perimetru. Wiersz 5 zamyka drugą połowę: `Contents: Read-only` wystarcza do pobrania kontraktu i paczki
bramek, bo obie są **assetami release'u**.

- **Kanał jedzie `workflow_dispatch`-em i wymaga `actions: write`.** `pull_requests` nie jest potrzebne
  w ogóle — PR-a otwiera po swojej stronie `external-intake.yml`, własnym `GITHUB_TOKEN`-em repozytorium
  perimetru.
- **`repository_dispatch` był tu wcześniej i został wycofany**, bo wymaga `contents: write`, czyli prawa
  zapisu do KODU perimetru. To „więcej niż otworzyć PR" — i składa się z drugim faktem: bramki treści
  (schema, OPA, budżet, pre-flight) wiszą na zdarzeniu `pull_request`, a apply rusza z **pushu na gałąź
  domyślną**. Poświadczenie z prawem zapisu jest więc ścieżką do zmiany granicy z pominięciem wszystkich
  bramek wszędzie tam, gdzie gałąź domyślna nie jest chroniona (ochrona gałęzi to na części planów GitHuba
  funkcja płatna dla repozytoriów prywatnych — patrz „Prerekwizyt" niżej).
- **Czego `actions: write` NIE odbiera i o czym nie milczymy:** pozwala też ponawiać i anulować przebiegi
  oraz **kasować logi przebiegów** w repo perimetru. Węższe niż zapis kodu, ale nie zerowe. Ślad, który
  ma znaczenie, siedzi więc w gicie (PR i commit), a nie wyłącznie w historii przebiegów.

Kanału i tak nie ogranicza sam zakres tokenu, tylko cztery rzeczy poza nim: mapowanie `contributors.yaml`
po tamtej stronie, payload traktowany jako dane (a nie autoryzacja), apply wyłącznie z gałęzi domyślnej
i **ochrona tej gałęzi**.

### Prerekwizyt po stronie perimetru: gałąź domyślna MUSI być chroniona

To nie jest zalecenie higieniczne. Bramki treści uruchamiają się na `pull_request`; push prosto na gałąź
domyślną nie uruchamia **ani jednej** z nich, a apply rusza właśnie z tej gałęzi. Ochrona gałęzi jest tym,
co sprawia, że słowo „bramka" cokolwiek znaczy.

Zmierzone: na darmowym planie GitHuba dla repozytorium **prywatnego** `GET /repos/{o}/{r}/branches/main/protection`
odpowiada **403** `Upgrade to GitHub Pro or make this repository public to enable this feature.` Upublicznienie
repo perimetru nie jest obejściem — jego treść to mapa tego, co i skąd sięga po wasze dane.

`tools/bootstrap_github.sh` odczytuje ten stan z API (nie z kodu wyjścia `PUT`-a), nazywa przyczynę i
**kończy się błędem**, gdy ochrony nie ma. Świadome odstępstwo: `--no-branch-protection "<powód>"`.

**Bramki przypinasz, kontraktu NIE.** To nie jest niekonsekwencja: bramki są **regułami**, więc pin daje
powtarzalną walidację. Kontrakt jest **stanem świata** — przypięty pokazywałby profile i access levels,
których już nie ma, czyli dawałby zielono na wejściu, które repo perimetru odrzuci.

## Co się dzieje po twojej stronie granicy

1. Action waliduje plik lokalnie (schema + reguły onboardingu).
2. Wysyła zgłoszenie (`workflow_dispatch` na `external-intake.yml`, na gałęzi domyślnej repo perimetru)
   z `change_ref: pr:TWOJE-REPO#NUMER` — **ustawianym przez action**, nie przez ciebie; samodzielnie
   zadeklarowana referencja niczego by nie dowodziła.
3. Repo perimetru sprawdza, czy twoje repozytorium ma ten projekt na liście dozwolonych
   (`perimeter/contributors.yaml`) i czy dywizja się zgadza — po czym otwiera PR.
4. Zespół sieciowy zatwierdza, apply dodaje projekt do konfiguracji **dry-run**: nic nie jest blokowane
   i nic nie jest jeszcze chronione.
5. Po ~2 tygodniach dostajesz raport naruszeń, a promocja do stanu chronionego to osobny, ludzko zatwierdzony PR.

## Walidacja bez pipeline'u

```bash
gh release download --repo ORG/gcp-vpc-sc --pattern gates.tar.gz --clobber && tar -xzf gates.tar.gz
gh release download contract --repo ORG/gcp-vpc-sc --pattern contract.json --clobber
./gates/validate-local.sh --member vpc-sc/prj-example-vertex-prod.yaml --gates ./gates --contract ./contract.json
```

Obie komendy chodzą na tokenie GitHuba (`gh auth login`). `gcloud` nie jest tu potrzebny — i to jest właśnie
ta zmiana: dywizja nie musi mieć konta w Google Cloud, żeby zwalidować swój plik.

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
| `brak kontraktu` | apply perimetru jeszcze nie przeszedł (release `contract` nie istnieje) albo twój token nie ma dostępu do release'ów repo perimetru |
| `Resource not accessible by integration` (HTTP 403) na wysyłce zgłoszenia | aplikacja nie ma `Actions: Read and write` na repo perimetru — `workflow_dispatch` wymaga `actions: write`, a `contents: write` na tym endpoincie **nie wystarcza** (§„Zakres tokenu") |
| `Workflow does not have 'workflow_dispatch' trigger` (HTTP 422) | repo perimetru jest na starym kanale albo plik `external-intake.yml` nie istnieje na jego **gałęzi domyślnej** — GitHub przyjmuje `workflow_dispatch` tylko dla workflowów obecnych na tej gałęzi |
| `profil … wymaga parametru …` | profil deklaruje parametr, którego nie podałeś — parametry są w pliku profilu |
