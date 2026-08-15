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

TRZECIA KLASA NARUSZEŃ NIE MA ŻADNEJ Z TYCH DWÓCH TABLIC (`SERVICE_NOT_ALLOWED_FROM_VPC`, DEC-31)
-------------------------------------------------------------------------------------------------
Naruszenie z `vpcAccessibleServices` (`enableRestriction: true`) — wywołanie z sieci WEWNĄTRZ perimetru do
usługi spoza `allowedServices` — nie ma ani `ingressViolations`, ani `egressViolations`. Nie jest ani
wejściem, ani wyjściem: perimetr odmawia własnej sieci użycia usługi, której nie wpuścił na listę.

Zmierzone na 865 wpisach z sinka (okno 2026-08-11T09:21 → 2026-08-12T16:33, org labu): 132 wpisy tej klasy,
w tym 112 odmów EGZEKWOWANYCH (bez pola `dryRun`). Do liczby czytanej przez `promotion_gate` wchodziły —
przez ścieżkę zapasową niżej, po `resource.labels.project_id` — i to jest jedyny powód, dla którego nie było
tu cichego zera. Ścieżka zapasowa zbiera jednak WSZYSTKO, co wygląda na projekt, więc w 11 z tych 132 wpisów
brała także numer projektu WOŁANEGO (u nas: projektu Google'a obsługującego usługę agentową); gdyby taki
numer trafił kiedyś w numer INNEGO członka, wpis obciążyłby członka, który nie ma z wywołaniem nic wspólnego.

Autorytatywnym polem dla tej klasy jest `protoPayload.resourceName` (nie `metadata.resourceNames`): niesie
`projects/<numer>` projektu PO STRONIE PERIMETRU. Zmierzone na tych samych 865 wpisach: 132/132 wpisów bez
rekordów naruszeń miało tam numer członka, a na 733 wpisach Z rekordami pole zgadzało się z członkiem
wskazanym przez rekord w 733/733 — czyli nie jest to nowa heurystyka, tylko to samo źródło widziane z drugiej
strony. Potwierdza to niezależnie `requestMetadata.callerNetwork` (`//compute.googleapis.com/projects/<id>/…`):
dla tej klasy było obecne w 132/132 wpisach i wskazywało ten sam projekt.

Ta klasa ZOSTAJE w liczbie bramki. Jej tryb awarii jest fałszywie uspokajający: workload członka używa usługi
spoza `allowedServices`, po promocji przestaje działać, a naruszenie nie jest ani wejściem, ani wyjściem —
więc licznik zbudowany na dwóch tablicach nie widziałby go z definicji.

ARTEFAKT PROJEKTU ROZLICZENIOWEGO — naruszenie „egress", w którym nic nie wypływa (DEC-31)
------------------------------------------------------------------------------------------
Wywołanie wykonane z domyślnym `billing/quota_project` operatora dotyka DWÓCH projektów naraz: sondowanego
(w perimetrze) i rozliczeniowego (poza nim). Granica odrzuca je jako `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER`
i księguje jako naruszenie EGRESS, w którym `source` = członek, a `targetResource` = projekt rozliczeniowy.
Raport czytał to jako „dane członka wychodzą na zewnątrz" i wysyłał właściciela po regułę egress — czyli po
prawdziwą dziurę — za wywołanie, w którym nie wypłynął ani jeden bajt.

Zmierzone na tym samym oknie: 160 wpisów tej klasy (152 na jednym członku, 8 na drugim), 159 od zredagowanej
tożsamości CZŁOWIEKA z adresu domowego, wszystkie `google.storage.buckets.list`. Sygnaturą nie jest jednak ani
tożsamość, ani metoda, tylko UPRAWNIENIE ŻĄDANE NA CELU:

    sourceType == "Resource"                                   (nie ruch z sieci członka, tylko drugi zasób
                                                                w tym samym żądaniu)
    targetResourcePermissions == ["serviceusage.services.use"]  (dokładnie to jedno — zużycie kwoty)
    targetResource            = projekt SPOZA listy członków

`serviceusage.services.use` nie daje odczytu żadnych danych. Wpis, w którym na celu żądane jest COKOLWIEK
ponad to (`storage.objects.list`, `bigquery.tables.getData`, …), przestaje pasować do sygnatury i wraca do
liczby — dlatego to wykluczenie nie umie schować wypływu. Kontrola na tych samych danych: realny egress z
sieci członka niesie `sourceType: "Network"` i uprawnienia danych (`storage.buckets.list` 243×,
`storage.objects.list` 175×, `storage.buckets.get` 5×) i nie pasuje do sygnatury ani razu.

Wykluczone wpisy NIE ZNIKAJĄ: idą do pliku wykluczeń obok dowodu (`--platform-json-out`) i do raportu,
nad słowo „czysto". To jest ważne, bo kierunek tego błędu bywa odwrotny, niż wygląda: jeśli wśród wykluczonych
tożsamości jest WORKLOAD, a nie człowiek przy laptopie, to jest realny przepływ do naprawy przed promocją —
tyle że naprawia się go ustawieniem projektu rozliczeniowego, a nie regułą egress.

CZEGO TEN RAPORT NIE MOŻE ZAWIERAĆ — i to nie jest usterka, tylko definicja (DEC-27). Ruch między dwoma
członkami, którzy OBAJ są w dry-run, jest dla konfiguracji dry-run ruchem WEWNĄTRZ perimetru: nie narusza
niczego, więc nie powstaje żaden wpis. Promocja przenosi jednego z nich do konfiguracji egzekwowanej i
dokładnie ten przepływ staje się naruszeniem egress. Zmierzone 2026-08-12 (#2005) dwiema maszynami i tą samą
sondą: z członka wyłącznie dry-run do drugiego takiego członka — PRZESZŁO i zero wpisów; z członka
egzekwowanego do tego samego zasobu — ODMOWA (`NETWORK_NOT_IN_SAME_SERVICE_PERIMETER`, `egressViolations`).
Dlatego raport wypisuje listę członków w dry-run: bez niej słowo „czysto" opisuje mniejszy zbiór, niż znaczy.

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
    --freshness="${DAYS}d" --format=json > raw.json || exit 1   # DAYS = onboarding.clean_window_days

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
SIEC_PROJEKTU = re.compile(r"^//compute\.googleapis\.com/projects/([^/]+)/")

# Uprawnienie, którego obecność JAKO JEDYNEGO na celu oznacza „ten projekt jest tu tylko po to, żeby zapłacić
# za kwotę". Nie daje odczytu żadnych danych, więc wpis o takim celu nie może być wypływem — patrz nagłówek.
KWOTA = frozenset({"serviceusage.services.use"})

# Nazwy kierunków wypisywane w raporcie. Trzecia pozycja istnieje, bo trzecia klasa naruszeń istnieje.
WEJSCIE = "wejście"
WYJSCIE = "wyjście"
USLUGA_SPOZA_VPC = "usługa spoza allowedServices"
KIERUNEK_NIEZNANY = "kierunek nierozpoznany"


def artefakt_projektu_rozliczeniowego(rekord: dict, jest_czlonkiem) -> bool:
    """Czy ten rekord egress jest artefaktem projektu rozliczeniowego, a nie wypływem danych.

    Sygnatura jest wąska CELOWO — ma nie umieć schować wypływu. Wymagamy naraz: źródła typu `Resource`
    (a więc drugiego zasobu w tym samym żądaniu, nie ruchu z sieci członka), celu spoza listy członków
    oraz zbioru uprawnień na celu równego DOKŁADNIE `{serviceusage.services.use}`. Cokolwiek, co czyta
    dane, dokłada do tego zbioru własne uprawnienie i wpis wraca do liczby bramki.
    """
    if rekord.get("sourceType") != "Resource":
        return False
    if frozenset(rekord.get("targetResourcePermissions") or []) != KWOTA:
        return False
    cel = NUMER_PROJEKTU.match(str(rekord.get("targetResource", "")))
    return bool(cel) and not jest_czlonkiem(cel.group(1))


def przypisania_z_rekordow(meta: dict, jest_czlonkiem) -> list:
    """(numer projektu, kierunek, czy artefakt) dla KAŻDEGO rekordu naruszenia w tym wpisie.

    Rekordy `ingressViolations`/`egressViolations` są źródłem autorytatywnym: mówią wprost, którego
    członka dotyczy naruszenie. Dopiero ich brak uzasadnia sięganie po pola niżej.
    """
    out = []
    for v in meta.get("ingressViolations", []) or []:
        m = NUMER_PROJEKTU.match(str(v.get("targetResource", "")))
        if m:
            out.append((m.group(1), WEJSCIE, False))
    for v in meta.get("egressViolations", []) or []:
        m = NUMER_PROJEKTU.match(str(v.get("source", "")))
        if m:
            out.append((m.group(1), WYJSCIE, artefakt_projektu_rozliczeniowego(v, jest_czlonkiem)))
    return out


def przypisania_bez_rekordow(meta: dict, entry: dict) -> tuple:
    """Przypisania dla wpisu, który NIE MA żadnej z dwóch tablic — plus nazwa użytego pola.

    Kolejność jest wynikiem pomiaru, nie gustu. `protoPayload.resourceName` niesie `projects/<numer>`
    projektu po stronie perimetru w 132/132 takich wpisów i zgadza się z rekordem naruszenia tam, gdzie
    rekord w ogóle jest (733/733) — więc jest tym samym źródłem, nie nową heurystyką.

    Stary zbiór poglądowy (`metadata.resourceNames` + `resource.labels.project_id`) zostaje jako OSTATNIA
    deska: nowy kształt wpisu nie może cicho wypaść z rachunku. Jest jednak świadomie ostatni, bo zbiera
    wszystko, co wygląda na projekt — łącznie z numerem projektu WOŁANEGO (zmierzone: 11 wpisów, w których
    dokładał go obok właściwego członka).
    """
    pp = entry.get("protoPayload", {})
    reason = meta.get("violationReason") or ""
    kierunek = USLUGA_SPOZA_VPC if "SERVICE_NOT_ALLOWED_FROM_VPC" in str(reason) else KIERUNEK_NIEZNANY

    m = NUMER_PROJEKTU.match(str(pp.get("resourceName", "")))
    if m:
        return [(m.group(1), kierunek, False)], "protoPayload.resourceName"

    ident = set()
    for rn in meta.get("resourceNames", []) or []:
        m = NUMER_PROJEKTU.match(str(rn))
        if m:
            ident.add(m.group(1))
    project_id = str(entry.get("resource", {}).get("labels", {}).get("project_id", ""))
    if project_id:
        ident.add(project_id)
    if not ident:
        return [], "brak"
    return [(i, kierunek, False) for i in sorted(ident)], "zbiór poglądowy (resourceNames + project_id)"


def siec_wolajaca(entry: dict) -> str:
    """`project_id` sieci VPC, z której przyszło wywołanie — albo pusty string.

    Dla klasy bez rekordów naruszeń to jedyne pole mówiące, CZYJ workload przestanie działać po promocji;
    do raportu wchodzi jako namiar dla właściciela, nie jako podstawa przypisania.
    """
    m = SIEC_PROJEKTU.match(str(entry.get("protoPayload", {}).get("requestMetadata", {}).get("callerNetwork", "")))
    return m.group(1) if m else ""


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

    def jest_czlonkiem(ident: str) -> bool:
        return ident in po_identyfikatorze

    counts = collections.Counter()
    detail = collections.defaultdict(collections.Counter)
    platforma = collections.Counter()
    platforma_detail = collections.defaultdict(collections.Counter)
    rozliczeniowy = collections.Counter()
    rozliczeniowy_detail = collections.defaultdict(collections.Counter)
    klasy_wpisy = collections.Counter()          # violationReason → ile wpisów w oknie
    klasy_zrodlo = collections.defaultdict(set)  # violationReason → z jakiego pola czytany członek
    klasy_los = collections.defaultdict(collections.Counter)  # violationReason → co się z przypisaniem stało
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
        siec = siec_wolajaca(entry)

        przypisania = przypisania_z_rekordow(meta, jest_czlonkiem)
        zrodlo = "rekord naruszenia"
        if not przypisania:
            przypisania, zrodlo = przypisania_bez_rekordow(meta, entry)

        klasy_wpisy[reason or "(bez violationReason)"] += 1
        klasy_zrodlo[reason or "(bez violationReason)"].add(zrodlo)

        if not przypisania:
            # Wpisu nie zrozumieliśmy. Policzenie go jako „nie nasz" jest dokładnie tym błędem, przez
            # który 26 naruszeń członka raportowało się jako czyste okno — więc raport pada, patrz niżej.
            nierozpoznane.append(f"{method} ({reason}) [{unikat or 'brak id'}]")
            continue

        # Jeden wpis może dotyczyć dwóch członków i nieść dla nich RÓŻNE rekordy. Wykluczamy członka
        # dopiero wtedy, gdy KAŻDY rekord wskazujący na niego jest artefaktem — wpis mieszany (jeden
        # rekord o kwocie, drugi o danych) ma zostać w liczbie.
        trafienia = {}
        for ident, kierunek, artefakt in przypisania:
            name = po_identyfikatorze.get(ident)
            if name is None:
                continue
            t = trafienia.setdefault(name, {"artefakt": True, "kierunki": set()})
            t["kierunki"].add(kierunek)
            t["artefakt"] = t["artefakt"] and artefakt

        if not trafienia:
            obce[f"{principal} → {method} ({reason})"] += 1
            klasy_los[reason or "(bez violationReason)"]["spoza listy członków"] += 1
            continue

        regula = pokryte_przez_baseline(decl, principal, service, method)
        opis_sieci = f", sieć: {siec}" if siec and zrodlo != "rekord naruszenia" else ""
        for member, t in trafienia.items():
            kierunki = "/".join(sorted(t["kierunki"]))
            if regula:
                # Ruch platformy pokryty jawną regułą baseline. NIE znika — idzie do własnego licznika,
                # do raportu i do osobnego artefaktu; nie wchodzi tylko do liczby, którą czyta bramka.
                platforma[member] += 1
                platforma_detail[member][f"{principal} → {method} (pokrywa baseline_ingress[{regula}])"] += 1
                klasy_los[reason or "(bez violationReason)"]["wykluczone: ruch platformy"] += 1
                continue
            if t["artefakt"]:
                # Artefakt projektu rozliczeniowego: „egress", w którym na celu żądane jest wyłącznie
                # zużycie kwoty. Nie jest wypływem, więc nie blokuje promocji — ale jest wypisany
                # z nazwiskiem wołającego, bo workload z takim wywołaniem naprawdę stanie po promocji.
                rozliczeniowy[member] += 1
                rozliczeniowy_detail[member][f"{principal} → {method} ({reason}, cel: tylko kwota)"] += 1
                klasy_los[reason or "(bez violationReason)"]["wykluczone: projekt rozliczeniowy"] += 1
                continue
            counts[member] += 1
            detail[member][f"{principal} → {method} ({reason}, {kierunki}{opis_sieci})"] += 1
            klasy_los[reason or "(bez violationReason)"]["do liczby bramki"] += 1
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
    # Kategorie są nazwane, bo wykluczają z RÓŻNYCH powodów i naprawia się je różnymi rzeczami:
    # ruch platformy pokrywa reguła baseline, artefakt kwoty naprawia `CLOUDSDK_BILLING_QUOTA_PROJECT`.
    platform_out = {
        name: {
            "razem": platforma.get(name, 0) + rozliczeniowy.get(name, 0),
            "platforma": {
                "razem": platforma.get(name, 0),
                "wpisy": dict(platforma_detail.get(name, {})),
            },
            "projekt_rozliczeniowy": {
                "razem": rozliczeniowy.get(name, 0),
                "wpisy": dict(rozliczeniowy_detail.get(name, {})),
            },
        }
        for name in decl["members"]
    }
    pathlib.Path(args.platform_json_out).write_text(json.dumps(platform_out, indent=2, sort_keys=True) + "\n")

    # ZAKRES, W KTÓRYM „CZYSTO" COKOLWIEK ZNACZY (DEC-27). Konfiguracja dry-run zawiera WSZYSTKICH członków
    # naraz, więc ruch między dwoma członkami w dry-run jest dla niej ruchem wewnątrz perimetru — nie ma
    # czego zalogować. Promocja przenosi natomiast JEDNEGO: reszta zostaje na zewnątrz i ten sam przepływ
    # staje się naruszeniem egress. Raport, który pisze samo „czysto", opisuje więc mniejszy zbiór, niż
    # sugeruje to słowo. Nazwiska rówieśników są tu po to, żeby dało się zadać właścicielowi konkretne
    # pytanie („rozmawiacie z <X>?"), a nie ogólne — to samo, co robi lista przepływów rzadkich w runbooku.
    w_dry_run = sorted(n for n, m in decl["members"].items() if m.get("stage") != "enforced")

    lines = ["# Naruszenia dry-run — okno obserwacji", ""]
    if w_dry_run:
        lines.append(f"**Czego to okno nie mogło zobaczyć:** {len(w_dry_run)} członków jest w konfiguracji "
                     f"dry-run ({', '.join(w_dry_run)}). Przepływy MIĘDZY nimi są dla tej konfiguracji ruchem "
                     "wewnątrz perimetru i nie generują wpisów — a po promocji pojedynczego członka stają się "
                     "naruszeniem egress. Słowo „czysto\" niżej znaczy: czysto wobec ruchu, który granica dziś ocenia.")
        lines.append("")
    for name in sorted(result):
        member = decl["members"][name]
        status = "czysto" if result[name] == 0 else f"**{result[name]} naruszeń**"
        lines.append(f"## {name} ({member['project_id']}, stage: {member['stage']}) — {status}")
        lines.append(f"właściciel: {member['owner_group']}")
        # Tylko dla członków, których promocja jest jeszcze przed nami. Dla członka już egzekwowanego ta
        # sama lista nie jest do niczego — jego decyzja zapadła, a bramka pyta o PRZEJŚCIE, nie o stan.
        rowiesnicy = [n for n in w_dry_run if n != name] if member.get("stage") != "enforced" else []
        if rowiesnicy:
            lines.append("")
            # Pełna lista zostaje TUTAJ i to nie jest kosmetyka: od DEC-55 bramka nie pyta już o licznik
            # globalny (unieważniał go każdy cudzy onboarding, #2076), więc kompletność zbioru rówieśników
            # nie ma innego nośnika niż ten raport. Bramka odsyła tu wprost.
            lines.append(f"niemierzalne w tym oknie: przepływy do/z **{len(rowiesnicy)}** członków w dry-run "
                         f"({', '.join(rowiesnicy)}) — przy promocji tego członka wypisz w "
                         f"`unmeasured_peers_ack` klucze tych, z którymi ten członek **wymienia ruch**. "
                         f"Pusta lista `[]` jest legalna i jest oświadczeniem, że z żadnym; brak pola "
                         f"zatrzymuje promocję")
        if platforma.get(name):
            # Świadomie NAD listą naruszeń dywizji: czytelnik ma zobaczyć, co zostało wyłączone z liczby,
            # zanim uwierzy w słowo „czysto". Milczenie o wykluczeniach byłoby tym samym, co ich brak.
            lines.append("")
            lines.append(f"ruch platformy wyłączony z liczby (pokryty regułą `baseline_ingress`): "
                         f"**{platforma[name]}** — pełna lista w `{args.platform_json_out}`")
            for what, n in platforma_detail[name].most_common(10):
                lines.append(f"- `{what}` × {n}")
        if rozliczeniowy.get(name):
            # Też NAD listą i też z nazwiskami: to jest wykluczenie, które trzeba umieć podważyć.
            lines.append("")
            lines.append(f"artefakt projektu rozliczeniowego wyłączony z liczby: **{rozliczeniowy[name]}** — "
                         f"wywołanie dotknęło projektu spoza perimetru WYŁĄCZNIE po to, żeby zużyć jego kwotę "
                         f"(`serviceusage.services.use`), więc nic z tego członka nie wypłynęło. Naprawa jest "
                         f"po stronie wołającego: `CLOUDSDK_BILLING_QUOTA_PROJECT` = projekt sondowany, NIE "
                         f"reguła egress. **Jeśli poniżej jest tożsamość workloadu, a nie człowieka — to jest "
                         f"realny przepływ i po promocji stanie.** Pełna lista w `{args.platform_json_out}`")
            for what, n in rozliczeniowy_detail[name].most_common(10):
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
        lines.append("")

    # KLASY NARUSZEŃ — po to, żeby nowa klasa nie weszła do raportu bezimiennie. Licznik bramki stoi na
    # założeniu „każde naruszenie da się przypisać członkowi i wiadomo, którym polem"; ta tabela pokazuje
    # to założenie wprost, klasa po klasie, na danych z TEGO okna. Klasa bez rekordów naruszeń
    # (`SERVICE_NOT_ALLOWED_FROM_VPC`) jest widoczna tu jako osobny wiersz, a nie rozpuszczona w sumie.
    lines.append("## Klasy naruszeń w tym oknie")
    lines.append("")
    lines.append("| violationReason | wpisów | członek czytany z | rozkład przypisań |")
    lines.append("| --- | ---: | --- | --- |")
    for reason in sorted(klasy_wpisy, key=lambda r: (-klasy_wpisy[r], r)):
        zrodla = ", ".join(sorted(klasy_zrodlo[reason]))
        los = ", ".join(f"{k}: {v}" for k, v in sorted(klasy_los[reason].items()))
        lines.append(f"| `{reason}` | {klasy_wpisy[reason]} | {zrodla} | {los or '—'} |")
    lines.append("")

    pathlib.Path(args.markdown_out).write_text("\n".join(lines) + "\n")
    print(f"zapisano {args.json_out}, {args.platform_json_out} i {args.markdown_out}")
    if sum(platforma.values()):
        print(f"UWAGA: {sum(platforma.values())} naruszeń zaklasyfikowano jako ruch platformy "
              f"(pokryty regułą baseline_ingress) i NIE wchodzi do liczby czytanej przez promotion_gate — "
              f"rozpiska w {args.platform_json_out}", file=sys.stderr)
    if sum(rozliczeniowy.values()):
        print(f"UWAGA: {sum(rozliczeniowy.values())} naruszeń zaklasyfikowano jako artefakt projektu "
              f"rozliczeniowego (cel żądany wyłącznie o `serviceusage.services.use`) i NIE wchodzi do liczby "
              f"czytanej przez promotion_gate — rozpiska w {args.platform_json_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
