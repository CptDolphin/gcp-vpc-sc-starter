#!/usr/bin/env python3
"""Zbiera deklaracje z perimeter/ do jednego dokumentu JSON — wejścia dla OPA i dla guardu budżetu.

DLACZEGO osobny krok, a nie „conftest na katalogu YAML": reguły onboardingu potrzebują KONTEKSTU —
policy.yaml, katalogu profili, dzisiejszej daty i (przy promocji) liczby naruszeń z okna obserwacji.
Conftest ocenia jeden plik naraz i o pozostałych nie wie, więc reguła „profil, o który prosi ten członek,
istnieje" byłaby niewyrażalna.

Użycie:
    python3 tools/collect_declarations.py                       > declarations.json
    python3 tools/collect_declarations.py --violations v.json   > declarations.json
    python3 tools/collect_declarations.py --contract c.json     > declarations.json
    python3 tools/collect_declarations.py --today 2026-08-15    # do testów okna dry-run

Członkowie przychodzą z JEDNEGO pliku `perimeter/projects.yaml` (DEC-12), a czyta go `tools/projects_file.py`
— nigdy `yaml.safe_load` wprost. Powód jest w nagłówku tamtego modułu: `safe_load` na duplikacie klucza
CICHO bierze ostatni, a przy pliku wspólnym duplikat jest normalnym wynikiem scalenia, nie egzotyką.
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

import projects_file


def load_dir(path: pathlib.Path) -> dict:
    """Wszystkie *.yaml z katalogu, kluczowane nazwą pliku bez rozszerzenia."""
    if not path.is_dir():
        return {}
    return {f.stem: yaml.safe_load(f.read_text()) for f in sorted(path.glob("*.yaml"))}


# Wersja schematu kontraktu, którą to narzędzie umie przeczytać. Kontrakt w innej wersji traktujemy jak
# jego BRAK, a nie „pewnie pola się nie zmieniły": pole `stage` jest tu wejściem bramki bezpieczeństwa,
# więc zgadywanie kształtu po numerze, którego nie znamy, jest dokładnie tym, czego wersjonowanie miało
# zabronić. Podniesienie wersji w terraform/contract.tf wymaga świadomego podniesienia jej TUTAJ.
WERSJA_KONTRAKTU = 1


def etapy_z_kontraktu(sciezka: pathlib.Path) -> tuple[dict, bool]:
    """Mapa klucz_członka → etap ZASTOSOWANY, plus flaga „dało się to ustalić".

    Kontrakt (`terraform/contract.tf`) publikuje po KAŻDYM apply m.in. `division`, `project_id` i `stage`
    każdego członka. To jedyne w tym repozytorium źródło mówiące, co NAPRAWDĘ zostało włączone — pliki
    w `perimeter/` mówią, czego chcemy. Bramka promocji potrzebuje różnicy między jednym a drugim, bo
    pyta o PRZEJŚCIE do `enforced`, a nie o sam stan `enforced` (patrz policy/onboarding.rego).

    ZWRACAMY FLAGĘ, A NIE SAMĄ MAPĘ. Pusta mapa jest dwuznaczna: „kontraktu nie ma" kontra „kontrakt jest
    i nie publikuje członków". Reguła OPA musi te przypadki traktować tak samo (fail-closed), ale musi też
    móc odróżnić je od „kontrakt jest, członków publikuje, tego akurat w nim nie ma" — bo to trzecie jest
    normalnym stanem członka przed pierwszym apply i również ma żądać dowodu.

    KAŻDY POWÓD, DLA KTÓREGO NIE UMIEMY ODCZYTAĆ ETAPÓW, DAJE `False` — nie wyjątek. Wywrócenie się tutaj
    zamieniłoby uszkodzony artefakt (a jest pobierany po sieci) w czerwone WSZYSTKIM pull requestom;
    `False` czyni surowszą wyłącznie bramkę promocji, czyli degraduje w stronę bezpieczną i wąską.
    Powód idzie na stderr — cicha degradacja bezpiecznej strony też jest cicha.
    """
    try:
        dokument = json.loads(sciezka.read_text())
    except (OSError, ValueError) as e:
        print(f"kontrakt nieczytelny ({e}) — stan zastosowany NIEZNANY, bramka promocji zostaje uzbrojona",
              file=sys.stderr)
        return {}, False

    if dokument.get("schema_version") != WERSJA_KONTRAKTU:
        print(f"kontrakt w wersji {dokument.get('schema_version')!r}, umiem {WERSJA_KONTRAKTU} — "
              "stan zastosowany NIEZNANY", file=sys.stderr)
        return {}, False

    # `is not True`, nie `not …`: pole musi być JAWNIE prawdziwe. Brak pola (stary kontrakt) albo `null`
    # znaczy „nie wiadomo, czy lista członków jest kompletna", a niekompletna lista wygląda dokładnie tak
    # samo jak lista, na której członka nie ma — czyli dałaby fałszywe „to nie jest przejście".
    if dokument.get("members_published") is not True:
        print("kontrakt nie publikuje listy członków (publish_members: false) — stan zastosowany NIEZNANY",
              file=sys.stderr)
        return {}, False

    try:
        # Klucz składany DOKŁADNIE tak jak w projects_file.klucz() — ten sam ciąg jest adresem zasobu
        # w stanie Terraform i kluczem mapy `members`, więc druga definicja byłaby drugim zbiorem członków.
        etapy = {f"{m['division']}-{m['project_id']}": m["stage"] for m in dokument["members"]}
    except (KeyError, TypeError) as e:
        # Wpis bez `stage` albo bez pary dywizja/projekt czyni CAŁĄ listę niewiarygodną: nie wiadomo, czy
        # brakuje jednego pola, czy kontrakt opisuje coś innego niż myślimy. Częściowa mapa dałaby ciche
        # „tego członka nie ma w kontrakcie" — czyli poprawny werdykt z niepoprawnego powodu.
        print(f"kontrakt ma wpis członka bez wymaganych pól ({e}) — stan zastosowany NIEZNANY",
              file=sys.stderr)
        return {}, False
    return etapy, True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="perimeter", help="katalog z deklaracjami")
    ap.add_argument("--today", default=datetime.date.today().isoformat(),
                    help="data odniesienia dla okna dry-run (domyślnie dziś)")
    ap.add_argument("--violations", help="JSON {nazwa_członka: liczba_naruszeń} z violations-report")
    ap.add_argument("--contract", help="contract.json z ostatniego apply — STAN ZASTOSOWANY (etap per członek)")
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

    # Brak `--contract` = stan zastosowany NIEZNANY, a nie „nic nie jest jeszcze enforced". Różnica jest
    # cała w tym, że bramka promocji zostaje wtedy uzbrojona (fail-closed), zamiast przepuszczać.
    applied_stages, applied_known = ({}, False)
    if args.contract:
        applied_stages, applied_known = etapy_z_kontraktu(pathlib.Path(args.contract))

    # CZŁONKOWIE IDĄ DO OPA W DWÓCH POSTACIACH I TO NIE JEST REDUNDANCJA — to jedyny sposób, żeby bramka
    # duplikatu miała czego pilnować.
    #
    # `members` (mapa klucz→wpis) jest tym, co czyta reszta reguł, kontrakt, budżet i raport naruszeń —
    # dokładnie tak samo, jak przy pliku na projekt, gdzie kluczem była nazwa pliku. Mapa jednak GUBI
    # duplikaty z definicji: dwa wpisy o tym samym kluczu dadzą jeden element i żadna reguła nie zobaczy,
    # że drugi kiedykolwiek istniał (ZMIERZONE: to samo robi `yamldecode` Terraforma i `yaml.safe_load`).
    #
    # `members_list` to surowa lista z pliku, w kolejności zapisu, z duplikatami. Reguły `vpcsc.onboarding`
    # liczą duplikaty WYŁĄCZNIE na niej, a osobna reguła porównuje liczności obu — gdyby mapa zjadła wpis
    # z jakiegokolwiek powodu, którego dziś nie przewidujemy, ta różnica jest widoczna i blokuje PR.
    wpisy = projects_file.wczytaj_plik(root / projects_file.PLIK)["members"]

    json.dump(
        {
            "policy": policy,
            "profiles": load_dir(root / "profiles"),
            "members": projects_file.mapa(wpisy),
            "members_list": wpisy,
            "access_levels": access_levels,
            "contributors": contributors,
            "today": args.today,
            # Brak klucza dla członka ≠ zero naruszeń. Reguła promotion_gate traktuje brak wpisu jako
            # „brak dowodu” i blokuje promocję — inaczej wystarczyłoby nie uruchomić raportu.
            "violations_last_window": violations,
            # STAN ZASTOSOWANY. Dzięki tym dwóm polom bramka promocji pyta o PRZEJŚCIE (repo mówi
            # `enforced`, ostatni apply mówił co innego), a nie o stan — inaczej członek, dla którego
            # granica działa, odrzucałby każdy kolejny pull request własnymi odmowami.
            "applied_stages": applied_stages,
            "applied_stages_known": applied_known,
        },
        sys.stdout,
        indent=2,
        sort_keys=True,
    )
    print()
    return 0


if __name__ == "__main__":
    # Zepsuty plik członków NIE MOŻE dać częściowego `declarations.json`. Wyjście z kodem != 0 przed
    # wypisaniem czegokolwiek jest jedynym bezpiecznym zachowaniem: `conftest` na okrojonym dokumencie
    # świeciłby na zielono, bo reguły nie mają czego oceniać. Fail-closed przed fail-quiet.
    try:
        raise SystemExit(main())
    except projects_file.BladPliku as e:
        print(f"BŁĄD PLIKU CZŁONKÓW: {e}", file=sys.stderr)
        raise SystemExit(1) from e
