# Runbook — promocja członka do enforced i procedura awaryjna

Dwie procedury o przeciwnych kierunkach: pierwsza włącza ochronę, druga ją zdejmuje w incydencie. Obie mają
ten sam wymóg: **dowód, nie deklaracja**.

---

## A. Promocja dry-run → enforced

### Kiedy wolno

Wszystkie warunki muszą być spełnione (bramka `promotion_gate` w `policy/onboarding.rego` egzekwuje 1–3):

| Warunek | Próg | Skąd wiadomo |
|---|---|---|
| **Repo nie odstaje od startera** | `starter-drift` zielony | patrz krok 0 — bez tego pozostałe wiersze są dowodem z nieznanej wersji narzędzi |
| Czas w dry-run | `dry_run_min_days` z `policy.yaml` (domyślnie 14) | pole `dry_run_since` w pliku członka |
| Naruszenia w oknie | **0** w ostatnich `clean_window_days` (domyślnie 7) | `violations.json` z workflow `violations-report` |
| Raport w ogóle istnieje | wpis dla tego członka | brak wpisu = brak dowodu, nie „zero" |
| Rzadkie przepływy widziane | ocena człowieka | czy w oknie zmieścił się miesięczny batch / kwartalny job? |

> **Nie skracaj okna „bo zielono od trzech dni".** Dry-run rejestruje tylko to, co faktycznie zaszło.
> Najczęstszy tryb awarii po promocji to zadanie, które uruchamia się raz w miesiącu.

### Gdy warunku naprawdę nie da się spełnić — wyjątek, nie obniżenie baseline

Prędzej czy później trafi się przypadek, w którym okno obserwacji nie da się przeczekać (migracja
z terminem, projekt utworzony pod jeden pomiar) albo naruszenia w oknie pochodzą z audytu, a nie z ruchu
dywizji. Odruch jest jeden: obniżyć `dry_run_min_days` w `policy.yaml`. **To jest najgorsze z możliwych
wyjść** — poluzowuje reżim dla wszystkich dywizji naraz, bezterminowo i bez śladu, kto o to poprosił.

Do tego służy `onboarding.promotion_waivers` — wyjątek **per członek**, z datą ważności:

```yaml
onboarding:
  dry_run_min_days: 14
  clean_window_days: 7
  promotion_waivers:
    - member: <NAZWA_PLIKU_CZLONKA_BEZ_ROZSZERZENIA>
      justification: "<40+ znakow: dlaczego warunku nie da sie spelnic i czemu promocja mimo to jest bezpieczna>"
      approved_by: <KTO_ZATWIERDZIL>
      expires: "<YYYY-MM-DD>"
      accept_dry_run_days_below_minimum: true
      accept_violations_up_to: 2
```

Co ten kształt wymusza i dlaczego:

| Własność | Po co |
|---|---|
| `member` — jeden członek | decyzja nie rozlewa się na organizację; wyjątek na nieistniejącego członka jest **odrzucany**, żeby literówka nie udawała działającego wyjątku |
| `expires` — obowiązkowe | wyjątek przestaje działać sam. Bezterminowy jest obniżeniem baseline pod inną nazwą |
| mieszka w `policy.yaml` | ten plik jest pod CODEOWNERS Security. W pliku członka dywizja zwalniałaby się z bramki własnym PR-em |
| `accept_violations_up_to` — **liczba** | wyjątek na 2 naruszenia nie przepuści trzeciego: nowy przepływ w oknie znów zatrzymuje promocję |
| dwa osobne pola | zgoda na krótsze okno nie jest zgodą na naruszenia. Dwa warunki, dwie decyzje |
| uzasadnienie ≥ 40 znaków | dwa razy tyle, co przy `exceptions` członka — to zwalnia z warunku chroniącego dywizję przed odcięciem ruchu |

**Czego wyjątek NIE robi: nie zwalnia z obowiązku posiadania raportu naruszeń.** „Nie zmierzyliśmy" nie
jest stanem, o którym da się podjąć decyzję — wyjątek mówi „widzieliśmy N naruszeń i bierzemy je na
siebie", więc najpierw musi być co zobaczyć. Zwolnienie z dowodu zamieniłoby wyjątek w wyłącznik bramki.

Po promocji **usuń wyjątek** tym samym PR-em co następna zmiana konfiguracji — albo pozwól mu wygasnąć.
Wyjątek, który przeżył swój powód, jest dokładnie tym, przed czym broni `expires`.

### Kroki

