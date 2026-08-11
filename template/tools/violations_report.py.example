#!/usr/bin/env python3
"""Mapuje naruszenia dry-run z audit-logów na członków perimetru i buduje raport dla właścicieli.

DLACZEGO to jest osobne narzędzie, a nie „zajrzyj do SCC": surowy log mówi „principal X wywołał metodę Y i
naruszył perimetr". Właściciel dywizji nie wie, czy to jego. Raport tłumaczy to na zdanie, które da się
naprawić: „twój SA robi Z, po promocji przestanie działać, pokrywa to profil P".

Wynik służy dwóm rzeczom naraz:
  * raport w PR / komentarz do ticketu (czytelny dla człowieka),
  * plik violations.json dla reguły OPA promotion_gate — czyli DOWÓD, że okno było czyste.
    Brak wpisu dla członka reguła traktuje jako brak dowodu, nie jako zero.

GDZIE W LOGU JEST NUMER CZŁONKA — i dlaczego nie tam, gdzie się wydaje
----------------------------------------------------------------------
To jest miejsce, w którym ta funkcja była zepsuta, dopóki nie zobaczyła pierwszego prawdziwego naruszenia.
`metadata.resourceNames` NIE niesie numeru projektu-członka. Na 26 realnych wpisach zmierzonych na żywej
organizacji ostatni segment `resourceNames[0]` był kolejno: numerem OBCEGO projektu (10×), nazwą REGIONU
`…/locations/europe-west4` (8×), `project_id` zamiast numeru (4×) oraz `_` z aliasu `projects/_` (4×).
Zero trafień w członka. Kolejność `resourceNames` przy egressie bywa przy tym różna dla tego samego
kształtu wywołania, więc nawet indeks `[0]` jest losowaniem.

Numer członka mieszka w rekordzie naruszenia i zależy od KIERUNKU:

    ingressViolations[].targetResource  → projects/<numer>   członek, DO którego ktoś wchodzi
    egressViolations[].source           → projects/<numer>   członek, Z którego coś wychodzi

Kierunku nie wolno mylić: przy egressie `resourceNames`/`targetResource` wskazują zasób POZA perimetrem,
więc przypisanie po nich obwinia stronę wołaną zamiast członka, którego dane wychodzą.

CZEGO TEN RAPORT NIE OBIECUJE: `principalEmail` w logach `cloudaudit.googleapis.com/policy` bywa przez
GCP zredagowany (`m...@ra...m`) i wtedy raport nie nazwie wołającego. Do namierzenia wywołania służy
`vpcServiceControlsUniqueId` — dlatego trafia do raportu markdown.

SKĄD BRAĆ WEJŚCIE — jedno zapytanie do sinka, nie N do projektów. Wpis audytowy VPC-SC ląduje w logu
PROJEKTU będącego właścicielem chronionego zasobu, czyli członka; `--organization=` czyta wyłącznie
`organizations/<id>/logs/…` i nic poniżej. Zmierzone na żywym perimetrze: zakres organizacji zwrócił **0**
wpisów, a pojedynczy projekt członka **41** — ten sam filtr, to samo okno. To zero jest nieodróżnialne od
czystego okna, więc sam zły zakres wystarczał, by `promotion_gate` przepuścił członka z 41 naruszeniami.

Odczyt każdego członka OSOBNO usuwał tę ślepotę i wprowadzał inną: przy kilkuset projektach to kilkaset
wywołań `logging read` na przebieg, a JEDEN projekt bez uprawnień wywracał całość — czyli dowód. Dlatego
wejściem jest teraz **sink org-level** (`include_children`) zbierający naruszenia z całej organizacji do
jednego kubełka logów w projekcie administracyjnym; raport czyta go jednym zapytaniem. Terraform sinka:
`violations-sink/`. Zmierzona równoważność (2026-08-11, okno 11m47s): sink = 16 wpisów w 1 zapytaniu,
suma odczytów per projekt = 16 wpisów w 3 zapytaniach, **identyczne zbiory `insertId`**.

Ten plik NIE ZMIENIŁ SIĘ przy tej migracji ani o linijkę logiki — i to był argument za kubełkiem logów
przeciwko BigQuery. Kubełek oddaje ten sam JSON, który parser niżej już czyta (zagnieżdżone
`ingressViolations`/`egressViolations`); sink do BigQuery wkłada `protoPayload.metadata` do kolumny STRING
`metadataJson`, więc trzeba by ją odparsować z powrotem — nowy tryb awarii na ścieżce niosącej DOWÓD.

Filtr sinka NIE MA predykatu na `dryRun` i to jest celowe: pole istnieje wyłącznie przy naruszeniu dry-run
(wartość `true`), a odmowa EGZEKWOWANA nie ma go w ogóle, więc `dryRun="false"` nie łapie nigdy niczego.
Zmierzone na 25 żywych wpisach: sam filtr po typie dał 16 dry-run + 9 egzekwowanych, a dołożenie
`dryRun="false"` dało 0.

Sink celowo NIE filtruje po liście członków — niesie też naruszenia projektów, które członkami jeszcze nie
są (kandydaci w pre-flighcie) albo już nie są (offboarding). Filtruje się TUTAJ, przy raportowaniu: obcy
ruch idzie do sekcji „Naruszenia spoza listy członków", zamiast zniknąć w zbieraniu.

Sprawdź kod wyjścia: przy odmowie `gcloud logging read` i tak wypisuje na stdout `[]`, więc samo
przekierowanie do pliku zamienia „nie wolno mi było przeczytać" w „nie było naruszeń":

  set -o pipefail
  gcloud logging read \\
    'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"' \\
    --project=<PROJEKT_ADM> --bucket=<KUBELEK> --location=<LOKALIZACJA> --view=<WIDOK> \\
    --freshness=14d --format=json > raw.json || exit 1

I JESZCZE JEDNO, ZMIERZONE PRZY ZAKŁADANIU SINKA: sink, który nie dostarcza, wygląda identycznie jak czyste
okno. Zanim grant `logging.bucketWriter` dla jego tożsamości się rozpropagował, 9 z 18 wpisów przepadło
BEZPOWROTNIE (ponowny odczyt tego samego, zamkniętego okna 3 minuty później: te same 9 braków), a
`sinks describe` przez cały ten czas raportował sink jako zdrowy. Po każdej zmianie sinka potwierdź
DOSTARCZANIE, a nie konfigurację — i nie licz okna obserwacji od chwili sprzed tego potwierdzenia.

Użycie:
    python3 tools/violations_report.py --logs raw.json --declarations declarations.json \\
        --json-out violations.json --markdown-out report.md
"""
import argparse
import collections
import json
import pathlib
import re
import sys

