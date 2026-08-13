# Kanał ServiceNow — od formularza do reguły w perimetrze

Ten dokument opisuje **pierwszy i domyślny kanał wejścia**: dywizja wypełnia formularz w ServiceNow, networking
zatwierdza, automat otwiera PR. Zawiera specyfikację pozycji katalogu (pola, typy, walidacje), mapowanie pól na
plik członka, ścieżkę zatwierdzeń, obsługę błędów i sposób przetestowania całości **bez ServiceNow**.

Pozostałe dwa kanały: `docs/README.md` (ręczny PR architekta) i `contrib/README.md` (repozytorium zespołu).
Wszystkie trzy kończą się tym samym: **wpisem dopisanym do listy w `perimeter/projects.yaml`** i jednym
mutatorem (DEC-7). Kanał nie nadpisuje wpisu, który już opisuje ten projekt — pyta o `project_id` ORAZ
`project_number`, bo literówka w dywizji daje inny klucz przy tym samym projekcie (DEC-12).

---

## 1. Co ServiceNow robi, a czego NIE robi

ServiceNow jest **rejestrem zgody biznesowej i technicznej** — i tylko tym. Nie jest źródłem prawdy o stanie
perimetru i nie wywołuje API Google.

| Robi | Nie robi |
|---|---|
| zbiera wniosek w ustrukturyzowanej formie | nie zapisuje niczego w Access Context Managerze |
| przeprowadza approval (dywizja → networking → security dla profili `risk: high`) | **nie jest miejscem, w którym zgoda Security zaczyna obowiązywać** — tym jest wpis w `perimeter/policy.yaml` §`egress_approvals` (DEC-23) |
| wysyła `workflow_dispatch` do repo perimetru | nie tworzy projektów GCP ani sieci (patrz §7) |
| zostaje rekordem „kto poprosił, kto zatwierdził, kiedy" | nie zastępuje audytu w gicie — ten jest w historii PR-ów |

**Dlaczego nie ticket → API wprost.** Wywołanie API z ticketa oddaje trzy własności, bez których granica
bezpieczeństwa nie działa: historię *dlaczego* reguła istnieje (git blame na pliku), rollback równy
`git revert` oraz drift detection (bez zadeklarowanego stanu nie ma z czym porównać żywego). Ticket zostaje
przy tym, w czym jest dobry.

---

## 2. Pozycja katalogu — specyfikacja pól

Nazwy techniczne po lewej to nazwy zmiennych w Catalog Item; automat wysyła je 1:1 jako `inputs` zgłoszenia.

| Pole (techniczne) | Typ / kontrolka | Wymagane | Walidacja w SNOW | Uwaga |
|---|---|---|---|---|
| `division` | Choice (lista dywizji) | tak | wartość ze słownika, nie free-text | musi zgadzać się z właścicielem grupy z `owner_group`; bramka OPA porównuje to z `contributors.yaml` przy kanale `pr:` |
| `project_id` | String | tak | `^[a-z][a-z0-9-]{4,28}[a-z0-9]$` | ID projektu, **nie** nazwa wyświetlana |
| `project_number` | String (cyfry) | tak | `^[0-9]{6,20}$` | ACM adresuje projekty **numerem**; literówka cicho dodaje CUDZY projekt — dlatego pre-flight sprawdza parę ID↔numer |
| `owner_group` | Reference (Group) | tak | grupa musi istnieć | adresat raportu naruszeń i przeglądu po 6 miesiącach |
| `profiles` | Multi-row (lista) | tak, min. 1 | każdy wiersz: `name` + parametry | dozwolone nazwy = katalog `perimeter/profiles/` opublikowany w kontrakcie |
| `profiles[].params` | Key-value per wiersz | tak | klucze = `parameters` profilu | brak parametru → OPA odrzuca PR z nazwą brakującego pola |
| `use_case` | Multi-line text | tak | min. 40 znaków | nie trafia do YAML-a; zostaje w tickecie i w opisie PR-a jako uzasadnienie |
| `data_classification` | Choice | tak | słownik klasyfikacji danych organizacji | wejście do decyzji Security, nie jej egzekwowanie — bramka czyta `risk` profilu z katalogu, a nie to pole (DEC-23) |
| `requested_by` | Reference (User) | auto | — | wypełnia SNOW |

**Czego formularz świadomie NIE ma:**

- **`stage`** — bot zawsze zapisuje `dry-run`. Pole w formularzu byłoby zaproszeniem do „od razu enforced",
  czyli do włączenia blokowania bez okna obserwacji. Promocja to osobny PR (`docs/3-runbook…`).
- **surowych reguł ingress/egress** — dywizja wybiera **profil** i podaje jego parametry. Formularz z polem
  „wklej reguły" produkuje reguły, których nikt później nie umie ocenić (DEC-3).
- **`restricted_services`** — baseline jest własnością platformy, nie wniosku.

---

## 3. Ścieżka zatwierdzeń

```
wnioskodawca (dywizja)
      │
      ├─ approval 1: właściciel dywizji            (czy to nasz projekt i nasz koszt)
      │
      ├─ approval 2: networking team               (czy sieć projektu jest gotowa: PGA, DNS, restricted VIP)
      │
      └─ approval 3: security  ── TYLKO gdy któryś z profili ma `risk: high`
                                  (dziś: bq-omni-external-read — jedyny, który wypuszcza dane z GCP)
```

