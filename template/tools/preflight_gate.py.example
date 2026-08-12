#!/usr/bin/env python3
"""Bramka pre-flightu: uruchamia `tools/preflight_check.sh` dla członków WCHODZĄCYCH do perimetru.

DLACZEGO TEN PLIK W OGÓLE ISTNIEJE. `preflight_check.sh` był przez cały czas narzędziem bez wyzwalacza —
`grep -rn preflight_check .github tools` dawało ZERO trafień w czymkolwiek wykonywalnym, a cztery miejsca
w materiale opisywały go jako bramkę egzekwowaną. Narzędzie poprawiano dwukrotnie (pięć defektów, potem
cichy no-op przy >1 zasobie w konfiguracji) — czyli poprawiano skrypt, którego nikt nie uruchamiał. Sam
skrypt nie mógł się o to upomnieć: umie orzec o JEDNYM projekcie, a nie wie, KTÓRY projekt dziś wchodzi.
Ten plik odpowiada wyłącznie na to drugie pytanie i to jest cała jego treść.

KOGO SPRAWDZAMY — I DLACZEGO NIE DIFFA GITA (to jest najważniejsza decyzja w tym pliku)

    zadeklarowani w perimeter/projects.yaml        ⟶  KTO MA BYĆ członkiem
    `spec.resources` ∪ `status.resources` (API)    ⟶  KTO JUŻ JEST w granicy
    różnica                                        ⟶  KTO WCHODZI, czyli kogo pyta pre-flight

Trzy niezależne powody, każdy zmierzony albo rozstrzygnięty wcześniej w tym repozytorium:

  1. DIFF ZNIKA RAZEM ZE ZDARZENIEM. `workflow_dispatch`, `gh run rerun` i apply po nieudanym apply nie
     mają żadnego diffa, a stosują dokładnie tę samą treść — bramka na diffie byłaby nieobecna w tych
     trzech przebiegach, czyli tam, gdzie człowiek patrzy najmniej. Ten sam argument stoi za bramką
     promocji (DEC-17) i jest tam rozpisany szerzej.
  2. DIFF ZABLOKOWAŁBY WŁASNE LEKARSTWO. Pull request USUWAJĄCY martwego członka (projekt skasowany,
     `DELETE_REQUESTED`) dotyka jego wpisu — więc bramka na diffie uruchomiłaby pre-flight na projekcie,
     którego już nie ma, dostała `BŁĄD` i zatrzymała jedyną zmianę, która ten stan naprawia. Rozstrzygnięte
     wcześniej: pre-flight NIE MOŻE stać się bramką na istnienie członków już obecnych.
  3. TO SAMO NA OBU TORACH, BEZ ANI JEDNEGO `if`. Porównanie ze światem daje identyczny zbiór na pull
     requeście i na ścieżce mutatora, więc jedna definicja bramki wystarcza (DEC-16).

CZEGO TA BRAMKA ŚWIADOMIE NIE PILNUJE. Zmiany wpisu członka JUŻ OBECNEGO w granicy (np. dołożenie
tożsamości do parametru profilu). Kształtu adresu pilnuje `perimeter.rego` na każdym pull requeście,
a istnienie konta i tak weryfikuje ACM przy apply — odrzuca CAŁĄ zmianę komunikatem
`invalid or non-existent`, czyli głośno i na nietkniętej granicy (`git revert` cofa treść, bo apply
w ogóle nie doszedł do skutku). Kosztem jest nieudany apply po review; ceną alternatywy byłby diff
z punktów 1–3 albo pytanie API o KAŻDEGO członka przy każdym przebiegu.

KOSZT PRZY SKALI. Zbiór wchodzących jest przy ustabilizowanym perimetrze PUSTY, więc bramka kosztuje
wtedy DOKŁADNIE JEDEN odczyt ACM na przebieg — niezależnie od tego, czy członków jest pięciu, czy pięciuset.
Ten jeden odczyt (`perimeters list`) jest jednocześnie odczytem, którego potrzebuje check kolizji
perimetrów w samym skrypcie, więc przekazujemy go dalej plikiem (`--lista-perimetrow`) zamiast płacić
za niego N razy. Limit tempa ACM to 500 odczytów/min i jest to najciaśniejsza kwota w tym stosie —
przy partii 50 wniosków różnica jest między 1 a 51 odczytami.
"""
import argparse
import os
import pathlib
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("brakuje pyyaml: pip install pyyaml")

