# Eksperyment: dwa stany Terraform, jeden perimetr

Rozstrzyga jedno pytanie, które wraca przy każdej rozmowie o architekturze:

> **Czy dwa repozytoria z osobnymi stanami mogą bezpiecznie dodawać własne reguły do tego samego perimetru?**

Argument teoretyczny brzmi: nie, bo Access Context Manager przepisuje politykę jako całość
(read-modify-write), a blokada Terraforma jest per-state, nie per-obiekt w chmurze. Ten eksperyment zamienia
ten argument w **wynik pomiaru** — albo go obala.

**Uruchom to, zanim ktoś podejmie decyzję na podstawie mojej opinii.** Jeśli obie reguły przetrwają, model
można poluzować. Jeśli jedna zniknie, masz dowód mocniejszy niż jakikolwiek cytat z dokumentacji: *sprawdziliśmy, ginie.*

## Czego wymaga

- perimetr w organizacji, w trybie **dry-run** (żeby eksperyment nie mógł niczego zablokować),
- tożsamość z `accesscontextmanager.servicePerimeters.update`,
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
./run.sh
```

`run.sh` robi dokładnie to:

1. `terraform apply` w `state-a/` → dodaje regułę `race-test-alpha`,
2. `terraform apply` w `state-b/` → dodaje regułę `race-test-beta`,
   **oba uruchomione równolegle**, w tle, bez żadnej synchronizacji między nimi,
3. czeka na oba,
4. czyta perimetr z API i sprawdza, **ile reguł race-test-\* faktycznie w nim jest**,
5. sprząta (usuwa oba zasoby).

## Jak czytać wynik

| Wynik | Co to znaczy | Konsekwencja |
|---|---|---|
| `2 reguły` | równoległe patche się nie zgubiły w tym przebiegu | powtórz 5–10 razy; wyścig jest zależny od czasu, więc jeden zielony przebieg **nie dowodzi bezpieczeństwa** |
| `1 reguła` | jedna zmiana została nadpisana | model „każde repo aplikuje" jest wykluczony — masz dowód |
| `0 reguł` albo błąd `409` | konflikt wersji zasobu | to samo wnioskowanie: równoległość nie jest obsługiwana |

**Uwaga na interpretację:** brak utraty w jednym przebiegu to *nie* dowód poprawności. Wyścig to zjawisko
zależne od przeplotu — przy sekwencyjnym wykonaniu (A kończy, potem B czyta) obie reguły przetrwają zawsze.
Dlatego `run.sh` uruchamia je równolegle i dlatego warto powtórzyć kilka razy. Jeden przebieg, w którym reguła
ginie, przesądza sprawę; dziesięć, w których nie ginie, mówi tylko „nie trafiliśmy w okno".

## Co to NIE testuje

- **Uprawnień.** Nawet gdyby wyścigu nie było, każde takie repozytorium potrzebuje
  `servicePerimeters.update` na **organizacji** — czyli prawa zmiany granicy całej firmy. Tego eksperyment
  nie mierzy i to jest osobny, niezależny argument.
- **`destroy`.** Zachowanie przy równoległym usuwaniu reguł (czy `destroy` w jednym stanie zdmuchnie regułę
  dodaną w międzyczasie przez drugi) to osobny scenariusz — dopisz go, jeśli pierwszy wynik będzie zielony.
- **Sierot.** Repo porzucone z regułą w state to problem organizacyjny, nie techniczny.

## Wynik z waszego środowiska

Wpiszcie go tutaj po uruchomieniu — to jest dokument, który idzie do rozmowy z architektem:

```
data:        ____________
przebiegi:   ____ / ____ (utrata reguły / wszystkich)
wniosek:     ____________
```
