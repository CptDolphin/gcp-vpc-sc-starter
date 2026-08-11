# AGENTS.md — jak czytać i odtwarzać ten materiał

Dokument dla człowieka albo modelu, który ma **odtworzyć to repozytorium w innym środowisku**: zrozumieć, co
jest niezmiennikiem, co placeholderem, a co świadomą decyzją wyglądającą na błąd. Czytaj to przed pierwszą
zmianą, nie po niej.

## Czym to jest w trzech zdaniach

Repozytorium zarządza **jednym perimetrem VPC Service Controls** w organizacji Google Cloud. Zespoły dołączają
do niego samoobsługowo: zgłoszenie → automatyczny PR z jednym plikiem YAML → bramki maszynowe → apply przez
pipeline z tożsamością WIF. Terraform jest **wyłącznie rendererem**: źródłem prawdy są pliki w `perimeter/`,
a nie HCL.

## Kolejność czytania

1. [`docs/0-decyzje.md`](docs/0-decyzje.md) — osiem decyzji `DEC-1`…`DEC-8` z odrzuconymi wariantami. Komentarze
   w kodzie odsyłają tam skrótem `(DEC-4)`. **Bez tego pliku połowa kodu wygląda na przekomplikowaną.**
2. [`README.md`](README.md) — co jest w pudełku, tabela „co robi / dlaczego tak", świadome pominięcia.
3. [`terraform/locals.tf`](template/terraform/locals.tf.example) — **jedyne miejsce w repo z logiką**. Reszta
   Terraforma to deklaracje. Jeśli coś się cicho psuje, psuje się tutaj.
4. [`docs/1-wdrozenie.md`](docs/1-wdrozenie.md) — kolejność etapów wdrożenia; ma znaczenie.

## Niezmienniki — zmiana któregokolwiek wymaga decyzji, nie commita

