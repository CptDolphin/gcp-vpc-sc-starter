#!/usr/bin/env python3
"""Czy każda decyzja, na którą powołuje się to repozytorium, ma tutaj swoje UZASADNIENIE.

DLACZEGO TO ISTNIEJE — I DLACZEGO NIE ZAŁATWIA TEGO `starter-drift`. Repozytorium perimetru jest
rozpakowanym starterem plus wartościami środowiska. `starter-drift` porównuje świadomie sam WSKAŹNIK
(commit startera zapisany w `.starter-sync` kontra `main` startera), bo porównanie drzewa świeciłoby
na czerwono zawsze i legalnie — wartości środowiska są dokładnie tym, co to repo ma mieć, a szablon nie.
Wskaźnik odpowiada więc na pytanie „czy ktoś przeniósł commity", a NIE na pytanie „czy przeniósł
wszystko, co w nich było".

ZMIERZONE, i to jest powód powstania tego pliku: wskaźnik wskazywał aktualny commit `main` startera —
gate zielony — a `docs/0-decyzje.md` NIE MIAŁO dwóch całych decyzji. Jedna z nich (bramka na ścieżce
mutatora) była w tym samym repo cytowana w DZIEWIĘCIU miejscach: w dwóch workflowach, w regułach OPA,
w akcji bramki promocji. Kod odsyłał do uzasadnienia, którego w repo nie było, a wszystko było zielone.
Sync „commit po commicie" nie ma jak tego zobaczyć, bo każdy pojedynczy przeniesiony commit wygląda na
kompletny; niekompletność widać dopiero na zbiorze.

DWA SPRAWDZENIA, BO ZNIKNĄĆ MOŻNA NA DWA SPOSOBY:

  domyślne (`bramki-tresci`, oba tory — pull request i apply)
      Każdy numer decyzji CYTOWANY gdziekolwiek w repo ma tutaj swoją sekcję. Łapie decyzję, do której
      kod się odwołuje, a której nikt nie przeniósł. Nie potrzebuje sieci ani startera — pyta wyłącznie
      o wewnętrzną spójność, więc może stać przy pozostałych bramkach treści i biec na każdym wniosku.

  `--wzgledem <plik>` (`starter-drift`, raz w tygodniu i na żądanie)
      Zbiór decyzji tutaj pokrywa zbiór decyzji w starterze. Łapie decyzję, której NIKT NIE CYTUJE —
      taką, co do której nie ma odsyłacza w kodzie, więc sprawdzenie wyżej przepuści ją w ciszy.
      To jest dokładnie ta połowa, którą zgubił sync opisany wyżej.

TRZECIE SPRAWDZENIE (też domyślne): CZY REPOZYTORIUM MÓWI O SWOIM REJESTRZE PRAWDĘ. Oba sprawdzenia wyżej
pytają, czy sekcja ISTNIEJE. Żadne nie pyta, czy zdanie „`DEC-1`…`DEC-N`" albo „N rozstrzygnięć" opisuje
zbiór, który naprawdę tam leży — a to rozjeżdżało się TRZY RAZY (zakres w nagłówku szedł `…18` → `…19` →
`…23`, w każdym z tych momentów mniejszy od realnego) i za każdym razem naprawa była ręczna, bo nic tej
liczby nie mierzyło. Czwarty raz kosztował już więcej niż rozjazd: dwie gałęzie rozwiązały go przeciwnie
(jedna podbiła liczbę, druga usunęła ją z uzasadnieniem), a scalenie zostawiło w rejestrze DWA nagłówki
H1 — stary i nowy — przy obu bramkach na zielono. Sprawdzamy więc trzy rzeczy naraz:

  * **deklaracja zakresu** `DEC-a`…`DEC-b` GDZIEKOLWIEK w repo ma się zgadzać z KOŃCAMI zbioru sekcji;
  * **licznik w preambule** rejestru („N rozstrzygnięć", też słownie) — z liczbą sekcji;
  * **rejestr ma dokładnie JEDEN nagłówek H1** — dwa znaczą rozwiązany na oślep konflikt merge'a.

CZWARTE SPRAWDZENIE (też domyślne): CZY KAŻDY NUMER WYSTĘPUJE DOKŁADNIE RAZ. Trzy sprawdzenia wyżej pytają
o ISTNIENIE sekcji, a mapa numerów zwija powtórzenia do jednego klucza — więc drugi `## DEC-27` był dla nich
wszystkich niewidzialny, łącznie z licznikiem. Numery przydziela KOLEJNOŚĆ MERGE'A, a nadaje je odczyt
„ostatnia sekcja + 1"; gdy dwie gałęzie czytają ten sam stan, obie biorą tę samą liczbę. Zmierzone w jeden
dzień: CZTERY przenumerowania DEC (19, 24, 27, 28), każde ręczne i każde po scaleniu.

Najtańszą naprawą każdego z nich jest USUNIĘCIE liczby z prozy: zbiór sekcji jest źródłem prawdy, a zdanie
o jego rozmiarze utrzymuje wyłącznie czyjaś uwaga. Bramka nie zakazuje jej wpisać — pilnuje, żeby wpisana
przestała być zielona w dniu, w którym przestaje być prawdziwa (DEC-20).

CZEGO ŚWIADOMIE NIE SPRAWDZAMY (żeby zielony wynik nie znaczył więcej, niż znaczy):

  * TREŚCI sekcji. Ten sam numer może tu brzmieć inaczej niż w starterze i zwykle brzmieć musi —
    decyzja opisuje wdrożenie, a wdrożenia różnią się od szablonu. Porównanie treści przywróciłoby
    bramkę zawsze-czerwoną, czyli to, czego `starter-drift` unika z premedytacją.
  * NUMERACJI ciągłej. Dziura w numerach jest legalna: decyzja może zostać wycofana, a numery pochodzą
    ze startera i nigdy nie są przenumerowywane. Bramka pyta o POKRYCIE zbioru, nie o jego kształt —
    także w sprawdzeniu zakresu, które porównuje wyłącznie KOŃCE (`min` i `max`), nigdy ciągłość.
  * TREŚCI deklaracji poza zakresem i licznikiem. „Kilkanaście decyzji" przejdzie, bo nie jest liczbą.
    Bramka domyka formę, w której to realnie gniło — zakres i liczebnik — a nie prozę w ogóle.
  * CZY CYTOWANY NUMER WSKAZUJE TĘ decyzję, o której cytujące zdanie mówi. Sprawdzenie 1 pyta, czy sekcja
    ISTNIEJE, nie czy jest NA TEMAT. Zmierzone: trzy niezmienniki w `AGENTS.md` (werdykt bramek treści,
    dostarczanie narzędzi, `continue-on-error`) cytowały `DEC-28`, opisując co do zdania treść sekcji
    `DEC-26`; obie sekcje istnieją, więc oba sprawdzenia świeciły na zielono, a błąd przejechał
    synchronizacją do repozytorium perimetru. Powstał PRZENUMEROWANIEM PO SCALENIU: gałąź podbiła własny
    numer globalną podmianą w tym samym commicie, w którym `merge origin/main` wniósł CUDZE cytowania na
    tę samą liczbę — podmiana nie ma jak odróżnić numeru własnego od dopiero co wciągniętego, a zrobiła
    to dwa razy pod rząd. Trzy warianty domknięcia zmierzone na tym materiale (20 par wiersz-cytat),
    wszystkie odrzucone fałszywymi alarmami na treści POPRAWNEJ:
      – KOTWICA (identyfikator w odwrotnych apostrofach z wiersza musi stać w cytowanej sekcji): łapie
        wszystkie trzy, ale 4 fałszywe. Wiersz nazywa MIEJSCE egzekucji (`render_member.py`, `apply.yml`),
        a decyzja tłumaczy POWÓD i nazwy pliku nieść nie musi. Bramka wymuszałaby wpisywanie nazw plików
        do uzasadnień — czyli psucie rejestru pod bramkę.
      – ARGMAX pokrycia tokenów (cytowana sekcja ma być najbliższa ze wszystkich): łapie wszystkie trzy,
        2 fałszywe, i jeden z nich jest STRUKTURALNY — komórka wolno cytuje kilka decyzji naraz (dwie
        takie), a argmax ma z definicji jednego zwycięzcę, więc pozostałe cytaty fałszuje z zasady.
      – SEKCJA-SIEROTA (każda sekcja cytowana choć raz): nie łapie NICZEGO. Sekcja `DEC-26` jest cytowana
        w ośmiu innych plikach, więc przestawiony cytat jej nie osierocił; do tego 4 fałszywe, bo sekcja
        bez ani jednego cytatu jest legalna.
    Wariant bez fałszywych alarmów musiałby WIĄZAĆ wiersz z sekcją stabilnym kluczem po obu stronach,
    zamiast wnioskować z prozy — a to jest zmiana kształtu obu plików i własna decyzja, nie komentarz.

GDZIE TE SPRAWDZENIA BIEGAJĄ — I DLACZEGO NIE WSZĘDZIE TAK SAMO (DEC-30). Sprawdzenie 1 pyta konsumenta
rejestru: „czy cytujesz decyzję, której nie niesiesz". To pytanie do ROZPAKOWANEGO repozytorium, które
kopiuje ze startera podzbiór. W drzewie SAMEGO startera odpowiedź jest z założenia inna: leżą tam testy
negatywne cytujące numery nieistniejące z premedytacją (fixture dowodzący, że `--wzgledem` gryzie), więc
sprawdzenie 1 świeciłoby tam na czerwono na treści POPRAWNEJ — a naprawiałoby się je kasowaniem testu.
Sprawdzenia 2a-2d pytają o coś innego — „czy repozytorium mówi o swoim rejestrze prawdę" — i to pytanie
należy przede wszystkim do startera, bo tam rejestr MIESZKA. `--tylko-deklaracje` uruchamia więc drugą
grupę bez pierwszej. Zmierzone: bez tego trybu deklaracja w `selftest/skan_samodzielnosci.py` przeżyła
dwadzieścia jeden decyzji, bo bramka nie widziała katalogu, w którym stała.

Użycie (patrz `.github/actions/bramki-tresci/action.yml`, `.github/workflows/starter-drift.yml`
i `test_kompletnosc_decyzji` w selfteście startera):
    python3 tools/decisions_check.py
    python3 tools/decisions_check.py --wzgledem /tmp/0-decyzje-startera.md
    python3 tools/decisions_check.py --tylko-deklaracje --root /sciezka/do/startera
"""
import argparse
import pathlib
import re
import sys

