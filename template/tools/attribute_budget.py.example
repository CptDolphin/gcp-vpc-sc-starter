#!/usr/bin/env python3
"""Guard budżetu atrybutów perimetru.

Perimetr ma limit 6000 atrybutów NA KONFIGURACJĘ, liczony osobno dla egzekwowanej i dry-run
(https://docs.cloud.google.com/vpc-service-controls/quotas). Każda tożsamość, access level, zasób, usługa
i metoda w regule konsumuje ten budżet.

DLACZEGO guard, skoro API i tak odrzuci przepełnienie: odrzuci je przy APPLY — czyli po review, po
zatwierdzeniu ticketu i po tym, jak dywizja usłyszała „zrobione". Guard przesuwa tę informację na PR i robi
to z progiem (domyślnie 70%), żeby był czas na reakcję: konsolidację profili albo decyzję o drugim perimetrze.

Liczymy ZACHOWAWCZO (raczej przeszacowanie): dokładna definicja „atrybutu" po stronie Google nie jest
publicznie policzalna, a guard, który niedoszacowuje, jest gorszy niż żaden — dawałby fałszywe poczucie zapasu.

Użycie:
    python3 tools/collect_declarations.py | python3 tools/attribute_budget.py
    python3 tools/attribute_budget.py --input declarations.json --format markdown
"""
import argparse
import json
import sys


def rule_cost(rule: dict, params: dict) -> int:
    """Koszt jednej reguły profilu po podstawieniu parametrów członka."""
    cost = 0
    cost += len(params.get(rule.get("identities_from", ""), []))
    cost += len(params.get(rule.get("access_levels_from", ""), []))
    cost += len(params.get(rule.get("to_projects_from", ""), [])) or (1 if rule.get("to") else 0)
    for op in rule.get("operations", []):
        cost += 1 + len(op.get("methods", []))  # usługa + metody
    return cost


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="-", help="declarations.json albo '-' dla stdin")
    ap.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input).read()
    doc = json.loads(raw)

    limit = doc["policy"]["attribute_budget"]["limit_per_config"]
    warn_pct = doc["policy"]["attribute_budget"]["warn_at_percent"]

    per_member = {}
    dry_run_total = 0
    enforced_total = 0

    for name, member in doc["members"].items():
        cost = 0
        for entry in member.get("profiles", []):
            profile = doc["profiles"].get(entry["name"])
            if profile is None:
                continue  # brak profilu łapie osobna reguła OPA — tu nie zgadujemy kosztu
            for rule in profile.get("ingress", []) + profile.get("egress", []):
                cost += rule_cost(rule, entry.get("params", {}))
        per_member[name] = cost
        # Konfiguracja dry-run zawiera WSZYSTKICH członków (także już egzekwowanych) — patrz komentarz
        # w terraform/locals.tf: dzięki temu promocja jest addytywna i nie ma okna bez ochrony.
        dry_run_total += cost
        if member.get("stage") == "enforced":
            enforced_total += cost

    worst = max(dry_run_total, enforced_total)
    pct = round(100 * worst / limit, 1)
    over = pct >= warn_pct

    if args.format == "json":
        json.dump({"limit": limit, "dry_run": dry_run_total, "enforced": enforced_total,
                   "worst_pct": pct, "over_threshold": over, "per_member": per_member},
                  sys.stdout, indent=2, sort_keys=True)
        print()
    else:
        bullet = "- " if args.format == "markdown" else "  "
        print(f"Budżet atrybutów (limit {limit} na konfigurację, próg {warn_pct}%)")
        print(f"{bullet}dry-run : {dry_run_total} ({round(100 * dry_run_total / limit, 1)}%)")
        print(f"{bullet}enforced: {enforced_total} ({round(100 * enforced_total / limit, 1)}%)")
        print(f"{bullet}najwięksi konsumenci:")
        for name, cost in sorted(per_member.items(), key=lambda kv: -kv[1])[:5]:
            print(f"{bullet}  {name}: {cost}")

    if over:
        print(f"\nPRZEKROCZONY PRÓG: {pct}% >= {warn_pct}%. Skonsoliduj profile albo rozważ drugi perimetr "
              f"(kryterium rewizji z DEC-1).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
