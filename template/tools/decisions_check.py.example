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

Użycie (patrz `.github/actions/bramki-tresci/action.yml` i `.github/workflows/starter-drift.yml`):
    python3 tools/decisions_check.py
    python3 tools/decisions_check.py --wzgledem /tmp/0-decyzje-startera.md
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
    """Numery decyzji mające w tym tekście własną sekcję -> numer linii nagłówka."""
    out = {}
    for i, linia in enumerate(tekst.splitlines(), 1):
        m = NAGLOWEK.match(linia)
        if m:
            out.setdefault(m.group(1), i)
    return out


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
    args = ap.parse_args()

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
    odsylacze, zakresy = skanuj(root)
    for numer in sorted(odsylacze, key=lambda s: int(s.split("-")[1])):
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
    print(f"OK: {len(tutaj)} decyzji w {DECYZJE}{rozpietosc}, {len(odsylacze)} cytowanych numerow "
          f"rozwiazanych, {len(deklaracje)} deklaracji zakresu zgodnych ze zbiorem{ile_wzorzec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