# Plik z decyzjami. Ta sama nazwa w starterze i w repo perimetru — `install.sh` kopiuje `docs/` bez zmiany
# nazw, więc jedna stała wystarcza obu stronom.
DECYZJE = pathlib.Path("docs/0-decyzje.md")

# Nagłówek sekcji decyzji: `## DEC-<numer> — <tytuł>`.
NAGLOWEK = re.compile(r"^##\s+(DEC-([0-9]+))\b")

# Odsyłacz do decyzji w dowolnym miejscu repo. Wzorzec jest zbudowany ze sklejenia dwóch kawałków
# CELOWO: napisany wprost, ta linia byłaby pierwszym trafieniem własnej bramki (powierzchnia skanu
# obejmuje `tools/`). Ta sama pułapka co w guardzie zakazanej komendy `enforce` — guard, który wywraca
# się o własne źródło, uczy tylko usuwania guardów.
ODSYLACZ = re.compile("DEC" + r"-([0-9]+)")

# Deklaracja ZAKRESU rejestru: „DEC-<a>…DEC-<b>", w odwrotnych apostrofach albo bez, z wielokropkiem,
# trzema kropkami, pauzą, półpauzą albo dywizem — każda z tych form padła w tym repozytorium, a wzorzec
# na sam `…` przepuściłby dokładnie ten wariant, który ktoś napisze następnym razem. Sam wzorzec jest
# sklejony z kawałków z tego samego powodu co odsyłacz wyżej, a PRZYKŁADÓW nie zapisujemy tu z cyframi:
# bramka skanuje własne źródło, więc komentarz z prawdziwym zakresem byłby jej pierwszym trafieniem —
# zmierzone przy pierwszym uruchomieniu tej wersji, trzy błędy, wszystkie z tej jednej linii.
ZAKRES = re.compile("`?" + "DEC" + r"-([0-9]+)`?\s*(?:…|\.{2,3}|[-–—])\s*`?" + "DEC" + r"-([0-9]+)`?")

