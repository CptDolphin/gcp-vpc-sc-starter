# Eksperyment: ile PR-ów przechodzi bez konfliktu przy 200 projektach

Rozstrzyga pytanie, które wraca przy każdej rozmowie o skali perimetru:

> **Trzymać listę projektów w jednym `perimeter/projects.yaml`, czy w pliku na projekt?**

Argument „jeden plik = konflikty" jest intuicyjny i przez to podejrzany — bo intuicja mówi też, że 200 plików
to za dużo. Ten skrypt zamienia obie intuicje w liczbę, i rozbija „jeden plik" na warianty, bo każdy z nich
bywa proponowany jako rozwiązanie: dopisywanie na końcu zamiast sortowania, sterownik `merge=union`, bot
z rebase-retry.

## Uruchomienie

```bash
./run.sh /tmp/vpcsc-konflikty
```

Koszt: 25-90 s zależnie od obciążenia maszyny — skrypt zakłada osiem repozytoriów git i robi w nich 108
commitów, więc dominują wywołania gita, nie obliczenia. Wszystko lokalnie, żadnej chmury, żadnych uprawnień.
Wymaga `git`, `python3` i `pyyaml`.

Skrypt kończy się kodem `!= 0`, gdy przebieg **nie jest pomiarem** — na przykład gdy kontrola dla wariantu D
wyszła 10/10 i D nie ma czego poprawiać, gdy bramka duplikatów okazała się czerwona na wszystkim, albo gdy
wariant B-edit nie pokazał cichej utraty. To nie jest test hipotezy: wynik niewygodny jest w porządku, wynik
pusty nie.

## Wynik ostatniego przebiegu

**Data: 2026-08-11.** 200 istniejących projektów, 10 równoległych PR-ów (gałęzie odbite od tego samego
commita), każdy dodaje jeden projekt.

| Wariant | Bez konfliktu | Wpisów w pliku | Ponowień | Bramka duplikatów |
|---|---|---|---|---|
| **A** — jeden plik, wstawka **sortowana**, projekty z **różnych** dywizji | 10/10 | 210 z 210 | – | ZIELONA |
| **A** — jeden plik, dopisanie **na końcu**, projekty z **różnych** dywizji | **1/10** | 201 z 201 | – | ZIELONA |
| **A-worst** — jeden plik, wstawka **sortowana**, **ta sama** dywizja | **1/10** | 201 z 201 | – | ZIELONA |
| **A-worst** — jeden plik, dopisanie **na końcu**, **ta sama** dywizja | **1/10** | 201 z 201 | – | ZIELONA |
| **B** — jeden plik + `merge=union`, dodawanie wpisów | 10/10 | **201 z 210** | – | **CZERWONA** |
| **B-edit** — `merge=union`, dwa PR-y **edytujące ten sam wpis** | 2/2 | 200 z 200 † | – | **CZERWONA** |
| **C** — plik na projekt (kontrola) | **10/10** | 210 plików, 840 kB | – | – |
| **D** — jeden plik + **bot z rebase-retry** | **10/10** | 210 z 210 | **9** | **ZIELONA** |

Kolumna „wpisów" to `ile jest w pliku` z `ile powinno być` — a „powinno" liczy się jako 200 plus liczba
scaleń, **które przeszły**: odrzucony PR ma nie wnieść nic, zmergowany dokładnie jeden wpis. Dlatego wiersz
A z 1/10 ma 201 z 201 i jest w porządku (dziewięć PR-ów wróciło do zespołów po rebase), a wiersz B z 10/10
ma 201 z 210 i jest awarią. **To jest główna lekcja tego przebiegu: liczba zielonych scaleń nie jest miarą
sukcesu.** Wariant B ma komplet zielonych scaleń i gubi dziewięć projektów.

† B-edit nie dodaje wpisów, tylko edytuje jeden istniejący — liczba wpisów się zgadza, a mimo to plik jest
zepsuty w środku wpisu. Dlatego bramka nie może liczyć samych wpisów.

## Jak to czytać

### 1. Konflikt nie bierze się ze wspólnego pliku, tylko z sąsiedztwa linii

