#!/usr/bin/env python3
"""Symulator Table API ServiceNow — serwer, na ktorym kanal ticketowy MOZE SIE WYWROCIC.

PO CO TO ISTNIEJE, POWIEDZIANE JEDNYM ZDANIEM: fixture potwierdza nasze zalozenia, a symulator ma je
LAMAC. Fixture jest odpowiedzia, ktora sami napisalismy — odpowiada wiec dokladnie na to zapytanie,
ktore sobie wyobrazilismy, i nie ma jak zaprzeczyc. Zmierzone (#2046): `snow_verify.py` CZYTAL
`assignment_group.name`, a ZAMAWIAL samo `sysparm_query`; Table API zwraca dot-walk wylacznie na jawne
zamowienie w `sysparm_fields`, wiec na zywej instancji ta bramka odrzucilaby KAZDY ticket — a fixture
przez caly czas swiecil na zielono, bo mial klucz z kropka wpisany recznie. Serwer, ktory implementuje
KONTRAKT zamiast odtwarzac ODPOWIEDZ, tego defektu nie przepuszcza: pytanie bez `sysparm_fields`
dostaje tu referencje jako obiekt `{link, value}` i zadnego klucza z kropka.

Symulator implementuje `docs/5-servicenow-intake.md` §8 — nie definiuje go. Rozjazd miedzy kontraktem
a tym plikiem ma byc CZERWONY (`tools/snow_symulator_kontrakt.py`), i to w obie strony: pole, ktorego
kontrakt nie zamawia, nie moze tu przyjsc, a pole, ktore zamawia, musi.

════════════════════════════════════════════════════════════════════════════════════════════════
CZEGO TEN SYMULATOR **NIE** DOWODZI — przeczytaj, ZANIM uznasz zielony przebieg za gotowosc
════════════════════════════════════════════════════════════════════════════════════════════════

Zielony przebieg przeciw temu serwerowi znaczy: „nasz kod rozmawia poprawnie z czyms, co zachowuje sie
zgodnie z opublikowana dokumentacja platformy". Nie znaczy nic wiecej. W szczegolnosci NIE dowodzi:

1. **Pol wlasnych organizacji docelowej.** `u_project_id` ma prefiks `u_`, czyli jest polem WLASNYM
   (customer-defined). Ten symulator wie o nim tylko tyle, ze my go zamawiamy. W organizacji
   docelowej moze nazywac sie inaczej, moze byc referencja zamiast tekstu, moze nie istniec — i wtedy
   kanal odmowi kazdemu wnioskowi.
2. **Przeplywu approvali organizacji docelowej.** Tu `approval` to kolumna tekstowa, ktora ustawiamy
   w pliku danych. Tam zatwierdzenie to rekordy w `sysapproval_approver`, workflow, delegacje i role.
   Zgodnosc z ta symulacja nie mowi nic o tym, czy „approved” w tamtej instancji znaczy „zatwierdzone
   przez kogos, kto mial prawo zatwierdzic".
3. **Wersji API i konfiguracji instancji.** ACL na tabeli, `sysparm_*` wylaczone przez wlasciwosc
   systemowa, MFA/OAuth zamiast Basic, limity zapytan, wersja rodziny wydan — kazde z tych ustawien
   zmienia odpowiedz, a zadnego nie da sie zgadnac z zewnatrz.
4. **Ze zbior wartosci `approval` jest taki, jak zakladamy.** `APPROVED_STATES` w `snow_verify.py` to
   nasz domysl o procesie tamtej organizacji, nie stala platformy.
5. **Ze uwierzytelnienie Basic w ogole przejdzie.** Tu przechodzi, bo tak to napisalismy.

Domkniecie tych piatek jest jedno i nie ma na nie skrotu: JEDEN odczyt z instancji docelowej,
procedura w `docs/5-servicenow-intake.md` §8.4. Symulator skraca droge do tego odczytu — nie zastepuje go.

════════════════════════════════════════════════════════════════════════════════════════════════
SKAD WIEMY, ZE TAK TO DZIALA — zrodlo dla kazdego zachowania, ktore tu odtwarzamy
════════════════════════════════════════════════════════════════════════════════════════════════

Zachowania bierzemy z dokumentacji dostawcy, nie z naszej wygody. Tam, gdzie zrodla nie ma albo jest
slabe, stoi to napisane wprost zamiast domyslu udajacego fakt.

| # | Zachowanie | Skad | Pewnosc |
|---|---|---|---|
| Z1 | Dot-walk (`x.y`) przychodzi WYLACZNIE gdy pole zamowiono w `sysparm_fields`; bez tego referencja to `{"link": …, "value": <sys_id>}`, a klucza z kropka NIE MA | blog deweloperski dostawcy „Dot-Walking in the REST Table API" (przyklad `location` / `location.name`) | **wysoka** — przyklad wprost pokazuje obie odpowiedzi |
| Z2 | Referencja bez dot-walku = obiekt `{link, value}` (przy domyslnym `sysparm_display_value=false`) | jw. | **wysoka** |
| Z3 | Zapytanie kolekcji, ktore nie pasuje do zadnego rekordu → **200** i `{"result": []}` na sciezce nieopatrzonej wersja (= v2). Sciezka **v1** (`/api/now/v1/table/…`) w tej samej sytuacji zwraca **404 „No Record Found"** | watki wsparcia dostawcy o roznicy v1/v2 („Query returning 404 in case of no records") | **wysoka** co do v2, **srednia** co do dokladnej TRESCI bledu v1 |
| Z4 | Brak/zle poswiadczenie Basic → **401** z cialem `{"error":{"message":"User Not Authenticated","detail":"Required to provide Auth information"},"status":"failure"}` | wielokrotnie cytowane cialo odpowiedzi w watkach wsparcia dostawcy | **wysoka** co do kodu, **srednia** co do dokladnego brzmienia `detail` |
| Z5 | Nieznana nazwa pola w `sysparm_fields` jest **ignorowana po cichu**, odpowiedz zostaje 200 — Table API nie zglasza bledu na nieznanych polach | watek dostawcy „Table API Doesn't Throw Errors for Invalid Field Names or References" | **srednia** — brak strony referencyjnej, wiele zgodnych relacji |
| Z6 | Nieprawidlowy WARUNEK w `sysparm_query` (np. nieistniejaca kolumna) NIE konczy sie bledem: platforma **odrzuca ten warunek** i wykonuje reszte — czyli potrafi zwrocic CALA tabele. Wlasciwosc `glide.invalid_query.returns_no_rows` przelacza to na „zero wierszy" | blog deweloperski dostawcy (odcinek o tej wlasciwosci) + watki wsparcia; **wartosci domyslnej NIE potwierdzilismy na stronie referencyjnej** — zrodla spolecznosciowe mowia `false` | **niska co do domyslnej**, wysoka co do ISTNIENIA obu trybow |
| Z7 | Operatory zakodowanego zapytania (`^` = AND, `^OR` = OR, `!=`, `IN`, `STARTSWITH`, `LIKE`, `ISEMPTY`) i ich skladnia | jezyk zakodowanych zapytan platformy, powszechnie udokumentowany | **wysoka** |

**Z6 obslugujemy OBUSTRONNIE i to jest decyzja, nie ostroznosc.** Skoro nie umiemy potwierdzic wartosci
domyslnej, a jest to wlasciwosc przestawiana po stronie wdrozenia, to bramka musi byc poprawna
przy OBU. Domyslny tryb symulatora to ten GORSZY dla nas (`odrzuc-warunek`) — testowanie przeciw
lagodniejszemu wariantowi bylo by dokladnie tym, co robi fixture.

════════════════════════════════════════════════════════════════════════════════════════════════

Uruchomienie:
    python3 tools/snow_symulator.py --dane tests/symulator-instancja.json --port 0 \
        --uzytkownik u --haslo h --plik-portu /tmp/port

`--port 0` wybiera wolny port i wypisuje go na stdout (oraz do `--plik-portu`) — bez tego kazdy przebieg
CI musialby zgadywac wolny numer, a zajety port dawalby porazke nie do odroznienia od bledu materialu.

TEN SERWER NIE NASLUCHUJE POZA PETLA ZWROTNA. Wiaze sie do `127.0.0.1` i nie ma przelacznika, ktory by
to zmienil: system rekordu udawany na adresie osiagalnym z zewnatrz to nie narzedzie testowe, tylko
falszywy system rekordu. `snow_verify.py` przyjmuje po tej stronie wylacznie adres petli zwrotnej.
"""
import argparse
import base64
import http.server
import json
import re
import socket
import sys
import threading
import urllib.parse

