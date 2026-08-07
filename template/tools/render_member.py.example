#!/usr/bin/env python3
"""Renderuje plik członka z zatwierdzonego ticketu. Używany przez workflow intake.

DLACZEGO osobny skrypt, a nie heredoc w workflow: `stage: dry-run` i data przeglądu muszą być USTAWIANE
PRZEZ KOD, nie przepisywane z payloadu. Gdyby wnioskodawca mógł podać `stage`, ominąłby całą dwustopniowość
onboardingu jednym polem w formularzu.

Użycie (patrz .github/workflows/intake.yml):
    python3 tools/render_member.py --division risk --project-id prj-x --project-number 1 \\
        --owner-group grp@example.com --change-ref snow:RITM0000001 --approved-by net@example.com \\
        --profiles-json '[{"name":"vertex-online-serving","params":{...}}]' --out perimeter/members/risk-prj-x.yaml
"""
import argparse
import datetime
import json
import pathlib

import yaml

REVIEW_AFTER_DAYS = 180  # pół roku — wpis bez potwierdzenia wygasa (expiry-sweep otwiera PR offboardingowy)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--division", required=True)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--project-number", required=True)
    ap.add_argument("--owner-group", required=True)
    ap.add_argument("--change-ref", required=True, help="snow:RITM… | pr:ORG/repo#123 | manual:<uzasadnienie>")
    ap.add_argument("--approved-by", required=True)
    ap.add_argument("--profiles-json", required=True)
    ap.add_argument("--today", default=datetime.date.today().isoformat())
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    today = datetime.date.fromisoformat(args.today)
    member = {
        "schema_version": 1,
        "division": args.division,
        "project_id": args.project_id,
        # str(): numery projektów przekraczają bezpieczny zakres integerów w części parserów YAML.
        "project_number": str(args.project_number),
        "owner_group": args.owner_group,
        "change_ref": args.change_ref,
        "approved_by": args.approved_by,
        # NIE z payloadu — zawsze dry-run. Promocja to osobny PR z człowiekiem (DEC-4).
        "stage": "dry-run",
        "dry_run_since": today.isoformat(),
        "review_by": (today + datetime.timedelta(days=REVIEW_AFTER_DAYS)).isoformat(),
        "profiles": json.loads(args.profiles_json),
        "exceptions": [],
    }

    out = pathlib.Path(args.out)

    # Plik członka JUŻ ISTNIEJE = ten projekt jest w perimetrze. Nadpisanie go wyglądałoby jak onboarding,
    # a byłoby przepisaniem cudzego wpisu — w tym CICHYM cofnięciem `stage: enforced` do `dry-run`, bo
    # słownik wyżej zawsze ustawia dry-run. Projekt straciłby realną ochronę PR-em zatytułowanym „onboard",
    # przechodzącym bramki (nowy stan `dry-run` nie łamie żadnej reguły promocji) i kwalifikującym się do
    # auto-merge'a jako „dodanie do dry-run". Duplikat w DWÓCH plikach łapie reguła OPA po project_number —
    # ten sam projekt pod tą samą nazwą pliku nie tworzy drugiego pliku, więc tam nie ma czego złapać.
    # Zmiana profili i promocja idą PR-em na istniejącym pliku (docs/3-runbook-promocja-i-break-glass.md).
    if out.exists():
        existing = yaml.safe_load(out.read_text()) or {}
        raise SystemExit(
            f"{out} juz istnieje — projekt {args.project_id} jest czlonkiem perimetru "
            f"(stage: {existing.get('stage', '?')}, change_ref: {existing.get('change_ref', '?')}). "
            "To nie jest onboarding: zmiane profili albo promocje zglos PR-em na istniejacym pliku."
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(member, sort_keys=False, allow_unicode=True))
    print(f"zapisano {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