import projects_file

# Format odczytu jest TAKI SAM, jakiego używa check kolizji perimetrów w `preflight_check.sh` — bo to jest
# dokładnie ten sam odczyt, wykonany raz zamiast N razy. Separator wypisany jawnie: `list()` bez argumentu
# skleja elementy PRZECINKIEM, a parser rozcinający po średniku trafiał wtedy wyłącznie przy konfiguracji
# z DOKŁADNIE JEDNYM zasobem (zmierzone; atrapa testowa miała wszędzie jeden zasób, czyli jedyny układ,
# w którym defekt się nie ujawnia).
FORMAT = "value(name,status.resources.list(separator=';'),spec.resources.list(separator=';'))"


def czytaj_liste_perimetrow(polityka: str) -> str:
    """Surowe wyjście `perimeters list` — tekst, nie struktura, bo w tej postaci jedzie dalej do skryptu.

    `--policy` JEST PODANY JAWNIE i to nie jest ozdoba. Bez niego gcloud zgaduje politykę z organizacji
    projektu z konfiguracji — działa na laptopie z ustawionym projektem, a w CI zależy od zmiennej,
    której ten kod nie kontroluje. Bramka, która działa u autora i nie działa u mutatora, jest gorsza
    od jej braku, bo dowód „u mnie zielone" jest wtedy prawdziwy i bezwartościowy.
    """
    p = subprocess.run(
        ["gcloud", "access-context-manager", "perimeters", "list",
         f"--policy={polityka}", f"--format={FORMAT}"],
        capture_output=True, text=True)
    if p.returncode != 0:
        # FAIL-CLOSED, i to jest najostrzejszy punkt tego pliku. „Nie wiem, kto wchodzi" NIE JEST tym samym
        # co „nikt nie wchodzi": pierwsze znaczy, że bramka nie wykonała swojej jedynej pracy. Przepuszczenie
        # przebiegu w tym stanie dałoby dokładnie tę własność, którą ten plik naprawia — kontrolę obecną
        # w drzewie i celującą w pustkę.
        sys.exit(f"::error::nie odczytalem listy perimetrow z polityki {polityka} "
                 f"(rc={p.returncode}) — bramka pre-flightu NIE WIE, kto wchodzi do granicy, "
                 f"wiec nie przepuszcza tego przebiegu: {p.stderr.strip()[:400]}")
    return p.stdout


def numery_w_granicy(lista: str, perimetr: str) -> tuple:
    """(numery projektów już obecnych w NASZYM perimetrze, czy perimetr w ogóle jest na liście).

    Union `status` ∪ `spec` świadomie: członek w dry-run siedzi w `spec`, egzekwowany w `status`, a nas
    interesuje jedno pytanie — czy on JUŻ TAM JEST. Rozdzielanie tych dwóch zbiorów należy do bramki
    promocji (DEC-17), która pyta o coś innego: o moment rozpoczęcia egzekwowania.
    """
    obecne = set()
    znaleziony = False
    for wiersz in lista.splitlines():
        if not wiersz.strip():
            continue
        pola = wiersz.split("\t")
        # Krótka nazwa (`ai_core`) albo pełna (`accessPolicies/…/servicePerimeters/ai_core`) — API
        # odpowiada dziś krótką, ale porównanie po ostatnim segmencie jest odporne na jedno i drugie.
        if pola[0].split("/")[-1] != perimetr:
            continue
        znaleziony = True
        for kolumna in pola[1:3]:
            for zasob in kolumna.split(";"):
                zasob = zasob.strip()
                if zasob:
                    obecne.add(zasob.split("/")[-1])
    return obecne, znaleziony


