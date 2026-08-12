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

CZEGO ŚWIADOMIE NIE SPRAWDZAMY (żeby zielony wynik nie znaczył więcej, niż znaczy):

  * TREŚCI sekcji. Ten sam numer może tu brzmieć inaczej niż w starterze i zwykle brzmieć musi —
    decyzja opisuje wdrożenie, a wdrożenia różnią się od szablonu. Porównanie treści przywróciłoby
    bramkę zawsze-czerwoną, czyli to, czego `starter-drift` unika z premedytacją.
  * NUMERACJI ciągłej. Dziura w numerach jest legalna: decyzja może zostać wycofana, a numery pochodzą
    ze startera i nigdy nie są przenumerowywane. Bramka pyta o POKRYCIE zbioru, nie o jego kształt.

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


def cytowane(root: pathlib.Path) -> dict[str, list[str]]:
    """Numer decyzji -> lista miejsc `plik:linia`, w których repo się na nią powołuje."""
    out: dict[str, list[str]] = {}
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
                out.setdefault("DEC-" + numer, []).append(f"{p.relative_to(root)}:{i}")
    return out


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

    tutaj = zdefiniowane(plik.read_text(encoding="utf-8"))
    problemy: list[str] = []

    # 1. Każdy cytowany numer ma sekcję. Sortujemy po NUMERZE, nie leksykalnie — inaczej lista błędów
    #    czyta się jak losowa (DEC-10 przed DEC-2), a to jest lista do odhaczania.
    odsylacze = cytowane(root)
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

    # 2. Pokrycie zbioru startera — tylko gdy mamy z czym porównać.
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
        print(f"\nNIEZALICZONE ({len(problemy)}): rejestr decyzji jest niekompletny.", file=sys.stderr)
        return 1

    ile_wzorzec = f", pokrycie startera: {len(zdefiniowane(pathlib.Path(args.wzgledem).read_text(encoding='utf-8')))} sekcji" if args.wzgledem else ""
    print(f"OK: {len(tutaj)} decyzji w {DECYZJE}, {len(odsylacze)} cytowanych numerow rozwiazanych"
          f"{ile_wzorzec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
