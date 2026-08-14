#!/usr/bin/env python3
"""Filtr `paths:` workflowa MUSI pokrywać pliki, które ten workflow naprawdę czyta.

PO CO. Bramka, która nie odpala się na zmianę pliku definiującego tę bramkę, jest bramką tylko
z nazwy. W tym repozytorium ten sam błąd popełniono PIĘĆ razy pod rząd (§9.45 runbooka: `iam-bootstrap/**`,
`contrib/**`+`tools/**`, `.github/actions/**`, `violations-sink/**`, `docs/**`+`.starter-sync`) i za każdym
razem wykryto go tym samym komunikatem — `no checks reported on the branch` — czyli PO fakcie, ręcznie,
na cudzym pull requeście. Za każdym razem lekarstwem było dopisanie jednej linii do listy. Lista nazw
utrzymywana ręcznie obok mechanizmu, który z niej korzysta, nie przestaje się rozjeżdżać od tego, że
poprawiono ją po raz piąty.

CO ROBI INACZEJ. Nie ma tu listy plików do pilnowania. Zbiór wejść liczy się ZA KAŻDYM URUCHOMIENIEM
z drzewa: `git ls-files` daje pliki śledzone, a przez tekst wykonywalny workflowa (ciała `run:`, wartości
`uses:`/`with:`, przechodnio przez akcje lokalne `./.github/actions/*`) sprawdzamy, które z nich ten
workflow realnie czyta. Nowe narzędzie dopisane do `tools/` i zawołane z akcji jest objęte tą bramką
w tym samym commicie, w którym powstało — bez pamiętania o czymkolwiek.

CZEGO NIE ROBI. Nie zgaduje ścieżek budowanych dynamicznie w kodzie (sklejanych ze zmiennej): dla nich
tekst workflowa nie zawiera nazwy pliku i żadna analiza statyczna jej nie zobaczy. Takie wejścia trzeba
zadeklarować ręcznie w `.github/paths-pokrycie.yaml` — i właśnie dlatego ten plik jest bramką porównującą
deklarację ze źródłem, a nie zwykłą listą wyjątków (patrz `sprawdz_deklaracje`).

FAIL-CLOSED. Zero workflowów z `paths:`, zero wyliczonych wejść dla workflowa, który `paths:` ma, brak
odpowiedzi z `git ls-files`, wyjątek bez powodu i wyjątek NIEAKTUALNY (ścieżka już pokryta albo już
nieczytana) — wszystko to jest czerwone. Bramka bez wsadu przechodzi każdy test pozytywny, więc brak
wsadu musi być błędem, a nie ciszą.
"""
import json
import pathlib
import re
import subprocess
import sys

import yaml

KATALOG_WORKFLOWOW = pathlib.Path(".github/workflows")
DEKLARACJA = pathlib.Path(".github/paths-pokrycie.yaml")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Matcher `paths:` GitHuba
# ─────────────────────────────────────────────────────────────────────────────
def na_regex(wzorzec):
    """Tłumaczy wzorzec `paths:` GitHuba na wyrażenie regularne.

    Reguły, których trzymamy się świadomie (dokumentacja GitHuba, sekcja o filtrach ścieżek):
    `*` obejmuje dowolne znaki OPRÓCZ `/`, `**` obejmuje także `/`, `?` to jeden znak poza `/`.
    W przeciwieństwie do globa powłoki wzorce GitHuba łapią też pliki-kropki — dlatego NIE robimy
    tu wyjątku na wiodącą kropkę; `.tflint.hcl` ma być łapane przez `**` i jest.
    """
    wynik = []
    i = 0
    while i < len(wzorzec):
        if wzorzec.startswith("**", i):
            wynik.append(".*")
            i += 2
        elif wzorzec[i] == "*":
            wynik.append("[^/]*")
            i += 1
        elif wzorzec[i] == "?":
            wynik.append("[^/]")
            i += 1
        else:
            wynik.append(re.escape(wzorzec[i]))
            i += 1
    return re.compile("^" + "".join(wynik) + "$")


def pokryty(sciezka, wzorce):
    """Czy `paths:` łapie plik. Wzorzec z `!` odejmuje, zgodnie z semantyką GitHuba."""
    trafiony = False
    for w in wzorce:
        neg = w.startswith("!")
        if na_regex(w[1:] if neg else w).match(sciezka):
            trafiony = not neg
    return trafiony


