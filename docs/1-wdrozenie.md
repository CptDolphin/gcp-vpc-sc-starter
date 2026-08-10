# Wdrożenie startera — kolejność ma znaczenie

Etapami, bo przy czerwonym CI ma być wiadomo **która** bramka padła. Każdy etap kończy się stanem, w którym
repo jest spójne i nic nie jest zepsute.

## Etap 0 — rozpakowanie i placeholdery

```bash
./install.sh /sciezka/do/repo
```

Podmień (grep po `<` znajdzie wszystkie):

| Placeholder | Gdzie | Co wpisać |
|---|---|---|
| `<ORG_ID>` | `perimeter/policy.yaml` | numer organizacji GCP |
| `<ACCESS_POLICY_NUMBER>` | `perimeter/policy.yaml` | numer org-level access policy (`gcloud access-context-manager policies list`) |
| `<STATE_BUCKET>` | `terraform/versions.tf` **oraz** `iam-bootstrap/versions.tf` | bucket stanu (versioning + soft-delete, **bez** retention-lock). Ta sama nazwa w obu miejscach, ale **prefiksy różne** (`vpc-sc/perimeter` vs `vpc-sc/iam-bootstrap`) — konta CI perimetru mają zapis wyłącznie na swoim prefiksie i nie mogą nadpisać stanu stacku, który nadaje im uprawnienia |
| `@your-org/*` | `.github/CODEOWNERS` | realne zespoły GitHub |
| `commit: 000…0` | `.starter-sync` | SHA commita startera, z którego rozpakowałeś materiał (`git -C <starter> rev-parse HEAD`). Bez tego `starter-drift` nie ma z czym porównać i pada — celowo: repo, o którym nie wiadomo, jaką wersję bramek uruchamia, nie jest „zsynchronizowane" |
| zakresy IP | `perimeter/access-levels/corp.yaml` | korporacyjne zakresy (w szablonie są adresy TEST-NET z RFC 5737) |

W `perimeter/policy.yaml` zostaw `manage_skeleton: false`, jeśli perimetr **już istnieje** — patrz
[`4-brownfield-import.md`](4-brownfield-import.md).

## Etap 1 — bramki bez chmury (nic jeszcze nie dotyka GCP)

```bash
./install.sh /sciezka --only validate.yml
pre-commit install && pre-commit run --all-files
```

Efekt: PR-y są sprawdzane schematem, regułami OPA i budżetem atrybutów. **Zero uprawnień w GCP** na tym
etapie — to celowe: chcemy udowodnić, że kształt danych jest poprawny, zanim poprosimy o dostępy.

**Udowodnij, że bramka realnie odrzuca.** Bramka, której nikt nie widział przy pracy, jest deklaracją.
Otwórz PR z celowo złym wpisem i sprawdź, że CI go zatrzymuje:

```bash
cp perimeter/members/example-*.yaml perimeter/members/gate-test-prj-gate-test.yaml
# w skopiowanym pliku ustaw:
#   division: gate-test
#   project_id: prj-gate-test
#   stage: enforced          <-- promocja bez ani jednego dnia w dry-run
#   dry_run_since: <dzisiejsza data>
git checkout -b test/gate-check && git add perimeter/members/gate-test-prj-gate-test.yaml
git commit -m "test: celowo zły wpis — bramka ma go odrzucić" && git push -u origin test/gate-check
```

Oczekiwany wynik: job `declarations` **czerwony**, z komunikatem o promocji przed oknem obserwacji i o braku
raportu naruszeń. Zamknij PR bez merge'a i skasuj gałąź.

## Etap 2 — dostępy i WIF

Zamów dostępy według [`2-uprawnienia-i-wif.md`](2-uprawnienia-i-wif.md) (jest tam gotowa lista do wklejenia
w ticket). Zanim pójdziesz dalej, zweryfikuj **read-only**:

```bash
gcloud access-context-manager perimeters list --policy=<ACCESS_POLICY_NUMBER>
```

Jeśli to nie działa, `plan` też nie zadziała — i lepiej dowiedzieć się o tym teraz niż z czerwonego CI.

## Etap 3 — plan (nadal nic nie zmieniamy)

