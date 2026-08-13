#!/usr/bin/env python3
"""Czy granica wyglada tak, jak plik w gicie — werdykt czytany z TRESCI planu, nie z koloru przebiegu.

PO CO TO ISTNIEJE (zmierzone, nie hipotetyczne)
==============================================
`terraform apply` na regule EGZEKWOWANEJ aktualizowanej W MIEJSCU potrafi zglosic `rc=0` i NIE zapisac
zmiany. Pomiar na zywej organizacji: z 9 przebiegow, w ktorych OBA rownolegle applye zglosily sukces,
**5 skonczylo sie brakiem jednej ze zmian w API** — bez jednego bledu, przy dwoch zielonych przebiegach
(DEC-6, DEC-45). Kiedy provider w ogole cos zglasza, mowi `Provider produced inconsistent result
after apply … Root object was present, but now absent` — nieodroznialnie od „ktos skasowal moja regule".

Zrodlo roznicy jest w schemacie providera: warianty `..._dry_run_*` nie maja `Update` (kazda zmiana to
ForceNew), warianty egzekwowane `Update` maja i ida read-modify-write po CALEJ liscie regul. Jednostka
wylacznosci jest przy tym ACCESS POLICY, nie perimetr, a `concurrency:` obejmuje jedno repozytorium —
wiec pisarz spoza tego workflowa (czlowiek z `gcloud`, osobny stack, odtworzenie perimetru) wchodzi
w to samo okno i nic go nie serializuje.

Wniosek operacyjny jest jednozdaniowy: **zielony `apply` nie konczy zmiany — konczy ja odczyt.**
Ten skrypt jest tym odczytem, wykonanym mechanizmem, ktorym pipeline i tak opisuje granice.

CZEGO TO NIE WYKRYWA (nazwane, zeby nikt nie czytal tej bramki szerzej, niz siega)
=================================================================================
* Zmiany, ktore ROZJECHALY SIE I WROCILY miedzy `apply` a tym planem — okno jest krotkie, ale istnieje.
* Wszystkiego, czego Terraform nie ma w stanie: regul dopisanych z konsoli, resztek po cudzym apply,
  obiektow spod `lifecycle.ignore_changes` (szkielet perimetru — patrz DEC-6/DEC-36). Ten skrypt
  odpowiada na pytanie „czy zywa granica zgadza sie z DEKLARACJA", nie „czy nikt nic nie dopisal".
* Rozjazdu wewnatrz atrybutu, ktory provider zglasza jako `(known after apply)` — plan po apply juz go
  zna, wiec akurat tu problemu nie ma, ale zaden plan nie wie wiecej niz schemat zasobu.

DLACZEGO PLAN, A NIE `perimeters describe`
==========================================
Porownanie ksztaltu z API z tym, co apply zamierzal, jest tansze (jedno wywolanie zamiast pelnego
refreshu), ale wymaga DRUGIEGO renderera deklaracji — a dwa renderery rozjezdzaja sie predzej czy
pozniej i wtedy bramka opisuje wlasny blad, nie granice. Do tego `describe` widzi WYLACZNIE perimetr,
a ten stan Terraforma trzyma takze access levele, obiekt kontraktu w buckecie i polityki alertow;
cicha utrata na ktorymkolwiek z nich przeszlaby niezauwazona. Plan pyta o wszystko naraz i tym samym
mechanizmem, ktorym pipeline opisuje granice — kosztem pelnego refreshu. Cena jest nazwana w naglowku
kroku w `apply.yml` i mierzona w KAZDYM przebiegu (`--sekundy`), zeby nie trzeba jej bylo zgadywac.

TRZY WERDYKTY, NIE DWA
======================
`ZGODNE`     — plan pusty: granica jest tym, co w gicie.
`ROZJAZD`    — plan niepusty ZARAZ PO udanym apply: desired-state NIE zostal osiagniety.
`NIE ZMIERZONO` — planu nie da sie odczytac (awaria srodowiska, brak uprawnien, przerwany refresh).

Trzeci werdykt jest tu z tego samego powodu, dla ktorego eksperyment o wyscigu ma kategorie
„nierozstrzygniete": **awaria narzedzia nie moze wygladac jak wynik pomiaru** — ani jak porazka
(„zmiana nie wyladowala"), ani jak sukces („czysto"). `plan` przy bledzie srodowiska tez zwraca
niezero; mylenie tego z „zmiana nie wyladowala" byloby dokladnie tym bledem, ktory dwa razy zepsul
pomiar wyscigu. Dlatego kod wyjscia planu jest tu WEJSCIEM, a nie werdyktem: rozstrzyga tresc.

Uzycie (z korzenia repo):
    python3 tools/weryfikacja_po_apply.py --kod <rc planu> --plan-po terraform/weryfikacja.json \\
        [--plan-przed terraform/plan.json] [--log weryfikacja.log] [--sekundy 12.9]

Kod wyjscia: 0 = ZGODNE, 1 = ROZJAZD albo NIE ZMIERZONO (oba czerwienia przebieg).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

# Akcje planu, ktore NIE sa zmiana granicy. `no-op` mowi samo za siebie; `read` to odczyt zrodla danych
# odlozony na czas apply — nie zmienia niczego w chmurze, a policzony jako rozjazd dawalby falszywy alarm
# w kazdym przebiegu konfiguracji z takim zrodlem.
BEZ_SKUTKU = ({"no-op"}, {"read"})


def zmiany(plan: dict) -> list[dict]:
    """Zasoby, ktore plan po apply NADAL chce zmienic — czyli tresc werdyktu."""
    out = []
    for rc in plan.get("resource_changes") or []:
        akcje = set((rc.get("change") or {}).get("actions") or [])
        if akcje in BEZ_SKUTKU:
            continue
        out.append({"adres": rc.get("address", "?"), "akcje": sorted(akcje)})
    return sorted(out, key=lambda d: d["adres"])


def outputy(plan: dict) -> list[str]:
    """Outputy z niepustym diffem. `-detailed-exitcode` zwraca 2 takze dla nich SAMYCH."""
    out = []
    for nazwa, zmiana in (plan.get("output_changes") or {}).items():
        if set(zmiana.get("actions") or []) not in BEZ_SKUTKU:
            out.append(nazwa)
    return sorted(out)


def zamierzone(plan: dict | None) -> set[str]:
    """Adresy, ktore TEN apply zamierzal zmienic — z planu, ktory zostal zastosowany."""
    return {z["adres"] for z in zmiany(plan)} if plan else set()


def wczytaj(sciezka: str | None) -> tuple[dict | None, str]:
    """Plan jako JSON albo powod, dla ktorego go nie ma. Brak pliku to NIE jest pusty plan."""
    if not sciezka:
        return None, "nie podano sciezki"
    p = pathlib.Path(sciezka)
    if not p.is_file():
        return None, f"pliku {sciezka} nie ma (plan nie doszedl do zapisu?)"
    try:
        return json.loads(p.read_text()), ""
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, f"{sciezka} nie jest czytelnym JSON-em: {e}"


def ogon(sciezka: str | None, linii: int = 25) -> str:
    """Koniec logu planu — do werdyktu NIE ZMIERZONO, zeby nie trzeba bylo otwierac przebiegu."""
    if not sciezka or not pathlib.Path(sciezka).is_file():
        return "(logu planu brak)"
    linie = pathlib.Path(sciezka).read_text(errors="replace").splitlines()
    return "\n".join(linie[-linii:])


def wypisz(tytul: str, tresc: str, blad: bool) -> None:
    """Werdykt niesie ADNOTACJA i podsumowanie, nie sam kolor przebiegu (DEC-26)."""
    poziom = "error" if blad else "notice"
    pierwsza = tresc.strip().splitlines()[0] if tresc.strip() else tytul
    print(f"::{poziom} title={tytul}::{pierwsza}")
    print(tresc)
    plik = os.environ.get("GITHUB_STEP_SUMMARY")
    if plik:
        with open(plik, "a", encoding="utf-8") as fh:
            fh.write(f"\n### {'❌' if blad else '✅'} Weryfikacja stanu po apply — {tytul}\n\n{tresc}\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kod", required=True, help="kod wyjscia `terraform plan -detailed-exitcode`")
    ap.add_argument("--plan-po", required=True, help="JSON planu wykonanego PO apply")
    ap.add_argument("--plan-przed", help="JSON planu, ktory ten przebieg ZASTOSOWAL")
    ap.add_argument("--log", help="log planu po apply (cytowany przy NIE ZMIERZONO)")
    ap.add_argument("--sekundy", help="ile trwal plan weryfikujacy — cena tej bramki, w kazdym przebiegu")
    a = ap.parse_args(argv)

    kod = a.kod.strip()
    cena = f"\nKoszt tej weryfikacji w tym przebiegu: **{a.sekundy} s** (pelny refresh stanu).\n" \
        if a.sekundy else ""
    po, powod = wczytaj(a.plan_po)

    # NIE ZMIERZONO — pierwszy, bo bez czytelnego planu nie ma z czego czytac werdyktu. Dotyczy TAKZE
    # kodu 0: „plan zglosil brak roznic, ale nie zostawil po sobie planu" nie jest dowodem zgodnosci,
    # tylko awaria narzedzia — a bramka, ktora w takiej sytuacji swieci na zielono, nie jest bramka.
    if po is None or kod not in {"0", "2"}:
        powod_kodu = f"`terraform plan` zwrocil **{kod}**" if kod not in {"0", "2"} else f"plan: {powod}"
        wypisz("NIE ZMIERZONO", (
            f"**Nie wiadomo, czy zmiana wyladowala** — weryfikacja sie nie wykonala ({powod_kodu}).\n\n"
            "To NIE znaczy „zmiana nie weszla” i NIE znaczy „granica jest czysta”. `terraform plan` zwraca\n"
            "niezero takze przy awarii srodowiska (wygasle poswiadczenia, `403`, limit tempa, przerwany\n"
            "refresh), a takiej awarii nie wolno raportowac jako wyniku pomiaru.\n\n"
            "CO ZROBIC: przeczytaj ogon logu nizej i usun przyczyne, potem powtorz ten przebieg\n"
            "(`workflow_dispatch` na galezi domyslnej). Do czasu rozstrzygniecia traktuj stan granicy jako\n"
            "NIEZNANY — rozstrzyga odczyt z API:\n"
            "`gcloud access-context-manager perimeters describe <perimetr> --policy=<polityka>`.\n\n"
            f"{cena}\n<details><summary>ogon logu planu</summary>\n\n```\n{ogon(a.log)}\n```\n</details>"
        ), blad=True)
        return 1

    rozjazd, out = zmiany(po), outputy(po)

    if not rozjazd and not out:
        # Sprzecznosc kodu z trescia rozstrzygamy na korzysc TRESCI, ale nazywamy ja: „2 bez ani jednej
        # zmiany w planie" znaczy, ze nie rozumiemy tego planu, a nie ze jest pusty.
        if kod == "2":
            wypisz("NIE ZMIERZONO", (
                "**Kod planu (`2`) przeczy jego tresci** — `-detailed-exitcode` zglosil roznice, a w planie\n"
                "nie ma ani jednej zmiany zasobu ani outputu. Nie umiemy tego wytlumaczyc, wiec nie oglaszamy\n"
                "zgodnosci: werdykt idzie na czerwono z nazwana przyczyna, a nie na zielono „bo lista pusta”.\n\n"
                f"CO ZROBIC: obejrzyj `{a.plan_po}` w artefaktach przebiegu i porownaj z odczytem z API.\n{cena}"
            ), blad=True)
            return 1
        wypisz("ZGODNE", (
            "Plan wykonany BEZPOSREDNIO PO `apply` jest pusty: zywa granica zgadza sie z deklaracja\n"
            f"w gicie (`{os.environ.get('GITHUB_SHA', 'HEAD')[:12]}`). Zapis wszedl w calosci.\n{cena}"
        ), blad=False)
        return 0

    przed, _ = wczytaj(a.plan_przed)
    nasze = zamierzone(przed)
    adresy = {z["adres"] for z in rozjazd}
    wspolne, obce = sorted(adresy & nasze), sorted(adresy - nasze)

    lista = "\n".join(f"* `{z['adres']}` → {', '.join(z['akcje'])}"
                      f"{'  ← **ten apply wlasnie to zmienial**' if z['adres'] in nasze else ''}"
                      for z in rozjazd)
    if out:
        lista += f"\n* outputy z niepustym diffem: {', '.join(f'`{o}`' for o in out)}"

    # Dwa ksztalty rozjazdu, dwie rozne przyczyny i dwie rozne procedury. Rozroznienie bierze sie
    # z PRZECIECIA ze zbiorem adresow, ktore ten przebieg zamierzal zmienic — nie ze zgadywania.
    if wspolne:
        czym = (f"**Zasoby, ktore ten apply wlasnie zmienial, NADAL roznia sie od deklaracji**: "
                f"{', '.join(f'`{a_}`' for a_ in wspolne)}.\n"
                "To jest ksztalt CICHEJ UTRATY opisanej w DEC-6: `apply` zglosil sukces, a zapisu nie ma w API.\n"
                "Najczestsza przyczyna to rownolegly zapis do TEJ SAMEJ access policy (jednostka eTagu to\n"
                "polityka, nie perimetr) — z tego repozytorium chroni `concurrency: vpc-sc-apply`, spoza\n"
                "niego nie chroni nic.")
    else:
        czym = ("**Zaden z rozniacych sie zasobow nie byl przedmiotem tego apply.** To nie wyglada na cicha\n"
                "utrate wlasnego zapisu, tylko na zmiane granicy Z ZEWNATRZ pipeline'u (czlowiek z `gcloud`,\n"
                "osobny stack, odtworzenie perimetru) albo na dryf, ktory istnial juz przed tym przebiegiem.")

    wypisz("ROZJAZD", (
        "**Plan wykonany ZARAZ PO udanym `apply` NIE jest pusty** — czyli stan opisany w gicie NIE zostal\n"
        "osiagniety, mimo ze `apply` zakonczyl sie sukcesem.\n\n"
        f"{czym}\n\n"
        f"Roznice (z tresci planu, nie z kodu wyjscia):\n{lista}\n\n"
        "CO ZROBIC — w tej kolejnosci:\n"
        "1. **Odczytaj granice z API** (zrodlo prawdy, nie stan Terraforma):\n"
        "   `gcloud access-context-manager perimeters describe <perimetr> --policy=<polityka> --format=json`.\n"
        "2. Sprawdz, czy w oknie tego przebiegu pisal ktos jeszcze — alert `konfiguracja zmieniona poza\n"
        "   pipeline'em` i log audytowy `accesscontextmanager.googleapis.com`.\n"
        "3. **Powtorz apply** (`workflow_dispatch` na galezi domyslnej). Zapis jest idempotentny, a przy\n"
        "   braku drugiego pisarza drugi przebieg konczy sie pusto — jesli NIE konczy, to nie jest wyscig\n"
        "   i szukaj przyczyny w tresci planu wyzej.\n"
        "4. Nie zamykaj zgloszenia na zielonym `apply` — zamykaj je na PUSTYM planie po apply.\n\n"
        "Czego NIE robic: nie dokladaj `retry` na eTagu. Retry leczy wylacznie sciezke, ktora zglasza blad,\n"
        "a podnosi odsetek przebiegow „oba OK” — czyli tych, w ktorych zmierzono utrate (DEC-6, DEC-45).\n"
        f"{cena}"
    ), blad=True)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
