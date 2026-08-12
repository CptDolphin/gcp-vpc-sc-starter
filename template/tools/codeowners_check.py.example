#!/usr/bin/env python3
"""Czy CODEOWNERS opisuje ROZDZIELENIE, na ktorym stoi zgoda Security — i czy nie klamie o nim.

DLACZEGO TO ISTNIEJE. Bramka `vpcsc.onboarding` odrzuca czlonka z profilem `risk: high` bez wpisu
w `perimeter/policy.yaml` §egress_approvals (DEC-23). Cala wartosc tego ukladu siedzi w jednym zdaniu:
`policy.yaml` ma INNYCH wlascicieli niz `perimeter/projects.yaml`, wiec zgody nie wystawia sobie ten sam
zespol, ktory sklada wniosek. To zdanie jest dzis prawda i nikt jej z niczym nie konfrontuje — a jest to
JEDNA LINIA w pliku tekstowym, ktora „porzadkujacy" pull request potrafi zrownac w dobrej wierze.

Rownanie wlascicieli nie wyglada w diffie na osłabienie kontroli. Wyglada na uporzadkowanie listy.

CZEGO TEN SKRYPT NIE UDAJE. Nie jest kontrola dostepu i nie zastepuje ochrony galezi. Na repozytorium
prywatnym w darmowym planie `branches/main/protection` i `rulesets` odpowiadaja `403 Upgrade to GitHub
Pro`, wiec `require_code_owner_reviews` nie ma gdzie zadzialac i CODEOWNERS nie jest egzekwowany PRZEZ NIC.
Wlasnie dlatego zgoda Security jest egzekwowana regula OPA (na obu torach: pull request i apply), a nie
approvalem w GitHubie. Ten skrypt pilnuje, zeby PLIK OPISUJACY INTENCJE nie zaczal opisywac czegos innego,
niz robi mechanizm — bo rozjazd miedzy tym, co plik obiecuje, a tym, co dziala, jest dokladnie defektem,
ktory zamyka DEC-23.

DWA POZIOMY USTALEN, I ROZNICA MIEDZY NIMI JEST CELOWA:

  BLAD (kod 1)   — rozjazd, ktory znosi wlasnosc bezpieczenstwa: plik ze zgodami ma dokladnie tych samych
                   wlascicieli co plik z wnioskami, albo ktorys z plikow niosacych decyzje stracil wlasna
                   regule i spadl na domyslna `*`.
  NIEDOKONCZONE  — nazwy zespolow sa nadal placeholderami z szablonu (`@your-org/...`). W organizacji
                   GitHuba to zwykla robota wdrozeniowa; na koncie prywatnym zespoly NIE ISTNIEJA i nie da
                   sie ich utworzyc, wiec twardy blad byloby bramka, ktora w swoim wlasnym srodowisku
                   testowym musi byc trwale wylaczona. Taka bramka nie jest ostroznoscia, tylko wylacznikiem
                   z dobra opinia. Ustalenie jest za to wypisywane PRZY KAZDYM PRZEBIEGU, nazwane wprost
                   i nigdy nie milczy.

OGRANICZENIE DOPASOWANIA, swiadome i wypisane, zeby zielony wynik nie znaczyl wiecej, niz znaczy:
rozumiemy podzbior skladni CODEOWNERS, ktorego uzywa ten szablon — `*`, `/sciezka/pliku`, `/katalog/`.
Wygrywa OSTATNIA pasujaca regula, tak jak u GitHuba. Wzorce z `?`, `[]` i `**` nie sa obslugiwane i sa
zglaszane jako nierozpoznane, zamiast po cichu nie pasowac do niczego.

    python3 tools/codeowners_check.py
"""
import argparse
import fnmatch
import pathlib
import re
import sys

# Placeholder nazwy zespolu z nierozpakowanego szablonu. Ta sama klasa ustalenia co `<MONITORING_PROJECT>`
# w `control_plane_check.py`, inne pole — i dlatego ten sam sposob raportowania.
PLACEHOLDER_ZESPOL = re.compile(r"^@(your-org|YOUR-ORG|<[A-Z0-9_]+>)/")

