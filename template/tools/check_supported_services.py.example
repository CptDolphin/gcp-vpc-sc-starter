#!/usr/bin/env python3
"""Konfrontuje policy.yaml z ŻYWĄ listą usług wspieranych przez VPC Service Controls.

DLACZEGO to istnieje: bez tej bramki błąd wychodzi dopiero na `apply`, czyli w momencie, w którym pipeline
już zaczął zmieniać obiekt o zasięgu całej organizacji. Zmierzone: domyślny baseline zawierał
`colab.googleapis.com`, którego VPC-SC nie wspiera — 115 zielonych bramek lokalnych tego nie widziało, bo
żadna nie rozmawia z API. Pierwszy apply padał na `Error 400: Service ... is not supported`.

DLACZEGO w `plan.yml`, a nie w `validate.yml`: to jedyne miejsce w pipeline, które ma już poświadczenia GCP.
`validate.yml` jest celowo offline (schematy, OPA, budżet) i ma taki zostać — bramka wymagająca chmury
zamieniłaby szybki feedback na PR w oczekiwanie na token.

Trzy sprawdzenia, każde zamyka inny tryb awarii:

  1. każda usługa z `restricted_services` JEST wspierana  → apply na org-plane nie pada na literówce
  2. każda usługa z `services_without_method_selectors` faktycznie NIE publikuje metod
     → nikt nie przemyci `*` dla usługi, dla której da się wypisać metody (np. storage)
  3. każda usługa, która metod NIE publikuje, a jest w `restricted_services`, JEST na liście wyjątków
     → profil użyje `*` i przejdzie bramkę OPA, zamiast paść na apply

Użycie (patrz .github/workflows/plan.yml):
    python3 tools/check_supported_services.py --policy perimeter/policy.yaml
"""
import argparse
import json
import pathlib
import subprocess
import sys

import yaml


def gcloud_json(args: list[str]) -> object:
    """Wywołanie gcloud z czytelnym błędem — bez tego padnie na json.loads pustego stringa."""
    p = subprocess.run(["gcloud", *args, "--format=json"], capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"gcloud {' '.join(args)} zwrocilo {p.returncode}: {p.stderr.strip()[:300]}")
    return json.loads(p.stdout or "[]")