**Approval 3 jest ZAPISEM DECYZJI, a nie jej egzekwowaniem — i ta różnica kosztowała już jeden defekt.**
Do 2026-08-12 ten diagram był jedynym miejscem, w którym udział Security istniał: `perimeter/projects.yaml`
ma w CODEOWNERS wyłącznie zespół sieciowy, a pole `risk` nie sterowało niczym (`grep -rn "risk" terraform/
policy/ .github/` → publikacja w kontrakcie i enum w schemacie, zero bramek). Ticket z pominiętym approvalem
3 wjeżdżał do granicy tak samo gładko jak każdy inny.

Od DEC-23 zgoda Security **materializuje się jako wpis** w `perimeter/policy.yaml` §`egress_approvals` —
w pliku, którego Security jest właścicielem w CODEOWNERS — i wymienia członka, profil oraz **dokładne cele**,
z obowiązkową datą wygaśnięcia. Bez tego wpisu reguła OPA odrzuca wniosek, i robi to **także na ścieżce
apply**, więc nie da się jej ominąć commitem prosto na gałąź domyślną. Praktyczna konsekwencja dla ścieżki
ticketowej: po approvalu 3 ktoś z Security otwiera jednolinijkowy pull request do `policy.yaml`. To jest
jedyny krok ręczny, jaki ta zgoda dokłada — i jedyny, który zostawia po sobie ślad dający się zaudytować bez
dostępu do ServiceNow i bez dostępu do GitHuba.

Po ostatnim approvalu Flow Designer wysyła:

```http
POST https://api.github.com/repos/<ORG>/<REPO>/actions/workflows/intake.yml/dispatches
Authorization: Bearer <token integracji>
Content-Type: application/json

{
  "ref": "main",
  "inputs": {
    "snow_ticket": "RITM0000123",
    "division": "example-division",
    "project_id": "prj-example-vertex-prod",
    "project_number": "123456789012",
    "owner_group": "grp-example-division-cloud@example.com",
    "approved_by": "net-approver@example.com",
    "profiles": "[{\"name\":\"vertex-online-serving\",\"params\":{\"caller_identities\":[\"serviceAccount:sa-scoring@prj-example-app-prod.iam.gserviceaccount.com\"],\"access_levels\":[\"corp_network\"]}}]"
  }
}
```

`inputs` są **płaskimi stringami** (max 10, po 65535 znaków), więc zagnieżdżone profile jadą jako jeden
input z JSON-em — dokładnie tak samo jak w kanale dywizji.

Token integracji potrzebuje `actions: write` na tym jednym repozytorium i **nic ponadto**:
`pull-requests: write` nie jest potrzebne (PR-a otwiera po tej stronie `intake.yml`), a `contents` — patrz
niżej — celowo nie. Nie dotyka GCP: cała moc zapisu w chmurze siedzi w koncie apply, za environmentem.