# Liczebniki, którymi rejestr opisywał w prozie swój rozmiar („Osiemnaście rozstrzygnięć", „Dwadzieścia
# trzy rozstrzygnięcia"). MIANOWNIK, bo w takiej formie stoi w zdaniu otwierającym; formy zależne
# („dwóch decyzji") są świadomie poza wzorcem — zdanie „nie zawierało dwóch całych decyzji" opisuje
# incydent, a nie rozmiar rejestru, i bramka łapiąca je byłaby czerwona na własnym uzasadnieniu.
_JEDNOSCI = ["jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć", "dziesięć",
             "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście", "szesnaście",
             "siedemnaście", "osiemnaście", "dziewiętnaście"]
_DZIESIATKI = ["dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt", "sześćdziesiąt",
               "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt"]
LICZEBNIKI = {slowo: i + 1 for i, slowo in enumerate(_JEDNOSCI)}
for _i, _dziesiec in enumerate(_DZIESIATKI):
    LICZEBNIKI[_dziesiec] = (_i + 2) * 10
    for _j, _jeden in enumerate(_JEDNOSCI[:9]):
        LICZEBNIKI[f"{_dziesiec} {_jeden}"] = (_i + 2) * 10 + _j + 1

# Licznik decyzji w preambule: liczba (cyframi albo słownie) tuż przed rzeczownikiem. Warianty złożone
# muszą stać w alternatywie PRZED prostymi, bo `re` bierze pierwsze dopasowanie: inaczej „dwadzieścia
# trzy rozstrzygnięcia" zostałoby przeczytane jako „dwadzieścia" i bramka pytałaby o złą liczbę.
LICZNIK = re.compile(
    r"(?<![\w-])(" + "|".join([r"[0-9]+"] + sorted(LICZEBNIKI, key=len, reverse=True)) + r")"
    r"\s+(?:decyzj|rozstrzygni)\w*", re.IGNORECASE)

# Czego nie czytamy. Katalogi narzędziowe i binaria — nie dlatego, że „nie warto", tylko dlatego, że
# odsyłacz do decyzji jest konstrukcją TEKSTOWĄ i w skompilowanym artefakcie nie ma go jak zapisać.
POMIJANE_KATALOGI = {".git", ".terraform", "node_modules", "__pycache__"}
POMIJANE_ROZSZERZENIA = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".tar", ".gz", ".binary"}