# Operatory zakodowanego zapytania, ktore ROZUMIEMY. Wszystko poza ta lista jest „skladnia, ktorej API
# nie zna" i idzie sciezka Z6 — bo tak wlasnie zachowuje sie platforma: nie odsyla 400, tylko wyrzuca
# warunek. Kolejnosc MA ZNACZENIE: dluzsze operatory przed krotszymi, inaczej `!=` zostalby rozpoznany
# jako `=` z pusta nazwa pola po lewej.
OPERATORY = (
    "STARTSWITH", "ENDSWITH", "NOTLIKE", "LIKE", "ISNOTEMPTY", "ISEMPTY", "NOT IN", "IN",
    "!=", ">=", "<=", "=", ">", "<",
)
BEZ_ARGUMENTU = {"ISEMPTY", "ISNOTEMPTY"}

CIALO_401 = {
    "error": {"message": "User Not Authenticated", "detail": "Required to provide Auth information"},
    "status": "failure",
}


class ZapytanieNieprawidlowe(Exception):
    """Warunek, ktorego platforma nie umie wykonac — patrz Z6. NIE jest to blad HTTP."""


def dopasuj_operator(warunek: str) -> tuple[str, str, str]:
    """Rozbija `pole<operator>[wartosc]`. Rzuca ZapytanieNieprawidlowe, gdy nie ma znanego operatora."""
    for op in OPERATORY:
        idx = warunek.find(op)
        if idx <= 0:  # `<= 0`, bo operator na pozycji 0 znaczy warunek bez nazwy pola
            continue
        pole = warunek[:idx]
        wartosc = warunek[idx + len(op):]
        if op in BEZ_ARGUMENTU and wartosc:
            continue
        return pole, op, wartosc
    raise ZapytanieNieprawidlowe(f"warunek {warunek!r} nie zawiera znanego operatora")