# ─────────────────────────────────────────────────────────────────────────────
# 2. Drzewo — jedyne źródło zbioru plików
# ─────────────────────────────────────────────────────────────────────────────
def drzewo():
    r = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"::error::`git ls-files` nie odpowiedziało (rc={r.returncode}) — "
                         "bramka nie ma z czego wyliczyć zbioru wejść i dlatego NIE przepuszcza")
    pliki = [p for p in r.stdout.split("\0") if p]
    if not pliki:
        raise SystemExit("::error::`git ls-files` zwróciło pustą listę — puste drzewo nie jest "
                         "sytuacją, w której 'nie ma czego sprawdzać'")
    return pliki


# ─────────────────────────────────────────────────────────────────────────────
# 3. Tekst WYKONYWALNY workflowa (przechodnio przez akcje lokalne)
# ─────────────────────────────────────────────────────────────────────────────
ADNOTACJA = re.compile(r"::(error|warning|notice|debug)::")
DOCSTRING = re.compile(r'"""(?:.|\n)*?"""' + r"|'''(?:.|\n)*?'''")


def bez_komentarzy(tekst):
    """Odsiewa to, co CYTUJE ścieżkę, zamiast ją czytać.

    Trzy źródła fałszywych trafień, wszystkie zmierzone na tym drzewie:
      * komentarze — nagłówki w tym repo opisują ścieżki słownie („patrz tools/x.py");
      * docstringi — narzędzia w `tools/` zaczynają się od kilkunastu linii prozy, która cytuje
        ścieżki dokładnie tak samo jak komentarz, tylko w potrójnym cudzysłowie;
      * treść adnotacji `::error::`/`::warning::` — komunikat dla człowieka potrafi wymienić plik,
        którego krok w ogóle nie otwiera.
    Wszystko to zawyżałoby zbiór wejść, a bramka żądająca ścieżki dla pliku, którego nikt nie
    uruchamia, uczy zespołu dopisywania wyjątków — czyli psuje sama siebie.
    """
    tekst = DOCSTRING.sub("", tekst)
    return "\n".join(l for l in tekst.splitlines()
                     if not l.strip().startswith("#") and not ADNOTACJA.search(l))


def zbierz_kroki(obiekt, kroki):
    """Wyławia listy `steps` z dowolnego poziomu zagnieżdżenia (workflow ma je w `jobs`,
    akcja złożona w `runs`)."""
    if isinstance(obiekt, dict):
        for k, v in obiekt.items():
            if k == "steps" and isinstance(v, list):
                kroki.extend(x for x in v if isinstance(x, dict))
            else:
                zbierz_kroki(v, kroki)
    elif isinstance(obiekt, list):
        for v in obiekt:
            zbierz_kroki(v, kroki)


def tekst_wykonywalny(sciezka_yaml, odwiedzone):
    """Skleja to, co w danym pliku REALNIE się wykonuje, i schodzi do akcji lokalnych."""
    sciezka_yaml = str(sciezka_yaml)
    if sciezka_yaml in odwiedzone or not pathlib.Path(sciezka_yaml).exists():
        return "", []
    odwiedzone.add(sciezka_yaml)
    dane = yaml.safe_load(pathlib.Path(sciezka_yaml).read_text(encoding="utf-8"))
    kroki = []
    zbierz_kroki(dane, kroki)

    czesci, akcje = [], []
    for k in kroki:
        if k.get("run"):
            czesci.append(bez_komentarzy(str(k["run"])))
        uses = str(k.get("uses") or "")
        if uses:
            czesci.append(uses)
        if isinstance(k.get("with"), dict):
            czesci.append(yaml.safe_dump(k["with"], allow_unicode=True))
        if uses.startswith("./"):
            akcje.append(uses[2:].rstrip("/"))

    for a in akcje:
        for kandydat in (f"{a}/action.yml", f"{a}/action.yaml"):
            if pathlib.Path(kandydat).exists():
                podtekst, podakcje = tekst_wykonywalny(kandydat, odwiedzone)
                czesci.append(podtekst)
                akcje.extend(podakcje)
                break
    return "\n".join(czesci), akcje