NUMER_PROJEKTU = re.compile(r"^projects/(\d+)$")


def numery_z_naruszen(meta: dict) -> set:
    """Numery projektów-CZŁONKÓW implikowanych przez ten wpis, czytane po KIERUNKU naruszenia.

    Rekordy `ingressViolations`/`egressViolations` są źródłem autorytatywnym: mówią wprost, którego
    członka dotyczy naruszenie. Dopiero ich brak uzasadnia sięganie po dane poglądowe (niżej).
    """
    numery = set()
    for v in meta.get("ingressViolations", []) or []:
        m = NUMER_PROJEKTU.match(str(v.get("targetResource", "")))
        if m:
            numery.add(m.group(1))
    for v in meta.get("egressViolations", []) or []:
        m = NUMER_PROJEKTU.match(str(v.get("source", "")))
        if m:
            numery.add(m.group(1))
    return numery


def identyfikatory_zapasowe(meta: dict, entry: dict) -> set:
    """Identyfikatory poglądowe — używane WYŁĄCZNIE, gdy wpis nie ma rekordów naruszeń.

    Nowa usługa albo nowy kształt wpisu nie może cicho wypaść z rachunku, więc bierzemy stąd wszystko,
    co w ogóle wygląda na projekt: każdy `projects/<numer>` z `resourceNames` (nie tylko `[0]`) oraz
    `project_id` z etykiet zasobu — mapa członków jest kluczowana i numerem, i identyfikatorem.
    """
    ident = set()
    for rn in meta.get("resourceNames", []) or []:
        m = NUMER_PROJEKTU.match(str(rn))
        if m:
            ident.add(m.group(1))
    project_id = str(entry.get("resource", {}).get("labels", {}).get("project_id", ""))
    if project_id:
        ident.add(project_id)
    return ident


