#!/usr/bin/env python3
"""Kontrakt kanalu ticketowego zmierzony na SYMULATORZE — a nie na fixturze, ktory go potwierdza.

CO TO ZA PLIK. `tools/snow_symulator.py` jest bezwartosciowy, dopoki ktos nie pokaze, ze LAMIE nasze
zalozenia. Ten harness jest tym pokazaniem: uruchamia symulator na petli zwrotnej i pyta go tak, jak
pytal kod PRZED naprawa (#2046) oraz tak, jak pyta dzisiaj — na TYM SAMYM serwerze i TYM SAMYM
rekordzie. Stare zapytanie ma nie dostac pola, na ktorym stal werdykt. Nowe ma je dostac. Para, nie
pojedynczy przebieg: kontrola odrzucajaca wszystko przechodzi kazdy test negatywny i nie chroni niczego.

DLACZEGO TO NIE JEST DRUGI FIXTURE. Fixture jest ODPOWIEDZIA, ktora sami napisalismy — odpowiada wiec
na zapytanie, ktore sobie wyobrazilismy, i nie umie zaprzeczyc. Symulator jest KONTRAKTEM: dostaje
zapytanie i buduje odpowiedz wedlug reguly platformy. Dlatego zapytanie niesprawne dostaje tu
odpowiedz niesprawna, a fixture dawal na nie odpowiedz idealna.

CZEGO TEN HARNESS NIE DOWODZI — to samo, czego nie dowodzi symulator: nazw pol wlasnych organizacji
docelowej (`u_*`), jej przeplywu approvali i wersji jej API. Pelna lista w naglowku
`tools/snow_symulator.py` i w `docs/5-servicenow-intake.md` §9. Zielony wynik TUTAJ nie jest
gotowoscia produkcyjna; prerekwizytem zostaje jeden odczyt z instancji docelowej (§8.4).

Uruchomienie:  python3 tools/snow_symulator_kontrakt.py
"""
import base64
import importlib.util
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
UZYTKOWNIK, HASLO = "symulator-user", "symulator-token"
PROJEKT = "prj-x-test"
APPROVER = "net-approver@example.com"
# Ten sam zatwierdzajacy, co w selftescie: ROZNI sie od wnioskodawcy w RITM0000001 i ZGADZA z tym
# w RITM0000003, wiec jedna stala daje pare anty-tautologiczna szostej kontroli.

wyniki = []


def check(nazwa: str, warunek: bool, detal: str = ""):
    wyniki.append(bool(warunek))
    print(f"{'OK  ' if warunek else 'FAIL'} {nazwa}")
    if not warunek and detal:
        print(f"       {detal[:600]}")