def wchodzacy(czlonkowie: dict, obecne: set) -> dict:
    """Mapa klucz członka → (project_id, project_number) dla tych, których w granicy jeszcze nie ma."""
    return {k: (m["project_id"], str(m["project_number"]))
            for k, m in sorted(czlonkowie.items())
            if str(m.get("project_number")) not in obecne}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="perimeter/policy.yaml")
    ap.add_argument("--root", default=".", help="korzen repozytorium (dla perimeter/projects.yaml)")
    ap.add_argument("--skrypt", default="tools/preflight_check.sh")
    ap.add_argument("--perimetry-z-pliku",
                    help="surowe wyjscie `perimeters list` zamiast wywolania gcloud (testy)")
    ap.add_argument("--tylko-wypisz", action="store_true",
                    help="wypisz zbior wchodzacych i zakoncz — bez ani jednego wywolania pre-flightu")
    args = ap.parse_args()

    polityka = yaml.safe_load(pathlib.Path(args.policy).read_text())
    nazwa = polityka["perimeter"]["name"]
    czlonkowie = projects_file.mapa(projects_file.wczytaj(args.root)["members"])

    if args.perimetry_z_pliku:
        lista = pathlib.Path(args.perimetry_z_pliku).read_text()
    else:
        lista = czytaj_liste_perimetrow(str(polityka["organization"]["access_policy_name"]))

    obecne, znaleziony = numery_w_granicy(lista, nazwa)
    linie = []
    if not znaleziony:
        # Pierwszy apply na świeżej organizacji: perimetru jeszcze nie ma, bo tworzy go ten sam przebieg.
        # Wtedy WSZYSCY zadeklarowani są wchodzący i tak ma być — ale mówimy to wprost, bo ten sam objaw
        # daje literówka w `perimeter.name`, a wtedy bramka pytałaby API o każdego członka po kolei.
        linie.append(f"perimetr `{nazwa}` nie wystepuje w tej polityce — wszyscy zadeklarowani czlonkowie "
                     f"sa WCHODZACY (pierwszy apply? literowka w perimeter.name?)")

    kandydaci = wchodzacy(czlonkowie, obecne)
    linie.append(f"bramka pre-flightu: zadeklarowanych {len(czlonkowie)}, "
                 f"juz w granicy {len(obecne)}, WCHODZACYCH {len(kandydaci)}")

    if not kandydaci:
        # Zielone „nic do zrobienia" jest tu WERDYKTEM, nie ciszą: przy ustabilizowanym perimetrze to
        # normalny wynik każdego przebiegu i musi być widoczny, żeby dało się odróżnić bramkę, która nie
        # miała czego sprawdzać, od bramki, która się nie uruchomiła.
        linie.append("nikt nie wchodzi do granicy w tym przebiegu — pre-flight nie ma czego pytac")
    else:
        linie += [f"  {k}  {pid}  {num}" for k, (pid, num) in kandydaci.items()]

    raport(linie)
    if args.tylko_wypisz or not kandydaci:
        return 0

    # Lista perimetrów jedzie do skryptu PLIKIEM: ten sam odczyt obsługuje wtedy i wybór kandydatów,
    # i check kolizji w każdym z nich. Plik, nie zmienna środowiskowa — wyjście `perimeters list` jest
    # wielolinijkowe i zawiera taby, a przepisywanie go przez środowisko to kolejne miejsce na zgubienie
    # kolumny (dokładnie ten defekt kosztował już raz cichy no-op tego checku).
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as f:
        f.write(lista)
        plik_listy = f.name

    bledy = []
    try:
        for k, (pid, num) in kandydaci.items():
            print(f"\n--- pre-flight: {k} ({pid}, {num}) ---", flush=True)
            p = subprocess.run(
                ["bash", args.skrypt, "--project", pid, "--number", num,
                 "--lista-perimetrow", plik_listy],
                capture_output=True, text=True)
            print(p.stdout, end="")
            print(p.stderr, end="", file=sys.stderr)
            if p.returncode != 0:
                bledy.append(k)
    finally:
        os.unlink(plik_listy)

    if bledy:
        raport([f"::error::pre-flight NIEZALICZONY dla: {', '.join(bledy)}. "
                f"Prerekwizyty naprawia WLASCICIEL PROJEKTU (Private Google Access na podsieciach, "
                f"prywatna strefa DNS na restricted VIP) — repozytorium perimetru cudzej sieci nie "
                f"provisionuje (DEC-5). Po naprawie uruchom ten przebieg ponownie."])
        return 1
    raport([f"pre-flight zaliczony dla wszystkich wchodzacych ({len(kandydaci)})"])
    return 0


def raport(linie: list) -> None:
    """Log przebiegu i podsumowanie dostają TO SAMO — kto patrzy na kolor kropki, ma tam zobaczyć powód."""
    for l in linie:
        print(l)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("### bramka pre-flightu\n```\n" + "\n".join(linie) + "\n```\n")


if __name__ == "__main__":
    raise SystemExit(main())