> **Ten kanał był na `repository_dispatch` i został z niego ZDJĘTY (#1947)** — tak samo jak kanał dywizji
> (#1958) i z tego samego powodu, mimo że ta sama dokumentacja tłumaczyła wcześniej, dlaczego akurat tu
> zostaje. Tamten argument brzmiał: integracja ticketowa to jeden system pod kontrolą tego samego zespołu,
> co perimetr, więc „prawo zapisu do kodu perimetru" jest tu do przyjęcia. Argument jest prawdziwy
> i nieistotny: **zasięg wycieku wynika z UPRAWNIEŃ tokenu, nie z tego, kto miał go trzymać.**
> `POST /repos/{o}/{r}/dispatches` wymaga `contents: write`; złożone z gałęzią domyślną bez ochrony
> (`403 Upgrade to GitHub Pro` na tym planie) i z apply ruszającym z pushu na tę gałąź, poświadczenie
> integracji było ścieżką do zmiany granicy organizacji z pominięciem **wszystkich** bramek treści — te
> wiszą na `pull_request`. `workflow_dispatch` wymaga `actions: write`, które uruchamia workflow i nie
> zapisuje kodu (rozłączność zmierzona w obie strony: `contrib/README.md` §macierz).
>
> Prerekwizyt **chronionej gałęzi domyślnej** obowiązuje nadal — zawężenie tokenu zmniejsza skutki wycieku,
> a nie zastępuje ochrony gałęzi.

### 3.1 Prerekwizyt, bez którego ten kanał NIE OTWIERA PR-a (zmierzone 2026-08-11, #1947 i #1977)

Automat renderuje plik członka, przechodzi bramki, **wypycha gałąź** i dopiero wtedy woła API pull
requestów. Jeśli PR-a otwiera `GITHUB_TOKEN`, to wołanie kończy się:

```
GitHub Actions is not permitted to create or approve pull requests
```

— dopóki ustawienie repozytorium *Allow GitHub Actions to create and approve pull requests* jest wyłączone
(`GET /repos/{o}/{r}/actions/permissions/workflow` → `can_approve_pull_request_reviews: false`, wartość
domyślna). Kanał pada wtedy **w połowie**: gałąź z plikiem członka zostaje, PR-a nie ma.

**Włączenie tego ustawienia nie jest naprawą.** Po pierwsze, ten sam przełącznik daje Actions prawo
**zatwierdzania** PR-ów. Po drugie — i to jest powód właściwy — pull request utworzony `GITHUB_TOKEN`-em
**nie dostaje ani jednej bramki**, więc kanał zacząłby produkować PR-y z plikiem członka, na które nie
patrzy `validate` ani `plan`. Kanał, który omija bramkę, jest luką, nie udogodnieniem.

#### Jak dokładnie — mechanizm sprostowany pomiarem (2026-08-11, #1977)

Ten punkt jako jedyny w całym opisie kanału stał na dokumentacji GitHuba, a nie na przebiegu: brzmiał
„pull request utworzony `GITHUB_TOKEN`-em **nie uruchamia żadnego workflow** `pull_request`". Domknięty
pomiarem — przełącznik włączony na kilka minut za zgodą właściciela repozytorium, kanał puszczony w trybie
testowym, stan przywrócony. **Mechanizm jest inny, niż brzmiał; wniosek się utrzymał.**

Przebiegi `pull_request` **powstają** — po jednym na każdy workflow pasujący ścieżkami, `validate` i `plan`
— i **nie wykonuje się z nich nic**: oba `completed` / `action_required` / `jobs: []`. Efekt na PR-ze:

```
gh api …/commits/<head-sha>/check-runs --jq .total_count  ->  0
gh api …/commits/<head-sha>/status     --jq .state        ->  pending   (0 wpisów)
gh pr checks <n>                                          ->  no checks reported   (exit 1)
gh pr view <n> --json mergeable                           ->  MERGEABLE
```

**Kontrola, bez której to nie byłby pomiar:** `action_required` wystąpiło na **dokładnie tych dwóch**
przebiegach ze 100 ostatnich w repozytorium, a ludzkie PR-y z tego samego dnia mają `validate` **i** `plan`
zielone. Przyczyną jest więc token, którym otwarto PR-a (`triggering_actor: github-actions[bot]`), a nie
ścieżki w triggerze ani inne ustawienie repozytorium.

Praktyczna różnica między „nie uruchamia" a „uruchamia i parkuje" jest jedna i **nie ratuje przełącznika**:
zaparkowane przebiegi widać w zakładce Actions, więc ktoś **mógłby** je zatwierdzić ręcznie — nikt i nic
tego nie wymusza, a PR jest scalalny bez tego kliknięcia. Reviewer patrzący na taki PR widzi komplet zer,
nie czerwoną bramkę.

#### Konfiguracja wspierana: token Appa **mintowany w przebiegu**, nie wklejony do sekretu

Trzy workflow, które dotykają gałęzi i PR-ów kanału (`intake.yml`, `external-intake.yml`,
`intake-rebase.yml`), wołają `actions/create-github-app-token` i biorą token z jego outputu:

| co | gdzie | dlaczego tam |
|---|---|---|
| `INTAKE_APP_ID` | **zmienna** repozytorium (`vars`) | identyfikator, nie poświadczenie — a `secrets` nie jest widoczne w `if:` kroku, więc na czymś jawnym musi stać warunek |
| `INTAKE_APP_KEY` | **sekret** repozytorium | klucz prywatny aplikacji; ważny do odwołania, więc nadaje się do sekretu |

**Dlaczego nie „wklej gotowy token do sekretu":** token instalacji Appa **wygasa po godzinie**. Wklejony
raz działa do końca dnia i milknie nazajutrz — awaria bez żadnej zmiany w kodzie, która by ją tłumaczyła,
w kanale, który i tak odpala się rzadko. Sekret trzyma więc klucz, a token powstaje na każdy przebieg.

**Zakres aplikacji:** `Contents: Read and write` + `Pull requests: Read and write`, instalacja
**wyłącznie** na repozytorium perimetru. `owner`/`repositories` w kroku mintującym czytane są z kontekstu
przebiegu, więc token jest zawężony do tego jednego repozytorium także wtedy, gdy aplikację ktoś
zainstaluje szerzej.

**Degradacja, gdy Appa jeszcze nie ma.** Krok mintujący ma `if: vars.INTAKE_APP_ID != ''`, a wyrażenie
tokenu brzmi `${{ steps.app.outputs.token || github.token }}`. Bez zmiennej krok jest **pomijany**,
odczyt nieobecnego pola kontekstu daje wartość pustą (nie błąd), i kanał zachowuje się dokładnie tak jak
wyżej: staje na kroku otwarcia PR-a, głośno, ze sprzątnięciem gałęzi. Dodanie dwóch wartości przełącza go
na Appa **bez zmiany w kodzie**.

PR otwarty tokenem Appa powinien uruchamiać bramki jak każdy inny — to **przewidywanie, nie pomiar**:
Appa nadal nie ma, więc nie było czego zmierzyć. Domknięcie tej luki to jeden przebieg: otworzyć PR-a
tokenem Appa i sprawdzić `check-runs.total_count > 0`. Aplikacji nie da się założyć przez API — to ta
sama pozycja „wymaga człowieka", co App dywizji.

---

## 4. Co robi automat (`intake.yml`), krok po kroku

0. **Tylko gałąź domyślna.** Endpoint dispatchu przyjmuje `ref` wybierany przez NADAWCĘ i uruchamia plik
   workflow w wersji z tej gałęzi. Nadawca nie umie gałęzi utworzyć (`actions: write` nie zapisuje kodu),
   ale gałęzie po otwartych PR-ach istnieją, a wersja tego pliku na takiej gałęzi nie jest wersją, która
   przeszła review. Ten sam guard, co w kanale dywizji.
1. **`workflow_dispatch`** — wejście. `concurrency` grupuje po `project_id`, bez `cancel-in-progress`:
   dwa zgłoszenia tego samego projektu ustawiają się w kolejce, zamiast ścigać się o ten sam plik.
2. **`snow_verify.py` — oddzwonienie do ServiceNow.** To jest krok, który zamienia „ufam wiadomości" w „ufam
   systemowi rekordu". Payload jest **danymi, nigdy autoryzacją**: zgłoszenie jest tak wiarygodne jak token,
   którym je wysłano, a tokeny wyciekają. Skrypt sprawdza pięć rzeczy:
   ticket istnieje · stan == zatwierdzony · **grupa** z ticketu należy do allowlisty sieciowej ·
   **projekt w tickecie == projekt w zgłoszeniu** (payload nie podmienił celu po zatwierdzeniu) ·
   **zatwierdzający != wnioskodawca** (rozdział obowiązków po OSOBIE — §8).
   Brak konfiguracji ServiceNow to **odmowa z komunikatem** (rc=2), nie traceback: „nie mamy jak zapytać"
   nigdy nie znaczy „zatwierdzono".
3. **`render_member.py` — plik członka.** Nazwa: `<division>-<project_id>.yaml`. Skrypt **wymusza**
   `stage: dry-run`, ustawia `dry_run_since` na dziś i `review_by` na dziś + okno z `policy.yaml`,
   i składa plik z **listy dozwolonych pól** — czyli `control_plane_exception` czy `exceptions` nie da się
   przemycić w zgłoszeniu. Ten sam skrypt renderuje kanał dywizji (jeden renderer, trzy kanały).
4. **Bramki treści JESZCZE PRZED PR-em**: `check-jsonschema` na pliku członka i reguły OPA
   (`vpcsc.onboarding`). Wcześniej ich tu nie było i kanał ticketowy polegał wyłącznie na tym, że
   ktoś kiedyś spojrzy na PR — a czy PR w ogóle dostaje bramki, zależy od tokenu, który go otworzył (§3.1).
5. **Świeża baza** (`swieza_baza.py`) — gałąź zgłoszenia ma powstać z `main` odczytanego **tuż przed
   pushem**, a nie z commita sprzed bramek. Między checkoutem a pushem mija kilkadziesiąt sekund, a merge,
   który w tym oknie ruszy `.github/workflows/**`, sprawia, że push gałęzi ze starszej bazy leci
   `remote rejected … without workflows permission` — mimo że commit zgłoszenia dotyka **wyłącznie** pliku
   członków. GitHub porównuje wypychaną gałąź z gałęzią **domyślną**, nie z jej własną bazą, więc starsza
   wersja pliku workflow wygląda dla tej kontroli na jego modyfikację. Konsekwencje, które łatwo przeoczyć:
   `add-paths` tego **nie** zamyka (ogranicza commit, a kontrola patrzy na drzewo), a `workflows: write`
   **nie jest naprawą** — brak tego uprawnienia jest kontrolą, nie usterką.
   Gdy w tym samym oknie zmienił się **także plik członków** (wszedł czyjś onboarding), przeniesienie
   gotowej kopii skasowałoby tamten wpis, więc wniosek jest **renderowany ponownie** na świeżym pliku,
   a bramki treści lecą **jeszcze raz** — inaczej do PR-a poszłoby drzewo, którego żadna bramka nie widziała.
6. **PR** przez `create-pull-request`: gałąź `onboard/<division>-<project_id>`, etykiety `onboarding`,
   `dry-run`, w opisie numer ticketu i checklista dla recenzenta. Gdy krok padnie, workflow **rozstrzyga
   DLACZEGO i mówi to wprost** — bo `conclusion: failure` wygląda tak samo w trzech różnych sytuacjach,
   a czerwień kanału wejściowego czyta ktoś **spoza tego repozytorium**:
   gałęzi nie ma + pliki workflow ruszyły się na `main` → **wyścig transportu**, treść jest w porządku,
   powtórzenie pomoże · gałąź **jest** → padło utworzenie PR-a (§3.1), powtórzenie nie pomoże ·
   gałęzi nie ma i nic nie wskazuje na wyścig → „nie rozpoznaję przyczyny", powiedziane wprost zamiast
   zgadywania. Sprzątanie rozróżnia przy tym **„nie ma czego kasować"** (odmowa nastąpiła przed powstaniem
   gałęzi — `Reference does not exist`, HTTP 422) od **„kasowanie padło"**; wcześniej oba kończyły się
   czerwienią, a ta pierwsza maskowała prawdziwą przyczynę w podsumowaniu przebiegu.
7. **`validate.yml`** na tym PR-ze: schematy → reguły OPA → budżet atrybutów → `terraform fmt/validate/test`
   → tflint. Nic z tego nie dotyka chmury, więc PR nie może zejść na czerwono z powodu credentiali.
8. **Merge** → `apply.yml` czeka na zatwierdzenie environmentu `perimeter-apply`. Projekt wchodzi do
   **konfiguracji dry-run**: naruszenia są logowane, nic nie jest blokowane.
9. **Po oknie obserwacji** — osobny PR promocyjny (`stage: enforced`) z raportem naruszeń jako dowodem.

Sekrety: `SNOW_INSTANCE`, `SNOW_USER`, `SNOW_TOKEN` w secrets repozytorium. `snow_verify.py` ich nie loguje —
w razie błędu wypisuje przyczynę, nie odpowiedź API.

---

## 5. Błędy i co się wtedy dzieje

| Sytuacja | Zachowanie | Co zrobić |
|---|---|---|
| ticket nie istnieje / stan ≠ zatwierdzony | `snow_verify.py` kończy błędem, **PR nie powstaje** | dokończyć approval; automat nie ma trybu „na razie otwórz" |
| approver spoza grupy sieciowej | odrzucone (samo-zatwierdzenie przez GRUPĘ wnioskodawcy) | approval przez właściwą grupę |
| zatwierdzający == wnioskodawca | odrzucone — rozdział obowiązków po osobie (§8) | zatwierdzenie przez kogoś innego niż wnioskodawca; „byłem w grupie sieciowej" nie jest tu argumentem |
| w odpowiedzi nie ma pola z wnioskodawcą albo niesie ono `sys_id` zamiast loginu | odrzucone z nazwaniem pola — kontrola, która **nie umie odrzucić**, jest gorsza od jej braku | potwierdzić nazwy pól na instancji docelowej i poprawić kontrakt (§8), nie obchodzić bramki |
| ServiceNow odpowiada czymś, co nie jest JSON-em (instancja w hibernacji, strona logowania) | odrzucone (rc=2) z komunikatem, **nie traceback** | obudzić/naprawić instancję; „nie rozumiem odpowiedzi" nigdy nie znaczy „zatwierdzono" |
| projekt w payloadzie ≠ projekt w tickecie | odrzucone | to jest podmiana celu po zatwierdzeniu — zgłoś do security, nie „popraw i wyślij ponownie" |
| profil nie istnieje w katalogu | PR powstaje, ale OPA go blokuje z nazwą literówki | poprawić nazwę w formularzu, ponowić dispatch |
| brakujący parametr profilu | OPA blokuje, podając którego brakuje | uzupełnić w formularzu |
| projekt już jest w `members/` **pod tą samą dywizją** | `render_member.py` przerywa na kroku renderowania, **PR nie powstaje**; komunikat podaje aktualny `stage` | to nie onboarding, a zmiana istniejącego wpisu — edytuj plik PR-em. Bez tej bramki zgłoszenie nadpisałoby wpis i zapisało `stage: dry-run` **także na członku `enforced`**, czyli zdjęłoby ochronę PR-em wyglądającym na onboarding |
| ten sam projekt zgłoszony pod **inną** dywizją | powstaje drugi plik → blokuje reguła OPA po `project_number` | ustal właściciela: jeden projekt = jeden wpis = jedna dywizja |
| ServiceNow niedostępny | workflow czerwony na kroku weryfikacji | ponów dispatch; **nie** obchodź weryfikacji |
| push gałęzi odrzucony: `refusing to allow … without workflows permission` | **wyścig transportu** — w oknie między checkoutem a pushem na `main` wszedł merge dotykający `.github/workflows/**`. Bramki treści **przeszły**; krok werdyktu mówi to wprost w adnotacji i w podsumowaniu | ponów dispatch — druga próba startuje z bazy zawierającej tamten merge. **Nie** nadawaj tokenowi `workflows: write`: jego brak jest kontrolą, nie usterką |
| gałąź zgłoszenia nie powstała, a sprzątanie zgłasza `Reference does not exist` (422) | nie ma czego sprzątać — odmowa nastąpiła **przed** powstaniem gałęzi. Krok melduje to jako `notice`, nie jako czerwień | nic; przyczyny szukaj w werdykcie kroku wyżej, nie w sprzątaniu |
| `review_by` w przeszłości (wpis odgrzebany) | OPA blokuje każdy PR dotykający tego pliku | potwierdź wpis albo go usuń (`expiry-sweep.yml` otwiera PR sam) |

Zasada wspólna dla wszystkich wierszy: **awaria kończy się brakiem zmiany**, nigdy zmianą „domyślną".

---

## 6. Jak to przetestować BEZ ServiceNow

Trzy poziomy, każdy uruchamialny lokalnie:

**a) Weryfikacja ticketu na fixture** — bez sieci, bez instancji SNOW:

```bash
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --approver net-approver@example.com --offline-fixture tests/snow-approved.json      # przechodzi
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --approver net-approver@example.com --offline-fixture tests/snow-not-approved.json  # MUSI paść
# para anty-tautologiczna piątej kontroli: te same argumenty, inny WNIOSKODAWCA w fixturze
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --approver net-approver@example.com \
  --offline-fixture tests/snow-self-approved-person.json                              # MUSI paść
```

`--approver` jest **wymagany**: kontrola, którą wyłącza się pominięciem flagi, jest kontrolą wyłączoną,
a tego nie widać ani w logu przebiegu, ani w diffie zgłoszenia.

**b) Renderowanie pliku członka** — sprawdza, że bot nie umie zapisać `enforced`:

```bash
python3 tools/render_member.py --division risk --project-id prj-x --project-number 123456789012 \
  --owner-group grp@example.com --change-ref snow:RITM0000001 --approved-by net@example.com \
  --profiles-json '[{"name":"vertex-online-serving","params":{}}]' --out /tmp/member.yaml
grep stage /tmp/member.yaml     # zawsze: stage: dry-run
```

**c) CAŁY KANAŁ NA ŻYWO, bez ServiceNow** — wejście `fixture` podmienia system rekordu na plik z `tests/`
i nie podmienia niczego innego: te same kroki, ten sam renderer, te same bramki, ten sam PR.

