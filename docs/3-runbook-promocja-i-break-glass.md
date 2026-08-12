# Runbook — promocja członka do enforced i procedura awaryjna

Dwie procedury o przeciwnych kierunkach: pierwsza włącza ochronę, druga ją zdejmuje w incydencie. Obie mają
ten sam wymóg: **dowód, nie deklaracja**.

---

## A. Promocja dry-run → enforced

### Kiedy wolno

Wszystkie warunki muszą być spełnione (bramka `promotion_gate` w `policy/onboarding.rego` egzekwuje wszystkie
poza pierwszym i ostatnim — tamte sprawdza osobny workflow i człowiek):

| Warunek | Próg | Skąd wiadomo |
|---|---|---|
| **Repo nie odstaje od startera** | `starter-drift` zielony | patrz krok 0 — bez tego pozostałe wiersze są dowodem z nieznanej wersji narzędzi |
| Czas w dry-run | `dry_run_min_days` z `policy.yaml` (domyślnie 14) | pole `dry_run_since` w pliku członka |
| Naruszenia w oknie | **0** w ostatnich `clean_window_days` (domyślnie 7) | `violations.json` z workflow `violations-report` |
| Raport w ogóle istnieje | wpis dla tego członka | brak wpisu = brak dowodu, nie „zero" |
| **Zakres ciszy potwierdzony** | `unmeasured_peers_ack` = liczba członków zostających w dry-run | nagłówek `violations.md`; DEC-27 — ruch między dwoma członkami w dry-run NIE MOŻE dać wpisu |
| Rzadkie przepływy widziane | ocena człowieka | czy w oknie zmieścił się miesięczny batch / kwartalny job? |

> **Nie skracaj okna „bo zielono od trzech dni".** Dry-run rejestruje tylko to, co faktycznie zaszło.
> Najczęstszy tryb awarii po promocji to zadanie, które uruchamia się raz w miesiącu.

### Dokąd te warunki sięgają: do momentu WŁĄCZENIA, nie na zawsze

Bramka pyta o **przejście**, a nie o stan (DEC-18). Warunki egzekwowane przez bramkę obowiązują dopóty, dopóki repo deklaruje
`enforced`, a ostatni apply opublikował dla tego członka co innego — czyli dopóki decyzja jest przed nami.
Gdy kontrakt (`gh release download contract`) potwierdzi `stage: enforced`, granica **już działa** i te
same liczby znaczą co innego: naruszenia w oknie to teraz **odmowy**, czyli dowód, że perimetr robi swoje.
Bramka je wtedy przemilcza; od patrzenia na nie jest alert `vpcsc-violations-enforced`, nie `validate`.

Praktyczne konsekwencje przy diagnozie:

- **`validate` czerwony komunikatem o promocji na PR-ze, który promocji nie dotyczy** = stan zastosowany
  jest nieznany. Sprawdź, czy istnieje release `contract` i czy `policy.yaml` ma sekcję `contract`
  z `publish_members: true`. To jest **świadome fail-closed**: brak wiedzy o stanie zastosowanym uzbraja
  bramkę dla każdego członka `enforced`, żeby wyłącznikiem kontroli nie było usunięcie pliku.
- **Członek promowany, ale apply jeszcze nie przeszedł** (kolejka single-flight, czerwony przebieg):
  kontrakt nadal mówi `dry-run`, więc bramka pilnuje wniosku dalej — i tak ma być, bo granica realnie
  nie jest jeszcze włączona.
- **Wyjątek `promotion_waivers` po zastosowanej promocji jest zbędny.** Zdejmij go — jeśli `validate`
  bez niego jest zielony, wyjątek nie pokrywał ryzyka, tylko maskował pytanie o stan.

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

   Przeczytaj też nagłówek raportu: **listę członków, którzy zostają w dry-run**. To jest zakres, w którym
   „czysto" NIC nie znaczy (DEC-27, sekcja „Przepływ, który ZASZEDŁ…" niżej). Zapytaj właściciela wprost,
   czy jego projekt rozmawia z którymkolwiek z nich — bo tego pytania raport nie zada za Ciebie.

