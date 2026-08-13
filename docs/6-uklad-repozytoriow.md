# 6 · Układ repozytoriów przy 100–200 projektach

Strona do rozmowy z architektem, gdy pada pytanie: *gdzie trzymacie listę projektów w perimetrze i czy to
się nie rozsypie przy pięćdziesięciu onboardingach miesięcznie?*

Odpowiedź jest pomiarem, nie preferencją — i **zmieniła się**. Wcześniejsza wersja tej strony rekomendowała
**plik na projekt** i miała po temu twardy powód. Dziś rekomendujemy **jeden wspólny
`perimeter/projects.yaml`** — ale nie dlatego, że tamten powód zniknął, tylko dlatego, że go **domknęliśmy**.
Cały ten rozdział jest o tym, czym go domknęliśmy, bo bez tego zmiana byłaby regresem.

![Struktura folderów](diagrams/D5-struktura-folderow.png)

Źródło do edycji: [`diagrams/D5-struktura-folderow.drawio`](diagrams/D5-struktura-folderow.drawio) ·
przepływ zgłoszenia w mermaidzie: [`diagrams/D5-struktura-folderow.mmd`](diagrams/D5-struktura-folderow.mmd)

## Co gdzie ląduje

| Co | Gdzie | Właściciel | Jak często się zmienia |
|---|---|---|---|
| członkostwo projektu | [`perimeter/projects.yaml`](../template/perimeter/projects.yaml.example) — **jeden plik, lista wpisów** | Security + Networking (treść dopisuje bot z wniosku) | ciągle: 200 wpisów, ruch codzienny |
| kształt reguł ingress/egress | [`perimeter/profiles/*.yaml`](../template/perimeter/profiles/) — **4 pliki na całą organizację** | Security + Networking | rzadko, świadomie |
| baseline i access levels | [`perimeter/policy.yaml`](../template/perimeter/policy.yaml.example), [`access-levels/`](../template/perimeter/access-levels/) | Security + Networking | rzadko |
| renderer YAML → zasoby ACM | [`terraform/`](../template/terraform/) | platforma | rzadko |
| **prereq sieciowy** (PGA, strefa DNS na restricted VIP) | `terraform/` w repo **dywizji** | dywizja | jak jej infrastruktura |
| **wniosek** dywizji | `vpc-sc/request.yaml` w repo **dywizji** | dywizja | raz na projekt |

Granica wynika z odpowiedzialności, nie z wygody: **automatyzujemy granicę, prereq tylko weryfikujemy.**
Kto zmienia trasy i strefy DNS w cudzym środowisku, ten odbiera telefon, gdy tam cokolwiek przestanie
działać — także z powodów niezwiązanych z perimetrem.

## Pomiar, który kazał NIE robić jednego pliku — i co pokazał po powtórzeniu

200 istniejących projektów, 10 równoległych PR-ów, każdy dodaje jeden projekt. Przebieg **2026-08-11**,
do odtworzenia jedną komendą: [`experiments/konflikty-ukladow/`](../experiments/konflikty-ukladow/README.md).

| Układ | PR-ów bez konfliktu | Wpisów w pliku | Bramka duplikatu |
|---|---|---|---|
| jeden plik, wstawka **sortowana**, **różne** dywizje | 10/10 | 210 z 210 | zielona |
| jeden plik, dopisywanie **na końcu**, **różne** dywizje | **1/10** | 201 z 201 | zielona |
| jeden plik, **ta sama** dywizja (obie wstawki) | **1/10** | 201 z 201 | zielona |
| jeden plik + **`merge=union`**, dodawanie wpisów | 10/10 | **201 z 210** | **CZERWONA** |
| jeden plik + `merge=union`, dwie **edycje** jednego wpisu | 2/2 | 200 | **CZERWONA** |
| **plik na projekt** (kontrola) | **10/10** | 210 plików, 840 kB | — |
| **jeden plik + bot z rebase-retry** | **10/10** | 210 z 210 | zielona |