```bash
# pozytyw — ticket zatwierdzony przez grupę sieciową
gh workflow run intake.yml -R <ORG>/<REPO> --ref main \
  -f fixture=snow-approved -f snow_ticket=RITM0000001 \
  -f division=example-division -f project_id=prj-x-test -f project_number=000000000000 \
  -f owner_group=grp@example.com -f approved_by=net@example.com \
  -f profiles='[{"name":"vertex-online-serving","params":{"caller_identities":["serviceAccount:a@b.iam.gserviceaccount.com"],"access_levels":["corp_network"]}}]'

# negatywy — ta sama komenda z -f fixture=snow-not-approved | snow-self-approved | snow-wrong-project
```

**Co ogranicza tryb testowy** (bo test na ścieżce wejściowej granicy bezpieczeństwa jest dziurą, dopóki
ktoś nie napisze, co go ogranicza): nazwa fixture'a musi pasować do `^snow-[a-z0-9-]+$` i wskazywać plik
w `tests/` **na gałęzi domyślnej**, czyli treść, która przeszła review; plik musi deklarować się jako
materiał testowy (pole `_material_testowy` — bez niego `snow_verify.py` odmawia, rc=2); a projekt jest
ograniczony przez `u_project_id` w samym fixturze, bo `snow_verify.py` porównuje go z `project_id`
ze zgłoszenia. `tests/snow-approved.json` mówi `prj-x-test` — żadne wejście dispatchu nie zamieni tego
na czyjś realny projekt. Tryb testowy da się włączyć **wyłącznie** jawnym wejściem `fixture` zgłoszenia
(wartość domyślna: pusta) — nie zmienną repozytorium, nie sekretem, nie plikiem w drzewie.

