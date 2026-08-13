# 8. Zmiany ręczne — cztery procedury, których nie obsługuje żaden formularz

Trzy kanały wejścia (`snow:`, `pr:`, `manual:`) opisują **jedną** czynność: dołożenie albo zmianę
**członka**. Wszystko inne w tym repozytorium zmienia człowiek, ręcznie, pull requestem — i przez długi
czas nie było o tym ani jednej procedury, mimo że dwa runbooki wskazują „dodaj profil" jako **naprawę**,
a katalog access leveli opisuje pole `armed` bez powiedzenia, jak z niego wyjść.

Ten dokument opisuje te cztery czynności:

| § | Zmiana | Kto ją zwykle robi | Co poszerza |
|---|---|---|---|
| [8.1](#81-wniosek-ręczny-architekta-change_ref-manual) | **wniosek ręczny** architekta (`change_ref: manual:`) | architekt / zespół sieciowy | zbiór członków |
| [8.2](#82-dodanie-profilu-do-katalogu) | **dodanie profilu** do katalogu | zespół sieciowy + Security | to, co wolno regule z katalogu |
| [8.3](#83-dodanie-i-uzbrojenie-access-levelu) | **dodanie i uzbrojenie access levelu** | zespół sieciowy | kontekst, który autoryzuje |
| [8.4](#84-zmiana-restricted_services) | **zmiana `restricted_services`** | Security + zespół sieciowy | **nic** — zawęża albo poszerza to, co granica w ogóle obejmuje |

## Co te cztery mają wspólnego — i dlaczego to jest cała treść tego dokumentu

**Nie ma systemu rekordu.** Wniosek z ServiceNow weryfikuje się oddzwonieniem do API, wniosek z repozytorium
dywizji — mapowaniem repo→projekty. Tutaj jedynym śladem intencji jest **treść pull requesta**, a wnioskodawca
i zatwierdzający bywają tą samą osobą. Dlatego każda z czterech procedur niżej ma jawnie nazwaną sekcję
**„kto to zatwierdza"** i żadna nie kończy się na merge'u.

**Zielony `apply` NIE jest dowodem.** Jest dowodem na to, że **zapisaliśmy to, co chcieliśmy zapisać** —
i nic ponadto. Cztery zmierzone tryby awarii, po jednym na każdą procedurę niżej, wyglądają na zielonym
apply identycznie jak sukces:

| co wyglądało na zrobione | czym naprawdę było |
|---|---|
| access level z zakresami RFC 5737 | obiekt kompletny w konsoli, **nie autoryzujący nikogo** |
| profil `bq-omni-external-read` | **nieaplikowalny od dnia powstania** — trzy reguły API poznane dopiero na apply |
| `restricted_services` z usługą spoza wsparcia VPC-SC | zielone bramki offline, `Error 400` dopiero na org-plane |
| offboarding członka | `apply` padł w połowie na `403`, granica już bez członka, poziom **został** |

Stąd wspólny kształt ostatniego kroku każdej procedury: **odczyt z żywego API po apply**
(`perimeters describe`, `levels describe`, przelot sondy), a nie „pipeline zielony". To jest **DEC-41**.

**Bramka, nie CODEOWNERS.** Bez ochrony gałęzi (funkcja płatna) GitHub nie egzekwuje CODEOWNERS w ogóle.
Egzekwuje to reguła OPA `vpcsc.onboarding` uruchamiana przez `bramki-tresci` na **obu** torach — pull request
i apply (DEC-16) — więc commit wypchnięty prosto na gałąź domyślną zatrzymuje się u mutatora. CODEOWNERS
mówi, **kto ma przeczytać**; bramka mówi, że **bez wpisu nie pojedzie**.

**Trzy z tych czterech zmian rozszerzają dostęp** (członek, profil, access level; `restricted_services`
rozszerza go, gdy usługa z listy **znika**). Dla ścieżki egress poza Google Cloud zatwierdzającego niesie
mechanizm — `policy.yaml` §`egress_approvals`, wpis z celami i datą wygaśnięcia (DEC-23). Dla pozostałych
trzech **odpowiednika nie ma** i procedura nie udaje, że ma: zatwierdzający jest nazwany w sekcji „kto to
zatwierdza", a jego ślad zostaje w opisie pull requesta i w polu `change_ref`. Kto chce z tego zrobić
mechanizm, ma w tym dokumencie napisane, czego by on dotyczył.

---

## 8.1 Wniosek ręczny architekta (`change_ref: manual:`)

Kanał, którym architekt dokłada albo zmienia członka **bez** ticketu i bez repozytorium dywizji: migracja
z brownfieldu, projekt platformowy, incydent, pilotaż. Schemat dopuszcza go wprost —
`manual:<uzasadnienie ≥ 20 znaków>` — bo alternatywą byłby **wymyślony numer ticketu**, a fikcyjnych pól
nikt nie czyta.

**Kto to zatwierdza.** Zespół sieciowy (CODEOWNERS `perimeter/projects.yaml`). Uzasadnienie w `change_ref`
jest **jedynym trwałym śladem** tego wniosku — piszemy w nim, **dlaczego ręcznie**, a nie „dodanie projektu".
Wpis wybierający profil `risk: high` z niepustym celem wymaga **osobno** zgody Security w `policy.yaml`
§`egress_approvals` — i wtedy zatwierdzającym jest Security, nie sieć.

### Kroki

```bash
# 0. PREREKWIZYTY PO STRONIE WNIOSKODAWCY — sprawdź je ZANIM napiszesz wpis.
#    Pre-flight jedzie w CI na obu torach, ale odpowiedź „czego brakuje" jest tańsza teraz niż w review.
./tools/preflight_check.sh <project_id>

# 1. Gałąź i wpis w perimeter/projects.yaml (JEDEN plik na całą organizację — DEC-12).
git checkout -b wniosek/<dywizja>-<projekt> origin/main
```

```yaml
# 2. Wpis. Pola, które przy kanale ręcznym najczęściej są wypełniane źle:
- schema_version: 1
  division: example-division
  project_id: prj-example-vertex-dev
  project_number: '123456789012'   # STRING, w cudzysłowach — bez nich YAML da liczbę i bramka
                                   # control_plane nigdy nie trafi (porównuje stringi)
  owner_group: grp-example-division-cloud@example.com
  change_ref: 'manual:migracja z perimetru zespolowego, ticket nie istnieje bo projekt
    juz jest chroniony — przenosimy wlasnosc, nie dodajemy ochrony'
  approved_by: net-approver@example.com
  stage: dry-run                   # NOWY członek ZAWSZE wchodzi w dry-run (DEC-4).
  dry_run_since: '2026-01-15'      # dzień wejścia — to jest ZEGAR bramki promocji, nie ozdoba
  review_by: '2026-07-15'
  profiles:
    - name: vertex-online-serving
      params:
        caller_identities: ["serviceAccount:sa-scoring@prj-example-app-dev.iam.gserviceaccount.com"]
        access_levels: ["corp_network"]
```

```bash
# 3. Bramki lokalnie — te same, które pojadą w CI. Kolejność od najtańszej.
#
#    UWAGA: `conftest` BEZ kontraktu widzi INNY stan świata niż CI i pokazuje czerwień na członkach,
#    których nie dotknąłeś. Bramka promocji porównuje deklarację ze stanem z OSTATNIEGO APPLY, a nie
#    z niczym: bez `--contract` jest uzbrojona dla KAŻDEGO członka `enforced`, więc każdy z nich wygląda
#    na promowany „teraz" — bez dowodu i bez okna obserwacji. Zmierzone: 2 czerwone linie o cudzym
#    członku na PR-ze, który zmieniał zupełnie co innego. Pobierz kontrakt tak, jak robi to CI:
gh release download contract --pattern contract.json --dir stan
python3 tools/collect_declarations.py --contract stan/contract.json > /tmp/dekl.json
conftest test --policy policy --namespace vpcsc.onboarding /tmp/dekl.json
python3 tools/attribute_budget.py --input /tmp/dekl.json
#    Brak release'u `contract` (repo przed pierwszym apply) jest stanem poprawnym — wtedy czerwień
#    bramki promocji jest OCZEKIWANA i CI zgłasza to samo, `::notice::brak release'u contract`.

# 4. Pull request. Opis odpowiada na pytanie, na które `change_ref` nie ma miejsca:
#    co ten członek realnie robi i czego w związku z tym potrzebuje.

# 5. Merge → apply.yml na gałęzi domyślnej. NIE jest to jeszcze koniec procedury.
```

### Weryfikacja — na żywym API, nie na zielonym pipeline

```bash
POLITYKA=$(python3 -c 'import yaml;print(yaml.safe_load(open("perimeter/policy.yaml"))["organization"]["access_policy_name"])')
NAZWA=$(python3 -c 'import yaml;print(yaml.safe_load(open("perimeter/policy.yaml"))["perimeter"]["name"])')
gcloud access-context-manager perimeters describe "$NAZWA" --policy="$POLITYKA" --format=json > /tmp/granica.json

# Numer projektu MUSI być w `spec.resources` (dry-run). W `status.resources` (egzekwowana) NIE MA go
# i tak ma być — nowy członek nie jest promowany tym pull requestem.
python3 - <<'PY'
import json
d = json.load(open("/tmp/granica.json"))
for k in ("status", "spec"):
    c = d.get(k) or {}
    print(k, "resources:", len(c.get("resources") or []), "ingress:", len(c.get("ingressPolicies") or []))
    print("   ", c.get("resources"))
PY
```

**Co ma się zgadzać:** `spec.resources` urosło **dokładnie o jeden** numer projektu, a `spec.ingressPolicies`
o tyle reguł, ile renderują wybrane profile. Liczba `status.*` **niezmieniona**. Jeżeli `spec.resources`
nie urosło, a pipeline był zielony — apply nie dojechał do tego zasobu albo dojechał do innej polityki;
zacznij od `docs/7-alerty.md#apply-nie-doszedł`, nie od czytania diffa.

### Pułapki

- **`dry_run_since` jest zegarem, nie metadaną.** Data z przeszłości „na skróty" skraca okno obserwacji
  o tyle samo dni, o ile skraca czekanie. Bramka promocji nie ma jak tego wykryć — mierzy wobec tego, co
  wpiszesz.
- **Projekt płaszczyzny sterowania.** Bramka `control_plane` odrzuci wpis wskazujący projekt z listy
  w `policy.yaml`. To jest **jedyny tryb awarii tego repozytorium, którego `git revert` NIE cofa** (konto
  apply traci dostęp do własnego stanu). Gdy wciągnięcie jest zamierzone, użyj `control_plane_exception`
  — nie usuwaj projektu z listy.
- **Powrót członka po offboardingu** to ten sam kanał, ale prerekwizyty są takie jak przy wejściu pierwszy
  raz (`docs/3-runbook-promocja-i-break-glass.md` §C).

### Jak cofnąć

`git revert` wpisu + apply. Członek znika ze `spec.resources`. Gdy był już **promowany**, kolejność jest
odwrotna niż intuicja i opisuje ją §C runbooka: najpierw wyprowadzenie z granicy, potem cokolwiek z projektem.

---

## 8.2 Dodanie profilu do katalogu

Katalog profili jest **jedyną** drogą dołożenia reguły — pole `exceptions:` w pliku członka zostało usunięte,
bo przez cały czas swojego istnienia nie renderowało ani jednej reguły, a schemat opisywał je jako działającą
furtkę (DEC-3, DEC-23). Dlatego „dodaj profil" pojawia się w dwóch runbookach jako **naprawa**: przy alercie
budżetu atrybutów (konsolidacja powtarzalnego wzorca) i po break-glassie (przepływ, którego reguła nie
przewidywała).

**Kto to zatwierdza.** Zespół sieciowy **i** Security (CODEOWNERS `perimeter/profiles/`). Profil to biblioteka
współdzielona: zmiana propaguje się na **każdą** dywizję, która go już wybrała — recenzuje się go jak zmianę
API, nie jak konfigurację. Profil z regułą egress opuszczającą Google Cloud (`to_external_from`) jest
**zawsze** `risk: high` i dokłada wnioskodawcom wymóg wpisu w §`egress_approvals`.

### Krok 0 — budżet atrybutów PRZED, nie po

```bash
python3 tools/collect_declarations.py | python3 tools/attribute_budget.py
```

Zapisz liczbę **przed**. Po dodaniu profilu i po pierwszym członku, który go wybierze, uruchom to samo
i porównaj — to jest jedyny moment, w którym koszt profilu widać jako **różnicę**, a nie jako sumę.

**Czym ta liczba NIE jest.** Narzędzie liczy **deklarację w repozytorium**, nie granicę w ACM. Odpowiada
na pytanie „ile będzie kosztował **następny** apply", a nie „ile kosztuje granica **dziś**". Gdy apply
zalega, obie liczby się rozjeżdżają i to jest **poprawne** zachowanie obu — stan granicy czyta
`tools/perimeter_watch.py` i `perimeters describe`, nie ten guard. Limit wynosi 6000 atrybutów
**na konfigurację**, liczony osobno dla egzekwowanej i dry-run.

### Krok 1 — kształt profilu rozstrzyga o `risk`, nie odwrotnie

`risk` **nie jest etykietą opisową — jest wejściem bramki** i jest sprawdzane wobec kształtu:

| kształt profilu | dopuszczalne `risk` | co dokłada wnioskodawcy |
|---|---|---|
| bez reguły egress | `low` | nic |
| egress **w granicach** Google Cloud (`to_projects_from`) | `medium` (`low` odrzucane) | nic |
| egress **poza** Google Cloud (`to_external_from`) | **`high`, wyłącznie** | wpis w `policy.yaml` §`egress_approvals` z **dokładnymi** celami i datą wygaśnięcia |

Wiersz trzeci jest tym, który procedura **egzekwuje**, a nie „wspomina": profil z `to_external_from`
i etykietą niższą niż `high` to obejście bramki jedną linią, więc zgodność etykiety z kształtem jest
osobną regułą OPA. Sprawdzisz to lokalnie, zanim pull request w ogóle powstanie:

```bash
# Para: profil z `to_external_from` i risk: high przechodzi; ten sam profil z risk: medium ma paść.
# `--contract` jak w §8.1 krok 3 — bez niego w wyniku siedzi czerwień bramki promocji na cudzych członkach
# i para przestaje być czytelna.
gh release download contract --pattern contract.json --dir stan
python3 tools/collect_declarations.py --contract stan/contract.json > /tmp/dekl.json
conftest test --policy policy --namespace vpcsc.onboarding /tmp/dekl.json
sed -i.bak 's/^risk: high$/risk: medium/' perimeter/profiles/<nowy>.yaml
python3 tools/collect_declarations.py --contract stan/contract.json > /tmp/dekl-zly.json
conftest test --policy policy --namespace vpcsc.onboarding /tmp/dekl-zly.json  # MA BYĆ CZERWONE
mv perimeter/profiles/<nowy>.yaml.bak perimeter/profiles/<nowy>.yaml
```

Bramka, której nie widziałeś odrzucającej, jest bramką, o której **nic nie wiesz** — para wyżej kosztuje
dwie minuty i zamyka tę wątpliwość raz.

### Krok 2 — selektory metod

Metody wypisujemy **jawnie**. `methods: ["*"]` jest dopuszczalne **wyłącznie** dla usług, które nie
publikują listy metod, i tylko wtedy, gdy usługa stoi w `policy.yaml` §`services_without_method_selectors`:

```bash
gcloud access-context-manager supported-services describe <usluga>   # supportedMethods puste?
python3 tools/check_supported_services.py --policy perimeter/policy.yaml
```

**Ostrzeżenie, które kosztowało cały apply:** katalog wspieranych usług **kłamie w obie strony** — patrz
[§8.4](#84-zmiana-restricted_services). Dla operacji z `permissions` (egress do zasobów zewnętrznych)
`check_supported_services.py` **świadomie nie orzeka**, bo katalog nie ma tam pokrycia; wartości pilnuje
reguła OPA zbudowana z pomiaru, a ostateczne „przyjmie / nie przyjmie" mówi dopiero apply.

### Krok 3 — pull request i apply

Opis pull requesta odpowiada na trzy pytania, których sam plik nie niesie: **jaki wzorzec** to jest
(czemu profil, a nie reguła u jednego członka), **ile kosztuje** (różnica z kroku 0) i **kto pierwszy
go wybierze**.

### Weryfikacja — na żywym API, dwa poziomy

**Profil, którego nikt nie wybrał, nie renderuje ani jednej reguły.** To nie jest awaria — to jest kształt
katalogu. Dlatego weryfikacja ma dwa poziomy i **oba** są konieczne:

```bash
# POZIOM 1 — profil dotarł do konsumentów. Kontrakt to jedyna rzecz, którą repozytorium dywizji widzi.
gcloud storage cat "gs://<bucket-kontraktow>/vpc-sc/contract.json" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print([p["name"] for p in d["profiles"]])'

# POZIOM 2 — profil DZIAŁA. Dopiero pierwszy członek, który go wybierze, dowodzi, że reguła
# w tym kształcie jest w ogóle aplikowalna.
gcloud access-context-manager perimeters describe "$NAZWA" --policy="$POLITYKA" --format=json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin);
print([r.get("title") or r for r in (d["spec"].get("ingressPolicies") or [])])'
```

**Dlaczego poziom 2 nie jest przesadą.** Profil `bq-omni-external-read` przeszedł schemat, OPA,
`terraform validate` i `plan`, stał w katalogu i był **nieaplikowalny od dnia powstania**: API odrzuca
`methods` przy ustawionym `external_resources`, przyjmuje wyłącznie `permissions`, a z uprawnień wyłącznie
jedno. Poznano to dopiero wtedy, gdy pierwszy członek go wybrał. **Profil bez ani jednego członka jest
deklaracją, nie funkcją** — i tak go w katalogu opisz, dopóki nie ma pierwszego.

### Jak cofnąć

`git revert` + apply. **Ale**: usunięcie profilu, który ktoś już wybrał, kasuje jego reguły przy
najbliższym apply — więc rewert profilu jest bezpieczny wyłącznie dopóki `grep -l <nazwa>
perimeter/projects.yaml` nie zwraca nic.

---

## 8.3 Dodanie i uzbrojenie access levelu

Access level jest warunkiem **kontekstu**, który musi spełnić wywołujący spoza granicy. Ma jeden tryb
awarii, którego **nie widać**: warunek przestaje pasować (zmienił się koncentrator VPN, doszło biuro,
dostawca przenumerował pulę NAT) — a obiekt w Access Context Managerze wygląda identycznie jak przedtem.
Pusty zbiór dopasowań jest nieodróżnialny od „nikt nie próbował". Ten sam kształt ma poziom oparty
o **placeholder**, którego nikt nie podmienił.

Dlatego katalog ma pole `armed` i dlatego ta procedura ma dwie połowy: **dodanie** (tanie, odwracalne)
i **uzbrojenie** (zmienia autoryzację, czasem natychmiast).

**Kto to zatwierdza.** Zespół sieciowy (CODEOWNERS `perimeter/access-levels/`). Poszerzenie zakresu tutaj
**po cichu poszerza każdą regułę, która ten poziom referuje** — także reguły dywizji, które o zmianie nie
wiedzą. Przy uzbrajaniu poziomu z `ip_subnetworks` zatwierdzającym jest **zespół sieciowy jako źródło
wartości**: pola `source_of_truth` i `reviewed` są wymagane i są zapisem tego, kto potwierdził zakres i kiedy.

### Kontrakt pól

| pole | kiedy wymagane | co znaczy |
|---|---|---|
| `armed: false` | zawsze, gdy poziom nie wpuszcza nikogo | „wiemy o tym, to jest decyzja" |
| `unarmed_reason` | przy `armed: false` (min. 30 znaków) | odróżnia decyzję od niedokończonej roboty |
| `unarmed_accepted_until` | przy `armed: false` **referowanym przez konfigurację egzekwowaną** | data przyszła; wymusza powrót do tematu |
| `source_of_truth` | przy `armed: true` z `ip_subnetworks` (min. 10 znaków) | skąd zakres: firewall / NAT / VPN / CMDB |
| `reviewed` | przy `armed: true` z `ip_subnetworks` | kiedy sieć potwierdziła zakres |
| `review_interval_days` | opcjonalne | jak długo atestacja jest ważna, zanim plan zaczerwieni |

Renderer sprawdza to `precondition`-ami **przed** wysłaniem czegokolwiek do API — plan pada z komunikatem,
a nie z `Error 400`. Trzy z nich łapią rzeczy niewidoczne w diffie:

- **zakresy wyłącznie dokumentacyjne** (RFC 5737 / RFC 3849) przy `armed: true` → plan czerwony;
- **kompozycja `armed: true` nad nieuzbrojonym składnikiem** → plan czerwony, bo `AND` dziedziczy
  nieosiągalność; warunek jest lokalny (rodzic vs bezpośrednie dzieci) i domyka się indukcyjnie;
- **poziom nieuzbrojony referowany przez konfigurację EGZEKWOWANĄ** → plan czerwony, chyba że niesie
  `unarmed_accepted_until` z datą przyszłą.

### Krok 1 — dodanie poziomu (bez uzbrajania)

```yaml
# perimeter/access-levels/corp.yaml
# NAZWA: `name` to short_name obiektu w ACM — musi zaczynać się LITERĄ i zawierać wyłącznie znaki
# alfanumeryczne oraz `_`. Myślnik jest odrzucany, a błąd wychodzi dopiero na apply.
  - name: branch_offices
    title: "Branch office networks"
    armed: false
    unarmed_reason: "czekamy na potwierdzenie puli NAT od zespolu sieciowego; do tego czasu poziom nikogo nie wpuszcza"
    ip_subnetworks:
      - "203.0.113.0/24"   # placeholder RFC 5737 — podmień
```

To jest stan, w którym poziom **wolno** zostawić na dłużej: nie autoryzuje nikogo i **mówi to wprost**.
Nie jest to stan, w którym wolno zostawić poziom **referowany przez regułę w konfiguracji egzekwowanej** —
tam reguła oparta na nim nie wpuszcza nikogo, a w konsoli wygląda na obecną.

### Krok 2 — uzbrojenie

Uzbrojenie to **wymiana treści warunku na taką, którą ktoś realnie spełnia** — nie przestawienie flagi.
Flaga jest tylko deklaracją, że wiesz, co robisz:

```yaml
  - name: branch_offices
    title: "Branch office networks"
    armed: true
    ip_subnetworks:
      - "198.51.100.0/24"          # zakres z systemu rekordu sieci, nie z pamięci
    source_of_truth: "CMDB: pula NAT oddzialow, rekord NET-1234"
    reviewed: "2026-01-15"
    review_interval_days: 180
```

**Blast-radius, zanim naciśniesz merge.** Wypisz, kogo ten poziom autoryzuje **po** zmianie:

```bash
# Które reguły referują ten poziom — w OBU konfiguracjach.
gcloud access-context-manager perimeters describe "$NAZWA" --policy="$POLITYKA" --format=json \
  | python3 - <<'PY'
import json, sys
d = json.load(sys.stdin)
for k in ("status", "spec"):
    for r in (d.get(k) or {}).get("ingressPolicies") or []:
        zrodla = (r.get("ingressFrom") or {}).get("sources") or []
        for z in zrodla:
            if "branch_offices" in (z.get("accessLevel") or ""):
                print(k, r.get("title"), (r.get("ingressFrom") or {}).get("identities"))
PY
```

Gdy choć jeden wiersz ma `status` — **autoryzacja zmienia się w chwili apply**, bez okna obserwacji.
Uzbrajaj wtedy w oknie, w którym ktoś patrzy, i miej gotowy rewert.

### Weryfikacja — para kanarków, bo z logu tego nie widać

To jest jedyny krok, którego **nie da się zastąpić odczytem konfiguracji**. `describe` pokaże treść, którą
sami wysłaliśmy. Audit-log zapisuje **naruszenia**, nie wpuszczenia — wywołanie, które granica wpuściła,
**nie zostawia w logu żadnego śladu** (zmierzone: to samo wywołanie ma wpis przed uzbrojeniem i nie ma go
po). Więc „poziom kogoś wpuszcza" da się stwierdzić wyłącznie **przychodząc z miejsca, które poziom
spełnia** — czyli generując ruch, nie obserwując go.

Służy do tego para reguł `canary-*` w `policy.yaml` i para poziomów `ci_probe_*`: **dwie reguły identyczne
poza jednym polem** (wymagany access level), wołane **tą samą** tożsamością, na tym samym projekcie,
w tej samej chwili, z tego samego runnera. Każda **wspólna** przyczyna odmowy — brak roli IAM, wyłączone
API, zepsuty projekt, nieobecna reguła — daje ten sam wynik po obu stronach i **nie potrafi wyprodukować
rozjazdu**. Rozjazd może pochodzić już tylko z poziomu.

```bash
# UZBROJONY: sonda „poziom spełniony" ma PRZEJŚĆ, „poziom niespełniony" ma dostać ODMOWĘ VPC-SC.
gh workflow run boundary-probe.yml -f project=<czlonek> -f expect=blocked -f kanarek=uzbrojony

# ROZBROJONY: ten sam przelot na konfiguracji sprzed uzbrojenia — OBA wywołania mają dostać ODMOWĘ.
gh workflow run boundary-probe.yml -f project=<czlonek> -f expect=blocked -f kanarek=rozbrojony
```

**Bez drugiego przelotu pierwszy jest obserwacją, nie dowodem.** „Sonda przeszła" jest prawdziwe także
wtedy, gdy reguła jest szersza, niż wygląda, gdy projekt nie jest w perimetrze i gdy usługa wypadła
z `restricted_services`. Dopiero **para** — ta sama sonda, ta sama tożsamość, jedyna różnica w uzbrojeniu
— pokazuje, że to poziom rozstrzyga. Przelot `rozbrojony` jest z tego powodu **zielony**, a nie czerwony:
mierzy stan, który ma zajść.

Kanarek stojący na warunku **tożsamościowym** mierzy MECHANIZM. We wdrożeniu z self-hosted runnerem
w sieci korporacyjnej ta sama para celuje wprost w poziom z **realnym zakresem** i wtedy odpowiedź na
pytanie „skąd wiemy, że zakres jest aktualny" jest mocniejsza niż data w polu `reviewed`: **bo wczoraj
ktoś tędy wszedł, i był to nasz własny przelot**.

### Jak cofnąć

`git revert` + apply — poziom wraca do `armed: false` z powodem. **Skasowanie** poziomu to inna procedura
i inna klasa problemu: kasowanie jest odrzucane przez bramkę, dopóki cokolwiek poziom referuje, a rola CI
dostała `accessLevels.delete` osobną decyzją (DEC-37). Kolejność `destroy` jest wymuszona w rendererze:
reguła → poziom, nigdy odwrotnie.

---

## 8.4 Zmiana `restricted_services`

**To jest jedyna nastawa, która decyduje, KTÓRE API granica w ogóle obejmuje.** Wszystko inne w tym
repozytorium mówi, kto i skąd może wejść; ta lista mówi, **czy jest gdzie wchodzić**. Usługa spoza listy
nie jest chroniona ani odrobinę — żadna reguła, żaden access level i żaden alert tego nie nadrobi.

**Blast-radius: wszyscy członkowie naraz, w obu konfiguracjach.** Lista nie jest per członek. Dodanie
usługi zaczyna odmawiać wywołań, które wczoraj przechodziły, **w każdym projekcie w granicy** —
w `spec` cicho (wpis w audit-logu), w `status` realną odmową. Usunięcie usługi zdejmuje ochronę tak samo
szeroko i **nie odpala żadnego alertu**: „granica obejmuje mniej" nie jest zdarzeniem, które cokolwiek
tu obserwuje. To jest asymetria, którą trzeba znać: dodanie zobaczysz po odmowach, usunięcia nie zobaczysz
w ogóle.

**Kto to zatwierdza.** Security **i** zespół sieciowy (CODEOWNERS `perimeter/policy.yaml`). Formularz
onboardingu świadomie tego pola nie ma i mieć nie będzie — dywizja nie zmienia definicji granicy.
Import brownfieldowy również tej listy **nie stosuje** (`manage_skeleton: false` zostawia treść szkieletu
u obecnego właściciela), więc w takim wdrożeniu ta sekcja jest dokumentacją, nie źródłem prawdy.

### Krok 0 — czy usługa jest w ogóle wspierana

```bash
# Bramka porównuje policy.yaml z ŻYWĄ listą wspieranych usług. Jedzie w `plan.yml`, bo to jedyne
# miejsce w pipeline z poświadczeniami GCP — `validate.yml` jest celowo offline.
python3 tools/check_supported_services.py --policy perimeter/policy.yaml

# Punktowo, dla jednej usługi — i od razu odpowiedź na pytanie o selektory metod:
gcloud access-context-manager supported-services describe <usluga>
```

Trzy sprawdzenia narzędzia zamykają trzy różne tryby awarii: usługa z `restricted_services` **jest**
wspierana · usługa z `services_without_method_selectors` **faktycznie** nie publikuje metod (nikt nie
przemyci `*` tam, gdzie da się wypisać metody) · usługa nie publikująca metod, a chroniona, **jest**
na liście wyjątków (profil użyje `*` i przejdzie OPA, zamiast paść na apply).

### Ostrzeżenie: katalog usług kłamie w OBIE strony

To nie jest ostrożnościowy zwrot, tylko zapis pomiaru. Dla `bigquery.googleapis.com` katalog
`supported-services describe`:

- **wymienia** uprawnienia, których API **odrzuca** w regule egress (`bigquery.jobs.create`,
  `bigquery.tables.getData`, `bigquery.tables.get` — każde padło `Error 400: PERMISSION ... is not
  supported`);
- **nie wymienia** jedynego, które API **przyjmuje** (`externalResource.read`).

Konsekwencja dla tej procedury: `check_supported_services.py` jest **warunkiem koniecznym, nie
wystarczającym**. Odpowiada na pytanie „czy ta usługa da się w ogóle objąć granicą" i na tym kończy się
jego zasięg — dla operacji z `permissions` świadomie nie orzeka. Ostateczne „API to przyjmie" mówi
wyłącznie apply na żywej polityce, a przy zmianie tej listy apply dotyczy **wszystkich** członków.

### Kroki

```bash
# 1. Zmiana w perimeter/policy.yaml. `vpc_accessible_services.same_as_restricted: true` znaczy, że lista
#    „co wolno wołać Z WNĘTRZA" idzie 1:1 — pod-skopowana cicho psuje bootstrap workloadów (usługa objęta
#    granicą, ale niedostępna od środka = błąd wyglądający na awarię aplikacji, nie na politykę).
# 2. Bramki offline + bramka żywa:
python3 tools/collect_declarations.py | python3 tools/attribute_budget.py   # INNY budżet — patrz niżej
python3 tools/check_supported_services.py --policy perimeter/policy.yaml
# 3. Pull request → merge → apply.
```

`restricted_services`, `vpc_accessible_services` i sama lista członków mają **własne, osobne limity** —
`attribute_budget.py` ich **nie liczy** i nie jest to przeoczenie: doliczanie ich mieszałoby dwa różne
budżety. Guard budżetu nie zaczerwieni się od tej zmiany i nie ma się od czego zaczerwienić.

### Weryfikacja — na żywym API, obie konfiguracje

```bash
gcloud access-context-manager perimeters describe "$NAZWA" --policy="$POLITYKA" --format=json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin);
[print(k, len((d[k] or {}).get("restrictedServices") or []), sorted((d[k] or {}).get("restrictedServices") or [])) for k in ("status","spec")]'
```

**Co ma się zgadzać:** obie listy — `status` i `spec` — mają nową długość. Zmiana widoczna tylko w jednej
z nich znaczy, że apply dotknął jednej konfiguracji: przy `useExplicitDryRunSpec: true` obie są zapisywane
osobno i rozjazd między nimi jest realnym stanem, nie artefaktem odczytu.

Drugi krok weryfikacji jest **objawowy** i wykonuje się go, gdy usługa doszła do listy przy członku
w konfiguracji egzekwowanej — sondą, nie odczytem:

```bash
gh workflow run boundary-probe.yml -f project=<czlonek-egzekwowany> -f expect=blocked
```

### Jak cofnąć

`git revert` + apply. Lista wraca w tym samym apply. **Czego rewert nie cofa:** wywołań odrzuconych
w oknie między jednym a drugim apply — nie ma ich kto powtórzyć. Przy dodawaniu usługi do granicy
z niepustą konfiguracją egzekwowaną rewert jest planem awaryjnym, a nie strategią; strategią jest
dodanie usługi **najpierw** tam, gdzie wszyscy członkowie są w dry-run, i odczytanie naruszeń.

**Czego cofnąć się nie da bramką:** `aiplatform.googleapis.com` jest zablokowane przed usunięciem regułą
OPA (baseline chroni Vertex AI od dnia zero — DEC-1). Każda inna usługa może z tej listy zniknąć zwykłym
pull requestem i **nie odpali żadnego alertu**.
