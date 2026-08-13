# tests/ — dane wejściowe do testowania kanałów BEZ zewnętrznych systemów

Fixture'y są wersjonowane, a nie generowane w kodzie testu. Powód jest prozaiczny: `docs/5-servicenow-intake.md`
obiecuje, że weryfikację ticketu da się uruchomić jedną komendą — obietnica z fixture'em schowanym w teście
jest nieprawdziwa, a plik, którego nikt nie widzi, nie jest dokumentacją formatu.

| Plik | Scenariusz | Oczekiwany wynik |
|---|---|---|
| `snow-approved.json` | ticket zatwierdzony przez grupę sieciową, projekt zgodny | `snow_verify.py` kończy się **0** |
| `snow-not-approved.json` | approval jeszcze trwa (`approval: requested`) | **PADA** — wniosek w trakcie akceptacji nie wchodzi |
| `snow-self-approved.json` | zatwierdzony przez grupę wnioskodawcy | **PADA** — samo-zatwierdzenie (patrz zastrzeżenie niżej) |
| `snow-wrong-project.json` | ticket dotyczy innego projektu niż payload | **PADA** — podmiana celu po approvalu |
| `snow-no-approval.json` | ticket istnieje, ale nie niesie ŻADNEGO śladu zatwierdzenia | **PADA** — trzema regułami naraz; zarazem dowód, że nieznany kształt odpowiedzi degraduje się do odmowy, nie do zgody |
| `snow-not-found.json` | `result: []` — numeru ticketu nie ma w systemie rekordu | **PADA** — payload zmyślił numer |
| `snow-self-approved-person.json` | grupa **poprawna** (sieciowa), ale wnioskodawca == zatwierdzający | **PADA** — samo-zatwierdzenie po OSOBIE; do piątej kontroli ten wiersz przechodził komplet checków |
| `snow-raw-reference.json` | kształt, który Table API zwraca dla zapytania **bez** `sysparm_fields`: referencja jako `{link, value}`, zero kluczy z kropką | **PADA** — brak grupy i brak wnioskodawcy; dowód, dlaczego zapytanie musi zamawiać pola dot-walk |
| `snow-requester-sysid.json` | wnioskodawca podany jako `sys_id`, nie login | **PADA** — porównanie z adresem zatwierdzającego nigdy by nie odrzuciło, więc kontrola mówi to wprost zamiast przepuścić |
| `dispatch-example.json` | komplet wejść `workflow_dispatch` kanału ticketowego | wejście dla `gh workflow run intake.yml -f …` |
| `vpcsc-violation-dryrun.json` | 4 naruszenia dry-run w kształcie zwracanym przez `gcloud logging read` | `violations_report.py` przypisuje **3** członkowi, 4. trafia do „spoza listy członków" |

```bash
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --approver net-approver@example.com --offline-fixture tests/snow-approved.json          # 0
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --approver net-approver@example.com --offline-fixture tests/snow-not-approved.json      # != 0
```

Osiem z dziewięciu plików `snow-*` opisuje przypadki **negatywne** i to jest sedno: bramka, która nigdy nie
odrzuca, przechodzi każdy test pozytywny i nie chroni niczego. `snow_verify.py` sprawdza pięć rzeczy i każda
ma swój fixture — `snow-not-found` domyka punkt 1 („ticket istnieje"), który przez cały czas był **jedynym
bez pokrycia**: kod tej gałęzi nigdy nie wykonał się w żadnym teście.

## Te pliki są KONTRAKTEM, nie odpowiedzią systemu rekordu (DEC-43)

Każdy `snow-*.json` niesie pole **`_material_testowy`** i bez niego `snow_verify.py` **odmawia** przyjęcia go
w trybie offline (`rc=2`). To nie jest ozdoba: do tej pory jedyną różnicą między „werdykt z systemu rekordu"
a „werdykt z pliku w repo" była **nazwa kroku w workflow**, a przebieg testowy otwierał pull requesta, którego
opis twierdził, że ticket zweryfikowano w API ServiceNow. Znacznik sprawia, że plik mówi o sobie, czym jest —
przy otwarciu, w każdej linii werdyktu i w opisie pull requesta.

**Czego te fixture'y NIE dowodzą, powiedziane wprost.** Nie dowodzą, że taki kształt odpowiedzi przychodzi
z realnej instancji: żadna instancja ServiceNow nie została w tym repozytorium zapytana ani razu. Kształt
pochodzi z dokumentacji dostawcy (`sysparm_fields` + dot-walk), nazwy pól są **konfiguracją organizacji**
(`u_project_id` jest polem własnym, nie standardem platformy), a rekordu approvalu (`sysapproval_approver`)
nie czyta nikt — czyli payload kłamiący o zatwierdzającym nadal przejdzie punkt 5. Pełny kontrakt zapytania
i lista pozycji do potwierdzenia jednym odczytem: `docs/5-servicenow-intake.md` §8.

## `vpcsc-violation-dryrun.json` — kształt zdjęty z żywej organizacji, nie wymyślony

Ten fixture powstał z **anonimizowanych** wpisów audytowych żywego perimetru (podmienione numery projektów,
identyfikatory i tokeny; `principalEmail` GCP redaguje sam). Wymyślony fixture był tu wcześniej problemem,
nie ułatwieniem: raport przez cały czas testowano na pustym wejściu `[]`, gdzie każdy członek ma 0 niezależnie
od tego, czy funkcja przypisująca w ogóle działa — i nie działała.

Cztery wpisy to cztery różne sposoby, na jakie `metadata.resourceNames[0]` **nie jest** numerem członka:

| Wpis | `resourceNames[0]` kończy się na | Gdzie naprawdę jest członek |
|---|---|---|
| ingress, Vertex AI | `…/locations/europe-west4` → **nazwa regionu** | `ingressViolations[].targetResource` |
| ingress, Logging | `prj-example-vertex-dev` → **`project_id`, nie numer** | `ingressViolations[].targetResource` |
| egress, Cloud Storage | numer **obcego** projektu (kolejność listy bywa różna) | `egressViolations[].source` |
| ingress, projekt spoza `members/` | `prj-not-a-member` | — (poprawnie „spoza listy") |