0. **Sprawdź, czy to repo nie odstaje od startera — PRZED raportem, nie po nim:**

```bash
gh workflow run starter-drift.yml && gh run watch
```

   Ten krok jest tu, bo pominięcie go już raz kosztowało dowód. Raport naruszeń przez pewien czas
   przypisywał **0 z 26** realnych naruszeń do członka, a potem — po naprawie przypisania — czytał logi
   z zakresu, w którym ich nie ma (**0** wpisów na organizacji przy **30** w projekcie członka). Obie
   poprawki istniały w starterze, zanim ktokolwiek przeniósł je tutaj. W obu przypadkach `violations.json`
   pokazywał czyste okno, `promotion_gate` przechodził, a promocja opierałaby się na dowodzie, o którym
   dziś wiadomo, że kłamał. **Czerwony `starter-drift` = promocja czeka**, bo narzędzia produkujące dowód
   są częścią tego, co jest przestarzałe.

0b. **Zmierz, że wywołanie DZIAŁA, zanim je zablokujesz** — inaczej krok 6 nie ma z czym porównać:

```bash
gh workflow run boundary-probe.yml -f project=<PROJEKT_CZLONKA> -f expect=open && gh run watch
```

   Przelot musi być ZIELONY. Chroniona usługa z wyłączonym API i brak roli IAM zwracają ten sam
   `PERMISSION_DENIED`, co odmowa VPC-SC — bez tego pomiaru „przed" nie da się odróżnić granicy, która
   zadziałała, od projektu, który i tak był zepsuty. Sonda nazywa te trzy stany osobno i nie zaliczy
   dwóch pierwszych jako dowodu.

1. Uruchom raport za pełne okno:

```bash
gh workflow run violations-report.yml -f days=14
```

2. Pobierz artefakt `violations` i **przeczytaj `violations.md`**, nie tylko liczbę z JSON-a. Jeśli są
   naruszenia — to nie jest „szum", tylko lista wywołań, które przestaną działać.

3. Otwórz PR promocyjny: w pliku członka zmień **wyłącznie** `stage: dry-run` → `stage: enforced`.
   Wypełnij sekcję *Evidence* w szablonie PR-a.

   `violations.json` **dołącza się sam**: `validate.yml` pobiera artefakt `violations` z ostatniego udanego
   przebiegu `violations-report.yml` na gałęzi domyślnej i podaje go regułom OPA. Dlatego krok 1 nie jest
   formalnością — bez świeżego raportu (starszego niż `clean_window_days` też nie licząc) bramka odrzuci
   promocję na „brak raportu naruszeń dla okna obserwacji". **Ręcznie dopisanego pliku bramka nie przyjmie
   i przyjąć nie może**: dowód, który promujący sam sobie pisze, mierzy jego zdanie, nie ruch.

4. Bramki muszą przejść. Jeśli `promotion_gate` odrzuca — nie obchodź go zmianą `dry_run_since`. To pole jest
   datą wejścia do dry-run, nie parametrem do dostrojenia.

5. Merge → apply czeka na zatwierdzenie w environment `perimeter-apply`.

6. **Zmierz po apply** (done = zmierzone). Najpierw ta sama sonda co w kroku 0b, tylko z drugim
   oczekiwaniem — to jest **jedyny** dowód, że granica cokolwiek blokuje:

```bash
gh workflow run boundary-probe.yml -f project=<PROJEKT_CZLONKA> -f expect=blocked && gh run watch
```

   Zielony przelot znaczy komplet czterech rzeczy naraz: chronione wywołanie bez reguły zostało odmówione
   **z powodem VPC-SC** (nie z braku roli, nie z wyłączonego API), ruch dozwolony regułą ingress NADAL
   przechodzi, usługa spoza `restricted_services` NADAL działa (czyli projekt nie jest po prostu zepsuty),
   a odmowa ma niezależny drugi dowód we wpisie audytowym. Czerwony przelot mówi, KTÓRA z tych czterech
   nie zaszła.

   Reszta pomiaru:

```bash
terraform -chdir=terraform output members_enforced        # członek na liście
# ZAKRES = PROJEKT CZŁONKA, nie organizacja. Wpis audytowy VPC-SC ląduje w logu projektu, który jest
# właścicielem chronionego zasobu; `--organization=` czyta tylko `organizations/<id>/logs/…` i nic poniżej.
# Zmierzone: 0 wpisów na organizacji przy 30 w projekcie członka, ten sam filtr i to samo okno.
gcloud logging read 'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"
  AND protoPayload.metadata.dryRun="false"' --project=<PROJEKT_CZLONKA> --freshness=1h --limit=20
```

