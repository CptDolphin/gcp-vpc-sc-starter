# Kanał ServiceNow — od formularza do reguły w perimetrze

Ten dokument opisuje **pierwszy i domyślny kanał wejścia**: dywizja wypełnia formularz w ServiceNow, networking
zatwierdza, automat otwiera PR. Zawiera specyfikację pozycji katalogu (pola, typy, walidacje), mapowanie pól na
plik członka, ścieżkę zatwierdzeń, obsługę błędów i sposób przetestowania całości **bez ServiceNow**.

Pozostałe dwa kanały: `docs/README.md` (ręczny PR architekta) i `contrib/README.md` (repozytorium zespołu).
Wszystkie trzy kończą się tym samym: plikiem YAML w `perimeter/members/` i jednym mutatorem (DEC-7).

---

## 1. Co ServiceNow robi, a czego NIE robi

ServiceNow jest **rejestrem zgody biznesowej i technicznej** — i tylko tym. Nie jest źródłem prawdy o stanie
perimetru i nie wywołuje API Google.

| Robi | Nie robi |
|---|---|
| zbiera wniosek w ustrukturyzowanej formie | nie zapisuje niczego w Access Context Managerze |
| przeprowadza approval (dywizja → networking → security dla profili `risk: high`) | nie decyduje, czy projekt jest chroniony (o tym decyduje merge PR-a i `stage`) |
| wysyła `repository_dispatch` do repo perimetru | nie tworzy projektów GCP ani sieci (patrz §7) |
| zostaje rekordem „kto poprosił, kto zatwierdził, kiedy" | nie zastępuje audytu w gicie — ten jest w historii PR-ów |

**Dlaczego nie ticket → API wprost.** Wywołanie API z ticketa oddaje trzy własności, bez których granica
bezpieczeństwa nie działa: historię *dlaczego* reguła istnieje (git blame na pliku), rollback równy
`git revert` oraz drift detection (bez zadeklarowanego stanu nie ma z czym porównać żywego). Ticket zostaje
przy tym, w czym jest dobry.

---

## 2. Pozycja katalogu — specyfikacja pól

Nazwy techniczne po lewej to nazwy zmiennych w Catalog Item; automat wysyła je 1:1 w `client_payload`.

| Pole (techniczne) | Typ / kontrolka | Wymagane | Walidacja w SNOW | Uwaga |
|---|---|---|---|---|
| `division` | Choice (lista dywizji) | tak | wartość ze słownika, nie free-text | musi zgadzać się z właścicielem grupy z `owner_group`; bramka OPA porównuje to z `contributors.yaml` przy kanale `pr:` |
| `project_id` | String | tak | `^[a-z][a-z0-9-]{4,28}[a-z0-9]$` | ID projektu, **nie** nazwa wyświetlana |
| `project_number` | String (cyfry) | tak | `^[0-9]{6,20}$` | ACM adresuje projekty **numerem**; literówka cicho dodaje CUDZY projekt — dlatego pre-flight sprawdza parę ID↔numer |
| `owner_group` | Reference (Group) | tak | grupa musi istnieć | adresat raportu naruszeń i przeglądu po 6 miesiącach |
| `profiles` | Multi-row (lista) | tak, min. 1 | każdy wiersz: `name` + parametry | dozwolone nazwy = katalog `perimeter/profiles/` opublikowany w kontrakcie |
| `profiles[].params` | Key-value per wiersz | tak | klucze = `parameters` profilu | brak parametru → OPA odrzuca PR z nazwą brakującego pola |
| `use_case` | Multi-line text | tak | min. 40 znaków | nie trafia do YAML-a; zostaje w tickecie i w opisie PR-a jako uzasadnienie |
| `data_classification` | Choice | tak | słownik klasyfikacji danych organizacji | steruje tym, czy wymagany jest approval Security (profile `risk: high` — zawsze) |
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

Po ostatnim approvalu Flow Designer wysyła:

```http
POST https://api.github.com/repos/<ORG>/<REPO>/dispatches
Authorization: Bearer <token integracji>
Content-Type: application/json

{
  "event_type": "vpc-sc-onboard",
  "client_payload": {
    "snow_ticket": "RITM0000123",
    "division": "example-division",
    "project_id": "prj-example-vertex-prod",
    "project_number": "123456789012",
    "owner_group": "grp-example-division-cloud@example.com",
    "approved_by": "net-approver@example.com",
    "profiles": [
      { "name": "vertex-online-serving",
        "params": { "caller_identities": ["serviceAccount:sa-scoring@prj-example-app-prod.iam.gserviceaccount.com"],
                    "access_levels": ["corp_network"] } }
    ]
  }
}
```

Token integracji potrzebuje **wyłącznie** `contents: write` + `pull-requests: write` na tym jednym
repozytorium. Nie dotyka GCP — cała moc zapisu w chmurze siedzi w koncie apply, za environmentem z
reviewerami.

---

## 4. Co robi automat (`intake.yml`), krok po kroku

1. **`repository_dispatch: vpc-sc-onboard`** — wejście. `concurrency` grupuje po `project_id`, bez
   `cancel-in-progress`: dwa zgłoszenia tego samego projektu ustawiają się w kolejce, zamiast ścigać się o
   ten sam plik.
2. **`snow_verify.py` — oddzwonienie do ServiceNow.** To jest krok, który zamienia „ufam wiadomości" w „ufam
   systemowi rekordu". Payload jest **danymi, nigdy autoryzacją**: `repository_dispatch` jest tak wiarygodny
   jak token, którym go wysłano, a tokeny wyciekają. Skrypt sprawdza cztery rzeczy:
   ticket istnieje · stan == zatwierdzony · approver należy do grupy sieciowej (nie samo-zatwierdzenie) ·
   **projekt w tickecie == projekt w payloadzie** (payload nie podmienił celu po zatwierdzeniu).
3. **`render_member.py` — plik członka.** Nazwa: `<division>-<project_id>.yaml`. Skrypt **wymusza**
   `stage: dry-run`, ustawia `dry_run_since` na dziś i `review_by` na dziś + okno z `policy.yaml`.
4. **PR** przez `create-pull-request`: gałąź `onboard/<division>-<project_id>`, etykiety `onboarding`,
   `dry-run`, w opisie numer ticketu i checklista dla recenzenta.
5. **`validate.yml`** na tym PR-ze: schematy → reguły OPA → budżet atrybutów → `terraform fmt/validate/test`
   → tflint. Nic z tego nie dotyka chmury, więc PR nie może zejść na czerwono z powodu credentiali.
6. **Merge** → `apply.yml` czeka na zatwierdzenie environmentu `perimeter-apply`. Projekt wchodzi do
   **konfiguracji dry-run**: naruszenia są logowane, nic nie jest blokowane.
7. **Po oknie obserwacji** — osobny PR promocyjny (`stage: enforced`) z raportem naruszeń jako dowodem.

Sekrety: `SNOW_INSTANCE`, `SNOW_USER`, `SNOW_TOKEN` w secrets repozytorium. `snow_verify.py` ich nie loguje —
w razie błędu wypisuje przyczynę, nie odpowiedź API.

---

## 5. Błędy i co się wtedy dzieje

| Sytuacja | Zachowanie | Co zrobić |
|---|---|---|
| ticket nie istnieje / stan ≠ zatwierdzony | `snow_verify.py` kończy błędem, **PR nie powstaje** | dokończyć approval; automat nie ma trybu „na razie otwórz" |
| approver spoza grupy sieciowej | odrzucone (scenariusz samo-zatwierdzenia) | approval przez właściwą grupę |
| projekt w payloadzie ≠ projekt w tickecie | odrzucone | to jest podmiana celu po zatwierdzeniu — zgłoś do security, nie „popraw i wyślij ponownie" |
| profil nie istnieje w katalogu | PR powstaje, ale OPA go blokuje z nazwą literówki | poprawić nazwę w formularzu, ponowić dispatch |
| brakujący parametr profilu | OPA blokuje, podając którego brakuje | uzupełnić w formularzu |
| projekt już jest w `members/` **pod tą samą dywizją** | `render_member.py` przerywa na kroku renderowania, **PR nie powstaje**; komunikat podaje aktualny `stage` | to nie onboarding, a zmiana istniejącego wpisu — edytuj plik PR-em. Bez tej bramki zgłoszenie nadpisałoby wpis i zapisało `stage: dry-run` **także na członku `enforced`**, czyli zdjęłoby ochronę PR-em wyglądającym na onboarding |
| ten sam projekt zgłoszony pod **inną** dywizją | powstaje drugi plik → blokuje reguła OPA po `project_number` | ustal właściciela: jeden projekt = jeden wpis = jedna dywizja |
| ServiceNow niedostępny | workflow czerwony na kroku weryfikacji | ponów dispatch; **nie** obchodź weryfikacji |
| `review_by` w przeszłości (wpis odgrzebany) | OPA blokuje każdy PR dotykający tego pliku | potwierdź wpis albo go usuń (`expiry-sweep.yml` otwiera PR sam) |