3. Otwórz PR promocyjny: w pliku członka zmień `stage: dry-run` → `stage: enforced` i dopisz
   `unmeasured_peers_ack: <liczba z raportu>`. **Nic więcej** — dwa pola, oba wskazane przez raport.
   Wypełnij sekcję *Evidence* w szablonie PR-a.

   Bramka odrzuci liczbę inną niż faktyczna, więc pola nie da się „przeklikać": jeśli między wygenerowaniem
   raportu a merge'em dołączy kolejna dywizja, promocja staje i wracasz do kroku 1. Po zastosowaniu promocji
   pole jest historią — usuń je przy najbliższej zmianie pliku, inaczej bramka zgłosi je jako nieaktualne.

   `violations.json` **dołącza się sam**: `validate.yml` pobiera artefakt `violations` z ostatniego udanego
   przebiegu `violations-report.yml` na gałęzi domyślnej i podaje go regułom OPA. Dlatego krok 1 nie jest
   formalnością — bez świeżego raportu (starszego niż `clean_window_days` też nie licząc) bramka odrzuci
   promocję na „brak raportu naruszeń dla okna obserwacji". **Ręcznie dopisanego pliku bramka nie przyjmie
   i przyjąć nie może**: dowód, który promujący sam sobie pisze, mierzy jego zdanie, nie ruch.

4. Bramki muszą przejść. Jeśli `promotion_gate` odrzuca — nie obchodź go zmianą `dry_run_since`. To pole jest
   datą wejścia do dry-run, nie parametrem do dostrojenia.

5. **Merge NIE JEST promocją — apply zatrzyma się sam.** Po scaleniu `apply.yml` rusza, wykonuje bramki
   i **staje na bramce promocji**, zanim weźmie zamek stanu. Przebieg jest CZERWONY i wypisuje, kogo ten
   apply zacząłby egzekwować. To jest zamierzone: promocja to jedyna zmiana w tym repozytorium, której
   skutkiem jest odmowa ruchu (DEC-17).

   Przeczytaj listę z podsumowania przebiegu i uruchom apply ręcznie, wpisując **dokładnie tych** członków:

```bash
gh workflow run apply.yml -f promocje="<dywizja>-<project_id>" && gh run watch
```

   Lista musi być **równa** zbiorowi oczekujących promocji — nie podzbiorem ani nadzbiorem. Jeśli w
   międzyczasie ktoś scalił drugą promocję, bramka stanie ponownie: masz wtedy zatwierdzić obie świadomie
   albo zrewertować jedną. Drugie wyjście z zatrzymanego apply jest zawsze dostępne i nie wymaga niczyjej
   zgody: `git revert <commit promocji> && git push` — zdejmowanie egzekwowania nie jest bramkowane.

   Environment `perimeter-apply` **nie jest** tą bramką: wymagani recenzenci to funkcja płatna dla
   repozytoriów prywatnych i na planie bez niej environment zostaje bez ani jednej reguły ochrony
   (`tools/bootstrap_github.sh` odczytuje to z API i mówi o tym wprost). Gdy wasz plan ją ma — zostawcie
   włączoną; obie warstwy się składają, bo dają co innego: recenzent to **druga tożsamość**, bramka
   promocji to **drugi świadomy akt w momencie skutku**.

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
  AND NOT protoPayload.metadata.dryRun="true"' --project=<PROJEKT_CZLONKA> --freshness=1h --limit=20