Puste drugie zapytanie przez pierwszą godzinę = ruch dywizji działa. Niepuste = masz incydent, przejdź do
sekcji B, zanim ktoś zadzwoni.

### Czego NIE robić: `perimeters dry-run enforce`

W dokumentacji Google i w połowie odpowiedzi ze Stack Overflow promocja dry-run wygląda tak:

```
gcloud access-context-manager perimeters dry-run enforce PERIMETER --policy=POLICY_ID
```

**Ta komenda nie jest naszą promocją i nie wolno jej tu uruchamiać.** Robi coś zupełnie innego:
commituje **CAŁĄ** konfigurację dry-run do egzekwowanej, jednym ruchem. W modelu jednego perimetru dla całej
organizacji konfiguracja dry-run zawiera **wszystkich** członków — także tych, którzy weszli wczoraj i mają
przed sobą dwa tygodnie okna obserwacji. Jedno wywołanie promuje więc trzydzieści dywizji naraz, w tym te,
których przepływów nikt nie zdążył zmierzyć. Skutek: masowe odcięcie ruchu bez ani jednego PR-a, którego
dałoby się zrewertować, bo w gicie nic się nie zmieniło.

Nasza promocja jest **per członek** i wygląda inaczej: jedno pole `stage` w jednym pliku, PR, bramki, apply.
Terraform dokłada wtedy pojedynczy zasób do konfiguracji egzekwowanej i nie rusza pozostałych.

Guard `no-dry-run-commit` w `validate.yml` pilnuje, żeby ta komenda nie trafiła do żadnego workflow ani
skryptu w `tools/`. Nie jest to guard przeciw złej woli — jest przeciw skopiowaniu jej z dokumentacji Google
w dobrej wierze, w pośpiechu, w trakcie incydentu.

### Przepływy, o których zapomina się przed pierwszym enforce

Raport naruszeń pokazuje ruch, który **faktycznie zaszedł** w oknie obserwacji. Ta lista to rzeczy, które w
oknie mogą się nie pojawić albo zostać zignorowane jako „nasze własne narzędzia" — a perimetr nie zna tej
kategorii i odrzuci je tak samo jak każde inne wywołanie spoza granicy:

| Przepływ | Dlaczego umyka | Gdzie to obsłużyć |
|---|---|---|
| **Skaner bezpieczeństwa** (CNAPP typu Wiz, SCC, agentless) | woła z infrastruktury dostawcy, więc nie spełni korpo-access-levelu; brak findingów wygląda jak brak problemów | `baseline_ingress` w `policy.yaml` — dotyczy KAŻDEGO członka, nie trzeba go wybierać |
| **Backup / DR** | uruchamia się raz w tygodniu albo w miesiącu — okno 14 dni może go nie zobaczyć | `baseline_ingress` albo profil, zależnie od zasięgu |
| **Monitoring i eksport metryk** | „to przecież nasze" — a to nadal wywołanie API spoza perimetru | `restricted_services` + reguła, albo projekt monitoringu w perimetrze |
| **CI/CD deployujący z zewnątrz** | zespół pamięta o aplikacji, nie o pipeline'ie, który ją wdraża | profil `cicd-deploy-from-outside` |
| **Rzadkie zadania** (kwartalny audyt, roczna recertyfikacja) | statystycznie nie mieszczą się w oknie | świadoma decyzja: wydłużyć okno albo przyjąć ryzyko i zapisać je |
| **Raport naruszeń tego perimetru** (`violations-report.yml`) | „to przecież nasza własna bramka" — a czyta audit-log projektu członka kontem planu, czyli woła `logging.googleapis.com` (usługę chronioną) spoza granicy | `baseline_ingress` §`platform-violations-read` — **musi istnieć PRZED pierwszą promocją** |

> **Ten ostatni wiersz jest inny od pozostałych i dlatego stoi osobno.** Wszystkie powyżej odcinają ruch
> DYWIZJI, a ten odcina **dowód**. W dry-run raport dopisuje członkowi naruszenie od samego siebie, więc okno
> nigdy się nie wyczyści; po promocji ten sam odczyt jest odmawiany, a workflow pada — czyli pierwsza udana
> promocja zabiera `violations.json` wszystkim następnym. Zmierzone na żywej organizacji 2026-08-10:
> 1 z 34 naruszeń członka pochodziło od `sa-vpcsc-plan`, metoda `LoggingServiceV2.ListLogEntries`.

