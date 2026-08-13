#!/usr/bin/env python3
"""Weryfikuje ticket ServiceNow U ŹRÓDŁA, zanim bot otworzy PR.

DLACZEGO to jest osobny, obowiązkowy krok: zgłoszenie niesie payload, który jest tak wiarygodny jak token,
którym go wysłano — a tokeny wyciekają. Gdyby workflow ufał payloadowi, każdy, kto zdobędzie token
integracji, dopisywałby sobie projekty do perimetru całej organizacji, w pełni „proceduralnie".
Oddzwonienie zamienia „ufam wiadomości" w „ufam systemowi rekordu". Nie zmienia tego zawężenie kanału do
`workflow_dispatch`: węższe uprawnienie nadawcy zmniejsza skutki wycieku, ale nie czyni payloadu prawdziwym.

KONTRAKT ZAPYTANIA — SPISANY, BO NIE JEST ZMIERZONY (DEC-43). Ten skrypt nie rozmawiał jeszcze z żadną
instancją ServiceNow; wszystko, co o niej „wie", stoi na dokumentacji dostawcy i jest wypisane niżej,
żeby dało się to skonfrontować JEDNYM odczytem, a nie czytaniem kodu:

    GET https://<instancja>.service-now.com/api/now/table/sc_req_item
        ?sysparm_query=number=<ticket>&sysparm_fields=<POLA_WERDYKTU>&sysparm_limit=1
    Accept: application/json          · uwierzytelnienie: Basic (SNOW_USER / SNOW_TOKEN)
    Odpowiedź: {"result": [ {<pole>: <wartość tekstowa>, …} ]}   ·   brak rekordu -> {"result": []}

**Dot-walk (`assignment_group.name`) Table API zwraca WYŁĄCZNIE wtedy, gdy pole jest jawnie zamówione
w `sysparm_fields`.** Bez tego referencja przychodzi jako obiekt `{"link": …, "value": <sys_id>}`, a klucza
z kropką w odpowiedzi NIE MA W OGÓLE. To jest defekt, który zamykał `POLA_WERDYKTU`: wcześniejsza wersja
CZYTAŁA `assignment_group.name`, a ZAMAWIAŁA samo `sysparm_query` — czyli pytała o pole, którego jej własne
zapytanie nie mogło przynieść, i na żywej instancji odrzuciłaby KAŻDY ticket. Fixture obiecywał kształt,
którego to zapytanie nigdy by nie dostało; dlatego pola werdyktu i pola zapytania mają dziś jedno źródło.

CZEGO TEN SKRYPT NIE DOWODZI, powiedziane wprost: że pola nazywają się w danej instancji tak, jak stoi
w `POLA_WERDYKTU` (`u_project_id` jest polem WŁASNYM organizacji, nie standardem platformy), i że
`approval` przyjmuje akurat te wartości. Rozstrzyga to jeden odczyt z instancji docelowej — procedura
w `docs/5-servicenow-intake.md` §8. Do tego czasu kanał jest fail-closed: nieznany kształt odpowiedzi
degraduje się do ODMOWY, nigdy do zgody, a fixture musi zadeklarować się jako materiał testowy.

Sprawdzamy pięć rzeczy — każda zamyka inny scenariusz:
  1. ticket istnieje                     → payload nie zmyśla numeru,
  2. stan == zatwierdzony                → nie przepuszczamy wniosku w trakcie akceptacji,
  3. approver z grupy sieciowej          → zatwierdza uprawniony zespół, nie dowolna grupa,
  4. treść ticketu == treść payloadu     → payload nie podmienił projektu po zatwierdzeniu,
  5. zatwierdzający != wnioskodawca      → rozdział obowiązków po OSOBIE, nie po grupie.

Punkt 5 był luką: punkt 3 porównuje GRUPĘ z allowlistą, więc wnioskodawca NALEŻĄCY do grupy sieciowej
zatwierdzał własny ticket i przechodził komplet kontroli. To ta sama asercja, którą po stronie
repozytorium egzekwuje `tools/codeowners_check.py` (zatwierdzający spoza zbioru wnioskodawców).
Zakres punktu 5, żeby nikt nie czytał go szerzej: porównuje tożsamość WNIOSKODAWCY z ticketu z tym, kogo
zgłoszenie podaje jako zatwierdzającego. Nie czyta rekordu approvalu (`sysapproval_approver`), więc payload
kłamiący o zatwierdzającym nadal przejdzie — domknięcie wymaga drugiego odczytu z żywej instancji i jest
wypisane jako pozycja do zmierzenia w §8, nie udawane zieloną bramką.

Sekrety: SNOW_INSTANCE, SNOW_USER, SNOW_TOKEN wyłącznie z secrets GitHuba. Skrypt ich nie loguje.

Użycie:
    python3 tools/snow_verify.py --ticket RITM0000123 --expect-project prj-example-vertex-prod \
        --approver net-approver@example.com
    python3 tools/snow_verify.py --ticket RITM0000123 --expect-project X --approver n@example.com \
        --offline-fixture tests/snow-approved.json
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

APPROVED_STATES = {"approved", "3"}  # SNOW zwraca stan zależnie od konfiguracji instancji
NETWORK_APPROVER_GROUPS = {"network-team", "cloud-networking"}

# Pola wnioskodawcy w kolejności czytania: `requested_for` to osoba, DLA której złożono wniosek,
# `opened_by` to ten, kto go wyklikał. Pierwsze niepuste rozstrzyga; brak obu = odmowa (niżej).
POLA_WNIOSKODAWCY = ("requested_for.user_name", "opened_by.user_name")

# JEDNO ŹRÓDŁO dla zapytania i dla checków. Każde pole, na którym stoi werdykt, MUSI być tutaj — inaczej
# ServiceNow go nie przyśle (patrz nagłówek: dot-walk tylko na jawne zamówienie), a check czytałby pustkę
# i degradował się do odmowy na każdym tickecie. Selftest pilnuje tej równości w obie strony.
POLA_WERDYKTU = (
    "number",
    "approval",
    "state",
    "u_project_id",
    "assignment_group.name",
) + POLA_WNIOSKODAWCY

# sys_id: 32 znaki hex. Pole tożsamości w tej postaci NIE JEST porównywalne z loginem ani adresem e-mail —
# porównanie zawsze wypadłoby „różni", czyli kontrola samo-zatwierdzenia nigdy by nie odrzuciła. Kontrola,
# która nie umie odrzucić, jest gorsza od jej braku, więc taki kształt kończy się odmową z nazwaniem powodu.
SYS_ID = re.compile(r"^[0-9a-f]{32}$")


def url_odczytu(instance: str, ticket: str) -> str:
    """URL odczytu ticketu — osobno, żeby test mógł potwierdzić, że zamawiamy DOKŁADNIE pola werdyktu."""
    query = urllib.parse.urlencode({
        "sysparm_query": f"number={ticket}",
        "sysparm_fields": ",".join(POLA_WERDYKTU),
        "sysparm_limit": "1",
    })
    return f"https://{instance}.service-now.com/api/now/table/sc_req_item?{query}"


def fetch(instance: str, ticket: str, user: str, token: str) -> dict:
    url = url_odczytu(instance, ticket)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    auth = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    auth.add_password(None, url, user, token)
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(auth))
    with opener.open(req, timeout=20) as resp:
        return json.loads(resp.read())


def tozsamosc(wartosc: str) -> str:
    """Klucz porównania tożsamości: bez wielkości liter, bez domeny.

    Zgłoszenie podaje zatwierdzającego adresem e-mail, a ServiceNow trzyma login (`user_name`) — porównanie
    surowych napisów nigdy by nie zrównało `net-approver@example.com` z `net-approver`, czyli kontrola
    samo-zatwierdzenia byłaby zielona zawsze. Odcięcie domeny to ZAŁOŻENIE (login == część przed `@`)
    i jest wypisane w kontrakcie §8 jako pozycja do potwierdzenia na instancji docelowej.
    """
    return wartosc.strip().lower().split("@", 1)[0]


def pierwsze_niepuste(row: dict, pola) -> tuple[str, str] | tuple[None, None]:
    for pole in pola:
        wartosc = str(row.get(pole, "") or "").strip()
        if wartosc:
            return pole, wartosc
    return None, None


def verify(doc: dict, ticket: str, expect_project: str, approver: str) -> list[str]:
    problems = []
    rows = doc.get("result", [])
    if not rows:
        return [f"ticket {ticket} nie istnieje w ServiceNow"]

    row = rows[0]
    state = str(row.get("approval", row.get("state", ""))).lower()
    if state not in APPROVED_STATES:
        problems.append(f"ticket {ticket}: stan={state!r}, wymagany zatwierdzony")

    # Bez zapasowego `approval_group`: pole o takiej nazwie nie jest polem platformy, tylko domysłem,
    # a domysł w bramce fail-closed dokłada ścieżkę, którą odpowiedź o NIEZNANYM kształcie mogłaby
    # przejść. Zostaje jedno pole, to samo, które zamawia zapytanie — nazwane w kontrakcie §8.
    group = str(row.get("assignment_group.name", "")).lower()
    if group not in NETWORK_APPROVER_GROUPS:
        problems.append(f"ticket {ticket}: approver z grupy {group!r} — wymagana grupa sieciowa")

    # Punkt 4: to jest ten check, który wyłapuje podmianę treści między zatwierdzeniem a dispatchem.
    declared = str(row.get("u_project_id", "")).strip()
    if declared != expect_project:
        problems.append(
            f"ticket {ticket}: zatwierdzono projekt {declared!r}, a dispatch prosi o {expect_project!r}"
        )

    # Punkt 5: rozdział obowiązków po OSOBIE. Trzy wyjścia, bo „nie wiem" musi brzmieć inaczej niż „ok".
    pole, wnioskodawca = pierwsze_niepuste(row, POLA_WNIOSKODAWCY)
    if wnioskodawca is None:
        problems.append(
            f"ticket {ticket}: NIE ZNALAZŁEM pola z wnioskodawcą ({', '.join(POLA_WNIOSKODAWCY)}) — bez niego "
            "nie da się odróżnić zatwierdzającego od wnioskodawcy, więc odmawiam zamiast przepuścić"
        )
    elif SYS_ID.match(wnioskodawca):
        problems.append(
            f"ticket {ticket}: pole {pole} niesie sys_id ({wnioskodawca!r}), a nie login — porównanie "
            f"z zatwierdzającym {approver!r} nigdy by nie odrzuciło, więc odmawiam"
        )
    elif tozsamosc(wnioskodawca) == tozsamosc(approver):
        problems.append(
            f"ticket {ticket}: zatwierdzający {approver!r} to ten sam człowiek co wnioskodawca "
            f"{wnioskodawca!r} (pole {pole}) — samo-zatwierdzenie"
        )
    return problems


def wczytaj_fixture(sciezka: str) -> tuple[dict | None, str]:
    """Fixture musi POWIEDZIEĆ O SOBIE, że jest materiałem testowym — inaczej nie jest wejściem tego trybu.

    Bez tego znacznika jedyną różnicą między „werdykt z systemu rekordu" a „werdykt z pliku w repo" jest
    nazwa kroku w workflow. Znacznik jest wymagany, żeby (a) plik dało się rozpoznać po samym otwarciu,
    (b) tryb offline nie dał się nakarmić dowolnym JSON-em, który akurat ma pasujący kształt.
    """
    try:
        doc = json.loads(open(sciezka, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"nie da się odczytać fixture'u {sciezka}: {exc}"
    if not isinstance(doc, dict) or not str(doc.get("_material_testowy", "")).strip():
        return None, (
            f"{sciezka} nie deklaruje się jako materiał testowy (brak niepustego pola "
            "`_material_testowy`) — tryb offline przyjmuje wyłącznie pliki, które mówią o sobie, czym są"
        )
    return doc, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket", required=True)
    ap.add_argument("--expect-project", required=True)
    # WYMAGANY, nie opcjonalny: kontrola, którą wyłącza się pominięciem flagi, jest kontrolą wyłączoną.
    ap.add_argument("--approver", required=True,
                    help="kto zatwierdził po stronie wnioskodawcy (wejście `approved_by` zgłoszenia)")
    ap.add_argument("--offline-fixture", help="plik JSON zamiast wywołania API (selftest / dev)")
    args = ap.parse_args()

    prefiks = ""
    if args.offline_fixture:
        # KAŻDA linia werdyktu niesie ten prefiks. Werdykt z fixture'u czyta się w podsumowaniu przebiegu
        # i w opisie pull requesta — bez prefiksu jest nieodróżnialny od odpowiedzi systemu rekordu.
        prefiks = f"[MATERIAŁ TESTOWY: {args.offline_fixture}] "
        doc, blad = wczytaj_fixture(args.offline_fixture)
        if doc is None:
            print(f"ODRZUCONE: {blad}", file=sys.stderr)
            return 2
    else:
        # BRAK KONFIGURACJI TO NIE JEST ZGODA — i musi to POWIEDZIEĆ. Wcześniej `os.environ[...]` rzucało
        # `KeyError: 'SNOW_INSTANCE'` z tracebackiem: kod wyjścia był niezerowy, więc bramka trzymała, ale
        # w logu przebiegu wyglądało to na awarię skryptu, a nie na odmowę. Tryb awarii, którego nikt nie
        # umie odczytać, kończy się „to chyba flaka, puść jeszcze raz" — czyli ścieżką, na której ludzie
        # zaczynają szukać obejścia bramki zamiast przyczyny.
        brakujace = [n for n in ("SNOW_INSTANCE", "SNOW_USER", "SNOW_TOKEN") if not os.environ.get(n)]
        if brakujace:
            print(
                "ODRZUCONE: brak konfiguracji ServiceNow (" + ", ".join(brakujace) + ") — bez systemu "
                "rekordu nie ma czym potwierdzić zatwierdzenia, więc nie ma PR-a",
                file=sys.stderr,
            )
            return 2
        instance = os.environ["SNOW_INSTANCE"]
        try:
            doc = fetch(instance, args.ticket, os.environ["SNOW_USER"], os.environ["SNOW_TOKEN"])
        except urllib.error.HTTPError as exc:
            # Błąd wywołania NIE jest zgodą. Fail-closed: bez odpowiedzi z systemu rekordu nie ma PR-a.
            print(f"ServiceNow odpowiedziało {exc.code} — traktuję jako brak zatwierdzenia", file=sys.stderr)
            return 2
        except (urllib.error.URLError, TimeoutError) as exc:
            # Sieć/DNS/timeout — ta sama zasada, co wyżej, ale INNY wyjątek: bez tej gałęzi instancja
            # nieosiągalna kończyła się tracebackiem, czyli trybem awarii nie do odczytania w logu.
            print(f"ODRZUCONE: ServiceNow nieosiągalne ({exc}) — brak odpowiedzi nie znaczy zatwierdzone",
                  file=sys.stderr)
            return 2
        except json.JSONDecodeError:
            # Instancja developerska w hibernacji odpowiada STRONĄ HTML z kodem 200. „Nie rozumiem
            # odpowiedzi" to odmowa, nie zgoda — i musi się tak wypisać.
            print("ODRZUCONE: odpowiedź nie jest JSON-em (instancja w hibernacji? strona logowania?) — "
                  "nie mam czym potwierdzić zatwierdzenia", file=sys.stderr)
            return 2

    problems = verify(doc, args.ticket, args.expect_project, args.approver)
    if problems:
        for p in problems:
            print(f"{prefiks}ODRZUCONE: {p}", file=sys.stderr)
        return 1

    print(f"{prefiks}OK: {args.ticket} zatwierdzony przez zespół sieciowy dla {args.expect_project}, "
          f"zatwierdzający ({args.approver}) != wnioskodawca")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