**Kolumna „wpisów" jest ważniejsza od kolumny „bez konfliktu"** i to jest główna korekta tego przebiegu:
liczba zielonych scaleń NIE jest miarą sukcesu. Wariant z `merge=union` ma komplet zielonych scaleń i gubi
dziewięć projektów.

Powtórzenie pomiaru poprawiło dwie liczby z jego wcześniejszej wersji — obie **na niekorzyść** wygodnych
tez, i żadna nie ruszyła wiersza, który rządzi decyzją:

* **Wiersz „różne dywizje" to 10/10, nie 9/10.** Dawne 9/10 było artefaktem nazw bez zera wiodącego
  (`div-1` sąsiadował po sortowaniu z `div-10`) — właściwością nazewnictwa, nie układu.
* **`merge=union` nie jest „10/10, tylko cicho duplikuje przy edycji".** Union gubi wpisy **także przy
  dodawaniu**, i to jest przypadek codzienny, nie brzegowy.

**Konflikt nie bierze się z tego, że plik jest wspólny**, tylko z tego, że dwie zmiany trafiają w te same
~3 linie kontekstu. Dywizje onboardują się **falami**, więc wiersz „ta sama dywizja" jest przypadkiem
NORMALNYM, nie skrajnym. **To on rządzi decyzją i on się nie zmienił: 1/10.**

**„To dopisujmy na końcu zamiast sortować" nie jest rozwiązaniem** — zmierzone osobno właśnie po to, żeby
bot nie rozwiązywał problemu, który dałoby się usunąć jedną linijką. Kolejność w pliku faktycznie nic nie
znaczy (klucz bierze się z treści), ale wtedy wszystkie wnioski trafiają w te same OSTATNIE linie: znowu
1/10, tym razem niezależnie od dywizji.

## Dlaczego mimo to jeden plik — i co musiało wejść razem z nim

Plik na projekt wygrywał pomiar konfliktów i przegrywał wszystko inne, im dalej od dziesięciu członków:

* **Nie ma jednego miejsca, w którym widać granicę.** „Kto jest w perimetrze" wymagało przeczytania
  katalogu, a nie pliku — i przy każdym pytaniu o stan odpowiadał `ls`, nie diff.
* **Onboarding to `git add` NOWEGO pliku.** Kanał wejściowy tworzył plik, którego wcześniej nie było, więc
  review nie miało z czym porównać wpisu; przy jednym pliku każdy wniosek jest diffem na tle wszystkich
  pozostałych i widać, że wygląda jak one.
* **Duplikat projektu dawało się złapać wyłącznie regułą porównującą PLIKI.** A ta reguła nie widziała
  najgroźniejszego przypadku: powtórnego zgłoszenia TEGO SAMEGO projektu, bo tam plik był jeden i ten sam.
  Broniło przed tym `out.exists()` w rendererze, czyli warunek o systemie plików — nie o członkostwie.
* **Sharding po dywizji, gdyby kiedyś był potrzebny, i tak wymagał zmiany renderera** (wzorzec `**/*.yaml`,
  klucz z `replace(f, "/", "-")`), czyli przeadresowania zasobów w stanie. Układ „płaski katalog" nie był
  więc etapem w drodze do czegokolwiek — był ślepą uliczką o tym samym koszcie wyjścia co teraz.

Dlatego jeden plik wchodzi **razem** z dwiema rzeczami. Nie po nich, nie „w kolejnym kroku":

### 1 · Bramka duplikatu — cztery warstwy, żadna nie jest jedyna

Duplikat wpisu przy pliku wspólnym nie jest egzotyką, tylko **normalnym wynikiem scalenia**. Bramka jest
więc fail-closed i występuje na czterech niezależnych poziomach — każdy łapie coś, czego nie widzą pozostałe:

| Warstwa | Co łapie | Czego nie łapie |
|---|---|---|
| strict loader w [`tools/projects_file.py`](../template/tools/projects_file.py.example) | duplikat KLUCZA MAPY na dowolnym poziomie — także `stage:` dwa razy wewnątrz jednego wpisu (typowy wynik `merge=union` na edycji) | duplikaty semantyczne: dwa poprawne wpisy o tym samym projekcie |
| reguły `vpcsc.onboarding` w [`policy/onboarding.rego`](../template/policy/onboarding.rego.example) | ten sam `project_id`, ten sam `project_number`, ten sam klucz `<dywizja>-<project_id>` przy różnych projektach | rozjazdy, których nie przewidzieliśmy |
| ta sama reguła: liczność listy kontra liczność mapy | KAŻDĄ ciszę — mapa zjadła wpis z dowolnego powodu | nic; to jest backstop |
| `terraform plan` | `Duplicate object key` w wyrażeniu `for` po liście | wszystko, co nie doszło do planu |

Ostatnia warstwa jest ważna nie dlatego, że jest najlepsza — komunikat ma najgorszy ze wszystkich — tylko
dlatego, że jest **nie do pominięcia**: renderer uruchamia się zawsze, a bramki da się nie odpalić.

Reguły duplikatu liczą na **surowej liście** (`members_list`), a nie na mapie członków. Mapa duplikatu nie
umie reprezentować: dwa wpisy o jednym kluczu dają jeden element i żadna reguła nie zobaczy, że drugi
istniał. To jest ten sam mechanizm, przez który `merge=union` był „cichy" — tyle że po stronie bramki.

**Dlaczego lista, a nie mapa `project_id → wpis` w samym pliku YAML.** Mapa byłaby czytelniejsza i klucz
byłby zapisany wprost. Zmierzone (Terraform 1.15.5 i PyYAML): **duplikat klucza mapy jest CICHY** —
`yamldecode` bierze ostatni wpis i nie mówi nic, `yaml.safe_load` zachowuje się identycznie. W liście ten
sam przypadek jest twardym błędem planu, zanim powstanie jakikolwiek zasób:

```
Error: Duplicate object key
Two different items produced the key "div-aaa" in this 'for' expression.
```

Czyli wybór między mapą a listą to wybór między **cichą wygraną ostatniego** a **zatrzymaniem się**. Przy
pliku, w którym „ostatni" bywa wynikiem scalenia, a wartością bywa `stage: enforced` cofnięte do `dry-run`,
to nie jest wybór stylu.

### 2 · Rebase-retry w bocie — ponowienie intencji, nie scalanie tekstu

[`.github/workflows/intake-rebase.yml`](../template/github/workflows/intake-rebase.yml.example) odpala się
po każdym merge'u dotykającym pliku członków i przenosi otwarte wnioski na bieżący `main`.

**Nie robi `git rebase`.** Rebase odtwarza PATCH, a patch dopisujący linie na końcu pliku, do którego ktoś
inny też dopisał, to dokładnie ten konflikt, którego unikamy. Bot nie musi scalać tekstu — musi **ponowić
intencję**. Intencją jest jeden wpis członka, czyli DANE, więc ponowienie to: „usiądź na nowym `main`
i dopisz wpis jeszcze raz". Dopisanie do zmienionego pliku nie ma z czym kolidować.

Co go ogranicza — bot force-pushuje gałęzie, więc każdy z tych warunków jest nośny: tylko gałęzie
`onboard/*` i `external/*`, tylko PR-y z etykietą `onboarding`, tylko gdy PR **nie zmienia niczego poza**
plikiem członków, tylko gdy różnica wobec bazy to **dokładnie jeden** dodany wpis, i tylko z
`--force-with-lease` wobec SHA odczytanego na starcie przebiegu. Gdy projekt trafił do perimetru inną drogą,
bot **nie** dopisuje go drugi raz: komentuje raz i zostawia PR człowiekowi.

