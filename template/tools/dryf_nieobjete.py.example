#!/usr/bin/env python3
"""Obiekty granicy, których NIE MA w konfiguracji — czyli ta połowa dryfu, której `terraform plan` nie widzi.

DLACZEGO TO ISTNIEJE — i dlaczego samego planu do tego NIE DA SIĘ użyć.

`drift.yml` odpowiada na pytanie „czy chmura zgadza się z Gitem" jednym `terraform plan
-detailed-exitcode`. To jest poprawna odpowiedź dla obiektu, który Terraform ZNA: zmieniony poza
pipeline'em access level wraca w planie jako `1 to change`, skasowany członek jako `1 to add`. Dla
obiektu, którego Terraform NIE ZNA, ta sama komenda odpowiada „No changes" — i to nie jest błąd
Terraforma, tylko konsekwencja dwóch świadomych decyzji z `terraform/`:

  1. `google_access_context_manager_service_perimeter` niesie `ignore_changes` na SZEŚCIU listach
     (`status[0].resources|ingress_policies|egress_policies` i te same w `spec[0]`). Bez tego szkielet
     i zasoby granularne biją się o te same listy przy każdym apply. Skutek uboczny: cokolwiek dopisze
     się do tych list POZA pipeline'em, plan ma polecone ignorować.
  2. Zasoby granularne (członkowie, reguły) i access levele powstają z `for_each` po tym, co zadeklarowane.
     Obiekt spoza deklaracji nie ma swojej instancji w stanie, więc nie ma czego odświeżyć ani z czym
     porównać. Plan go po prostu nie ogląda.

ZMIERZONE NA ŻYWEJ GRANICY (2026-08-13): access level utworzony `gcloud`-iem obok pipeline'u stał
w polityce, a `drift.yml` zameldował `No changes` i pominął krok zgłoszenia — przebieg zielony, wykrywacz
niemy. Ta sama komenda w tym samym repozytorium wykryła natomiast ZMIANĘ access levelu, który był
zadeklarowany. Różnica nie leży w wadze zmiany, tylko w tym, czy obiekt jest w stanie Terraforma.

CO Z TEGO WYNIKA DLA WDROŻENIA. Zmiana wprowadzona ręcznie prawie nigdy nie jest modyfikacją — jest
DOPISANIEM: ktoś dokłada regułę ingress „na chwilę", dokłada projekt do granicy, tworzy access level pod
incydent. Wykrywacz ślepy na dopisanie jest ślepy na najczęstszy kształt obejścia procesu.

CO TO NARZĘDZIE ROBI (DEC-46). Porównuje INWENTARZ: co żyje w API kontra co Terraform planuje utrzymywać.
Kierunek jest JEDEN — raportujemy wyłącznie NADMIAR po stronie chmury:

    żywe − planowane  →  obiekt spoza pipeline'u (nikt tego nie zgłosi, bo plan tego nie widzi)
    planowane − żywe  →  zwykły dryf; `terraform plan` melduje to jako `to add` i to jego robota

CO POROWNUJEMY DOKŁADNIE I DLACZEGO WŁAŚNIE TAK:

  * ACCESS LEVELE — po NAZWACH. Nazwa jest w ACM identyfikatorem trwałym, więc porównanie jest
    jednoznaczne i wskazuje winowajcę z imienia.
  * CZŁONKOWIE — po zasobach (`projects/<numer>`), OSOBNO dla konfiguracji egzekwowanej i dry-run.
    Też jednoznacznie: zasób jest identyfikatorem.
  * REGUŁY — po LICZBIE, osobno dla każdej z czterech par (kierunek × konfiguracja). To jedyne miejsce,
    gdzie schodzimy z nazw na licznik, i jest to ograniczenie API, nie skrót: reguła ingress/egress NIE
    MA w ACM żadnego identyfikatora. Porównanie po treści wymagałoby uruchomienia renderera profili
    i odtworzenia kształtu, jaki wysyła provider — czyli drugiej implementacji tego samego, która
    rozjeżdżałaby się po cichu przy każdej zmianie renderera. Licznik jest słabszy (nie powie KTÓRA
    reguła doszła), ale odpowiada na pytanie, które ma znaczenie operacyjne — „czy ktoś dołożył regułę"
    — i nie kłamie w żadną stronę.

CZEGO ŚWIADOMIE NIE SPRAWDZAMY (żeby zielony wynik nie znaczył więcej, niż znaczy):

  * TREŚCI reguł. Podmiana reguły na inną, bez zmiany liczby, przejdzie tędy niezauważona. Zamknięcie
    tego wymaga renderera — patrz akapit wyżej.
  * INNYCH PERIMETRÓW w tej samej polityce. Perimetr utworzony obok jest niewidoczny dla całej tej
    maszynerii (`drift`, sonda granicy, metryka obserwatora, raport naruszeń pytają o KONKRETNY perimetr
    z konfiguracji). To jest osobna dziura, opisana przy własnej decyzji, i celowo nie łatamy jej tutaj
    przy okazji — sprawdzenie „ile perimetrów ma polityka" należy do innego wsadu niż ten.
  * `restricted_services` i `vpc_accessible_services`. Tych pól `ignore_changes` NIE obejmuje, więc
    zmiana w nich wraca zwykłym planem — i tam ma zostać.

FAIL-CLOSED. Każdy nieczytelny wsad (brak pliku, zły JSON, brak spodziewanego klucza) to kod 1 i głośny
komunikat. Zero różnic wolno zameldować WYŁĄCZNIE wtedy, gdy porównano komplet trzech wsadów — inaczej
ślepota przebrałaby się za spokój, czyli dokładnie ten tryb awarii, który to narzędzie tropi.

Wejście — trzy pliki JSON, żadnych poświadczeń i żadnego ruchu sieciowego (cała chmura jest zaciągana
krok wcześniej w workflow, przez `gcloud` uwierzytelnione tym samym WIF-em, co plan):

    terraform show -json tfplan.binary                                    > plan.json
    gcloud access-context-manager levels list      --policy=… --format=json > levels.json
    gcloud access-context-manager perimeters describe … --format=json      > perimeter.json

Użycie:

    python3 tools/dryf_nieobjete.py --plan-json plan.json \
        --poziomy-json levels.json --perimetr-json perimeter.json

Kody wyjścia: 0 = brak obiektów spoza pipeline'u · 2 = są (ten sam kod, co `plan -detailed-exitcode`,
żeby workflow składał oba werdykty jednym warunkiem) · 1 = nie dało się orzec.
"""
import argparse
import json
import pathlib
import sys

