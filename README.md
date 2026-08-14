# vpc-sc-perimeter-starter — bootstrap repozytorium zarządzającego perimetrem VPC-SC

Kompletny starter repo GitHub, w którym **dywizje dołączają do jednego perimetru VPC Service Controls
samoobsługowo**: ticket w ServiceNow → approval zespołu sieciowego → PR otwierany przez bota → bramki →
apply. Trzy kanały wejścia (formularz · bezpośredni PR architekta · repo zespołu przez publikowany kontrakt)
prowadzą do **jednego** mutatora — zmienia się tylko to, skąd przychodzi PR (DEC-7, DEC-8 w `docs/0-decyzje.md`). Vertex AI jest chroniony od dnia zero; każdy nowy członek ląduje najpierw w konfiguracji **dry-run**,
a promocja do **enforced** to osobny, ludzko-zatwierdzony PR.

Osiem decyzji, na których to stoi — wraz z odrzuconymi wariantami — jest w
[`docs/0-decyzje.md`](docs/0-decyzje.md). Komentarze w kodzie odsyłają tam skrótem `(DEC-4)`.

> **To jest bootstrap dla innego repozytorium, nie działająca instalacja.** Szablony są **martwe** —
> `template/**.example`, bez plików-kropek i bez żywych `*.tf` — więc żadne narzędzie nie uruchomi ich
> przypadkiem tam, gdzie ten katalog leży. Ożywia je dopiero `install.sh`, świadomie i gdzie indziej.

## Szybki start

```bash
./install.sh /sciezka/do/nowego/repo          # rozpakuj wszystko
./install.sh /sciezka --dry-run               # tylko pokaż mapowanie nazw
./install.sh /sciezka --only validate.yml     # jeden plik — wdrożenie etapami
python3 selftest/selftest.py                  # dowód, że to działa (270 testów)
```

Po rozpakowaniu podmień placeholdery (`<ORG_ID>`, `<ACCESS_POLICY_NUMBER>`, `<STATE_BUCKET>`,
`<CONTRACTS_BUCKET>`, `<SCANNER_SA>`, `@your-org/*`)
i przeczytaj [`docs/1-wdrozenie.md`](docs/1-wdrozenie.md) — kolejność kroków ma znaczenie.

## Co dostajesz

