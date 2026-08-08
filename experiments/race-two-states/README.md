# Eksperyment: dwa stany Terraform, jeden perimetr

Rozstrzyga jedno pytanie, które wraca przy każdej rozmowie o architekturze:

> **Czy dwa repozytoria z osobnymi stanami mogą bezpiecznie dodawać własne reguły do tego samego perimetru?**

Argument teoretyczny brzmi: nie, bo Access Context Manager przepisuje politykę jako całość
(read-modify-write), a blokada Terraforma jest per-state, nie per-obiekt w chmurze. Ten eksperyment zamienia
ten argument w **wynik pomiaru** — albo go obala.

**U nas go obalił, i to jest ważniejsze niż samo potwierdzenie.** ACM ma optymistyczną kontrolę
współbieżności na eTagach: przegrany apply pada **głośno**, nic nie znika po cichu. Wniosek (single-flight)
zostaje, ale uzasadnienie jest inne — patrz [§Wynik z organizacji labu](#wynik-z-organizacji-labu).

**Uruchom to, zanim ktoś podejmie decyzję na podstawie mojej opinii** — łącznie z opinią zapisaną wyżej.

> **Czego ten eksperyment nauczył nas o eksperymentach.** Pierwsza wersja miała tożsamości wpisane na sztywno,
> na fikcyjne konta. ACM waliduje istnienie tożsamości, więc **oba** applye padały na walidacji, w API nie było
> żadnej reguły, a werdykt — liczący wyłącznie „czy są dwie reguły" — brzmiał *„reguły giną"*. Eksperyment
> potwierdzał tezę **zawsze**, niezależnie od zachowania API. Dlatego dziś tożsamości są parametrem
> (`IDENTITY_A`/`IDENTITY_B`, konta muszą realnie istnieć), a werdykt rozróżnia **cztery** wyniki, w tym
> osobną kategorię „nierozstrzygnięte" na przebiegi, które nic nie mierzą.

## Czego wymaga

- perimetr w organizacji, w trybie **dry-run** (żeby eksperyment nie mógł niczego zablokować),
- tożsamość z `accesscontextmanager.servicePerimeters.update`,
- **dwa istniejące konta serwisowe** do wstawienia w reguły — ACM waliduje istnienie tożsamości i odrzuca
  całą zmianę (`invalid or non-existent`), więc konto zmyślone zamienia eksperyment o współbieżności w test
  walidacji,
- dwa lokalne katalogi stanu (celowo lokalne — chodzi o brak wspólnej blokady),
- ~15 minut.

**Koszt: zero.** Access Context Manager jest darmowy.

## Dlaczego to jest bezpieczne do uruchomienia

Eksperyment dodaje **dwie reguły ingress w trybie dry-run** do perimetru, który sam wskażesz. Dry-run nie
blokuje niczego — reguły są tylko zapisywane w konfiguracji, która loguje naruszenia. Na końcu skrypt je
usuwa. Nie dotyka `restricted_services`, nie dodaje ani nie usuwa projektów.

Mimo to: **uruchom na perimetrze testowym**, nie na tym, do którego dołączają dywizje.

## Krok po kroku

```bash
export TF_VAR_policy_id=123456789          # gcloud access-context-manager policies list --organization=<ORG>
export TF_VAR_perimeter_name=test_race     # perimetr TESTOWY, nie produkcyjny
export IDENTITY_A=serviceAccount:sa-example-a@prj-example.iam.gserviceaccount.com  # MUSI istnieć
export IDENTITY_B=serviceAccount:sa-example-b@prj-example.iam.gserviceaccount.com  # MUSI istnieć, inne niż A
./run.sh 5
```

`run.sh` robi dokładnie to:

1. `terraform apply` w `state-a/` → dodaje regułę `race-test-alpha`,
2. `terraform apply` w `state-b/` → dodaje regułę `race-test-beta`,
   **oba uruchomione równolegle**, w tle, bez żadnej synchronizacji między nimi,
3. czeka na oba,
4. czyta perimetr z API i sprawdza, **ile reguł race-test-\* faktycznie w nim jest**,
5. sprząta (usuwa oba zasoby).

## Jak czytać wynik

Skrypt klasyfikuje każdy przebieg do jednej z czterech kategorii. **Rozróżnienie „apply padł" od „reguła
zniknęła" jest tu całą treścią eksperymentu** — bez niego dowolna awaria wygląda jak utrata danych.

| Kategoria | Kiedy | Co to znaczy |
|---|---|---|
| **cicha utrata** | oba apply `rc=0`, a reguł mniej niż 2 | **jedyny** wynik potwierdzający tezę o cichym nadpisaniu. Sam retry nie wystarczy — trzeba weryfikować stan po każdym apply. Kończy się kodem `1` |
| **konflikt głośny (eTag)** | apply padł na `Error 400: The eTag provided … does not match` | API odrzuciło przegranego. Nic nie zniknęło niezauważenie; wniosek dotyczy **niezawodności**, nie utraty danych |
| **bez nałożenia** | oba `rc=0`, obie reguły obecne | przebieg nie trafił w okno wyścigu — powtórz |
| **nierozstrzygnięte** | apply padł z **innego** powodu (uprawnienia, nieistniejące konto, zły perimetr) | ten przebieg **nic nie mierzy**. Napraw przyczynę i powtórz — inaczej raportujesz awarię środowiska jako wynik pomiaru |

**Uwaga na interpretację:** brak utraty w jednym przebiegu to *nie* dowód poprawności. Wyścig to zjawisko
zależne od przeplotu — przy sekwencyjnym wykonaniu (A kończy, potem B czyta) obie reguły przetrwają zawsze.
Dlatego `run.sh` uruchamia je równolegle i dlatego warto powtórzyć kilka razy.

Kategoria **nierozstrzygnięte** istnieje dlatego, że jej brak zepsuł pierwszą wersję tego eksperymentu:
awaria walidacji tożsamości była liczona jako utrata reguły i werdykt zawsze wychodził po myśli hipotezy.

## Co to NIE testuje

- **Uprawnień.** Nawet gdyby wyścigu nie było, każde takie repozytorium potrzebuje
  `servicePerimeters.update` na **organizacji** — czyli prawa zmiany granicy całej firmy. Tego eksperyment
  nie mierzy i to jest osobny, niezależny argument.
- **`destroy`.** Zachowanie przy równoległym usuwaniu reguł (czy `destroy` w jednym stanie zdmuchnie regułę
  dodaną w międzyczasie przez drugi) to osobny scenariusz — dopisz go, jeśli pierwszy wynik będzie zielony.
- **Sierot.** Repo porzucone z regułą w state to problem organizacyjny, nie techniczny.

## Wynik z organizacji labu

Pierwszy przebieg na **prawdziwym** Access Context Managerze, po naprawie fixture'ów:

```
data:        2026-08-07
przebiegi:   5
  cicha utrata reguły:    0
  konflikt głośny (eTag): 5
  bez nałożenia:          0

przebieg 1: A=0 B=1 reguł=1 | Error 400: The eTag provided '…' does not match the eTag
przebieg 2: A=1 B=0 reguł=1 | Error 400: The eTag provided '…' does not match the eTag
przebiegi 3-5: identycznie

kontrola: przy przebiegu BEZ nałożenia w czasie — oba rc=0, obie reguły obecne
```

**Wniosek:** ACM ma optymistyczną kontrolę współbieżności na eTagach. Przegrany apply pada głośno; **nic nie
znika po cichu**. Single-flight zostaje słuszny, ale argument brzmi inaczej: bez niego ~80-100% nałożonych
w czasie przebiegów kończy się błędem, czyli platforma, w której co drugi merge losowo pada. Różnica jest
praktyczna — **przy eTagu retry pomaga**, przy cichej utracie by nie pomógł.

## Wynik z waszego środowiska

Wpiszcie go tutaj po uruchomieniu — to jest dokument, który idzie do rozmowy z architektem:

```
data:        ____________
przebiegi:   ____
  cicha utrata reguły:    ____
  konflikt głośny (eTag): ____
  bez nałożenia:          ____
  nierozstrzygnięte:      ____   <- musi być 0, inaczej to nie jest pomiar
wniosek:     ____________
```
