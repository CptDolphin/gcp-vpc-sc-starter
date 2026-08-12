# 7. Alerty granicy — co robić, kiedy któryś odpali

Alert bez procedury budzi człowieka i zostawia go z pytaniem, co teraz. Każda polityka alertu w tym
repozytorium niesie `documentation.links` z URL-em na **konkretną kotwicę w tym pliku** — jeśli dopisujesz
alert, dopisz sekcję tutaj w tym samym pull requeście. Kotwice są stałe i pilnuje ich selftest.

**Skąd te alerty biorą dane.** Dwa niezależne źródła i to jest celowe:

| źródło | co widzi | co się z nim dzieje, gdy pipeline padnie |
|---|---|---|
| audit-logi Google (`monitoring.tf`) | ruch przez granicę, zmiany konfiguracji | **działa dalej** — logi powstają po stronie Google |
| `watch.yml` → metryki (`alerts.tf`) | czy nasza maszyneria żyje | **milknie**, dlatego alert `apply` ma warunek na BRAK danych |
| `watch.yml` → heartbeat poza GCP ([niżej](#dms-zewnetrzny)) | czy cokolwiek z powyższego jeszcze istnieje | **milknie — i o to chodzi**: obserwator siedzi poza tą organizacją i alarmuje sam |

Trzeci wiersz jest odpowiedzią na pytanie „a kto pilnuje pilnującego". Dwa pierwsze źródła i wszystkie
cztery polityki alertów leżą w **jednym projekcie GCP**. Skasowanie go albo wyłączenie mu billingu nie
odpala niczego, bo nie ma czego ewaluować — również warunku o braku danych, który też potrzebuje żywego
silnika. Dlatego ostatnia warstwa nie jest w GCP w ogóle.

**Kanały.** Dwa, celowo rozdzielone (`perimeter/alerting.yaml`):

* **pojemność** — budżet atrybutów, członkowie po terminie, `apply`, który nie doszedł;
* **bezpieczeństwo** — dryf, zmiana poza pipeline'em, odmowa w trybie egzekwowanym.

Alert o obejściu procesu w tej samej skrzynce co comiesięczne „zbliżasz się do 70%" kończy się zawsze
tak samo: odbiorca uczy się ignorować całą kategorię.

---

<a id="apply-nie-doszedl"></a>

## apply nie doszedł

**Alert:** `VPC-SC: zmiana granicy zmergowana i niezastosowana` (CRITICAL, kanał pojemnościowy).

**Kto to odczuwa:** dywizja, która zmergowała wniosek i usłyszała „zrobione", a jej projekt nie jest
w granicy. Każda następna decyzja o promocji liczy stan, którego w chmurze nie ma.

Polityka ma **dwa warunki i to są dwie różne procedury** — sprawdź w incydencie, który odpalił.

### Warunek „niezastosowana zmiana starsza niż próg"

Zmiana jest w gałęzi domyślnej i nie została zastosowana. Trzy tryby awarii dają ten sam objaw:

```bash
# 1. Który commit czeka i jaki był ostatni UDANY apply
gh run list --workflow=apply.yml --branch=main --limit=10 \
  --json databaseId,headSha,status,conclusion,createdAt

# 2. Co konkretnie czeka (zakres od ostatniego udanego apply do HEAD)
git log --first-parent <sha-ostatniego-udanego-apply>..HEAD -- perimeter terraform
```

* **przebieg padł** (`conclusion: failure`) → przeczytaj log. Najczęstsza przyczyna na tym stacku to
  `403` na odświeżeniu zasobu, którym konto `apply` zarządza, ale którego nie umie **przeczytać** —
  `apply` zaczyna od refreshu, więc każdy nowy typ zasobu wymaga uprawnienia odczytu w
  `iam-bootstrap/main.tf` (sekcja 3c). Objaw: `plan` zielony, `apply` czerwony, przy **każdej** zmianie.
* **przebieg się nie odpalił** (brak przebiegu dla tego SHA) → sprawdź `paths` w `apply.yml`. Zmiana poza
  `perimeter/**` i `terraform/**` świadomie nie uruchamia apply; zmiana wewnątrz, która nie uruchomiła —
  to jest defekt filtru albo wyłączone Actions.
* **przebieg wisi** (`status: in_progress` od godzin) → environment `perimeter-apply` czeka na recenzenta
  albo job stoi na `concurrency`. Zatwierdź lub anuluj; nie odpalaj drugiego apply „obok".

**Naprawa:** doprowadź `apply.yml` do zielonego. Ręczny `terraform apply` z laptopa **nie** jest naprawą —
zostawia stan, którego nie widział żaden pipeline, i zamienia ten alert na alert o dryfie.

### Warunek „obserwator granicy milczy"

Nie ma danych od `watchdog_absent_seconds`. To znaczy `watch.yml` nie chodzi — **albo** nie może pisać
metryk.

```bash
gh run list --workflow=watch.yml --limit=5 --json status,conclusion,createdAt
gcloud monitoring time-series list \
  --project=<projekt-monitoringu> \
  --filter='metric.type="custom.googleapis.com/vpcsc/apply_pending_seconds"' \
  --format='value(points[0].interval.endTime, points[0].value.int64Value)' 2>/dev/null | head -3
```

Trzy przyczyny w kolejności prawdopodobieństwa: (1) `terraform plan` w jobie `measure` pada — kolizja
blokady stanu z trwającym apply jest **normalna i tolerowana** (jeden brakujący pomiar), stała nie jest;
(2) konto `watch` straciło `roles/monitoring.metricWriter`; (3) **projekt monitoringu znalazł się wewnątrz
konfiguracji egzekwowanej** i zapis z GitHuba jest odrzucany przez samą granicę. Trzeci przypadek poznasz
po `VPC_SERVICE_CONTROLS` w logu joba `publish` — i wtedy jest to prawdziwy sygnał, nie fałszywy alarm:
w tym samym momencie apply też nie działa, bo stan Terraform leży w tym samym projekcie.

**Czwarta przyczyna nie da o sobie znać TĄ drogą:** projektu monitoringu już nie ma (skasowany albo bez
billingu). Wtedy nie odpala się nic, bo nie ma czego ewaluować — także tego warunku. Od tego jest
[obserwator poza tą organizacją](#dms-zewnetrzny), i to on odezwie się jako jedyny.

---

<a id="budzet-atrybutow"></a>

## budżet atrybutów

**Alerty:** `VPC-SC: budżet atrybutów perimetru` (WARNING) i `VPC-SC: budżet atrybutów wyczerpie się
w mniej niż próg krytyczny` (CRITICAL). Oba na kanał pojemnościowy.

**Kto to odczuwa:** następna dywizja w kolejce. Przekroczenie 6000 atrybutów to odrzucenie z API przy
`apply` — wniosek przechodzi review, dostaje zgodę i rozbija się na ostatnim kroku.

**Limit jest NA KONFIGURACJĘ, nie łączny.** `spec` (dry-run) i `status` (egzekwowana) mają po 6000.
Etykieta `config` w incydencie mówi, o którą chodzi. Nie sumuj ich i nie bierz maksimum — pierwsze alarmuje
przy dwóch zdrowych konfiguracjach, drugie ukrywa tę, która właśnie się zapycha.

**Skąd bierze się ta liczba — to nie jest to samo źródło, co bramka na pull requeście.** Alert liczy
atrybuty z **żywej granicy** (`servicePerimeters.get`), a nie z plików YAML. Powód jest konkretny:
`attribute_budget.py` modeluje renderer na podstawie deklaracji i jest przez to ślepy na wszystko, co jest
w granicy, a czego nie ma w Gicie — zdublowane reguły po nieudanym odzysku stanu, ręczne dopiski, dryf.
Bramka na PR-ze odpowiada na pytanie „czy moja zmiana się zmieści" (i tam deklaracja jest właściwa, bo
zmiany w chmurze jeszcze nie ma); alert odpowiada na pytanie „ile zostało w granicy". Obie liczby lądują
w podsumowaniu przebiegu `watch.yml` obok siebie, a ich rozjazd jest osobną kontrolą — z **dwiema**
przyczynami i dwiema procedurami: [rozjazd granicy z deklaracją](#rozjazd-granicy-z-deklaracja).

**Nie myl z drugą pulą:** wpisy członków konsumują osobny limit 40 000 „protected resources" **na politykę**.
Ten alert go nie dotyczy.

```bash
python3 tools/collect_declarations.py | python3 tools/attribute_budget.py --format markdown
```

Raport podaje koszt stały baseline'u, koszt marginalny **najdroższego** członka i wynikający z tego sufit
w członkach. Sufit liczy się najdroższym, nie średnią: pytanie brzmi „czy następny wniosek jeszcze wejdzie".

**Co robić, w kolejności rosnącego kosztu:**

1. **skonsoliduj profile** — dwa profile różniące się jedną metodą to dwa komplety `operations` w każdej
   regule. Scalenie jest zmianą w `perimeter/profiles/`, bez dotykania członków;
2. **zetnij selektory metod** — `methods: ["*"]` kosztuje tyle samo co jedna metoda, ale lista dziesięciu
   kosztuje dziesięć. Sprawdź, czy wyliczanie jest tam potrzebne;
3. **drugi perimetr** — to jest kryterium rewizji z DEC-1 i decyzja architektoniczna, nie operacyjna.
   Wymaga ADR-a: dwa perimetry znaczą dwie granice do utrzymania i ruch między nimi staje się egressem.

**Wariant predykcyjny** (`< days_to_limit_critical`) mówi coś innego niż statyczny: przy dzisiejszym tempie
uderzysz w limit w tym miesiącu. Konsolidacja profili to praca na tygodnie, więc na tym progu zaczyna się
planowanie, a nie reakcja. Prognoza to regresja liniowa z 30 dni; przy krótszej historii albo braku wzrostu
producent publikuje sentynelę 3650 dni i alert **nie odpala** — brak prognozy jest lepszy niż prognoza
z trzech punktów.

---

<a id="rozjazd-granicy-z-deklaracja"></a>

## rozjazd granicy z deklaracją

**To nie jest alert — to adnotacja w przebiegu `watch.yml`.** Nie budzi nikogo i nie ma polityki w Cloud
Monitoring. Jest tu, bo jako jedyna widzi pewien stan **od razu**, podczas gdy oba alerty, które go
docelowo złapią, mają progi czasowe.

```
budzet spec: ROZJAZD OCZEKIWANY   — granica ma 48 atrybutow, deklaracja opisuje 53 (roznica -5); apply ZALEGA (...)
budzet spec: ROZJAZD NIEOCZEKIWANY — granica ma 48 atrybutow, deklaracja opisuje 53 (roznica -5), a apply NIE zalega (...)
```

Pierwsza liczba to koszt policzony z **żywej granicy** (`servicePerimeters.get`), druga — z **deklaracji**
w `perimeter/**` (`attribute_budget.py`). Mają być równe. **Rozstrzyga drugie słowo komunikatu** —
producent rozróżnia dwa przypadki, bo mają różne procedury.

Oba idą jako `::warning::` i **żaden nie czerwieni przebiegu**. Nie dlatego, że drugi jest mniej ważny —
dlatego, że `measure` z czerwonym statusem zatrzymuje `publish` przez `needs`, więc metryki by nie powstały
i obserwator zamilkłby dokładnie w stanie, w którym ma krzyczeć. Wagę niesie prefiks, nie poziom adnotacji.

### „ROZJAZD OCZEKIWANY" — apply zalega

W Gicie jest zmergowana zmiana, której jeszcze nie ma w chmurze. Różnica jest **oczekiwana** i zniknie po
udanym `apply`. **Nie szukaj tu dryfu — nie znajdziesz go, i to jest zamierzone:**

* `drift_resources` jest w takim przebiegu **celowo 0** (dyskryminator „zmiana spoza Gita vs opóźnienie
  propagacji" — patrz [dryf granicy](#dryf-granicy), sekcja o niestrzelaniu po każdym apply),
* alert `apply` odezwie się dopiero po `apply_pending_seconds` (domyślnie godzina).

Czyli przez pierwszą godzinę po merge'u ta adnotacja jest **jedynym** sygnałem. Idź do **historii przebiegów
`apply`**, nie do granicy:

```bash
gh run list --workflow=apply.yml --limit=5 --json conclusion,headSha,createdAt,databaseId
gh run view <ID> --log-failed        # gdy ostatni jest czerwony
```

Nic nie rób „na granicy". Napraw przyczynę czerwonego `apply` i zmerguj poprawkę — różnica zamknie się sama.

**Zmierzone, żeby to nie było teorią** (2026-08-12, przebiegi `watch` `31565377821` i `31565606010`):
„granica ma 48, deklaracja 53" przy `drift_resources = 0` i `apply_pending_seconds = 72`. Przyczyną był
`apply`, który padł na numerze projektu nieistniejącego w organizacji — członek warty 5 atrybutów był
w deklaracji i nie było go w granicy. Kolejny `apply`, zdejmujący ten wpis, zamknął różnicę po ~9 minutach.
Adnotacja odsyłała wtedy do alertu o dryfie, czyli do kontroli, która w tym stanie milczy z definicji; to
jest defekt naprawiony właśnie tą sekcją i rozróżnieniem w komunikacie.

### „ROZJAZD NIEOCZEKIWANY" — apply nie zalega

Git i chmura **powinny** być zgodne, a nie są. Dwa źródła, oba warte reakcji:

1. **ktoś zmienił granicę poza pipeline'em** — to jest [dryf granicy](#dryf-granicy) i ma własny alert
   CRITICAL na kanale bezpieczeństwa. Zacznij od niego;
2. **modele rozjechały się arytmetycznie** — `attribute_budget.py` modeluje renderer z `terraform/locals.tf`.
   Gdy renderer się zmienia (kolaps reguł, `*` zamiast listy, nowe pole w API), a model nie — komunikat
   wygląda **identycznie** jak dryf, choć w granicy nie ma nic obcego.

**Rozstrzyga porównanie regułą po regule, nie sum.** Równe sumy nie dowodzą parytetu — dwa błędy potrafią
się znieść:

```bash
gcloud access-context-manager perimeters describe <NAZWA> --policy=<NUMER> --format=json > /tmp/zywa.json
python3 tools/collect_declarations.py | python3 tools/attribute_budget.py --format json
python3 - <<'PY'
import json, sys; sys.path.insert(0, "tools")
import perimeter_watch as pw
p = json.load(open("/tmp/zywa.json"))
for k in ("spec", "status"):
    cfg = p.get(k) or {}
    print(f"== {k}: razem {pw.koszt_konfiguracji(cfg)}")
    for r in (cfg.get("ingressPolicies") or []) + (cfg.get("egressPolicies") or []):
        print("  ", r.get("title"), pw.koszt_konfiguracji(
            {"ingressPolicies": [r]} if "ingressFrom" in r else {"egressPolicies": [r]}))
PY
```

Zestaw wynik z `per_member` i `baseline_fixed` z raportu deklaracyjnego. Reguła, która występuje po jednej
stronie i nie po drugiej — albo kosztuje inaczej — wskazuje, którą stronę naprawiać. Poprawka modelu idzie
**najpierw do startera** (`.starter-sync`), bo inaczej granica chodzi na innym kodzie niż jego źródło.

---

<a id="dryf-granicy"></a>

## dryf granicy

**Alerty:** `VPC-SC: granica rozjechana z Gitem (dryf)` (CRITICAL, kanał bezpieczeństwa) oraz
`VPC-SC: konfiguracja zmieniona poza pipeline'em` (CRITICAL, kanał bezpieczeństwa).

**Kto to odczuwa:** właściciel granicy — od tej chwili Git nie opisuje rzeczywistości, więc review,
`git revert` i raport zgodności mówią o konfiguracji, której w chmurze nie ma.

**To są dwie warstwy tego samego objawu, nie duplikat:**

| alert | źródło | latencja | co mówi |
|---|---|---|---|
| `konfiguracja zmieniona poza pipeline'em` | audit-log ACM | minuty | **KTO** zmienił i jaką metodą |
| `granica rozjechana z Gitem` | `terraform plan` | ~1 h | **CO** się rozjechało i że **wciąż** trwa |

Pierwszy sam nie powie, czy naprawiono; drugi sam da godzinę zwłoki na sygnale bezpieczeństwa.

**Kolejność działań — najpierw dowód, potem naprawa:**

```bash
# 1. KTO i CO. Audit-log jest jedynym miejscem, w którym to jeszcze jest — apply go nadpisze.
gcloud logging read 'protoPayload.serviceName="accesscontextmanager.googleapis.com"
  AND NOT protoPayload.methodName:("Get" OR "List")' \
  --organization=<ORG_ID> --freshness=6h \
  --format='table(timestamp, protoPayload.authenticationInfo.principalEmail, protoPayload.methodName)'

# 2. CO KONKRETNIE różni się od Gita
terraform -chdir=terraform plan -no-color | head -60
```

**Nie „naprawiaj" tego ślepym apply.** Apply kasuje dowód, a jeśli zmiana była zasadna (ktoś gasił pożar) —
cofa ją bez rozmowy z tym, kto ją wprowadził. Dopiero po ustaleniu KTO i PO CO:

* zmiana **nieuprawniona** → incydent bezpieczeństwa. Przywrócenie stanu z Gita to `apply` na nietkniętym
  repozytorium (`git revert` nie pomoże — w repo nic się nie zmieniło), a potem postmortem: jak ktoś ominął
  `apply.yml` i czy warstwa IAM Deny w ogóle stoi (`tools/deny_check.sh`);
* zmiana **zasadna, zrobiona w pośpiechu** → dopisz ją do repozytorium pull requestem i przepuść przez
  bramki. Wtedy dryf znika bez cofania czegokolwiek.

### Dlaczego ten alert nie strzela po każdym apply

Bo dwa niezależne mechanizmy odróżniają zmianę spoza Gita od **opóźnienia propagacji**:

1. **producent** publikuje `drift_resources = 0`, kiedy w Gicie stoi jeszcze niezastosowana zmiana — wtedy
   niepusty plan jest oczekiwany i mówi o nim alert `apply`, nie ten;
2. **konsument** wymaga, żeby różnica **utrzymała się** przez `drift_persist_seconds` (domyślnie 1 h).
   Zmierzone: konfiguracja w ACM wraca natychmiast, a **skutek** propaguje się ~20 s dłużej (rollback:
   46 s do apply, 78 s do powrotu ruchu). Godzina to 180× ten margines.

Reguła licząca różnicę w oknie krótszym niż propagacja strzelałaby po każdym apply — i nauczyłaby dyżurnego
ignorować ją w tydzień.

---

<a id="czlonek-po-terminie"></a>

## członek po terminie

**Alert:** `VPC-SC: członek granicy po dacie review_by` (WARNING, kanał pojemnościowy).

**Kto to odczuwa:** audyt i security — projekt korzysta z granicy na podstawie zgody, której nikt nie
odnowił.

```bash
python3 - <<'PY'
import datetime, sys
sys.path.insert(0, "tools")
import projects_file
doc = projects_file.wczytaj(".")
dzis = datetime.date.today()
for m in doc["members"]:
    if datetime.date.fromisoformat(str(m["review_by"])) < dzis:
        print(m["project_id"], m["owner_group"], m["review_by"], m["stage"])
PY
```

**Dlaczego alert, skoro jest `expiry-sweep.yml`.** Sweeper chodzi raz w miesiącu i otwiera pull requesta,
więc w najgorszym razie wpis żyje 29 dni po terminie, zanim ktokolwiek się dowie. Gorzej: sweeper, który
przestał chodzić, **nie zgłasza niczego**, a jego cisza wygląda identycznie jak „nikt nie wygasł". Ten
alert mierzy STAN, więc świeci również wtedy, gdy zepsuł się sam sweeper.

**Dwie drogi wyjścia, obie przez pull requesta:**

* **projekt nadal potrzebny** → nowy `review_by` z odniesieniem do ticketu w `change_ref`. To jest
  odnowienie zgody, a nie formalność — ktoś musi potwierdzić, że dostęp dalej ma sens;
* **projekt zbędny** → offboarding. Uwaga na kolejność przy konfiguracji egzekwowanej: **najpierw**
  wyprowadź członka z perimetru (PR + apply), **potem** kasuj projekt. Odwrotnie zostaje w konfiguracji
  martwy numer projektu.

Usunięcie członka z konfiguracji egzekwowanej **zdejmuje z niego ochronę** — to jest zmiana bezpieczeństwa
i idzie tą samą ścieżką review co onboarding.

---

<a id="odmowa-w-trybie-egzekwowanym"></a>

## odmowa w trybie egzekwowanym

**Alert:** `VPC-SC: ruch odrzucony w trybie egzekwowanym` (CRITICAL, **oba** kanały).

**Kto to odczuwa:** albo workload, który właśnie przestał działać, albo nikt — bo zadziałała granica.
Rozstrzygnięcie, które z dwóch, jest treścią tego alertu, i dlatego idzie do obu odbiorców naraz.

Pełna procedura: [`3-runbook-promocja-i-break-glass.md`](3-runbook-promocja-i-break-glass.md) §B.

**Jedna rzecz, na której ten odczyt łamie się najczęściej — zmierzona:** wpis o odmowie **egzekwowanej nie
ma pola `dryRun`**. Pojawia się ono wyłącznie przy dry-run, z wartością `true`. Filtr `dryRun="false"` nie
zwraca więc **nigdy niczego** — w żadnej organizacji. Poprawnie:

```
protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"
AND NOT protoPayload.metadata.dryRun="true"
```

Druga: wpis leży w logu **projektu członkowskiego**, nie organizacji — `--organization` na tym samym
filtrze zwraca 0.

---

<a id="dms-zewnetrzny"></a>

## Obserwator poza tą organizacją — dead-man's-switch

**To nie jest polityka alertu w GCP i celowo nie może nią być.** Cztery alerty powyżej stoją w projekcie
monitoringu — tym samym, w którym leży stan Terraform, pula WIF i buckety kontraktów. Ta warstwa odpowiada
na jedyne pytanie, którego tamte cztery nie potrafią zadać: **czy ten projekt w ogóle jeszcze istnieje.**

**Jak działa.** Ostatni krok joba `publish` w `watch.yml` wysyła po udanej publikacji metryk jeden `GET`
na URL checka u zewnętrznego dostawcy dead-man's-switcha. Dostawca liczy czas od ostatniego pingu i gdy
przekroczy okno — alarmuje **własnym kanałem**, którego nasza organizacja GCP nie dotyka.

**Co pokrywa, czego nie.** Ping idzie na końcu łańcucha, więc jego brak znaczy, że pękło którekolwiek
ogniwo:

| tryb awarii | czy widzą go alerty w GCP | czy widzi go ta warstwa |
|---|---|---|
| `apply` padł / wisi / nie odpalił się | tak (`vpcsc_apply_stale`) | tak, ale wolniej — nie po to tu jest |
| `watch.yml` nie chodzi (Actions wyłączone, brak minut) | tak, warunkiem o braku danych | tak |
| konto `watch` straciło `timeSeries.create` | tak, warunkiem o braku danych | tak |
| projekt monitoringu wewnątrz konfiguracji egzekwowanej | tak (`condition_absent`) | tak |
| **projekt monitoringu SKASOWANY / billing wyłączony** | **NIE — nie ma czego ewaluować** | **tak** |
| repozytorium skasowane, organizacja GitHuba zawieszona | nie | tak |
| padł sam dostawca DMS | — | fałszywy alarm; degradacja w bezpieczną stronę |

Ostatni wiersz jest ceną tej warstwy i jest tania: fałszywy alarm kosztuje jedno sprawdzenie, cisza po
skasowanym projekcie kosztuje granicę bezpieczeństwa, o której nikt nie wie, że przestała być pilnowana.

**Gdzie leży poświadczenie i dlaczego akurat tam.** URL pingu to **GitHub Actions secret `DMS_PING_URL`
na poziomie repozytorium**. Nie environment (`watch` nie używa żadnego, a environment z recenzentem
zatrzymałby heartbeat na review) i nie żaden magazyn sekretów w chmurze — konsumentem jest runner
GitHuba, więc każde ogniwo pośrednie dokłada rzecz, która może paść sama z siebie i wyprodukować alarm
o granicy, kiedy granica ma się dobrze. Secret **nie jest podawany do joba `measure`**: URL pozwala
uciszyć DMS, a `measure` chodzi na koncie impersonowalnym z każdego pull requesta. Pilnuje tego guard
`heartbeat DMS we właściwym jobie` w `validate.yml`.

**Okno ciszy jest ZWIĄZANE z `watchdog_absent_seconds`** z `perimeter/alerting.yaml` (3 h): `period` = 1 h
(kadencja `watch.yml`) + `grace` = 2 h. Musi tolerować dwa pominięte przebiegi, bo cron GitHuba jest
best-effort, a kolizja blokady stanu z trwającym `apply` wywraca `measure` celowo. **Zmieniasz kadencję
`watch.yml` — zmień okno u dostawcy i `watchdog_absent_seconds`; to trzy liczby opisujące jedną decyzję.**
Nie ma pingu `/fail` przy porażce joba: alarmowałby na zdarzeniu znanym i samonaprawialnym.

### Uzbrojenie

```bash
# 1. Załóż check u dostawcy: period 1h, grace 2h, i PRZYPNIJ MU KANAŁ POWIADOMIEŃ.
#    Check bez kanału to najczęstszy sposób, w jaki DMS staje się dekoracją: świeci się
#    na dashboardzie, na który nikt nie patrzy, bo po to był DMS, żeby nie trzeba było patrzeć.
# 2. Wstrzyknij URL pingu jako sekret — wartość z pliku albo ze stdin, NIGDY w argumencie
#    (argumenty lądują w historii powłoki i w `ps`).
gh secret set DMS_PING_URL --repo <owner>/<repo> < /sciezka/do/pliku-z-url

# 3. Uzbrojenie potwierdza sam przebieg, nie deklaracja:
gh workflow run watch.yml --repo <owner>/<repo>
gh run list --workflow=watch.yml --limit=1 --json conclusion,url
#    W podsumowaniu przebiegu ma stać "Dead-man's-switch (poza GCP): ping wyslany".
#    Wiersz "NIEUZBROJONY" = sekretu nie ma i warstwy nie ma.
```

Kolejność ma znaczenie i jest samosprawdzająca: check założony **przed** wpięciem sekretu zaczyna odliczać
od razu, więc jeśli uzbrojenie utknie w połowie, dostawca zaalarmuje sam po oknie. Nie da się zostawić tego
w stanie „prawie zrobione".

### Triage — dostawca zgłosił, że heartbeat zamilkł

Idź od najtańszego sprawdzenia do najdroższego; pierwsze, które odpowie „nie", jest przyczyną.

```bash
# 1. Czy `watch.yml` w ogóle chodzi? (Actions wyłączone, wyczerpane minuty, awaria GitHuba)
gh run list --workflow=watch.yml --limit=5 --json status,conclusion,createdAt,url

# 2. Chodzi, ale czerwony — który job? `measure` czerwony raz na jakiś czas jest NORMALNY
#    (kolizja blokady stanu z trwającym apply). Czerwony stale — nie jest.
gh run view <run-id> --log-failed | tail -40

# 3. Zielony, a pingu nie ma → sekret zniknął albo dostawca odrzuca. Szukaj w podsumowaniu
#    przebiegu wiersza "NIEUZBROJONY" (skasowany sekret) albo adnotacji "ping nie doszedl".

# 4. Wszystko powyżej wygląda dobrze → sprawdź to, po co ta warstwa istnieje:
gcloud projects describe <projekt-monitoringu> --format='value(lifecycleState)'   # ACTIVE?
gcloud beta billing projects describe <projekt-monitoringu> \
  --format='value(billingEnabled)'                                                # True?
```

`lifecycleState: DELETE_REQUESTED` znaczy, że projekt jest w 30-dniowym oknie kasowania i **da się go
jeszcze odzyskać** (`gcloud projects undelete`). To jest ten moment, dla którego cała warstwa powstała —
po oknie zostaje odtworzenie stanu Terraform i puli WIF od zera.

### Test negatywny tej warstwy

Obowiązkowy i osobny od testów alertów w GCP, bo mierzy inny tor. Nie wolno go zrobić ręcznym `curl`-em
w drugą stronę — sprawdzałby palce, nie mechanizm.

1. **Kontrola pozytywna:** potwierdź, że check jest `up` i że ostatni ping pochodzi z **przebiegu
   `watch.yml`**, a nie z ręcznego wywołania (porównaj znacznik czasu pingu z czasem przebiegu).
2. **Zatrzymaj sygnał.** Nie rozbrajaj maszynerii produkcyjnej — **skróć okno checka** u dostawcy do
   wartości minutowych i przeczekaj jedną kadencję bez pingu.
3. **Asercja:** check przechodzi w `down`, a powiadomienie dociera **kanałem dostawcy**. Dowód do
   runbooka: status z API dostawcy + wpis w historii przejść (`flips`), nie zrzut ekranu.
4. **Przywróć okno** (1 h / 2 h) i pokaż powrót do `up` po najbliższym przebiegu `watch.yml`.

### Rotacja

URL pingu jest poświadczeniem bearer — kto go ma, ten potrafi uciszyć DMS. Rotacja = nowy check u dostawcy
(albo regeneracja URL-a, jeśli dostawca to potrafi) → `gh secret set DMS_PING_URL` → ręczny przebieg
`watch.yml` → potwierdzenie, że **nowy** check dostał ping → skasowanie starego. W tej kolejności: check
skasowany jako pierwszy zostawia okno, w którym nikt nie pilnuje i nikt o tym nie wie.

---

<a id="test-negatywny"></a>

## Test negatywny — alert, którego nikt nie widział, jak strzela

Alert bez testu negatywnego jest deklaracją. Każdy z powyższych ma dać się odpalić **sztucznie**, i to
jest część Definition of Done, a nie ćwiczenie.

Warunki progowe odpala się, publikując punkt metryki o wartości przekraczającej próg — tą samą drogą,
którą pisze producent, tylko z inną liczbą:

```bash
TOKEN=$(gcloud auth print-access-token)
TERAZ=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://monitoring.googleapis.com/v3/projects/<PROJEKT>/timeSeries" -d "{
    \"timeSeries\":[{
      \"metric\":{\"type\":\"custom.googleapis.com/vpcsc/attribute_budget_percent\",
                  \"labels\":{\"config\":\"spec\"}},
      \"resource\":{\"type\":\"global\",\"labels\":{\"project_id\":\"<PROJEKT>\"}},
      \"points\":[{\"interval\":{\"endTime\":\"$TERAZ\"},\"value\":{\"doubleValue\":85}}]}]}"
```

Po odpaleniu **zweryfikuj, że incydent realnie istnieje** — `gcloud alpha monitoring policies list` mówi
tylko, że polityka jest, a nie że zadziałała:

```bash
gcloud alpha monitoring policies list --project=<PROJEKT> \
  --format='table(displayName,enabled,severity)'
curl -sS -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://monitoring.googleapis.com/v3/projects/<PROJEKT>/alertPolicies" >/dev/null   # sanity
```

Incydenty czyta się z Cloud Console (`Monitoring → Alerting → Incidents`) albo z API
`projects.alertPolicies` + `incidents` — a najpewniejszym dowodem jest wiadomość, która **doszła
do kanału**. Jeśli kanał e-mail jest `UNVERIFIED`, incydent się otworzy i **nie dojdzie nic**:

```bash
gcloud alpha monitoring channels list --project=<PROJEKT> \
  --format='table(displayName,type,verificationStatus)'
```

**Warunek `condition_absent` (watchdog) ma własną pułapkę:** jest znaczący dopiero **po pierwszym
zapisie**. Metryka, do której nigdy nic nie napisano, nie jest „nieobecna" — jest nieznana, i alert nie
odpali. Dlatego deskryptory metryk powstają w Terraformie, a `watch.yml` ma wyzwalacz `workflow_run` na
`apply`: pierwszy punkt pojawia się minuty po wdrożeniu.