| Element | Co robi | Dlaczego tak |
|---|---|---|
| `perimeter/policy.yaml` | baseline: usługi objęte granicą, okno dry-run, budżet atrybutów | jeden czytelny plik zamiast HCL — audytor i security czytają go bez znajomości Terraform |
| `perimeter/profiles/*.yaml` | katalog wzorców reguł (serving, training, konsola) | dywizje wybierają profil, nie piszą reguł: limit **6000 atrybutów/konfigurację** i review, który się skaluje |
| `perimeter/projects.yaml` | jedna lista = wszyscy członkowie perimetru | całą granicę widać w jednym pliku, a diff w PR pokazuje dokładnie tyle, ile zmienia wniosek; duplikat wpisu łapią cztery niezależne bramki (DEC-12) |
| `terraform/` | renderer YAML → **granularne** zasoby ACM | błąd w jednym wniosku wywraca własny zasób, nie apply całego perimetru |
| `policy/*.rego` | bramki: brak `ANY_*`, brak `method: "*"`, ingress bez access-levelu, promocja bez okna | reguła oceniana na **planie**, nie na deklaracji — plan jest tym, co zmieni granicę |
| `terraform/tests/*.tftest.hcl` | natywne testy renderera (14 przypadków, bez credentiali) | `locals.tf` to jedyne miejsce z logiką — reszta to deklaracje, więc tu jest jedyne, co może się cicho zepsuć |
| `policy.yaml` §`baseline_ingress` | reguły dla **każdego** członka: skanery, backup, monitoring | jako profil per-member pierwsza dywizja, która zapomni go wybrać, wypada ze skanowania w momencie promocji |
| `policy.yaml` §`control_plane_projects` | lista projektów, w których leży maszyneria perimetru (stan Terraform, kontrakty, monitoring); bramka OPA odrzuca członka wskazującego którykolwiek z nich | **jedyny tryb awarii tego repo, którego `git revert` nie cofa**: projekt z bucketem stanu w konfiguracji egzekwowanej odcina konto apply od własnego stanu (apply woła spoza granicy), a apply rewertu też potrzebuje stanu — wyjście tylko przez człowieka z uprawnieniami org-level. Furtka `control_plane_exception` w pliku członka zamiast wyłączania bramki |
| `tools/control_plane_check.py` | konfrontuje **listę** wyżej z tym, gdzie maszyneria leży naprawdę: backend ↔ `contract.state_bucket`, `monitoring.project_id` ↔ lista, stack tożsamości ↔ lista, a przy `--live` — **właściciel bucketa stanu odczytany z API** | bramka wyżej pilnuje listy, więc projekt płaszczyzny sterowania, którego na niej NIE MA, przechodzi jak zwykły wniosek. Deklaracja, której nikt z niczym nie konfrontuje, chroni zbiór wyglądający na pełny — ta sama klasa błędu co bramka czytająca nieistniejący plik |
| `tools/` | budżet atrybutów · pre-flight · weryfikacja ticketu · raport naruszeń · render członka · **zgodność baseline z żywą listą usług VPC-SC** | każdy zamyka konkretny tryb awarii (opisany w nagłówku pliku) |
| `.github/workflows/` (13) | intake · external-intake · **intake-rebase** · validate · plan · apply · drift · violations-report · expiry-sweep · break-glass · publish-gates · starter-drift · boundary-probe | apply jest jedynym mutatorem: WIF keyless, environment z polityką gałęzi (i z recenzentami tam, gdzie plan GitHuba je ma), single-flight |
| `.github/actions/contrib/` (tutaj) + `contrib/validate-local.sh` + `perimeter/contributors.yaml` | trzeci kanał wejścia: repo zespołu waliduje u siebie i **uruchamia** `external-intake.yml` (`workflow_dispatch`) | zespół dostaje `actions: write` — prawo URUCHOMIENIA workflowa, bez zapisu kodu i bez `servicePerimeters.update` na organizacji (DEC-7) |
| `terraform/contract.tf` + `publish-gates.yml` | publikuje wąski JSON (~4 KB) **w dwóch miejscach z jednego kroku apply** (bucket + asset release'u) i paczkę bramek | submodule oddawał `members/` wszystkich dywizji i zakresy IP, żeby zwalidować jeden plik; sam bucket kosztował dywizję tożsamość w GCP i grant IAM po to, by przeczytać 4 KB (DEC-8) |
| `.tflint.hcl` + job `tflint` | statyczna analiza HCL: martwe zmienne, brak pinów providerów, literówki w atrybutach Google | `validate` przechodzi na konfiguracji z martwym knobem i niepinowanym providerem — jedno i drugie boli na obiekcie org-plane |
| `tests/` + `docs/5-servicenow-intake.md` | fixture'y kanału ServiceNow (3 z 5 negatywne) + specyfikacja formularza i mapowania pól | kanał wejścia musi dać się przetestować **bez** działającej instancji ServiceNow — inaczej pierwszy test odbywa się na produkcji |
| `.github/dependabot.yml` | aktualizacje pinów SHA akcji i lock providera | pin SHA bez mechanizmu aktualizacji to stara wersja z odznaką bezpieczeństwa |
| `iam-bootstrap/` | **osobny stack**: 2 konta serwisowe, custom rola (`update` bez `create`/`delete`), role read-only pre-flight, pula WIF z `attribute_condition`, IAM Deny | applikuje go **zespół IAM**, nie ten pipeline — kod nadający uprawnienia nie może być stosowany przez tożsamość, która z nich korzysta |

## Diagramy

| | |
|---|---|
| [D1 — onboarding flow](docs/diagrams/D1-onboarding-flow.drawio) ([PNG](docs/diagrams/D1-onboarding-flow.png)) | ticket → PR → bramki → dry-run → obserwacja → promocja |
| [D2 — model dostępów i WIF](docs/diagrams/D2-iam-and-wif.drawio) ([PNG](docs/diagrams/D2-iam-and-wif.png)) | która tożsamość potrzebuje której roli i dlaczego — materiał do requestu |
| [D3 — anatomia perimetru](docs/diagrams/D3-perimeter-anatomy.drawio) ([PNG](docs/diagrams/D3-perimeter-anatomy.png)) | co należy do repo, co znaczą dwie konfiguracje, brownfield |
| [D4 — ścieżka dywizji](docs/diagrams/D4-division-journey.drawio) ([PNG](docs/diagrams/D4-division-journey.png)) | onboarding oczami zespołu, który dołącza — oś czasu, co robi on, co platforma, co obowiązuje |
| [D5 — struktura folderów](docs/diagrams/D5-struktura-folderow.drawio) ([PNG](docs/diagrams/D5-struktura-folderow.png)) | układ dwóch repozytoriów przy 200 projektach: który plik gdzie ląduje i kto jest jego właścicielem |
| [D6 — trzy kanały wejścia](docs/diagrams/D6-trzy-kanaly.drawio) ([PNG](docs/diagrams/D6-trzy-kanaly.png)) | **zacznij tutaj**: cała mechanika na jednym obrazku — trzy kanały, jeden mutator, gdzie kończy się zaufanie |
| [D7 — co gdzie leży](docs/diagrams/D7-struktura-repo.drawio) ([PNG](docs/diagrams/D7-struktura-repo.png)) | mapa obu repozytoriów: który plik czyj i co między nimi płynie (kontrakt w jedną stronę, dispatch w drugą). Treść po angielsku |

## Dokumentacja

- [`docs/1-wdrozenie.md`](docs/1-wdrozenie.md) — kolejność kroków, placeholdery, ochrona gałęzi, environments
- [`docs/2-uprawnienia-i-wif.md`](docs/2-uprawnienia-i-wif.md) — **rola po roli: po co i co się stanie bez niej**;
  gotowa lista do wklejenia w ticket do architekta
- [`docs/3-runbook-promocja-i-break-glass.md`](docs/3-runbook-promocja-i-break-glass.md) — promocja do enforced
  i procedura awaryjna
- [`docs/4-brownfield-import.md`](docs/4-brownfield-import.md) — perimetr **już istnieje**: jak podłączyć się
  bez ryzyka nadpisania cudzej konfiguracji
- [`docs/5-servicenow-intake.md`](docs/5-servicenow-intake.md) — **kanał ServiceNow od formularza do reguły**:
  pola pozycji katalogu, ścieżka approvali, payload `repository_dispatch`, tabela błędów, testowanie bez SNOW
- [`docs/6-uklad-repozytoriow.md`](docs/6-uklad-repozytoriow.md) — **plik na projekt czy jeden `projects.yml`**:
  co gdzie ląduje przy 100–200 projektach, diagram struktury folderów i pomiar konfliktów (10 równoległych
  PR-ów: 10/10 kontra 1/10)
- [`docs/7-alerty.md`](docs/7-alerty.md) — alert po alercie: co znaczy, kto to odczuwa, procedura per objaw
- [`docs/8-zmiany-reczne.md`](docs/8-zmiany-reczne.md) — zmiany, których nie obsługuje żaden formularz:
  wniosek ręczny, profil, access level (dodanie i **uzbrojenie**), `restricted_services`
- [`docs/9-karta-wejscia.md`](docs/9-karta-wejscia.md) — **wejście do cudzej organizacji**: pytania o stan
  zastany granicy, uprawnienia (łącznie z tymi, których nie dostaniemy) i cudze procesy — każde z konsekwencją
  odpowiedzi „nie" i mapą odpowiedź→knob
- [`.github/actions/contrib/README.md`](.github/actions/contrib/README.md) — instrukcja dla **innych
  repozytoriów**: co dostają w kontrakcie, jak walidują u siebie, czego nie mogą. Akcja mieszka TUTAJ,
  a nie w repozytorium perimetru: `uses:` rozwiązuje się tokenem repo dywizji, zanim wykona się
  jakikolwiek krok, więc źródło musi być publiczne (DEC-21)

## Przykład drugiej strony granicy

[`examples/division-repo/`](examples/division-repo/README.md) — **kompletne repozytorium dywizji** do
skopiowania: jeden `vpc-sc/request.yaml`, workflow (walidacja na PR, zgłoszenie dopiero po merge) i README,
który mówi wprost **czego zespół NIE dostaje** — konta serwisowego, stanu Terraform, wglądu w `members/`
innych dywizji ani w zakresy IP z `access-levels/`. Jedno prawo: doprowadzić do powstania PR-a —
`Contents: Read-only` (kontrakt i bramki z release'ów) + `Actions: Read and write` (uruchomienie
`external-intake.yml`). Zmierzone: `actions` i `contents` są rozłączne w obie strony, więc token dywizji
**nie ma prawa zapisu do kodu perimetru**. Prerekwizyt po drugiej stronie: chroniona gałąź domyślna.

Ten katalog **nie jest rozpakowywany** przez `install.sh`: to materiał dla repozytorium dywizji, a `install.sh`
buduje repozytorium perimetru — workflow przykładu stałby się tam żywym jobem wysyłającym zgłoszenie do
samego siebie (uzasadnienie w nagłówku `install.sh`, guard w selfteście).

## Eksperymenty

[`experiments/konflikty-ukladow/`](experiments/konflikty-ukladow/README.md) — ile PR-ów z dziesięciu przechodzi
bez konfliktu przy 200 projektach, w trzech układach plików. Kilkanaście sekund, zero chmury; odpal, zanim
ktoś rozstrzygnie „plik na projekt czy jeden plik" preferencją.

[`experiments/race-two-states/`](experiments/race-two-states/README.md) — gotowy zestaw rozstrzygający, czy
dwa stany Terraform mogą bezpiecznie dodawać reguły do jednego perimetru. Dwa równoległe applye, odczyt z API,
sprzątanie. Uruchom, zanim ktoś podejmie decyzję na podstawie opinii — koszt zero, ACM jest darmowy.

## Dowód, że działa

`python3 selftest/selftest.py` rozpakowuje starter do katalogu tymczasowego i uruchamia na nim realne bramki —
**270/270** przy ostatnim przebiegu: `terraform fmt`/`validate`/**`test`** (14 przypadków renderera),
`conftest verify` (47 testów reguł), **`tflint`** na każdym stacku Terraforma, narzędzia na realnych deklaracjach
(w tym cztery fixture'y kanału ticketowego), `actionlint` na dwunastu workflow **i na workflow przykładu
dywizji**, realny `validate-local.sh` uruchomiony na `examples/division-repo/vpc-sc/request.yaml`, guardy
na treść stacku IAM, kontraktu, nazwy obiektów ACM i pinowanie akcji.

Testy są w połowie **negatywne** i to jest sedno: sprawdzają, że bramka **PADA** na złym wejściu — promocja
przed oknem obserwacji, baseline bez usługi zadeklarowanej jako niezmiennik, plan z `ANY_IDENTITY`/`method: "*"`, ticket bez
zatwierdzenia, podmiana projektu w payloadzie, przekroczony budżet atrybutów, projekt płaszczyzny sterowania
wciągany do perimetru. Bramka, która nigdy nie odrzuca, przechodzi każdy test pozytywny i nie chroni niczego.

Każdy negatyw ma **parę anty-tautologiczną**: obok „członek z listy `control_plane_projects` jest odrzucany"
stoi „zwykły projekt przechodzi przy **niepustej** liście". Bez tej drugiej asercji reguła odrzucająca
wszystko wyglądałaby na działającą.

Czego selftest **nie** sprawdza: mechaniki GitHuba (environments, OIDC, required reviewers) ani realnego API
Google — pierwszą warstwę pokrywa `actionlint`, drugą dopiero pierwszy apply na środowisku docelowym.

Skoro nie potrafi sprawdzić, czy bramka po stronie GitHuba **istnieje**, sprawdza to, co da się sprawdzić:
że `tools/bootstrap_github.sh` **odczytuje ustawienia z powrotem z API** zamiast wnioskować z wysłanego
PUT-a, i że brak bramki ludzkiej wymaga jawnego odstępstwa. Wymagani recenzenci na environment i ochrona
gałęzi prywatnego repo bywają funkcjami płatnymi — na planie bez nich API odrzuca żądanie, a environment
zostaje bez ani jednej reguły ochrony, opisany w dokumentacji jako bramka. To jest ten tryb awarii.

## Świadome pominięcia (znamy, nie renderujemy)

Model danych startera pokrywa te elementy VPC-SC, których wymaga opisany tu przepływ. Poniższe **istnieją w API i są
pominięte świadomie** — zapisane tutaj, żeby „nie ma tego" nie było mylone z „nie wiedzieliśmy":

| Element API | Dlaczego nie renderujemy |
|---|---|
| `egressFrom.identityType` / `ingressFrom.identityType` (`ANY_IDENTITY`, `ANY_SERVICE_ACCOUNT`) | Zawsze wypisujemy tożsamości jawnie. `ANY_IDENTITY` w regule ingress to najszersza możliwa dziura w granicy — bramka OPA odrzuca ją w planie, więc renderer nie ma jak jej wytworzyć. |
| `egressFrom.sources` + `sourceRestriction` | Zawęża, *skąd wewnątrz* perimetru wolno wyjść. Realna wartość przy wielu strefach zaufania w jednym perimetrze; tutaj każdy egress jest już zawężony tożsamością i celem, a każdy dodatkowy atrybut liczy się do limitu 6000/konfigurację. Do dołożenia, gdy pojawi się pierwszy przypadek, który tego wymaga — nie „na zapas". |
| `ingressFrom.sources.resource` (ingress z projektu wewnątrz perimetru) | Ruch między projektami w tym samym perimetrze nie wymaga reguły — reguła sugerowałaby, że wymaga, i zużywałaby atrybuty na przepływ, który i tak przechodzi. |
| Perimetry typu **bridge** | Rozwiązują problem „dwa perimetry muszą się widzieć". Wytyczna to jeden perimeter org-wide (DEC-1), więc bridge nie ma czego łączyć. |
| **Scoped policies** (`--scopes=folders/…`) | Byłyby naturalną odpowiedzią na „każda dywizja rządzi swoim" i usuwałyby wyścig z DEC-6 — zamyka je ta sama wytyczna o jednym perimetrze. Zostają jako **środowisko testowe** (`docs/2` §4a). |
| `vpcAccessibleServices` per członek | To pole jest własnością perimetru, nie członka — jedna lista dla całej granicy. Per-member wymagałoby wielu perimetrów. |
| Globalny „kill-switch" wyłączający egzekwowanie całego perimetru | Wygląda na oczywisty lever incydentowy, ale rollback już istnieje i jest lepszy: `git revert` złej zmiany + apply (jeden PR, historia zachowana). Switch dokładałby **globalny wyłącznik ochrony całej organizacji** — czyli nowy blast-radius w imię oszczędzenia kilku minut. Awaryjne wyjęcie POJEDYNCZEGO członka robi `break-glass.yml`. |
| Promocja komendą `perimeters dry-run enforce` | Commituje CAŁĄ konfigurację dry-run naraz. Przy jednym perimetrze = promocja wszystkich dywizji jednym wywołaniem. Guard `no-dry-run-commit` (w `.github/actions/bramki-tresci`, wołany przez PR i przez apply) nie dopuszcza jej do workflow ani skryptów. |

Każda pozycja to decyzja odwracalna: dołożenie pola do renderera jest zmianą na kilkanaście linii w
`terraform/`, plus wpis w schemacie i test. Kolejność jest odwrotna niż zwykle — najpierw przypadek użycia,
potem knob.

## Wymagania

`terraform` 1.15.5 · `conftest` (OPA) · `tflint` 0.63.1 (`tflint --init` raz, po plugin google) · `python3`
z `pyyaml` · opcjonalnie `actionlint`, `check-jsonschema`. Wszystkie wersje są w `.tool-versions`, a CI
instaluje je sam w `.github/actions/bramki-tresci` — lokalny brak narzędzia daje w selfteście SKIP z nazwą, nie ciche zielone.
