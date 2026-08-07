#!/usr/bin/env python3
"""Zrzuca ŻYWY perimetr do fragmentu policy.yaml — i pokazuje różnicę wobec tego, co jest w repo.

DLACZEGO ten skrypt istnieje: procedura przejęcia szkieletu (docs/4-brownfield-import.md) wymaga, żeby
`policy.yaml` opisywał rzeczywistość PRZED importem — inaczej pierwszy apply nadpisze cudzą listę
`restricted_services` treścią z repo. Przepisywanie tego ręcznie z `gcloud describe` to praca, w której
łatwo pominąć jedną usługę; a pominięta usługa oznacza wyłączenie ochrony, o którym nikt nie wie.

Kierunek jest jednoznaczny: **rzeczywistość → plik**, nigdy odwrotnie. Skrypt nie zmienia niczego w GCP.

Użycie:
    # 1. zobacz, co jest w chmurze i czym różni się od repo (NIC nie zapisuje)
    python3 tools/perimeter_to_policy.py --policy-id 123456789 --perimeter ai_core --diff

    # 2. gdy różnice są zrozumiałe — wygeneruj fragment do wklejenia
    python3 tools/perimeter_to_policy.py --policy-id 123456789 --perimeter ai_core > /tmp/live.yaml

Wymaga: gcloud z rolą accesscontextmanager.policyReader (odczyt), pyyaml.
"""
import argparse
import json
import pathlib
import subprocess
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("brakuje pyyaml: pip install pyyaml")


def describe(policy_id: str, perimeter: str) -> dict:
    """Odczyt perimetru przez gcloud. Świadomie NIE przez Terraform data source — takiego nie ma."""
    out = subprocess.run(
        ["gcloud", "access-context-manager", "perimeters", "describe", perimeter,
         "--policy", policy_id, "--format", "json"],
        capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"gcloud describe nie zadziałał:\n{out.stderr.strip()}")
    return json.loads(out.stdout)