def zdefiniowane(tekst: str) -> dict[str, int]:
    """Numery decyzji mające w tym tekście własną sekcję -> numer linii PIERWSZEGO nagłówka.

    Słownik zwija powtórzenia z premedytacją — pytanie „czy sekcja istnieje" ma jedną odpowiedź. Za to,
    czy ten sam numer nie występuje DWA RAZY, odpowiada `powtorzone()` niżej; bez niej drugi `## DEC-27`
    byłby niewidzialny dla wszystkich trzech sprawdzeń tego pliku, łącznie z licznikiem sekcji.
    """
    out = {}
    for i, linia in enumerate(tekst.splitlines(), 1):
        m = NAGLOWEK.match(linia)
        if m:
            out.setdefault(m.group(1), i)
    return out


def tytuly(tekst: str) -> dict[str, str]:
    """Numer decyzji -> tytul jej PIERWSZEJ sekcji, znormalizowany do porownania miedzy repozytoriami.

    PO CO OSOBNO OD `zdefiniowane()`. Tamta funkcja odpowiada na pytanie „czy sekcja o tym numerze
    ISTNIEJE" i to wystarcza, dopoki numer znaczy po obu stronach TO SAMO. Nie wystarcza, gdy przestaje:
    numer nadaje KOLEJNOSC MERGE'A, wiec dwie galezie czytajace ten sam stan biora te sama liczbe, a po
    scaleniu jedna z nich jest przenumerowywana RECZNIE — po jednej stronie, nie po obu.

    ZMIERZONE (#2096, przy synchronizacji #2068): repozytorium wdrozenia mialo DEC-26 i DEC-27
    w ODWROTNEJ kolejnosci niz starter. Trojstronny merge zobaczyl wtedy tresc DEC-27 startera jako
    DODATEK w miejscu, gdzie wdrozenie ma DEC-28, i wstawil ja DRUGI RAZ — przy ZERO konfliktow, bo obie
    strony byly wewnetrznie spojne. Zlapala to dopiero bramka duplikatu, czyli PO fakcie i na czerwonym
    wniosku, ktory byl poprawny.

    CZEGO TA FUNKCJA NIE ROBI I DLACZEGO. Nie jest stabilnym kluczem sekcji — takiego klucza tu nie ma
    i jego wprowadzenie rusza 56 sekcji w dwoch repozytoriach naraz (osobne zadanie). Porownuje TYTUL,
    ktory jest najtansza rzecza rozroznialna miedzy „ta sama decyzja pod innym numerem" a „inna decyzja
    pod tym samym numerem". Tytul bywa poprawiany, wiec porownanie jest ZNORMALIZOWANE i celowo tepe:
    male litery, zbite biale znaki, bez znakow innych niz alfanumeryczne. Falszywy alarm kosztuje tu
    jedna linie w cotygodniowym zgloszeniu; przeoczenie kosztuje zablokowany sync i reczna interwencje
    w rejestrze, ktory wszystko cytuje.
    """
    out: dict[str, str] = {}
    for linia in tekst.splitlines():
        m = NAGLOWEK.match(linia)
        if m and m.group(1) not in out:
            reszta = linia[m.end():]
            out[m.group(1)] = " ".join("".join(
                z if z.isalnum() or z.isspace() else " " for z in reszta).lower().split())
    return out


def kolejnosc(tekst: str) -> list[str]:
    """Numery decyzji w KOLEJNOSCI WYSTEPOWANIA w pliku. Nie posortowane — o to wlasnie chodzi."""
    return [m.group(1) for m in (NAGLOWEK.match(l) for l in tekst.splitlines()) if m]


def powtorzone(tekst: str) -> dict[str, list[int]]:
    """Numery decyzji mające WIĘCEJ NIŻ JEDNĄ sekcję -> numery linii wszystkich nagłówków.

    DLACZEGO OSOBNO. Ten rejestr rośnie z gałęzi równoległych, a numer nadawany jest przez odczyt
    ostatniej sekcji i dodanie jedynki — czyli przez odczyt stanu, który druga gałąź właśnie zmienia.
    Zmierzone w jeden dzień (2026-08-12): CZTERY przenumerowania DEC (19, 24, 27, 28), za każdym razem
    po scaleniu i zawsze ręcznie. Dwa tryby awarii kończą się tym samym obrazem w pliku:

      * scalenie „zostawmy oba" — rozwiązanie konfliktu, w którym obie sekcje zostają na jednym numerze;
      * synchronizacja liczona od ZAPAMIĘTANEJ bazy — trójstronny merge nie wie, że „ours" dostało tę
        samą zmianę inną drogą, i wciąga cudzą sekcję DRUGI RAZ, przy ZERO konfliktów.

    Drugiego trybu nie widzi tu nic innego: sekcje są na miejscu, cytowania się zgadzają, a licznik
    liczy klucze słownika, więc dwie sekcje na jednym numerze liczą się jako jedna. Sprawdzenie
    nagłówków H1 łapie tylko szczególny przypadek, w którym powtórzył się nagłówek NAJWYŻSZEGO poziomu.
    """
    out: dict[str, list[int]] = {}
    for i, linia in enumerate(tekst.splitlines(), 1):
        m = NAGLOWEK.match(linia)
        if m:
            out.setdefault(m.group(1), []).append(i)
    return {numer: linie for numer, linie in out.items() if len(linie) > 1}


