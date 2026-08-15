#!/usr/bin/env python3
"""Czy piny akcji w MATERIALE WYCHODZACYM sa aktualne wobec wydan upstreamu.

PO CO TO ISTNIEJE. Dependabot czyta `.github/workflows/*.yml` i pliki `action.yml`. Material szablonowy
lezy w `template/**/*.yml.example` i w `examples/**` — czyli POZA jego zasiegiem. Skutek jest zmierzony
i jednokierunkowy: piny w szablonie zostaja na wartosci z dnia, w ktorym plik powstal, a przy najblizszej
synchronizacji WRACAJA do wdrozenia, takze wtedy, gdy Dependabot juz je stamtad wycofal. Jeden pomiar:
plik przyniesiony szablonem cofnal w jednym wdrozeniu `actions/checkout` o TRZY wersje glowne, przy
zielonych bramkach (DEC-53).

Ani `groups`, ani `ignore` w `dependabot.yml` tego nie naprawia — to problem WIDOCZNOSCI SCIEZKI, nie
polityki grupowania. `ignore` byloby wrecz szkodliwe: zamrozilo by wdrozenie na starszym pinie szablonu.
Dlatego mechanizm jest osobny i pyta upstream wprost.

TRZY ROZNE PYTANIA, TRZY ROZNE MECHANIZMY — nie mieszaj ich:
  * „czy komentarz wersji KLAMIE"          -> `rozjazdy_pinow` w selftescie (ten sam tag, dwa SHA-e);
  * „czy material jest JEDNORODNY"          -> `rozjazdy_wersji` w selftescie (jedna akcja, dwie wersje);
  * „czy material jest AKTUALNY"            -> TEN plik (material kontra wydania upstreamu).
Pierwsze dwa dzialaja offline i sa bramkami PR-a. Trzeci wymaga sieci i jest przebiegiem cyklicznym,
bo „upstream wydal nowa wersje" nie jest wina autora pull requesta.

POWIERZCHNIA JEST TA SAMA, CO U BRAMKI JEDNORODNOSCI, i to jest celowe: material rozpakowany przez
`install.sh` plus `.github/actions/` i `examples/` startera (dwie drogi, ktorymi pin trafia na cudzy
runner bez przechodzenia przez `install.sh`). Gdyby te dwa zbiory sie rozjechaly, jeden mechanizm
pilnowalby czegos, czego drugi nie widzi.

FAIL-CLOSED. Akcja, dla ktorej nie da sie odczytac najnowszego wydania, jest BLEDEM (kod 2), a nie
„aktualna". Odwrotna domyslnosc zamienilaby ten skrypt w wylacznik uruchamiany awaria sieci — dokladnie
ta klasa, ktora ten stos tropi: kontrola zielona z powodu, ktorego nie deklaruje.

KODY WYJSCIA: 0 = aktualne · 1 = sa zaleglosci · 2 = nie udalo sie rozstrzygnac (blad wejscia albo API).

    python3 selftest/piny_szablonu.py [--json] [--self-test]
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
STARTER = HERE.parent

# Ten sam wzorzec, co w selftescie. Swiadomie NIE importujemy go stamtad: selftest przy imporcie rozpakowuje
# szablony do katalogu tymczasowego, a ten skrypt ma dzialac takze bez terraforma i conftesta na PATH.
PIN = re.compile(r"uses:\s*(?P<akcja>[\w.-]+/[\w./-]+)@(?P<sha>[0-9a-f]{40})\s*#\s*(?P<tag>v[\w.-]+)")

# Katalogi startera, ktorych tresc trafia na cudzy runner BEZ przechodzenia przez `install.sh`.
# `selftest/` i `.github/workflows/` startera sa poza zbiorem z tych samych powodow, co w `zrodla_wychodzace`.
KATALOGI_STARTERA = (".github/actions", "examples")


def material(rozpakowane: pathlib.Path | None) -> dict[str, dict[str, str]]:
    """{akcja: {sha: tag}} z calego materialu wychodzacego."""
    zrodla: list[tuple[str, pathlib.Path]] = []
    if rozpakowane is not None:
        zrodla += [("rozpakowane", p) for p in sorted(rozpakowane.rglob("*"))]
    else:
        # Bez rozpakowania czytamy `template/` wprost — ta sama tresc, inne nazwy plikow.
        zrodla += [("template", p) for p in sorted((STARTER / "template").rglob("*"))]
    for katalog in KATALOGI_STARTERA:
        zrodla += [("starter", p) for p in sorted((STARTER / katalog).rglob("*"))]

    out: dict[str, dict[str, str]] = {}
    for _, p in zrodla:
        if not p.is_file() or ".git" in p.parts:
            continue
        try:
            tresc = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for m in PIN.finditer(tresc):
            out.setdefault(m.group("akcja"), {})[m.group("sha")] = m.group("tag")
    return out


def api(sciezka: str) -> dict | list:
    req = urllib.request.Request(
        f"https://api.github.com{sciezka}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "vpcsc-piny-szablonu"},
    )
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def najnowsze(akcja: str) -> tuple[str, str]:
    """(tag, sha commita) najnowszego wydania. Rzuca, gdy nie da sie rozstrzygnac — fail-closed."""
    wyd = api(f"/repos/{akcja}/releases/latest")
    tag = wyd["tag_name"]                                   # type: ignore[index]
    ref = api("/repos/%s/git/ref/tags/%s" % (akcja, urllib.parse.quote(tag, safe="")))
    obiekt = ref["object"]                                  # type: ignore[index]
    if obiekt["type"] == "tag":                             # tag anotowany — rozwin do commita
        obiekt = api(f"/repos/{akcja}/git/tags/{obiekt['sha']}")["object"]  # type: ignore[index]
    return tag, obiekt["sha"]


def sprawdz(rozpakowane: pathlib.Path | None) -> tuple[list[dict], list[str]]:
    zalegle, bledy = [], []
    for akcja, po_sha in sorted(material(rozpakowane).items()):
        if len(po_sha) > 1:
            # Niejednorodnosc jest pytaniem innej bramki; tutaj nie da sie powiedziec „ktora wersja zalega".
            bledy.append(f"{akcja}: material niejednorodny ({', '.join(sorted(po_sha.values()))}) "
                         f"— to lapie `rozjazdy_wersji` w selftescie, nie ten skrypt")
            continue
        sha, tag = next(iter(po_sha.items()))
        try:
            nowy_tag, nowy_sha = najnowsze(akcja)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, TimeoutError) as e:
            bledy.append(f"{akcja}: nie odczytano najnowszego wydania ({type(e).__name__}: {e})")
            continue
        if nowy_sha != sha:
            zalegle.append({"akcja": akcja, "mamy": tag, "mamy_sha": sha,
                            "najnowsze": nowy_tag, "najnowsze_sha": nowy_sha})
    return zalegle, bledy


def self_test() -> int:
    """Bramka, ktora nie umie zaplonac, cicho przepuszcza — wiec sprawdzamy, ze umie."""
    ok = True

    def chk(nazwa: str, warunek: bool, detal: str = "") -> None:
        nonlocal ok
        ok &= warunek
        print(f"  {'ok  ' if warunek else 'BLAD'} self-test: {nazwa}" + (f" — {detal}" if detal else ""))

    znalezione = material(None)
    chk("skan widzi material szablonu", len(znalezione) >= 6, f"akcji: {len(znalezione)}")
    chk("skan siega poza `template/` (akcja `contrib`, `examples/`)",
        any((STARTER / k).exists() for k in KATALOGI_STARTERA)
        and bool(PIN.search((STARTER / ".github/actions/contrib/action.yml").read_text())),
        "akcja `contrib` musi niesc pin")
    chk("wzorzec odrzuca pin BEZ komentarza wersji",
        PIN.search("uses: a/b@" + "0" * 40) is None)
    chk("wzorzec odrzuca tag zamiast SHA",
        PIN.search("uses: a/b@v4 # v4") is None)
    m = PIN.search("      - uses: a/b@" + "1" * 40 + " # v9.9.9")
    chk("wzorzec czyta akcje, sha i tag", bool(m) and m.group("tag") == "v9.9.9")
    return 0 if ok else 2


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    rozpakowane = None
    if "--rozpakuj" in sys.argv:
        import tempfile
        rozpakowane = pathlib.Path(tempfile.mkdtemp(prefix="vpcsc-piny-"))
        subprocess.run(["bash", str(STARTER / "install.sh"), str(rozpakowane)],
                       check=True, capture_output=True)

    zalegle, bledy = sprawdz(rozpakowane)

    if "--json" in sys.argv:
        print(json.dumps({"zalegle": zalegle, "bledy": bledy}, indent=2, ensure_ascii=False))
    else:
        for b in bledy:
            print(f"BLAD  {b}")
        for z in zalegle:
            print(f"ZALEGA  {z['akcja']}: material {z['mamy']} -> upstream {z['najnowsze']} "
                  f"({z['najnowsze_sha']})")
        if not zalegle and not bledy:
            print("OK — material szablonu jest na najnowszych wydaniach wszystkich uzywanych akcji")

    if bledy:
        return 2
    return 1 if zalegle else 0


if __name__ == "__main__":
    sys.exit(main())