**Czym przebieg testowy KRZYCZY, że jest testem (DEC-43).** Do 2026-08-13 jedynym śladem trybu testowego
poza logiem kroku była nazwa kroku, która w trybie normalnym wygląda tak samo. Zmierzone: przebieg
z fixture'em otworzył pull requesta z **tą samą** nazwą gałęzi, **tym samym** tytułem, **tymi samymi**
etykietami i opisem twierdzącym „verified against the ServiceNow API" — zdaniem nieprawdziwym dla przebiegu,
który ServiceNow nie zapytał. Dziś przebieg z fixture'em oznacza się na pięć sposobów naraz:

| gdzie | co widać |
|---|---|
| lista kroków przebiegu | osobny krok `WERDYKT NA MATERIALE TESTOWYM - system rekordu NIE zostal zapytany` |
| adnotacje przebiegu | `::warning` z nazwą pliku, który zastąpił system rekordu |
| podsumowanie przebiegu | sekcja `### TRYB TESTOWY` + zdanie, że werdykt **nie jest** dowodem zgody |
| gałąź i tytuł pull requesta | `onboard/test-…` oraz `[TRYB TESTOWY] … — NIE MERGOWAC` |
| etykiety i opis pull requesta | `tryb-testowy` **zamiast** `onboarding` (czyli poza zasięgiem bota z `intake-rebase.yml`) + baner `[!WARNING]` na górze opisu |

Każda z tych wartości powstaje w **kroku rozstrzygającym fixture**, a krok otwierający pull requesta tylko
je czyta — nie zna trybu i nie umie o nim zapomnieć. Selftest sprawdza to na WYJŚCIACH kroku (co realnie
wyprodukował), a nie na obecności napisu w pliku.

Wszystkie fixture'y są w `tests/` (opis: `tests/README.md`) — osiem z dziewięciu opisuje przypadki
**negatywne**. Selftest repozytorium (`python3 selftest/selftest.py`) uruchamia (a) i (b) na każdym
przebiegu, na TYCH SAMYCH plikach, które cytuje ta dokumentacja — więc zepsuty fixture wychodzi w teście,
nie u czytelnika. Bramka, która nigdy nie odrzuca, przechodzi każdy test pozytywny i nie chroni niczego.

**Czego te fixture'y NIE dowodzą, powiedziane wprost.** Nie dowodzą, że taki kształt odpowiedzi przychodzi
z realnej instancji — żadnej nie zapytano ani razu. Piąta kontrola porównuje wnioskodawcę Z TICKETU
z zatwierdzającym ZE ZGŁOSZENIA, więc zamyka samo-zatwierdzenie zrobione uczciwie, a nie payload kłamiący
o zatwierdzającym; to wymaga odczytu rekordu approvalu (`sysapproval_approver`), czyli drugiego wywołania,
którego kontrakt nie jest potwierdzony. Pełna lista założeń i sposób ich zmierzenia: §8.

---

## 7. Granica: czego ten kanał NIE tworzy

Wniosek dodaje **istniejący** projekt do perimetru i renderuje jego reguły. **Nie tworzy projektu GCP, sieci,
podsieci, Private Google Access ani wpisów DNS.** Te rzeczy muszą istnieć wcześniej — inaczej projekt wejdzie
do perimetru i po promocji jego workloady stracą łączność z API Google, mimo że wszystkie reguły VPC-SC będą
poprawne.