# ─────────────────────────────────────────────────────────────────────────────
# 4. Które pliki z drzewa ten workflow czyta
# ─────────────────────────────────────────────────────────────────────────────
GLOB_W_KODZIE = [
    # pathlib.Path("terraform").glob("*.tf")
    re.compile(r'Path\(\s*["\']([\w./-]+)["\']\s*\)\s*\.glob\(\s*["\']([^"\']+)["\']'),
    # glob.glob("terraform/*.tf") albo shellowe terraform/*.tf
    re.compile(r'["\'\s(]([\w./-]+/\*[\w.*]*)["\'\s)]'),
]


SKRYPTY = (".py", ".sh", ".bash")


def _z_tekstu(tekst, pliki, czytane, skad):
    """Dopisuje do `czytane` pliki z drzewa, do których ten kawałek tekstu się odwołuje."""
    nowe = []
    for p in pliki:
        if p in tekst and p not in czytane:
            czytane[p] = skad
            nowe.append(p)
    for rx in GLOB_W_KODZIE:
        for m in rx.finditer(tekst):
            wzor = "/".join(g for g in m.groups() if g) if len(m.groups()) > 1 else m.group(1)
            rx_wzor = na_regex(wzor)
            for p in pliki:
                if rx_wzor.match(p) and p not in czytane:
                    czytane[p] = f"glob `{wzor}` ({skad})"
                    nowe.append(p)
    return nowe


def czytane_pliki(tekst, akcje, pliki):
    """Zbiór plików z DRZEWA, do których ten workflow się odwołuje — przechodnio.

    Cztery drogi, wszystkie liczone z `pliki` (czyli z `git ls-files`), żadna z listy nazw:
      (a) ścieżka pliku pada w tekście wykonywalnym dosłownie,
      (b) plik leży pod akcją lokalną, którą workflow woła przez `uses: ./…`,
      (c) plik pasuje do globa padającego w kodzie (`Path("terraform").glob("*.tf")`),
      (d) PRZECHODNIO: plik, do którego odwołuje się URUCHAMIANY skrypt.

    Punkt (d) jest tym, co odróżnia tę bramkę od czytania samych workflowów. Wejścia, które
    zgłoszenie #2077 wskazało jako niepokryte — `.github/CODEOWNERS` (wsad `codeowners_check.py`)
    i `tests/*.json` (wsad `snow_symulator_kontrakt.py`) — NIE padają w żadnym workflowie ani akcji.
    Padają w kodzie narzędzia, które workflow uruchamia. Bramka pytająca tylko o YAML-e nie
    zobaczyłaby ich i zameldowałaby spokój — czyli powtórzyłaby dokładnie ten błąd, który tropi.
    Iterujemy do punktu stałego, bo skrypt może uruchamiać kolejny skrypt.
    """
    czytane = {}
    do_przejrzenia = _z_tekstu(tekst, pliki, czytane, "odwołanie w workflow/akcji")
    for a in akcje:
        for p in pliki:
            if p.startswith(a + "/") and p not in czytane:
                czytane[p] = f"ciało akcji lokalnej `{a}`"
                do_przejrzenia.append(p)

    while do_przejrzenia:
        p = do_przejrzenia.pop()
        if not p.endswith(SKRYPTY):
            continue
        plik = pathlib.Path(p)
        if not plik.exists():
            continue
        do_przejrzenia += _z_tekstu(bez_komentarzy(plik.read_text(encoding="utf-8", errors="replace")),
                                    pliki, czytane, f"wsad skryptu `{p}`")
    return czytane


# ─────────────────────────────────────────────────────────────────────────────
# 5. Deklaracja wyjątków — porównywana ze źródłem, nie przyjmowana na słowo
# ─────────────────────────────────────────────────────────────────────────────
def wczytaj_deklaracje():
    if not DEKLARACJA.exists():
        return []
    dane = yaml.safe_load(DEKLARACJA.read_text(encoding="utf-8")) or {}
    return dane.get("pominiete") or []