# Pliki, ktorych wlasnosc jest WEJSCIEM mechanizmu, a nie preferencja. Kazdy z nich musi miec WLASNA regule
# — spadniecie na domyslna `*` znaczy, ze plik przestal byc wymieniony, a taki diff wyglada jak sprzatanie.
NIOSA_DECYZJE = (
    "perimeter/policy.yaml",  # baseline + zgody Security (egress_approvals)
    "perimeter/profiles/bq-omni-external-read.yaml",  # katalog profili — szablon reguly dla wszystkich
    "policy/onboarding.rego",  # sama bramka; kto to edytuje, znosi kazda inna linie tego pliku
)

# Para, ktorej rozdzielenie jest cala wartoscia ukladu: wniosek kontra zgoda na wniosek.
PLIK_ZGOD = "perimeter/policy.yaml"
PLIK_WNIOSKOW = "perimeter/projects.yaml"


def reguly(tekst: str) -> list[tuple[str, list[str], int]]:
    """(wzorzec, wlasciciele, numer linii) — w kolejnosci z pliku, bez komentarzy i pustych linii."""
    out = []
    for nr, linia in enumerate(tekst.splitlines(), 1):
        bez = linia.split("#", 1)[0].strip()
        if not bez:
            continue
        czesci = bez.split()
        out.append((czesci[0], czesci[1:], nr))
    return out


def wlasciciele(regs: list[tuple[str, list[str], int]], sciezka: str) -> tuple[set[str], str | None, int]:
    """Wlasciciele sciezki wg OSTATNIEJ pasujacej reguly — tak jak rozstrzyga GitHub.

    Zwracamy takze sam wzorzec i numer linii, bo komunikat bledu bez wskazania linii zamienia bramke
    w zagadke: autor pull requesta widzi „rozjazd wlasnosci" i nie wie, ktora z kilkunastu linii poprawic.
    """
    trafiony, wzorzec, nr = set(), None, 0
    for wz, owns, linia in regs:
        if dopasowanie(wz, sciezka):
            trafiony, wzorzec, nr = set(owns), wz, linia
    return trafiony, wzorzec, nr


