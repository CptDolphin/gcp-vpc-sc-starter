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
}

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
                       powod_zalegania: str) -> tuple[str, str] | None:
    """`(poziom, tresc)` dla adnotacji o rozjezdzie zywej granicy z deklaracja. `None`, gdy liczby rowne.

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

    POZIOM ADNOTACJI ROZNI SIE CELOWO, ale ZADEN z wariantow nie wywraca joba: obserwator, ktory pada
    wtedy, gdy jest co zglosic, jest gorszy niz jego brak (ta sama zasada co `|| true` przy budzecie
    w `watch.yml`). `::error::` jest tu wylacznie po to, zeby na LISCIE przebiegow dalo sie odroznic
    „czeka na apply" od „granica rozjechala sie z Gitem" bez wchodzenia w log.
    """
    if zywe == zadeklarowane:
        return None
    roznica = zywe - zadeklarowane
    wspolne = (f"budzet {nazwa}: granica ma {zywe} atrybutow, deklaracja opisuje {zadeklarowane} "
               f"(roznica {roznica:+d})")
    if apply_zalega:
        return "warning", (
            f"{wspolne} — apply ZALEGA ({powod_zalegania}), wiec ta roznica jest OCZEKIWANA i zniknie po "
            f"udanym apply. To NIE jest dryf: `drift_resources` jest w tym przebiegu celowo 0, a alert "
            f"o dryfie milczy. Sprawdzaj HISTORIE PRZEBIEGOW APPLY, nie granice; jesli zaleganie przekroczy "
            f"`apply_pending_seconds`, odezwie sie alert `apply`.")
    return "error", (
        f"{wspolne}, a apply NIE zalega ({powod_zalegania}) — Git i chmura powinny byc zgodne. Albo ktos "
        f"zmienil granice poza pipelinem (patrz alert o dryfie), albo model w `attribute_budget.py` przelicza "
        f"koszt inaczej, niz renderuje sie na ACM. Rozstrzyga porownanie REGULA PO REGULE, nie samych sum: "
        f"docs/7-alerty.md#rozjazd-granicy-z-deklaracja")


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


def pobierz_perimetr(policy_id: str, nazwa: str, token: str) -> dict:
    """Zywa konfiguracja granicy z Access Context Managera. Konto planu ma do tego `policyReader`."""
    return _http(f"https://accesscontextmanager.googleapis.com/v1/accessPolicies/{policy_id}"
                 f"/servicePerimeters/{nazwa}", token)


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
                poziom, tresc = komunikat
                print(f"::{poziom}::{tresc}", file=sys.stderr)

    plan = json.load(open(args.plan_json)) if os.path.exists(args.plan_json) else {}
    dryf = dryf_z_planu(plan, zaleganie > 0)

    projects_doc = yaml.safe_load(open(args.projects))
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
        ],
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
        },
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