Konsekwencja praktyczna: pozycja katalogu powinna mieć **prerekwizyt** — projekt utworzony przez fabrykę
projektów (warstwa landing zone, jeśli organizacja ją ma) z włączonym PGA i DNS na restricted VIP.
Sprawdza to **bramka maszynowa**: job `pre-flight` w `plan.yml` i w `apply.yml` uruchamia
`tools/preflight_check.sh` dla każdego członka WCHODZĄCEGO do perimetru (zadeklarowanego, a nieobecnego
jeszcze w `spec`/`status` żywej granicy) i przy czerwonym werdykcie zostawia `terraform plan` oraz
`terraform apply` w stanie `skipped` — DEC-24. Recenzent czyta werdykt w podsumowaniu przebiegu; jedyne,
co zostaje mu do zrobienia z ręki, to check tożsamości (`--identity`, niżej), bo bramka go nie woła. Gdyby
jeden ticket miał robić oba kroki, to jest integracja **dwóch** automatów (fabryka projektów + ten kanał), a nie
rozszerzenie tego workflow — i wymaga osobnej decyzji, bo tworzenie projektu to inny blast-radius niż dodanie
go do granicy.

Prerekwizyt PGA/DNS jest **warunkowy i tak też go sprawdza pre-flight**: dotyczy projektu, który ma sieć VPC.
VPC-SC działa na płaszczyźnie API, więc członkiem może być projekt bez jednej maszyny — trzymający same
zbiory BigQuery, buckety albo endpoint wołany z zewnątrz. W takim projekcie nie ma czego routować do
googleapis.com i pre-flight raportuje oba checki jako **N/D**, nie jako błąd. Wymóg „zawsze" kazałby
poprawnemu kandydatowi zbudować sieć, której nie potrzebuje, i — groźniej — zamieniłby check w alarm
odpalający się przy każdym onboardingu, a odruchową reakcją na taki alarm jest `--warn-only`, czyli
wyciszenie **również** projektów, w których PGA naprawdę brakuje.

**Check tożsamości (`--identity`) to jedyna część pre-flightu, której bramka NIE wykonuje**, i to jest
decyzja, nie luka (DEC-24). Wymaga `iam.serviceAccounts.get`, którego wdrożenie nie nadaje kontom CI —
wpięty byłby więc fail-closed na **każdym** wniosku, z powodu leżącego po stronie perimetru, a nie
wnioskodawcy. Nadanie tego prawa kontu `plan`, impersonowalnemu z każdego pull requesta, oznaczałoby
możliwość enumeracji wszystkich kont serwisowych organizacji. Recenzent uruchamia ten check z ręki,
z tożsamościami z wniosku — powtarzalne `--identity`, wartości przepisane 1:1 z pliku członka:

```bash
tools/preflight_check.sh --project prj-example-vertex-dev --number 123456789012 \
  --identity serviceAccount:sa-example-serving@prj-example-vertex-dev.iam.gserviceaccount.com
```

Checki 1–5 policzą się przy okazji drugi raz — to jest tanie i zamierzone: uruchomienie z ręki ma dawać
komplet, a nie wymagać sklejania go z dwóch źródeł.

**Dlaczego to nie jest duplikat bramki OPA (a §8 niżej mówi, czego ten kanał NIE zmierzył).**
`perimeter.rego` sprawdza **kształt** adresu na plan-JSON i robi
to na każdym PR, bez żadnych poświadczeń — łapie literówkę w domenie. Adres poprawny składniowo, wskazujący na
**nieistniejące** konto, przechodzi tam bez zająknięcia, a ACM odrzuca go dopiero przy apply komunikatem
`invalid or non-existent` i wywraca **całą** zmianę, nie jedną regułę. Istnienie da się sprawdzić wyłącznie
pytaniem do API, więc siedzi tam, gdzie są poświadczenia: w pre-flighcie. `user:`/`group:` pre-flight
raportuje jako **niezweryfikowane** — to Directory API Workspace, inna domena administracyjna.

---

## 8. Kontrakt z ServiceNow — spisany, bo NIE jest zmierzony (DEC-43)

Ten kanał **nie rozmawiał z żadną instancją ServiceNow ani razu**. Cała jego ścieżka — łącznie z jedynym
przebiegiem, który dojechał do pull requesta — była weryfikowana fixture'em z `tests/`. To nie jest to samo,
co „działa": fixture dowodzi, że kod poprawnie interpretuje odpowiedź o **zakładanym** kształcie, i nic ponadto.

Rozstrzygnięcie jest świadome: kanał zostaje w trybie fixture'owym, a fixture przestaje udawać system rekordu
i staje się **jawnie oznaczonym kontraktem**. Ryzyko nie znika — przestaje być niewidoczne.

### 8.1 Zapytanie, które ten kod wysyła

```http
GET https://<instancja>.service-now.com/api/now/table/sc_req_item
    ?sysparm_query=number=<ticket>
    &sysparm_fields=number,approval,state,u_project_id,assignment_group.name,requested_for.user_name,opened_by.user_name
    &sysparm_limit=1
Accept: application/json
Authorization: Basic <SNOW_USER:SNOW_TOKEN>
```

**`sysparm_fields` nie jest optymalizacją, tylko warunkiem poprawności.** Table API zwraca pola **dot-walk**
(`assignment_group.name`) **wyłącznie wtedy, gdy zostały jawnie zamówione**; bez tego referencja przychodzi jako
obiekt `{"link": …, "value": <sys_id>}`, a klucza z kropką w odpowiedzi nie ma w ogóle. Wcześniejsza wersja tego
narzędzia **czytała** `assignment_group.name`, a **zamawiała** samo `sysparm_query` — czyli pytała o pole,
którego jej własne zapytanie nie mogło przynieść, i na żywej instancji odrzuciłaby **każdy** ticket. Fixture
obiecywał kształt, który dla tego zapytania nigdy by nie przyszedł; dlatego pola zapytania i pola werdyktu mają
dziś jedno źródło (`POLA_WERDYKTU`), a selftest pilnuje tej równości w obie strony. Kształt bez zamówienia opisuje
`tests/snow-raw-reference.json` i **musi** kończyć się odmową.