**Jak to sprawdzić, zanim promujesz:** przejdź listę z właścicielem projektu i zapytaj wprost *„co się
uruchamia u was rzadziej niż raz na dwa tygodnie?"*. To pytanie wyłapuje więcej niż przeglądanie logów, bo
raport nie może pokazać czegoś, co się nie wykonało.

**Reguły `baseline_ingress` bez access levelu** wymagają jawnego `allow_without_access_level: true` i
approvalu Security — bo dotyczą wszystkich chronionych projektów naraz. Pominięcie pola nie daje tego samego
skutku co jego ustawienie; pilnuje tego reguła OPA.

---

## B. Break-glass — perimetr blokuje legalny ruch

### Zasada

Zdejmujemy członka z konfiguracji **egzekwowanej**, zostawiając go w **dry-run**. Incydent nie kasuje wiedzy
o jego ruchu — po naprawie promocja wymaga takiego samego dowodu jak za pierwszym razem.

### Kroki

1. Potwierdź, że to naprawdę perimetr (a nie IAM, nie sieć, nie aplikacja):

```bash
# ZAKRES = PROJEKT, w którym stanął ruch (patrz uwaga o zakresie w części A, krok 6). Na organizacji
# tych wpisów NIE MA i pusty wynik przeczytasz jako „to nie perimetr" — czyli odwrotnie niż jest.
gcloud logging read 'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"
  AND protoPayload.metadata.dryRun="false"' --project=<PROJEKT_CZLONKA> --freshness=1h \
  --format='table(protoPayload.authenticationInfo.principalEmail, protoPayload.methodName,
                  protoPayload.metadata.violationReason)'
```

`violationReason` mówi, czego zabrakło: `NO_MATCHING_ACCESS_LEVEL` (brak access levelu / zły kontekst) albo
`RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER` (projekt-cel poza granicą).

2. Uruchom procedurę:

```bash
gh workflow run break-glass.yml \
  -f member=<dywizja>-<projekt> \
  -f incident=INC0012345 \
  -f reason="scoring API returns 403 for the payments service"
```

3. Approverzy zatwierdzają environment `break-glass` — **jeśli** ten environment ma wymaganych recenzentów
   (funkcja płatna, sprawdź `gh api repos/<ORG>/<REPO>/environments/break-glass --jq '.protection_rules'`).
   Gdy ich nie ma, workflow rusza od razu; to nie jest awaria procedury, ale ma być zapisane jako
   odstępstwo (`docs/1`, etap 4), a nie odkryte w trakcie incydentu.

4. Workflow demotuje członka, applikuje i **sam otwiera issue postmortem**. Ślad audytowy zostaje w
   repozytorium, nie tylko w interfejsie Actions: kto uruchomił i odsyłacz do przebiegu idą do **treści
   commita** oraz do issue. Tam też stoi zdanie, o którym najłatwiej zapomnieć — **nie ma żadnego timera**:
   członek jest niechroniony do momentu ponownej promocji i nic mu o tym nie przypomni.

5. Zweryfikuj, że ruch wrócił (ta sama komenda z kroku 1 — ma być pusta).

### Po incydencie

Postmortem ma odpowiedzieć na jedno pytanie: **dlaczego okno obserwacji tego nie złapało?** Typowe
odpowiedzi i wnioski:

| Przyczyna | Wniosek |
|---|---|
| Przepływ rzadki (miesięczny job) | wydłuż okno dla tej klasy projektów, nie dla wszystkich |
| Przepływ nowy (wdrożenie w trakcie okna) | promocja musi być po zamrożeniu zmian u dywizji |
| Brak profilu pokrywającego wzorzec | dodaj profil (trzeci taki sam wyjątek = sygnał, nie czwarty wyjątek) |
| Access level za wąski | popraw access level — to zmiana dotykająca wszystkich, więc osobny PR |

Ponowna promocja: świeże okno, świeży raport, ten sam próg. Skrócenie okna „bo już raz było zielono" to
dokładnie ta decyzja, która wywołała incydent.

---

## C. Offboarding (dla porządku)

Usunięcie pliku członka wyprowadza projekt z **obu** konfiguracji. To także zmiana granicy bezpieczeństwa —
projekt przestaje być chroniony — więc idzie przez ten sam review co dołączenie. Automatyczny PR z
`expiry-sweep` jest **propozycją**: właściciel może zamiast tego potwierdzić wpis nową datą `review_by`.
