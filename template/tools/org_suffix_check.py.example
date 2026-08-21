#!/usr/bin/env python3
"""Czy każdy obiekt ORG-SCOPED tego repozytorium da się postawić DRUGI RAZ w tej samej organizacji.

DLACZEGO TO ISTNIEJE — I DLACZEGO NIE ZAŁATWIA TEGO `terraform validate` ANI `plan`.

`iam-bootstrap` tworzy obiekty, których nazwa jest unikalna w SKALI ORGANIZACJI: rola własna
(`role_id`) i polityka IAM Deny (`name`). Jedna organizacja — jedna nazwa. Przy nazwie wpisanej na
sztywno DRUGI apply tego stacku w tej samej organizacji nie pada na starcie, tylko w POŁOWIE:

    Error: Custom project role organizations/<ORG>/roles/vpcScSinkReader already exists
           and must be imported

…po utworzeniu większości zasobów. Zostawia więc stan, którego nie opisuje żaden plik, i zabiera
jedyny moment, w którym ćwiczenie odtworzenia toru ma sens: organizację, która ten tor JUŻ MA
(DR, pilot obok produkcji, próba przed go-live). Koszt pomyłki jest asymetryczny — roli własnej nie
da się natychmiast odtworzyć pod tym samym id: kasowanie ma 7-dniowe okno `undelete`, a pełny proces
zwalniający identyfikator trwa 44 dni. „Skasuj i spróbuj ponownie" nie jest tu obejściem.

Ani `validate`, ani `plan`, ani `tflint` tego nie widzą: nazwa wpisana na sztywno jest POPRAWNA.
Niepoprawna jest dopiero wtedy, gdy ten sam kod zastosuje się drugi raz w tej samej organizacji —
czyli w sytuacji, której żadne z tych narzędzi nie modeluje.

CO ZMIERZONE (i po co ta bramka powstała akurat teraz). Zmienna `org_resource_suffix` została
dodana właśnie po to, żeby drugi apply przechodził — i doklejono ją do TRZECH obiektów z CZTERECH.
Czwarty (`vpcScSinkReader`) został bez sufiksu, więc cel zmiany nie był osiągnięty, ale WYGLĄDAŁ na
osiągnięty. Zbiór obiektów objętych sufiksem opisywał komentarz („to jedyne trzy obiekty tego
stacku"), a ról org-level było w tym samym pliku trzy, nie dwie. Lista stojąca OBOK mechanizmu
rozjeżdża się z nim w ciszy — dlatego ta bramka nie ma listy nazw (DEC-57, DEC-59).

CZEGO BRAMKA PYTA. Nie „czy nazwa zawiera `var.org_resource_suffix`" — bo to znów byłaby jedna
zapisana odpowiedź na pytanie, które ma kilka poprawnych. Pyta o WŁASNOŚĆ:

    nazwa obiektu org-scoped MUSI zależeć od wejścia, które da się USTAWIĆ INACZEJ w drugim
    wdrożeniu w TEJ SAMEJ organizacji

Stąd dwa wykluczenia, oba konieczne:
  * literał (`"vpcScSinkReader"`) — stały, więc kolizja pewna;
  * `var.org_id` — zmienna, ale w obu wdrożeniach w tej samej organizacji ma tę SAMĄ wartość, więc
    nazwa `"x-${var.org_id}"` jest tak samo stała jak literał. Bez tego wykluczenia bramkę dałoby
    się uciszyć doklejeniem czegokolwiek.

`var.bucket_id` w `violations-sink` przechodzi i ma przechodzić: sink org-level bierze nazwę wprost
z wejścia operatora, więc druga instancja różnicuje ją bez żadnego sufiksu. Bramka pilnuje
WŁAŚCIWOŚCI, a nie jednego sposobu jej osiągnięcia.

FAIL-CLOSED NA NIEZNANYM TYPIE — to jest ta część, która ma przeżyć autora. Zbiór typów org-scoped
nie jest zamknięty (`google_organization_iam_custom_role`, `google_iam_deny_policy`,
`google_logging_organization_sink`, …). Typ, którego ta bramka NIE ZNA, a który w drzewie jest
org-scoped, daje CZERWONO z żądaniem klasyfikacji — zamiast przejść jako „nie znam, więc pewnie OK".
Bez tego czwarty obiekt powtórzyłby się przy piątym, dokładnie tak jak powtórzył się przy czwartym.

CZEGO ŚWIADOMIE NIE POKRYWAMY (żeby zielony wynik nie znaczył więcej, niż znaczy):

  * OBIEKTÓW ACCESS CONTEXT MANAGER (`terraform/`): perimeter, access levele, reguły. Ich nazwy są
    unikalne w obrębie ACCESS POLICY, a nie organizacji, i pochodzą z `perimeter/policy.yaml` —
    czyli z wejścia, które druga instancja i tak podmienia w całości. To osobne pytanie („czy dwie
    instancje mogą dzielić jedną politykę dostępu") i osobna decyzja, nie efekt uboczny tej bramki.
  * OBIEKTÓW PROJECT-SCOPED (konta serwisowe, pula WIF, `google_project_iam_custom_role`). One nie
    kolidują w organizacji — kolidują w PROJEKCIE, a druga instancja i tak musi dostać własny
    `identity_project_id` (patrz `iam-bootstrap/terraform.tfvars.sample`). Rozszerzenie bramki na
    nie oznaczałoby żądanie sufiksu tam, gdzie rozwiązaniem jest inny projekt.
  * TEGO, CZY SUFIKS JEST NIEPUSTY. Pusty jest poprawny i domyślny — to pierwsza (produkcyjna)
    instancja. Bramka pyta o ZDOLNOŚĆ do rozróżnienia, nie o jej użycie.

Użycie (patrz `.github/actions/bramki-tresci/action.yml`):
    python3 tools/org_suffix_check.py
    python3 tools/org_suffix_check.py --korzen .
"""
import argparse
import pathlib
import re
import sys