Wiersz A z wstawką sortowaną wygląda niewinnie — 10/10, żadnego problemu. To jest pułapka, nie wynik:
dziesięć PR-ów z dziesięciu **różnych** dywizji trafia w dziesięć miejsc oddalonych o kilkadziesiąt linii,
więc nie mają jak się pobić. Tak onboarding nie wygląda. **Dywizje wchodzą falami** — jeden zespół składa
dziesięć wniosków w tym samym tygodniu — a sortowanie po `<dywizja>-<project_id>` kładzie całą falę
w jednym miejscu pliku. Stąd 1/10 w wierszu A-worst. **Najgorszy przypadek jest przypadkiem normalnym.**

### 2. „To nie sortujmy, dopisujmy na końcu" nie jest rozwiązaniem

Kolejność wpisów w pliku i tak nic nie znaczy — renderer kluczuje po treści (`<dywizja>-<project_id>`),
nie po pozycji. Kusi więc, żeby zrezygnować z sortowania i dopisywać nowy wpis na końcu pliku, skoro to
sortowanie produkuje sąsiedztwo. **Zmierzone: 1/10, i to niezależnie od dywizji.** Wszystkie PR-y trafiają
wtedy w te same ostatnie linie, więc zamiast dziesięciu kolizji w jednej dywizji mamy dziesięć kolizji na
końcu pliku. Ten wiersz istnieje w tabeli po to, żeby wariant D nie był rozwiązaniem problemu, który dałoby
się usunąć jedną linijką — gdyby wystarczyło zmienić miejsce wstawki, nie budowalibyśmy bota.

### 3. `merge=union` jest gorszy, niż się wydaje na pierwszy rzut oka

`union` nie scala treści — dla spornego fragmentu wypisuje po prostu obie wersje, jedna za drugą. Przy
**dodawaniu** wpisów brzmi to jak dokładnie to, czego chcemy („weź oba wnioski"), i pierwsza wersja tego
eksperymentu tak to opisywała. Pomiar to obalił. Dziesięć wstawek w to samo miejsce union zlepia w **jeden**
wpis z dziesięcioma polami `project_id`:

```yaml
  - division: example-division-07
    project_id: prj-example-new-01
    project_number: "…0001"
    project_id: prj-example-new-02
    project_number: "…0002"
    …
    project_id: prj-example-new-10
    project_number: "…0010"
    owner_group: grp-example-division-07@example.com
    stage: dry-run
    profiles: []
```

Dziesięć PR-ów zmergowanych, dziesięć zielonych pipeline'ów, **dziewięć projektów nie ma w perimetrze**.
Nikt nie dostał błędu.

Przy **edycji** tego samego wpisu jest inaczej i równie źle. Dwa PR-y — promocja (`stage: dry-run` →
`enforced`) i zmiana właściciela — oba scalają się bez konfliktu, a w pliku zostaje wpis z podwojonymi
kluczami:

```yaml
  - division: example-division-07
    project_id: prj-example-0008
    project_number: "…0008"
    owner_group: grp-example-division-07@example.com
    stage: enforced                                       # z PR-a promocyjnego
    owner_group: grp-example-division-security@example.com # z PR-a właścicielskiego
    stage: dry-run                                        # ...i jego wersja stage
    profiles: []
```

> Numery projektów w obu wycinkach są skrócone do czterech ostatnich cyfr. W pliku są pełne, 12-cyfrowe —
> skrót jest tylko po to, żeby README nie niósł numerów spoza listy placeholderów repozytorium.

I teraz najważniejsze zdanie o tym wariancie. **`yaml.safe_load` czyta ten plik BEZ BŁĘDU** — na duplikacie
klucza mapy po cichu bierze ostatnie wystąpienie. Zmierzone, jest w wyjściu skryptu:

```
safe_load: wczytal plik BEZ bledu, wpisow po parsowaniu: 200
safe_load: prj-example-0008 -> stage='dry-run', owner_group='grp-example-division-security@example.com'
PR promocyjny zmergowany, a po scaleniu stage=dry-run (zatwierdzono: enforced)
```

Czyli: PR promocyjny **przeszedł review, przeszedł CI i został zmergowany** — i nie zmienił niczego.
Projekt zostaje w `dry-run`, choć w historii repozytorium widnieje zatwierdzona promocja. To jest cały sens
wiersza B-edit: **union zamienia konflikt widoczny na cichy.** Konflikt widoczny kosztuje zespół pół godziny
rebase'u; konflikt cichy kosztuje rozjazd między tym, co zatwierdzono, a tym, co stoi na granicy — i nie ma
momentu, w którym ktokolwiek go zauważy. Dlatego `union` na tym pliku wchodzi **wyłącznie** razem z bramką
duplikatów, i dlatego ta bramka nie może być zbudowana na `safe_load`.

### 4. Bot z rebase-retry (wariant D) — jedyne działające wyjście dla wspólnego pliku

Bot **nie scala tekstu — ponawia INTENCJĘ.** Gdy jego gałąź nie wchodzi w nowy `main`, wyrzuca własny commit
i renderuje swój wpis jeszcze raz, na świeżym pliku:

```bash
git fetch origin main
git reset --hard origin/main       # wyrzuca swój commit — nie próbuje go ratować
<ponownie dopisz swój wpis do pliku na NOWYM main>
git commit
```

Dopisanie bloku na końcu pliku o zmienionej treści udaje się **zawsze**, bo to nie jest replay patcha, tylko
ponowne wykonanie tej samej operacji na nowym wejściu. Dlatego ten wariant nie ma przypadku „nie da się":
**10/10, 210 wpisów, bramka zielona.**

Koszt jest w kolumnie „ponowień": **9**. Dziewięć z dziesięciu PR-ów musiało się przerenderować, bo `main`
ruszył, zanim doszła ich kolej. To jest **dolna granica**, nie średnia: skrypt scala sekwencyjnie (jeden PR
w całości, potem następny), więc jedno ponowienie zawsze wystarcza. Bot rebase'ujący się zachłannie po
każdym pushu do `main` wykona ich `n(n-1)/2` = 45 przy tych samych dziesięciu PR-ach. Do tego dochodzi kod
bota i utrzymanie bramki duplikatów.

Wariant **C** daje ten sam wynik (10/10) bez bota, bez bramki i bez ponowień — 210 plików zajmuje 840 kB.

### 5. Dlaczego wynik D jest sprawdzalny, a nie tylko ładny

Warianty **A-worst z dopisywaniem na końcu** i **D** mają bajt w bajt ten sam plik wejściowy, te same
gałęzie i tę samą kolejność scalania. **Różni je wyłącznie zachowanie bota**: 1/10 kontra 10/10. Bez tej
pary „D daje 10/10" nie znaczyłoby nic — 10/10 daje też układ, w którym nie ma czego rozwiązywać (patrz
wiersz A). Skrypt sprawdza to jako asercję i przerywa, gdy kontrola wyjdzie zdegenerowana.

