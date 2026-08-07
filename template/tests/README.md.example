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

```bash
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --offline-fixture tests/snow-approved.json          # 0
python3 tools/snow_verify.py --ticket RITM0000001 --expect-project prj-x-test \
  --offline-fixture tests/snow-not-approved.json      # != 0
```

Trzy z pięciu plików opisują przypadki **negatywne** i to jest sedno: bramka, która nigdy nie odrzuca,
przechodzi każdy test pozytywny i nie chroni niczego.
