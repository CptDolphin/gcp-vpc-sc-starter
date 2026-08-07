# Eksperyment: ile PR-ów przechodzi bez konfliktu przy 200 projektach

Rozstrzyga pytanie, które wraca przy każdej rozmowie o skali perimetru:

> **Trzymać listę projektów w jednym pliku, czy w pliku na projekt?**

Argument „jeden plik = konflikty" jest intuicyjny i przez to podejrzany — bo intuicja mówi też, że 200 plików
to za dużo. Ten skrypt zamienia obie intuicje w liczbę.

## Uruchomienie

```bash
./run.sh /tmp/vpcsc-konflikty
```

Koszt: kilkanaście sekund, wszystko lokalnie, żadnej chmury. Skrypt zakłada trzy repozytoria z **200
istniejącymi projektami**, w każdym robi **10 gałęzi** (każda dodaje jeden projekt, tak jak dziesięć zespołów
składających wnioski tego samego dnia) i liczy, ile scaleń przechodzi bez konfliktu.

## Wynik ostatniego przebiegu

| Układ | PR-ów bez konfliktu |
|---|---|
| A. jeden `projects.yml`, projekty z **różnych** dywizji | 9/10 |
| A-worst. jeden `projects.yml`, 10 PR-ów z **tej samej** dywizji | **1/10** |
| B. jeden plik + `merge=union` w `.gitattributes` | 10/10 |
| C. plik na projekt (210 plików, 840 kB) | **10/10** |

## Jak to czytać

**Konflikt nie bierze się z tego, że plik jest wspólny**, tylko z tego, że dwie zmiany trafiają w te same
~3 linie kontekstu. Przy sortowanej liście projekty jednej dywizji lądują obok siebie — a dywizje onboardują
się falami, nie po jednym projekcie z losowego miejsca. Dlatego wiersz **A-worst** jest ważniejszy niż A:
najgorszy przypadek jest przypadkiem normalnym.

**`merge=union` (wiersz B) nie jest darmowym rozwiązaniem** i drugi skrypt (`run.sh` sekcja B-edit) to
pokazuje: przy **edycji** tego samego wpisu w dwóch PR-ach (promocja do `enforced` i zmiana właściciela)
oba scalenia przechodzą i zostają dwa wiersze na jeden projekt. Dla renderera to dwa klucze `for_each` na
ten sam zasób ACM, czyli dwóch właścicieli jednego wpisu — każdy `apply` kasuje cudzy. Union zamienia
konflikt **widoczny** na **cichy**, więc wchodzi wyłącznie razem z bramką na duplikaty:

```bash
grep -o 'project: [a-z0-9-]*' projects.yml | sort | uniq -d   # musi być pusty
```

## Czego ten eksperyment NIE mierzy

Kosztu przeglądania katalogu z 200 plikami (rozwiązuje go katalog na dywizję) ani **budżetu 6000 atrybutów
na konfigurację perimetru** — a to jest realny limit skali, nie liczba plików. Do tego drugiego jest
`tools/attribute_budget.py`.