def zbierz_operacje(sciezka_policy: str, katalog_profili: str):
    """Zwraca (zrodlo, operacje) z baseline_ingress i ze wszystkich profili.

    Jedno miejsce zbierania, bo obie ścieżki renderują się do tego samego kształtu reguły w API — a błąd
    w nazwie metody wygląda identycznie niezależnie od tego, czy przyszedł z baseline'u, czy z profilu.
    """
    polityka = yaml.safe_load(open(sciezka_policy))
    for regula in polityka.get("baseline_ingress") or []:
        yield f"policy.yaml baseline_ingress[{regula.get('title')}]", regula.get("operations") or []

    katalog = pathlib.Path(katalog_profili)
    if not katalog.is_dir():
        return
    for plik in sorted(katalog.glob("*.yaml")):
        profil = yaml.safe_load(plik.read_text()) or {}
        for kierunek in ("ingress", "egress"):
            for regula in profil.get(kierunek) or []:
                yield f"profiles/{plik.name} [{regula.get('title')}]", regula.get("operations") or []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="perimeter/policy.yaml")
    ap.add_argument("--profiles", default="perimeter/profiles", help="katalog profili — sprawdzenie nazw metod")
    args = ap.parse_args()

    polityka = yaml.safe_load(open(args.policy))
    restricted = list(polityka.get("restricted_services") or [])
    bez_metod_zadeklarowane = set(polityka.get("services_without_method_selectors") or [])

    wspierane = {s["name"] for s in gcloud_json(["access-context-manager", "supported-services", "list"])}
    print(f"usług wspieranych przez VPC-SC: {len(wspierane)}")

    problemy: list[str] = []

    # 1. Nieobsługiwana usługa w baseline = apply padnie na obiekcie org-plane.
    for s in restricted:
        if s not in wspierane:
            problemy.append(
                f"{s}: NIE jest wspierane przez VPC Service Controls — usuń z restricted_services "
                f"(pełna lista: gcloud access-context-manager supported-services list)")

    # 2 i 3 wymagają zapytania per usługa o `supportedMethods`. Pytamy tylko o usługi, które nas dotyczą.
    do_sprawdzenia = sorted(set(restricted) & wspierane | (bez_metod_zadeklarowane & wspierane))
    bez_metod_realnie = set()
    for s in do_sprawdzenia:
        opis = gcloud_json(["access-context-manager", "supported-services", "describe", s])
        if not opis.get("supportedMethods"):
            bez_metod_realnie.add(s)

    # 2. Deklaracja szersza niż rzeczywistość = próba przemycenia `*` tam, gdzie metody da się wypisać.
    for s in sorted(bez_metod_zadeklarowane & wspierane - bez_metod_realnie):
        problemy.append(
            f"{s}: jest w services_without_method_selectors, ale API PUBLIKUJE dla niej metody — "
            f"wypisz je jawnie w profilu zamiast dopuszczać \"*\"")

    # 3. Deklaracja węższa niż rzeczywistość = profil wypisze metody i padnie dopiero na apply.
    for s in sorted(bez_metod_realnie - bez_metod_zadeklarowane):
        problemy.append(
            f"{s}: API nie publikuje dla niej metod, a nie ma jej w services_without_method_selectors — "
            f"profil z jawnymi metodami padnie na apply (Error 400: METHOD ... is not supported)")

    # 4. Nazwy metod. Konwencja RÓŻNI SIĘ per usługa i nie da się jej zgadnąć: storage używa
    #    `google.storage.buckets.get`, compute `InstancesService.Get`, bigquery `TableService.GetTable`.
    #    Zmyślona nazwa przechodzi schemat i OPA, a pada dopiero na apply — dokładnie w tym miejscu, w którym
    #    pipeline już zmienia politykę produkcyjną.
    metody_api: dict[str, set[str]] = {}
    for zrodlo, operacje in zbierz_operacje(args.policy, args.profiles):
        for op in operacje:
            usluga, metody = op.get("service"), op.get("methods") or []
            uprawnienia = op.get("permissions") or []

            # SELEKTORY `permission` NIE SĄ WERYFIKOWALNE TĄ LISTĄ i to nie jest luka do „domknięcia
            # kiedyś", tylko zmierzona właściwość API. Reguła egress z `external_resources` przyjmuje
            # DOKŁADNIE JEDNO uprawnienie — `externalResource.read` — którego `supported-services` dla
            # bigquery NIE WYMIENIA (75 uprawnień, tego wśród nich nie ma). Odwrotnie: `bigquery.jobs.create`
            # i `bigquery.tables.getData` NA TEJ LIŚCIE SĄ, a perimetr odrzuca je komunikatem
            # `PERMISSION ... is not supported`. Lista kłamie w OBIE strony, więc porównywanie z nią
            # zamieniłoby jedyną działającą regułę BigQuery Omni w czerwony pipeline.
            # Wartości pilnuje zamiast tego reguła OPA `dozwolone_uprawnienia_zewnetrzne` (policy/onboarding.rego),
            # zbudowana z POMIARU, a nie z katalogu. Zmierzone 2026-08-11.
            if uprawnienia:
                continue
            if usluga not in wspierane or "*" in metody:
                continue
            if usluga not in metody_api:
                opis = gcloud_json(["access-context-manager", "supported-services", "describe", usluga])
                metody_api[usluga] = {m["method"] for m in opis.get("supportedMethods", []) if "method" in m}
            znane = metody_api[usluga]
            if not znane:
                # Usługa nie publikuje ANI JEDNEJ metody — jedyne, co API przyjmuje, to `*`. Jawna metoda
                # jest tu zawsze błędem, a poprzednia wersja tego warunku (`if znane and ...`) po cichu ją
                # przepuszczała: pusty zbiór jest falsy, więc pętla nie miała czego porównać.
                problemy.append(
                    f"{zrodlo}: {usluga} nie publikuje metod — użyj methods: [\"*\"] zamiast {metody}")
                continue
            for m in metody:
                if m not in znane:
                    podobne = sorted(k for k in znane if k.split(".")[-1].lower() == m.split(".")[-1].lower())[:3]
                    problemy.append(
                        f"{zrodlo}: metoda {m!r} nie istnieje w {usluga}"
                        + (f" — może chodziło o {', '.join(podobne)}?" if podobne else ""))

    for p in problemy:
        print(f"  BŁĄD   {p}")
    if problemy:
        print(f"\nNIEZALICZONE ({len(problemy)}) — popraw perimeter/policy.yaml przed apply.", file=sys.stderr)
        return 1

    print(f"  OK     {len(restricted)} usług baseline wspieranych; "
          f"lista bez selektorów metod zgodna z API ({len(bez_metod_realnie)} usług)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