```bash
./install.sh /sciezka --only plan.yml
gh variable set WIF_PROVIDER --body "projects/<NUM>/locations/global/workloadIdentityPools/github-actions/providers/github"
gh variable set PLAN_SERVICE_ACCOUNT --body "sa-vpcsc-plan@<proj>.iam.gserviceaccount.com"
```

Pierwszy `plan` na pustym `members/` musi pokazać **zero zmian** (brownfield) albo utworzenie samego
szkieletu (greenfield). Jeśli pokazuje coś więcej, zatrzymaj się i przeczytaj [`4-brownfield-import.md`](4-brownfield-import.md).

## Etap 4 — apply za bramką człowieka

```bash
./install.sh /sciezka --only apply.yml
gh variable set APPLY_SERVICE_ACCOUNT --body "sa-vpcsc-apply@<proj>.iam.gserviceaccount.com"
```

W GitHubie: utwórz environment **`perimeter-apply`** z *required reviewers* (sieć + security) i osobny
**`break-glass`** z innym zestawem osób. Obu ogranicz **politykę gałęzi** do gałęzi domyślnej. Ochrona
gałęzi `main`: wymagane statusy `validate` i `plan`, wymagane review CODEOWNERS, zakaz force-push.
Wszystko to robi `tools/bootstrap_github.sh` — i, co ważniejsze, **czyta wynik z powrotem**.

> Environment jest bramką **niezależną** od CODEOWNERS: nawet zmergowany PR nie zaaplikuje się, dopóki
> człowiek nie zatwierdzi uruchomienia. To jedyne miejsce, w którym „merge" i „zmiana granicy" są rozdzielone.

**Zweryfikuj, że bramka istnieje — nie zakładaj tego po wysłaniu ustawienia:**

```bash
gh api repos/<ORG>/<REPO>/environments/perimeter-apply --jq '.protection_rules'
gh api repos/<ORG>/<REPO>/environments/perimeter-apply/deployment-branch-policies --jq '.branch_policies[].name'
```

Pierwsza komenda ma pokazać `required_reviewers`, druga — samą gałąź domyślną. Rozróżnij dwa braki, bo
ważą inaczej:

| Czego brak | Co to znaczy naprawdę | Co robić |
|---|---|---|
| polityka gałęzi (`branch_policies` puste, `deployment_branch_policy: null`) | **dziura**, nie odstępstwo: `principalSet` konta apply pinuje samą nazwę environment, więc job z `environment: perimeter-apply` na **dowolnej** gałęzi dostaje tożsamość zapisującą | ustaw natychmiast — działa na każdym planie GitHuba |
| wymagani recenzenci (`protection_rules: []`) | funkcja płatna; na części planów prywatnych API ją odrzuca (`Please ensure the billing plan supports…`) | jeśli plan jej nie ma: **zapisz świadome odstępstwo z powodem** i wymień kontrole, które zostają — polityka gałęzi, `principalSet` na environment, IAM Deny na kasowaniu, bramki OPA uruchamiane **ponownie** na planie w apply, `git revert` + apply jako droga wycofania. Zaznacz też, czego one NIE dają: pary oczu na treści zmiany |

Nie zastępuj wtedy apply ręcznym `workflow_dispatch` w przekonaniu, że to przywraca bramkę: pauza to nie
kontrola, a gdy „zatwierdza" ta sama osoba, która zmergowała, w tej samej minucie — jest to ta sama para
oczu w innym oknie przeglądarki. Jeśli w waszym środowisku bramka ludzka istnieje, **używajcie jej**;
odstępstwo opisane wyżej jest wyjątkiem dla środowisk, w których jej po prostu nie ma.

## Etap 5 — pierwszy członek, zawsze w dry-run

Dopiero teraz podłącz `intake.yml` (i integrację ServiceNow). Pierwszy członek wchodzi ręcznym PR-em, żeby
zobaczyć cały przepływ bez zmiennej „czy bot dobrze wypełnił plik":

```bash
cp perimeter/members/example-*.yaml perimeter/members/<dywizja>-<projekt>.yaml
# uzupełnij, zostaw stage: dry-run
```

