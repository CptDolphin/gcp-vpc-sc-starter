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
| `snow-no-approval.json` | ticket istnieje, ale nie niesie ŻADNEGO śladu zatwierdzenia | **PADA** — dwiema regułami naraz; zarazem dowód, że nieznany kształt odpowiedzi degraduje się do odmowy, nie do zgody |
| `snow-not-found.json` | `result: []` — numeru ticketu nie ma w systemie rekordu | **PADA** — payload zmyślił numer |
| `dispatch-example.json` | komplet wejść `workflow_dispatch` kanału ticketowego | wejście dla `gh workflow run intake.yml -f …` |
| `vpcsc-violation-dryrun.json` | 4 naruszenia dry-run w kształcie zwracanym przez `gcloud logging read` | `violations_report.py` przypisuje **3** członkowi, 4. trafia do „spoza listy członków" |

```bash
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --offline-fixture tests/snow-approved.json          # 0
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --offline-fixture tests/snow-not-approved.json      # != 0
```

Pięć z siedmiu plików opisuje przypadki **negatywne** i to jest sedno: bramka, która nigdy nie odrzuca,
przechodzi każdy test pozytywny i nie chroni niczego. `snow_verify.py` sprawdza cztery rzeczy i każda ma
teraz swój fixture — `snow-not-found` domyka punkt 1 („ticket istnieje"), który przez cały czas był
**jedynym bez pokrycia**: kod tej gałęzi nigdy nie wykonał się w żadnym teście.

**Czego `snow-self-approved.json` NIE pokrywa, powiedziane wprost.** Opisuje samo-zatwierdzenie przez
GRUPĘ wnioskodawcy i tyle sprawdza `snow_verify.py`: porównuje grupę z ticketu z allowlistą sieciową.
Nie porównuje **osoby** zatwierdzającej z wnioskodawcą, więc wnioskodawca należący do grupy sieciowej
zatwierdziłby własny ticket i przeszedł. Domknięcie wymaga odczytu rekordu approvalu
(`sysapproval_approver`) z żywej instancji ServiceNow — a fixture napisany „z wyobrażenia o kształcie
API", którego nie da się skonfrontować z niczym prawdziwym, produkowałby zieloną bramkę o nieznanej
wartości. To jest zapisana luka, nie przeoczenie.

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