# Typy zasobów Terraforma, z których czytamy INWENTARZ deklaracji. Nazwy są w jednym miejscu, bo ich
# rozjazd z providerem dałby pustą stronę „planowane" — czyli raport, w którym KAŻDY żywy obiekt jest
# nadmiarem. Tak wygląda bramka, która krzyczy zawsze; po tygodniu nikt jej nie czyta.
TYP_POZIOM = "google_access_context_manager_access_level"
TYP_CZLONEK = {
    "enforced": "google_access_context_manager_service_perimeter_resource",
    "dry-run": "google_access_context_manager_service_perimeter_dry_run_resource",
}
TYP_REGULA = {
    ("enforced", "ingress"): "google_access_context_manager_service_perimeter_ingress_policy",
    ("enforced", "egress"): "google_access_context_manager_service_perimeter_egress_policy",
    ("dry-run", "ingress"): "google_access_context_manager_service_perimeter_dry_run_ingress_policy",
    ("dry-run", "egress"): "google_access_context_manager_service_perimeter_dry_run_egress_policy",
}

# Gdzie w opisie żywego perimetru leży która konfiguracja. `status` = egzekwowana, `spec` = dry-run.
KONFIG = {"enforced": "status", "dry-run": "spec"}


class BladWsadu(Exception):
    """Wsadu nie da się odczytać. Zawsze kod 1 — nigdy „przyjmij zero i jedź dalej”."""


def wczytaj(sciezka: str) -> dict:
    p = pathlib.Path(sciezka)
    if not p.is_file():
        raise BladWsadu(f"nie ma pliku {sciezka}")
    try:
        dane = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise BladWsadu(f"{sciezka}: nie jest poprawnym JSON-em ({e})") from e
    if not isinstance(dane, (dict, list)):
        raise BladWsadu(f"{sciezka}: spodziewany obiekt albo lista, jest {type(dane).__name__}")
    return dane


def zasoby_planu(plan: dict) -> list:
    """Instancje zasobów, które Terraform PLANUJE utrzymywać po tym apply.

    Czytamy `planned_values`, a nie `resource_changes`: `planned_values` to stan DOCELOWY, więc obejmuje
    zarówno zasoby bez zmian, jak i te dopiero tworzone. `resource_changes` niesie wyłącznie różnice,
    więc na czystym planie („No changes") byłoby PUSTE — a wtedy każdy żywy obiekt wyszedłby na nadmiar.
    """
    if "planned_values" not in plan:
        raise BladWsadu("plan JSON bez `planned_values` — to nie jest wyjście `terraform show -json`")
    korzen = (plan["planned_values"] or {}).get("root_module") or {}
    zasoby = list(korzen.get("resources") or [])
    for modul in korzen.get("child_modules") or []:
        zasoby.extend(modul.get("resources") or [])
    return zasoby