def dopasowanie(wzorzec: str, sciezka: str) -> bool:
    if wzorzec == "*":
        return True
    goly = wzorzec.lstrip("/")
    if wzorzec.endswith("/"):  # katalog: pasuje wszystko pod nim
        return sciezka.startswith(goly)
    return sciezka == goly or fnmatch.fnmatch(sciezka, goly)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codeowners", default=".github/CODEOWNERS")
    args = ap.parse_args()

    p = pathlib.Path(args.codeowners)
    if not p.exists():
        # Brak pliku nie jest „brakiem konfiguracji" — na GitHub Enterprise znaczy, ze KAZDY moze
        # zatwierdzic wszystko. Fail-closed, tak jak przy braku `policy.yaml` w bramkach tresci.
        print(f"::error::{args.codeowners} nie istnieje — na wdrozeniu z ochrona galezi znaczy to, "
              f"ze zadna sciezka nie ma wymaganego recenzenta")
        return 1

    regs = reguly(p.read_text())
    problemy, niedokonczone, zrobione = [], [], []

    nierozpoznane = [f"{wz} (linia {nr})" for wz, _, nr in regs if re.search(r"[?\[\]]|\*\*", wz)]
    for n in nierozpoznane:
        problemy.append(
            f"wzorzec {n} uzywa skladni, ktorej ten guard NIE rozumie — nie potrafie policzyc wlascicieli, "
            f"wiec nie moge twierdzic, ze rozdzielenie stoi. Uprosc wzorzec albo rozszerz `dopasowanie()`")

    # --- 1. KAZDY PLIK NIOSACY DECYZJE MA WLASNA REGULE -------------------------------------------
    for sciezka in NIOSA_DECYZJE:
        owns, wzorzec, nr = wlasciciele(regs, sciezka)
        if wzorzec is None:
            problemy.append(f"{sciezka}: zadna regula nie pasuje — nawet domyslna `*` zniknela")
        elif wzorzec == "*":
            problemy.append(
                f"{sciezka}: pasuje wylacznie domyslna regula `*` (linia {nr}) — plik niosacy decyzje "
                f"stracil wlasna linie, a taki diff wyglada jak sprzatanie listy")
        elif not owns:
            problemy.append(f"{sciezka}: regula `{wzorzec}` (linia {nr}) nie wymienia ANI JEDNEGO wlasciciela")
        else:
            zrobione.append(f"{sciezka} ma wlasna regule `{wzorzec}` (linia {nr}): {' '.join(sorted(owns))}")

    # --- 2. ZGODA NIE MOZE BYC WYSTAWIANA PRZEZ TEGO, KOGO DOTYCZY --------------------------------
    # To jest jedyna asercja tego skryptu, ktora broni wlasnosci BEZPIECZENSTWA, a nie higieny pliku.
    # Sprawdzamy RELACJE ZBIOROW, a nie konkretne nazwy: dziala tak samo na placeholderach szablonu,
    # na realnych zespolach organizacji i po kazdym przemianowaniu — czyli przezyje to, co zwykle zabija
    # guardy pisane na nazwy.
    zgody, wz_zgod, nr_zgod = wlasciciele(regs, PLIK_ZGOD)
    wnioski, wz_wnioskow, nr_wnioskow = wlasciciele(regs, PLIK_WNIOSKOW)
    nadwyzka = zgody - wnioski
    if not zgody or not wnioski:
        problemy.append(
            f"nie umiem porownac wlascicieli {PLIK_ZGOD} i {PLIK_WNIOSKOW} — ktorys zbior jest pusty "
            f"(patrz bledy wyzej)")
    elif not nadwyzka:
        problemy.append(
            f"ROZDZIELENIE ZNIESIONE: {PLIK_ZGOD} (linia {nr_zgod}, wzorzec `{wz_zgod}`) nie ma ANI JEDNEGO "
            f"wlasciciela poza wlascicielami {PLIK_WNIOSKOW} (linia {nr_wnioskow}, wzorzec `{wz_wnioskow}`). "
            f"Zgoda na wyprowadzanie danych poza Google Cloud (§egress_approvals) trafia wtedy do pliku "
            f"zatwierdzanego przez ten sam zespol, ktory sklada wniosek — czyli do zgody wystawianej samemu "
            f"sobie. Przywroc osobnego wlasciciela pliku ze zgodami (DEC-23)")
    else:
        zrobione.append(
            f"rozdzielenie stoi: {PLIK_ZGOD} ma wlascicieli spoza {PLIK_WNIOSKOW}: {' '.join(sorted(nadwyzka))}")

    # --- 3. PLACEHOLDERY: nazwane, nigdy przemilczane ---------------------------------------------
    pod_placeholderem = sorted({
        w for _, owns, _ in regs for w in owns if PLACEHOLDER_ZESPOL.match(w)
    })
    if pod_placeholderem:
        niedokonczone.append(
            f"nazwy zespolow sa nadal placeholderami szablonu ({', '.join(pod_placeholderem)}) — te zespoly "
            f"NIE ISTNIEJA, wiec na wdrozeniu z ochrona galezi zaden z tych wpisow nie wskaze realnego "
            f"recenzenta. Podmien je przy wdrozeniu w organizacji; na koncie prywatnym zespolow nie da sie "
            f"utworzyc i to jest znany, zapisany brak — kontrola zgody Security NIE stoi na tym pliku, "
            f"tylko na regule OPA (DEC-23)")

    for z in zrobione:
        print(f"  OK            {z}")
    for z in niedokonczone:
        print(f"  NIEDOKONCZONE {z}")
    for z in problemy:
        print(f"  BLAD          {z}")
    if problemy:
        sys.stdout.flush()
        print(f"\nNIEZALICZONE ({len(problemy)}): CODEOWNERS przestal opisywac rozdzielenie, na ktorym stoi "
              f"zgoda Security.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
