# tests/ — dane wejściowe do testowania kanałów BEZ zewnętrznych systemów

Fixture'y są wersjonowane, a nie generowane w kodzie testu. Powód jest prozaiczny: `docs/5-servicenow-intake.md`
obiecuje, że weryfikację ticketu da się uruchomić jedną komendą — obietnica z fixture'em schowanym w teście
jest nieprawdziwa, a plik, którego nikt nie widzi, nie jest dokumentacją formatu.

| Plik | Scenariusz | Oczekiwany wynik |
|---|---|---|
| `snow-approved.json` | ticket zatwierdzony przez grupę sieciową, projekt zgodny | `snow_verify.py` kończy się **0** |
| `snow-not-approved.json` | approval jeszcze trwa | **PADA** — wniosek w trakcie akceptacji nie wchodzi |
| `snow-self-approved.json` | zatwierdzony przez grupę wnioskodawcy | **PADA** — samo-zatwierdzenie |
| `snow-wrong-project.json` | ticket dotyczy innego projektu niż payload | **PADA** — podmiana celu po approvalu |
| `dispatch-example.json` | kompletny payload `repository_dispatch` | wejście dla `gh api …/dispatches` |
| `vpcsc-violation-dryrun.json` | 4 naruszenia dry-run w kształcie zwracanym przez `gcloud logging read` | `violations_report.py` przypisuje **3** członkowi, 4. trafia do „spoza listy członków" |

```bash
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --offline-fixture tests/snow-approved.json          # 0
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --offline-fixture tests/snow-not-approved.json      # != 0
```

Trzy z pięciu plików opisują przypadki **negatywne** i to jest sedno: bramka, która nigdy nie odrzuca,
przechodzi każdy test pozytywny i nie chroni niczego.

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