def spelnia(rekord: dict, kolumny: set, warunek: str) -> bool:
    pole, op, oczek = dopasuj_operator(warunek)
    if pole not in kolumny:
        # NIEISTNIEJACA KOLUMNA. To jest dokladnie ten przypadek, ktory wlasciwosc z Z6 obsluguje —
        # i powod, dla ktorego nie wolno tego zamienic na 400. Zwrocenie bledu tutaj czynilo by
        # symulator LAGODNIEJSZYM od platformy: nasza bramka dostawalaby czytelny sygnal tam, gdzie
        # na docelowej instancji dostanie ciche „oto pierwszy wiersz tabeli".
        raise ZapytanieNieprawidlowe(f"kolumna {pole!r} nie istnieje w tej tabeli")
    mam = str(rekord.get(pole, "") or "")
    if op == "=":
        return mam == oczek
    if op == "!=":
        return mam != oczek
    if op == "LIKE":
        return oczek.lower() in mam.lower()
    if op == "NOTLIKE":
        return oczek.lower() not in mam.lower()
    if op == "STARTSWITH":
        return mam.lower().startswith(oczek.lower())
    if op == "ENDSWITH":
        return mam.lower().endswith(oczek.lower())
    if op == "IN":
        return mam in [c.strip() for c in oczek.split(",")]
    if op == "NOT IN":
        return mam not in [c.strip() for c in oczek.split(",")]
    if op == "ISEMPTY":
        return mam == ""
    if op == "ISNOTEMPTY":
        return mam != ""
    if op in (">", "<", ">=", "<="):
        return {">" : mam > oczek, "<": mam < oczek, ">=": mam >= oczek, "<=": mam <= oczek}[op]
    raise ZapytanieNieprawidlowe(f"operator {op!r} rozpoznany, ale niezaimplementowany")


