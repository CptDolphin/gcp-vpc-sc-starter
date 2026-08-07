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
| Nowy członek zawsze `stage: dry-run` | `render_member.py` + reguła OPA | wejście od razu do konfiguracji egzekwowanej odcina cudzą produkcję po merge'u (DEC-4) |
| Kanał wejściowy **nie nadpisuje** istniejącego pliku członka | `out.exists()` w `render_member.py` i `external-intake.yml` | powtórne zgłoszenie zapisałoby `stage: dry-run` na członku `enforced` — projekt traci ochronę PR-em wyglądającym na onboarding. Reguła OPA tego nie łapie: porównuje dwa PLIKI, a tu plik jest ten sam |
| Apply jest single-flight | `concurrency` w `apply.yml`, bez `cancel-in-progress` | dwa równoległe apply nadpisują się na polityce org-level (DEC-6) |
| Projekt z `policy.yaml` §`control_plane_projects` **nie wchodzi** do perimetru | reguła OPA w `onboarding.rego` (furtka: `control_plane_exception` w pliku członka) | **jedyne złamanie, którego `git revert` NIE COFA.** Bucket stanu leży w projekcie administracyjnym perimetru; w konfiguracji egzekwowanej konto apply traci dostęp do własnego stanu, bo woła z GitHub Actions — spoza granicy. Apply rewertu też potrzebuje stanu, więc pętli nie da się przerwać pipeline'em: wychodzi z niej człowiek z uprawnieniami org-level, ręcznie na żywej polityce |
| Sekcja `control_plane_projects` **istnieje** (może być pusta) | `required` w `schemas/policy.schema.json` + asercja w selfteście | brak sekcji i pusta lista dają ten sam skutek — bez `required` bramkę rozbraja się „sprzątaniem" nieużywanego pola, a różnica między „zdecydowaliśmy, że nie ma takich projektów" a „nikt o tym nie pomyślał" znika z diffu |
| Zakaz `ANY_IDENTITY` / `method: "*"` / `resources: ["*"]` | `perimeter.rego` na plan-JSON | reguła przestaje cokolwiek ograniczać, a wygląda tak samo (DEC-3) |
| Kontrakt buduje się polami, nigdy `jsonencode(<zbiorcze>)` | `contract.tf` + test w selfteście | kontrakt zamienia się w drugą kopię stanu (DEC-8) |
| Kontrakt i stan w **różnych** bucketach | `precondition` w `contract.tf` | jeden błąd w IAM odsłania pełną mapę granicy (DEC-8) |
| Obie publikacje kontraktu (bucket + asset release'u) wychodzą z **jednego kroku apply** | `test_kontrakt_dwie_publikacje` w selfteście (parsuje kroki `apply.yml`) | dwa kroki = dwa wyzwalacze i dwa odczyty stanu, więc dwie kopie cicho się rozjadą, a konsument nie ma jak zauważyć, że czyta starszą (DEC-8) |
| Zakaz komendy commitującej całą konfigurację dry-run | guard w `validate.yml` | promocja WSZYSTKICH członków jednym wywołaniem, bez czego cofnąć (`docs/3` §A) |
| Akcje przypięte 40-znakowym SHA | guard w `validate.yml` + Dependabot | kto kontroluje tag, kontroluje pipeline mający prawo zmieniać granicę organizacji |

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
- **`fileset(…, "*.yaml")` czyta tylko jeden poziom `members/`.** Sharding po zespole (`members/<zespół>/`)
  wymaga zmiany wzorca na `**/*.yaml` i klucza `for_each` na `replace(f, "/", "-")` — czyli zmiany adresów
  w stanie, więc idzie osobnym PR-em z `moved{}`. Patrz `docs/6`.
- **Członek w konfiguracji dry-run zostaje tam po promocji.** Dry-run to „proponowana przyszła konfiguracja",
  nie „poczekalnia". Dzięki temu promocja jest czysto addytywna i nie ma momentu, w którym projekt nie należy
  do żadnej konfiguracji.
- **Reguły `baseline_ingress` nie są profilem.** Profil trzeba wybrać; baseline obowiązuje każdego. Pierwszy
  zespół, który zapomniałby wybrać profil skanera, wypadłby ze skanowania dokładnie w momencie promocji.
- **`iam-bootstrap/` to osobny stack z osobnym stanem.** Applikuje go zespół IAM, nie ten pipeline: kod
  nadający uprawnienia nie może być stosowany przez tożsamość, która z nich korzysta.
- **Testy są w połowie negatywne.** Bramka, która nigdy nie odrzuca, przechodzi każdy test pozytywny
  i nie chroni niczego. Dodając bramkę, dodaj też przypadek, w którym ma PAŚĆ.

## Jak zweryfikować, że odtworzenie się udało

```bash
python3 selftest/selftest.py          # rozpakowuje starter do katalogu tymczasowego i uruchamia realne bramki
```

Wymaga na PATH: `terraform` (1.15.5), `conftest`, `tflint`, `python3` z `pyyaml`; opcjonalnie `actionlint`
i `check-jsonschema` (ich brak daje SKIP z nazwą, nigdy ciche zielone). Oczekiwany wynik: **138/138**.

Sam skan samodzielności (bez terraforma i conftesta, sam Python) da się uruchomić na dowolnej ścieżce —
przydaje się tam, gdzie materiał jest publikowany razem z innymi katalogami:

```bash
python3 selftest/skan_samodzielnosci.py . ../inny-katalog
```

Selftest **nie** sprawdza mechaniki GitHuba (environments, OIDC, required reviewers) ani realnego API Google.
Pierwszą warstwę pokrywa `actionlint`, drugą dopiero pierwszy `plan` na docelowej organizacji.

## Czego tu nie ma

Świadome pominięcia są wypisane w [`README.md`](README.md) §„Świadome pominięcia" — razem z powodem, dla
którego każde z nich jest pominięciem, a nie przeoczeniem. Zanim dołożysz pole do renderera, sprawdź, czy nie
jest tam już opisane jako odrzucone; kolejność jest odwrotna niż zwykle — najpierw przypadek użycia, potem knob.