def sprawdz_deklaracje(pominiete, luki_wszystkie):
    """Wyjątek musi być UZASADNIONY i AKTUALNY.

    Nieaktualny wyjątek (ścieżka już pokryta albo już nieczytana) jest tym samym długiem, co lista,
    którą ta bramka zastępuje: deklaracją, której nikt nie skonfrontował ze źródłem. Dlatego stary
    wpis jest czerwony — inaczej plik wyjątków rósłby w nieskończoność i po roku byłby obejściem.
    """
    bledy, uzasadnione = [], set()
    for i, w in enumerate(pominiete):
        if not isinstance(w, dict):
            bledy.append(f"pominiete[{i}]: wpis nie jest mapą `workflow`/`sciezka`/`powod`")
            continue
        wf, sc, powod = w.get("workflow"), w.get("sciezka"), (w.get("powod") or "").strip()
        if not wf or not sc:
            bledy.append(f"pominiete[{i}]: brakuje `workflow` albo `sciezka`")
            continue
        if len(powod) < 20:
            bledy.append(f"pominiete[{i}] ({wf} / {sc}): `powod` jest pusty albo zdawkowy — "
                         "wyjątek bez zapisanego powodu jest obejściem bramki, nie decyzją")
            continue
        if (wf, sc) not in luki_wszystkie:
            bledy.append(f"pominiete[{i}] ({wf} / {sc}): NIEAKTUALNY — ta ścieżka jest już pokryta "
                         "przez `paths:` albo nie jest już czytana. Zdejmij wpis.")
            continue
        uzasadnione.add((wf, sc))
    return bledy, uzasadnione


# ─────────────────────────────────────────────────────────────────────────────
def analizuj():
    pliki = drzewo()
    if not KATALOG_WORKFLOWOW.is_dir():
        raise SystemExit(f"::error::brak {KATALOG_WORKFLOWOW} — bramka nie ma czego sprawdzić")

    raport, bledy = {}, []
    z_filtrem = 0
    for wf in sorted(KATALOG_WORKFLOWOW.glob("*.yml")) + sorted(KATALOG_WORKFLOWOW.glob("*.yaml")):
        dane = yaml.safe_load(wf.read_text(encoding="utf-8"))
        # `on:` w YAML-u 1.1 wczytuje się jako True — to nie jest ciekawostka, tylko powód,
        # dla którego naiwne `dane["on"]` w tej rodzinie skryptów zwraca KeyError.
        on = dane.get(True, dane.get("on"))
        if not isinstance(on, dict):
            continue
        wzorce = {ev: cfg["paths"] for ev, cfg in on.items()
                  if isinstance(cfg, dict) and cfg.get("paths")}
        if not wzorce:
            continue
        z_filtrem += 1
        tekst, akcje = tekst_wykonywalny(wf, set())
        czytane = czytane_pliki(tekst, akcje, pliki)
        # Sam plik workflowa jest swoim własnym wejściem: jego zmiana zmienia to, co się wykona.
        czytane.setdefault(str(wf), "definicja samego workflowa")
        if not czytane:
            bledy.append(f"{wf.name}: ma filtr `paths:`, a bramka nie wyliczyła ANI JEDNEGO "
                         "czytanego pliku — zmienił się kształt workflowa i ta analiza mierzy pustkę")
        wszystkie = sorted({w for lista in wzorce.values() for w in lista})
        luki = {p: powod for p, powod in sorted(czytane.items()) if not pokryty(p, wszystkie)}
        raport[wf.name] = {"wzorce": wszystkie, "czytane": len(czytane), "luki": luki}

    if z_filtrem == 0:
        bledy.append("żaden workflow nie ma filtru `paths:` — albo zniknęły, albo zmienił się "
                     "kształt pliku i ta bramka przestała cokolwiek widzieć")
    return raport, bledy


