#!/usr/bin/env python3
"""Jedno miejsce, w ktorym czyta sie i zapisuje `perimeter/projects.yaml`.

DLACZEGO OSOBNY MODUL, A NIE `yaml.safe_load` W KAZDYM SKRYPCIE. Ten plik jest wspolnym zrodlem prawdy
o czlonkostwie: dopisuje do niego kanal wejsciowy, czyta renderer, kasuje z niego sweeper, edytuje
break-glass. Cztery kopie „jak sie czyta ten plik” rozjechalyby sie tak samo, jak rozjechaly sie trzy
kopie liczenia budzetu atrybutow (komentarz w `terraform/locals.tf`) — z ta roznica, ze tutaj rozjazd
nie da falszywej liczby w podsumowaniu, tylko CICHO zgubi czlonka.

TRZY WLASNOSCI, KTORE TEN MODUL MA WYMUSZAC — kazda odpowiada na zmierzony tryb awarii:

1. **DUPLIKAT KLUCZA MAPY JEST BLEDEM, NIE „ostatni wygrywa”.** ZMIERZONE: `yaml.safe_load` przy dwoch
   kluczach `stage:` w jednym wpisie bierze OSTATNI i nie mowi nic; `yamldecode` Terraforma zachowuje sie
   tak samo. Przy jednym wspolnym pliku i `merge=union` w `.gitattributes` to nie jest teoria: union
   scala obie strony konfliktu, wiec edycja tego samego wpisu w dwoch pull requestach potrafi zostawic
   zdublowane klucze WEWNATRZ wpisu. Cicha wygrana ostatniego znaczy tu „ktos promowal projekt do
   `enforced`, a scalenie po cichu przywrocilo `dry-run`". Loader nizej rzuca wyjatek.

2. **KANONICZNA POSTAC PLIKU.** Plik jest zapisywany wylacznie przez `yaml.safe_dump` w ustalonym
   ksztalcie, wiec `dump(load(x)) == x`. Dwie rzeczy z tego wynikaja i obie sa powodem, dla ktorego ta
   wlasnosc ma bramke w CI (`validate.yml`), a nie tylko konwencje:
   * przepisanie pliku przez sweeper albo break-glass daje diff DOKLADNIE tych linii, ktore sie zmienily,
     a nie 200 wpisow — czyli w commicie awaryjnym widac, co sie stalo;
   * `safe_dump` NIE ZNA KOMENTARZY. Komentarz dopisany recznie do tego pliku zniknalby przy pierwszym
     zapisie bota, po cichu. Bramka mowi o tym na pull requescie, zanim ktos wlozy tam uzasadnienie,
     ktore i tak ma miejsce w polu `change_ref`.

3. **DOPISANIE WPISU NIE PRZEPISUJE PLIKU.** Nowy czlonek dolacza jako TEKST na koncu — reszta pliku
   zostaje bajt w bajt. Diff wniosku to N dodanych linii, a nie 200 przepisanych, wiec review widzi
   zmiane, a nie szum; przy okazji okno konfliktu jest najmniejsze z mozliwych.

DLACZEGO WPIS DOPISUJEMY NA KONCU, A NIE W MIEJSCU WYNIKAJACYM Z SORTOWANIA: posortowana lista klada
wpisy jednej dywizji obok siebie, a dywizje onboarduja sie falami — to jest dokladnie ten uklad, ktory
w eksperymencie `experiments/konflikty-ukladow/` dal 1/10 pull requestow bez konfliktu. Kolejnosc w pliku
i tak nie znaczy nic: renderer kluczuje czlonka po TRESCI (`<dywizja>-<project_id>`), nie po pozycji.
"""
import pathlib

import yaml

# Nazwa pliku w JEDNYM miejscu — sciezki budowane recznie w czterech skryptach to czwarty sposob na to,
# zeby polowa systemu czytala inny plik niz druga polowa.
PLIK = "projects.yaml"
SCIEZKA = f"perimeter/{PLIK}"


class BladPliku(Exception):
    """Plik czlonkow jest nie do przyjecia. Zawsze fail-closed — nigdy „napraw i jedz dalej”."""


