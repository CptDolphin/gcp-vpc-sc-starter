#!/usr/bin/env python3
"""Obserwator granicy: mierzy, czy maszyneria perimetru zylaby, i publikuje to jako metryki.

DLACZEGO TO ISTNIEJE. Audit-logi Google odpowiadaja na pytanie „co sie stalo NA granicy". Nie odpowiadaja
na pytanie „czy nasz wlasny pipeline jeszcze dziala" — a to ono psuje sie po cichu. `apply`, ktory padl,
nie zostawia sladu nigdzie poza lista przebiegow w GitHubie; `apply`, ktory sie NIE ODPALIL, nie zostawia
nawet tego. Ten skrypt zamienia cztery takie ciche stany w cztery liczby, ktore da sie odpytac i o ktore
da sie oprzec alert.

CO MIERZY (kazda liczba = jeden objaw z `docs/7-alerty.md`):
  apply_pending_seconds   wiek zmergowanej, a niezastosowanej zmiany granicy. 0 = Git zgodny z chmura.
  attribute_budget_percent  zuzycie limitu 6000 atrybutow — OSOBNO dla `spec` i `status`.
  attribute_budget_days_to_limit  (limit - uzyte) / nachylenie z 30 dni. Sentynela 3650 = nie prognozuje.
  drift_resources         ile zasobow `terraform plan` chce zmienic przy NIETKNIETYM repozytorium.
  members_expired         ile wpisow ma `review_by` w przeszlosci.
  violations_enforced     ile odmow EGZEKWOWANYCH w oknie — jedyna liczba mowiaca „ktos jest blokowany TERAZ”.
  violations_dry_run      ile naruszen dry-run w oknie (zapowiedz problemu po promocji, nie problem).
  config_changed_outside_pipeline  ile zmian ACM tozsamoscia INNA niz konto apply.
  network_inserts_enforced  ile sieci VPC powstalo w czlonkach EGZEKWOWANYCH — kontekst, BEZ alertu.
  network_window_workload   do ilu z nich wstawiono maszyne, ZANIM siec zdazyla dojrzec (DEC-32).
  members_not_active      ilu czlonkow granicy NIE MA potwierdzonego stanu ACTIVE (DEC-42). Etykieta
                          `state` rozdziela `not_active` (odczytany stan inny niz ACTIVE) od `unreadable`
                          (stanu NIE ODCZYTANO) — druga wartosc NIGDY nie chowa sie pod „ACTIVE".

LICZBY OPISUJACE GRANICE (naruszenia, zmiany ACM, okno swiezej sieci) JADA WIDOKIEM SINKA, NIE METRYKA
LOG-BASED, I NIE JEST TO ROZSZERZENIE ZAKRESU, TYLKO NAPRAWA (#2000). Stały wczesniej na
metrykach log-based, ktore mialy ZERO serii przy realnych zdarzeniach: metryka log-based liczy wylacznie
wpisy PRZYJETE przez Log Router swojego projektu, a te wpisy powstaja w projekcie czlonka albo w logu
organizacji i docieraja do nas SINKIEM, czyli do magazynu — nie na wejscie. Uzasadnienie z para kontrolna
stoi w `terraform/monitoring.tf`; tutaj wystarczy wiedziec, ze zrodlem jest WIDOK SINKA, nie audit-log.

DWA TRYBY, DWIE TOZSAMOSCI — I TO JEST KONSTRUKCJA, NIE WYGODA. `measure` czyta i liczy; uruchamia go
konto `plan`, ktore jest read-only i ktore moze impersonowac KAZDY pull request. `publish` pisze do Cloud
Monitoring; uruchamia go osobne konto `watch`, ktorego jedynym uprawnieniem jest `timeSeries.create`.
Gdyby liczyl i pisal jeden proces, konto dostepne z pull requesta zyskaloby prawo zapisu — czyli autor
dowolnego PR-a moglby wpisac „budzet 5%" i uciszyc alert. Podzial kosztuje jeden dodatkowy job.

Uzycie:
    python3 tools/perimeter_watch.py measure --repo OWNER/REPO --plan-json terraform/plan.json > metryki.json
    python3 tools/perimeter_watch.py publish --input metryki.json --project PROJEKT
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# DRUGI EGZEMPLARZ TEJ LISTY JEST W `terraform/alerts.tf` (konsument). Rozjazd = alert patrzacy na metryke,
# ktorej nikt nie pisze, czyli cisza nie do odroznienia od spokoju. Selftest porownuje oba pliki.
METRYKI = {
    "apply_pending": "custom.googleapis.com/vpcsc/apply_pending_seconds",
    "budzet_procent": "custom.googleapis.com/vpcsc/attribute_budget_percent",
    "budzet_dni": "custom.googleapis.com/vpcsc/attribute_budget_days_to_limit",
    "dryf": "custom.googleapis.com/vpcsc/drift_resources",
    "wygasli": "custom.googleapis.com/vpcsc/members_expired",
    # Trzy ponizsze opisuja to, co dzieje sie NA granicy, a nie w naszym pipelinie — i stoja tutaj
    # dlatego, ze metryka log-based ich policzyc NIE MOZE (#2000, uzasadnienie w `terraform/monitoring.tf`).
    "naruszenia_enforced": "custom.googleapis.com/vpcsc/violations_enforced",
    "naruszenia_dry_run": "custom.googleapis.com/vpcsc/violations_dry_run",
    "zmiany_poza_pipelinem": "custom.googleapis.com/vpcsc/config_changed_outside_pipeline",
    # DWIE PONIZSZE OPISUJA OKNO, W KTORYM GRANICA NIE CHRONI I NIE ZOSTAWIA SLADU (DEC-32).
    # `sieci_egzekwowane` jest KONTEKSTEM i NIE MA polityki alertu — utworzenie sieci w projekcie
    # czlonkowskim jest czynnoscia legalna i czesta, wiec alert na nia sam jest szumem, a szum sie wycisza.
    # Alert stoi na `sieci_z_obciazeniem`: sieci, do ktorej wstawiono maszyne, ZANIM zdazyla dojrzec.
    "sieci_egzekwowane": "custom.googleapis.com/vpcsc/network_inserts_enforced",
    "sieci_z_obciazeniem": "custom.googleapis.com/vpcsc/network_window_workload",
    # CZLONEK, KTOREGO PROJEKT PRZESTAL ISTNIEC (DEC-42). Jedna metryka, DWIE serie po etykiecie `state`,
    # bo „stanu nie odczytano" jest osobnym zdaniem o swiecie niz „stan jest inny niz ACTIVE" — i tylko
    # drugie jest werdyktem. Zlanie ich w jedna liczbe zamienialoby slepote w rozpoznanie.
    "czlonkowie_nieaktywni": "custom.googleapis.com/vpcsc/members_not_active",
}

# Typ zasobu Asset Inventory, ktory niesie stan cyklu zycia projektu. JEDNO wywolanie na cala organizacje.
ASSET_TYP_PROJEKT = "cloudresourcemanager.googleapis.com/Project"

# Jedyny stan, ktory znaczy „ten czlonek zyje". Werdykt budujemy na TRESCI pola `state`, nie na kodzie
# bledu — `projects describe` odpowiada tym samym komunikatem na „nie ma projektu" i „brak dostepu",
# wiec licznik oparty na kodzie wyjscia myli slepote z rozpoznaniem.
STAN_ZYWY = "ACTIVE"

# Zdarzenia sterujace Compute, z ktorych sklada sie okno. Wszystkie sa Admin Activity — zawsze wlaczone
# i niekonfigurowalne, wiec nie da sie ich wylaczyc po stronie projektu czlonkowskiego.
COMPUTE_SIEC = "v1.compute.networks.insert"
COMPUTE_MASZYNA = "v1.compute.instances.insert"
# TRZECI strumien, i jedyne zrodlo mapy podsiec->siec (DEC-44). Bez niego dopasowanie maszyny do sieci
# custom-mode NIE MA z czego powstac: wpis maszyny niesie wylacznie `subnetwork` (patrz `sieci_maszyny`),
# a z samej referencji podsieci nie da sie odczytac, do ktorej sieci ona nalezy.
COMPUTE_PODSIEC = "v1.compute.subnetworks.insert"

# Domyslne okno dojrzewania sieci. Gorna OBSERWACJA z pomiaru to 5 m 18 s (3 przeloty: 5 m 18 s / 3 m 53 s
# / 4 m 41 s, rozrzut 85 s), a propagacja jest NIEDETERMINISTYCZNA i migocze — DEC-32 bierze wiec zapas
# do 10 minut i tego samego progu uzywa procedura („twórz siec przed obciazeniem, zostaw na >= 10 min").
# Detektor MUSI uzywac tej samej liczby co procedura: mniejsza oskarzalaby o zlamanie zasady kogos, kto ja
# stosowal, a wieksza zglaszalaby jako incydent zachowanie zgodne z runbookiem.
OKNO_DOJRZEWANIA_S = 600

# Metody ACM, ktore ZMIENIAJA granice. Odczyty (`Get*`, `List*`) sa szumem: konto planu czyta granice przy
# kazdym pull requescie, wiec bez tego wykluczenia metryka „ktos zmienil granice” rosla by przy kazdym PR-ze.
ACM_ZMIANA = ("ServicePerimeter", "AccessLevel", "AccessPolicy")
ACM_ODCZYT = ("Get", "List")

# Sentynela „nie da sie prognozowac". SWIADOMIE po BEZPIECZNEJ stronie (10 lat, nie 0): prognoza policzona
# z trzech punktow pomiarowych swiezego wdrozenia bylaby szumem, a alert na szumie uczy ignorowania alertow.
BRAK_PROGNOZY_DNI = 3650.0

# Minimum historii, ponizej ktorego nie liczymy nachylenia. 7 punktow rozlozonych na >= 7 dni: pojedynczy
# wniosek dywizji podnosi zuzycie skokowo, wiec regresja z dwoch dni opisywalaby ten skok jako trend.
MIN_PUNKTOW_HISTORII = 7
MIN_ROZPIETOSC_DNI = 7.0


# --- czyste funkcje (testowalne bez sieci) -----------------------------------------------------------

def wiek_niezastosowanej_zmiany(sekundy_od_wejscia_na_glowna: int | None) -> int:
    """0, gdy nie ma czego stosowac; inaczej wiek najstarszej niezastosowanej zmiany.

    Wydzielone tak, zeby caly warunek dal sie przetestowac bez gita: wejsciem jest juz LICZBA sekund,
    a nie repozytorium.
    """
    if sekundy_od_wejscia_na_glowna is None:
        return 0
    return max(0, int(sekundy_od_wejscia_na_glowna))


def nachylenie_na_dobe(historia: list[tuple[float, float]]) -> float | None:
    """Nachylenie regresji liniowej [jednostka/dobe]. None, gdy historia za krotka albo zdegenerowana.

    Regresja, a nie „ostatni minus pierwszy": roznica koncow bierze za trend pojedynczy wniosek dywizji,
    ktory wszedl wczoraj, i ignoruje ksztalt reszty okna. Przy +50 projektach na miesiac to jest roznica
    miedzy „30 dni do sciany" a „300".
    """
    if len(historia) < MIN_PUNKTOW_HISTORII:
        return None
    czasy = [t for t, _ in historia]
    rozpietosc_dni = (max(czasy) - min(czasy)) / 86400.0
    if rozpietosc_dni < MIN_ROZPIETOSC_DNI:
        return None

    n = len(historia)
    sx = sum(t for t, _ in historia)
    sy = sum(v for _, v in historia)
    sxx = sum(t * t for t, _ in historia)
    sxy = sum(t * v for t, v in historia)
    mianownik = n * sxx - sx * sx
    if mianownik == 0:
        return None
    return ((n * sxy - sx * sy) / mianownik) * 86400.0


def dni_do_sciany(historia: list[tuple[float, float]], biezacy_procent: float) -> float:
    """Ile dni do 100% budzetu przy dzisiejszym tempie. `BRAK_PROGNOZY_DNI`, gdy nie rosnie albo brak danych.

    Liczymy na PROCENTACH, nie na surowej liczbie atrybutow, i to jest celowe: limit bywa zmieniany
    (`policy.yaml -> attribute_budget.limit_per_config`), a wtedy historia w atrybutach opisuje inny sufit
    niz dzis. Procent jest niezmienniczy wzgledem tej zmiany.
    """
    nachylenie = nachylenie_na_dobe(historia)
    if nachylenie is None or nachylenie <= 1e-9:
        return BRAK_PROGNOZY_DNI
    zostalo = max(0.0, 100.0 - biezacy_procent)
    return min(BRAK_PROGNOZY_DNI, zostalo / nachylenie)


def koszt_operacji_api(operacje: list | None) -> int:
    """Usluga + kazdy selektor metody — ten sam model co `attribute_budget.py`, tylko na obiekcie z API.

    Parytet obu modeli jest tu warunkiem uzytecznosci, nie estetyki: rozjazd w samej ARYTMETYCE
    wygladalby tak samo jak rozjazd Gita z chmura, wiec ostrzezenie o rozjezdzie przestaloby cokolwiek
    znaczyc. `methodSelectors` po stronie API niesie i `method`, i `permission` — tak samo jak
    `methods` + `permissions` po stronie YAML.
    """
    return sum(1 + len(o.get("methodSelectors") or []) for o in (operacje or []))


def koszt_konfiguracji(cfg: dict) -> int:
    """Atrybuty ZUZYTE PRZEZ JEDNA KONFIGURACJE perimetru, policzone z obiektu zwroconego przez API.

    DLACZEGO Z API, A NIE Z DEKLARACJI — to jest sedno tej metryki. `tools/attribute_budget.py` liczy
    z plikow YAML i modeluje renderer; jest to WLASCIWE narzedzie na pull requescie, bo odpowiada na
    pytanie „czy ZMIANA, ktora proponuje, sie zmiesci" — a zmiany w chmurze jeszcze nie ma. Jest za to
    STRUKTURALNIE SLEPE na wszystko, co jest w granicy, a czego nie ma w deklaracji: zdublowane reguly
    po nieudanym odzysku stanu, reczne dopiski w konsoli, dryf. Alert zbudowany na tej liczbie milczalby
    dokladnie w tym scenariuszu, w ktorym sufit zostaje przekroczony bez niczyjej wiedzy — czyli
    w jedynym, ktory boli. Alert mierzy wiec GRANICE, a bramka na PR-ze mierzy WNIOSEK; to sa dwa rozne
    pytania i dlatego maja dwa rozne zrodla.

    Ten sam wybor rozstrzyga wymiar predykcyjny: nachylenie liczone z deklaracji pokazywaloby tempo
    NASZYCH pull requestow, a nie tempo rosniecia granicy.

    CO LICZYMY: wylacznie atrybuty w regulach ingress/egress. `resources` (czlonkostwo),
    `restrictedServices` i `vpcAccessibleServices` maja WLASNE, osobne limity — doliczanie ich mieszaloby
    dwie pule kwotowe (regul: 6000 na konfiguracje; zasobow chronionych: 40 000 na polityke).
    """
    razem = 0
    for r in (cfg.get("ingressPolicies") or []):
        zrodlo = r.get("ingressFrom") or {}
        cel = r.get("ingressTo") or {}
        razem += (len(zrodlo.get("identities") or [])
                  + len(zrodlo.get("sources") or [])
                  + len(cel.get("resources") or [])
                  + koszt_operacji_api(cel.get("operations")))
    for r in (cfg.get("egressPolicies") or []):
        zrodlo = r.get("egressFrom") or {}
        cel = r.get("egressTo") or {}
        razem += (len(zrodlo.get("identities") or [])
                  + len(zrodlo.get("sources") or [])
                  + len(cel.get("resources") or [])
                  # `externalResources` (BigQuery Omni) API trzyma osobnym polem, ale konsumuja budzet
                  # dokladnie tak samo jak `resources`.
                  + len(cel.get("externalResources") or [])
                  + koszt_operacji_api(cel.get("operations")))
    return razem


def procenty_budzetu(perimetr: dict, limit: int) -> dict:
    """{'spec': %, 'status': %} — OSOBNO, bo limit 6000 jest NA KONFIGURACJE, nie laczny.

    Nazwy pol sa jezykiem API (`spec` = dry-run, `status` = egzekwowana), a nie jezykiem etapow czlonka
    (`dry_run`/`enforced`) uzywanym przez bramke na PR-ze. Alert i runbook mowia jezykiem API, bo operator
    patrzy na `perimeters describe`, a nie na nasz raport.
    """
    return {
        nazwa: round(100.0 * koszt_konfiguracji(perimetr.get(nazwa) or {}) / limit, 3)
        for nazwa in ("spec", "status")
    }


def dryf_z_planu(plan: dict, apply_zalega: bool) -> int:
    """Ile zasobow plan chce zmienic. 0, gdy w Gicie czeka niezastosowana zmiana.

    TO JEST DYSKRYMINATOR „ZMIANA SPOZA GITA vs OPOZNIENIE PROPAGACJI" PO STRONIE PRODUCENTA. Gdy apply
    zalega, niepusty plan jest OCZEKIWANY — to jest dokladnie ta zmiana, ktora czeka, i mowi o niej alert
    `apply`. Publikowanie jej tutaj jako dryfu dawaloby dwa alerty na jeden fakt i uczyloby, ze „dryf
    zdarza sie normalnie". Drugi, niezalezny mechanizm jest po stronie konsumenta: alert wymaga, zeby
    roznica UTRZYMALA sie przez `drift_persist_seconds` (domyslnie godzine przy zmierzonej propagacji
    skutku ~20 s).
    """
    if apply_zalega:
        return 0
    zmiany = 0
    for zasob in plan.get("resource_changes", []) or []:
        akcje = zasob.get("change", {}).get("actions", [])
        if akcje and akcje != ["no-op"] and akcje != ["read"]:
            zmiany += 1
    return zmiany


def komunikat_rozjazdu(nazwa: str, zywe: int, zadeklarowane: int, apply_zalega: bool,
                       powod_zalegania: str) -> str | None:
    """Tresc adnotacji o rozjezdzie zywej granicy z deklaracja. `None`, gdy liczby rowne.

    TEN SAM DYSKRYMINATOR CO `dryf_z_planu`, TYLKO PO STRONIE KOMUNIKATU — i to jest jedyny powod, dla
    ktorego ta funkcja istnieje osobno, zamiast byc f-stringiem w `zmierz`.

    Rozjazd tych dwoch liczb ma DWIE zupelnie rozne przyczyny i dwie rozne procedury, a jedno zdanie dla
    obu wysyla dyzurnego pod zly adres w tym z nich, ktory jest czestszy:

      * `apply` ZALEGA — w Gicie jest zmergowana zmiana, ktorej nie ma jeszcze w chmurze. Roznica jest
        wtedy OCZEKIWANA i znika sama po udanym apply. Wysylanie tu do alertu o dryfie jest gorsze niz
        cisza, bo ten alert MILCZY Z DEFINICJI: `dryf_z_planu` zwraca w tym stanie 0 celowo (patrz jego
        docstring), a alert o wieku `apply` ma prog `apply_pending_seconds` (godzina) — czyli przez cala
        pierwsza godzine rozjazd budzetu jest JEDYNYM sygnalem, a odsylacz prowadzi do dwoch kontroli
        pokazujacych czysta tablice. Dyzurny, ktory raz je sprawdzi i nic nie znajdzie, nauczy sie tej
        adnotacji nie czytac.
      * `apply` NIE ZALEGA — Git i chmura powinny byc zgodne, a nie sa. To jest objaw realny i ma dwa
        zrodla, oba warte obudzenia czlowieka: zmiana wprowadzona poza pipelinem albo rozjazd ARYTMETYKI
        obu modeli (`attribute_budget.py` modeluje renderer; gdy renderer sie zmieni, a model nie —
        ostrzezenie wyglada identycznie jak dryf). Tu odeslanie do alertu o dryfie jest trafne.

    ZMIERZONE, DLACZEGO TO NIE JEST HIPOTETYCZNE (2026-08-12, przebiegi `watch` 31565377821 i 31565606010):
    „granica ma 48 atrybutow, deklaracja opisuje 53 — patrz alert o dryfie", przy `drift_resources = 0`
    i `apply_pending_seconds = 72`. Przyczyna byla prawdziwa i dokladnie z pierwszej kategorii: `apply`
    poprzedniego commita padl na numerze projektu, ktory nie istnieje, wiec czlonek warty 5 atrybutow byl
    w deklaracji i nie byl w granicy. Kontrola zadzialala, jej zdanie nie.

    OBA WARIANTY IDA JAKO `::warning::`, A ROZROZNIENIE NIESIE PIERWSZE SLOWO TRESCI — i to nie jest
    kosmetyka, tylko odmowa oparcia kontroli na niezmierzonym zachowaniu platformy. Kuszace bylo dac
    drugiemu wariantowi `::error::`, zeby odcinal sie na LISCIE przebiegow. Adnotacja poziomu error
    prawdopodobnie nie zmienia statusu joba (status robi kod wyjscia), ale „prawdopodobnie" jest tu za
    slabe: gdyby jednak zmieniala, `measure` staje sie czerwony, `publish` nie rusza przez `needs`,
    metryki nie powstaja — czyli obserwator MILKNIE dokladnie w tym stanie, w ktorym ma krzyczec, i to
    bez ani jednego alertu przez pierwsze trzy godziny (`watchdog_absent_seconds`). W calym tym
    repozytorium kazde `::error::` stoi obok niezerowego `exit`, wiec nie ma tu ani jednego pomiaru,
    na ktorym mozna by sie oprzec. Ryzyko asymetryczne i darmowe do usuniecia: prefiks „ROZJAZD
    OCZEKIWANY" / „ROZJAZD NIEOCZEKIWANY" daje to samo rozroznienie na liscie, bo GitHub pokazuje tam
    tresc adnotacji, a nie sam poziom.
    """
    if zywe == zadeklarowane:
        return None
    roznica = zywe - zadeklarowane
    wspolne = (f"granica ma {zywe} atrybutow, deklaracja opisuje {zadeklarowane} (roznica {roznica:+d})")
    if apply_zalega:
        return (
            f"budzet {nazwa}: ROZJAZD OCZEKIWANY — {wspolne}; apply ZALEGA ({powod_zalegania}), wiec ta "
            f"roznica zniknie po udanym apply. To NIE jest dryf: `drift_resources` jest w tym przebiegu "
            f"celowo 0, a alert o dryfie milczy. Sprawdzaj HISTORIE PRZEBIEGOW APPLY, nie granice; jesli "
            f"zaleganie przekroczy `apply_pending_seconds`, odezwie sie alert `apply`.")
    return (
        f"budzet {nazwa}: ROZJAZD NIEOCZEKIWANY — {wspolne}, a apply NIE zalega ({powod_zalegania}). Git "
        f"i chmura powinny byc zgodne. Albo ktos zmienil granice poza pipelinem (patrz alert o dryfie), albo "
        f"model w `attribute_budget.py` przelicza koszt inaczej, niz renderuje sie na ACM. Rozstrzyga "
        f"porownanie REGULA PO REGULE, nie samych sum: docs/7-alerty.md#rozjazd-granicy-z-deklaracja")


def wygasli_czlonkowie(projects_doc: dict, dzis: datetime.date) -> int:
    """Ile wpisow ma `review_by` w przeszlosci. Ta sama arytmetyka co `expiry-sweep.yml`.

    Roznica wobec sweepera jest zamierzona: sweeper CHODZI RAZ W MIESIACU i otwiera pull requesta, wiec
    jego cisza znaczy albo „nikt nie wygasl", albo „sweeper przestal chodzic". Ta liczba mierzy STAN,
    wiec rozroznia te dwa przypadki.
    """
    ile = 0
    for m in projects_doc.get("members", []) or []:
        if datetime.date.fromisoformat(str(m["review_by"])) < dzis:
            ile += 1
    return ile


def stany_projektow(wyniki: list[dict]) -> dict[str, str]:
    """{numer projektu -> stan cyklu zycia} z odpowiedzi `searchAllResources`.

    Kluczem jest NUMER, bo numerem operuje granica (`spec.resources` / `status.resources`). Asset
    Inventory podaje go w polu `project` (`projects/<numer>`), a ID w `additionalAttributes.projectId` —
    indeksujemy po obu, zeby ta sama mapa obslugiwala odczyt z deklaracji, gdzie wystepuja oba.

    Wpis BEZ pola `state` jest pomijany, a nie liczony jako zywy: brak pola znaczy „nie wiem", a
    `czlonkowie_bez_potwierdzenia` zamieni ten brak na `unreadable`. To jest ta sama zasada, ktora
    w tym pliku dotyczy kazdej metryki — zero publikujemy tylko wtedy, gdy JEST czym.
    """
    mapa: dict[str, str] = {}
    for w in wyniki or []:
        stan = str(w.get("state") or "")
        if not stan:
            continue
        numer = str(w.get("project") or "").rsplit("/", 1)[-1]
        if numer:
            mapa[numer] = stan
        pid = str((w.get("additionalAttributes") or {}).get("projectId") or "")
        if pid:
            mapa[pid] = stan
    return mapa


def czlonkowie_bez_potwierdzenia(perimetr: dict, stany: dict[str, str]) -> dict:
    """Czlonkowie granicy, o ktorych NIE POTWIERDZONO, ze ich projekt jest ACTIVE (DEC-42).

    ZRODLEM JEST ZYWA GRANICA, NIE DEKLARACJA — `spec.resources` + `status.resources`. Powod jest ten sam,
    dla ktorego `projekty_egzekwowane` czyta `status`: falszywy dowod „czystego okna" produkuje to, co
    REALNIE stoi w granicy, a nie to, co ktos zadeklarowal. Numer dopisany do granicy z reki tez ma
    projekt, ktory moze zniknac, a wpis w Gicie bez apply nie jest jeszcze niczyim czlonkostwem.

    TRZY WORKI, BO SA TRZY ROZNE ZDANIA:
      * `nieaktywni`  — stan ODCZYTANY i inny niz ACTIVE (`DELETE_REQUESTED`, `DELETE_IN_PROGRESS`).
        To jest werdykt: ktos kasuje projekt, ktory nadal jest w granicy;
      * `nieodczytani` — stanu NIE MA w odpowiedzi. Projekt skasowany twardo (po 30 dniach ID znika
        z indeksu), opoznienie indeksowania, zawezony zakres, odebrane uprawnienie — nie rozrozniamy
        tych przyczyn i NIE UDAJEMY, ze rozrozniamy. Jedno jest pewne: to NIE JEST potwierdzenie, ze
        czlonek zyje, wiec nie wolno tego policzyc jako OK;
      * `pominiete`   — zasoby, ktore nie sa projektem (siec VPC: `//compute…/networks/<nazwa>`). Maja
        wlasny cykl zycia i nie ma ich w tym indeksie; raportujemy je, zamiast po cichu zmniejszac
        mianownik.

    RAPORT CZESCIOWY > BRAK RAPORTU: jeden czlonek bez stanu nie wywraca calego przelotu — laduje
    w `nieodczytani`, reszta jest policzona. Ale nie ma sciezki, ktora zamiata go pod „ACTIVE".
    """
    numery: list[str] = []
    pominiete: list[str] = []
    for konfiguracja in ("spec", "status"):
        for zasob in ((perimetr.get(konfiguracja) or {}).get("resources") or []):
            ref = str(zasob)
            ogon = ref.rsplit("/", 1)[-1]
            if ref.startswith("projects/") and ogon.isdigit():
                if ogon not in numery:
                    numery.append(ogon)
            elif ref not in pominiete:
                pominiete.append(ref)

    nieaktywni, nieodczytani = [], []
    for numer in numery:
        stan = stany.get(numer)
        if stan is None:
            nieodczytani.append(numer)
        elif stan != STAN_ZYWY:
            nieaktywni.append({"numer": numer, "stan": stan})
    return {
        "czlonkowie": numery,
        "nieaktywni": nieaktywni,
        "nieodczytani": nieodczytani,
        "pominiete": sorted(pominiete),
    }


def policz_naruszenia(wpisy: list[dict]) -> dict:
    """Dzieli wpisy o naruszeniu VPC-SC na EGZEKWOWANE i DRY-RUN.

    PULAPKA, KTORA JUZ RAZ KOSZTOWALA NAS BRAMKE (#1941, powtorzona w #2000). Odmowa EGZEKWOWANA
    NIE MA pola `dryRun` — ono istnieje WYLACZNIE przy naruszeniu dry-run i ma wtedy wartosc `true`.
    Rozroznienie musi wiec isc po OBECNOSCI pola, nie po jego wartosci: predykat `dryRun == "false"`
    (albo `.get("dryRun") == False`) nie dopasuje NIGDY NICZEGO, w zadnej organizacji, i zostawi
    metryke „ktos jest blokowany TERAZ” pusta dokladnie wtedy, gdy ma rosnac.

    Wartosc bywa bool `True` albo string `"true"` zaleznie od tego, czy wpis przyszedl przez
    `entries.list` (JSON) czy przez `gcloud --format=json` — dlatego porownujemy po znormalizowanym
    napisie, a nie po typie.
    """
    licznik = {"enforced": 0, "dry_run": 0}
    for w in wpisy:
        meta = (w.get("protoPayload") or {}).get("metadata") or {}
        if "dryRun" not in meta:
            licznik["enforced"] += 1
        elif str(meta["dryRun"]).lower() == "true":
            licznik["dry_run"] += 1
        else:
            # Ksztalt nieznany: pole JEST, ale nie jest `true`. Google takiego wpisu dzis nie produkuje.
            # Liczymy go jako EGZEKWOWANY — fail-closed: falszywy alarm jest tanszy niz przeoczona odmowa.
            licznik["enforced"] += 1
    return licznik


def policz_zmiany_konfiguracji(wpisy: list[dict], konto_apply: str) -> int:
    """Ile razy granice zmienila tozsamosc INNA niz konto apply pipeline'u.

    Odtwarza semantyke filtra, ktory stal wczesniej w metryce log-based — z jedna roznica: konto apply
    wyklucza sie TUTAJ, a nie w filtrze widoku. Widok jest struktura i nie ma sie zmieniac przy rotacji
    konta serwisowego; tozsamosc jest wartoscia srodowiska i nalezy do konsumenta.
    """
    ile = 0
    for w in wpisy:
        pp = w.get("protoPayload") or {}
        metoda = pp.get("methodName") or ""
        if not any(z in metoda for z in ACM_ZMIANA):
            continue
        if any(o in metoda for o in ACM_ODCZYT):
            continue
        kto = ((pp.get("authenticationInfo") or {}).get("principalEmail") or "")
        if konto_apply and kto == konto_apply:
            continue
        ile += 1
    return ile


def _epoch(znacznik: str | None) -> float | None:
    """`2026-08-12T18:38:16.5Z` -> epoch. None, gdy pola nie ma albo ma nieznany ksztalt."""
    if not znacznik:
        return None
    try:
        return datetime.datetime.fromisoformat(str(znacznik).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def projekt_wpisu(wpis: dict) -> str:
    """ID projektu, w ktorym powstalo zdarzenie. Dwa zrodla, bo zadne nie jest gwarantowane osobno.

    `resource.labels.project_id` jest normalna droga. `logName` (`projects/<ID>/logs/...`) jest zapasem —
    kazdy wpis go ma, bo to on decyduje, gdzie wpis lezy. Zwracamy ID, nie numer: wpis audytowy Compute
    numeru projektu nie niesie, a `status.resources` perimetru operuje numerami — przeklada je
    `projekty_egzekwowane`, korzystajac z deklaracji jako SLOWNIKA numer->ID.
    """
    pid = ((wpis.get("resource") or {}).get("labels") or {}).get("project_id")
    if pid:
        return str(pid)
    nazwa = str(wpis.get("logName") or "")
    if nazwa.startswith("projects/"):
        return nazwa.split("/")[1]
    return ""


def projekty_egzekwowane(perimetr: dict, projects_doc: dict) -> tuple[set[str], list[str]]:
    """({ID projektow w konfiguracji EGZEKWOWANEJ}, [numery, ktorych nie da sie przelozyc]).

    ZRODLEM PRAWDY JEST ZYWA GRANICA (`status.resources`), a nie `stage` w deklaracji — z tego samego
    powodu, dla ktorego budzet liczy sie z API: deklaracja opisuje INTENCJE, a okno bez ochrony otwiera
    sie w tym, co jest w granicy NAPRAWDE. Czlonek, ktorego apply jeszcze nie wniosl do `status`, nie ma
    okna; czlonek dopisany do granicy z reki — ma, i wlasnie jego alert musi zobaczyc.

    Deklaracja wystepuje tu WYLACZNIE jako slownik numer->ID. Numer bez wpisu w deklaracji jest sam
    w sobie objawem (ktos jest w granicy, a nie ma go w Gicie) — ma juz swoj alert (dryf, rozjazd budzetu),
    wiec tutaj tylko go RAPORTUJEMY, zamiast po cichu pomijac albo udawac, ze go rozpoznajemy.
    """
    numery = set()
    for zasob in ((perimetr.get("status") or {}).get("resources") or []):
        numer = str(zasob).split("/")[-1]
        if numer:
            numery.add(numer)
    slownik = {str(m.get("project_number")): str(m.get("project_id"))
               for m in (projects_doc.get("members") or []) if m.get("project_number")}
    identyfikatory = {slownik[n] for n in numery if n in slownik}
    return identyfikatory, sorted(n for n in numery if n not in slownik)


def _siec_z_referencji(ref: str) -> str:
    """`.../projects/p/global/networks/w22a` -> `w22a`. Puste, gdy referencja nie ma tego ksztaltu."""
    return _nazwa_z_referencji(ref, "/networks/")


def _nazwa_z_referencji(ref: str, znacznik: str) -> str:
    """Ostatni segment po `znacznik`. Puste, gdy referencja nie ma tego ksztaltu."""
    tekst = str(ref or "")
    return tekst.rsplit(znacznik, 1)[-1] if znacznik in tekst else ""


def scal_operacje(wpisy: list[dict], metoda: str) -> list[dict]:
    """Jedno ZDARZENIE = jeden wynik, z NAJWCZESNIEJSZYM znacznikiem czasu.

    PULAPKA, KTORA PODWAJA KAZDY LICZNIK ZBUDOWANY NA AUDIT-LOGU COMPUTE: operacja dlugotrwala zostawia
    DWA wpisy o tej samej `resourceName` — jeden przy przyjeciu zadania (`operation.first`) i jeden przy
    zakonczeniu (`operation.last`). Licznik bez scalania meldowalby dwie sieci tam, gdzie powstala jedna,
    a przy alercie z progiem „> 0" bylby to blad niewidoczny (i tak strzela), az do chwili, gdy ktos
    zacznie czytac liczby.

    Bierzemy NAJWCZESNIEJSZY znacznik, bo zero czasu okna to moment utworzenia sieci — od niego liczy sie
    dojrzewanie. Wpis z niezerowym `status.code` (operacja odrzucona) WYRZUCA cale zdarzenie: sieci, ktora
    nie powstala, nie ma jak byc poza granica.
    """
    zebrane: dict[str, dict] = {}
    odrzucone: set[str] = set()
    for w in wpisy:
        pp = w.get("protoPayload") or {}
        if (pp.get("methodName") or "") != metoda:
            continue
        klucz = str(pp.get("resourceName") or "")
        if not klucz:
            continue
        if int(((pp.get("status") or {}).get("code")) or 0) != 0:
            odrzucone.add(klucz)
            continue
        czas = _epoch(w.get("timestamp"))
        if czas is None:
            continue
        biezacy = zebrane.get(klucz)
        if biezacy is None or czas < biezacy["czas"]:
            zebrane[klucz] = {"czas": czas, "wpis": w, "zasob": klucz}
    return sorted((z for k, z in zebrane.items() if k not in odrzucone), key=lambda z: z["czas"])


def sieci_maszyny(wpis: dict) -> list[str]:
    """Nazwy sieci, do ktorych podpieta jest tworzona maszyna. PUSTA LISTA = nie dalo sie odczytac.

    Rozroznienie „brak interfejsow" od „nie umiem odczytac" jest tu rozstrzygajace dla kierunku bledu:
    pusta lista oznacza NIEWIEDZE, a konsument traktuje niewiedze jako dopasowanie (fail-closed).

    ZMIERZONE NA ZYWYM WPISIE 2026-08-13 (#2028) — I TO ZMIENIA STATUS TEJ FUNKCJI. Wpis
    `v1.compute.instances.insert` z maszyny utworzonej w sieci CUSTOM-MODE **nie niesie pola
    `networkInterfaces[].network` W OGOLE**. Niesie wylacznie `subnetwork`:

        request.networkInterfaces[0].subnetwork =
            https://compute.googleapis.com/compute/v1/projects/<p>/regions/<r>/subnetworks/<s>
        request.networkInterfaces[0].network    =  (pola NIE MA)

    Przeszukanie calego wpisu pod katem nazwy sieci dalo zero trafien: poza `subnetwork` jedynym miejscem
    z ta informacja jest `authorizationInfo[].resource` — tez wskazujace PODSIEC, nie siec. Do tego wpis
    `operation.last` niesie `request` zlozony wylacznie z `@type`, wiec jest pusty niezaleznie od trybu
    sieci (scalanie i tak bierze `operation.first`, wiec to nie szkodzi).

    SKUTEK, KTORY TRZEBA ZNAC CZYTAJAC KONSUMENTA: dla sieci custom-mode ta funkcja zwraca ZAWSZE liste
    pusta, wiec sciezka fail-closed w `policz_okna_sieci` nie jest — jak zakladal pierwotny komentarz —
    rzadkim przypadkiem „przycietego `request`", tylko SCIEZKA DOMYSLNA. Funkcja zostaje, bo dla sieci
    auto-mode (`--network`, bez podsieci) pole `network` wystepuje, a wtedy dopasowanie jest scisle.
    """
    zadanie = (wpis.get("protoPayload") or {}).get("request") or {}
    nazwy = []
    for nic in (zadanie.get("networkInterfaces") or []):
        nazwa = _siec_z_referencji(nic.get("network"))
        if nazwa:
            nazwy.append(nazwa)
    return nazwy


def podsieci_maszyny(wpis: dict) -> list[str]:
    """Nazwy PODSIECI, do ktorych podpieta jest tworzona maszyna. PUSTA LISTA = nie dalo sie odczytac.

    ISTNIEJE, BO `sieci_maszyny` NA ZYWYCH DANYCH NIE ZWRACA NIC (patrz jej docstring). Zwraca SAMA
    NAZWE, wiec sluzy do POKAZANIA czlowiekowi (adnotacja, tresc alertu), a nie do dopasowania —
    nazwa podsieci jest unikalna dopiero w parze (projekt, region), wiec jako klucz mapy bylaby
    dwuznaczna. Do dopasowania sluzy `sciezki_podsieci_maszyny` nizej.
    """
    zadanie = (wpis.get("protoPayload") or {}).get("request") or {}
    nazwy = []
    for nic in (zadanie.get("networkInterfaces") or []):
        nazwa = _nazwa_z_referencji(nic.get("subnetwork"), "/subnetworks/")
        if nazwa:
            nazwy.append(nazwa)
    return nazwy


def _sciezka_podsieci(ref: str) -> str:
    """Referencja podsieci -> `projects/<p>/regions/<r>/subnetworks/<s>`. Puste, gdy to nie podsiec.

    DLACZEGO NORMALIZACJA, A NIE PLASKA NAZWA. Obie strony dopasowania podaja te sama podsiec w INNYM
    ksztalcie — zmierzone na zywych wpisach 2026-08-13 (#2052):

        instances.insert   request.networkInterfaces[0].subnetwork =
            https://compute.googleapis.com/compute/v1/projects/<p>/regions/<r>/subnetworks/<s>
        subnetworks.insert protoPayload.resourceName =
            projects/<p>/regions/<r>/subnetworks/<s>            (bez hosta i bez /compute/v1)

    Kotwica `projects/` sprowadza oba do jednej postaci. Klucz zostaje PELNA SCIEZKA, a nie sama nazwa,
    bo nazwa podsieci jest unikalna tylko w obrebie (projekt, region): `web` w `europe-west1` i `web`
    w `us-central1` moga nalezec do DWOCH ROZNYCH sieci, a splaszczenie do nazwy sklejaloby je w jeden
    wpis mapy i dawalo dopasowanie do zlej sieci — czyli dokladnie ten defekt, ktory ta zmiana zamyka.
    """
    tekst = str(ref or "")
    if "/subnetworks/" not in tekst:
        return ""
    i = tekst.find("projects/")
    return tekst[i:] if i >= 0 else ""


def sciezki_podsieci_maszyny(wpis: dict) -> list[str]:
    """Znormalizowane sciezki podsieci maszyny — klucze do `mapa_podsieci`. PUSTA = nie dalo sie odczytac."""
    zadanie = (wpis.get("protoPayload") or {}).get("request") or {}
    sciezki = []
    for nic in (zadanie.get("networkInterfaces") or []):
        sciezka = _sciezka_podsieci(nic.get("subnetwork"))
        if sciezka:
            sciezki.append(sciezka)
    return sciezki


def mapa_podsieci(wpisy: list[dict]) -> dict[str, str]:
    """Mapa `projects/../regions/../subnetworks/<s>` -> NAZWA SIECI, ze zdarzen `subnetworks.insert`.

    ZMIERZONE NA ZYWYCH WPISACH 2026-08-13 (#2052, 10 wpisow = 5 operacji, projekt czlonkowski labu) —
    i to jest jedyny powod, dla ktorego ta funkcja wyglada tak, a nie prosciej:

        operation.first=true  ->  request = {name, network, ipCidrRange, ...}   network JEST   (5/5)
        operation.last=true   ->  request = {"@type": ...} i NIC WIECEJ         network BRAK   (0/5)

    Czyli siec niesie WYLACZNIE wpis otwierajacy operacje. `scal_operacje` bierze wpis o NAJWCZESNIEJSZYM
    znaczniku czasu, wiec bierze wlasnie `first` — ale bierze go jako skutek uboczny reguly „zero czasu
    okna to moment utworzenia", a nie dlatego, ze ktos chcial `request`. Gdyby ta regula kiedykolwiek
    zmienila sie na „ostatni wpis" (kuszace: `last` niesie potwierdzony skutek), mapa zrobilaby sie PUSTA
    — a pusta mapa nie wywala niczego, tylko po cichu cofa dopasowanie do fail-closed. Cisza jest wtedy
    nieodroznialna od „nikt nie tworzyl podsieci". Dlatego selftest asertuje NIEPUSTOSC mapy zbudowanej
    z PARY wpisow (first + last) tej samej operacji, a nie sam ksztalt funkcji.
    """
    mapa: dict[str, str] = {}
    for z in scal_operacje(wpisy, COMPUTE_PODSIEC):
        zadanie = (z["wpis"].get("protoPayload") or {}).get("request") or {}
        siec = _siec_z_referencji(zadanie.get("network"))
        sciezka = _sciezka_podsieci(z["zasob"])
        if siec and sciezka:
            mapa[sciezka] = siec
    return mapa


def policz_okna_sieci(wpisy: list[dict], egzekwowane: set[str], okno_s: int) -> dict:
    """Ile sieci powstalo w czlonkach EGZEKWOWANYCH i do ilu z nich wstawiono maszyne PRZED dojrzeniem.

    DLACZEGO DWIE LICZBY, A ALERT TYLKO NA DRUGIEJ. Pierwsza (`sieci`) jest kontekstem i mianownikiem:
    utworzenie sieci VPC w projekcie czlonkowskim jest czynnoscia legalna, czesta i wykonywana przez
    ludzi, ktorzy o VPC-SC nie musza wiedziec nic. Alert na nia znaczylby „obudz dyzurnego, bo dywizja
    pracuje" — i zostalby wyciszony w tydzien, zabierajac ze soba jedyny sygnal o oknie. Druga liczba
    (`z_obciazeniem`) opisuje ZLAMANIE kolejnosci z DEC-32: obciazenie znalazlo sie w sieci, ktora przez
    pierwsze minuty nie jest dla granicy „wewnatrz". Dopiero to jest objaw — i dopiero to jest rzadkie.

    DLACZEGO CZLONKOWIE DRY-RUN SIE NIE LICZA. Siec w czlonku dry-run tez dojrzewa i tez jest przez chwile
    niewidoczna dla obu plaszczyzn konfiguracji (zmierzone), ale w konfiguracji dry-run NIC nie jest
    egzekwowane, wiec zadna dziura sie przez nia nie otwiera — nie ma czego alertowac.

    DOPASOWANIE MASZYNY DO SIECI JEST FAIL-CLOSED. Maszyna liczy sie do okna, gdy powstala w TYM SAMYM
    projekcie, w oknie `[t_sieci, t_sieci + okno_s]`, ORAZ (a) jawnie wskazuje te siec, albo (b) nie da sie
    odczytac zadnej jej sieci. Wariant (b) przeszacowuje: maszyna w sieci dojrzalej moze zostac policzona.
    To jest swiadomy kierunek bledu — falszywy alarm kosztuje jedno sprawdzenie w widoku sinka, a przeoczone
    okno jest nieodwracalne, bo ruch, ktory przez nie przeszedl, NIE ZOSTAWIA SLADU (41 przekroczen granicy,
    0 wpisow audytowych).

    SIEC ODCZYTUJE SIE NA DWA SPOSOBY, A DOPIERO ICH BRAK URUCHAMIA (b) — DEC-44. Wpis maszyny w sieci
    CUSTOM-MODE nie niesie pola `network` w ogole (#2028), wiec sposob pierwszy — jawna referencja
    z `sieci_maszyny` — na zywych danych milczy i (b) bylo sciezka DOMYSLNA. Sposob drugi to mapa
    podsiec->siec zbudowana ze zdarzen `subnetworks.insert` z TEGO SAMEGO okna odczytu: wpis maszyny
    zawsze niesie `subnetwork`, wiec gdy podsiec jest w mapie, siec jest ODCZYTEM, a nie hipoteza.

    CO SIE PRZEZ TO ZMIENIA W KIERUNKU BLEDU: NIC. Podsiec NIEZNANA (utworzona przed oknem odczytu, albo
    strumien `subnetworks.insert` nie dotarl) nadal idzie przez (b) i nadal liczy sie do okna. Zmienia sie
    tylko to, ze maszyna w sieci DOJRZALEJ obok swiezej sieci przestaje podnosic licznik — bo teraz wiadomo,
    ze stoi gdzie indziej, zamiast byc zgadywana. Alert przestaje nazywac siec, ktorej nie odczytal.
    """
    sieci = [z for z in scal_operacje(wpisy, COMPUTE_SIEC) if projekt_wpisu(z["wpis"]) in egzekwowane]
    maszyny = [z for z in scal_operacje(wpisy, COMPUTE_MASZYNA) if projekt_wpisu(z["wpis"]) in egzekwowane]
    # Mapa idzie z CALEGO okna odczytu, nie z projektow egzekwowanych — podsiec jest tu faktem
    # o topologii, a nie zdarzeniem do policzenia, wiec zawezanie jej niczego nie chroni, a moze zgubic.
    podsiec_do_sieci = mapa_podsieci(wpisy)

    szczegoly = []
    for s in sieci:
        projekt = projekt_wpisu(s["wpis"])
        nazwa = _siec_z_referencji(s["zasob"])
        trafione = []
        for m in maszyny:
            if projekt_wpisu(m["wpis"]) != projekt:
                continue
            if not (s["czas"] <= m["czas"] <= s["czas"] + okno_s):
                continue
            podpiete = sieci_maszyny(m["wpis"])
            zrodlo = "wpis" if podpiete else ""
            if not podpiete:
                # Kolejnosc ma znaczenie: mapy pytamy DOPIERO, gdy jawnej referencji nie ma. Jawna
                # referencja jest odczytem z tego samego wpisu, wiec nie ma czego nia przebijac.
                podpiete = [podsiec_do_sieci[p] for p in sciezki_podsieci_maszyny(m["wpis"])
                            if p in podsiec_do_sieci]
                zrodlo = "mapa" if podpiete else ""
            if podpiete and nazwa and nazwa not in podpiete:
                continue
            trafione.append({
                "maszyna": m["zasob"].rsplit("/", 1)[-1],
                "po_sekundach": round(m["czas"] - s["czas"]),
                # `False` = dopasowanie poszlo sciezka fail-closed, czyli `siec` obok jest HIPOTEZA.
                # `True` = siec zostala ODCZYTANA: albo z wpisu maszyny, albo z mapy podsiec->siec.
                "siec_odczytana": bool(podpiete),
                "zrodlo_sieci": zrodlo or None,
                "podsiec": ", ".join(podsieci_maszyny(m["wpis"])) or None,
            })
        szczegoly.append({"projekt": projekt, "siec": nazwa,
                          "utworzona": datetime.datetime.fromtimestamp(
                              s["czas"], datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "obciazenie": trafione})
    return {
        "sieci": len(sieci),
        "z_obciazeniem": sum(1 for s in szczegoly if s["obciazenie"]),
        "szczegoly": szczegoly,
    }


# --- wejscie/wyjscie ---------------------------------------------------------------------------------

def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout.strip()


def _http(url: str, token: str, metoda: str = "GET", cialo: dict | None = None,
          naglowki: dict | None = None) -> dict:
    dane = json.dumps(cialo).encode() if cialo is not None else None
    req = urllib.request.Request(url, data=dane, method=metoda)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if dane is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (naglowki or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=60) as odp:
        tresc = odp.read().decode()
    return json.loads(tresc) if tresc else {}


def sekundy_zalegania(repo: str, workflow: str, galaz: str, token: str, sciezki: list[str],
                      teraz: int) -> tuple[int, str]:
    """Wiek najstarszej zmergowanej, a niezastosowanej zmiany granicy + jednozdaniowe uzasadnienie.

    ALGORYTM I JEGO TRZY PULAPKI:
      * bierzemy `head_sha` OSTATNIEGO UDANEGO przebiegu apply, nie ostatniego przebiegu. Przebieg
        nieudany, wiszacy i nieistniejacy daja wtedy ten sam wynik — o to chodzi, bo objaw jest ten sam;
      * `--first-parent` przy liczeniu czasu: bez tego bierzemy date commita AUTORA (moze byc sprzed
        tygodnia), a nie moment WEJSCIA zmiany na galaz domyslna. Zawyzaloby to wiek o czas trwania review;
      * jesli `head_sha` nie istnieje w lokalnej historii (force-push, rebase, plytki klon), NIE udajemy,
        ze wszystko gra: liczymy wiek od HEAD i mowimy o tym w uzasadnieniu.
    """
    odp = _http(
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs"
        f"?status=success&branch={galaz}&per_page=1",
        token, naglowki={"X-GitHub-Api-Version": "2022-11-28"})
    przebiegi = odp.get("workflow_runs") or []
    head = _git("rev-parse", "HEAD")

    if not przebiegi:
        czas = _git("log", "-1", "--format=%ct", "--first-parent", "HEAD", "--", *sciezki)
        if not czas:
            return 0, "brak udanego apply i brak commitow dotykajacych granicy"
        return max(0, teraz - int(czas)), "ANI JEDEN przebieg apply nie zakonczyl sie sukcesem"

    sha = przebiegi[0]["head_sha"]
    if sha == head:
        return 0, f"ostatni udany apply stoi na HEAD ({sha[:8]})"

    znany = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True).returncode == 0
    if not znany:
        czas = _git("log", "-1", "--format=%ct", "--first-parent", "HEAD", "--", *sciezki)
        return (max(0, teraz - int(czas)) if czas else 0,
                f"commit ostatniego udanego apply ({sha[:8]}) nie istnieje w historii — liczone od HEAD")

    czasy = _git("log", "--format=%ct", "--first-parent", f"{sha}..HEAD", "--", *sciezki).splitlines()
    if not czasy:
        return 0, f"od ostatniego udanego apply ({sha[:8]}) nic nie dotknelo granicy"
    najstarszy = int(czasy[-1])
    return max(0, teraz - najstarszy), f"zmiana z {sha[:8]}..{head[:8]} czeka na apply"


def czytaj_widok(widok: str, filtr: str, od_epoch: int, token: str, limit_stron: int = 10) -> list[dict]:
    """Wpisy z JEDNEGO widoku kubelka logow, od `od_epoch` do teraz.

    DLACZEGO WIDOK, A NIE PROJEKT CZLONKA. Naruszenie powstaje w logu projektu-wlasciciela zasobu,
    a po promocji ten log sam lezy ZA GRANICA — odczyt z zewnatrz bywa odrzucany przez VPC-SC, czyli
    producent metryki „ile bylo odmow” sam generowalby odmowy. Widok sinka stoi w projekcie
    administracyjnym POZA perimetrem, wiec ten tryb awarii nie istnieje.

    STRONICOWANIE JEST OBOWIAZKOWE, nie optymalizacja: `entries.list` oddaje domyslnie strone, a incydent
    to setki wpisow w minutach. Bez petli metryka pokazywalaby sufit strony zamiast liczby odmow —
    czyli mylilaby „duzo” z „bardzo duzo” dokladnie wtedy, gdy ta roznica decyduje o eskalacji.
    """
    od = datetime.datetime.fromtimestamp(od_epoch, datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    pelny_filtr = f'{filtr} AND timestamp>="{od}"' if filtr else f'timestamp>="{od}"'
    wpisy: list[dict] = []
    strona = None
    for _ in range(limit_stron):
        cialo = {"resourceNames": [widok], "filter": pelny_filtr, "pageSize": 1000}
        if strona:
            cialo["pageToken"] = strona
        odp = _http("https://logging.googleapis.com/v2/entries:list", token, metoda="POST", cialo=cialo)
        wpisy.extend(odp.get("entries") or [])
        strona = odp.get("nextPageToken")
        if not strona:
            break
    return wpisy


def pobierz_perimetr(policy_id: str, nazwa: str, token: str) -> dict:
    """Zywa konfiguracja granicy z Access Context Managera. Konto planu ma do tego `policyReader`."""
    return _http(f"https://accesscontextmanager.googleapis.com/v1/accessPolicies/{policy_id}"
                 f"/servicePerimeters/{nazwa}", token)


def szukaj_projektow(org_id: str, token: str, limit_stron: int = 20) -> list[dict]:
    """Stan cyklu zycia WSZYSTKICH projektow organizacji — JEDNO wywolanie Asset Inventory na strone.

    DLACZEGO ASSET INVENTORY, A NIE `resourcemanager.projects.get` PO KAZDYM CZLONKU (DEC-42):
      * UPRAWNIENIE, KTORE JUZ MAMY. Konto planu ma `roles/cloudasset.viewer` na organizacji (zawiera
        `cloudasset.assets.searchAllResources`); `resourcemanager.projects.get` nie ma ZADNE z kont
        pipeline'u. Wariant per czlonek zaczynalby sie wiec od nowego nadania na organizacji;
      * KOSZT NIE ROSNIE Z LICZBA CZLONKOW. Kilkuset czlonkow to nadal jedno wywolanie na strone
        (`pageSize=500`), a nie kilkaset wywolan przy kazdym przelocie;
      * WIDZI PROJEKTY SKASOWANE. `projects list` domyslnie oddaje wylacznie `ACTIVE`, wiec martwy czlonek
        jest tam NIEWIDOCZNY — „nie ma go na liscie" wyglada identycznie jak „nigdy go nie bylo".

    BEZ NAGLOWKA `X-Goog-User-Project` — I TO JEST DECYZJA, NIE PRZEOCZENIE. Ustawienie projektu
    rozliczeniowego wymaga `serviceusage.services.use` na tym projekcie; konto planu go NIE MA, wiec
    naglowek zamienilby dzialajace wywolanie w `403`. Kwota konta serwisowego idzie domyslnie na projekt,
    ktory je posiada — a tam `cloudasset.googleapis.com` musi byc wlaczone (`docs/2-uprawnienia-i-wif.md`).
    Z poswiadczen UZYTKOWNIKA (odczyt z reki) jest odwrotnie: tam naglowek albo `--billing-project` JEST
    wymagany, i dlatego komenda w runbooku wyglada inaczej niz ten kod.

    OPOZNIENIE INDEKSU JEST REALNE I NAZWANE: Asset Inventory nie jest odczytem z Resource Managera,
    tylko z indeksu, ktory za nim nadaza. Zmierzone na tej organizacji — patrz `docs/7-alerty.md`
    (sekcja o martwym czlonku). Dla przelotu godzinnego jest to nieistotne; dla bramki na pull requescie
    byloby to zrodlo falszywych werdyktow — i to jeden z powodow, dla ktorych bramki tam nie ma.
    """
    wyniki: list[dict] = []
    strona = None
    for _ in range(limit_stron):
        zapytanie = {"assetTypes": ASSET_TYP_PROJEKT, "pageSize": "500"}
        if strona:
            zapytanie["pageToken"] = strona
        url = (f"https://cloudasset.googleapis.com/v1/organizations/{org_id}:searchAllResources"
               f"?{urllib.parse.urlencode(zapytanie)}")
        odp = _http(url, token)
        wyniki.extend(odp.get("results") or [])
        strona = odp.get("nextPageToken")
        if not strona:
            break
    return wyniki


def historia_procentow(projekt: str, token: str, dni: int, teraz: int) -> dict:
    """Historia `attribute_budget_percent` z Cloud Monitoring, per etykieta `config`.

    Czytamy WLASNA metryke sprzed godzin zamiast trzymac plik historii w GCS — Cloud Monitoring i tak
    przechowuje te punkty (6 tygodni dla metryk wlasnych), wiec osobny magazyn byłby druga kopia tych
    samych danych, z wlasnym IAM, wlasnym trybem awarii i wlasnym rozjazdem.
    """
    start = datetime.datetime.fromtimestamp(teraz - dni * 86400, datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    koniec = datetime.datetime.fromtimestamp(teraz, datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    filtr = urllib.parse.quote(f'metric.type="{METRYKI["budzet_procent"]}"')
    url = (f"https://monitoring.googleapis.com/v3/projects/{projekt}/timeSeries"
           f"?filter={filtr}&interval.startTime={start}&interval.endTime={koniec}"
           f"&view=FULL&pageSize=2000")
    wynik: dict[str, list[tuple[float, float]]] = {"spec": [], "status": []}
    try:
        odp = _http(url, token)
    except urllib.error.HTTPError as e:
        # Brak historii NIE jest awaria obserwatora: przy pierwszym przebiegu metryka jeszcze nie istnieje.
        # Zwracamy pustke, a `dni_do_sciany` odda sentynele — czyli brak prognozy, nie falszywy alarm.
        print(f"::warning::nie udalo sie odczytac historii budzetu ({e.code}) — prognoza bedzie sentynela",
              file=sys.stderr)
        return wynik
    for seria in odp.get("timeSeries", []) or []:
        config = seria.get("metric", {}).get("labels", {}).get("config")
        if config not in wynik:
            continue
        for punkt in seria.get("points", []) or []:
            koniec_p = punkt["interval"]["endTime"]
            znacznik = datetime.datetime.fromisoformat(koniec_p.replace("Z", "+00:00")).timestamp()
            wynik[config].append((znacznik, float(punkt["value"]["doubleValue"])))
    for config in wynik:
        wynik[config].sort()
    return wynik


def punkt(typ: str, wartosc, etykiety: dict | None, projekt: str, teraz: int, calkowita: bool) -> dict:
    czas = datetime.datetime.fromtimestamp(teraz, datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "metric": {"type": typ, "labels": etykiety or {}},
        # `global` z jawnym `project_id`: metryka opisuje KONFIGURACJE perimetru, ktora jest obiektem
        # organizacyjnym, a nie zasobem w tym projekcie. Zwiazanie jej z instancja czy klastrem sugerowaloby
        # zrodlo, ktorego nie ma.
        "resource": {"type": "global", "labels": {"project_id": projekt}},
        "points": [{
            "interval": {"endTime": czas},
            "value": {"int64Value": str(int(wartosc))} if calkowita else {"doubleValue": float(wartosc)},
        }],
    }


def zmierz(args) -> int:
    # `yaml` importujemy DOPIERO TUTAJ, a nie na gorze modulu, i to jest celowe: czyste funkcje wyzej maja
    # dac sie zaimportowac i przetestowac bez ani jednej zaleznosci spoza biblioteki standardowej. Import
    # na gorze zamienilby brak `pyyaml` w bledzie importu calego modulu, czyli w bramce, ktora pada
    # z powodu niezwiazanego z tym, co sprawdza.
    import yaml

    teraz = int(args.teraz or datetime.datetime.now(datetime.UTC).timestamp())
    gh_token = os.environ.get("GH_TOKEN", "")
    g_token = os.environ.get("GOOGLE_ACCESS_TOKEN", "")

    zaleganie, powod = sekundy_zalegania(args.repo, args.workflow, args.branch, gh_token,
                                         args.sciezki.split(","), teraz)
    zaleganie = wiek_niezastosowanej_zmiany(zaleganie)

    # BUDZET LICZYMY Z ZYWEJ GRANICY, nie z deklaracji — patrz `koszt_konfiguracji`. Deklaracja zostaje
    # jako KONTROLA: rozjazd tych dwoch liczb znaczy, ze w granicy jest cos, czego nie ma w Gicie (albo
    # odwrotnie), i wyglada dokladnie tak samo jak dryf — o ktorym mowi wlasny alert.
    polityka = yaml.safe_load(open(args.policy))
    limit = polityka["attribute_budget"]["limit_per_config"]
    budzet_z_deklaracji = json.load(open(args.budget))
    zadeklarowane = {"spec": budzet_z_deklaracji["dry_run"], "status": budzet_z_deklaracji["enforced"]}

    perimetr = {}
    blad_odczytu = None
    try:
        perimetr = pobierz_perimetr(polityka["organization"]["access_policy_name"],
                                    polityka["perimeter"]["name"], g_token)
    except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
        blad_odczytu = str(e)

    if blad_odczytu:
        # FAIL-CLOSED: NIE podstawiamy liczby z deklaracji. Metryka nazywa sie „zuzycie budzetu granicy";
        # podstawienie liczby z YAML-i daloby wartosc, ktora wyglada poprawnie i opisuje co innego —
        # dokladnie ten tryb awarii, ktory ten plik ma tropic. Brak punktu jest uczciwszy niz zly punkt.
        print(f"::warning::nie udalo sie odczytac zywej granicy ({blad_odczytu}) — metryki budzetu "
              f"NIE zostana opublikowane w tym przebiegu", file=sys.stderr)
        procenty, prognoza = {}, {}
        zywe = {}
    else:
        procenty = procenty_budzetu(perimetr, limit)
        zywe = {n: koszt_konfiguracji(perimetr.get(n) or {}) for n in ("spec", "status")}
        historia = historia_procentow(args.project, g_token, args.history_days, teraz) if g_token else \
            {"spec": [], "status": []}
        prognoza = {k: round(dni_do_sciany(historia[k], procenty[k]), 2) for k in procenty}
        # Rozjazd zywej granicy z deklaracja: JEDNA liczba, DWIE przyczyny, dwie procedury. Rozroznienie
        # robi `komunikat_rozjazdu` — patrz jego docstring, bo to jest miejsce, w ktorym ta kontrola raz
        # juz wyslala dyzurnego pod alert milczacy z definicji.
        for n in ("spec", "status"):
            komunikat = komunikat_rozjazdu(n, zywe[n], zadeklarowane[n], zaleganie > 0, powod)
            if komunikat:
                print(f"::warning::{komunikat}", file=sys.stderr)

    # --- CZY PROJEKTY CZLONKOW NADAL ISTNIEJA (DEC-42) -------------------------------------------
    #
    # JEDYNA WARSTWA, KTORA W OGOLE WIDZI SKASOWANY PROJEKT CZLONKA. Zmierzone: `plan` -> `No changes`,
    # `apply` -> `0 added, 0 changed, 0 destroyed`, dryf -> 0, `expiry-sweep` -> pomija, pre-flight ->
    # „projekt istnieje". Wszystkie te odpowiedzi sa PRAWDZIWE — Git i granica zgadzaja sie co do numeru,
    # ktorego nie ma. Milczy przy tym rzecz grozniejsza od martwego wpisu: naruszenia takiego czlonka
    # spadaja do zera, a zero jest dowodem „czystego okna" dla bramki promocji.
    #
    # FAIL-CLOSED W DWOCH MIEJSCACH, oba z tego samego powodu co reszta tego pliku. Bez ZYWEJ granicy nie
    # wiadomo, kto jest czlonkiem — liczenie z deklaracji daloby liczbe wygladajaca poprawnie i opisujaca
    # co innego. Bez odpowiedzi Asset Inventory nie wiadomo NIC o stanach. W obu przypadkach NIE
    # publikujemy zera: zero znaczyloby „wszyscy czlonkowie zyja", czyli zamienialoby slepote w spokoj.
    # Brak punktu zapala `condition_absent` polityki, czyli awarie widac JAKO awarie.
    czlonkowie_stan = None
    org_id = str((polityka.get("organization") or {}).get("org_id") or "")
    if blad_odczytu:
        print("::warning::bez odczytu zywej granicy nie wiadomo, kto jest jej czlonkiem — zywotnosc "
              "projektow czlonkowskich NIE jest liczona w tym przebiegu", file=sys.stderr)
    elif not org_id:
        print("::warning::brak `organization.org_id` w policy.yaml — nie ma zakresu dla Asset Inventory, "
              "metryka members_not_active NIE powstanie", file=sys.stderr)
    else:
        try:
            czlonkowie_stan = czlonkowie_bez_potwierdzenia(
                perimetr, stany_projektow(szukaj_projektow(org_id, g_token)))
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            print(f"::warning::nie udalo sie odczytac stanu projektow z Asset Inventory ({e}) — metryka "
                  f"members_not_active NIE zostanie opublikowana, martwy-czlowiek alertu ja przejmie",
                  file=sys.stderr)
    if czlonkowie_stan:
        for wpis in czlonkowie_stan["nieaktywni"]:
            print(f"::warning::MARTWY CZLONEK GRANICY: `projects/{wpis['numer']}` ma stan "
                  f"`{wpis['stan']}`, a nadal jest w konfiguracji perimetru. Jego naruszenia spadna do "
                  f"zera i beda wygladac jak czyste okno: docs/7-alerty.md#martwy-czlonek", file=sys.stderr)
        if czlonkowie_stan["nieodczytani"]:
            print(f"::warning::STANU NIE ODCZYTANO dla czlonkow: "
                  f"{', '.join(czlonkowie_stan['nieodczytani'])} — to NIE jest potwierdzenie, ze zyja: "
                  f"docs/7-alerty.md#martwy-czlonek", file=sys.stderr)
        if czlonkowie_stan["pominiete"]:
            print(f"::warning::czlonkowie spoza indeksu projektow (wlasny cykl zycia, NIE liczeni): "
                  f"{', '.join(czlonkowie_stan['pominiete'])}", file=sys.stderr)

    plan = json.load(open(args.plan_json)) if os.path.exists(args.plan_json) else {}
    dryf = dryf_z_planu(plan, zaleganie > 0)

    # --- to, co dzieje sie NA granicy (naruszenia + zmiany konfiguracji) ---------------------------
    #
    # ZRODLEM JEST WIDOK SINKA, a nie metryka log-based — bo log-based liczy tylko wpisy przyjete przez
    # Log Router WLASNEGO projektu, a te powstaja w projekcie czlonka (naruszenia) albo w organizacji
    # (zmiany ACM). Zmierzone para kontrolna w #2000; pelne uzasadnienie w `terraform/monitoring.tf`.
    #
    # FAIL-CLOSED: gdy odczyt padnie, NIE publikujemy zera. Zero znaczyloby „nie bylo odmow”, czyli
    # zamienialoby slepote w cisze, a cisze w spokoj — dokladnie ten tryb awarii, ktory ten plik tropi.
    # Brak punktu zapala `condition_absent` obu polityk, czyli awarie obserwatora widac JAKO awarie.
    punkty_granicy = []
    projects_doc = yaml.safe_load(open(args.projects))
    okna_sieci = None
    zrodlo = (yaml.safe_load(open(args.alerting)) or {}).get("violations_source") if \
        os.path.exists(args.alerting) else None
    if not zrodlo:
        print("::warning::brak sekcji `violations_source` w alerting.yaml — metryki naruszen i zmian "
              "konfiguracji NIE beda publikowane (polityki alertu tez sie wtedy nie tworza)", file=sys.stderr)
        naruszenia, zmiany_acm = None, None
    else:
        okno = int(zrodlo.get("window_seconds", 5400))
        baza = (f"projects/{zrodlo['project_id']}/locations/{zrodlo['location']}"
                f"/buckets/{zrodlo['bucket']}/views")
        # Ta sama tozsamosc, ktora wykluczal filtr metryki log-based — czytana z `policy.yaml`, bo tam
        # mieszka konfiguracja monitoringu i tam zmienia sie przy rotacji konta.
        konto_apply = (polityka.get("monitoring") or {}).get("apply_service_account", "")
        naruszenia, zmiany_acm = None, None
        try:
            wpisy = czytaj_widok(
                f"{baza}/{zrodlo['view']}",
                'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.'
                'VpcServiceControlAuditMetadata"',
                teraz - okno, g_token)
            naruszenia = policz_naruszenia(wpisy)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            print(f"::warning::nie udalo sie odczytac widoku naruszen ({e}) — metryki odmow NIE zostana "
                  f"opublikowane, martwy-czlowiek alertu je przejmie", file=sys.stderr)
        try:
            wpisy_acm = czytaj_widok(
                f"{baza}/{zrodlo['config_view']}",
                'protoPayload.serviceName="accesscontextmanager.googleapis.com"',
                teraz - okno, g_token)
            zmiany_acm = policz_zmiany_konfiguracji(wpisy_acm, konto_apply)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            print(f"::warning::nie udalo sie odczytac widoku zmian konfiguracji ({e}) — metryka zmian "
                  f"poza pipeline'em NIE zostanie opublikowana", file=sys.stderr)

        # OKNO SWIEZEJ SIECI (DEC-32) — trzeci strumien, WLASNY kubelek i wlasny widok.
        #
        # DWA WARUNKI, OBA FAIL-CLOSED. Bez wspolrzednych widoku nie ma czego czytac. Bez ZYWEJ granicy nie
        # wiadomo, kto jest egzekwowany — a policzenie tego z deklaracji dawaloby liczbe, ktora wyglada
        # poprawnie i opisuje co innego (ten sam powod, dla ktorego budzet nie podstawia deklaracji).
        # W obu przypadkach NIE publikujemy zera: zero znaczyloby „nikt nie zlamal kolejnosci", czyli
        # zamienialoby slepote w spokoj. Brak punktu zapala `condition_absent` polityki.
        widok_sieci = zrodlo.get("network_view")
        if not widok_sieci:
            print("::warning::brak `violations_source.network_view` — detektor okna swiezej sieci NIE "
                  "liczy (metryki network_inserts_enforced / network_window_workload nie powstana)",
                  file=sys.stderr)
        elif blad_odczytu:
            print("::warning::bez odczytu zywej granicy nie wiadomo, ktore projekty sa EGZEKWOWANE — "
                  "detektor okna swiezej sieci NIE liczy w tym przebiegu", file=sys.stderr)
        else:
            egzekwowane, nieznane = projekty_egzekwowane(perimetr, projects_doc)
            if nieznane:
                # Numer w `status` bez wpisu w deklaracji: ktos jest w granicy, a nie ma go w Gicie. Ma to
                # wlasne alerty (dryf, rozjazd budzetu); tutaj liczy sie to, ze detektor NIE UDAJE, ze
                # przeszukal cala konfiguracje egzekwowana, skoro czesci jej nie umie nazwac.
                print(f"::warning::numery w `status` bez wpisu w projects.yaml: {', '.join(nieznane)} — "
                      f"okno swiezej sieci NIE jest dla nich liczone", file=sys.stderr)
            okno_dojrzewania = int(zrodlo.get("network_maturation_seconds", OKNO_DOJRZEWANIA_S))
            baza_sieci = (f"projects/{zrodlo['project_id']}/locations/{zrodlo['location']}"
                          f"/buckets/{zrodlo.get('network_bucket', widok_sieci)}/views")
            try:
                # Okno ODCZYTU jest dluzsze od okna liczenia o okno DOJRZEWANIA: para (siec, maszyna) ma
                # sie zmiescic w calosci w jednym przebiegu. Bez tego zapasu siec utworzona tuz przed
                # granica okna zostalaby przeczytana bez swojej maszyny, a w nastepnym przebiegu — maszyna
                # bez swojej sieci, i para nie zostalaby zlozona przez ZADEN przebieg.
                #
                # TRZECI CZLON (`subnetworks.insert`) MUSI BYC TU, A NIE TYLKO W FILTRZE SINKA — to sa
                # DWA rozne filtry i przepuszczenie zdarzenia przez sink nic nie daje, dopoki zapytanie
                # odczytu go nie wpuszcza. Pominiecie tego miejsca nie wywala niczego: mapa podsiec->siec
                # wyszlaby pusta, dopasowanie cofneloby sie do fail-closed, a przebieg nadal bylby zielony.
                wpisy_compute = czytaj_widok(
                    f"{baza_sieci}/{widok_sieci}",
                    f'protoPayload.methodName="{COMPUTE_SIEC}" OR '
                    f'protoPayload.methodName="{COMPUTE_MASZYNA}" OR '
                    f'protoPayload.methodName="{COMPUTE_PODSIEC}"',
                    teraz - okno - okno_dojrzewania, g_token)
                okna_sieci = policz_okna_sieci(wpisy_compute, egzekwowane, okno_dojrzewania)
            except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
                print(f"::warning::nie udalo sie odczytac widoku zdarzen Compute ({e}) — metryki okna "
                      f"swiezej sieci NIE zostana opublikowane", file=sys.stderr)

        if naruszenia is not None:
            punkty_granicy += [
                punkt(METRYKI["naruszenia_enforced"], naruszenia["enforced"], None, args.project, teraz, True),
                punkt(METRYKI["naruszenia_dry_run"], naruszenia["dry_run"], None, args.project, teraz, True),
            ]
        if zmiany_acm is not None:
            punkty_granicy.append(
                punkt(METRYKI["zmiany_poza_pipelinem"], zmiany_acm, None, args.project, teraz, True))
        if okna_sieci is not None:
            punkty_granicy += [
                punkt(METRYKI["sieci_egzekwowane"], okna_sieci["sieci"], None, args.project, teraz, True),
                punkt(METRYKI["sieci_z_obciazeniem"], okna_sieci["z_obciazeniem"], None, args.project,
                      teraz, True),
            ]
            # KTORA siec i KTORA maszyna — do adnotacji przebiegu, nie do etykiety metryki. Etykieta
            # sprawilaby, ze seria powstaje i znika razem ze zdarzeniem, czyli zdrowa cisza bylaby
            # nieodrozninalna od awarii obserwatora (lekcja z metryki odmow).
            for s in okna_sieci["szczegoly"]:
                if not s["obciazenie"]:
                    continue
                # PRZY DOPASOWANIU FAIL-CLOSED NAZWA SIECI JEST HIPOTEZA — i adnotacja MUSI to mowic
                # wprost. Na zywych danych `network` nie wystepuje we wpisie maszyny (#2028), wiec
                # „siec X dostala obciazenie" bez tego zastrzezenia bylo zdaniem twierdzacym wiecej, niz
                # pomiar uprawnia: maszyna mogla stac w sieci dojrzalej.
                #
                # ODKAD JEST MAPA PODSIEC->SIEC (DEC-44) TA SCIEZKA JEST WYJATKIEM, A NIE DOMYSLNA — ale
                # nadal istnieje (podsiec starsza niz okno odczytu, brak strumienia). Adnotacja nazywa
                # ZRODLO odczytu, bo „z wpisu" i „z mapy" roznia sie tym, czego wymagaly: mapa dziala
                # tylko wtedy, gdy `subnetworks.insert` trafil do tego samego okna. Dyzurny, ktory tego
                # nie wie, nie odrozni „odczytalem" od „mialem z czego odczytac".
                czesci = []
                for o in s["obciazenie"]:
                    tekst = f"{o['maszyna']} po {o['po_sekundach']} s"
                    podsiec = o.get("podsiec") or "nieodczytana"
                    if not o["siec_odczytana"]:
                        tekst += f" (siec NIEODCZYTANA z wpisu — dopasowanie fail-closed, podsiec: {podsiec})"
                    elif o.get("zrodlo_sieci") == "mapa":
                        tekst += f" (siec odczytana z mapy podsiec->siec, podsiec: {podsiec})"
                    czesci.append(tekst)
                opis = ", ".join(czesci)
                pewnosc = "" if all(o["siec_odczytana"] for o in s["obciazenie"]) else " [HIPOTEZA]"
                print(f"::warning::OKNO BEZ OCHRONY{pewnosc}: siec `{s['siec']}` w `{s['projekt']}` (utworzona "
                      f"{s['utworzona']}) dostala obciazenie przed dojrzeniem: {opis}", file=sys.stderr)
    # Data w UTC, nie lokalna: `review_by` jest datą kalendarzową bez strefy, a runner i laptop operatora
    # bywają w różnych strefach — wtedy ta sama konfiguracja daje dwa różne wyniki w oknie kilku godzin.
    wygasli = wygasli_czlonkowie(projects_doc, datetime.datetime.fromtimestamp(teraz, datetime.UTC).date())

    wynik = {
        "teraz": teraz,
        "powod_zalegania": powod,
        "punkty": [
            punkt(METRYKI["apply_pending"], zaleganie, None, args.project, teraz, True),
            punkt(METRYKI["dryf"], dryf, None, args.project, teraz, True),
            punkt(METRYKI["wygasli"], wygasli, None, args.project, teraz, True),
        ] + [
            punkt(METRYKI["budzet_procent"], procenty[c], {"config": c}, args.project, teraz, False)
            for c in sorted(procenty)
        ] + [
            punkt(METRYKI["budzet_dni"], prognoza[c], {"config": c}, args.project, teraz, False)
            for c in sorted(prognoza)
        ] + ([
            # OBIE SERIE PUBLIKUJA SIE ZAWSZE, TAKZE Z ZEREM — i to jest warunek poprawnosci, nie
            # symetria dla ozdoby. Zbior wartosci etykiety jest ZAMKNIETY (dwie), wiec seria nie
            # powstaje i nie znika razem ze zdarzeniem; gdyby publikowal sie tylko niezerowy worek,
            # zdrowa cisza bylaby nieodrozninalna od awarii producenta i martwy-czlowiek polityki
            # chodzilby bez przerwy. To ta sama lekcja, co przy metryce odmow.
            punkt(METRYKI["czlonkowie_nieaktywni"], len(czlonkowie_stan["nieaktywni"]),
                  {"state": "not_active"}, args.project, teraz, True),
            punkt(METRYKI["czlonkowie_nieaktywni"], len(czlonkowie_stan["nieodczytani"]),
                  {"state": "unreadable"}, args.project, teraz, True),
        ] if czlonkowie_stan else []) + punkty_granicy,
        # Czytelne podsumowanie dla `$GITHUB_STEP_SUMMARY` — to jest DOWOD, ze producent liczy realne
        # wartosci, niezalezny od tego, czy alert akurat odpalil. `zadeklarowane` stoi obok `zywe`
        # celowo: te dwie liczby maja byc rowne, a ich rozjazd jest sam w sobie informacja.
        "podsumowanie": {
            "apply_pending_seconds": zaleganie,
            "attribute_budget_percent": procenty,
            "attribute_budget_days_to_limit": prognoza,
            "atrybuty_w_granicy": zywe,
            "atrybuty_w_deklaracji": zadeklarowane,
            "limit_na_konfiguracje": limit,
            "drift_resources": dryf,
            "members_expired": wygasli,
            "blad_odczytu_granicy": blad_odczytu,
            # `null` znaczy NIE ODCZYTANO (awaria albo brak konfiguracji), a `0` znaczy ODCZYTANO ZERO.
            # Te dwie rzeczy MUSZA byc rozroznialne w podsumowaniu, bo tylko druga jest zdaniem o swiecie.
            "violations_enforced": (naruszenia or {}).get("enforced") if naruszenia else None,
            "violations_dry_run": (naruszenia or {}).get("dry_run") if naruszenia else None,
            "config_changed_outside_pipeline": zmiany_acm,
            # To samo rozroznienie `null` vs `0` co wyzej: `null` = detektor nie liczyl (brak widoku,
            # brak zywej granicy, blad odczytu), `0` = policzyl i nie bylo czego zglosic.
            "network_inserts_enforced": (okna_sieci or {}).get("sieci") if okna_sieci else None,
            "network_window_workload": (okna_sieci or {}).get("z_obciazeniem") if okna_sieci else None,
            # To samo rozroznienie `null` vs `0`, a tutaj jest ono NAJWAZNIEJSZE w calym podsumowaniu:
            # `null` znaczy „nie sprawdzilem, czy czlonkowie zyja", a `0` — „sprawdzilem i zyja". Zlanie
            # tych dwoch daloby raport, ktory po awarii odczytu meldowalby zdrowie.
            "members_not_active": len(czlonkowie_stan["nieaktywni"]) if czlonkowie_stan else None,
            "members_unreadable": len(czlonkowie_stan["nieodczytani"]) if czlonkowie_stan else None,
        },
        # KTORY czlonek i z jakim stanem — do artefaktu przebiegu i do runbooka, nie do etykiety metryki
        # (etykieta z numerem projektu tworzylaby i kasowala serie razem ze zdarzeniem).
        "czlonkowie_bez_potwierdzenia": czlonkowie_stan,
        # Szczegoly okna zostaja w artefakcie przebiegu — alert niesie LICZBE, a „ktora siec" odzyskuje
        # sie stad albo odczytem z widoku (komenda w docs/7-alerty.md).
        "okna_sieci": (okna_sieci or {}).get("szczegoly") if okna_sieci else None,
    }
    json.dump(wynik, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    print()
    return 0


def opublikuj(args) -> int:
    token = os.environ["GOOGLE_ACCESS_TOKEN"]
    dane = json.load(open(args.input))
    punkty = dane["punkty"]
    if args.only:
        punkty = [p for p in punkty if p["metric"]["type"].endswith(args.only)]
    _http(f"https://monitoring.googleapis.com/v3/projects/{args.project}/timeSeries",
          token, metoda="POST", cialo={"timeSeries": punkty})
    for p in punkty:
        wartosc = p["points"][0]["value"]
        print(f"opublikowano {p['metric']['type']} {p['metric']['labels']} = "
              f"{wartosc.get('int64Value', wartosc.get('doubleValue'))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    pod = ap.add_subparsers(dest="tryb", required=True)

    m = pod.add_parser("measure", help="policz metryki (konto read-only)")
    m.add_argument("--repo", required=True, help="OWNER/REPO")
    m.add_argument("--project", required=True, help="projekt monitoringu")
    m.add_argument("--workflow", default="apply.yml")
    m.add_argument("--branch", default="main")
    m.add_argument("--sciezki", default="perimeter,terraform",
                   help="katalogi, ktorych zmiana wymaga apply — MUSZA zgadzac sie z `paths` w apply.yml")
    m.add_argument("--declarations", default="declarations.json")
    m.add_argument("--budget", default="budget.json",
                   help="wynik `attribute_budget.py --format json` — uzywany WYLACZNIE jako kontrola "
                        "rozjazdu; metryka budzetu liczy sie z zywej granicy")
    m.add_argument("--policy", default="perimeter/policy.yaml",
                   help="stad bierze sie nazwa polityki dostepu, nazwa perimetru i limit atrybutow")
    m.add_argument("--plan-json", default="terraform/plan.json")
    m.add_argument("--projects", default="perimeter/projects.yaml")
    m.add_argument("--alerting", default="perimeter/alerting.yaml",
                   help="stad bierze sie sekcja `violations_source` — wspolrzedne widokow sinka, z ktorych "
                        "licza sie metryki odmow i zmian konfiguracji. Brak sekcji = te metryki nie powstaja")
    m.add_argument("--history-days", type=int, default=30)
    m.add_argument("--teraz", type=int, default=None, help="epoch do testow")
    m.set_defaults(func=zmierz)

    p = pod.add_parser("publish", help="zapisz metryki (konto z timeSeries.create)")
    p.add_argument("--input", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--only", default=None, help="opublikuj tylko metryki o tej koncowce nazwy")
    p.set_defaults(func=opublikuj)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
