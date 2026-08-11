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


def procenty_budzetu(deklaracje: dict, budzet_json: dict) -> dict:
    """{'spec': %, 'status': %} — OSOBNO, bo limit 6000 jest NA KONFIGURACJE, nie laczny.

    Mapowanie nazw jest tu jawne, bo dwa slowniki opisuja to samo dwoma jezykami: `attribute_budget.py`
    mowi `dry_run`/`enforced` (etapy czlonka), a API ACM `spec`/`status` (pola obiektu). Alert i runbook
    mowia jezykiem API — operator patrzy na `perimeters describe`, nie na nasz raport.
    """
    limit = deklaracje["policy"]["attribute_budget"]["limit_per_config"]
    return {
        "spec": round(100.0 * budzet_json["dry_run"] / limit, 3),
        "status": round(100.0 * budzet_json["enforced"] / limit, 3),
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

    deklaracje = json.load(open(args.declarations))
    budzet = json.load(open(args.budget))
    procenty = procenty_budzetu(deklaracje, budzet)

    historia = historia_procentow(args.project, g_token, args.history_days, teraz) if g_token else \
        {"spec": [], "status": []}
    prognoza = {k: round(dni_do_sciany(historia[k], procenty[k]), 2) for k in procenty}

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
            for c in ("spec", "status")
        ] + [
            punkt(METRYKI["budzet_dni"], prognoza[c], {"config": c}, args.project, teraz, False)
            for c in ("spec", "status")
        ],
        # Czytelne podsumowanie dla `$GITHUB_STEP_SUMMARY` — to jest DOWOD, ze producent liczy realne
        # wartosci, niezalezny od tego, czy alert akurat odpalil.
        "podsumowanie": {
            "apply_pending_seconds": zaleganie,
            "attribute_budget_percent": procenty,
            "attribute_budget_days_to_limit": prognoza,
            "drift_resources": dryf,
            "members_expired": wygasli,
            "punktow_historii": {k: len(v) for k, v in historia.items()},
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
    m.add_argument("--budget", default="budget.json")
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