def self_test():
    """Bramka, która nigdy nie odrzuca, przechodzi każdy test pozytywny — więc mierzymy OBA kierunki.

    Sam matcher jest tu przedmiotem testu na równi z logiką: gdyby `na_regex` łapało za dużo, bramka
    meldowałaby pełne pokrycie przy pustym filtrze i byłaby gorsza niż jej brak.
    """
    zle = 0

    def sprawdz(nazwa, warunek):
        nonlocal zle
        print(f"  {'ok ' if warunek else 'ZLE'} self-test: {nazwa}")
        zle += not warunek

    # ── matcher ──────────────────────────────────────────────────────────────
    sprawdz("`**` przechodzi przez ukośnik", pokryty("a/b/c.txt", ["a/**"]))
    sprawdz("`*` NIE przechodzi przez ukośnik", not pokryty("a/b/c.txt", ["a/*"]))
    sprawdz("plik-korzeń nie wpada pod wzorzec katalogowy", not pokryty(".przyklad.hcl", ["docs/**"]))
    # Wzorce GitHuba łapią pliki-kropki — w globie powłoki `*` ich nie widzi i to jest realna pułapka
    # przy przenoszeniu wzorca „z pamięci o bashu".
    sprawdz("`**` łapie plik-kropkę w korzeniu", pokryty(".przyklad.hcl", ["**"]))
    sprawdz("dokładna ścieżka łapie sama siebie", pokryty("kat/PLIK", ["kat/PLIK"]))
    sprawdz("`!` odejmuje", not pokryty("docs/a.md", ["docs/**", "!docs/a.md"]))
    sprawdz("pusty filtr nie pokrywa niczego", not pokryty("a.txt", []))

    # ── odsiewanie cytatów ───────────────────────────────────────────────────
    sprawdz("komentarz nie liczy się jako odczyt",
            "tools/x.py" not in bez_komentarzy("# patrz tools/x.py"))
    sprawdz("treść adnotacji nie liczy się jako odczyt",
            "tools/x.py" not in bez_komentarzy('echo "::error::sprawdz tools/x.py"'))
    sprawdz("zwykłe wywołanie liczy się jako odczyt",
            "tools/x.py" in bez_komentarzy("python3 tools/x.py"))

    # ── deklaracja wyjątków: fail-closed w obie strony ───────────────────────
    luka = {("w.yml", "a/b.txt")}
    bledy, uzasadnione = sprawdz_deklaracje(
        [{"workflow": "w.yml", "sciezka": "a/b.txt", "powod": "powód dostatecznie długi, by coś znaczyć"}], luka)
    sprawdz("wyjątek z powodem i aktualny — przechodzi", not bledy and uzasadnione == luka)
    bledy, _ = sprawdz_deklaracje([{"workflow": "w.yml", "sciezka": "a/b.txt", "powod": "bo tak"}], luka)
    sprawdz("wyjątek ze zdawkowym powodem — czerwony", len(bledy) == 1)
    bledy, _ = sprawdz_deklaracje([{"workflow": "w.yml", "sciezka": "a/b.txt"}], luka)
    sprawdz("wyjątek bez powodu — czerwony", len(bledy) == 1)
    bledy, _ = sprawdz_deklaracje(
        [{"workflow": "w.yml", "sciezka": "juz/pokryte.txt", "powod": "powód dostatecznie długi, by coś znaczyć"}], luka)
    sprawdz("wyjątek NIEAKTUALNY — czerwony", len(bledy) == 1)
    bledy, _ = sprawdz_deklaracje(["nie-mapa"], luka)
    sprawdz("wpis o złym kształcie — czerwony", len(bledy) == 1)

    return zle


def main():
    if "--self-test" in sys.argv[1:]:
        return 1 if self_test() else 0
    tylko_raport = "--raport" in sys.argv[1:]
    raport, bledy = analizuj()

    luki_wszystkie = {(wf, p) for wf, r in raport.items() for p in r["luki"]}
    bledy_dekl, uzasadnione = sprawdz_deklaracje(wczytaj_deklaracje(), luki_wszystkie)
    bledy += bledy_dekl

    if tylko_raport:
        print(json.dumps({wf: {**r, "luki": sorted(r["luki"])} for wf, r in raport.items()},
                         indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    nieuzasadnione = 0
    for wf in sorted(raport):
        r = raport[wf]
        otwarte = {p: powod for p, powod in r["luki"].items() if (wf, p) not in uzasadnione}
        stan = "LUKA" if otwarte else "ok  "
        print(f"{stan} {wf}: {r['czytane']} czytanych wejść, "
              f"{len(r['wzorce'])} wzorców, {len(r['luki'])} poza filtrem "
              f"({len(r['luki']) - len(otwarte)} z zapisanym powodem)")
        for p, powod in otwarte.items():
            nieuzasadnione += 1
            print(f"       - {p}  ({powod})")

    for b in bledy:
        print(f"::error::{b}")
    if nieuzasadnione:
        print(f"::error::{nieuzasadnione} wejść bramek leży poza filtrem `paths:` workflowa, który "
              "je czyta. Pull request dotykający wyłącznie takiego pliku dostaje "
              "„no checks reported on the branch" + "”"
              " — czyli zmiana definicji bramki wchodzi bez ani jednego czerwonego światła. "
              "Rozszerz `paths:` albo zapisz powód w .github/paths-pokrycie.yaml.")
    return 1 if (bledy or nieuzasadnione) else 0


if __name__ == "__main__":
    sys.exit(main())
