# Dokumentacja startera perimetru VPC-SC

Osiem dokumentów, osiem różnych momentów:

| Dokument | Kiedy go czytasz |
|---|---|
| [0 — Decyzje (DEC-1…DEC-20)](0-decyzje.md) | pytasz „dlaczego akurat tak"; przed każdą zmianą kształtu repo |
| [1 — Wdrożenie](1-wdrozenie.md) | stawiasz repo od zera; kolejność etapów i placeholdery |
| [2 — Uprawnienia i WIF](2-uprawnienia-i-wif.md) | zamawiasz dostępy u architekta; rola po roli z uzasadnieniem i gotową listą do ticketu |
| [3 — Runbook: promocja i break-glass](3-runbook-promocja-i-break-glass.md) | promujesz członka do enforced albo perimetr właśnie zablokował produkcję |
| [4 — Brownfield: import](4-brownfield-import.md) | perimetr już istnieje i chcesz się podłączyć bez nadpisania cudzej konfiguracji |
| [5 — Kanał ServiceNow](5-servicenow-intake.md) | budujesz pozycję katalogową i mapowanie pól formularza na wniosek |
| [6 — Układ repozytoriów](6-uklad-repozytoriow.md) | architekt pyta o skalę: plik na projekt czy jeden `projects.yml` przy 100–200 projektach |
| [7 — Alerty granicy](7-alerty.md) | któryś alert właśnie odpalił — procedura per objaw; albo dokładasz alert i szukasz, gdzie dopisać kotwicę |

Decyzje, na których stoi całość — z odrzuconymi wariantami — są w [`0-decyzje.md`](0-decyzje.md)
(`DEC-1`…`DEC-20`). Kod odsyła do nich tym skrótem; numeracja `DEC-` jest rozłączna z `D1`…`D5`,
którymi oznaczone są diagramy.

## Diagramy

| Diagram | Odpowiada na pytanie |
|---|---|
| [D1 — onboarding flow](diagrams/D1-onboarding-flow.drawio) · [PNG](diagrams/D1-onboarding-flow.png) | jak dywizja dołącza: od ticketu do enforce, z bramkami po drodze |
| [D2 — model dostępów i WIF](diagrams/D2-iam-and-wif.drawio) · [PNG](diagrams/D2-iam-and-wif.png) | która tożsamość potrzebuje której roli, co się stanie bez niej, gdzie jest guardrail WIF |
| [D3 — anatomia perimetru](diagrams/D3-perimeter-anatomy.drawio) · [PNG](diagrams/D3-perimeter-anatomy.png) | co należy do repo, co znaczą konfiguracje dry-run i enforced, jak wygląda brownfield |
| [D4 — ścieżka dywizji](diagrams/D4-division-journey.drawio) · [PNG](diagrams/D4-division-journey.png) | **to samo z perspektywy zespołu, który dołącza**: co robisz ty, co dzieje się bez ciebie, co realnie obowiązuje w twoim projekcie na każdym etapie |
| [D5 — struktura folderów](diagrams/D5-struktura-folderow.drawio) · [PNG](diagrams/D5-struktura-folderow.png) | **układ dwóch repozytoriów**: który plik gdzie ląduje, kto jest jego właścicielem i gdzie w ogóle mogą powstać konflikty przy 200 projektach |
| [D6 — trzy kanały wejścia](diagrams/D6-trzy-kanaly.drawio) · [PNG](diagrams/D6-trzy-kanaly.png) | **najprostszy obraz całości**: skąd przychodzi zgłoszenie w każdym z trzech kanałów, kto co weryfikuje, które JEDNO miejsce ma dostęp do GCP i dlaczego repozytorium zespołu nie dostaje ani PAT-a, ani WIF-a |
| [D7 — co gdzie leży](diagrams/D7-struktura-repo.drawio) · [PNG](diagrams/D7-struktura-repo.png) | **mapa obu repozytoriów i własności**: który plik należy do kogo i co płynie między repozytoriami (kontrakt w jedną stronę, `workflow_dispatch` w drugą). D5 odpowiada na pytanie o SKALĘ i konflikty, D7 na pytanie „co gdzie i czyje". **Treść po angielsku** — to jest diagram do pokazania na zewnątrz |

D4 jest materiałem **dla dywizji** — to jego wysyłasz razem z linkiem do formularza, a nie D1 (ten pokazuje
maszynerię, która zespołu dołączającego nie interesuje).

Źródła `.drawio` są edytowalne (diagrams.net / drawio desktop). Render:

```bash
drawio -x -f png --crop --scale 1.5 -o D1-onboarding-flow.png D1-onboarding-flow.drawio
```