def filtruj(rekordy: list, kolumny: set, zapytanie: str, tryb_nieprawidlowego: str) -> list:
    """Zakodowane zapytanie: `^` = AND, `^OR` = OR (wiaze slabiej), `^NQ` = nowe zapytanie (tez OR).

    Zwraca rekordy pasujace. Nieprawidlowy warunek obslugujemy wg Z6 — dwa tryby, oba realne.
    """
    if not zapytanie:
        return list(rekordy)
    # `^NQ` i `^OR` rozdzielaja alternatywy; wewnatrz alternatywy `^` laczy koniunkcyjnie.
    alternatywy = [a for a in re.split(r"\^NQ|\^OR", zapytanie)]
    wynik = []
    for rekord in rekordy:
        for alternatywa in alternatywy:
            warunki = [w for w in alternatywa.split("^") if w]
            spelnione = True
            for warunek in warunki:
                try:
                    if not spelnia(rekord, kolumny, warunek):
                        spelnione = False
                        break
                except ZapytanieNieprawidlowe:
                    if tryb_nieprawidlowego == "zero-wierszy":
                        # `glide.invalid_query.returns_no_rows = true`
                        return []
                    # `= false`: warunek WYPADA, reszta sie wykonuje. Pusty zbior warunkow po
                    # odrzuceniu = brak filtra = cala tabela. To nie jest przesada — to jest ten
                    # tryb awarii, o ktorym mowi Z6.
                    continue
            if spelnione:
                wynik.append(rekord)
                break
    return wynik


class Instancja:
    """Dane „instancji": tabele, kolumny referencyjne i baza URL do budowania `link`."""

    def __init__(self, dane: dict, baza: str):
        self.tabele = dane["tabele"]
        self.referencje = dane.get("referencje", {})
        self.baza = baza

    def kolumny(self, tabela: str) -> set:
        kolumny = set()
        for rekord in self.tabele.get(tabela, []):
            kolumny |= set(rekord.keys())
        return kolumny

    def rekord_po_sys_id(self, tabela: str, sys_id: str) -> dict | None:
        for rekord in self.tabele.get(tabela, []):
            if rekord.get("sys_id") == sys_id:
                return rekord
        return None

    def referencja(self, tabela: str, kolumna: str) -> str | None:
        return self.referencje.get(tabela, {}).get(kolumna)

    def obiekt_referencji(self, tabela_docelowa: str, sys_id: str) -> dict:
        return {"link": f"{self.baza}/api/now/table/{tabela_docelowa}/{sys_id}", "value": sys_id}

    def wiersz_pelny(self, tabela: str, rekord: dict) -> dict:
        """Odpowiedz BEZ `sysparm_fields`: wszystkie kolumny, referencje jako obiekt, ZERO kluczy z kropka.

        To jest miejsce, w ktorym symulator lamie zalozenie fixture'u. Kluczy `x.y` tu NIE MA i nie moze
        byc — nie dlatego, ze ich nie dopisalismy, tylko dlatego, ze platforma ich w tej odpowiedzi
        nie wysyla (Z1).
        """
        wiersz = {}
        for kolumna, wartosc in rekord.items():
            if kolumna == "sys_id":
                wiersz[kolumna] = wartosc
                continue
            cel = self.referencja(tabela, kolumna)
            wiersz[kolumna] = self.obiekt_referencji(cel, wartosc) if cel else str(wartosc)
        return wiersz

    def wiersz_zamowiony(self, tabela: str, rekord: dict, pola: list) -> dict:
        """Odpowiedz Z `sysparm_fields`: wylacznie zamowione klucze, dot-walk rozwiazany.

        Nieznane pole wypada po cichu (Z5) — nie 400, nie klucz z pusta wartoscia. Klucz z pusta
        wartoscia bylby GORSZY od braku: nasza bramka czyta `row.get(pole, "")`, wiec obie postacie
        znaczylyby dla niej to samo, a dla czlowieka czytajacego odpowiedz — cos zupelnie innego.
        """
        wiersz = {}
        for pole in pola:
            if "." in pole:
                kolumna, dalej = pole.split(".", 1)
                cel = self.referencja(tabela, kolumna)
                if cel is None or kolumna not in self.kolumny(tabela):
                    continue  # dot-walk po czyms, co nie jest referencja — pole nieznane, wypada
                wskazany = self.rekord_po_sys_id(cel, str(rekord.get(kolumna, "")))
                if wskazany is None or dalej not in wskazany:
                    continue
                wiersz[pole] = str(wskazany[dalej])
                continue
            if pole not in rekord:
                continue
            cel = self.referencja(tabela, pole)
            wiersz[pole] = self.obiekt_referencji(cel, rekord[pole]) if cel else str(rekord[pole])
        return wiersz


