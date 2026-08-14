#!/usr/bin/env python3
"""`continue-on-error` albo ma powod zapisany OBOK i widoczny werdykt — albo znika.

PO CO TEN GUARD ISTNIEJE (zmierzone, nie hipotetyczne)
=====================================================
Krok z `continue-on-error: true` raportuje w REST API GitHuba `steps[].conclusion: "success"` **mimo ze
padl** — per-krokowego `outcome` API nie wystawia w ogole. Sonda diagnostyczna wygladala wiec na w pelni
zielona (`A: success`, `B: success`), podczas gdy w logu obie proby konczyly sie `##[error]`. To jest
druga polowa tego samego defektu, co „czerwony pipeline nierozroznialny od odrzucenia wniosku" (DEC-26),
tylko w przeciwna strone: **zielony krok != krok, ktory sie udal**.

Krok, ktorego porazka jest NIEWIDOCZNA w API, jest gorszy niz krok bez tej flagi: bez flagi porazka
czerwieni job i ktos ja zobaczy; z flaga porazka wyglada jak sukces i nie zobaczy jej nikt.

CO WOLNO, A CZEGO NIE
=====================
1. Na POWIERZCHNI BRAMEK (`.github/actions/**`) — flaga jest ZAKAZANA bez wyjatkow. Tam kazdy krok jest
   bramka albo dostarcza bramkom narzedzi, a bramka, ktorej porazka nie czerwieni niczego, nie jest
   bramka. Dodatkowo API nie wystawia krokow wewnatrz akcji zlozonej w ogole, wiec porazka nie zostawia
   TAM zadnego sladu poza logiem.
2. W workflowach — wolno, ale przy trzech warunkach naraz:
   a) krok ma `id`,
   b) POWOD stoi w komentarzu bezposrednio nad flaga (`# POWOD (continue-on-error): …`) — po to, zeby
      nastepny czytajacy nie musial go odgadywac z nazwy kroku,
   c) `steps.<id>.outcome` jest gdzies w tym samym jobie wypisywany do `$GITHUB_STEP_SUMMARY` — czyli
      werdykt kroku jest widoczny bez czytania logu. To jest warunek, ktory realnie zamyka zmierzony
      defekt; sam komentarz bylby deklaracja.

Uzycie: `python3 tools/continue_on_error_check.py` (z korzenia repo). Kod wyjscia 1 = naruszenie.
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

KORZEN = pathlib.Path(__file__).resolve().parents[1]
FLAGA = re.compile(r"^\s*continue-on-error\s*:")
POWOD = re.compile(r"^\s*#\s*POWOD \(continue-on-error\):\s*\S")


def powierzchnie() -> list[pathlib.Path]:
    """Wykonywalne YAML-e, OBA rozszerzenia. Kolejnosc stabilna — komunikat ma sie nie zmieniac.

    GitHub Actions honoruje `.yml` i `.yaml` IDENTYCZNIE, wiec `.github/workflows/cichy.yaml`
    i `.github/actions/obejscie/action.yaml` sa WYKONYWANE. Glob widzacy tylko `*.yml` nie widzial ich
    wcale — czyli jedna linijka `continue-on-error: true` w pliku o „drugim" rozszerzeniu czynila
    CALY zestaw bramek doradczym, a REST API raportowalo `conclusion: success`. Zmierzone (#2073):
    dwa takie wsady przeszly guarda, ktory zameldowal „zero naruszen".
    """
    return sorted({p for wz in ("*.yml", "*.yaml") for p in (KORZEN / ".github/workflows").glob(wz)}
                  | {p for wz in ("*/action.yml", "*/action.yaml")
                     for p in (KORZEN / ".github/actions").glob(wz)})


def prawda(v) -> bool:
    """`continue-on-error: false` nie jest naruszeniem — jest zapisaniem tego, co i tak jest domyslne.

    WYRAZENIE `${{ … }}` JEST naruszeniem, a nie „falszem". Statycznie nieocenialne znaczy „NIE WIEM",
    a „nie wiem" != „false": `continue-on-error: ${{ github.event_name == 'push' }}` to udokumentowana
    skladnia GitHuba i na zdarzeniu `push` daje dokladnie ten tryb awarii, dla ktorego ten guard
    powstal. Zmierzone (#2073) i najgrozniejszy z trzech przypadkow, bo plik BYL skanowany — guard
    go otwieral, czytal te linie i mimo to przepuszczal. Flaga sterowana wyrazeniem podlega wiec tym
    samym trzem warunkom (`id` + POWOD + `outcome` w podsumowaniu), co flaga wpisana na sztywno.
    """
    s = str(v).strip().lower()
    return s in {"true", "1", "yes"} or "${{" in s


def bledy_tekstowe(plik: pathlib.Path) -> list[str]:
    """Powod zapisany OBOK — czytany z tekstu, bo `yaml.safe_load` komentarzy nie widzi."""
    wynik: list[str] = []
    linie = plik.read_text().splitlines()
    for i, linia in enumerate(linie):
        if not FLAGA.match(linia) or not prawda(linia.split(":", 1)[1]):
            continue
        # Pusta linia miedzy komentarzem a flaga jest dopuszczalna — rozdziela je formatowanie, nie sens.
        j = i - 1
        while j >= 0 and not linie[j].strip():
            j -= 1
        if j < 0 or not POWOD.match(linie[j]):
            wynik.append(f"{plik.relative_to(KORZEN)}:{i + 1}: `continue-on-error: true` bez powodu obok. "
                         "Dopisz linie `# POWOD (continue-on-error): …` bezposrednio nad flaga albo zdejmij "
                         "flage. Krok, ktorego porazka jest niewidoczna w API, wymaga napisanego powodu.")
    return wynik


def bledy_strukturalne(plik: pathlib.Path) -> list[str]:
    """`id` + `outcome` wypisany do podsumowania — czyli werdykt kroku widoczny bez czytania logu."""
    wynik: list[str] = []
    dok = yaml.safe_load(plik.read_text()) or {}
    akcja = "runs" in dok and "jobs" not in dok
    joby = ({"(akcja zlozona)": dok.get("runs") or {}} if akcja else (dok.get("jobs") or {}))

    for nazwa_joba, job in joby.items():
        kroki = (job or {}).get("steps") or []
        tekst_joba = yaml.safe_dump(job, allow_unicode=True)
        for krok in kroki:
            if not isinstance(krok, dict) or not prawda(krok.get("continue-on-error", False)):
                continue
            gdzie = f"{plik.relative_to(KORZEN)} [{nazwa_joba}] krok {krok.get('name') or krok.get('uses')}"
            if akcja:
                wynik.append(f"{gdzie}: `continue-on-error` na powierzchni bramek jest ZAKAZANE. API nie "
                             "wystawia krokow wewnatrz akcji zlozonej, wiec porazka nie zostawia tam sladu "
                             "poza logiem — a bramka, ktorej porazka nic nie czerwieni, nie jest bramka.")
                continue
            idk = krok.get("id")
            if not idk:
                wynik.append(f"{gdzie}: `continue-on-error: true` bez `id`. Bez identyfikatora nie da sie "
                             "wypisac `outcome` tego kroku, a `conclusion` w API pokaze `success` mimo porazki.")
                continue
            if f"steps.{idk}.outcome" not in tekst_joba or "GITHUB_STEP_SUMMARY" not in tekst_joba:
                wynik.append(f"{gdzie}: `steps.{idk}.outcome` nie jest wypisywany do `$GITHUB_STEP_SUMMARY` "
                             "w tym jobie. Bez tego werdykt kroku jest czytelny WYLACZNIE z logu, a REST API "
                             "raportuje `conclusion: success` mimo `##[error]` (zmierzone).")
    return wynik


def main() -> int:
    pliki = powierzchnie()

    # ZEROWE POKRYCIE TO BLAD, NIE SUKCES. Guard, ktory zbadal 0 plikow, nie stwierdzil, ze jest czysto —
    # stwierdzil, ze nic nie widzial. Bez tego warunku wystarczy przeniesc/przemianowac katalog, zeby
    # dostac zielono „bez naruszen" na drzewie, ktorego nikt nie sprawdzil.
    if not pliki:
        print("::error::continue-on-error: ZERO plikow wykonywalnych do zbadania "
              f"(szukano w {KORZEN}/.github/workflows i .github/actions). Guard, ktory nie zbadal "
              "niczego, nie moze zameldowac, ze jest czysto — to cichy brak pokrycia, nie sukces.")
        return 1

    bledy: list[str] = []
    for plik in pliki:
        bledy += bledy_tekstowe(plik)
        bledy += bledy_strukturalne(plik)

    for b in bledy:
        print(f"::error::{b}")
    # Liczba zbadanych plikow jest CZESCIA werdyktu, nie ozdoba: bez niej „zero naruszen" nie odroznia
    # sie od „zero zbadanych", a to sa dwa przeciwne stany o tym samym kolorze.
    print(f"continue-on-error: {len(pliki)} plikow wykonywalnych sprawdzonych "
          f"({sum(1 for p in pliki if p.suffix == '.yaml')} z rozszerzeniem .yaml), "
          f"{len(bledy)} naruszen")
    return 1 if bledy else 0


if __name__ == "__main__":
    sys.exit(main())
