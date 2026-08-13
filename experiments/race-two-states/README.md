# Eksperyment: dwa stany Terraform, jeden perimetr

Rozstrzyga jedno pytanie, które wraca przy każdej rozmowie o architekturze:

> **Czy dwa repozytoria z osobnymi stanami mogą bezpiecznie dodawać własne reguły do tego samego perimetru?**

Argument teoretyczny brzmi: nie, bo Access Context Manager przepisuje politykę jako całość
(read-modify-write), a blokada Terraforma jest per-state, nie per-obiekt w chmurze. Ten eksperyment zamienia
ten argument w **wynik pomiaru** — albo go obala.

**U nas odpowiedź brzmi: ZALEŻY OD ZASOBU — i to jest ważniejsze niż którakolwiek z dwóch skrajności.**
Reguła w konfiguracji **dry-run** (i każde **tworzenie** reguły) trafia na optymistyczną kontrolę eTagów:
przegrany apply pada **głośno**, nic nie znika. Reguła **egzekwowana aktualizowana w miejscu** — przeciwnie:
**gubi zmianę po cichu, przy dwóch zielonych apply**. Patrz [§Wynik z organizacji labu](#wynik-z-organizacji-labu).

**Uruchom to, zanim ktoś podejmie decyzję na podstawie mojej opinii** — łącznie z opinią zapisaną wyżej.
Ten dokument dwa razy niósł wniosek, który potem obalił własny pomiar.

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

Mimo to: **uruchom na perimetrze JEDNORAZOWYM, bez ani jednego członka**, nie na tym, do którego dołączają
dywizje. Perimetr bez członków nie obejmuje żadnego projektu, więc nie ma czego zepsuć — blast-radius jest
zerowy, a po pomiarze kasujesz go jedną komendą:

```bash
gcloud access-context-manager perimeters dry-run create t_race \
  --policy="$TF_VAR_policy_id" --perimeter-title="race (jednorazowy, ZERO czlonkow)" \
  --perimeter-type=regular --perimeter-restricted-services=storage.googleapis.com
# ... pomiar ...
gcloud access-context-manager perimeters delete t_race --policy="$TF_VAR_policy_id" --quiet
```

**Uwaga na sieroty.** `apply` przerwany w locie zostawia regułę w API bez odpowiednika w stanie. ACM pilnuje
**unikalności tytułu**, a `terraform import` dla tych zasobów **nie istnieje**, więc każde ponowienie pada na
`existing object was already found`. `run.sh` sprząta takie pozostałości sam, przed każdym przebiegiem —
i **wyłącznie** reguły `race-test-*`, żeby nie zabrać cudzych.

## Krok po kroku

```bash
export TF_VAR_policy_id=123456789          # gcloud access-context-manager policies list --organization=<ORG>
export TF_VAR_perimeter_name=test_race     # perimetr TESTOWY, nie produkcyjny
export IDENTITY_A=serviceAccount:sa-example-a@prj-example.iam.gserviceaccount.com  # MUSI istnieć
export IDENTITY_B=serviceAccount:sa-example-b@prj-example.iam.gserviceaccount.com  # MUSI istnieć, inne niż A

# Provider `google` na LOKALNYCH ADC pada na accesscontextmanager.googleapis.com z `403 SERVICE_DISABLED`
# („requires a quota project"), bo ADC nie mają projektu rozliczeniowego. Bez tego mierzysz swoje
# środowisko, nie API — dokładnie ten błąd wywrócił pierwszy przebieg tego eksperymentu na żywo.
export USER_PROJECT_OVERRIDE=true GOOGLE_BILLING_PROJECT=<projekt-z-wlaczonym-ACM>

# NAJPIERW kontrola anty-tautologiczna. Bez niej brak reguły po przebiegu równoległym nie odróżnia
# „zgubił wyścig" od „zepsuty scenariusz". MUSI wyjść komplet, inaczej wynik równoległy nic nie znaczy.
SEKWENCYJNIE=1 ./run.sh 3

# Dopiero teraz pomiar właściwy.
./run.sh 5
```

> **Ten eksperyment mierzy WYŁĄCZNIE ścieżkę dry-run** (`..._dry_run_ingress_policy`), bo tylko ona jest
> bezpieczna do uruchomienia na cudzej organizacji: reguła dry-run niczego nie przepuszcza ani nie blokuje.
> Zachowanie reguł **egzekwowanych** jest inne i **gorsze** (patrz wynik niżej) — jeśli chcesz je zmierzyć,
> zrób to na perimetrze **bez ani jednego członka**, podmieniając zasób na `..._ingress_policy`.

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
| **cicha utrata** | **którakolwiek** strona ma `rc=0`, a jej reguły nie ma w API | **jedyny** wynik potwierdzający tezę o cichym nadpisaniu. Sprawdzane **per strona**, niezależnie od drugiej: „zgłosił sukces, a jego zmiany nie ma" jest dowodem nadpisania także wtedy, gdy druga strona padła. Sam retry nie wystarczy — trzeba weryfikować stan po każdym apply. Kończy się kodem `1` |
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

Przebieg z **2026-08-07** (5 przebiegów, „konflikt głośny 5/5") **nie jest już cytowany jako dowód**:
rozpoznawał konflikt przez `grep -i etag` po całym logu, a plan Terraforma drukuje
`+ etag = (known after apply)`, więc **każda** awaria wychodziła jako konflikt eTagu. Zastępuje go pomiar
z **2026-08-13** na perimetrze jednorazowym **bez ani jednego członka** (`t_race_1949`, skasowany po pomiarze).

| ścieżka | przebiegi | `Error 400` eTag | „inconsistent result" | **cicha utrata** | oba OK + komplet |
|---|---|---|---|---|---|
| dry-run, **tworzenie** reguły | 5 | 4 | 0 | **0** | 1 |
| dry-run, **zmiana** reguły (ForceNew ⇒ replace) | 10 | 10 | 0 | **0** | 0 |
| egzekwowana, **tworzenie** reguły | 3 | 1 | 0 | **0** | 2 |
| egzekwowana, **zmiana w miejscu** (`Update` w schemacie) | 24 | 0 | 15 | **5** | 4 |
| KONTROLA sekwencyjna (`SEKWENCYJNIE=1`) | 6 | — | — | **0** | 6 |

**Wniosek — dwustronny, i to jest cała treść tego eksperymentu:**

1. **Ścieżka dry-run i każde tworzenie reguły**: optymistyczna kontrola działa, przegrany pada głośno.
   Komunikat sam nazywa jednostkę wyłączności — **politykę, nie perimetr**:
   `Error 400: The eTag provided '…' does not match the eTag of the current version of the Access Policy,
   which is '…'. The operation will not be performed.`
2. **Ścieżka reguły egzekwowanej aktualizowanej w miejscu**: z 9 przebiegów, w których **oba** applye
   zgłosiły sukces, **5 skończyło się brakiem jednej ze zmian w API** — bez błędu, przy dwóch zielonych
   przebiegach. Pozostałe padały komunikatem, który **nie mówi nic o współbieżności**:
   `Provider produced inconsistent result after apply … Root object was present, but now absent.`
   Ten sam komunikat zobaczysz, gdy ktoś naprawdę skasował Twoją regułę — z treści nie da się ich odróżnić.

**Czemu ścieżki różnią się zachowaniem:** warianty `..._dry_run_*` **nie mają `Update`** w schemacie
providera (każda zmiana to ForceNew ⇒ skasuj i utwórz), warianty egzekwowane `Update` mają i idą ścieżką
read-modify-write na całej liście reguł. Mechanizm utraty jest **hipotezą** — fakt utraty jest pomiarem.

**Co z tego wynika dla decyzji:** single-flight zostaje, ale jako kontrola **poprawności**, nie wygody.
**Retry na eTagu nie jest zamiennikiem** — leczy wyłącznie ścieżkę, która zgłasza błąd; na ścieżce cichej
nie ma czego ponowić, a retry podniósłby odsetek przebiegów „oba OK", czyli dokładnie tych, w których
zmierzyliśmy utratę. **Jednostką wyłączności jest access policy**: zapis do perimetru sąsiedniego unieważnia
eTag perimetru nietkniętego (zmierzone), więc podział na dwa perimetry **nie daje** drugiego toru zapisu.

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