def poziomy_zywe(dane) -> set:
    """Nazwy access leveli z `levels list --format=json` (lista obiektów z pełnym `name`)."""
    if not isinstance(dane, list):
        raise BladWsadu("poziomy: spodziewana LISTA z `levels list --format=json`")
    nazwy = set()
    for lvl in dane:
        nazwa = (lvl or {}).get("name")
        if not nazwa:
            raise BladWsadu(f"poziomy: wpis bez pola `name`: {lvl!r}")
        nazwy.add(nazwa)
    return nazwy


def poziomy_planowane(zasoby: list) -> set:
    nazwy = set()
    for z in zasoby:
        if z.get("type") == TYP_POZIOM:
            nazwa = (z.get("values") or {}).get("name")
            if not nazwa:
                raise BladWsadu(f"plan: access level bez `values.name`: {z.get('address')}")
            nazwy.add(nazwa)
    return nazwy


def konfiguracja_zywa(perimetr: dict, etap: str) -> dict:
    """`status` albo `spec` żywego perimetru. BRAK sekcji to pusta konfiguracja, nie błąd —
    perimetr bez ani jednego członka egzekwowanego jest poprawnym stanem dnia pierwszego."""
    if not isinstance(perimetr, dict) or "name" not in perimetr:
        raise BladWsadu("perimetr: spodziewany obiekt z `perimeters describe --format=json`")
    return (perimetr.get(KONFIG[etap]) or {})


def raport(plan_json: str, poziomy_json: str, perimetr_json: str) -> tuple[int, list]:
    """(liczba obiektów spoza pipeline'u, wiersze raportu)."""
    zasoby = zasoby_planu(wczytaj(plan_json))
    zywe_poziomy = poziomy_zywe(wczytaj(poziomy_json))
    perimetr = wczytaj(perimetr_json)

    wiersze, ile = [], 0

    # --- access levele: po nazwach ---------------------------------------------------------------
    nadmiar = sorted(zywe_poziomy - poziomy_planowane(zasoby))
    ile += len(nadmiar)
    for nazwa in nadmiar:
        wiersze.append(f"access level spoza pipeline'u: {nazwa}")

    for etap in ("enforced", "dry-run"):
        konfig = konfiguracja_zywa(perimetr, etap)

        # --- członkowie: po zasobach -------------------------------------------------------------
        zywi = set(konfig.get("resources") or [])
        planowani = {
            (z.get("values") or {}).get("resource")
            for z in zasoby if z.get("type") == TYP_CZLONEK[etap]
        } - {None}
        nadmiar = sorted(zywi - planowani)
        ile += len(nadmiar)
        for zasob in nadmiar:
            wiersze.append(f"czlonek spoza pipeline'u ({etap}): {zasob}")

        # --- reguły: po liczbie ------------------------------------------------------------------
        for kierunek, pole in (("ingress", "ingressPolicies"), ("egress", "egressPolicies")):
            zywych = len(konfig.get(pole) or [])
            planowanych = sum(1 for z in zasoby if z.get("type") == TYP_REGULA[(etap, kierunek)])
            if zywych > planowanych:
                ile += zywych - planowanych
                wiersze.append(
                    f"regul {kierunek} ({etap}) na granicy WIECEJ niz w konfiguracji: "
                    f"{zywych} kontra {planowanych} — roznica {zywych - planowanych}")

    return ile, wiersze


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan-json", required=True, help="wyjscie `terraform show -json <plan>`")
    ap.add_argument("--poziomy-json", required=True, help="wyjscie `levels list --format=json`")
    ap.add_argument("--perimetr-json", required=True, help="wyjscie `perimeters describe --format=json`")
    args = ap.parse_args()

    try:
        ile, wiersze = raport(args.plan_json, args.poziomy_json, args.perimetr_json)
    except BladWsadu as e:
        # Kod 1, nie 0 i nie 2: „nie wiem" nie jest ani spokojem, ani alarmem. Workflow ma paść.
        print(f"NIE DA SIE ORZEC: {e}", file=sys.stderr)
        return 1

    if not ile:
        print("Brak obiektow spoza pipeline'u: inwentarz granicy zgadza sie z konfiguracja.")
        return 0

    print(f"OBIEKTY SPOZA PIPELINE'U: {ile}")
    print()
    for w in wiersze:
        print(f"  * {w}")
    print()
    print("Te obiekty ISTNIEJA na granicy, a konfiguracja o nich nie wie — wiec `terraform plan` ich NIE")
    print("widzi i nie zobaczy (ignore_changes na listach szkieletu + for_each po deklaracji).")
    print("Zanim cokolwiek skasujesz: sprawdz w audit-logu KTO i KIEDY je dodal.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
