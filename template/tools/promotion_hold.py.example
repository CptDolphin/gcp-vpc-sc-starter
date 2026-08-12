#!/usr/bin/env python3
"""Wstrzymuje apply, który zacząłby EGZEKWOWAĆ granicę wobec kogoś, kogo dziś nie egzekwuje.

DLACZEGO AKURAT TA ZMIANA MA BRAMKĘ, SKORO CAŁA RESZTA REPOZYTORIUM JEDZIE AUTOMATEM. Bo jest jedyną,
której skutkiem jest ODMOWA RUCHU, i jedyną, w której cofnięcie konfiguracji nie równa się cofnięciu
skutku. Zmierzone przy rollbacku pierwszej promocji: **46 s do zakończenia `apply`, ale 78 s do powrotu
ruchu** — konfiguracja wraca natychmiast, skutek propaguje się ~20 s dłużej i w tym oknie realni
wywołujący dostają odmowę. Nowy członek w dry-run, reguła ingress, access level ani budżet atrybutów nie
odbierają nikomu dostępu; promocja tak — na podstawie diffa, który w review wygląda na jednowyrazową
kosmetykę (`stage: dry-run` → `stage: enforced`).

CO DOKŁADNIE JEST PORÓWNYWANE — I DLACZEGO NIE DIFF GITA. Bramka pyta o świat, nie o zdarzenie:

    zadeklarowani jako `enforced` w perimeter/projects.yaml   ⟶  KTO MA BYĆ egzekwowany
    `status.resources` żywego perimetru (API)                 ⟶  KTO JEST egzekwowany
    różnica                                                    ⟶  KOGO ten apply zacznie egzekwować

Diff dwóch commitów (`before..after` przy push, `base..head` przy pull requeście) opisuje ZDARZENIE i
znika razem z nim: `workflow_dispatch`, ponowienie przebiegu (`gh run rerun`) i apply po nieudanym apply
nie mają żadnego diffa, a stosują dokładnie tę samą treść. Bramka zbudowana na diffie byłaby więc
nieobecna dokładnie w tych trzech przebiegach, w których człowiek najmniej patrzy na to, co się dzieje.
Porównanie deklaracji ze stanem świata nie ma tej luki — jest prawdziwe przy każdym wyzwalaczu, także
gdy ktoś rozbije promocję na dwa commity albo wypchnie ją prosto na gałąź domyślną.

To jest przy tym nadal wykrycie „PO TREŚCI DEKLARACJI", a nie po nazwie gałęzi ani po etykiecie pull
requesta: nazwa i etykieta są pod kontrolą autora zmiany, a `stage:` w pliku członka jest tą treścią,
która realnie decyduje o kształcie konfiguracji egzekwowanej.

BRAMKA JEST ASYMETRYCZNA I TO JEST DECYZJA, NIE NIEDOPATRZENIE. Zatrzymujemy WYŁĄCZNIE ruch w stronę
`enforced`. Zdjęcie egzekwowania (`enforced` → `dry-run`, offboarding, break-glass) przechodzi automatem,
bo PRZYWRACA ruch — bramka na tej drodze wydłużałaby każdą awarię o czas szukania człowieka. Z tego samego
powodu rewert promocji nie potrzebuje niczyjej zgody: `git revert` + push i apply jedzie sam.

CO ZWALNIA BRAMKĘ. Wyłącznie ręczne uruchomienie `apply.yml` (`workflow_dispatch`) z listą kluczy
członków w polu `promocje` — i lista musi być RÓWNA zbiorowi oczekujących promocji, nie jego podzbiorem
ani nadzbiorem. „Zatwierdzam wszystko" nie jest wyrażalne: człowiek wpisuje, KOGO odcina. Gdy między
spojrzeniem na repo a uruchomieniem ktoś dołoży drugą promocję, zbiory przestają być równe i bramka staje
ponownie — zamiast przepuścić przy okazji coś, czego zatwierdzający nie widział.

CZEGO TA BRAMKA NIE ROBI. Nie jest rozdziałem obowiązków: na planie GitHuba bez wymaganych recenzentów dla
repozytoriów prywatnych (`403 Upgrade to GitHub Pro…` na ochronie gałęzi i na regułach ochrony environment)
ta sama tożsamość może scalić pull requesta i uruchomić apply. Daje co innego i nazywa to wprost: DRUGI,
ŚWIADOMY AKT w innym momencie, wymagający wypisania z nazwiska, kto od tej chwili będzie odrzucany.
Rozdział tożsamości dokłada się do tego bramką environment tam, gdzie plan ją ma — obie warstwy się składają.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("brakuje pyyaml: pip install pyyaml")

import projects_file

# Klucz członka: `<dywizja>-<project_id>`. Rozdzielamy przecinkami LUB białymi znakami, bo pole formularza
# GitHuba dostaje to, co człowiek wpisze, a nie to, co przewidział autor pola.
ROZDZIELACZ = re.compile(r"[\s,;]+")


def numery_egzekwowane(perimetr: dict) -> set:
    """Numery projektów w konfiguracji EGZEKWOWANEJ (`status.resources`).

    Pusty `status` (albo jego brak) znaczy „nikt nie jest egzekwowany" i jest stanem NORMALNYM — tak
    wygląda perimetr, w którym wszyscy członkowie siedzą w dry-run. Nie mylić z brakiem odpowiedzi API:
    tamto obsługuje `czytaj_perimetr`, i tamto jest błędem.
    """
    zasoby = ((perimetr or {}).get("status") or {}).get("resources") or []
    return {z.split("/")[-1] for z in zasoby if z}


def czytaj_perimetr(nazwa: str, polityka: str) -> dict:
    """Żywy perimetr z API. NIEISTNIEJĄCY PERIMETR = pusta konfiguracja egzekwowana, nie awaria.

    Rozróżnienie jest istotne w dokładnie jednym momencie — przy pierwszym apply na świeżej organizacji,
    kiedy perimetru jeszcze nie ma, bo tworzy go ten sam przebieg. Gdyby brak obiektu był błędem, bramka
    zatrzymywałaby bootstrap idący dokumentowaną ścieżką (wszyscy członkowie w `dry-run`), czyli psułaby
    wdrożenie w imię ochrony przed czymś, co się w nim nie dzieje.

    KAŻDY INNY BŁĄD JEST BŁĘDEM i przerywa apply. „Nie wiem, kto jest egzekwowany" nie może znaczyć
    „pewnie nikt" — to jest ta sama pomyłka, co czytanie pustego wyniku zapytania jako czystego okna.
    """
    p = subprocess.run(
        ["gcloud", "access-context-manager", "perimeters", "describe", nazwa,
         f"--policy={polityka}", "--format=json"],
        capture_output=True, text=True)
    if p.returncode == 0:
        return json.loads(p.stdout or "{}")
    if "NOT_FOUND" in p.stderr or "does not exist" in p.stderr:
        print(f"perimetr {nazwa} nie istnieje jeszcze w polityce {polityka} — "
              f"konfiguracja egzekwowana jest pusta (pierwszy apply)")
        return {}
    sys.exit(f"gcloud access-context-manager perimeters describe {nazwa} zwrocilo {p.returncode}: "
             f"{p.stderr.strip()[:400]}")


def oczekujace_promocje(czlonkowie: dict, egzekwowani: set) -> dict:
    """Członkowie zadeklarowani jako `enforced`, których żywa granica jeszcze nie egzekwuje.

    Zwraca mapę klucz → numer projektu. Kierunek jest jednostronny świadomie (patrz nagłówek modułu):
    członek zadeklarowany jako `dry-run`, a obecny w konfiguracji egzekwowanej, to ZDJĘCIE ochrony —
    przywraca ruch, więc nie jest tu widziany.
    """
    return {k: str(m.get("project_number"))
            for k, m in sorted(czlonkowie.items())
            if m.get("stage") == "enforced" and str(m.get("project_number")) not in egzekwowani}


def rozbij(zatwierdzone: str) -> set:
    return {c for c in ROZDZIELACZ.split(zatwierdzone or "") if c}


def werdykt(oczekujace: dict, zatwierdzone: set, zdarzenie: str, kto: str) -> tuple:
    """(kod_wyjscia, linie_raportu). Cała logika bramki w jednej czystej funkcji — bez API i bez plików,
    żeby selftest mógł ją przepytać na zbiorach, zamiast wnioskować z obecności słów w workflowie."""
    linie = []

    # ZATWIERDZENIE MA JEDNO LEGALNE ŹRÓDŁO: ręczne uruchomienie. Wpisane na stałe w workflow albo
    # doklejone do wyzwalacza `push` byłoby zgodą, której nikt nie wyraża w momencie skutku — czyli
    # bramką zdejmowaną jednym commitem, i to takim, który w diffie wygląda na konfigurację.
    if zatwierdzone and zdarzenie and zdarzenie != "workflow_dispatch":
        linie.append(f"::error::zatwierdzenie promocji przyszlo ze zdarzenia `{zdarzenie}`, a jedynym "
                     f"legalnym zrodlem jest RECZNE uruchomienie apply (`workflow_dispatch`). "
                     f"Zatwierdzenie wpisane na stale w workflow nie jest zgoda wyrazona w momencie skutku.")
        return 1, linie

    if not oczekujace:
        linie.append("bramka promocji: ten apply nie zaczyna egzekwowac granicy wobec nikogo nowego")
        if zatwierdzone:
            # Zatwierdzenie bez promocji = człowiek pracuje na nieaktualnym obrazie repozytorium (albo ktoś
            # zdążył zastosować tę promocję wcześniej). Przepuszczenie tego byłoby cichym „nieważne, co
            # wpisałeś" — a to jest dokładnie ten nawyk, przez który treść pola przestaje mieć znaczenie.
            linie.append(f"::error::pole `promocje` wskazuje {sorted(zatwierdzone)}, ale ten przebieg nie "
                         f"promuje NIKOGO. Zatwierdzenie opisuje inny stan repozytorium niz stosowany — "
                         f"odswiez i uruchom ponownie (albo uruchom bez wypelniania pola).")
            return 1, linie
        return 0, linie

    linie.append(f"bramka promocji: ten apply ZACZALBY EGZEKWOWAC granice wobec {len(oczekujace)} "
                 f"czlonka/ow, ktorzy dzis sa w dry-run:")
    linie += [f"  - {k}  (projects/{n})" for k, n in oczekujace.items()]

    if zatwierdzone == set(oczekujace):
        linie.append(f"ZATWIERDZONE recznie przez `{kto}` — dokladnie ten zbior, ktory zostanie "
                     f"zaczety egzekwowac. Apply idzie dalej.")
        return 0, linie

    brakuje = sorted(set(oczekujace) - zatwierdzone)
    nadmiar = sorted(zatwierdzone - set(oczekujace))
    if brakuje:
        linie.append(f"::error::bez zatwierdzenia dla: {brakuje}. Od momentu apply wywolania chronionych "
                     f"uslug w tych projektach SPOZA granicy beda ODRZUCANE. Cofniecie konfiguracji nie "
                     f"jest natychmiastowym cofnieciem skutku (zmierzone: 46 s do apply, 78 s do powrotu ruchu).")
    if nadmiar:
        linie.append(f"::error::zatwierdzenie wskazuje {nadmiar}, a ten przebieg ich NIE promuje — "
                     f"zbior zatwierdzony musi byc ROWNY oczekujacym, nie podzbiorem ani nadzbiorem.")
    linie.append("APPLY NIE ZOSTAL WYKONANY — granica jest nietknieta, stan Terraforma nie byl nawet "
                 "zablokowany. Sa dwie drogi dalej i obie sa swiadome:")
    linie.append(f"  * promuj:  gh workflow run apply.yml -f promocje=\"{' '.join(sorted(oczekujace))}\"")
    linie.append("  * cofnij:  git revert <commit promocji> && git push  — zdjecie promocji NIE jest "
                 "bramkowane, apply pojedzie automatem")
    return 1, linie


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="perimeter/policy.yaml")
    ap.add_argument("--root", default=".", help="korzen repozytorium (dla perimeter/projects.yaml)")
    ap.add_argument("--zatwierdzone", default="", help="klucze czlonkow z pola `promocje` (workflow_dispatch)")
    ap.add_argument("--zdarzenie", default="", help="github.event_name — zatwierdzenie liczy sie tylko z workflow_dispatch")
    ap.add_argument("--kto", default="?", help="github.triggering_actor — do raportu")
    ap.add_argument("--perimetr-z-pliku", help="JSON perimetru zamiast wywolania gcloud (testy)")
    args = ap.parse_args()

    polityka = yaml.safe_load(pathlib.Path(args.policy).read_text())
    czlonkowie = projects_file.mapa(projects_file.wczytaj(args.root)["members"])

    if args.perimetr_z_pliku:
        perimetr = json.loads(pathlib.Path(args.perimetr_z_pliku).read_text() or "{}")
    else:
        perimetr = czytaj_perimetr(polityka["perimeter"]["name"],
                                   str(polityka["organization"]["access_policy_name"]))

    kod, linie = werdykt(oczekujace_promocje(czlonkowie, numery_egzekwowane(perimetr)),
                         rozbij(args.zatwierdzone), args.zdarzenie, args.kto)
    for l in linie:
        print(l)
    # Podsumowanie przebiegu dostaje TO SAMO, co log: kto czyta zieloną/czerwoną kropkę, ma tam zobaczyć
    # listę odcinanych projektów, a nie musieć wchodzić w kroki.
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("### bramka promocji\n```\n" + "\n".join(linie) + "\n```\n")
    return kod


if __name__ == "__main__":
    raise SystemExit(main())