Zasada wspólna dla wszystkich wierszy: **awaria kończy się brakiem zmiany**, nigdy zmianą „domyślną".

---

## 6. Jak to przetestować BEZ ServiceNow

Trzy poziomy, każdy uruchamialny lokalnie:

**a) Weryfikacja ticketu na fixture** — bez sieci, bez instancji SNOW:

```bash
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x \
  --offline-fixture tests/snow-approved.json      # przechodzi
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x \
  --offline-fixture tests/snow-not-approved.json  # MUSI paść
```

**b) Renderowanie pliku członka** — sprawdza, że bot nie umie zapisać `enforced`:

```bash
python3 tools/render_member.py --division risk --project-id prj-x --project-number 123456789012 \
  --owner-group grp@example.com --change-ref snow:RITM0000001 --approved-by net@example.com \
  --profiles-json '[{"name":"vertex-online-serving","params":{}}]' --out /tmp/member.yaml
grep stage /tmp/member.yaml     # zawsze: stage: dry-run
```

**c) Cały kanał na sucho** — wywołaj dispatch ręcznie z własnego konta (token z `contents: write` na repo
testowym) i obserwuj, czy powstał PR z właściwą etykietą i gałęzią:

```bash
gh api repos/<ORG>/<REPO>/dispatches -f event_type=vpc-sc-onboard \
  --input tests/dispatch-example.json
```

Wszystkie fixture'y są w `tests/` (opis: `tests/README.md`) — trzy z pięciu opisują przypadki **negatywne**:
approval w toku, samo-zatwierdzenie i podmiana projektu po approvalu. Selftest repozytorium
(`python3 selftest/selftest.py`) uruchamia (a) i (b) na każdym przebiegu, na TYCH SAMYCH plikach, które
cytuje ta dokumentacja — więc zepsuty fixture wychodzi w teście, nie u czytelnika.
Bramka, która nigdy nie odrzuca, przechodzi każdy test pozytywny i nie chroni niczego.

---

## 7. Granica: czego ten kanał NIE tworzy

Wniosek dodaje **istniejący** projekt do perimetru i renderuje jego reguły. **Nie tworzy projektu GCP, sieci,
podsieci, Private Google Access ani wpisów DNS.** Te rzeczy muszą istnieć wcześniej — inaczej projekt wejdzie
do perimetru i po promocji jego workloady stracą łączność z API Google, mimo że wszystkie reguły VPC-SC będą
poprawne.

Konsekwencja praktyczna: pozycja katalogu powinna mieć **prerekwizyt** — projekt utworzony przez fabrykę
projektów (warstwa landing zone, jeśli organizacja ją ma) z włączonym PGA i DNS na restricted VIP.
Sprawdza to `tools/preflight_check.sh` i jest to element checklisty recenzenta w opisie PR-a. Gdyby
jeden ticket miał robić oba kroki, to jest integracja **dwóch** automatów, a nie
jeden ticket robił oba kroki, to jest integracja **dwóch** automatów (fabryka projektów + ten kanał), a nie
rozszerzenie tego workflow — i wymaga osobnej decyzji, bo tworzenie projektu to inny blast-radius niż dodanie
go do granicy.