def preambula(tekst: str) -> list[tuple[int, str]]:
    """Linie rejestru PRZED pierwszą sekcją decyzji — czyli miejsce, w którym rejestr opisuje sam siebie.

    Licznika szukamy wyłącznie tutaj, bo dalej ten sam wzorzec trafiałby w zdania o czymś innym:
    uzasadnienie DEC-20 mówi „nie zawierało dwóch całych decyzji" o zmierzonym incydencie, a nie
    o rozmiarze rejestru. Bramka czerwona na własnym uzasadnieniu uczy tylko kasowania uzasadnień.
    """
    out = []
    for i, linia in enumerate(tekst.splitlines(), 1):
        if NAGLOWEK.match(linia):
            break
        out.append((i, linia))
    return out


def naglowki_h1(tekst: str) -> list[int]:
    """Numery linii z nagłówkiem najwyższego poziomu, z pominięciem bloków kodu.

    Bloki są pomijane, bo rejestr cytuje wyjście `terraform plan` z komentarzami shellowymi
    (`# …must be replaced`). Bez tego bramka byłaby czerwona na treści całkowicie poprawnej — czyli
    powtarzałaby błąd guardu wywracającego się o własną dokumentację.
    """
    out, w_bloku = [], False
    for i, linia in enumerate(tekst.splitlines(), 1):
        if linia.lstrip().startswith("```"):
            w_bloku = not w_bloku
            continue
        if not w_bloku and re.match(r"#\s", linia):
            out.append(i)
    return out