def zbuduj_handler(inst: Instancja, uzytkownik: str, haslo: str, tryb_nieprawidlowego: str, log: list):
    oczekiwane = base64.b64encode(f"{uzytkownik}:{haslo}".encode()).decode()

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):  # cisza: log przebiegu ma niesc werdykty, nie ruch HTTP
            pass

        def _odeslij(self, kod: int, cialo: dict, naglowki: dict | None = None):
            payload = json.dumps(cialo).encode()
            self.send_response(kod)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            for k, v in (naglowki or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):  # noqa: N802 — nazwa narzucona przez BaseHTTPRequestHandler
            # UWIERZYTELNIENIE PIERWSZE, PRZED CZYMKOLWIEK INNYM. Brak poswiadczenia nie moze
            # skonczyc sie „pusta lista rekordow" — to jest ta sama klasa bledu, co „nie rozumiem
            # odpowiedzi" potraktowane jak „nie ma zatwierdzenia" (Z4).
            podane = (self.headers.get("Authorization") or "")
            if not podane.startswith("Basic ") or podane[6:].strip() != oczekiwane:
                self._odeslij(401, CIALO_401, {"WWW-Authenticate": 'Basic realm="Service-now"'})
                return

            rozbite = urllib.parse.urlparse(self.path)
            param = urllib.parse.parse_qs(rozbite.query, keep_blank_values=True)
            log.append({"sciezka": rozbite.path, "param": {k: v[0] for k, v in param.items()}})

            m = re.match(r"^/api/now(?:/(v1|v2))?/table/([A-Za-z0-9_]+)/?$", rozbite.path)
            if not m:
                self._odeslij(404, {"error": {"message": "No Record Found",
                                              "detail": "sciezka spoza Table API tego symulatora"},
                                    "status": "failure"})
                return
            wersja, tabela = m.group(1) or "v2", m.group(2)
            if tabela not in inst.tabele:
                self._odeslij(404, {"error": {"message": f"Invalid table {tabela}", "detail": None},
                                    "status": "failure"})
                return

            try:
                pasujace = filtruj(inst.tabele[tabela], inst.kolumny(tabela),
                                   param.get("sysparm_query", [""])[0], tryb_nieprawidlowego)
            except ZapytanieNieprawidlowe as exc:
                self._odeslij(400, {"error": {"message": str(exc), "detail": None}, "status": "failure"})
                return

            razem = len(pasujace)
            offset = int(param.get("sysparm_offset", ["0"])[0] or 0)
            # 10000 to udokumentowany limit domyslny Table API; podajemy go jawnie, zeby paginacja
            # symulatora byla tym samym mechanizmem, co w produkcji, a nie „bez limitu".
            limit = int(param.get("sysparm_limit", ["10000"])[0] or 10000)
            okno = pasujace[offset:offset + limit]

            pola = [p.strip() for p in param.get("sysparm_fields", [""])[0].split(",") if p.strip()]
            if pola:
                wynik = [inst.wiersz_zamowiony(tabela, r, pola) for r in okno]
            else:
                wynik = [inst.wiersz_pelny(tabela, r) for r in okno]

            if not wynik and wersja == "v1":
                # v1 na pustym zbiorze odpowiada bledem, v2 — pusta lista (Z3). Trzymamy obie sciezki,
                # bo to jest dokladnie ta roznica, na ktorej integracja moze wyladowac po zmianie URL-a.
                self._odeslij(404, {"error": {"message": "No Record Found",
                                              "detail": "Requested record not found"}, "status": "failure"})
                return

            naglowki = {"X-Total-Count": str(razem)}
            linki = []
            baza_link = f"{inst.baza}{rozbite.path}"
            def _link(off, rel):
                p = dict((k, v[0]) for k, v in param.items())
                p["sysparm_offset"] = str(off)
                linki.append(f'<{baza_link}?{urllib.parse.urlencode(p)}>;rel="{rel}"')
            if limit > 0:
                _link(0, "first")
                if offset > 0:
                    _link(max(0, offset - limit), "prev")
                if offset + limit < razem:
                    _link(offset + limit, "next")
                _link(max(0, ((razem - 1) // limit) * limit) if razem else 0, "last")
            if linki:
                naglowki["Link"] = ",".join(linki)
            self._odeslij(200, {"result": wynik}, naglowki)

        def do_POST(self):  # noqa: N802
            self._odeslij(405, {"error": {"message": "Method Not Allowed", "detail":
                                          "ten symulator jest READ-ONLY — kanal ticketowy tylko czyta"},
                                "status": "failure"})

        do_PUT = do_PATCH = do_DELETE = do_POST

    return Handler


class Serwer:
    """Serwer w watku — do uzycia z `with` w testach i z CLI w CI."""

    def __init__(self, dane: dict, uzytkownik: str, haslo: str, port: int = 0,
                 tryb_nieprawidlowego: str = "odrzuc-warunek"):
        self.log = []
        gniazdo = socket.socket()
        gniazdo.bind(("127.0.0.1", port))
        self.port = gniazdo.getsockname()[1]
        gniazdo.close()
        inst = Instancja(dane, f"http://127.0.0.1:{self.port}")
        self.httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", self.port), zbuduj_handler(inst, uzytkownik, haslo, tryb_nieprawidlowego, self.log))
        self.watek = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def baza(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        self.watek.start()
        return self

    def __exit__(self, *_exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def wczytaj_dane(sciezka: str) -> dict:
    dane = json.loads(open(sciezka, encoding="utf-8").read())
    # TEN SAM ZNACZNIK, CO NA FIXTURE'ACH, I Z TEGO SAMEGO POWODU (DEC-43): plik, ktory udaje system
    # rekordu, musi powiedziec o sobie, czym jest — przy otwarciu, a nie po przeczytaniu workflowa.
    if not str(dane.get("_material_testowy", "")).strip():
        raise SystemExit(f"{sciezka}: brak niepustego `_material_testowy` — symulator przyjmuje "
                         "wylacznie pliki, ktore mowia o sobie, ze sa materialem testowym")
    if "tabele" not in dane:
        raise SystemExit(f"{sciezka}: brak klucza `tabele`")
    return dane


def main() -> int:
    ap = argparse.ArgumentParser(description="Symulator Table API ServiceNow (petla zwrotna, read-only)")
    ap.add_argument("--dane", required=True, help="plik JSON z tabelami instancji")
    ap.add_argument("--port", type=int, default=0, help="0 = wybierz wolny (domyslnie)")
    ap.add_argument("--uzytkownik", required=True)
    ap.add_argument("--haslo", required=True)
    ap.add_argument("--plik-portu", help="zapisz wybrany port do tego pliku (dla CI)")
    ap.add_argument("--tryb-nieprawidlowego-zapytania", default="odrzuc-warunek",
                    choices=("odrzuc-warunek", "zero-wierszy"),
                    help="Z6: `odrzuc-warunek` = glide.invalid_query.returns_no_rows FALSE (domyslny "
                         "tryb symulatora, bo GORSZY dla nas); `zero-wierszy` = TRUE")
    args = ap.parse_args()

    serwer = Serwer(wczytaj_dane(args.dane), args.uzytkownik, args.haslo, args.port,
                    args.tryb_nieprawidlowego_zapytania)
    if args.plik_portu:
        open(args.plik_portu, "w", encoding="utf-8").write(str(serwer.port))
    print(serwer.port, flush=True)
    print(f"symulator ServiceNow: {serwer.baza} (tryb nieprawidlowego zapytania: "
          f"{args.tryb_nieprawidlowego_zapytania}) — TO NIE JEST SYSTEM REKORDU", file=sys.stderr, flush=True)
    with serwer:
        try:
            serwer.watek.join()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