def pokryte_przez_baseline(decl: dict, principal: str, service: str, method: str):
    """Tytuł reguły `baseline_ingress`, która pokrywa TĘ tożsamość NA TEJ usłudze i metodzie — albo None.

    DLACZEGO TO ISTNIEJE. `promotion_gate` pyta „czy okno obserwacji było czyste", czyli „czy jest przepływ,
    który po promocji przestanie działać". Naruszenie od tożsamości PLATFORMY, dla której perimetr ma
    JAWNĄ regułę baseline na dokładnie tej operacji, nie jest takim przepływem: po promocji reguła go
    przepuści. Liczenie go blokuje promocję za coś, co promocji nie przetrwa tylko dlatego, że reguła
    weszła w życie później niż wywołanie.

    DLACZEGO TO NIE JEST „FILTR, KTÓRY UKRYWA NARUSZENIA" — bo nie jest listą tożsamości do pominięcia.
    Wyklucza wyłącznie to, co konfiguracja perimetru już DEKLARUJE jako dozwolone, i to z dopasowaniem
    na trzech wymiarach naraz: tożsamość ORAZ usługa ORAZ metoda. Ruch dywizji i ruch człowieka nie mają
    jak w to wpaść, bo nie ma ich w `baseline_ingress` — a to jest dokładnie ten ruch, który bramka ma
    łapać. Wykluczone wpisy i tak trafiają do raportu (sekcja „ruch platformy") i do osobnego artefaktu,
    więc nic nie znika z oczu recenzenta.

    UWAGA na konwencję nazw metod: audit-log niesie nazwę pełną (`google.logging.v2.LoggingServiceV2.
    ListLogEntries`), a selektor w regule bywa skrócony (`LoggingServiceV2.ListLogEntries`) — ACM nie ma
    tu jednej konwencji dla wszystkich usług. Dopasowujemy więc równość ALBO sufiks po kropce, nigdy
    `in` na surowym stringu (to łapałoby `List` w `ListBuckets`).
    """
    for rule in decl.get("policy", {}).get("baseline_ingress", []) or []:
        tozsamosci = {str(i).split(":", 1)[-1] for i in rule.get("identities", []) or []}
        if principal not in tozsamosci:
            continue
        for op in rule.get("operations", []) or []:
            if op.get("service") != service:
                continue
            for m in op.get("methods", []) or []:
                if m == "*" or method == m or method.endswith("." + m):
                    return rule.get("title", "?")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", required=True, help="JSON z gcloud logging read")
    ap.add_argument("--declarations", required=True, help="wyjście collect_declarations.py")
    ap.add_argument("--json-out", default="violations.json")
    ap.add_argument("--markdown-out", default="violations.md")
    ap.add_argument("--platform-json-out", default="violations-platform.json",
                    help="wykluczone naruszenia platformy — publikowane obok dowodu, nie zamiast niego")
    args = ap.parse_args()

    surowe = json.loads(pathlib.Path(args.logs).read_text())
    if not isinstance(surowe, list):
        sys.exit(f"{args.logs}: oczekiwano listy wpisów z `gcloud logging read --format=json`")
    decl = json.loads(pathlib.Path(args.declarations).read_text())

    # Log niesie numery, czasem samo `project_id`; repo operuje nazwami plików członków. Mapa przyjmuje
    # oba klucze, żeby wpis bez rekordu naruszenia dało się jeszcze przypisać po identyfikatorze.
    po_identyfikatorze = {}
    for name, m in decl["members"].items():
        po_identyfikatorze[str(m["project_number"])] = name
        po_identyfikatorze[str(m["project_id"])] = name

    counts = collections.Counter()
    detail = collections.defaultdict(collections.Counter)
    platforma = collections.Counter()
    platforma_detail = collections.defaultdict(collections.Counter)
    namiar = {}  # członek → jeden vpcServiceControlsUniqueId, gdy principal jest zredagowany
    obce = collections.Counter()
    nierozpoznane = []

    for entry in surowe:
        pp = entry.get("protoPayload", {})
        meta = pp.get("metadata", {})
        principal = pp.get("authenticationInfo", {}).get("principalEmail", "?")
        method = pp.get("methodName", "?")
        service = pp.get("serviceName", "")
        reason = meta.get("violationReason") or ""
        if isinstance(reason, list):
            reason = ", ".join(str(r) for r in reason if r)
        unikat = meta.get("vpcServiceControlsUniqueId", "")

        identyfikatory = numery_z_naruszen(meta) or identyfikatory_zapasowe(meta, entry)
        if not identyfikatory:
            # Wpisu nie zrozumieliśmy. Policzenie go jako „nie nasz" jest dokładnie tym błędem, przez
            # który 26 naruszeń członka raportowało się jako czyste okno — więc raport pada, patrz niżej.
            nierozpoznane.append(f"{method} ({reason}) [{unikat or 'brak id'}]")
            continue

        czlonkowie = {po_identyfikatorze[i] for i in identyfikatory if i in po_identyfikatorze}
        if not czlonkowie:
            obce[f"{principal} → {method} ({reason})"] += 1
            continue
        regula = pokryte_przez_baseline(decl, principal, service, method)
        for member in czlonkowie:  # jeden wpis może dotyczyć dwóch członków — liczy się obu raz
            if regula:
                # Ruch platformy pokryty jawną regułą baseline. NIE znika — idzie do własnego licznika,
                # do raportu i do osobnego artefaktu; nie wchodzi tylko do liczby, którą czyta bramka.
                platforma[member] += 1
                platforma_detail[member][f"{principal} → {method} (pokrywa baseline_ingress[{regula}])"] += 1
                continue
            counts[member] += 1
            detail[member][f"{principal} → {method} ({reason})"] += 1
            if unikat:
                namiar.setdefault(member, unikat)

    # FAIL-CLOSED. `violations.json` JEST dowodem dla bramki promocji, więc nie wolno go wystawić na
    # podstawie wpisów, których nie umiemy przypisać: „nie rozumiem" zapisane jako 0 to zielona bramka
    # zbudowana na nieodczytanym stanie. Brak pliku = brak dowodu = promotion_gate blokuje.
    if nierozpoznane:
        print(f"BŁĄD: {len(nierozpoznane)} wpisów bez rozpoznanego projektu — raport NIE powstał "
              f"(brak dowodu ≠ zero naruszeń). Przykłady:", file=sys.stderr)
        for opis in nierozpoznane[:5]:
            print(f"  - {opis}", file=sys.stderr)
        return 2

    # KLUCZOWE: wypisujemy 0 dla KAŻDEGO członka, nie tylko dla tych z naruszeniami. Inaczej „brak wpisu"
    # byłoby nieodróżnialne od „raport nie objął tego członka", a na tej różnicy stoi bramka promocji.
    result = {name: counts.get(name, 0) for name in decl["members"]}
    pathlib.Path(args.json_out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    # Wykluczenia jadą OSOBNYM plikiem, a nie dodatkowym kluczem w `violations.json`: ten plik jest
    # wejściem OPA (`violations_last_window`), gdzie każdy klucz udaje nazwę członka. Osobny artefakt
    # zachowuje kontrakt dowodu i jednocześnie nie pozwala schować wykluczeń przed recenzentem.
    platform_out = {
        name: {
            "razem": platforma.get(name, 0),
            "wpisy": dict(platforma_detail.get(name, {})),
        }
        for name in decl["members"]
    }
    pathlib.Path(args.platform_json_out).write_text(json.dumps(platform_out, indent=2, sort_keys=True) + "\n")

    lines = ["# Naruszenia dry-run — okno obserwacji", ""]
    for name in sorted(result):
        member = decl["members"][name]
        status = "czysto" if result[name] == 0 else f"**{result[name]} naruszeń**"
        lines.append(f"## {name} ({member['project_id']}, stage: {member['stage']}) — {status}")
        lines.append(f"właściciel: {member['owner_group']}")
        if platforma.get(name):
            # Świadomie NAD listą naruszeń dywizji: czytelnik ma zobaczyć, co zostało wyłączone z liczby,
            # zanim uwierzy w słowo „czysto". Milczenie o wykluczeniach byłoby tym samym, co ich brak.
            lines.append("")
            lines.append(f"ruch platformy wyłączony z liczby (pokryty regułą `baseline_ingress`): "
                         f"**{platforma[name]}** — pełna lista w `{args.platform_json_out}`")
            for what, n in platforma_detail[name].most_common(10):
                lines.append(f"- `{what}` × {n}")
        if result[name]:
            lines.append("")
            lines.append("Te wywołania PRZESTANĄ działać po promocji do enforced:")
            for what, n in detail[name].most_common(10):
                lines.append(f"- `{what}` × {n}")
            lines.append("")
            if name in namiar:
                # GCP redaguje `principalEmail` w logach policy, więc powyższa lista bywa bez nazwiska.
                # Ten identyfikator jest tym, po czym da się odszukać konkretne wywołanie w Troubleshooterze.
                lines.append(f"namiar na wywołanie (`vpcServiceControlsUniqueId`): `{namiar[name]}`")
                lines.append("")
            lines.append("Napraw przepływ albo poproś o profil, który go pokrywa (nie o surową regułę).")
        lines.append("")

    if obce:
        lines.append("## Naruszenia spoza listy członków")
        lines.append("Dotyczą projektów, których nie ma w perimeter/projects.yaml — zwykle znaczy to, że ktoś")
        lines.append("woła chroniony zasób z projektu, o którego dołączenie nikt nie wystąpił.")
        for what, n in obce.most_common(10):
            lines.append(f"- `{what}` × {n}")

    pathlib.Path(args.markdown_out).write_text("\n".join(lines) + "\n")
    print(f"zapisano {args.json_out}, {args.platform_json_out} i {args.markdown_out}")
    if sum(platforma.values()):
        print(f"UWAGA: {sum(platforma.values())} naruszeń zaklasyfikowano jako ruch platformy "
              f"(pokryty regułą baseline_ingress) i NIE wchodzi do liczby czytanej przez promotion_gate — "
              f"rozpiska w {args.platform_json_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