```

**Filtr to NEGACJA `dryRun="true"`, a nie `dryRun="false"` — i to nie jest niuans składniowy.**
Wpis o odmowie EGZEKWOWANEJ **nie ma pola `dryRun` w ogóle**; pojawia się ono wyłącznie przy
naruszeniach dry-run, z wartością `true`. `dryRun="false"` nie dopasowuje więc **nigdy niczego** —
w żadnej organizacji. Zapytanie z tym filtrem jest puste ZAWSZE, a zdanie niżej każe czytać pustkę
jako sukces: procedura potwierdzałaby wtedy działanie ruchu również wtedy, gdy cała dywizja jest
zablokowana. Ten sam filtr siedział wcześniej w metryce alertu, w sondzie i w asercji selftestu.

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

### Przepływ, który ZASZEDŁ i mimo to nie mógł dać wpisu (DEC-27)

Cała tabela wyżej mówi o ruchu, który się **nie wykonał**. Jest jednak klasa ruchu, który wykonuje się co
minutę, a w oknie obserwacji nie zostawia śladu: **ruch między dwoma członkami, którzy oba są w dry-run**.

Konfiguracja dry-run zawiera wszystkich członków naraz, więc widzi taki przepływ jako ruch **wewnątrz**
perimetru — nie ma czego zalogować. Promocja przenosi natomiast **jednego**: rówieśnik zostaje na zewnątrz
konfiguracji egzekwowanej i ten sam przepływ staje się naruszeniem egress. Zmierzone dwiema maszynami i tą
samą sondą (szczegóły w DEC-27): z członka wyłącznie dry-run do drugiego takiego członka — **PRZESZŁO, zero
wpisów**; z członka egzekwowanego do tego samego zasobu — **ODMOWA**.

To jest jedyny wiersz na tej liście, którego **nie da się** naprawić dłuższym oknem: nie chodzi o zbyt krótki
pomiar, tylko o pomiar, który tego zdarzenia nie klasyfikuje. Dlatego:

* raport wypisuje na górze listę członków w dry-run i powtarza ją przy każdym z nich,
* `promotion_gate` żąda pola `unmeasured_peers_ack` **równego** liczbie tych członków (krok 3 niżej),
* **jeśli dywizje rozmawiają ze sobą — promuj je jedną kohortą** (jeden pull request, jeden apply). Wtedy
  wchodzą do konfiguracji egzekwowanej razem, zbiór niemierzalnych rówieśników robi się mniejszy, a przepływ
  między nimi przeżywa promocję. To jest zalecenie, nie wymóg — kohorta wiąże termin każdej dywizji
  z terminem najwolniejszej.

**Reguły `baseline_ingress` bez access levelu** wymagają jawnego `allow_without_access_level: true` i
approvalu Security — bo dotyczą wszystkich chronionych projektów naraz. Pominięcie pola nie daje tego samego
skutku co jego ustawienie; pilnuje tego reguła OPA.

---

## B. Break-glass — perimetr blokuje legalny ruch

### Zasada

Zdejmujemy członka z konfiguracji **egzekwowanej**, zostawiając go w **dry-run**. Incydent nie kasuje wiedzy
o jego ruchu — po naprawie promocja wymaga takiego samego dowodu jak za pierwszym razem.

**To NIE JEST procedura „wpuść bastion przez działającą granicę".** Access level `break_glass` w
`perimeter/access-levels/` należy do tamtej, innej procedury i ta droga go **nie używa** — patrz DEC-29.
Szukanie w incydencie adresu, który trzeba dopisać do poziomu, jest szukaniem w złym miejscu.

### Czasy, na które można liczyć (zmierzone, nie szacowane)

| Odcinek | Ile | Skąd |
|---|---|---|
| `workflow_dispatch` → start przebiegu | ~10 s | ćwiczenie procedury |
| demote + commit + push | ~3 s | j.w. |
| `terraform apply` (jeden członek z konfiguracji egzekwowanej) | ~90 s | przebieg `apply` na tej samej zmianie |
| koniec `apply` → **realny powrót ruchu** | **13 s** | sonda co 5 s tym samym wywołaniem, które dostawało `403` |
| rollback promocji (kierunek odwrotny, dla porównania) | 46 s do `apply`, **78 s do ruchu** | pomiar promocji |

Wniosek operacyjny, bo to jest pytanie, które pada w incydencie: **konfiguracja cofa się natychmiast, skutek
kilkanaście–kilkadziesiąt sekund później.** Nie ponawiaj procedury, gdy `apply` zszedł na zielono, a wywołujący
nadal widzi `403` — odczekaj minutę i sonduj dalej. Ponowne uruchomienie w tym oknie nie przyspiesza niczego,
a wchodzi w tę samą kolejkę `concurrency: vpc-sc-apply`, więc realnie opóźnia.

### Kroki

1. Potwierdź, że to naprawdę perimetr (a nie IAM, nie sieć, nie aplikacja):

```bash
# ZAKRES = PROJEKT, w którym stanął ruch (patrz uwaga o zakresie w części A, krok 6). Na organizacji
# tych wpisów NIE MA i pusty wynik przeczytasz jako „to nie perimetr" — czyli odwrotnie niż jest.
gcloud logging read 'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"
  AND NOT protoPayload.metadata.dryRun="true"' --project=<PROJEKT_CZLONKA> --freshness=1h \
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

