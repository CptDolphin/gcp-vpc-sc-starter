#!/usr/bin/env python3
"""Skan samodzielności materiału: czy nie niesie nazw organizacji, osób ani odsyłaczy do repo pochodzenia.

DLACZEGO OSOBNY PLIK, a nie funkcja w selftest.py: ten skan przydaje się poza starterem — na katalogu
z przykładami, na całym repozytorium, które starter u siebie publikuje. Selftest wymaga terraforma,
conftesta i tflinta; ten skan wymaga samego Pythona, więc da się go wpiąć jako tania bramka wszędzie.

    python3 skan_samodzielnosci.py <ścieżka> [<ścieżka> ...]

Kod wyjścia: 0 = czysto, 1 = znaleziono naruszenia (wypisane na stdout).

DWIE KLASY REGUŁ, celowo różne:

  * KSZTAŁT — wzorce opisujące, JAK WYGLĄDA naruszenie („numer projektu spoza listy placeholderów",
    „numer zgłoszenia spoza konwencji"). Łapią też przyszłe wycieki, nie tylko te, które już usunięto.
  * NAZWY WŁASNE — trzymane jako SKRÓTY SHA-256, nigdy dosłownie. Denylista z nazwą organizacji
    publikuje dokładnie to, co ma usunąć: guard stałby się jedynym miejscem w materiale, w którym ta
    nazwa występuje, czyli osiągałby odwrotny skutek. Skrót łapie tak samo, a nie niesie treści.

ŚWIADOME OGRANICZENIE: skróty porównujemy dla tokenów alfanumerycznych o długości >= 4. Nazwa zapisana
ze spacją albo znakiem specjalnym w środku przejdzie — na to jest przegląd człowieka, nie ten skan.
"""
import hashlib
import pathlib
import re
import sys

# Numery projektów uznane za jawnie fikcyjne. Poza tą listą przechodzi jeszcze każdy numer złożony
# z jednej powtórzonej cyfry — testy reguł używają ich, żeby odróżnić dwa wpisy.
NUMERY_PRZYKLADOWE = {"000000000000", "111111111111", "222222222222", "123456789012", "210987654321"}

REGULY_KSZTALTU = [
    (r"GCP-0\d{3}", "numeracja ADR z repo macierzystego (uzyj DEC-1..DEC-8 z docs/0-decyzje.md)"),
    (r"repo labu|klastrze Hetznera|k8s-hetzner", "odsylacz do repo macierzystego"),
    (r"\bklient(a|owi|em|ci)?\b|deliverable", "jezyk relacji z projektu zamiast instrukcji"),
    (r"RITM(?!0000\d{3}\b)\d{7}", "numer zgloszenia spoza konwencji RITM0000xxx"),
]

ZAKAZANE_SKROTY = {
    "62de5eebe37f4edd": "nazwa organizacji",
    "ca5a7747f31ea33c": "nazwa organizacji",
    "808c0780bdef7e54": "nazwisko",
    "8f527b0aeff1804a": "nazwisko",
    "294aa8d75483b833": "nazwa dostawcy z repo macierzystego",
    "aba651c146c7e331": "nazwa jednostki organizacyjnej",
}

POMIJANE_SUFIKSY = {".png", ".pyc", ".jpg", ".jpeg", ".gif", ".ico", ".pdf"}
POMIJANE_KATALOGI = {".git", "__pycache__", ".terraform", "node_modules"}


def numery_spoza_konwencji(tekst):
    for m in re.finditer(r"(?<!\d)\d{12}(?!\d)", tekst):
        n = m.group(0)
        if n in NUMERY_PRZYKLADOWE or len(set(n)) == 1:
            continue
        yield m, "numer projektu spoza listy placeholderow"


def tokeny_zakazane(tekst):
    for m in re.finditer(r"[A-Za-z0-9]{4,}", tekst):
        skrot = hashlib.sha256(m.group(0).lower().encode()).hexdigest()[:16]
        if skrot in ZAKAZANE_SKROTY:
            yield m, ZAKAZANE_SKROTY[skrot]


def skanuj_tekst(tekst):
    """Zwraca listę (offset, dopasowanie, powód) dla jednego dokumentu."""
    wynik = []
    for wzorzec, powod in REGULY_KSZTALTU:
        for m in re.finditer(wzorzec, tekst, re.IGNORECASE):
            wynik.append((m.start(), m.group(0), powod))
    for gen in (numery_spoza_konwencji(tekst), tokeny_zakazane(tekst)):
        for m, powod in gen:
            wynik.append((m.start(), m.group(0), powod))
    return sorted(wynik)


def skanuj_sciezke(base, pomijaj_nazwy=()):
    """Zwraca listę stringów 'plik:linia wartosc — powod'."""
    base = pathlib.Path(base)
    trafienia = []
    pliki = [base] if base.is_file() else sorted(base.rglob("*"))
    for f in pliki:
        if not f.is_file() or f.suffix in POMIJANE_SUFIKSY:
            continue
        if any(part in POMIJANE_KATALOGI for part in f.parts):
            continue
        # Plik skanu z definicji zawiera opis tego, czego szuka — to jego treść, nie naruszenie.
        if f.name in {"skan_samodzielnosci.py", *pomijaj_nazwy}:
            continue
        try:
            tekst = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for offset, wartosc, powod in skanuj_tekst(tekst):
            linia = tekst[:offset].count("\n") + 1
            try:
                nazwa = f.relative_to(base)
            except ValueError:
                nazwa = f
            trafienia.append(f"{nazwa}:{linia} {wartosc!r} — {powod}")
    return trafienia


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[0])
        print(f"uzycie: {argv[0]} <sciezka> [<sciezka> ...]")
        return 2
    wszystkie = []
    for sciezka in argv[1:]:
        trafienia = skanuj_sciezke(sciezka)
        status = "czysto" if not trafienia else f"{len(trafienia)} naruszen"
        print(f"{sciezka}: {status}")
        for t in trafienia:
            print(f"  {t}")
        wszystkie += trafienia
    return 1 if wszystkie else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
