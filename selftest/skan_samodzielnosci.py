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

Obie klasy są potrzebne i żadna nie zastępuje drugiej: skrót domyka wartość, którą już znamy, kształt
domyka wartości jeszcze nieznane (następne wdrożenie, następny odbiorca). Kształt zapisujemy jako
„czy identyfikator stoi w konwencji przykładów materiału" (`example-*`, `prj-example-*`, `example.com`,
numery z `NUMERY_PRZYKLADOWE`), a nie jako wyliczenie wartości zakazanych — wyliczenie z definicji
nie zna tej, która wycieknie jutro.

ŚWIADOME OGRANICZENIE: skróty porównujemy dla tokenów alfanumerycznych o długości >= 4. Nazwa zapisana
ze spacją albo znakiem specjalnym w środku przejdzie — na to jest przegląd człowieka, nie ten skan.

CZEGO ŚWIADOMIE NIE SPRAWDZAMY (warianty zmierzone i odrzucone — nie wyprowadzaj ich drugi raz):

  * „TOKEN WYGLĄDA NA IDENTYFIKATOR PROJEKTU" (małe litery + myślnik, 6-30 znaków, poza `example-*`) —
    529 unikalnych trafień na czystym repo, najczęstsze `dry-run`, `iam-bootstrap`, `pre-flight`,
    `break-glass`, `vpc-sc`. Bramka krzycząca 529 razy na materiale bez naruszeń zostaje wyłączona
    w tydzień, więc nie chroni przed niczym.
  * „IDENTYFIKATOR Z LOSOWYM SUFIKSEM" (>= 3 człony, ostatni 3-6 znaków z cyfrą i literą naraz) —
    kusząca, bo cicha, ale ma dziurę dokładnie tam, gdzie boli: sufiks bez cyfry przechodzi, czyli
    wdrożona byłaby zielona na tym wycieku, który tę regułę wywołał. Do tego NIE jest cicha:
    zmierzone na tym drzewie 3 trafienia na skrócie regionu (`…-ew1`), a skróty regionów i stref
    (`ew1`, `euw4`, `us1`) mają dokładnie ten kształt, więc źródło fałszywych alarmów jest strukturalne,
    nie jednorazowe. Klasę zamykamy inaczej: kubełki i numery zasobów kształtem w KONTEKŚCIE (niżej),
    prefiks wdrożenia skrótem.
  * ROZSZERZENIE „numeru projektu" z dokładnie 12 cyfr na 10-12 — 22 trafienia na czystym repo:
    identyfikatory przebiegów GitHuba cytowane w dowodach pomiarowych (11 cyfr) i fragment cyfr
    wewnątrz pinu `@sha256`. Dangerous shape (numer projektu/organizacji/polityki dostępu) domyka
    zamiast tego reguła kontekstowa `<zasób>/<numer>` — łapie numer DOWOLNEJ długości, także > 12,
    czego reguła bez kontekstu nie potrafi. Residual: numer 10-11-cyfrowy stojący samotnie, bez
    ścieżki zasobu, przechodzi. Świadome.