## Bramka duplikatów (`sprawdz_duplikaty.py`)

**Czym jest:** samodzielny odpowiednik bramki, postawiony tutaj po to, żeby eksperyment dało się uruchomić
bez reszty repozytorium — i żeby wynik wariantu B-edit dało się pokazać jako **czerwoną bramkę**, a nie jako
opinię. Sprawdza cztery rzeczy: duplikat klucza mapy na dowolnym poziomie, powtórzony `project_id`,
powtórzony `project_number` i powtórzony klucz `<division>-<project_id>` (czyli klucz `for_each` renderera).

**Czym NIE jest:** tą samą bramką, która realnie jedzie w materiale. Tam plik czyta i pilnuje
`tools/projects_file.py` (jedno miejsce wczytywania, własny loader, kanoniczny zapis), duplikaty odrzucają
reguły `policy/onboarding.rego` puszczane conftestem, a kształt wpisu pilnuje schemat JSON. Ten skrypt jest
**osobną, drugą implementacją tych samych czterech własności** — celowo, żeby eksperyment nie wymagał
reszty repozytorium i dał się uruchomić z samego katalogu `experiments/`. Zgodność wyniku obu implementacji
to nie jest dowód poprawności żadnej z nich: **eksperyment nie zastępuje testów tamtych bramek** i niczego
o nich nie orzeka. Pokazuje wyłącznie, że własność, której pilnują, w układzie jednoplikowym jest realnie
łamana — i to przez zwykłe, zatwierdzone pull requesty, nie przez błąd człowieka.

Jedna rzecz z tego skryptu jest jednak przenośna i warto ją znać przy pisaniu każdego walidatora tego pliku:
**`yaml.safe_load` nie wykrywa duplikatu klucza mapy.** Cicho bierze ostatnie wystąpienie. Bramka zbudowana
na `safe_load` przepuściłaby cały wariant B-edit, bo dla niej ten plik jest poprawny. Stąd własna podklasa
`SafeLoader` z nadpisanym `construct_mapping` — biblioteka nie ma na to opcji.

