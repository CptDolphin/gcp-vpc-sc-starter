#!/usr/bin/env python3
"""Zbiera deklaracje z perimeter/ do jednego dokumentu JSON — wejścia dla OPA i dla guardu budżetu.

DLACZEGO osobny krok, a nie „conftest na katalogu YAML": reguły onboardingu potrzebują KONTEKSTU —
policy.yaml, katalogu profili, dzisiejszej daty i (przy promocji) liczby naruszeń z okna obserwacji.
Conftest ocenia jeden plik naraz i o pozostałych nie wie, więc reguła „profil, o który prosi ten członek,
istnieje" byłaby niewyrażalna.

Użycie:
    python3 tools/collect_declarations.py                       > declarations.json
    python3 tools/collect_declarations.py --violations v.json   > declarations.json
    python3 tools/collect_declarations.py --today 2026-08-15    # do testów okna dry-run
"""
import argparse
import datetime
import json
import pathlib
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("brakuje pyyaml: pip install pyyaml")


def load_dir(path: pathlib.Path) -> dict:
    """Wszystkie *.yaml z katalogu, kluczowane nazwą pliku bez rozszerzenia."""
    if not path.is_dir():
        return {}
    return {f.stem: yaml.safe_load(f.read_text()) for f in sorted(path.glob("*.yaml"))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="perimeter", help="katalog z deklaracjami")
    ap.add_argument("--today", default=datetime.date.today().isoformat(),
                    help="data odniesienia dla okna dry-run (domyślnie dziś)")
    ap.add_argument("--violations", help="JSON {nazwa_członka: liczba_naruszeń} z violations-report")
    args = ap.parse_args()

    root = pathlib.Path(args.root)
    policy = yaml.safe_load((root / "policy.yaml").read_text())

    # access-levels trzymamy jako listę plików, ale reguły potrzebują płaskiej mapy nazwa → definicja:
    # sprawdzają, czy access level, o który prosi członek, w ogóle istnieje.
    access_levels = {}
    for doc in load_dir(root / "access-levels").values():
        for al in doc.get("access_levels", []):
            access_levels[al["name"]] = al

    # Mapowanie repo→projekty dla kanału `pr:`. Brak pliku = brak kanału zewnętrznego (bezpieczna
    # degradacja: reguła OPA odrzuci wtedy każde zgłoszenie `pr:`, zamiast je przepuścić).
    contributors_file = root / "contributors.yaml"
    contributors = []
    if contributors_file.exists():
        contributors = yaml.safe_load(contributors_file.read_text()).get("contributors", [])

    violations = {}
    if args.violations:
        violations = json.loads(pathlib.Path(args.violations).read_text())

    json.dump(
        {
            "policy": policy,
            "profiles": load_dir(root / "profiles"),
            "members": load_dir(root / "members"),
            "access_levels": access_levels,
            "contributors": contributors,
            "today": args.today,
            # Brak klucza dla członka ≠ zero naruszeń. Reguła promotion_gate traktuje brak wpisu jako
            # „brak dowodu" i blokuje promocję — inaczej wystarczyłoby nie uruchomić raportu.
            "violations_last_window": violations,
        },
        sys.stdout,
        indent=2,
        sort_keys=True,
    )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