"""
import hashlib
import pathlib
import re
import sys

# Numery projektów uznane za jawnie fikcyjne. Poza tą listą przechodzi jeszcze każdy numer złożony
# z jednej powtórzonej cyfry — testy reguł używają ich, żeby odróżnić dwa wpisy.
NUMERY_PRZYKLADOWE = {"000000000000", "111111111111", "222222222222", "123456789012", "210987654321"}

REGULY_KSZTALTU = [
    # Bez KOŃCA zakresu w tym zdaniu — rejestr rośnie, a wpisana granica jest nieprawdziwa od pierwszej
    # decyzji dołożonej po jej wpisaniu. Wpisana 2026-08-07 była PRAWDZIWA (rejestr miał wtedy dokładnie
    # tyle sekcji, ile deklarowała) i przeżyła dwadzieścia jeden kolejnych decyzji, bo nie mierzyło jej
    # nic: bramka deklaracji biegała wyłącznie na ROZPAKOWANYM repozytorium, a tam `selftest/` nie
    # istnieje. Najtańsza naprawa to WYKREŚLENIE liczby, nie jej podbicie (DEC-20); od DEC-30 ten
    # katalog jest już w zasięgu bramki, więc następne takie zdanie zaczerwieni się samo.
    (r"GCP-0\d{3}", "numeracja ADR z repo macierzystego (uzyj numeracji DEC-<n> z docs/0-decyzje.md)"),
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
    # Prefiks, od którego zaczynają się WSZYSTKIE identyfikatory konkretnego wdrożenia: projekty,
    # kubełki, część domenowa adresów kont serwisowych, nazwy gałęzi onboardingowych. Jeden skrót
    # domyka je naraz, bo tokenizer rozbija po myślnikach — z `<prefiks>-vpcsc-t-div` zostaje sam
    # prefiks. DLACZEGO skrót, a nie reguła kształtu: prefiks jest zwykłym słowem bez cech
    # szczególnych, a każda reguła opisująca go kształtem łapie przy okazji pół repozytorium
    # (zmierzone — patrz „CZEGO ŚWIADOMIE NIE SPRAWDZAMY" w docstringu).
    "f52b3d47cecd91fe": "prefiks identyfikatorow konkretnego wdrozenia",
    # Domena wdrożenia sklejona w JEDEN token. Nazwisko samo w sobie jest już wyżej, ale tokenizer
    # tnie po znakach niealfanumerycznych, więc `<imie><nazwisko>.com` daje token, którego żaden
    # z tamtych skrótów nie pokrywa — zmierzone: cała klasa „domena wdrożenia" przechodziła na zielono
    # mimo nazwiska na denyliście.
    "eeac6c0f07ddc696": "domena konkretnego wdrozenia",
}

# Zasoby GCP adresowane numerem. Numer organizacji, projektu i polityki dostępu wygląda tak samo —
# różni je wyłącznie to, co stoi przed ukośnikiem, więc jedna reguła pokrywa wszystkie trzy klasy.
ZASOBY_NUMEROWANE = "projects|organizations|folders|accessPolicies|billingAccounts"

# Domeny, które NIE są wartością żadnego wdrożenia, choć wyglądają jak adres:
#   * `*.gserviceaccount.com` — część adresu konta usługowego; wdrożenie identyfikuje w nim NAZWA
#     PROJEKTU (człon przed `.iam`), a ta wpada pod skrót prefiksu albo pod regułę kubełka/zasobu.
#     Bez tego wyjątku reguła krzyczy 22 razy na własnych przykładach kont.
#   * `*.github.com` — adresy bota commitującego (`…@users.noreply.github.com`) są stałą platformy,
#     a nie czyimkolwiek adresem; workflow, który ich potrzebuje, musi móc je wpisać.
DOMENY_NIEBEDACE_WDROZENIEM = ("gserviceaccount", "github.com")

POMIJANE_SUFIKSY = {".png", ".pyc", ".jpg", ".jpeg", ".gif", ".ico", ".pdf"}
POMIJANE_KATALOGI = {".git", "__pycache__", ".terraform", "node_modules"}


def _przykladowy(nazwa):
    """Czy identyfikator stoi w konwencji przykładów materiału (AGENTS.md, docs/): niesie `example`.

    Reguły kontekstowe pytają WYŁĄCZNIE o to — nie wyliczają wartości zakazanych, więc łapią także
    wdrożenie, o którym ten plik nic nie wie. Odwrotnie niż denylista, która zna tylko przeszłość.
    """
    return "example" in nazwa.lower()


def numery_spoza_konwencji(tekst):
    for m in re.finditer(r"(?<!\d)\d{12}(?!\d)", tekst):
        n = m.group(0)
        if n in NUMERY_PRZYKLADOWE or len(set(n)) == 1:
            continue
        yield m, "numer projektu spoza listy placeholderow"


def numery_zasobow_spoza_konwencji(tekst):
    """Numer zasobu GCP stojący w ścieżce — dowolnej długości, nie tylko 12-cyfrowy.

    DLACZEGO OSOBNO od reguły wyżej: tamta pyta o sam kształt liczby, więc rozszerzenie jej na 10-12
    cyfr wprowadza 22 fałszywe trafienia (identyfikatory przebiegów w dowodach pomiarowych, cyfry
    wewnątrz pinu SHA) — zmierzone. Kontekst `projects/`, `organizations/`, `accessPolicies/` jest
    jednoznaczny, więc reguła jest cicha (0 trafień na czystym repo) i widzi numery, których tamta
    z definicji nie zobaczy: krótsze niż 12 i dłuższe niż 12.
    """
    for m in re.finditer(rf"\b(?:{ZASOBY_NUMEROWANE})/(\d{{6,}})", tekst):
        n = m.group(1)
        # Dokładnie 12 cyfr zgłasza już reguła bez kontekstu — nie dublujemy wiersza w raporcie.
        if n in NUMERY_PRZYKLADOWE or len(set(n)) == 1 or len(n) == 12:
            continue
        yield m, "numer zasobu GCP spoza listy placeholderow"


def kubelki_spoza_konwencji(tekst):
    """Nazwa kubełka w adresie `gs://` poza konwencją przykładów.

    Kubełki stanu i kontraktów są jedynymi identyfikatorami wdrożenia, które w materiale muszą
    wystąpić w postaci pełnej nazwy (adres `gs://` nie ma placeholderowego wariantu, który dałoby się
    skopiować i uruchomić). Reguła nie zna żadnego prefiksu — pyta o konwencję, więc zadziała także
    dla wdrożenia o prefiksie, którego dziś nikt nie zna.
    """
    for m in re.finditer(r"gs://([a-z0-9][a-z0-9._-]{2,62})", tekst):
        if _przykladowy(m.group(1)):
            continue
        yield m, "nazwa kubelka spoza konwencji example-*"


def adresy_spoza_konwencji(tekst):
    """Adres pocztowy / grupy z domeną spoza `example.com`.

    Materiał szablonowy nie ma powodu nieść ani jednego prawdziwego adresu — czyjkolwiek by on nie był.
    Ta reguła domyka klasę „domena wdrożenia" kształtem: skrót w denyliście zna jedną domenę, ta zna
    każdą przyszłą. Wyjątki w `DOMENY_NIEBEDACE_WDROZENIEM` mają uzasadnienie przy stałej.
    """
    for m in re.finditer(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)", tekst):
        domena = m.group(1).lower()
        if _przykladowy(domena) or any(w in domena for w in DOMENY_NIEBEDACE_WDROZENIEM):
            continue
        yield m, "adres z domena spoza konwencji example.com"


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
    generatory = (
        numery_spoza_konwencji(tekst),
        numery_zasobow_spoza_konwencji(tekst),
        kubelki_spoza_konwencji(tekst),
        adresy_spoza_konwencji(tekst),
        tokeny_zakazane(tekst),
    )
    for gen in generatory:
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