4. Workflow, **w tej kolejności**: bierze tożsamość i sprawdza dostęp do stanu → demotuje członka
   i przestawia mu `dry_run_since` na dziś → commituje i wypycha → `apply` → **czyta żywą granicę**
   i pada, jeśli numer projektu nadal stoi w `status.resources` → otwiera issue postmortem (także gdy coś
   po drodze padło). Kolejność jest częścią procedury, nie stylem: zapis do repozytorium przed zdobyciem
   tożsamości zostawia commit twierdzący coś, czego granica nie zrobiła (zmierzone — patrz DEC-29).

   Ślad audytowy zostaje w repozytorium, nie tylko w interfejsie Actions: kto uruchomił i odsyłacz do
   przebiegu idą do **treści commita** oraz do issue. Tam też stoi zdanie, o którym najłatwiej zapomnieć —
   **nie ma żadnego timera**: członek jest niechroniony do momentu ponownej promocji i nic mu o tym nie
   przypomni.

5. Zweryfikuj, że ruch wrócił — **tym samym wywołaniem, które go nie miało**, a nie brakiem nowych wpisów.
   Pusty log jest nierozróżnialny od „nikt nie próbował"; jedynym dowodem powrotu jest przejście wywołania.
   Odczekaj kilkanaście sekund po zielonym `apply` (tabela czasów wyżej).

> [!WARNING]
> **Nie licz na to, że commit z tej procedury sam uruchomi `apply.yml`.** GitHub nie wyzwala workflowów
> push-em wykonanym tokenem `GITHUB_TOKEN`. Zmierzone: commit democji nie uruchomił niczego, a granica
> zmieniła się dopiero przy scaleniu **cudzego, niezwiązanego** pull requesta 88 s później — zmiana granicy
> bezpieczeństwa pojechała pod tytułem zmiany, której autor jej nie widział. Dlatego `apply` jest krokiem
> tej procedury. Jeśli kiedyś ten krok zostanie z niej wyjęty, wróci ten sam tryb awarii.

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

### Powrót do `enforced` — dwie rzeczy, które zaskakują, i obie są własnością konstrukcji

**1. Dowód o przepływach zostaje — i dlatego blokuje powrót.** Członek zostaje w konfiguracji dry-run, więc
to samo wywołanie, które w czasie egzekwowania dawało odmowę **bez** pola `dryRun`, po democji daje wpis
z `dryRun: true`. Ten sam `violationReason`, ten sam cel, ciągła seria — okno obserwacji nie zaczyna się od
zera i o to w tej procedurze chodzi. **Ale** `violations_report` nie ma predykatu na `dryRun` (bo odmowa
egzekwowana tego pola nie ma w ogóle), więc odmowy **z samego incydentu** wchodzą do liczby czytanej przez
`promotion_gate`. Zmierzone na ćwiczeniu: **628 wpisów** dla jednego członka w oknie 14 dni po jednej sesji
odmów. Powrót wymaga więc świadomej decyzji, jednej z dwóch:

* **przeczekać**, aż wpisy wypadną z okna (`clean_window_days`) — właściwe, gdy nie ma presji czasu;
* **`promotion_waivers`** w `perimeter/policy.yaml` z `accept_violations_up_to` — zakres jednego członka,
  data ważności, uzasadnienie min. 40 znaków, właściciel Security. Nie obniżaj progu globalnie.

**2. Zegar rusza od nowa.** Procedura przestawia `dry_run_since` na dzień democji, więc `dry_run_min_days`
liczy się od tego dnia — a nie od pierwszego wejścia członka do dry-run. Bez tego bramka „odsiedziałeś okno"
byłaby przy powrocie spełniona natychmiast dla każdego, kto przeszedł ścieżkę legalnie, czyli dokładnie tam,
gdzie obietnica „świeże okno" ma znaczyć najwięcej. Data to **zegar obserwacji, nie dowód**; dowód leży
w audit-logu i w raporcie, a te zostają nietknięte.

Konsekwencja obu naraz: **powrót po break-glassie jest zawsze albo powolny, albo jawnie zwolniony wpisem
w `policy.yaml`.** Trzeciej drogi nie ma i nie ma jej celowo — „wracamy, bo już naprawiliśmy" ma zostawić
ślad z nazwiskiem i datą, a nie wynikać z pola, którego nikt nie ogląda.

---

## C. Offboarding (dla porządku)

Usunięcie pliku członka wyprowadza projekt z **obu** konfiguracji. To także zmiana granicy bezpieczeństwa —
projekt przestaje być chroniony — więc idzie przez ten sam review co dołączenie. Automatyczny PR z
`expiry-sweep` jest **propozycją**: właściciel może zamiast tego potwierdzić wpis nową datą `review_by`.