### Czego `merge=union` w tym repozytorium NIE MA — i dlaczego

Jest to pierwsza rzecz, którą się proponuje przy wspólnym pliku, więc odpowiedź jest zapisana w
[`.gitattributes`](../template/gitattributes.example) obok linii, której tam nie włączyliśmy.

Union nie scala YAML-a, tylko linie — a wpisy członków mają identyczną strukturę. Dziesięć wniosków
dopisujących wpis w to samo miejsce zlepia się w **jeden** wpis z dziesięcioma polami `project_id`. Przy
edycji jest inaczej i równie źle: promocja do `enforced` i zmiana właściciela scalają się bez konfliktu,
a we wpisie zostają podwojone klucze `stage` i `owner_group` — `yaml.safe_load` czyta to **bez błędu**
i bierze ostatnie wystąpienie, więc zatwierdzona promocja po cichu wraca do `dry-run`. Pull request
przeszedł review, CI i merge, i nie zmienił niczego.

Czyli union **nie kupuje nic**: konflikt widoczny (który kosztuje zespół pół godziny rebase'u) zamienia na
plik, który bramka duplikatu i tak odrzuci — tyle że już po scaleniu i po tym, jak ktoś uwierzył, że wniosek
wszedł. Bez bramki byłaby to cicha utrata. Kolizje przy dopisywaniu rozwiązuje bot, nie sterownik scalania.

Warunek na przyszłość jest zapisany i pilnowany przez selftest: **gdyby ktoś kiedyś union włączył, wolno to
zrobić wyłącznie razem z kompletem czterech warstw bramki duplikatu — nigdy samo.**

## Co ten układ kosztuje — i czy się opłaca

Wariant „plik na projekt" daje **ten sam wynik 10/10 bez bota, bez bramki i bez ani jednego ponowienia**.
To jest uczciwa cena tej decyzji i warto ją nazwać wprost: płacimy kodem bota (`intake-rebase.yml`),
utrzymaniem czterowarstwowej bramki duplikatu i **9 ponowieniami na 10 wniosków** — za jedno miejsce,
w którym widać całą granicę, za wniosek będący diffem zamiast nowego pliku i za bramkę duplikatu, która
łapie powtórne zgłoszenie TEGO SAMEGO projektu (czego reguła porównująca pliki nie widziała nigdy).

Te 9 ponowień to **dolna granica, nie średnia**: pomiar scala sekwencyjnie, więc jedno ponowienie zawsze
wystarcza. Bot rebase'ujący się zachłannie po każdym pushu do `main` wykona ich `n(n-1)/2` = 45 przy tych
samych dziesięciu wnioskach. Dlatego `intake-rebase.yml` odpala się **wyłącznie** na push dotykający pliku
członków i przenosi każdy wniosek raz na zmianę bazy, a nie w pętli.

## CODEOWNERS: co jeden plik robi z własnością

Przy pliku na projekt `/perimeter/members/risk-* @org/risk-team` było **dostępne**. Nikt tego nie
skonfigurował — obowiązywała jedna linia na cały katalog — ale opcja istniała. Przy jednym pliku znika:
CODEOWNERS dopasowuje ŚCIEŻKI, a wszystkie wpisy leżą pod jedną.

**Co realnie tracimy: jedną przyszłą opcję, nie działającą kontrolę.** O tym, o co dywizja może wnioskować,
nigdy nie decydowała własność pliku, tylko KANAŁ:

* `snow:` — ticket weryfikowany oddzwonieniem do ServiceNow, a odpowiedź nazywa projekt,
* `pr:` — `perimeter/contributors.yaml` mapuje repozytorium na dozwolone projekty, i ten plik leży TUTAJ,
* `manual:` — approval pod CODEOWNERS; to jedyny kanał, który ta linia kiedykolwiek bramkowała.
  Procedura krok po kroku: [`8-zmiany-reczne.md` §8.1](8-zmiany-reczne.md#81-wniosek-ręczny-architekta-change_ref-manual).

Własność „dywizja nie zonboarduje cudzego projektu" trzyma się więc dokładnie tak samo jak wcześniej.

**Co to znaczy dla self-service przy kilkudziesięciu dywizjach.** Każda zmiana członkostwa potrzebuje
review zespołu sieciowego — tak jak dziś. Self-service zostaje w kształcie „dywizja składa wniosek,
platforma zatwierdza", a nie „dywizja zatwierdza własny wpis". Przy 30 dywizjach i ~50 onboardingach
miesięcznie to jest ~50 approvali, z wnioskiem wyrenderowanym maszynowo i diffem na jeden wpis — nie
50 dyskusji. Gdyby to kiedyś przestało wystarczać, wyjściem jest **shard katalogowy**
(`perimeter/projects/<dywizja>.yaml` + renderer czytający `**/*.yaml`). To zmiana ADRESÓW w stanie
Terraforma, więc idzie własnym PR-em z `moved{}` — nigdy w przelocie.

## Trzy odpowiedzi na trzy typowe zarzuty

**„Jeden plik to jeden blast-radius — literówka wywraca renderowanie WSZYSTKICH członków."** Tak, i to jest
realny koszt tej zmiany, nie retoryka. Dlatego bramka schematu i strict loader odpalają się na **pull
requeście**, a nie przy apply, a plik ma wymuszoną **postać kanoniczną** (guard w `validate.yml`), więc
narzędzia zapisujące produkują minimalny diff zamiast przepisywać 200 wpisów. Cena, którą płacimy
świadomie: **w tym pliku nie ma komentarzy** — `yaml.safe_dump` ich nie zna i pierwszy zapis bota
skasowałby je bez śladu. Uzasadnienia mieszkają w polu `change_ref` i w opisie pull requesta.

**„Chcę widzieć całość w jednym miejscu."** Teraz to jest to samo miejsce, co źródło — ale wynik nadal
istnieje osobno i nadal nie trzeba go generować: `terraform output members_enforced` oraz
`members_dry_run_only`, a dla innych repozytoriów kontrakt JSON (`contract.tf`).

**„To i tak nie skaluje się do 200 projektów."** Nie skaluje się **liczba i złożoność reguł**, nie liczba
wpisów: limit to **6000 atrybutów na konfigurację perimetru**, liczony osobno dla enforced i dry-run.
200 wpisów YAML to setki kilobajtów i milisekundy w `yamldecode`. Dlatego reguły są profilami, a budżet
mierzy się od pierwszego dnia (`tools/attribute_budget.py`).

## Gotowy przykład drugiej strony

Kompletne repozytorium dywizji — `vpc-sc/request.yaml`, workflow i README mówiące wprost, **czego zespół
nie dostaje** — leży w [`examples/division-repo/`](../examples/division-repo/README.md) tego startera.
Nie jest to snapshot do pokazania, tylko materiał do skopiowania: selftest uruchamia na nim realny
`validate-local.sh` (pozytyw) oraz ten sam wniosek z cudzego repozytorium (negatyw), więc przykład albo
działa, albo test jest czerwony.

Deklaracja dywizji to **jeden wpis**, nie plik członków — i dlatego schemat wpisu
(`schemas/member.schema.json`) jest osobny od schematu całego pliku (`schemas/projects.schema.json`).
Repozytorium dywizji waliduje u siebie dokładnie swój wpis i nie ma prawa wiedzieć, ilu jest członków.

Czego tam **nie ma**: `network.tf` i `dns.tf` dywizji. To prereq sieciowy, którego perimeter tylko
**weryfikuje** (pre-flight), a nie provisionuje — wiersz „prereq sieciowy" w tabeli wyżej. Wrzucenie ich
do przykładu sugerowałoby, że są częścią tego kanału; snippety do skopiowania są w `docs/`.