def skanuj(root: pathlib.Path) -> tuple[dict[str, list[str]], list[tuple[str, int, int]]]:
    """Jedno przejście po repo: odsyłacze do decyzji ORAZ deklaracje zakresu.

    Zwraca (numer decyzji -> lista miejsc `plik:linia`, lista `(miejsce, początek, koniec)` zakresów).
    Jedno przejście, bo oba pytania dotyczą tych samych linii tych samych plików — drugi rglob po
    całym drzewie kosztowałby tyle samo I/O i rozjeżdżałby się przy każdej zmianie listy pomijanych.
    """
    odsylacze: dict[str, list[str]] = {}
    zakresy: list[tuple[str, int, int]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        if set(p.relative_to(root).parts) & POMIJANE_KATALOGI:
            continue
        if p.suffix.lower() in POMIJANE_ROZSZERZENIA:
            continue
        try:
            tekst = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Binarium albo plik nie do odczytu. Nie jest to błąd bramki: odsyłacza i tak by tam nie było.
            continue
        for i, linia in enumerate(tekst.splitlines(), 1):
            for numer in ODSYLACZ.findall(linia):
                odsylacze.setdefault("DEC-" + numer, []).append(f"{p.relative_to(root)}:{i}")
            for poczatek, koniec in ZAKRES.findall(linia):
                zakresy.append((f"{p.relative_to(root)}:{i}", int(poczatek), int(koniec)))
    return odsylacze, zakresy


def main() -> int:
    ap = argparse.ArgumentParser(description="Kompletność rejestru decyzji.")
    ap.add_argument("--root", default=".", help="katalog repozytorium (domyślnie bieżący)")
    ap.add_argument("--wzgledem", metavar="PLIK",
                    help="plik `0-decyzje.md` startera — sprawdź, czy zbiór decyzji tutaj go POKRYWA")
    ap.add_argument("--tylko-deklaracje", action="store_true",
                    help="sprawdź WYŁĄCZNIE, czy repo mówi o swoim rejestrze prawdę (zakres, licznik, "
                         "jeden H1, jeden numer = jedna sekcja) — bez pytania o rozwiązywalność cytowań")
    args = ap.parse_args()

    # Wykluczenie, nie ciche pierwszeństwo. `--wzgledem` pyta o POKRYCIE zbioru, `--tylko-deklaracje`
    # wyłącza pytania o zbiór i zostawia pytania o prozę — złożone razem jedno z nich musiałoby zostać
    # zignorowane, a bramka wywołana z flagą, która nic nie robi, jest gorsza niż bramka niewywołana:
    # wygląda w logu tak samo jak działająca.
    if args.tylko_deklaracje and args.wzgledem:
        print("::error::--tylko-deklaracje i --wzgledem wykluczaja sie: pierwsza flaga wylacza porownanie "
              "zbiorow, ktore druga wlasnie zamawia", file=sys.stderr)
        return 1

    root = pathlib.Path(args.root).resolve()
    plik = root / DECYZJE
    if not plik.is_file():
        print(f"::error::brak {DECYZJE} — repozytorium bez rejestru decyzji nie ma czego sprawdzać",
              file=sys.stderr)
        return 1

    tresc = plik.read_text(encoding="utf-8")
    tutaj = zdefiniowane(tresc)
    problemy: list[str] = []

    # 1. Każdy cytowany numer ma sekcję. Sortujemy po NUMERZE, nie leksykalnie — inaczej lista błędów
    #    czyta się jak losowa (DEC-10 przed DEC-2), a to jest lista do odhaczania.
    #    Pomijane przy `--tylko-deklaracje`: to jedyne sprawdzenie w tym pliku, które pyta o ZBIÓR
    #    cytowań, a więc jedyne, na które drzewo startera odpowiada inaczej niż rozpakowane repo —
    #    leżą tam testy negatywne cytujące numery nieistniejące z premedytacją (DEC-30).
    odsylacze, zakresy = skanuj(root)
    for numer in (sorted(odsylacze, key=lambda s: int(s.split("-")[1])) if not args.tylko_deklaracje else []):
        if numer not in tutaj:
            # KOD PRZED DOKUMENTACJĄ na liście miejsc. Odsyłacz w pustkę z `apply.yml` albo z reguły OPA
            # znaczy co innego niż ten sam odsyłacz w prozie: pierwszy stoi w pliku, który coś wykonuje.
            # Lista przycięta do pięciu pozycji pokazałaby przy numerze cytowanym kilkanaście razy same
            # akapity — czyli najmniej pilne z tego, co trzeba naprawić.
            miejsca = sorted(odsylacze[numer], key=lambda m: (m.rsplit(":", 1)[0].endswith(".md"), m))
            gdzie = ", ".join(miejsca[:5]) + (f" (+{len(miejsca) - 5})" if len(miejsca) > 5 else "")
            problemy.append(
                f"{numer}: repozytorium powołuje się na tę decyzję w {len(miejsca)} miejscu/ach, "
                f"a {DECYZJE} jej nie zawiera — kod odsyła do uzasadnienia, którego tu nie ma. "
                f"Przenieś sekcję ze startera. Miejsca: {gdzie}")

    # 2. Rejestr mówi o SOBIE prawdę. Trzy pytania o tę samą rzecz: czy zdanie o rozmiarze/zakresie
    #    zbioru opisuje zbiór, który naprawdę tam leży. Bez tego liczbę utrzymuje wyłącznie czyjaś
    #    uwaga — i utrzymywała ją źle trzy razy z rzędu, przy zielonych sprawdzeniach 1 i 3.
    numery = sorted(int(n.split("-")[1]) for n in tutaj)
    # Pary MALEJĄCE odsiewamy od razu: zakres z definicji rośnie, a tak wygląda nagłówek sekcji cytujący
    # w tytule decyzję wcześniejszą („## DEC-<nowa> — DEC-<starsza> rozszerzona o…"). To nie jest
    # deklaracja rozmiaru zbioru i czerwień na niej uczyłaby tylko omijania bramki w tytułach.
    deklaracje = [(miejsce, a, b) for miejsce, a, b in zakresy if a < b]
    if numery:
        # 2a. Deklaracja zakresu gdziekolwiek w repo — KOŃCE, nigdy ciągłość (dziura jest legalna).
        for miejsce, poczatek, koniec in deklaracje:
            if (poczatek, koniec) != (numery[0], numery[-1]):
                problemy.append(
                    f"{miejsce}: deklaruje zakres decyzji {poczatek}…{koniec}, a rejestr obejmuje "
                    f"{numery[0]}…{numery[-1]} ({len(numery)} sekcji w {DECYZJE}). Najtańsza naprawa to "
                    f"USUNIĘCIE liczby ze zdania: zbiór sekcji jest źródłem prawdy, a zakres wpisany "
                    f"w prozę utrzymuje tylko czyjaś uwaga — i rozjechał się już trzy razy")

        # 2b. Licznik w preambule rejestru. Osobno od zakresu, bo licznik jest LICZBĄ SEKCJI, a zakres
        #     jego końcami: przy legalnej dziurze w numeracji te dwie liczby są różne i tylko jedna
        #     z nich jest błędem.
        for i, linia in preambula(tresc):
            for m in LICZNIK.finditer(linia):
                slowo = m.group(1).lower()
                ile = int(slowo) if slowo.isdigit() else LICZEBNIKI[slowo]
                if ile != len(numery):
                    problemy.append(
                        f"{DECYZJE}:{i}: preambuła mówi „{m.group(0)}”, a rejestr ma {len(numery)} "
                        f"sekcji. To jest dokładnie ta liczba, która stała tu przez pół roku mniejsza "
                        f"od realnej — jeśli nie ma jej kto podbijać przy każdej decyzji, wykreśl ją")

    # 2c. Jeden nagłówek H1. Dwa znaczą konflikt merge'a rozwiązany „zostawmy oba": tak w tym rejestrze
    #     powstał nagłówek z nieaktualnym zakresem STOJĄCY NAD nagłówkiem bez liczby, wraz z akapitem
    #     urwanym w pół zdania. Żadne sprawdzenie liczące sekcje tego nie widzi.
    h1 = naglowki_h1(tresc)
    if len(h1) != 1:
        problemy.append(
            f"{DECYZJE}: nagłówków najwyższego poziomu jest {len(h1)} (linie: "
            f"{', '.join(map(str, h1)) or 'brak'}), a ma być JEDEN. Tak wygląda konflikt merge'a "
            f"rozwiązany przez zostawienie obu wersji nagłówka — rejestr ma wtedy dwa różne zdania "
            f"o sobie samym i oba wyglądają na obowiązujące")

    # 2d. Każdy numer decyzji występuje DOKŁADNIE RAZ. Sprawdzenia 1-3 pytają, czy sekcja ISTNIEJE,
    #     a `zdefiniowane()` zwija powtórzenia do jednego klucza — więc drugi `## DEC-27` nie zapala tu
    #     niczego: cytowania się zgadzają, zakres się zgadza, a licznik liczy klucze, nie nagłówki.
    #     Tak wygląda konflikt numeru rozwiązany przez „zostawmy oba" ORAZ synchronizacja liczona od
    #     zapamiętanej bazy (trójstronny merge wciąga cudzą sekcję drugi raz przy ZERO konfliktów).
    #     Numery decyzji przydziela KOLEJNOŚĆ MERGE'A — dwie sekcje na jednym numerze znaczą, że dwie
    #     gałęzie policzyły „ostatnia + 1" z tego samego stanu.
    for numer, linie in sorted(powtorzone(tresc).items(), key=lambda kv: int(kv[0].split("-")[1])):
        problemy.append(
            f"{DECYZJE}: {numer} ma {len(linie)} sekcje (linie: {', '.join(map(str, linie))}), a ma mieć "
            f"JEDNĄ. Albo konflikt numeru rozwiązano przez zostawienie obu wersji, albo synchronizacja "
            f"liczona od nieaktualnej bazy wciągnęła cudzą sekcję drugi raz — w obu przypadkach jedna "
            f"z tych decyzji nie ma własnego numeru i nie da się jej zacytować")

    # 3. Pokrycie zbioru startera — tylko gdy mamy z czym porównać.
    if args.wzgledem:
        wzorzec = pathlib.Path(args.wzgledem)
        if not wzorzec.is_file():
            print(f"::error::--wzgledem: nie ma pliku {wzorzec}", file=sys.stderr)
            return 1
        tam = zdefiniowane(wzorzec.read_text(encoding="utf-8"))
        # Brak JAKIEJKOLWIEK decyzji po tamtej stronie znaczy, że pobraliśmy nie ten plik (404 zapisany
        # do pliku, pusta odpowiedź). Porównanie z pustym zbiorem przechodzi ZAWSZE — czyli bramka
        # milczy dokładnie wtedy, gdy jej wejście jest zepsute. Fail-closed.
        if not tam:
            print(f"::error::--wzgledem: {wzorzec} nie zawiera ANI JEDNEJ sekcji decyzji. To nie jest "
                  f"zero roznic, tylko zepsute wejscie bramki (zly plik, 404 zapisany do pliku, pusta "
                  f"odpowiedz API).", file=sys.stderr)
            return 1
        for numer in sorted(set(tam) - set(tutaj), key=lambda s: int(s.split("-")[1])):
            problemy.append(
                f"{numer}: jest w starterze ({wzorzec}:{tam[numer]}), nie ma jej tutaj. Nikt jej nie "
                f"cytuje, wiec sprawdzenie wewnetrzne jej nie widzi — a jej brak znaczy, ze sync "
                f"przeniosl commit, ale nie cala jego tresc")

        # DRUGIE PYTANIE TEGO TRYBU, wezsze niz pokrycie zbioru i szersze niz duplikat w jednym pliku:
        # czy ten sam NUMER znaczy po obu stronach TE SAMA decyzje. Bez tego `--wzgledem` przechodzi na
        # zbiorze {1..57} po obu stronach nawet wtedy, gdy dwa numery sa zamienione miejscami — a wlasnie
        # taka zamiana kazala trojstronnemu merge'owi wciagnac sekcje drugi raz (#2096/#2068).
        # TRZECIE PYTANIE: czy sekcje stoja po obu stronach w TEJ SAMEJ KOLEJNOSCI.
        #
        # To NIE jest estetyka i nie jest to „posortuj rejestr". Trojstronny merge dopasowuje tresc po
        # POLOZENIU: gdy ta sama sekcja stoi po dwoch stronach w innym miejscu, merge widzi ja jako DODATEK
        # w miejscu, gdzie druga strona ma cos innego — i wciaga ja DRUGI RAZ, przy ZERO konfliktow, bo obie
        # strony sa wewnetrznie spojne. Zmierzone (#2096, przy synchronizacji #2068): wdrozenie mialo sekcje
        # DEC-27 PRZED DEC-26, starter odwrotnie; scalenie 116 commitow dopisalo druga sekcje `## DEC-27`
        # i zatrzymalo poprawny wniosek na bramce duplikatu — czyli PO fakcie, na czerwonym CI.
        #
        # NIE zadamy kolejnosci ROSNACEJ, tylko ZGODNEJ. Dziura w numeracji jest legalna, a sekcja
        # dopisana swiadomie nie na koncu tez — pod warunkiem, ze obie strony robia to tak samo. Zmierzone:
        # oba rejestry maja dzis jedna wspolna „nierosnaca" pare i to jest w porzadku; rozjezdzala sie
        # WYLACZNIE ta jedna, ktora byla po jednej stronie.
        #
        # Porownujemy tylko numery obecne PO OBU STRONACH — sekcja, ktorej gdzies nie ma, jest pytaniem
        # sprawdzenia wyzej i zglaszanie jej tutaj drugi raz zamienialoby jeden problem w dwa komunikaty.
        wspolne = set(tam) & set(tutaj)
        kol_tutaj = [n for n in kolejnosc(tresc) if n in wspolne]
        kol_tam = [n for n in kolejnosc(wzorzec.read_text(encoding="utf-8")) if n in wspolne]
        if kol_tutaj != kol_tam:
            rozne = [(a, b) for a, b in zip(kol_tutaj, kol_tam) if a != b][:3]
            problemy.append(
                f"kolejnosc sekcji rozni sie od startera (pierwsze rozjazdy: "
                f"{', '.join(f'tutaj {a} / tam {b}' for a, b in rozne)}). Trojstronny merge dopasowuje "
                f"tresc po POLOZENIU, wiec ta sama sekcja stojaca gdzie indziej zostanie wciagnieta DRUGI "
                f"RAZ — przy zero konfliktow (zmierzone #2068). Przenies sekcje, nie zmieniaj numerow")

        tytuly_tam, tytuly_tutaj = tytuly(wzorzec.read_text(encoding="utf-8")), tytuly(tresc)
        for numer in sorted(set(tam) & set(tutaj), key=lambda s: int(s.split("-")[1])):
            a, b = tytuly_tutaj.get(numer, ""), tytuly_tam.get(numer, "")
            if a and b and a != b:
                problemy.append(
                    f"{numer}: ten sam numer znaczy tu i w starterze INNA decyzje "
                    f"(tutaj: \"{a[:70]}\"; starter: \"{b[:70]}\"). Numer nadaje kolejnosc merge'a, wiec "
                    f"przenumerowanie po JEDNEJ stronie rozjezdza znaczenie — a trojstronny merge widzi "
                    f"wtedy cudza sekcje jako DODATEK i wciaga ja drugi raz (zmierzone #2068)")

    for z in problemy:
        print(f"::error::{z}")
    if problemy:
        sys.stdout.flush()
        print(f"\nNIEZALICZONE ({len(problemy)}): rejestr decyzji jest niekompletny albo repozytorium "
              f"mówi o nim nieprawdę.", file=sys.stderr)
        return 1

    ile_wzorzec = f", pokrycie startera: {len(zdefiniowane(pathlib.Path(args.wzgledem).read_text(encoding='utf-8')))} sekcji" if args.wzgledem else ""
    # Zakres wypisujemy z realnego zbioru, nie z prozy — podsumowanie ma pokazywać to, co bramka
    # ZMIERZYŁA. Liczba sprawdzonych deklaracji stoi obok celowo: „0 deklaracji" znaczy, że repo
    # o swoim zakresie nie twierdzi nic, i to jest stan zalecany, a nie brak sprawdzenia.
    rozpietosc = f" ({numery[0]}…{numery[-1]})" if numery else ""
    # W trybie deklaracji NIE piszemy „N cytowanych numerow rozwiazanych": policzone one są (jedno
    # przejście po drzewie zbiera oba wyniki), ale rozwiązywalności nikt nie sprawdzał. Podsumowanie
    # ma mówić, co bramka ZMIERZYŁA — nie co miała pod ręką. Zielony wiersz obiecujący sprawdzenie,
    # którego nie było, jest dokładnie tym trybem awarii, dla którego powstał cały ten plik.
    ile_cytowan = "" if args.tylko_deklaracje else f", {len(odsylacze)} cytowanych numerow rozwiazanych"
    tryb = " [tylko deklaracje]" if args.tylko_deklaracje else ""
    print(f"OK{tryb}: {len(tutaj)} decyzji w {DECYZJE}{rozpietosc}{ile_cytowan}, "
          f"{len(deklaracje)} deklaracji zakresu zgodnych ze zbiorem{ile_wzorzec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
