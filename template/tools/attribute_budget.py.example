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

BASELINE MA KOSZT STAŁY PLUS JEDEN ATRYBUT NA CZŁONKA — i to jest cały sens jego kolapsu. `policy.yaml
§baseline_ingress` renderuje się jako JEDNA reguła na tytuł, z listą zasobów wszystkich członków
(terraform/locals.tf: `baseline_rules_all`), więc koszt to `stały_koszt_reguł + liczba_członków × liczba_reguł`,
a nie `koszt_reguł × liczba_członków`. Ta różnica decyduje o suficie perimetru: przy dwóch regułach baseline
(zmierzone na żywym ACM) było to 21 atrybutów na członka i sufit ~230 członków, po kolapsie 2 na członka.

Model liczenia MUSI odwzorowywać renderer, nie deklarację. Dwa miejsca, w których to boli:
  * `sources` — reguła z `allow_without_access_level: true` renderuje JEDEN blok źródła (`accessLevel: "*"`),
    mimo że `access_levels` w YAML jest puste. Liczenie samej listy z YAML dawało wynik mniejszy o 1 na regułę
    niż to, co API realnie trzyma — czyli guard niedoszacowywał dokładnie te reguły, które są wspólne dla
    wszystkich członków (a więc te, które przy skali kosztują najwięcej).
  * cele — po kolapsie baseline liczy tyle zasobów, ilu jest członków W DANEJ KONFIGURACJI (dry-run: wszyscy,
    enforced: tylko promowani), a nie „1", bo reguła nie należy już do jednego członka.

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


def baseline_sources_cost(rule: dict) -> int:
    """Liczba bloków `sources` W WYRENDEROWANEJ regule baseline — nie długość listy z YAML.

    Renderer (terraform/locals.tf, `baseline_rules_shape`) podstawia `accessLevel: "*"`, gdy reguła nie ma
    access levels, ale ma JAWNĄ flagę `allow_without_access_level`. Reguła bez jednego i bez drugiej nie
    dostaje źródła w ogóle — i wtedy nie autoryzuje niczego (zmierzone: `NO_MATCHING_ACCESS_LEVEL` mimo
    obecnej reguły), więc jej „zero" jest tu wierne, a nie zachowawcze.
    """
    poziomy = len(rule.get("access_levels", []) or [])
    if poziomy:
        return poziomy
    return 1 if rule.get("allow_without_access_level") else 0


def baseline_fixed_cost(rule: dict) -> int:
    """Koszt reguły baseline BEZ celów — część, która NIE rośnie z liczbą członków."""
    return len(rule.get("identities", [])) + baseline_sources_cost(rule) + operations_cost(rule)


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="-", help="declarations.json albo '-' dla stdin")
    ap.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input).read()
    doc = json.loads(raw)

    limit = doc["policy"]["attribute_budget"]["limit_per_config"]
    warn_pct = doc["policy"]["attribute_budget"]["warn_at_percent"]

    baseline = doc["policy"].get("baseline_ingress", []) or []

    # Baseline po kolapsie ma DWA składniki i tylko drugi rośnie z organizacją. Rozdzielamy je, bo to jest
    # liczba, którą planuje się pojemność: „ile jeszcze członków się zmieści" = (limit − stały) / marginalny.
    baseline_fixed = sum(baseline_fixed_cost(r) for r in baseline)
    baseline_per_member = len(baseline)  # jeden zasób (`projects/<numer>`) w każdej regule baseline

    per_member = {}  # koszt REGUŁ PROFILOWYCH członka — te zostały per członek świadomie (DEC-10)
    dry_run_members = 0
    enforced_members = 0
    dry_run_total = 0
    enforced_total = 0

    for name, member in doc["members"].items():
        cost = 0
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
        dry_run_members += 1
        dry_run_total += cost
        if member.get("stage") == "enforced":
            enforced_members += 1
            enforced_total += cost

    # Reguła bez ani jednego celu nie powstaje (renderer: `if length(baseline_targets_*) > 0`), więc przy
    # zerze członków baseline nie kosztuje nic. Doliczanie go „na zapas" zawyżałoby o konfigurację, której nie ma.
    if dry_run_members:
        dry_run_total += baseline_fixed + baseline_per_member * dry_run_members
    if enforced_members:
        enforced_total += baseline_fixed + baseline_per_member * enforced_members

    worst = max(dry_run_total, enforced_total)
    pct = round(100 * worst / limit, 1)
    over = pct >= warn_pct

    # Sufit liczony NAJDROŻSZYM członkiem, nie średnią: średnia mówi, ile zmieści się członków podobnych do
    # dzisiejszych, a pytanie brzmi „czy następny wniosek jeszcze wejdzie". Brak członków => brak jednostki.
    marginal = max(per_member.values(), default=0) + baseline_per_member
    headroom = (limit - baseline_fixed) // marginal if marginal else None

    if args.format == "json":
        json.dump({"limit": limit, "dry_run": dry_run_total, "enforced": enforced_total,
                   "worst_pct": pct, "over_threshold": over, "per_member": per_member,
                   "baseline_fixed": baseline_fixed, "baseline_per_member": baseline_per_member,
                   "marginal_per_member": marginal, "headroom_members": headroom},
                  sys.stdout, indent=2, sort_keys=True)
        print()
    else:
        bullet = "- " if args.format == "markdown" else "  "
        print(f"Budżet atrybutów (limit {limit} na konfigurację, próg {warn_pct}%)")
        print(f"{bullet}dry-run : {dry_run_total} ({round(100 * dry_run_total / limit, 1)}%)")
        print(f"{bullet}enforced: {enforced_total} ({round(100 * enforced_total / limit, 1)}%)")
        print(f"{bullet}baseline: {baseline_fixed} stałe + {baseline_per_member} na członka "
              f"({len(baseline)} reguł zbiorczych)")
        print(f"{bullet}koszt marginalny najdroższego członka: {marginal}"
              + (f" → sufit ~{headroom} członków" if headroom is not None else ""))
        print(f"{bullet}najwięksi konsumenci (same reguły profilowe):")
        for name, cost in sorted(per_member.items(), key=lambda kv: -kv[1])[:5]:
            print(f"{bullet}  {name}: {cost}")

    if over:
        print(f"\nPRZEKROCZONY PRÓG: {pct}% >= {warn_pct}%. Skonsoliduj profile albo rozważ drugi perimetr "
              f"(kryterium rewizji z DEC-1).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