# Pole niosące nazwę GLOBALNĄ DLA ORGANIZACJI — jedno na typ. Wpis tutaj jest klasyfikacją typu,
# a nie listą obiektów: obiekty wylicza drzewo, ten słownik mówi wyłącznie, GDZIE w danym typie
# leży nazwa. Nowy typ org-scoped nie przechodzi bez wpisu (patrz `NIENAZWANE` i błąd niżej).
POLE_NAZWY = {
    "google_organization_iam_custom_role": "role_id",
    "google_iam_deny_policy": "name",
    "google_logging_organization_sink": "name",
}

# Typy org-scoped BEZ własnej nazwy: przypisanie IAM jest identyfikowane przez trójkę
# (organizacja, rola, principal), a nie przez nazwę nadaną przez nas. Dwa wdrożenia nadające tę samą
# rolę temu samemu principalowi to JEDNO przypisanie, nie kolizja — a odkąd rola niesie sufiks,
# trójka i tak się różni. Doklejanie sufiksu byłoby tu nie do czego.
NIENAZWANE = {
    "google_organization_iam_member",
    "google_organization_iam_binding",
    "google_organization_iam_policy",
    "google_organization_iam_audit_config",
}

# Zmienne, które w DRUGIM wdrożeniu w tej samej organizacji mają tę samą wartość — więc nazwa oparta
# wyłącznie o nie jest tak samo stała jak literał. To NIE jest lista wygody: `org_id` identyfikuje
# organizację, czyli dokładnie to, co obie instancje mają wspólne.
NIEROZROZNIAJACE = {"org_id"}


def bez_komentarzy(tekst: str) -> str:
    """HCL z wyzerowanymi komentarzami — bez zmiany DŁUGOŚCI ani numeracji linii.

    Podmieniamy znaki na spacje zamiast wycinać, żeby `str.find`, numer linii i dopasowania regex
    wskazywały to samo miejsce co w pliku źródłowym; inaczej komunikat bramki podawałby linię, której
    autor nie znajdzie w edytorze.

    Skaner musi rozumieć STRINGI i HEREDOKI, a nie tylko `#` na początku linii. W tym repozytorium
    występują oba przypadki graniczne naraz: `url = "${local.runbook}#kotwica"` (hash W STRINGU —
    naiwne cięcie po `#` urwałoby klamrę zamykającą) oraz `content = <<-DOC … DOC` w `alerts.tf`
    (proza z nawiasami W TREŚCI heredoka). Bez tego dopasowanie klamer rozjeżdża się o kilka bloków
    i bramka bada nie ten fragment pliku, co trzeba — cicho, bo wynik nadal jest jakimś tekstem.
    """
    wynik = list(tekst)
    i, n = 0, len(tekst)
    while i < n:
        z = tekst[i]
        if z == '"':
            i += 1
            while i < n and tekst[i] != '"':
                i += 2 if tekst[i] == "\\" else 1
            i += 1
        elif z == "#" or tekst.startswith("//", i):
            while i < n and tekst[i] != "\n":
                wynik[i] = " "
                i += 1
        elif tekst.startswith("/*", i):
            koniec = tekst.find("*/", i + 2)
            koniec = n if koniec == -1 else koniec + 2
            for j in range(i, koniec):
                if wynik[j] != "\n":
                    wynik[j] = " "
            i = koniec
        elif tekst.startswith("<<", i):
            m = re.match(r"<<[-~]?\s*([A-Za-z_][A-Za-z0-9_]*)", tekst[i:])
            if not m:
                i += 2
                continue
            koniec = re.search(rf"^\s*{m.group(1)}\s*$", tekst[i:], re.M)
            i = n if not koniec else i + koniec.end()
        else:
            i += 1
    return "".join(wynik)


