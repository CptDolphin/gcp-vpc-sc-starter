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
git checkout -b test/gate-check
# dopisz do listy `members:` w perimeter/projects.yaml drugi wpis — skopiuj istniejący i podmień:
#   division: gate-test
#   project_id: prj-gate-test
#   project_number: "123456789012"
#   stage: enforced          <-- promocja bez ani jednego dnia w dry-run
#   dry_run_since: <dzisiejsza data>
git add perimeter/projects.yaml
git commit -m "test: celowo zły wpis — bramka ma go odrzucić" && git push -u origin test/gate-check
```

Drugi wariant tej samej próby, wart osobnego przebiegu, bo dotyczy bramki, która przy pliku na projekt nie
mogła istnieć: **skopiuj istniejący wpis bez zmiany `project_id`**. Oczekiwany wynik to czerwony job
`declarations` z komunikatem o duplikacie — a gdyby ktoś usunął reguły OPA, `terraform plan` i tak wywala się
na `Duplicate object key`. Dwie warstwy, dwa różne komunikaty, obie do zobaczenia.

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

> **Ochrona gałęzi domyślnej jest PREREKWIZYTEM, nie ozdobą — ale nie tym, którym była kiedyś.** Bramki
> (schema, OPA, budżet atrybutów, bramki żywe, pre-flight) biegną dziś na OBU torach: na pull requeście
> i u mutatora (DEC-16, DEC-24), więc push prosto na gałąź domyślną **przechodzi przez nie tak samo**.
> To była świadoma zmiana, bo ochrona gałęzi na repozytorium prywatnym bywa funkcją płatną — a bramka,
> której istnienie zależy od planu cenowego, nie jest bramką. Czego push prosto na gałąź nie przechodzi,
> to **review**: CODEOWNERS, druga para oczu i opis zmiany. Bez ochrony każde poświadczenie
> z prawem zapisu do tego repozytorium (CI, integracja ticketowa, token kanału wejściowego) jest ścieżką
> do zmiany granicy organizacji bez żadnej bramki. Dlatego kanał dywizji jedzie `workflow_dispatch`-em
> na `actions: write` — token, który nie ma prawa zapisu, nie może tej ścieżki użyć — a `bootstrap_github.sh`
> **kończy się błędem**, gdy odczyt z API ochrony nie widzi (`--no-branch-protection "<powód>"` = świadome
> odstępstwo).

> Environment jest bramką **niezależną** od CODEOWNERS: nawet zmergowany PR nie zaaplikuje się, dopóki
> człowiek nie zatwierdzi uruchomienia. Rozdziela „merge" od „zmiany granicy" dla **każdego** apply — i to
> jest jego zaleta oraz jego koszt (patrz niżej). Drugie takie rozdzielenie, węższe i działające na każdym
> planie, robi **bramka promocji** (DEC-17): zatrzymuje wyłącznie ten apply, który zacząłby egzekwować
> granicę wobec kogoś nowego. Nie zastępują się nawzajem — recenzent to druga tożsamość, bramka promocji
> to drugi świadomy akt w momencie skutku.

**Zweryfikuj, że bramka istnieje — nie zakładaj tego po wysłaniu ustawienia:**

```bash
gh api repos/<ORG>/<REPO>/environments/perimeter-apply --jq '.protection_rules'
gh api repos/<ORG>/<REPO>/environments/perimeter-apply/deployment-branch-policies --jq '.branch_policies[].name'
gh api repos/<ORG>/<REPO>/branches/main/protection --jq '.required_status_checks.contexts'
```

Pierwsza komenda ma pokazać `required_reviewers`, druga — samą gałąź domyślną. Rozróżnij dwa braki, bo
ważą inaczej:

| Czego brak | Co to znaczy naprawdę | Co robić |
|---|---|---|
| polityka gałęzi (`branch_policies` puste, `deployment_branch_policy: null`) | **dziura**, nie odstępstwo: `principalSet` konta apply pinuje samą nazwę environment, więc job z `environment: perimeter-apply` na **dowolnej** gałęzi dostaje tożsamość zapisującą | ustaw natychmiast — działa na każdym planie GitHuba |
| **ochrona gałęzi domyślnej** (`403` albo `404` na `branches/main/protection`) | **prerekwizyt**: bez niej bramki treści są omijalne pushem, a apply rusza z tego samego miejsca. Na darmowym planie dla repo prywatnego API odpowiada `403 Upgrade to GitHub Pro or make this repository public to enable this feature.` | plan GitHuba z ochroną gałęzi dla repo prywatnych **albo** zapisane odstępstwo (`bootstrap_github.sh --no-branch-protection "<powód>"`). Upublicznienie repo perimetru **nie jest** obejściem — jego treść to mapa dostępów do waszych danych |
| wymagani recenzenci (`protection_rules: []`) | funkcja płatna; na części planów prywatnych API ją odrzuca (`Please ensure the billing plan supports…`) | jeśli plan jej nie ma: **zapisz świadome odstępstwo z powodem** i wymień kontrole, które zostają — polityka gałęzi, `principalSet` na environment, **bramka promocji na ścieżce apply (DEC-17, działa na każdym planie)**, IAM Deny na kasowaniu, bramki OPA uruchamiane **ponownie** na planie w apply, `git revert` + apply jako droga wycofania. Zaznacz też, czego one NIE dają: pary oczu na treści zmiany |

Nie zastępuj wtedy **całego** apply ręcznym `workflow_dispatch` w przekonaniu, że to przywraca bramkę:
pauza przed każdym apply to nie kontrola, tylko przycisk, który po tygodniu klika się bez czytania —
a gdy „zatwierdza" ta sama osoba, która zmergowała, w tej samej minucie, jest to ta sama para oczu
w innym oknie przeglądarki. Jeśli w waszym środowisku bramka ludzka istnieje, **używajcie jej**;
odstępstwo opisane wyżej jest wyjątkiem dla środowisk, w których jej po prostu nie ma.

**Czym różni się od tego bramka promocji (DEC-17), która zostaje włączona zawsze.** Trzema rzeczami, i to
one decydują, czy pauza jest czytana:
* **zakresem** — staje wyłącznie przed apply, który zaczyna komuś ODMAWIAĆ ruchu; przy pozostałych
  przebiegach nie istnieje, więc nie zamienia się w rutynę;
* **treścią zgody** — nie pyta „zatwierdzasz?", tylko wymaga wypisania **kogo** ten przebieg odetnie;
  zbiór musi być równy oczekującym promocjom, więc zgoda „na wszystko" jest niewyrażalna, a zgoda
  nieaktualna (ktoś dołożył drugą promocję) zatrzymuje przebieg ponownie;
* **tym, czego nie udaje** — nie jest przeglądem TREŚCI zmiany i nie zastępuje CODEOWNERS ani recenzenta.
  Odpowiada na jedno pytanie: czy człowiek świadomie wybrał ten moment na odcięcie ruchu.

## Etap 5 — pierwszy członek, zawsze w dry-run

Dopiero teraz podłącz `intake.yml` (i integrację ServiceNow). Pierwszy członek wchodzi ręcznym PR-em, żeby
zobaczyć cały przepływ bez zmiennej „czy bot dobrze wypełnił plik":

```bash
# dopisz wpis na KOŃCU listy `members:` w perimeter/projects.yaml; zostaw stage: dry-run.
# Kolejność nic nie znaczy (klucz członka bierze się z `division` + `project_id`), a dopisanie na końcu
# daje najmniejsze okno konfliktu — DEC-12.
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

## Etap 8 — obserwator poza tą organizacją

Wszystko, co postawiłeś do tej pory, obserwuje samo siebie **z wnętrza jednego projektu GCP**. Ostatni krok
wyprowadza jeden sygnał na zewnątrz, żeby skasowanie tego projektu nie było zdarzeniem bez świadków:

```bash
# Check u dostawcy dead-man's-switch: period 1h, grace 2h (= `watchdog_absent_seconds`), Z KANAŁEM
# POWIADOMIEŃ. Potem URL pingu jako sekret repozytorium — wartością z pliku, nie z argumentu.
gh secret set DMS_PING_URL --repo <owner>/<repo> < /sciezka/do/pliku-z-url
gh workflow run watch.yml --repo <owner>/<repo>
```

Przebieg ma zameldować w podsumowaniu `ping wyslany`. Procedura, triage i test negatywny:
[`7-alerty.md#dms-zewnetrzny`](7-alerty.md#dms-zewnetrzny).

**Etap jest opcjonalny w sensie technicznym i obowiązkowy w sensie operacyjnym.** Bez sekretu `watch`
chodzi dalej i głośno melduje, że warstwa jest nieuzbrojona — nie ma cichego wariantu „prawie zrobione".

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
