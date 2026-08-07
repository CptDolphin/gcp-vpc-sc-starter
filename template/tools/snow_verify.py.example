#!/usr/bin/env python3
"""Weryfikuje ticket ServiceNow U ŹRÓDŁA, zanim bot otworzy PR.

DLACZEGO to jest osobny, obowiązkowy krok: `repository_dispatch` niesie payload, który jest tak wiarygodny
jak token, którym go wysłano — a tokeny wyciekają. Gdyby workflow ufał payloadowi, każdy, kto zdobędzie
token integracji, dopisywałby sobie projekty do perimetru całej organizacji, w pełni „proceduralnie".
Oddzwonienie zamienia „ufam wiadomości" w „ufam systemowi rekordu".

Sprawdzamy cztery rzeczy — każda zamyka inny scenariusz:
  1. ticket istnieje                     → payload nie zmyśla numeru,
  2. stan == zatwierdzony                → nie przepuszczamy wniosku w trakcie akceptacji,
  3. approver należy do grupy sieciowej  → nie samo-zatwierdzenie przez wnioskodawcę,
  4. treść ticketu == treść payloadu     → payload nie podmienił projektu po zatwierdzeniu.

Sekrety: SNOW_INSTANCE, SNOW_USER, SNOW_TOKEN wyłącznie z secrets GitHuba. Skrypt ich nie loguje.

Użycie:
    python3 tools/snow_verify.py --ticket RITM0000123 --expect-project prj-example-vertex-prod
    python3 tools/snow_verify.py --ticket RITM0000123 --expect-project X --offline-fixture fixture.json
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

APPROVED_STATES = {"approved", "3"}  # SNOW zwraca stan zależnie od konfiguracji instancji
NETWORK_APPROVER_GROUPS = {"network-team", "cloud-networking"}


def fetch(instance: str, ticket: str, user: str, token: str) -> dict:
    url = f"https://{instance}.service-now.com/api/now/table/sc_req_item?sysparm_query=number={ticket}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    auth = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    auth.add_password(None, url, user, token)
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(auth))
    with opener.open(req, timeout=20) as resp:
        return json.loads(resp.read())


def verify(doc: dict, ticket: str, expect_project: str) -> list[str]:
    problems = []
    rows = doc.get("result", [])
    if not rows:
        return [f"ticket {ticket} nie istnieje w ServiceNow"]

    row = rows[0]
    state = str(row.get("approval", row.get("state", ""))).lower()
    if state not in APPROVED_STATES:
        problems.append(f"ticket {ticket}: stan={state!r}, wymagany zatwierdzony")

    group = str(row.get("assignment_group.name", row.get("approval_group", ""))).lower()
    if group not in NETWORK_APPROVER_GROUPS:
        problems.append(f"ticket {ticket}: approver z grupy {group!r} — wymagana grupa sieciowa")

    # Punkt 4: to jest ten check, który wyłapuje podmianę treści między zatwierdzeniem a dispatchem.
    declared = str(row.get("u_project_id", "")).strip()
    if declared != expect_project:
        problems.append(
            f"ticket {ticket}: zatwierdzono projekt {declared!r}, a dispatch prosi o {expect_project!r}"
        )
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket", required=True)
    ap.add_argument("--expect-project", required=True)
    ap.add_argument("--offline-fixture", help="plik JSON zamiast wywołania API (selftest / dev)")
    args = ap.parse_args()

    if args.offline_fixture:
        doc = json.loads(open(args.offline_fixture).read())
    else:
        instance = os.environ["SNOW_INSTANCE"]
        try:
            doc = fetch(instance, args.ticket, os.environ["SNOW_USER"], os.environ["SNOW_TOKEN"])
        except urllib.error.HTTPError as exc:
            # Błąd wywołania NIE jest zgodą. Fail-closed: bez odpowiedzi z systemu rekordu nie ma PR-a.
            print(f"ServiceNow odpowiedziało {exc.code} — traktuję jako brak zatwierdzenia", file=sys.stderr)
            return 2

    problems = verify(doc, args.ticket, args.expect_project)
    if problems:
        for p in problems:
            print(f"ODRZUCONE: {p}", file=sys.stderr)
        return 1

    print(f"OK: {args.ticket} zatwierdzony przez zespół sieciowy dla {args.expect_project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