def blok(tekst: str, start: int) -> tuple[str, int]:
    """Treść bloku od klamry otwierającej pod `start` do jej pary. Zwraca (treść, pozycja_za_blokiem)."""
    glebokosc, i = 0, start
    while i < len(tekst):
        if tekst[i] == "{":
            glebokosc += 1
        elif tekst[i] == "}":
            glebokosc -= 1
            if glebokosc == 0:
                return tekst[start + 1:i], i + 1
        i += 1
    return tekst[start + 1:], len(tekst)


def atrybut(tresc: str, nazwa: str) -> str | None:
    """Wartość atrybutu `nazwa = …` z treści bloku (pierwsza linia wyrażenia)."""
    m = re.search(rf"^\s*{re.escape(nazwa)}\s*=\s*(.+?)\s*$", tresc, re.M)
    return m.group(1) if m else None


def stacki(korzen: pathlib.Path) -> list[pathlib.Path]:
    """Katalogi najwyższego poziomu z konfiguracją Terraforma — z DRZEWA, nie z listy (DEC-34).

    Ta sama zasada, co w `selftest.stacki_terraform()`: pytanie „czy każdy stack jest sprawdzony"
    wolno zadać wyłącznie zbiorowi wziętemu z rzeczywistości. `.terraform/` odpada — to katalog
    roboczy `init`-a z kopiami cudzych modułów, a nie stack tego repozytorium.
    """
    return sorted(
        d for d in korzen.iterdir()
        if d.is_dir() and not d.name.startswith(".") and any(d.glob("*.tf"))
    )


def locals_stacku(pliki: list[tuple[pathlib.Path, str]]) -> dict[str, str]:
    """Mapa `nazwa -> wyrażenie` ze wszystkich bloków `locals {}` stacku.

    Potrzebna, bo nazwa obiektu bywa podana pośrednio (`name = local.deny_policy_name`), a pytanie
    bramki dotyczy tego, od czego ta nazwa REALNIE zależy. Bez rozwinięcia locala bramka albo
    odrzucałaby poprawny kod, albo przepuszczała dowolny — i w obu przypadkach nie mierzyłaby niczego.
    """
    mapa: dict[str, str] = {}
    for _, tekst in pliki:
        for m in re.finditer(r"^locals\s*\{", tekst, re.M):
            tresc, _ = blok(tekst, m.end() - 1)
            for linia in tresc.splitlines():
                p = re.match(r"\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)\s*$", linia)
                if p:
                    mapa.setdefault(p.group(1), p.group(2))
    return mapa


