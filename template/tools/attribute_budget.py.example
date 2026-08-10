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
Stąd `1 +` przy każdej operacji: nazwa usługi doliczana obok selektorów metod, których Google wymienia wprost.

CO LICZYMY, A CZEGO NIE: limit dotyczy atrybutów W REGUŁACH ingress/egress (odwołania do projektów, sieci,
access levels, selektorów metod, tożsamości i ról). `restricted_services`, `vpc_accessible_services` i sama
lista członków perimetru mają WŁASNE, osobne limity — doliczanie ich tutaj mieszałoby dwa różne budżety.

REGUŁY BASELINE LICZĄ SIĘ TAK SAMO JAK PROFILOWE i to nie jest szczegół. `policy.yaml §baseline_ingress`
renderuje się dla KAŻDEGO członka (terraform/locals.tf: `baseline_rules_all` → `ingress_rules_effective`),
więc jego koszt to `koszt_reguł × liczba_członków`. Pominięcie baseline'u zaniżało wynik o stałą wartość na
każdego członka — czyli tym mocniej, im bliżej limitu repo naprawdę było. Zmierzone na żywym perimetrze:
narzędzie raportowało 5 atrybutów, gdy API trzymało 20 (jedna reguła baseline = 15) — 4× za mało.

Użycie:
    python3 tools/collect_declarations.py | python3 tools/attribute_budget.py
    python3 tools/attribute_budget.py --input declarations.json --format markdown
"""
import argparse
import json
import sys


def operations_cost(rule: dict) -> int:
    """Usługa + każdy selektor metody. `methods: ["*"]` to jeden selektor, nie zero."""
    return sum(1 + len(op.get("methods", [])) for op in rule.get("operations", []))


def profile_rule_cost(rule: dict, params: dict, direction: str) -> int:
    """Koszt reguły profilu po podstawieniu parametrów członka. -1 = reguła w ogóle nie powstanie.

    Renderer (terraform/locals.tf) pomija regułę egress bez ani jednego celu — ani projektu, ani zasobu
    zewnętrznego. Doliczanie jej tożsamości i operacji zawyżałoby budżet o regułę, której w konfiguracji
    nie ma, a guard ma opisywać konfigurację, nie deklarację.
    """
    to_projects = len(params.get(rule.get("to_projects_from", ""), []))
    to_external = len(params.get(rule.get("to_external_from", ""), []))

    if direction == "egress" and to_projects + to_external == 0:
        return -1

    # Ingress zawsze celuje w projekt członka (`to: member_project` → jeden zasób). Egress celuje w to,
    # co członek wypisał: projekty w GCP i/lub zasoby zewnętrzne BigQuery Omni — te ostatnie API liczy
    # osobnym polem `externalResources`, więc konsumują budżet dokładnie tak samo jak `resources`.
    targets = 1 if direction == "ingress" else to_projects + to_external

    return (len(params.get(rule.get("identities_from", ""), []))
            + len(params.get(rule.get("access_levels_from", ""), []))
            + targets
            + operations_cost(rule))


def baseline_rule_cost(rule: dict) -> int:
    """Koszt jednej reguły baseline DLA JEDNEGO członka.

    Baseline nie ma parametrów — tożsamości i access levels stoją wprost w `policy.yaml`. Cel jest zawsze
    jeden: projekt członka (locals.tf renderuje `resources = ["projects/<numer>"]`).
    """
    return (len(rule.get("identities", []))
            + len(rule.get("access_levels", []))
            + 1
            + operations_cost(rule))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="-", help="declarations.json albo '-' dla stdin")
    ap.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input).read()
    doc = json.loads(raw)

    limit = doc["policy"]["attribute_budget"]["limit_per_config"]
    warn_pct = doc["policy"]["attribute_budget"]["warn_at_percent"]

    # Baseline dotyczy KAŻDEGO członka — liczymy jego koszt raz i doliczamy każdemu z osobna. To jest ta
    # pozycja, która przy trzydziestu dywizjach zjada większość budżetu, choć w żadnym pliku członka nie widać.
    baseline_per_member = sum(baseline_rule_cost(r) for r in doc["policy"].get("baseline_ingress", []))

    per_member = {}
    dry_run_total = 0
    enforced_total = 0

    for name, member in doc["members"].items():
        cost = baseline_per_member
        for entry in member.get("profiles", []):
            profile = doc["profiles"].get(entry["name"])
            if profile is None:
                continue  # brak profilu łapie osobna reguła OPA — tu nie zgadujemy kosztu
            for direction in ("ingress", "egress"):
                for rule in profile.get(direction, []):
                    koszt = profile_rule_cost(rule, entry.get("params", {}), direction)
                    if koszt >= 0:
                        cost += koszt
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