| Niezmiennik | Gdzie egzekwowany | Co się stanie po złamaniu |
|---|---|---|
| `aiplatform.googleapis.com` w `restricted_services` | `precondition` w `perimeter.tf` + reguła OPA w `onboarding.rego` | perimeter wygląda na włączony i nie chroni tego, dla czego powstał (DEC-1) |
| `use_explicit_dry_run_spec = true` **zawsze** | `perimeter.tf` | bez tego nie istnieje członek „tylko w dry-run", czyli nie da się etapować onboardingu (DEC-4) |
| `lifecycle.ignore_changes` na listach szkieletu | `perimeter.tf` | szkielet i zasoby per-członek biją się o te same listy: każdy apply kasuje to, co dodał poprzedni (DEC-6) |
| Reguły ingress mają `depends_on` na `access_level` | `rules.tf` + asercja selftestu czytająca `terraform graph` | access level jest referowany po NAZWIE, więc bez tej pozycji graf nie ma krawędzi i `destroy` kasuje poziom, gdy reguła jeszcze go używa: `you must first remove the reference`. Wychodzi dopiero przy offboardingu członka, czyli w momencie, w którym nikt nie chce debugować granicy |
| Nowy członek zawsze `stage: dry-run` | `render_member.py` + reguła OPA | wejście od razu do konfiguracji egzekwowanej odcina cudzą produkcję po merge'u (DEC-4) |
| `stage`, `dry_run_since`, `review_by`, `change_ref` wpisuje **strona perimetru**, nigdy wnioskodawca | `render_member.py`, `external-intake.yml`, uzupełnianie w `validate-local.sh` + `test_przyklad_repo_dywizji` | `dry_run_since` z datą wsteczną sprawia, że bramka promocji liczy okno obserwacji jako dawno minione — 14 dni pomiaru, dla których istnieje DEC-4, znika. Pole opisujące czas pomiaru nie może pochodzić od mierzonego |
| Kanał wejściowy **nie nadpisuje** istniejącego pliku członka | `out.exists()` w `render_member.py` i `external-intake.yml` | powtórne zgłoszenie zapisałoby `stage: dry-run` na członku `enforced` — projekt traci ochronę PR-em wyglądającym na onboarding. Reguła OPA tego nie łapie: porównuje dwa PLIKI, a tu plik jest ten sam |
| Environment `perimeter-apply` i `break-glass` mają **politykę gałęzi** zawężoną do gałęzi domyślnej | `tools/bootstrap_github.sh` (ustawia i **odczytuje z powrotem**) + asercja selftestu na tym skrypcie | `principalSet` konta apply pinuje samą nazwę environment, **nie ref** — więc bez tej polityki job z `environment: perimeter-apply` na DOWOLNEJ gałęzi wymienia token na tożsamość zapisującą perimetr. To ta polityka, a nie recenzent, jest zdaniem „perimetr zmienia się wyłącznie z gałęzi domyślnej". Działa na każdym planie GitHuba, więc jej brak jest dziurą, nie odstępstwem |
| Kontrola **odczytana z API**, nie wywnioskowana z wysłanego ustawienia | odczyt zwrotny w `tools/bootstrap_github.sh` + asercja selftestu | wymagani recenzenci na environment i ochrona gałęzi prywatnego repo to **funkcje płatne**: na planie, który ich nie ma, API odrzuca żądanie i zostaje environment bez ani jednej reguły ochrony, opisany w komentarzach i dokumentacji jako bramka. Skrypt, który wysyła PUT i milczy o wyniku, produkuje dokładnie ten stan — kontrolę istniejącą wyłącznie w tekście |
| **Oba** kanały automatyczne (dywizji i ticketowy) jadą `workflow_dispatch` (`actions: write`), NIGDY `repository_dispatch` | `contrib/action.yml` + triggery w `external-intake.yml` i `intake.yml` + asercje selftestu | `POST /dispatches` wymaga `contents: write`, czyli prawa zapisu do KODU perimetru. Złożone z gałęzią domyślną bez ochrony i z apply ruszającym z pushu na nią, poświadczenie dywizji staje się ścieżką do zmiany granicy z pominięciem WSZYSTKICH bramek — te wiszą na `pull_request`. Zmierzone: `actions: write` → 204, `contents: write` bez `actions` → 403 (rozłączne w obie strony) |
| **Ochrona gałęzi domyślnej repo perimetru to PREREKWIZYT wdrożenia** | odczyt z API w `tools/bootstrap_github.sh` (błąd bez `--no-branch-protection "<powód>"`) + asercja selftestu | bramki treści (schema, OPA, budżet, pre-flight) uruchamiają się na `pull_request`; push prosto na gałąź domyślną nie uruchamia żadnej, a apply rusza właśnie stamtąd. Na darmowym planie dla repo PRYWATNEGO API odpowiada `403 Upgrade to GitHub Pro…` — wtedy to jest odstępstwo z powodem, nie brak do przemilczenia. Upublicznienie repo nie jest obejściem: jego treść to mapa dostępów do waszych danych |
| Apply jest single-flight | `concurrency` w `apply.yml`, bez `cancel-in-progress` | przegrany apply pada na `Error 400: eTag … does not match` — **nic nie ginie po cichu**, ale ~80-100% nałożonych w czasie przebiegów wymaga ponowienia z ręki. Argumentem jest NIEZAWODNOŚĆ, nie cicha utrata reguł (DEC-6, skorygowane pomiarem 2026-08-07) |
| Projekt z `policy.yaml` §`control_plane_projects` **nie wchodzi** do perimetru | reguła OPA w `onboarding.rego` (furtka: `control_plane_exception` w pliku członka) | **jedyne złamanie, którego `git revert` NIE COFA.** Bucket stanu leży w projekcie administracyjnym perimetru; w konfiguracji egzekwowanej konto apply traci dostęp do własnego stanu, bo woła z GitHub Actions — spoza granicy. Apply rewertu też potrzebuje stanu, więc pętli nie da się przerwać pipeline'em: wychodzi z niej człowiek z uprawnieniami org-level, ręcznie na żywej polityce |
| Lista `control_plane_projects` **opisuje rzeczywistość**, a nie sama siebie | `tools/control_plane_check.py` — offline w `validate.yml` (backend ↔ `contract.state_bucket`, `monitoring.project_id` ↔ lista, `iam-bootstrap/terraform.tfvars` ↔ lista), `--live` w `plan.yml` (właściciel bucketa stanu z API) | bramka wyżej chroni to, co NA LIŚCIE. Drugi bucket stanu, osobny projekt monitoringu albo backend przeniesiony jedną linijką w `versions.tf` wchodzą do perimetru jak zwykły wniosek, a bramka wygląda przy tym na uzbrojoną — chroni zbiór, który tylko wygląda na pełny. Dlatego numer projektu bucketa stanu musi być na liście **w obu formach**: API odpowiada NUMEREM |
| Sekcja `control_plane_projects` **istnieje** (może być pusta) | `required` w `schemas/policy.schema.json` + asercja w selfteście | brak sekcji i pusta lista dają ten sam skutek — bez `required` bramkę rozbraja się „sprzątaniem" nieużywanego pola, a różnica między „zdecydowaliśmy, że nie ma takich projektów" a „nikt o tym nie pomyślał" znika z diffu |
| Zakaz `ANY_IDENTITY` / `method: "*"` / `resources: ["*"]` | `perimeter.rego` na plan-JSON | reguła przestaje cokolwiek ograniczać, a wygląda tak samo (DEC-3). **Jedyny wyjątek: `ingress_to.resources = ["*"]` w regule baseline** — rozpoznawanej po ZGODNOŚCI TREŚCI z `policy.yaml` (tytuł + tożsamości + usługi + selektory) i tylko z niepustym `sources`, nigdy po nazwie (DEC-11). Egressowe `["*"]` nie ma wyjątku: znaczy „poza perimetrem" |
| Cel reguły baseline nie zależy od członkostwa (`resources = ["*"]`) | `renderer.tftest.hcl` §10a + selftest (odcisk reguły przed/po dodaniu członka) | `ingress_to.resources` jest **`ForceNew`**, więc lista rosnąca z każdym członkiem oznaczała REPLACE obu reguł baseline przy każdym wniosku — w konfiguracji egzekwowanej okno bez reguły skanera dla wszystkich promowanych naraz. Zmierzone: `Plan: 4 to add, 1 to change, 2 to destroy` (DEC-11) |
| Każda tożsamość ma poprawny **kształt** (prefiks typu + domena) | `perimeter.rego` na plan-JSON; **istnienie** konta osobno, w `preflight_check.sh --identity` | ACM waliduje tożsamości po swojej stronie i odrzuca **całą** zmianę (`invalid or non-existent`), więc literówka w adresie wywraca apply po review, na obiekcie org-plane — i wygląda jak problem z uprawnieniami. Wzorzec domeny jest świadomie luźny: bramka odrzucająca konto domyślne (`developer.`, `appspot.`) blokowałaby poprawny onboarding |
| Kontrakt buduje się polami, nigdy `jsonencode(<zbiorcze>)` | `contract.tf` + test w selfteście | kontrakt zamienia się w drugą kopię stanu (DEC-8) |
| Kontrakt i stan w **różnych** bucketach | `precondition` w `contract.tf` | jeden błąd w IAM odsłania pełną mapę granicy (DEC-8) |
| Obie publikacje kontraktu (bucket + asset release'u) wychodzą z **jednego kroku apply** | `test_kontrakt_dwie_publikacje` w selfteście (parsuje kroki `apply.yml`) | dwa kroki = dwa wyzwalacze i dwa odczyty stanu, więc dwie kopie cicho się rozjadą, a konsument nie ma jak zauważyć, że czyta starszą (DEC-8) |
| Zakaz komendy commitującej całą konfigurację dry-run | guard w `validate.yml` | promocja WSZYSTKICH członków jednym wywołaniem, bez czego cofnąć (`docs/3` §A) |
| Akcje przypięte 40-znakowym SHA | guard w `validate.yml` + Dependabot | kto kontroluje tag, kontroluje pipeline mający prawo zmieniać granicę organizacji |
| Warstwa IAM Deny jest **odczytywana**, nie zakładana | rola `vpcScDenyReader` + `manage_deny_policy` w `iam-bootstrap`, `tools/deny_check.sh`, testy trzech werdyktów w selfteście | `iam.denypolicies.*` nie należy do żadnej roli org-admina, a API na brak uprawnienia odpowiada tym samym `403` co na brak zasobu — więc bez tej roli zdanie „guardrail stoi" jest nieweryfikowalne, a `terraform plan` pokazuje `1 to add` niezależnie od stanu faktycznego. Zapisu tej warstwy **nie da się** zawęzić: `create`/`update`/`delete` mają `customRolesSupportLevel = NOT_SUPPORTED` i niesie je wyłącznie `roles/iam.denyAdmin` |

## Placeholdery — wszystko, co trzeba podmienić

`grep -rn '<[A-Z_]*>' .` znajduje komplet. Znaczenie:

| Token | Co wpisać |
|---|---|
| `<ORG_ID>` | numer organizacji Google Cloud |
| `<ACCESS_POLICY_NUMBER>` / `<POLICY_ID>` / `<POLICY>` | numer org-level access policy (`gcloud access-context-manager policies list`) |
| `<STATE_BUCKET>` | bucket stanu Terraform (versioning + soft-delete, **bez** retention-lock) |
| `<CONTRACTS_BUCKET>` | bucket kontraktu — **musi być inny** niż bucket stanu |
| `<MONITORING_PROJECT>` | projekt, w którym powstają metryki i alerty perimetru |
| `<SCANNER_SA>` / `<SCANNER_PROJECT>` | konto serwisowe skanera bezpieczeństwa dla reguły `baseline_ingress` |
| `<ORG>` / `<REPO>` | organizacja i nazwa repozytorium na GitHubie (`attribute_condition` WIF pinuje je oba) |
| `<PROJEKT>` / `<PROJ>` / `<NUM>` / `<ID>` | projekt i jego numer w przykładach komend |
| `<PERIMETER>` / `<NAZWA>` | nazwa techniczna perimetru (niezmienialna po utworzeniu) |
| `<FOLDER_SANDBOX>` | folder pod wariant testowy ze scoped policy (`docs/2` §4a) |
| `<SHA_WYDANIA>` | tag/SHA paczki bramek przypinanej przez repozytoria zespołów |
| `@your-org/*` | realne zespoły GitHuba w `CODEOWNERS` |
| zakresy IP w `access-levels/corp.yaml` | korporacyjne zakresy — w szablonie są adresy TEST-NET z RFC 5737 |

Nazwy przykładowe (`example-division`, `prj-example-*`, `000000000000`, `RITM0000001`, `example.com`) są
**jawnie fikcyjne i spójne w całym repo**. Jeśli zobaczysz nazwę wypadającą z tej konwencji, to jest błąd —
guard `test_samodzielnosc` w selfteście pilnuje tego przy każdym przebiegu.

## Rzeczy, które wyglądają na błąd, a są decyzją

- **Szablony w `template/` mają sufiks `.example` i katalog `github/` bez kropki.** To celowe: dopóki tam leżą,
  są martwym tekstem, którego żaden linter, pre-commit ani git nie uruchomi. Ożywia je `install.sh`.
- **Członkowie siedzą w JEDNYM `perimeter/projects.yaml`, jako LISTA, a klucz członka bierze się z treści**
  (`<division>-<project_id>`). Ten ciąg jest ADRESEM ZASOBU W STANIE Terraforma — wcześniej brała go nazwa
  pliku i dlatego przejście na jeden plik nie miało w planie ani jednego `destroy`. Nie „upraszczaj" klucza
  do samego `project_id`: to `destroy` + `create` na każdej granularnej regule ACM (DEC-11, DEC-12).
- **Lista, a nie mapa — bo duplikat klucza mapy jest CICHY.** Zmierzone: `yamldecode` (TF 1.15.5)
  i `yaml.safe_load` biorą przy duplikacie klucza OSTATNI wpis i nie mówią nic. Na liście ten sam przypadek
  wywraca plan (`Duplicate object key`). Przy pliku wspólnym duplikat jest normalnym wynikiem scalenia.
- **W `perimeter/projects.yaml` NIE MA KOMENTARZY i nie da się ich tam włożyć.** Plik jest w postaci
  kanonicznej (`yaml.safe_dump`, bramka w `validate.yml`), a `safe_dump` komentarzy nie zna — pierwszy zapis
  bota skasowałby je bez śladu. Uzasadnienie zmiany idzie w pole `change_ref` i w opis pull requesta.
- **Plik czytaj i zapisuj WYŁĄCZNIE przez `tools/projects_file.py`**, nigdy `yaml.safe_load` wprost. Tam
  siedzi strict loader, wyliczanie klucza, wykrywanie duplikatów i dopisywanie wpisu bez przepisywania pliku.
- **Sharding po dywizji** (`perimeter/projects/<dywizja>.yaml` + renderer na `**/*.yaml`) zostaje jako
  zapisane wyjście, gdyby self-service per dywizja stał się wymaganiem — ale to zmiana adresów w stanie,
  więc idzie osobnym PR-em z `moved{}`. Patrz `docs/6` i DEC-12.
- **Członek w konfiguracji dry-run zostaje tam po promocji.** Dry-run to „proponowana przyszła konfiguracja",
  nie „poczekalnia". Dzięki temu promocja jest czysto addytywna i nie ma momentu, w którym projekt nie należy
  do żadnej konfiguracji.
- **Reguły `baseline_ingress` nie są profilem.** Profil trzeba wybrać; baseline obowiązuje każdego. Pierwszy
  zespół, który zapomniałby wybrać profil skanera, wypadłby ze skanowania dokładnie w momencie promocji.
- **`iam-bootstrap/` to osobny stack z osobnym stanem.** Applikuje go zespół IAM, nie ten pipeline: kod
  nadający uprawnienia nie może być stosowany przez tożsamość, która z nich korzysta. „Osobny stan" znaczy
  **zdalny backend pod własnym prefiksem**, rozłącznym z tym, który `main.tf` oddaje kontom CI: warunek IAM
  na buckecie to `startsWith`, więc wspólny (albo tylko *prawie* rozłączny) prefiks daje pipeline'owi
  perimetru prawo zapisu do stanu, z którego biorą się jego własne uprawnienia.
- **Reguła egress do zasobu zewnętrznego wygląda inaczej niż każda inna: `permissions`, nie `methods`.**
  To nie jest niekonsekwencja katalogu profili, tylko wymóg API — zmierzony, nie wyczytany. Z ustawionym
  `external_resources` perimetr odrzuca selektory metod (`With 'external_resources' set, MethodSelector is
  only allowed to have permission`), a z uprawnień przyjmuje **dokładnie jedno**: `externalResource.read`.
  Prawdziwe uprawnienia IAM BigQuery (`bigquery.jobs.create`, `bigquery.tables.getData`) są odrzucane, mimo że
  figurują w `gcloud access-context-manager supported-services describe`; `externalResource.read` w tym
  katalogu nie figuruje. Katalog usług kłamie tu w obie strony, dlatego `check_supported_services.py`
  świadomie pomija operacje z `permissions`, a wartości pilnuje reguła OPA zbudowana z pomiaru.
- **Reguła egress nie przyjmuje `access_levels_from` — mimo że API to potrafi.** `egressFrom.sources.accessLevel`
  i `sourceRestriction` istnieją w schemacie providera; ten renderer ich **nie składa**. Dopóki nie składa,
  przyjęcie pola oznaczałoby deklarację „wymagaj sieci korporacyjnej" cicho zamienioną na regułę autoryzującą
  z dowolnego miejsca — zmierzone: schema, OPA i guard budżetu **przepuszczały i liczyły** to pole, a
  `egress_from.sources` w planie zostawało puste. Zamknięte na trzech warstwach (schema rozdzielona per
  kierunek, reguła OPA, asercja `terraform test`), każda mówi, co zrobić przy realnej potrzebie.
- **Testy są w połowie negatywne.** Bramka, która nigdy nie odrzuca, przechodzi każdy test pozytywny
  i nie chroni niczego. Dodając bramkę, dodaj też przypadek, w którym ma PAŚĆ.
- **Bramka ludzka na apply jest opisana jako warstwa OSOBNA i warunkowa, a nie jako fundament.** Kusi, żeby
  napisać „apply czeka na człowieka" i uznać sprawę za zamkniętą — ale wymagani recenzenci to płatna funkcja
  GitHuba, a materiał ma działać także tam, gdzie jej nie ma. Dlatego komentarze mówią, co ta warstwa daje
  i czego brak, gdy jej nie ma, zamiast twierdzić, że jest. Odstępstwo (brak recenzenta) zapisuje się
  z powodem, listą kontroli maszynowych, które zostają, i jawnym zdaniem, czego one **nie** dają — pary oczu
  na TREŚCI zmiany. Zamiana apply na ręczny `workflow_dispatch` nie jest tu zamiennikiem: to pauza, nie
  kontrola, a zatwierdzenie przez tę samą osobę minutę po merge'u nie dokłada niczyjego osądu.

## Jak zweryfikować, że odtworzenie się udało

```bash
python3 selftest/selftest.py          # rozpakowuje starter do katalogu tymczasowego i uruchamia realne bramki
```

Wymaga na PATH: `terraform` (1.15.5), `conftest`, `tflint`, `python3` z `pyyaml`; opcjonalnie `actionlint`
i `check-jsonschema` (ich brak daje SKIP z nazwą, nigdy ciche zielone). Oczekiwany wynik: **270/270**.

Bez `tflint` na PATH przebieg kończy się na **267/267** i wypisuje SKIP z nazwą — trzy asercje
(`--init` plus lint obu stacków) po prostu się nie wykonują. Liczba niższa niż 270 nie jest błędem
startera, tylko informacją, czego w tym środowisku nie sprawdzono.

Sam skan samodzielności (bez terraforma i conftesta, sam Python) da się uruchomić na dowolnej ścieżce —
przydaje się tam, gdzie materiał jest publikowany razem z innymi katalogami:

```bash
python3 selftest/skan_samodzielnosci.py . ../inny-katalog
```

Selftest **nie** sprawdza mechaniki GitHuba (environments, OIDC, required reviewers) ani realnego API Google.
Pierwszą warstwę pokrywa `actionlint`, drugą dopiero pierwszy `plan` na docelowej organizacji. Sprawdza za to
zastępczo, że `tools/bootstrap_github.sh` **czyta te ustawienia z powrotem z API** — bo skoro bramki nie da
się zobaczyć stąd, to przynajmniej narzędzie, które ją zakłada, ma odróżniać „wysłaliśmy PUT" od „jest".

## Czego tu nie ma

Świadome pominięcia są wypisane w [`README.md`](README.md) §„Świadome pominięcia" — razem z powodem, dla
którego każde z nich jest pominięciem, a nie przeoczeniem. Zanim dołożysz pole do renderera, sprawdź, czy nie
jest tam już opisane jako odrzucone; kolejność jest odwrotna niż zwykle — najpierw przypadek użycia, potem knob.