W skrypcie bramka jedzie na **każdym** wariancie jednoplikowym, a jej werdykty są **asercjami**, nie
obserwacjami. Wychodzi zielona pięć razy (cztery warianty A i wariant D) i czerwona dwa razy (B, B-edit)
w tym samym przebiegu — i skrypt sprawdza właśnie to rozróżnienie. **Bramka czerwona zawsze nie jest
bramką, tylko szumem**; bramka, która nigdy nie zapala się na czerwono, nie chroni niczego.

Do tego dochodzi asercja, której bramka sama nie zrobi: po scaleniach w pliku ma być `200 + liczba scaleń,
które przeszły`. Wariant łamiący ten niezmiennik gubi zatwierdzone wnioski bez błędu — i wtedy bramka
**musi** być czerwona, inaczej jest ślepa. Tak właśnie wychodzi na wariancie B.

### Test negatywny kontroli

Kontrola, która nigdy nie zapala się na czerwono, jest ozdobą. Obie da się sprawdzić w minutę, na kopii
skryptu (nie w repo):

| Co zepsuć | Co ma się stać |
|---|---|
| w `sprawdz_duplikaty.py` podmienić `naruszenia = sprawdz(argv[1])` na `naruszenia = []` | `rc=1`, trzy kontrole padają: *BRAMKA NIE DZIAŁA* (B-edit zielony), *BRAMKA ŚLEPA* (B ma 201 z 210 i przechodzi), *BRAMKA NIE ROZRÓŻNIA* |
| w `run.sh` ustawić `MAX_PROB=1` (bot przestaje ponawiać) | `rc=1`, D spada do 1/10 i pada kontrola *HIPOTEZA O REBASE-RETRY OBALONA* — bo D zrównuje się z A-worst |

Oba przebiegi zostały uruchomione i dały dokładnie te wyniki. To jest jedyny powód, dla którego zieleń
w sekcji „kontrole" cokolwiek znaczy.

## Co się zmieniło względem pierwszej wersji tego eksperymentu

- **Wpis jest wielolinijkowy** (blok YAML, 6 linii), a nie jednolinijkowy. To nie jest kosmetyka: git wykrywa
  konflikt na liniach, z trzema liniami kontekstu, więc **rozmiar wpisu wprost wyznacza**, jak blisko siebie
  muszą trafić dwa PR-y, żeby się pobiły. Realny plik członka ma kilkanaście linii; pomiar na wpisach
  jednolinijkowych mierzył format, którego i tak nikt nie użyje.
- **Wiersz A-worst istnieje w skrypcie**, a nie tylko w tabeli. Poprzednia wersja README podawała dla niego
  liczbę, której skrypt nie umiał odtworzyć — czyli liczbę bez dowodu.
- **Wiersz A z sortowaniem wychodzi teraz 10/10, nie 9/10.** Wcześniejsze 9/10 brało się z nazw dywizji bez
  zera wiodącego (`div-1`, `div-10`): sortowanie tekstowe wstawiało `div-10` tuż obok klastra `div-1`, więc
  jedna kolizja była artefaktem nazewnictwa, nie właściwości układu.
- **Wiersz B nie brzmi już „10/10, bezpieczne przy dodawaniu".** Union przy dodawaniu gubi wpisy — to jest
  zmierzone w tym przebiegu i zastąpiło wcześniejsze założenie.
- **Doszły warianty z dopisywaniem na końcu i wariant D**, bez których „bot rozwiązuje problem" byłoby tezą,
  a nie pomiarem.

## Czego ten eksperyment NIE mierzy

- **Kosztu przeglądania katalogu z 200 plikami** — rozwiązuje go katalog na dywizję, ale to wymaga zmiany
  wzorca `fileset` i kluczy `for_each`, czyli osobnego PR-a z `moved{}`.
- **Budżetu 6000 atrybutów na konfigurację perimetru** — a to jest realny limit skali, nie liczba plików.
  Do tego jest `tools/attribute_budget.py`.
- **Zachowania platformy hostującej.** Mierzymy `git merge` lokalnie. Kolejka merge'y na serwerze (merge
  queue) zmienia liczbę ponowień w wariancie D, ale nie zmienia tego, które warianty w ogóle się scalają.
- **Poprawności produkcyjnych bramek.** Patrz zastrzeżenie przy `sprawdz_duplikaty.py`.