### 8.2 Na czym stoi werdykt

| Pole odpowiedzi | Kontrola | Gdy pola nie ma |
|---|---|---|
| `result: []` | 1 — ticket istnieje | odmowa: „payload zmyślił numer" |
| `approval` (zapas: `state`) | 2 — stan zatwierdzony | wartość pusta ≠ `approved` → odmowa |
| `assignment_group.name` | 3 — grupa z allowlisty sieciowej | pusta → odmowa (brak zapasowej nazwy pola: domysł w bramce fail-closed dokłada ścieżkę, którą nieznany kształt mógłby przejść) |
| `u_project_id` | 4 — projekt z ticketu == projekt ze zgłoszenia | pusta ≠ `project_id` → odmowa |
| `requested_for.user_name` (zapas: `opened_by.user_name`) | 5 — zatwierdzający != wnioskodawca | odmowa z nazwaniem obu pól, nie ciche przepuszczenie |

Porównanie tożsamości normalizuje wielkość liter i **odcina domenę** (zgłoszenie podaje adres e-mail, ServiceNow
trzyma login), a wartość wyglądającą na `sys_id` (32 znaki hex) odrzuca wprost — porównanie `sys_id` z adresem
nigdy nie wypadłoby „ta sama osoba", czyli kontrola byłaby zielona zawsze. Negatyw: `tests/snow-requester-sysid.json`.

### 8.3 Czego ten kontrakt NIE dowodzi

1. **Że pola nazywają się tak w danej organizacji.** `u_project_id` jest polem WŁASNYM (`u_` = customer-defined),
   a nazwa grupy zatwierdzającej to konfiguracja, nie stała platformy.
2. **Że `approval` przyjmuje wartość `approved`** — zbiór wartości zależy od procesu w instancji.
3. **Że zatwierdzenie było prawdziwe.** Kontrola 5 porównuje wnioskodawcę z ticketu z zatwierdzającym
   **ze zgłoszenia**, więc zamyka uczciwe samo-zatwierdzenie, a nie payload kłamiący o zatwierdzającym.
   Domknięcie = odczyt rekordu approvalu (tabela `sysapproval_approver`, pola `approver` i `state`), czyli drugie
   wywołanie o kontrakcie równie niepotwierdzonym — dlatego nie jest napisane „na wyrost".
4. **Że nieznane pole w `sysparm_fields` jest ignorowane**, a nie kończy zapytanie błędem.
5. **Że uwierzytelnienie Basic przejdzie** — instancje bywają skonfigurowane inaczej (MFA, OAuth, ACL na tabeli).

### 8.4 Jak to zamknąć — jeden odczyt, nie projekt

Kanał wolno uznać za zweryfikowany dopiero, gdy ktoś wykona **jeden odczyt z instancji docelowej** i porówna
odpowiedź z §8.1–8.2:

```bash
curl -sS -u "$SNOW_USER:$SNOW_TOKEN" -H 'Accept: application/json' \
  "https://$SNOW_INSTANCE.service-now.com/api/now/table/sc_req_item?sysparm_query=number=RITM0000123&sysparm_fields=number,approval,state,u_project_id,assignment_group.name,requested_for.user_name,opened_by.user_name&sysparm_limit=1" \
  | python3 -m json.tool
```

Werdykt tego odczytu jest binarny: albo klucze zgadzają się z tabelą §8.2 (wtedy fixture'y są prawdziwe i to
trzeba zapisać), albo się nie zgadzają — i wtedy **poprawia się fixture'y**, bo fixture niezgodny
z rzeczywistością jest gorszy od jego braku.

**Instancja developerska (PDI) jako środowisko pomiarowe — co daje, a czego nie.** Dostawca wydaje bezpłatne
instancje developerskie z pełnym Service Catalogiem, więc §8.1–8.2 da się na nich sprawdzić. Trzy właściwości,
które trzeba znać, zanim ktoś oprze na tym bramkę:

- instancja jest przypisana do **konta osobistego** w portalu deweloperskim (rejestracja: dane osobowe
  + akceptacja regulaminu) — to jest krok dla człowieka, nie dla automatu;
- instancja **hibernuje** po okresie bezczynności i bywa **odbierana** po ~10 dniach bez logowania człowieka;
  wywołanie API z pipeline'u tego nie zastępuje. Poświadczenie w sekretach repozytorium zaczęłoby więc pewnego
  dnia dostawać stronę HTML zamiast JSON-a — dlatego `snow_verify.py` traktuje „to nie jest JSON" jako odmowę
  z komunikatem, a nie jako traceback;
- PDI dowodzi **kontraktu platformy** (nazwy pól standardowych, semantyka `sysparm_fields`, kształt referencji),
  **nie** konfiguracji organizacji docelowej: pola własne i nazwy grup i tak trzeba potwierdzić u niej.

Wniosek praktyczny: PDI skraca listę z §8.3 o punkty 2, 4 i 5 (i część 3), ale punktu 1 nie zamknie nikt poza
organizacją docelową. Dlatego **uruchomienie kanału ticketowego w nowym środowisku ma prerekwizyt: przelot
§8.4 na jego instancji**, a do tego czasu kanał wolno uruchamiać wyłącznie w trybie testowym (§6c) — który,
od DEC-43, sam mówi o sobie, czym jest.