Po apply sprawdź, że projekt jest w konfiguracji dry-run i **nie** w egzekwowanej:

```bash
terraform -chdir=terraform output members_dry_run_only
terraform -chdir=terraform output members_enforced   # ma być pusta lista
```

## Etap 6 — obserwacja i dopiero potem enforce

Uruchom `violations-report.yml` (ręcznie albo poczekaj na harmonogram). Promocję do enforced robi się
osobnym PR-em po czystym oknie — procedura w [`3-runbook-promocja-i-break-glass.md`](3-runbook-promocja-i-break-glass.md).

**Nie skracaj okna „bo zielono od trzech dni".** Dry-run łapie tylko przepływy, które faktycznie zaszły;
miesięczny batch albo kwartalny audyt złamią się dopiero po promocji.

## Etap 7 — automatyzacja rutyny

Na końcu, gdy przepływ jest przetestowany: `drift.yml`, `expiry-sweep.yml`, `break-glass.yml` i auto-merge
dla ścieżki niskiego ryzyka (dodanie do dry-run, przypisanie istniejącego profilu, offboarding).

## FAQ: czy perimetr może wisieć na folderze?

Nie. Rodzicem *access policy* jest zawsze organizacja (`parent = organizations/<ORG_ID>`), a członkami
perimetru są **projekty** (adresowane numerem) i sieci VPC. Folderu nie da się dodać jako członka — dlatego
„chronimy folder X" oznacza w praktyce „wyliczamy projekty pod folderem X i dodajemy każdy z nich", i dlatego
w ogóle potrzebujemy automatu, a nie listy w arkuszu.

Folder pojawia się w VPC-SC w jednym miejscu: jako `scopes` **scoped policy** (`scopes = ["folders/123"]`).
Taka polityka nadal wisi na organizacji, ale jej perimetry mogą obejmować wyłącznie zasoby spod tego folderu,
a administrację można delegować na samą politykę (limit: 1 polityka org-level + do 50 scoped). Gdyby wytyczna
brzmiała „każda dywizja rządzi swoim", to byłaby właściwa odpowiedź — i wtedy nie istniałby problem wyścigu
opisany w DEC-6, bo każdy zespół pisałby do własnego obiektu.

Wytyczna brzmi jednak **jeden perimeter** (DEC-1), więc ta ścieżka jest świadomie zamknięta, a jej
konsekwencją jest cała reszta konstrukcji: jeden mutator, trzy kanały wejścia, kontrakt zamiast dostępu.

## Uruchomienie z laptopa (ścieżka testowa)

Pipeline uwierzytelnia się przez WIF i tam nic dodatkowego nie trzeba. Człowiek uruchamiający `plan`/`apply`
lokalnie — czyli ścieżka scoped-policy z [`2-uprawnienia-i-wif.md`](2-uprawnienia-i-wif.md) §4a — musi wskazać
projekt rozliczeniowy, inaczej API Access Context Managera odbija:

```
Error 403: ... The accesscontextmanager.googleapis.com API requires a quota project, which is not set by default.
```

Samo `gcloud auth application-default set-quota-project` **nie wystarcza** — provider `google` podnosi to
dopiero z `user_project_override`:

```bash
export USER_PROJECT_OVERRIDE=true
export GOOGLE_BILLING_PROJECT=<projekt-z-wlaczonym-accesscontextmanager>
```

Ten sam projekt musi mieć włączone `accesscontextmanager.googleapis.com` i podpięte konto rozliczeniowe.

## Pierwszy apply uruchom DWA RAZY

`google_logging_metric` powstaje od razu, ale do Cloud Monitoring propaguje się **do 10 minut**, więc alerty
oparte na tych metrykach padają przy pierwszym przebiegu:

```
Error 404: Cannot find metric(s) that match type = "logging.googleapis.com/user/vpcsc/violations_enforced".
If a metric was created recently, it could take up to 10 minutes to become available.
```

To propagacja po stronie API — `depends_on` jej nie rozwiązuje. Drugi apply przechodzi. Sekcja `monitoring`
jest opcjonalna, więc alternatywą jest pominięcie jej przy bootstrapie i dołożenie osobnym PR-em.