class LoaderBezDuplikatow(yaml.SafeLoader):
    """`SafeLoader`, ktory na duplikacie klucza mapy RZUCA, zamiast cicho brac ostatni."""


def _mapa_bez_duplikatow(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise BladPliku(
                f"{SCIEZKA}: klucz {key!r} wystepuje dwa razy w tej samej mapie "
                f"(linia {key_node.start_mark.line + 1}). YAML nie ma na to reguly poza „ostatni wygrywa”, "
                f"a to znaczy, ze jedna z dwoch wartosci zniknelaby bez sladu. Najczestsza przyczyna: "
                f"scalenie `merge=union` dwoch zmian W TYM SAMYM wpisie — rozwiaz je recznie."
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


LoaderBezDuplikatow.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _mapa_bez_duplikatow,
)


def dokument(tekst: str) -> dict:
    """Parsuje tresc pliku czlonkow. Rzuca `BladPliku` na kazdym ksztalcie, ktorego nie umiemy obsluzyc."""
    doc = yaml.load(tekst, Loader=LoaderBezDuplikatow)  # noqa: S506 — loader dziedziczy z SafeLoader
    if not isinstance(doc, dict):
        raise BladPliku(f"{SCIEZKA}: plik ma byc mapa z kluczem `members`, a jest {type(doc).__name__}")
    wpisy = doc.get("members")
    # `members: []` (pusty perimetr) jest LEGALNY i musi sie roznic od braku klucza. Brak klucza znaczy
    # „to nie jest ten plik”, a pusta lista znaczy „nikogo jeszcze nie ma” — degradacja w te strone jest
    # bezpieczna (zero czlonkow), ale nie wolno jej mylic z blednym plikiem.
    if wpisy is None:
        raise BladPliku(f"{SCIEZKA}: brak klucza `members` — plik czlonkow ma byc lista wpisow pod tym kluczem")
    if not isinstance(wpisy, list):
        raise BladPliku(f"{SCIEZKA}: `members` ma byc LISTA wpisow, a jest {type(wpisy).__name__}")
    return doc


def wczytaj_plik(p) -> dict:
    """Wczytuje plik czlonkow spod wskazanej sciezki."""
    p = pathlib.Path(p)
    if not p.exists():
        raise BladPliku(f"nie ma {p} — plik czlonkow jest wymagany (pusty perimetr zapisz jako `members: []`)")
    return dokument(p.read_text())


def wczytaj(root=".") -> dict:
    """Wczytuje plik czlonkow z korzenia repozytorium."""
    return wczytaj_plik(pathlib.Path(root) / SCIEZKA)


def klucz(wpis: dict) -> str:
    """Klucz czlonka = `<dywizja>-<project_id>`.

    TO NIE JEST KOSMETYKA — to ADRES ZASOBU W STANIE TERRAFORMA. Ten sam ciag byl wczesniej nazwa pliku
    (`perimeter/members/<dywizja>-<projekt>.yaml`), a renderer robil `trimsuffix(f, ".yaml")`. Wyliczanie
    go z tresci zamiast z nazwy pliku bylo warunkiem, zeby przejscie na jeden plik NIE zmienilo ani jednego
    adresu w stanie — a zmiana adresu granularnej reguly ACM to jej `destroy` i `create`, czyli okno bez
    autoryzacji na zywej granicy.
    """
    return f"{wpis.get('division')}-{wpis.get('project_id')}"


def mapa(wpisy: list) -> dict:
    """Wpisy jako mapa klucz→wpis. NIE UZYWAJ jej do wykrywania duplikatow — ona je gubi z definicji."""
    return {klucz(w): w for w in wpisy}


def duplikaty(wpisy: list) -> list:
    """Wszystkie duplikaty, po ktorych plik nie moze przejsc dalej. Lista komunikatow, pusta = czysto.

    TRZY OSIE, BO TO SA TRZY ROZNE AWARIE:
    * `project_id` i `project_number` — ten sam projekt opisany dwa razy. Przy dwoch plikach lapala to
      regula OPA porownujaca pliki; przy jednym pliku wpisy moga miec ten sam klucz i wtedy nie ma czego
      porownac, bo mapa juz jeden z nich zjadla. Dlatego liczymy na LISCIE.
    * KLUCZ — dwa wpisy, ktore daja ten sam adres w stanie Terraforma. To NIE wynika z dwoch poprzednich:
      klucz powstaje przez sklejenie dywizji z projektem, wiec `division: a-b` + `project_id: cccccc`
      i `division: a` + `project_id: b-cccccc` to dwa ROZNE projekty o jednym adresie. Terraform odmowi
      („Duplicate object key”), ale dopiero na planie i komunikatem o wyrazeniu `for`, a nie o wniosku.
    """
    problemy = []
    for pole in ("project_id", "project_number"):
        widziane = {}
        for i, w in enumerate(wpisy):
            v = w.get(pole)
            if v is None:
                continue  # brak pola to sprawa schematu, nie duplikatow
            if v in widziane:
                problemy.append(
                    f"wpisy #{widziane[v] + 1} ({klucz(wpisy[widziane[v]])}) i #{i + 1} ({klucz(w)}) "
                    f"maja ten sam {pole} = {v!r} — jeden projekt moze miec tylko jeden wpis"
                )
            else:
                widziane[v] = i
    widziane = {}
    for i, w in enumerate(wpisy):
        k = klucz(w)
        if k in widziane:
            problemy.append(
                f"wpisy #{widziane[k] + 1} i #{i + 1} daja ten sam klucz {k!r} — to jeden adres zasobu "
                f"w stanie Terraforma dla dwoch wpisow; zmien dywizje albo popraw project_id"
            )
        else:
            widziane[k] = i
    return problemy


def znajdz(wpisy: list, project_id=None, project_number=None):
    """Pierwszy wpis o tym `project_id` ALBO `project_number`. `None`, gdy takiego nie ma.

    PYTAMY O OBA POLA, bo tozsamosc projektu niesie kazde z nich osobno. Wniosek z literowka w dywizji
    (`risk` zamiast `risc`) ma inny klucz, ten sam projekt — i bez pytania o `project_number` przeszedlby
    jako onboarding nowego czlonka.
    """
    for w in wpisy:
        if project_id is not None and w.get("project_id") == project_id:
            return w
        if project_number is not None and str(w.get("project_number")) == str(project_number):
            return w
    return None


def zrzut(doc: dict) -> str:
    """Kanoniczna postac calego pliku. JEDNA definicja — bramka w CI porownuje z nia tresc z repo."""
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def wpis_jako_tekst(wpis: dict) -> str:
    """Jeden wpis jako element listy YAML — w tej samej postaci, w jakiej zapisalby go `zrzut`."""
    return yaml.safe_dump([wpis], sort_keys=False, allow_unicode=True)


def dopisz(root, wpis: dict) -> pathlib.Path:
    """Dopisuje wpis NA KONCU pliku, nie ruszajac reszty jego bajtow.

    Wyjatek: pusty perimetr (`members: []`) — tam nie ma czego zachowac, a `- …` po `[]` nie jest
    poprawnym YAML-em, wiec plik powstaje od nowa z kanonicznego zrzutu.
    """
    p = pathlib.Path(root) / SCIEZKA
    doc = dokument(p.read_text())
    doc["members"].append(wpis)
    if len(doc["members"]) == 1:
        p.write_text(zrzut(doc))
        return p
    tekst = p.read_text()
    if not tekst.endswith("\n"):
        tekst += "\n"
    p.write_text(tekst + wpis_jako_tekst(wpis))
    return p


def zapisz(root, doc: dict) -> pathlib.Path:
    """Przepisuje CALY plik kanonicznie. Dla zmiany istniejacego wpisu (promocja, break-glass, sweeper).

    Diff jest maly wylacznie dlatego, ze plik JUZ jest kanoniczny — pilnuje tego bramka w `validate.yml`.
    Bez niej pierwsze uzycie tej funkcji przepisaloby caly plik i schowalo realna zmiane w szumie.
    """
    p = pathlib.Path(root) / SCIEZKA
    p.write_text(zrzut(doc))
    return p