def zaladuj(nazwa: str):
    spec = importlib.util.spec_from_file_location(nazwa, ROOT / "tools" / f"{nazwa}.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def get(url: str, uzytkownik: str = UZYTKOWNIK, haslo: str = HASLO, naglowek: bool = True):
    """Surowe GET — zwraca (kod, cialo, naglowki). Poswiadczenie wysylamy z gory, zeby dalo sie
    zmierzyc TAKZE przypadek bez niego (`naglowek=False`), ktorego opener z retry by nie pokazal."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if naglowek:
        klucz = base64.b64encode(f"{uzytkownik}:{haslo}".encode()).decode()
        req.add_header("Authorization", f"Basic {klucz}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}"), dict(exc.headers)


def verify_py(*argv, srodowisko_bazy: str | None = None):
    import os
    env = dict(os.environ)
    if srodowisko_bazy:
        env.update({"SNOW_INSTANCE": srodowisko_bazy, "SNOW_USER": UZYTKOWNIK, "SNOW_TOKEN": HASLO})
    return subprocess.run([sys.executable, "tools/snow_verify.py", *argv], cwd=ROOT, env=env,
                          capture_output=True, text=True)


def main() -> int:
    symulator = zaladuj("snow_symulator")
    verify = zaladuj("snow_verify")
    dane = symulator.wczytaj_dane(str(ROOT / "tests/symulator-instancja.json"))

    with symulator.Serwer(dane, UZYTKOWNIK, HASLO) as serwer:
        baza = serwer.baza
        tabela = f"{baza}/api/now/table/sc_req_item"

        # ═══════════════════════════════════════════════════════════════════════════════════════
        # D1. DOWOD WIERNOSCI. Stare, NIESPRAWNE zapytanie kontra dzisiejsze — jeden serwer, jeden
        #     rekord. Bez tej pary symulator jest tylko kolejnym plikiem, ktory sie z nami zgadza.
        # ═══════════════════════════════════════════════════════════════════════════════════════
        stare = f"{tabela}?" + urllib.parse.urlencode({
            "sysparm_query": "number=RITM0000001", "sysparm_limit": "1"})   # ← bez `sysparm_fields`
        kod, cialo, _ = get(stare)
        wiersz_stary = (cialo.get("result") or [{}])[0]
        check("D1a stare zapytanie (bez sysparm_fields) NIE dostaje `assignment_group.name`",
              kod == 200 and "assignment_group.name" not in wiersz_stary, str(sorted(wiersz_stary))[:300])
        check("D1b …a referencja przychodzi jako obiekt {link, value} — dokladnie ten ksztalt, "
              "ktorego stary kod nie umial przeczytac",
              isinstance(wiersz_stary.get("assignment_group"), dict)
              and {"link", "value"} <= set(wiersz_stary.get("assignment_group", {})),
              str(wiersz_stary.get("assignment_group"))[:200])
        check("D1c …zaden klucz odpowiedzi nie zawiera kropki (dot-walk bez zamowienia NIE ISTNIEJE)",
              not [k for k in wiersz_stary if "." in k], str([k for k in wiersz_stary if "." in k]))
        problemy_stare = verify.verify(cialo, "RITM0000001", PROJEKT, APPROVER)
        check("D1d WERDYKT na starym zapytaniu: ODMOWA — na zywej instancji ta bramka odrzucilaby "
              "KAZDY ticket, a fixture swiecil zielono",
              any("grupy" in p for p in problemy_stare), str(problemy_stare)[:400])

        nowe = verify.url_odczytu(baza, "RITM0000001")
        kod, cialo_nowe, _ = get(nowe)
        wiersz_nowy = (cialo_nowe.get("result") or [{}])[0]
        check("D1e dzisiejsze zapytanie (z sysparm_fields) DOSTAJE `assignment_group.name` jako tekst",
              kod == 200 and wiersz_nowy.get("assignment_group.name") == "network-team",
              str(wiersz_nowy)[:300])
        check("D1f PARA ANTY-TAUTOLOGICZNA: ten sam serwer i rekord — stare zapytanie ODRZUCONE, "
              "dzisiejsze PRZECHODZI",
              problemy_stare and not verify.verify(cialo_nowe, "RITM0000001", PROJEKT, APPROVER),
              f"stare={problemy_stare} nowe={verify.verify(cialo_nowe, 'RITM0000001', PROJEKT, APPROVER)}")

        # D1g. Fixture obiecywal ksztalt, ktorego stare zapytanie NIGDY by nie dostalo — to jest
        #      zdanie z #2046 zamienione w asercje, a nie w akapit dokumentacji.
        fixture = json.loads((ROOT / "tests/snow-approved.json").read_text(encoding="utf-8"))
        klucze_fixture = {k for k in fixture["result"][0] if not k.startswith("_")}
        check("D1g fixture `snow-approved.json` obiecuje klucze, ktorych stare zapytanie nie dostaje",
              klucze_fixture - set(wiersz_stary) != set()
              and klucze_fixture <= set(wiersz_nowy) | {"state"},
              f"nieosiagalne starym zapytaniem: {sorted(klucze_fixture - set(wiersz_stary))}")

        # ═══════════════════════════════════════════════════════════════════════════════════════
        # D2. KONTRAKT §8.1 JEST ZRODLEM, SYMULATOR GO IMPLEMENTUJE. Rozjazd ma byc czerwony —
        #     w obie strony: kazde zamowione pole ma wrocic, i nic ponadto.
        # ═══════════════════════════════════════════════════════════════════════════════════════
        param = urllib.parse.parse_qs(urllib.parse.urlparse(nowe).query)
        check("D2a zapytanie ma dokladnie ksztalt z §8.1 (query + fields + limit, tabela sc_req_item)",
              param["sysparm_query"][0] == "number=RITM0000001"
              and param["sysparm_limit"][0] == "1"
              and "/api/now/table/sc_req_item" in nowe, nowe)
        zamowione = set(param["sysparm_fields"][0].split(","))
        check("D2b symulator odsyla KAZDE zamowione pole werdyktu (brak = check bylby slepy)",
              zamowione <= set(wiersz_nowy), f"brakuje: {sorted(zamowione - set(wiersz_nowy))}")
        check("D2c …i NIC ponad zamowione (odpowiedz szersza niz zamowienie ukrylaby brak pola)",
              set(wiersz_nowy) <= zamowione, f"nadmiar: {sorted(set(wiersz_nowy) - zamowione)}")

        # ═══════════════════════════════════════════════════════════════════════════════════════
        # D3/D4. KANAL PRZECIW SYMULATOROWI: pozytyw + PIEC negatywow, kazdy przez `snow_verify.py`
        #        jako podproces po HTTP — z uwierzytelnieniem, parsowaniem i kodem wyjscia.
        #        Werdykt ma pochodzic z TRESCI (nazwany powod), nie z samego kodu wyjscia.
        # ═══════════════════════════════════════════════════════════════════════════════════════
        p = verify_py("--ticket", "RITM0000001", "--expect-project", PROJEKT, "--approver", APPROVER,
                      srodowisko_bazy=baza)
        check("D4 POZYTYW e2e przez symulator: rc=0", p.returncode == 0, p.stdout + p.stderr)
        check("D4b …i werdykt SAM MOWI, ze pochodzi z symulatora (prefiks w kazdej linii)",
              "[SYMULATOR:" in p.stdout, p.stdout[:200])

        negatywy = [
            ("RITM0000009", PROJEKT, "ticket NIEISTNIEJACY", "nie istnieje"),
            ("RITM0000002", PROJEKT, "bez zatwierdzenia (approval w toku)", "stan="),
            ("RITM0000003", PROJEKT, "zatwierdzajacy == wnioskodawca", "samo-zatwierdzenie"),
            ("RITM0000004", PROJEKT, "grupa spoza allowlisty sieciowej", "wymagana grupa sieciowa"),
            ("RITM0000005", PROJEKT, "projekt spoza wniosku (podmiana celu)", "a dispatch prosi o"),
        ]
        for ticket, projekt, opis, fragment in negatywy:
            p = verify_py("--ticket", ticket, "--expect-project", projekt, "--approver", APPROVER,
                          srodowisko_bazy=baza)
            check(f"D3 NEGATYW e2e przez symulator — {opis}",
                  p.returncode != 0 and fragment in p.stderr,
                  f"rc={p.returncode}: {p.stderr[-300:]}")

        # ═══════════════════════════════════════════════════════════════════════════════════════
        # D5. UWIERZYTELNIENIE. Brak/zle poswiadczenie ma dac KOD, nie cicha pustke — bo pusty
        #     `result` znaczy w tym kanale „ticket nie istnieje", czyli 401 zamieniony na pustke
        #     jest odmowa z NIEPRAWDZIWYM powodem.
        # ═══════════════════════════════════════════════════════════════════════════════════════
        kod, cialo, naglowki = get(tabela, naglowek=False)
        check("D5a bez naglowka Authorization → 401 i cialo bledu, NIE pusty `result`",
              kod == 401 and "result" not in cialo and cialo.get("status") == "failure", str(cialo)[:200])
        check("D5b …z naglowkiem WWW-Authenticate (bez niego biblioteka HTTP nie ma jak sie przedstawic)",
              "Basic" in (naglowki.get("WWW-Authenticate") or ""), str(naglowki)[:200])
        kod, cialo, _ = get(tabela, haslo="zle-haslo")
        check("D5c zle haslo → 401, nie 200 z pustka", kod == 401, f"kod={kod} {str(cialo)[:200]}")
        import os
        env = dict(os.environ, SNOW_INSTANCE=baza, SNOW_USER=UZYTKOWNIK, SNOW_TOKEN="zle-haslo")
        p = subprocess.run([sys.executable, "tools/snow_verify.py", "--ticket", "RITM0000001",
                            "--expect-project", PROJEKT, "--approver", APPROVER],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        check("D5d snow_verify.py przy zlym tokenie: rc=2 (fail-closed), bez tracebacku",
              p.returncode == 2 and "Traceback" not in p.stderr, f"rc={p.returncode}: {p.stderr[-300:]}")

        # ═══════════════════════════════════════════════════════════════════════════════════════
        # D6. REKORD NIEISTNIEJACY — zachowanie sprawdzone, nie zalozone (Z3 w naglowku symulatora).
        # ═══════════════════════════════════════════════════════════════════════════════════════
        brak = f"{tabela}?" + urllib.parse.urlencode({"sysparm_query": "number=RITM0000009"})
        kod, cialo, _ = get(brak)
        check("D6a sciezka bez wersji (=v2): brak rekordu → 200 i pusta tablica, NIE 404",
              kod == 200 and cialo == {"result": []}, f"kod={kod} {str(cialo)[:200]}")
        kod_v1, cialo_v1, _ = get(brak.replace("/api/now/table/", "/api/now/v1/table/"))
        check("D6b sciezka v1 w tej samej sytuacji: 404 — roznica, na ktorej integracja moze wyladowac "
              "po samej zmianie URL-a",
              kod_v1 == 404 and "error" in cialo_v1, f"kod={kod_v1} {str(cialo_v1)[:200]}")

        # ═══════════════════════════════════════════════════════════════════════════════════════
        # D7. LIMIT I PAGINACJA — nasza sciezka uzywa `sysparm_limit=1`, wiec musimy wiedziec, co on
        #     robi z reszta: NIE zawęża zbioru pasujacych, tylko OKNO. Stad szosta kontrola.
        # ═══════════════════════════════════════════════════════════════════════════════════════
        wszystkie = f"{tabela}?" + urllib.parse.urlencode({"sysparm_query": "numberSTARTSWITHRITM"})
        _, cialo, naglowki = get(wszystkie)
        razem = len(cialo["result"])
        _, cialo1, naglowki1 = get(wszystkie + "&sysparm_limit=1")
        _, cialo2, _ = get(wszystkie + "&sysparm_limit=1&sysparm_offset=1")
        check("D7a sysparm_limit tnie OKNO, a X-Total-Count niesie caly zbior",
              len(cialo1["result"]) == 1 and naglowki1.get("X-Total-Count") == str(razem),
              f"okno={len(cialo1['result'])} total={naglowki1.get('X-Total-Count')} razem={razem}")
        check("D7b sysparm_offset przesuwa okno (drugi rekord != pierwszy)",
              cialo2["result"][0]["number"] != cialo1["result"][0]["number"],
              f"{cialo1['result'][0]['number']} vs {cialo2['result'][0]['number']}")
        check("D7c naglowek Link niesie rel=\"next\", dopoki jest co pobierac",
              'rel="next"' in (naglowki1.get("Link") or ""), str(naglowki1.get("Link"))[:300])

        # ═══════════════════════════════════════════════════════════════════════════════════════
        # D8. SKLADNIA, KTOREJ API NIE ZNA. Platforma NIE odsyla 400 — odrzuca warunek i wykonuje
        #     reszte (Z6). To znaczy, ze zapytanie o nieistniejaca kolumne potrafi zwrocic PIERWSZY
        #     WIERSZ TABELI. Mierzymy oba tryby, bo wartosci domyslnej nie potwierdzilismy.
        # ═══════════════════════════════════════════════════════════════════════════════════════
        zle_pole = f"{tabela}?" + urllib.parse.urlencode(
            {"sysparm_query": "u_nie_ma_takiej_kolumny=cokolwiek", "sysparm_limit": "1",
             "sysparm_fields": ",".join(verify.POLA_WERDYKTU)})
        _, cialo_zle, _ = get(zle_pole)
        check("D8a tryb `odrzuc-warunek` (glide.invalid_query.returns_no_rows=FALSE): warunek wypada "
              "i wraca CUDZY rekord — brak bledu, brak pustki",
              len(cialo_zle["result"]) == 1 and cialo_zle["result"][0]["number"] == "RITM0000001",
              str(cialo_zle)[:300])
        problemy = verify.verify(cialo_zle, "RITM0000007", PROJEKT, APPROVER)
        check("D8b …a SZOSTA KONTROLA to odrzuca: `number` z odpowiedzi != numer, o ktory pytalismy",
              any("NIE jest ten ticket" in p for p in problemy), str(problemy)[:400])

    with symulator.Serwer(dane, UZYTKOWNIK, HASLO, tryb_nieprawidlowego="zero-wierszy") as drugi:
        _, cialo_zero, _ = get(f"{drugi.baza}/api/now/table/sc_req_item?" + urllib.parse.urlencode(
            {"sysparm_query": "u_nie_ma_takiej_kolumny=cokolwiek"}))
        check("D8c tryb `zero-wierszy` (…=TRUE): to samo zapytanie daje pusta tablice — bramka musi "
              "byc poprawna przy OBU ustawieniach, bo to wlasciwosc instancji docelowej",
              cialo_zero == {"result": []}, str(cialo_zero)[:200])

    with symulator.Serwer(dane, UZYTKOWNIK, HASLO) as serwer:
        baza, tabela = serwer.baza, f"{serwer.baza}/api/now/table/sc_req_item"

        # ═══════════════════════════════════════════════════════════════════════════════════════
        # D9. WSTRZYKNIECIE OPERATORA W NUMER TICKETU. Numer wchodzi do ZAKODOWANEGO ZAPYTANIA,
        #     a `^`/`^OR` sa tam operatorami — `urlencode` ich nie unieszkodliwia. Dwie warstwy
        #     obrony, kazda mierzona OSOBNO: warstwa bez wlasnego pomiaru znika przy refaktorze.
        # ═══════════════════════════════════════════════════════════════════════════════════════
        wstrzykniety = "RITM0000002^ORnumber=RITM0000001"
        p = verify_py("--ticket", wstrzykniety, "--expect-project", PROJEKT, "--approver", APPROVER,
                      srodowisko_bazy=baza)
        check("D9a WARSTWA 1 (ksztalt na wejsciu): numer z operatorem zapytania → rc=2, zapytanie "
              "nie wychodzi w ogole",
              p.returncode == 2 and "OPERATORAMI" in p.stderr, f"rc={p.returncode}: {p.stderr[-300:]}")
        # Warstwa 2 mierzona z POMINIECIEM warstwy 1 — inaczej test dowodzilby istnienia jednej obrony
        # i milczal o drugiej, a to wlasnie druga broni przy degradacji zapytania PO STRONIE INSTANCJI.
        _, cialo_wstrz, _ = get(f"{tabela}?" + urllib.parse.urlencode(
            {"sysparm_query": f"number={wstrzykniety}", "sysparm_limit": "1",
             "sysparm_fields": ",".join(verify.POLA_WERDYKTU)}))
        check("D9b …wstrzykniecie DZIALA po stronie instancji: zapytanie o RITM0000002 odsyla rekord "
              "RITM0000001 (zatwierdzony) — to nie jest teoria",
              cialo_wstrz["result"][0]["number"] == "RITM0000001", str(cialo_wstrz)[:300])
        problemy = verify.verify(cialo_wstrz, wstrzykniety, PROJEKT, APPROVER)
        check("D9c WARSTWA 2 (szosta kontrola): ta sama odpowiedz ODRZUCONA, bo numer sie nie zgadza",
              any("NIE jest ten ticket" in p for p in problemy), str(problemy)[:400])

        # ═══════════════════════════════════════════════════════════════════════════════════════
        # D10/D11. Pozostale zachowania kontraktu, ktorych nasza sciezka dotyka.
        # ═══════════════════════════════════════════════════════════════════════════════════════
        _, cialo, _ = get(f"{tabela}?" + urllib.parse.urlencode(
            {"sysparm_query": "number=RITM0000001", "sysparm_fields": "number,u_nie_ma_takiego_pola"}))
        check("D10 nieznane pole w sysparm_fields jest IGNOROWANE po cichu (200, klucz nie wraca) — "
              "wiec literowka w kontrakcie daje pustke, nie blad",
              cialo["result"][0] == {"number": "RITM0000001"}, str(cialo)[:200])
        _, cialo, _ = get(f"{tabela}?" + urllib.parse.urlencode(
            {"sysparm_query": "number=RITM0000001", "sysparm_fields": "number,assignment_group"}))
        check("D11 referencja zamowiona BEZ dot-walku wraca jako {link, value}, nie jako nazwa",
              isinstance(cialo["result"][0]["assignment_group"], dict), str(cialo)[:250])
        kod, cialo, _ = get(f"{serwer.baza}/api/now/table/nie_ma_takiej_tabeli")
        check("D12 nieznana tabela → 404 z cialem bledu", kod == 404 and "error" in cialo, str(cialo)[:200])

    # ═══════════════════════════════════════════════════════════════════════════════════════════
    # D13. GRANICA SYMULACJI MA STAC W KODZIE, NIE TYLKO W ZGLOSZENIU. Za miesiac ktos przeczyta
    #      zielony przebieg jako gotowosc produkcyjna — chyba ze plik, ktory ten przebieg produkuje,
    #      mowi wprost, czego nie dowodzi. Asercja pilnuje, zeby refaktor tego nie skasowal.
    # ═══════════════════════════════════════════════════════════════════════════════════════════
    naglowek = (ROOT / "tools/snow_symulator.py").read_text(encoding="utf-8")[:8000]
    check("D13a naglowek symulatora niesie sekcje „czego NIE dowodzi”",
          "NIE** DOWODZI" in naglowek or "NIE DOWODZI" in naglowek)
    check("D13b …i nazywa trzy granice wprost: pola wlasne, przeplyw approvali, wersje API",
          all(s in naglowek.lower() for s in ("u_project_id", "approval", "wersji api")), "")
    check("D13c …oraz tabele zrodel dla kazdego odtworzonego zachowania",
          naglowek.count("| Z") >= 7, f"wierszy Z*: {naglowek.count('| Z')}")
    doc = (ROOT / "docs/5-servicenow-intake.md").read_text(encoding="utf-8")
    check("D13d dokumentacja kanalu tez niesie te granice (nie tylko kod)",
          "NIE dowodzi" in doc and "symulator" in doc.lower(), "")

    zle = wyniki.count(False)
    print(f"\n{len(wyniki) - zle}/{len(wyniki)} OK" + (f", {zle} FAIL" if zle else ""))
    return 1 if zle else 0


if __name__ == "__main__":
    raise SystemExit(main())