def zrodla(wyrazenie: str, lokalne: dict[str, str], for_each: str | None) -> set[str]:
    """Wejścia, od których zależy wyrażenie — po rozwinięciu `local.*` i `each.*`.

    Rozwijamy przechodnio (local może wskazywać na local), z ochroną przed cyklem: bez niej pętla
    `a = local.b` / `b = local.a` zawiesiłaby bramkę zamiast ją zaczerwienić.
    """
    do_zbadania, odwiedzone, znalezione = [wyrazenie], set(), set()
    while do_zbadania:
        e = do_zbadania.pop()
        if e in odwiedzone:
            continue
        odwiedzone.add(e)
        znalezione |= set(re.findall(r"\bvar\.([a-zA-Z_][a-zA-Z0-9_]*)", e))
        for nazwa in re.findall(r"\blocal\.([a-zA-Z_][a-zA-Z0-9_]*)", e):
            if nazwa in lokalne:
                do_zbadania.append(lokalne[nazwa])
            else:
                znalezione.add(f"<local.{nazwa} spoza tego stacku>")
        # `each.key`/`each.value` niosą wartość z `for_each` TEGO bloku — więc pytanie o zależność
        # przenosi się na tamto wyrażenie, a nie kończy na „to iterator, pewnie się różni".
        if re.search(r"\beach\.", e) and for_each:
            do_zbadania.append(for_each)
    return znalezione


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--korzen", default=".", help="korzen repozytorium (domyslnie biezacy katalog)")
    args = ap.parse_args()
    korzen = pathlib.Path(args.korzen)

    problemy: list[str] = []
    zrobione: list[str] = []
    zbadane_pliki = 0
    org_scoped = 0

    katalogi = stacki(korzen)
    if not katalogi:
        # Pusty zbior jest bledem, nie cisza: bramka bez ani jednego stacku przechodzi zawsze
        # i nie chroni niczego (ta sama pulapka, co przy kotwicach runbooka — DEC-57).
        print(f"BLAD: w {korzen} nie ma ANI JEDNEGO katalogu z plikami *.tf — bramka nie miala czego "
              f"zbadac, wiec jej zielony wynik nic by nie znaczyl", file=sys.stderr)
        return 1

    for katalog in katalogi:
        pliki = [(p, bez_komentarzy(p.read_text())) for p in sorted(katalog.glob("*.tf"))]
        zbadane_pliki += len(pliki)
        lokalne = locals_stacku(pliki)

        for sciezka, tekst in pliki:
            for m in re.finditer(r'^resource\s+"([^"]+)"\s+"([^"]+)"\s*\{', tekst, re.M):
                typ, nazwa_zasobu = m.group(1), m.group(2)
                tresc, _ = blok(tekst, m.end() - 1)
                adres = f"{katalog.name}/{sciezka.name}: {typ}.{nazwa_zasobu}"

                # ORG-SCOPED wyprowadzamy z TRESCI bloku, nie z prefiksu nazwy typu: `google_iam_deny_policy`
                # nie ma w nazwie slowa "organization", a jest obiektem org-level (parent = organizations/...).
                # Klasyfikacja po nazwie typu przepuscilaby wlasnie ten obiekt.
                if not (atrybut(tresc, "org_id") or "organizations/" in tresc):
                    continue
                org_scoped += 1

                if typ in NIENAZWANE:
                    zrobione.append(f"{adres} — przypisanie IAM, wlasnej nazwy org-level nie ma")
                    continue

                pole = POLE_NAZWY.get(typ)
                if pole is None:
                    problemy.append(
                        f"{adres} — typ ORG-SCOPED, ktorego ta bramka NIE ZNA. Dopisz go do "
                        f"`POLE_NAZWY` (podaj pole niosace nazwe org-globalna) albo do `NIENAZWANE` "
                        f"(gdy obiekt wlasnej nazwy nie ma). Bramka nie przepuszcza typu "
                        f"nieklasyfikowanego, bo wlasnie tak zginal czwarty obiekt tej klasy")
                    continue

                wyrazenie = atrybut(tresc, pole)
                if wyrazenie is None:
                    problemy.append(
                        f"{adres} — brak pola `{pole}`, w ktorym ten typ niesie nazwe org-globalna. "
                        f"Albo pole nazywa sie inaczej (popraw `POLE_NAZWY`), albo nazwa powstaje "
                        f"gdzie indziej i bramka nie ma czego zbadac")
                    continue

                for_each = atrybut(tresc, "for_each")
                wejscia = zrodla(wyrazenie, lokalne, for_each)
                rozrozniajace = wejscia - NIEROZROZNIAJACE
                if rozrozniajace:
                    zrobione.append(
                        f"{adres} — `{pole}` zalezy od {', '.join('var.' + w if not w.startswith('<') else w for w in sorted(rozrozniajace))}")
                else:
                    powod = ("nie zalezy od zadnego wejscia" if not wejscia else
                             f"zalezy wylacznie od {', '.join('var.' + w for w in sorted(wejscia))}, "
                             f"a to w tej samej organizacji ma te sama wartosc")
                    problemy.append(
                        f"{adres} — `{pole} = {wyrazenie}` {powod}. Nazwa jest w organizacji STALA, "
                        f"wiec drugi apply w tej samej organizacji padnie na `already exists and must "
                        f"be imported` — w POLOWIE, po utworzeniu wiekszosci zasobow")

    for z in zrobione:
        print(f"  OK    {z}")
    for z in problemy:
        print(f"  BLAD  {z}")

    if problemy:
        # Bez tego stderr wyprzedza stdout i podsumowanie ląduje NAD listą błędów, którą podsumowuje.
        sys.stdout.flush()
        print(f"\nNIEZALICZONE ({len(problemy)}): obiekt org-scoped, o ktorym nie da sie powiedziec, "
              f"ze druga instancja toru w tej samej organizacji go NIE ROZBIJE — bo nazwa jest tam stala "
              f"albo bo typ nie zostal sklasyfikowany. Roli wlasnej nie odzyskuje sie od reki: zwolnienie "
              f"identyfikatora trwa 44 dni, wiec ten blad kosztuje wiecej niz jeden nieudany apply.",
              file=sys.stderr)
        return 1

    print(f"\nOK: {org_scoped} obiektow org-scoped w {zbadane_pliki} plikach *.tf "
          f"({len(katalogi)} stackow) — kazdy da sie postawic drugi raz w tej samej organizacji")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