def to_policy_fragment(live: dict) -> dict:
    """Mapuje odpowiedź API na kształt naszego policy.yaml.

    UWAGA: bierzemy `status` (konfigurację EGZEKWOWANĄ), bo to ona jest obowiązującym stanem. Jeśli perimetr
    ma też `spec` (dry-run) o innej treści, skrypt to zgłasza — bo import szkieletu, który ma rozjechane
    obie konfiguracje, wymaga świadomej decyzji, którą z nich uznajemy za docelową.
    """
    status = live.get("status", {}) or {}
    spec = live.get("spec", {}) or {}

    fragment = {
        "perimeter": {
            # Nazwa techniczna z pełnej ścieżki accessPolicies/<id>/servicePerimeters/<nazwa>.
            "name": live["name"].rsplit("/", 1)[-1],
            "title": live.get("title", ""),
            # Po imporcie zarządzamy szkieletem — ale flagę przełącza CZŁOWIEK, po pustym planie.
            "manage_skeleton": False,
        },
        "restricted_services": sorted(status.get("restrictedServices", [])),
        "vpc_accessible_services": {
            "enable_restriction": bool(
                (status.get("vpcAccessibleServices") or {}).get("enableRestriction", False)),
            # Nasz model trzyma tę listę 1:1 z restricted_services. Jeśli w chmurze jest inaczej, zgłaszamy
            # to jako różnicę do rozstrzygnięcia — cicha „normalizacja" byłaby zmianą zakresu ochrony.
            "same_as_restricted": sorted((status.get("vpcAccessibleServices") or {}).get("allowedServices", []))
            == sorted(status.get("restrictedServices", [])),
        },
    }

    notes = []
    if spec and spec.get("restrictedServices") != status.get("restrictedServices"):
        notes.append(
            "UWAGA: konfiguracja dry-run (spec) ma INNĄ listę restricted_services niż egzekwowana (status). "
            "Import szkieletu wymaga decyzji, która z nich jest docelowa — nasz renderer wypełni obie tą samą.")
    live_allowed = sorted((status.get("vpcAccessibleServices") or {}).get("allowedServices", []))
    if live_allowed and live_allowed != sorted(status.get("restrictedServices", [])):
        notes.append(
            f"UWAGA: vpc_accessible_services w chmurze ({len(live_allowed)} usług) NIE jest równe "
            f"restricted_services ({len(status.get('restrictedServices', []))}). Nasz model zakłada 1:1 — "
            "jeśli tak ma zostać, trzeba rozszerzyć renderer, a nie „poprawić" listę.")
    if status.get("resources"):
        notes.append(
            f"INFO: perimetr ma już {len(status['resources'])} projektów w konfiguracji egzekwowanej. "
            "Nie trafiają one do policy.yaml — członkostwo opisują pliki w perimeter/members/. "
            "Zaimportuj je osobno albo zostaw pod zarządzaniem obecnego właściciela (ignore_changes).")
    if status.get("ingressPolicies") or status.get("egressPolicies"):
        notes.append(
            f"INFO: perimetr ma {len(status.get('ingressPolicies', []))} reguł ingress i "
            f"{len(status.get('egressPolicies', []))} egress. Te też NIE są w policy.yaml — "
            "przy `manage_skeleton: true` chroni je `ignore_changes`, więc apply ich nie ruszy.")
    return fragment, notes


def diff_against_repo(fragment: dict, repo_policy: pathlib.Path) -> int:
    """Porównuje kluczowe pola i zwraca liczbę różnic. Nie modyfikuje pliku."""
    if not repo_policy.exists():
        print(f"  (brak {repo_policy} — nie ma z czym porównać)")
        return 0

    repo = yaml.safe_load(repo_policy.read_text())
    diffs = 0

    live_name = fragment["perimeter"]["name"]
    repo_name = (repo.get("perimeter") or {}).get("name")
    if live_name != repo_name:
        print(f"  RÓŻNICA  perimeter.name: repo={repo_name!r} chmura={live_name!r}")
        print("           → to jest ta pomyłka, po której dokładasz członków do NIEISTNIEJĄCEGO perimetru")
        diffs += 1

    live_svc = set(fragment["restricted_services"])
    repo_svc = set(repo.get("restricted_services", []))
    only_cloud = sorted(live_svc - repo_svc)
    only_repo = sorted(repo_svc - live_svc)
    if only_cloud:
        print(f"  RÓŻNICA  restricted_services tylko w CHMURZE ({len(only_cloud)}): {', '.join(only_cloud)}")
        print("           → apply po imporcie USUNĄŁBY ochronę tych usług")
        diffs += 1
    if only_repo:
        print(f"  RÓŻNICA  restricted_services tylko w REPO ({len(only_repo)}): {', '.join(only_repo)}")
        print("           → apply po imporcie DODAŁBY ochronę tych usług (może zablokować ruch)")
        diffs += 1

    if not diffs:
        print("  ZGODNE   policy.yaml opisuje rzeczywistość — plan po imporcie powinien być pusty")
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy-id", required=True, help="numer org-level access policy")
    ap.add_argument("--perimeter", required=True, help="nazwa TECHNICZNA perimetru")
    ap.add_argument("--diff", action="store_true", help="porównaj z perimeter/policy.yaml, nic nie wypisuj na stdout")
    ap.add_argument("--repo-policy", default="perimeter/policy.yaml")
    args = ap.parse_args()

    live = describe(args.policy_id, args.perimeter)
    fragment, notes = to_policy_fragment(live)

    for n in notes:
        print(f"  {n}", file=sys.stderr)

    if args.diff:
        print(f"\n== różnice: chmura vs {args.repo_policy} ==")
        return 1 if diff_against_repo(fragment, pathlib.Path(args.repo_policy)) else 0

    print("# Wygenerowane z ŻYWEGO perimetru — wklej do perimeter/policy.yaml i porównaj resztę pól ręcznie.")
    print("# Kierunek jest jednoznaczny: rzeczywistość → plik. Nigdy odwrotnie.")
    print(yaml.safe_dump(fragment, sort_keys=False, allow_unicode=True), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
