# Runbook — promocja członka do enforced i procedury awaryjne

Procedury o przeciwnych kierunkach: **A** włącza ochronę, **B** zdejmuje ją w incydencie, **C** wyprowadza
członka, **D** odbudowuje granicę, której już nie ma. Wszystkie mają ten sam wymóg: **dowód, nie deklaracja**.

**Część D ma jedyny w tym systemie krok, którego pipeline nie wykona** — utworzenie perimetru jest
zastrzeżone dla człowieka (DEC-37). Jeśli szukasz „dlaczego apply pada na `Error creating ServicePerimeter:
403`", idź od razu tam.

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
| **Zakres ciszy potwierdzony** | `unmeasured_peers_ack` = klucze członków zostających w dry-run, z którymi ten członek **wymienia ruch** (pusta lista = z żadnym) | nagłówek `violations.md`; DEC-27 + DEC-54 — ruch między dwoma członkami w dry-run NIE MOŻE dać wpisu |
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
   `unmeasured_peers_ack:` — **listę kluczy** tych członków z raportu, z którymi ten projekt wymienia ruch.
   **Nic więcej** — dwa pola, oba wskazane przez raport. Wypełnij sekcję *Evidence* w szablonie PR-a.

   Pusta lista `[]` jest legalna i jest **oświadczeniem**, że ten projekt nie rozmawia z żadnym z nich —
   pisz ją dopiero po pytaniu z kroku 1, bo to jedyne zdanie w tym pliku, które ktoś podpisuje własnym
   `approved_by`. Brak pola zatrzymuje promocję; klucz, który nie wskazuje innego członka (literówka,
   nazwa sprzed offboardingu, własny klucz), też.

   **Cudzy onboarding NIE unieważnia tej listy** (DEC-54). Dopisanie do `projects.yaml` dywizji, której
   ten wniosek nie dotyczy, zostawia promocję zieloną — do #2076 czerwieniło ją na torze apply, czyli już
   po merge'u. Zmienia się to tylko wtedy, gdy wypisany członek **zniknie** z pliku: wtedy klucz przestaje
   wskazywać kogokolwiek i wracasz do kroku 1.

   Po zastosowaniu promocji pole zostaje w pliku jako **zapis przyjętej decyzji** i nie jest już o nic
   pytane. Nie usuwaj go rutynowo — to nie jest potwierdzenie, które gnije, tylko lista nazw z datą
   promocji obok (`change_ref`, `approved_by`).

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

   > **ZIELONY `apply` NIE JEST CHWILĄ, OD KTÓREJ CZŁONEK JEST CHRONIONY.** Zmierzone na żywej granicy:
   > maszyna w istniejącej sieci promowanego projektu jest rozpoznawana jako „wewnątrz" po **~14 s** od
   > zapisu w API, ale **egzekwowanie egressu zapada niatomowo** i droga na zewnątrz **migocze jeszcze
   > przez ~2 minuty** (ostatnie wywołanie, które wyszło: **+135 s**; czysto dopiero od **+146 s**).
   > Przez ten czas maszyna czyta z wnętrza perimetru **i** wychodzi na zewnątrz — cała ścieżka
   > eksfiltracji jest przejezdna, tak jak w oknie świeżej sieci, tylko z innej przyczyny.
   >
   > Praktycznie: **nie ogłaszaj promocji za zamkniętą po jednym zielonym przelocie.** Wymagaj **dwóch
   > kolejnych rund** sondy z zamkniętymi wyjściami — jedna runda „PRZESZŁO" nie odróżnia „domknęło się"
   > od „trafiłem na punkt egzekwowania, który już wie". Jeśli w tym oknie planujesz cokolwiek wypuścić
   > z projektu, odczekaj te dwie minuty.
   >
   > **Czego to okno NIE jest:** to **nie** jest okno świeżej sieci. Sieć, która w promowanym projekcie
   > już istniała, jest przypisana do granicy od razu — pomiar nie złapał ani jednej rundy w stanie
   > `OKNO-SWIEZEJ-SIECI` (0 z 32). Okno świeżej sieci otwiera **`networks create`** w projekcie już
   > będącym członkiem, a nie wejście projektu do konfiguracji egzekwowanej.

```bash
gh workflow run boundary-probe.yml -f project=<PROJEKT_CZLONKA> -f expect=blocked && gh run watch
```

   Zielony przelot znaczy komplet **sześciu** rzeczy naraz: granica ISTNIEJE (odczytana z API, nie z gita),
   sondowany projekt jest w **konfiguracji egzekwowanej** (asercja po numerze, nie wypis do przeczytania
   okiem), chronione wywołanie bez reguły zostało odmówione **z powodem VPC-SC** (nie z braku roli, nie
   z wyłączonego API), ruch dozwolony regułą ingress NADAL przechodzi, usługa spoza `restricted_services`
   NADAL działa (czyli projekt nie jest po prostu zepsuty), a odmowa ma niezależny drugi dowód we wpisie
   audytowym. Czerwony przelot mówi, KTÓRA z tych sześciu nie zaszła.

   **Trzy werdykty, nie dwa** (DEC-39). Tytuł adnotacji rozstrzyga, co się stało, bez otwierania logu:

   | tytuł adnotacji | co znaczy | kod wyjścia |
   |---|---|---|
   | *(brak adnotacji)* | granica istnieje i zachowuje się zgodnie z oczekiwaniem | 0 |
   | `GRANICY NIE MA` | perimetr o tej nazwie nie istnieje — **nie ma czego przypisać** żadnej odmowie | 1 |
   | `PROJEKT NIE JEST W KONFIGURACJI EGZEKWOWANEJ` | granica istnieje, ale ten projekt jest poza `status` | 1 |
   | `GRANICA ZACHOWUJE SIE INACZEJ NIZ OCZEKIWANO` | sondy nie zgadzają się z modelem `expect` | 1 |
   | `WERDYKT NIEROZSTRZYGNIETY (nie zmierzono stanu granicy)` | `403`/błąd odczytu — **nie wiadomo**, nigdy „nie ma" | 2 |

   Sonda ma własną kontrolę anty-tautologiczną i wolno ją uruchomić kiedykolwiek — nic nie mutuje:

```bash
# „granicy nie ma" — nazwa perimetru, którego nie ma; ma dać GRANICY NIE MA, a nie krok, który padł
gh workflow run boundary-probe.yml -f project=<PROJEKT_CZLONKA> -f expect=blocked -f perimetr=nie-ma-takiego
# „nie wiadomo" — numer polityki bez dostępu; ma dać WERDYKT NIEROZSTRZYGNIETY, a nie „granicy nie ma"
gh workflow run boundary-probe.yml -f project=<PROJEKT_CZLONKA> -f expect=blocked -f polityka=999999999999
```

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

### Pomiar EGRESSU — osobny tor, i jedyny, który wymaga maszyny

`boundary-probe.yml` woła z runnera CI, który jest spoza granicy **z definicji**, więc mierzy wyłącznie
INGRESS. Reguła egress ocenia wywołanie, którego ŹRÓDŁO jest wewnątrz, a **„wewnątrz" jest własnością
SIECI, nie tożsamości**: konto serwisowe utworzone w projekcie członkowskim i impersonowane z zewnątrz
dostaje `ingressViolations` / `NO_MATCHING_ACCESS_LEVEL` z `callerIp: "private"` — jest liczone jako obce.
Wariant „pomiar egressu bez maszyny" nie istnieje i nie należy go szukać.

**Drugi wynik, ważny przy czytaniu `describe`:** pusta lista reguł egress (`status.egressPolicies: []`)
znaczy **„odmawiaj każdego wyjścia"**, a nie „egress nieegzekwowany". Reguła egress jest WYJĄTKIEM od
domyślnej odmowy. Dokument, który z `egress: 0` wnioskuje „nic nie chroni", mówi nieprawdę o własnym
systemie.

**Zanim postawisz maszynę — poczekaj na sieć.** Świeża sieć VPC w projekcie będącym członkiem konfiguracji
egzekwowanej jest przez **kilka minut poza granicą**; jednostką propagacji jest SIEĆ, nie maszyna i nie
podsieć. W tym oknie sonda zobaczy stan `OKNO-SWIEZEJ-SIECI` (własny projekt ODMAWIA, wyjścia
PRZECHODZĄ) — stan **gorszy** niż „poza granicą", bo cała ścieżka eksfiltracji jest przejezdna. Odczekaj
**≥ 10 min** od utworzenia sieci i POTWIERDŹ przynależność przelotem `sonda-oczekiwanie=obserwacja`, zanim
uznasz pomiar za ważny.

```bash
# 1. sieć + podsieć w projekcie CZŁONKOWSKIM (PGA włączone; adresu zewnętrznego NIE ma)
gcloud compute networks create sonda-egress --project=<CZLONEK> --subnet-mode=custom
gcloud compute networks subnets create sonda-egress-ew1 --project=<CZLONEK> \
  --network=sonda-egress --region=europe-west1 --range=10.10.0.0/24 --enable-private-ip-google-access

# 2. maszyna z sondą w metadanych; wynik idzie na PORT SZEREGOWY (`compute` nie jest w restricted_services,
#    więc serial czyta się z zewnątrz nawet przy w pełni egzekwowanej granicy — pomiar nie zmienia tego,
#    co mierzy: bez reguły firewalla, bez klucza SSH, bez wyjątku ingress dla operatora)
gcloud compute instances create sonda-egress --project=<CZLONEK> --zone=europe-west1-b \
  --machine-type=e2-micro --subnet=sonda-egress-ew1 --no-address \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=10GB --boot-disk-type=pd-standard \
  --service-account=<SONDA_SA> --scopes=https://www.googleapis.com/auth/cloud-platform \
  --metadata-from-file=startup-script=tools/sonda_egress_startup.sh,sonda-py=tools/sonda_egress_wewnetrzna.py \
  --metadata=sonda-projekt-wewnatrz=<CZLONEK>,sonda-projekt-cel=<PROJEKT_SPOZA_GRANICY>,\
sonda-kubelek-cel=<BUCKET_W_CELU>,sonda-kubelek-obcy=<BUCKET_SPOZA_REGULY>,\
sonda-oczekiwanie=wewnatrz-zamkniete,sonda-rundy=6,sonda-odstep=10,\
sonda-perimetr=accessPolicies/<ID_POLITYKI>/servicePerimeters/<NAZWA>

# 3. dowód
gcloud compute instances get-serial-port-output sonda-egress --project=<CZLONEK> \
  --zone=europe-west1-b | grep '@@SONDA'
```

**Trzy werdykty, tak samo jak w sondzie ingressu** — ostatnia linia `@@SONDA-WERDYKT` niesie `exit=`:

| `exit` | werdykt | co znaczy |
|---|---|---|
| 0 | `ZGODNE Z OCZEKIWANIEM` | ruch zachował się dokładnie tak, jak mówi model `sonda-oczekiwanie` |
| 1 | `NIEZGODNE Z OCZEKIWANIEM` | granica zachowuje się inaczej — w tym stan `GRANICA-NIE-DZIALA`, czyli **wszystko przeszło** |
| 2 | `NIE-ZMIERZONO` | brak roli, wyłączone API, błąd sieci lub brak tokenu — **nie wiadomo**, czy granica działa |

**Macierz — po uzbrojeniu reguły ma się przełączyć DOKŁADNIE JEDNA komórka.** Każda inna zmiana znaczy,
że zmierzyliśmy co innego niż regułę. Trzy dolne wiersze są kontrolą anty-tautologiczną; kolumna
`poza-granica` jest kontrolą dla samej sondy — uruchom ją na maszynie w projekcie **spoza** perimetru
i sprawdź, że sonda mówi „granica nie działa", zamiast wypisywać serię `PRZESZŁO`.

| sonda | co izoluje | `wewnatrz-zamkniete` | `wewnatrz-otwarte` | `poza-granica` |
|---|---|---|---|---|
| `wewnatrz` | przynależność: wnętrze → wnętrze | PRZESZŁO | PRZESZŁO | PRZESZŁO |
| `poza-uslugami` | przynależność: usługa spoza `vpcAccessibleServices` | ODMOWA | ODMOWA | PRZESZŁO |
| `egress-cel-metoda` | metoda **w** regule, cel **w** regule | ODMOWA | **PRZESZŁO** | PRZESZŁO |
| `egress-cel-inna` | metoda **spoza** reguły, ten sam cel | ODMOWA | ODMOWA | PRZESZŁO |
| `izolacja-cel` | metoda w regule, **cel spoza** reguły | ODMOWA | ODMOWA | PRZESZŁO |

`poza-uslugami` celuje we **własny** projekt i nie zależy od żadnej reguły — mierzy wyłącznie to, czy
wołający jest przypisany do sieci wewnątrz granicy. Odmowa `SERVICE_NOT_ALLOWED_FROM_VPC` jest tu
**oczekiwana**: przy `vpcAccessibleServices.enableRestriction: true` z wnętrza nie działa żadna usługa
spoza `allowedServices`. Kontrola negatywna ingressu („usługa spoza `restricted_services` ma nadal
działać") przeniesiona na egress świeciłaby na czerwono przy poprawnie działającej granicy.

**Odczyt ACM z wnętrza się nie uda — i to też jest pomiar.** `sonda-perimetr` każe sondzie zapytać ACM
o stan granicy; z wnętrza dostanie `SERVICE_NOT_ALLOWED_FROM_VPC` (`stan=NIEODCZYTYWALNY-Z-WNETRZA`),
bo ACM nie należy do `allowedServices` — i **ta odmowa jest dowodem przynależności**. Z maszyny poza
granicą ten sam odczyt zwraca `stan=ISTNIEJE` albo `stan=BRAK` (`404`, czyli **granicy nie ma**), a `403`
to zawsze `stan=NIE-WIADOMO`, nigdy „nie ma".

**Sprzątanie — natychmiast po pomiarze, nie „przy okazji".** Koszt przelotu to rząd eurocentów, ale
zostawiona maszyna i włączone `compute.googleapis.com` poszerzają powierzchnię projektu, który ma być pusty:

```bash
gcloud compute instances delete sonda-egress --project=<CZLONEK> --zone=europe-west1-b --quiet
gcloud compute networks subnets delete sonda-egress-ew1 --project=<CZLONEK> --region=europe-west1 --quiet
gcloud compute networks delete sonda-egress --project=<CZLONEK> --quiet
gcloud services disable compute.googleapis.com --project=<CZLONEK> --force --quiet
```

**Przy powtarzaniu przelotu:** `gcloud compute instances reset` uruchamia startup-script od nowa, ale DYSK
ZOSTAJE — wszystko, co skrypt dopisał w poprzednim rozruchu, nadal tam jest. Metadane zmieniaj przez
`gcloud compute instances add-metadata`, a stan ustawiany przez skrypt kasuj bezwarunkowo i dokładaj
warunkowo, nigdy odwrotnie.

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
* `promotion_gate` żąda pola `unmeasured_peers_ack` wymieniającego **klucze** tych z nich, z którymi
  promowany członek wymienia ruch (krok 3 niżej) — zbiór, nie licznik, bo licznik unieważniała każda
  cudza zmiana w tym samym pliku (DEC-54),
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

**To NIE JEST procedura „wpuść bastion przez działającą granicę".** Ta droga **nie używa żadnego access
levelu** — patrz DEC-29. Szukanie w incydencie adresu, który trzeba dopisać do poziomu, jest szukaniem
w złym miejscu, i właśnie dlatego poziom `break_glass` **przestał istnieć** (DEC-52): nazwa procedury
awaryjnej na obiekcie, którego ta procedura nie dotyka, jest w incydencie fałszywym tropem, a w audycie
fałszywą kontrolą. Jeśli kiedyś powstanie tamta, druga procedura — poziom wraca **razem z regułą ingress,
która go referuje**, nie wcześniej.

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
| Brak profilu pokrywającego wzorzec | dodaj profil (trzeci taki sam wyjątek = sygnał, nie czwarty wyjątek) — procedura: [`8-zmiany-reczne.md` §8.2](8-zmiany-reczne.md#82-dodanie-profilu-do-katalogu) |
| Access level za wąski | popraw access level — to zmiana dotykająca wszystkich, więc osobny PR; procedura wraz z **uzbrojeniem** i parą kanarków: [`8-zmiany-reczne.md` §8.3](8-zmiany-reczne.md#83-dodanie-i-uzbrojenie-access-levelu) |

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

## C. Offboarding — wyprowadzenie członka z perimetru

Usunięcie pliku członka wyprowadza projekt z **obu** konfiguracji. To także zmiana granicy bezpieczeństwa —
projekt przestaje być chroniony — więc idzie przez ten sam review co dołączenie. Automatyczny PR z
`expiry-sweep` jest **propozycją**: właściciel może zamiast tego potwierdzić wpis nową datą `review_by`.

### Zakres — czego ta procedura NIE robi

**Offboarding kończy się na granicy.** Cykl życia samego projektu GCP — założenie, skasowanie, przywrócenie —
należy do zespołu właścicielskiego projektów. Ta procedura **nie kasuje projektu** i nie zakłada, że
wykonujący ma do tego uprawnienie: w typowym wdrożeniu zespół perimetru **nie ma**
`resourcemanager.projects.delete`, a projekt bywa kasowany bez jego udziału i bez powiadomienia.

To nie jest ograniczenie do obejścia. `gcloud projects delete` jest operacją **nieodwracalną w praktyce**:
soft-delete trwa 30 dni, `projectId` jest przez ten czas zajęty, a `undelete` **nie przywraca konta
rozliczeniowego**. Wykonywanie jej na cudzym zasobie, w cudzym procesie, przy okazji zdejmowania ochrony,
łączy dwie zmiany o różnych właścicielach i różnej odwracalności w jeden nieodkręcalny krok.

Cztery znaczenia słowa „usuń", które trzeba rozdzielić, **zanim** zaczniesz:

| co masz na myśli | co to naprawdę jest | kto to robi |
|---|---|---|
| „projekt ma przestać być chroniony" | **offboarding** — usunięcie wpisu z `perimeter/projects.yaml`. Zwykły pull request | **ta procedura**, kroki 1–5 |
| „usuń też jego access level" | część **tego samego** PR-a, jeśli poziom należał do jednego członka; bramka pyta o REFEROWANIE (DEC-33) | **ta procedura**, krok 2 |
| „skasuj projekt GCP" | `gcloud projects delete` — soft-delete 30 dni, ID zajęte, billing po `undelete` nie wraca | **zespół właścicielski projektów** — nie ta procedura; reakcja w części „Gdy projekt zniknie" |
| „`terraform destroy` roota" | skasowanie perimetru, poziomów i reguł naraz — **nie ma legalnej ścieżki**: bramka odrzuca usunięcie perimetru, IAM Deny odbiera `servicePerimeters.delete` kontom CI, a rola własna nie ma `policies.delete` | człowiek z org-level, procedura wyjątkowa — nie ta |

### Kolejność — najpierw granica, potem cokolwiek z projektem

> **NAJPIERW wyprowadź członka z perimetru (PR + `apply`), DOPIERO POTEM ktokolwiek rusza projekt.**

Odwrotna kolejność zostawia w konfiguracji **martwy numer, którego `apply` nie zauważa** — soft-delete jest
dla Access Context Managera normalnym, rozwiązywalnym zasobem przez całe 30-dniowe okno. Zmierzone: po
skasowaniu projektu członka `plan` = `No changes.`, `apply` = `0 added, 0 changed, 0 destroyed`,
`spec.resources` **nadal z numerem**, obserwator = `drift_resources: 0`, `expiry-sweep` = krok PR `skipped`.
Repozytorium i granica **zgadzają się co do projektu, który nie istnieje**.

**Dlaczego to jest problem bezpieczeństwa, a nie porządku.** Raport naruszeń dalej liczy martwego członka,
tyle że jego naruszenia spadają do zera — a zero to dokładnie **dowód „czystego okna"** wymagany przez bramkę
promocji. Martwy wpis robi się więc z czasem **coraz lepszym kandydatem do egzekwowania**, na dowodzie,
którego nikt nie zmierzył. Kontrola pozytywna: **poprawny offboarding tego NIE robi** — patrz „Co się dzieje
z dowodem" niżej.

**Gdy nie kontrolujesz drugiej strony.** Skoro projektu nie kasujemy my, tej kolejności nie da się
wyegzekwować numeracją kroków. Egzekwuje ją **uzgodnienie z zespołem właścicielskim projektów** plus
detekcja po naszej stronie — patrz „Gdy projekt zniknie".

### Kroki

1. Gałąź i usunięcie wpisu. Plik ma postać kanoniczną pilnowaną bramką w `validate.yml`, więc nie edytuj go
   ręcznie w połowie — użyj modułu, który go zna:

```bash
git checkout -b offboard/<klucz-czlonka>
python3 - <<'PY'
import sys; sys.path.insert(0, "tools")
import projects_file as pf
doc = pf.dokument(open("perimeter/projects.yaml").read())
doc["members"] = [w for w in doc["members"] if w["project_id"] != "<PROJECT_ID>"]
open("perimeter/projects.yaml", "w").write(pf.zrzut(doc))
PY
```

   → **DOWÓD:** `git diff --stat perimeter/projects.yaml` pokazuje **wyłącznie** usunięcie tego jednego wpisu.

2. Access level członka — w **tym samym** PR-ze, jeśli po odejściu nie jest już przez nic referowany.
   Bramka `vpcsc.perimeter` odrzuci usunięcie poziomu, który **nadal** jest referowany (regułą albo
   `required_access_levels` innego poziomu), i poda jego nazwę; poziom osierocony przepuszcza (DEC-33).

   → **DOWÓD (lokalnie, bez poświadczeń):**

```bash
check-jsonschema --schemafile schemas/projects.schema.json      perimeter/projects.yaml
check-jsonschema --schemafile schemas/access-level.schema.json  perimeter/access-levels/*.yaml
python3 tools/collect_declarations.py > declarations.json
python3 tools/attribute_budget.py --input declarations.json --format markdown   # spadek `dry-run` = koszt członka
conftest verify --policy policy
```

   `conftest test --namespace vpcsc.onboarding` zgłosi lokalnie fałszywe FAIL-e na członkach już
   egzekwowanych — brakuje mu artefaktów „stan zastosowany" i „raport naruszeń", które dokłada CI.
   To artefakt uruchomienia lokalnego, nie regresja.

3. Opis PR-a. Szablon ma osobny haczyk *„a member is offboarded (stops being protected)"* — zaznacz go
   i napisz wprost, **kto** przestaje być chroniony. To nie jest formalność: bramka promocji jest
   **asymetryczna** i zatrzymuje wyłącznie ruch w stronę `enforced`. Zdjęcie ochrony — democja, offboarding,
   break-glass — przechodzi **automatem**, bo przywraca ruch. Konsekwencja: **wyprowadzenie członka
   `enforced` nie ma żadnej bramki maszynowej**, a jedyną kontrolą jest podpis recenzenta z CODEOWNERS.
   Widoczność w diffie jest tu całą obroną.

4. Scalenie i `apply`.

```bash
gh pr checks <N>                          # komplet zielony
gh pr merge <N> --merge --delete-branch
gh api repos/<ORG>/<REPO>/pulls/<N> -q '.merged, .merged_at'   # POTWIERDŹ scalenie, nie zakładaj
```

   `apply.yml` rusza na push do `main` (ścieżki `perimeter/**`, `terraform/**`). Zmierzone tempo:
   **scalenie → członek poza granicą ≈ 82 s.**

   → **DOWÓD — kolejności, nie samego „success":** w logu `apply` access level musi zacząć się kasować
   **po** `Destruction complete` reguły, która go referowała:

```
…dry_run_ingress_policy.rule["<klucz>--…"]: Destruction complete   06:46:11.484
…access_level.level["<poziom>"]:            Destroying…            06:46:11.485   ← 1 ms PO regule
```

   Ta kolejność nie bierze się sama: pilnuje jej `depends_on` w `terraform/rules.tf`. Bez niej graf nie ma
   krawędzi między regułą a poziomem, oba `destroy` lecą równolegle przy domyślnym `-parallelism=10`,
   a jeden z dwóch porządków API odrzuca komunikatem `you must first remove the reference` — czyli defekt,
   którego jeden zielony przebieg nie wyklucza.

5. **Weryfikacja na ŻYWEJ granicy — to jest krok rozstrzygający, nie formalność.** Zielony `apply` nie jest
   dowodem: zmierzono przypadek, w którym repozytorium twierdziło „zdemotowany", a granica egzekwowała
   jeszcze przez 3 min 01 s.

```bash
gcloud access-context-manager perimeters describe <PERIMETR> --policy=<POLICY> \
  --format='value(status.resources,spec.resources)' | tr ',;' '\n\n' | grep -c '<PROJECT_NUMBER>'
```

   → **DOWÓD:** wynik **`0`** — numeru nie ma **ani** w konfiguracji egzekwowanej (`status`), **ani**
   w dry-run (`spec`). Każda inna liczba znaczy, że `apply` nie zrobił tego, co pokazał `plan`.

   **Kontrola anty-tautologiczna, bez której ten dowód jest pusty:** ten sam odczyt z numerem **innego,
   nadal chronionego** członka musi zwrócić liczbę **niezerową**. Inaczej `0` nie odróżnia „członka nie ma"
   od „odpowiedzi nie ma".

   → **DOWÓD stanu:** `gh workflow run watch.yml --ref main` — obserwator czyta granicę surowym `GET`-em,
   nie ze stanu Terraforma. Oczekuj `atrybuty_w_deklaracji` **równe** granicy, `drift_resources: 0`,
   `apply_pending_seconds: 0`, a w kroku `plan` — `No changes. Your infrastructure matches the configuration.`

**Po kroku 5 procedura jest skończona.** Projekt nadal istnieje, ma swoje zasoby i swojego właściciela —
przestał być chroniony przez granicę. To jest cały zamierzony skutek.

### Gdy `apply` padnie w połowie na kasowaniu access levelu (`Error 403`)

Rola własna konta `apply` świadomie nie ma `accesscontextmanager.accessLevels.delete`, więc `apply` wykona
wszystko **poza** ostatnim krokiem:

```
Error when reading or editing AccessLevel: googleapi: Error 403: The caller does not have permission
```

Stan jest wtedy **częściowo zastosowany**: członek i reguły już zniknęły z granicy, poziom został. To blokuje
**całe repozytorium**, nie tylko to zadanie — obiekt siedzi w stanie, więc `plan` pokazuje `1 to destroy`,
a każdy kolejny `apply` pada tym samym `403`.

**Wyjście natychmiastowe:** przywróć wpis poziomu z `armed: false` i `unarmed_reason` mówiącym, że jest
osierocony i czeka na uzupełnienie roli. `plan` wraca do `No changes`, `apply` przechodzi, poziom zostaje
w katalogu jako jawny dług z odsyłaczem.

**Czego NIE robić:** nie zostawiaj repozytorium z czerwonym `apply` „do jutra". Zablokowany `apply` blokuje
**każdą** ścieżkę wdrożenia — w tym democję i break-glass, czyli dokładnie te, które przywracają ruch.
Wpis-nagrobek jest brzydki i jest właściwą reakcją.

### Gdy projekt zniknie — zdarzenie CUDZE, na które reagujemy

| sytuacja | co robimy |
|---|---|
| projekt skasowany **po** offboardingu (kolejność zachowana) | **nic** — członka już nie ma w granicy |
| projekt skasowany **przed** offboardingiem (kolejność złamana) | **wchodzimy w kroki 1–5 natychmiast po wykryciu**: wpis nadal zdejmuje ochronę z niczego i **fałszuje dowód promocyjny** |
| projekt przywrócony (`undelete` w oknie 30 dni) | numer **ten sam**, więc konfiguracja granicy nie wymaga zmiany — ale **billing nie wraca**. Powrót do granicy idzie normalnym onboardingiem z pre-flightem, nie „cofnięciem offboardingu" |

**Jak się o tym dowiemy.** Martwego członka nie widzi ANI JEDNA z warstw pytających o zgodność Gita
z chmurą (`plan`, `apply`, dryf, `expiry-sweep`, raport, pre-flight) — i nie jest to ich defekt: Git
i granica zgadzają się co do numeru, którego nie ma. Odpowiada za to **osobne pytanie**, zadawane przez
obserwatora: czy numer w granicy ma jeszcze za sobą projekt (**DEC-42**). Sygnał to metryka
`custom.googleapis.com/vpcsc/members_not_active` i alert
[„członek granicy bez potwierdzonego stanu ACTIVE"](7-alerty.md#martwy-czlonek), z rytmem **godzinnym**.
Do kompletu potrzebne są jeszcze **dwie** rzeczy i obie trzeba świadomie ustawić przy wdrożeniu:

1. **Uzgodnienie z zespołem właścicielskim projektów** — odpowiadające na cztery pytania: **skąd**
   dowiadujemy się o skasowaniu (ticket, subskrypcja Asset Inventory, lista) · **w jakim czasie** od
   `DELETE_REQUESTED` · czy jest **pytanie przed**, czy tylko **powiadomienie po** · **kto** po naszej stronie
   reaguje. Bez tego uzgodnienia zapisz wprost, że powiadomienia nie ma — milczące założenie jest gorsze
   od nazwanego braku.
2. **Rekoncyliacja po naszej stronie** — **wykonuje ją obserwator co godzinę** (DEC-42), czyli gęściej niż
   wymagane „nie rzadziej niż okno obserwacji `dry-run`". Poniższa komenda jest **odczytem kontrolnym
   człowieka** na tym samym źródle, z którego liczy się metryka — do użycia przy triage'u alertu albo gdy
   chcesz potwierdzić stan bez czekania na przelot:

```bash
gcloud asset search-all-resources --scope=organizations/<ORG_ID> \
  --asset-types=cloudresourcemanager.googleapis.com/Project \
  --billing-project=<PROJEKT_ADM> \
  --format='table(additionalAttributes.projectId, project, state)'
```

   → **DOWÓD:** `ACTIVE` przy każdym numerze, który stoi w `spec.resources` albo `status.resources`. Każdy
   inny stan = wejście w krok 1 dla tego członka, tego samego dnia. Numer **nieobecny w wyniku** to nie jest
   „w porządku" — obserwator liczy go jako `unreadable` i alarmuje osobnym warunkiem; rozstrzyga wtedy
   `gcloud projects describe <ID>`.

   > [!NOTE]
   > `--billing-project` jest tu potrzebny, bo to są poświadczenia **użytkownika**. Producent metryki go nie
   > ustawia (nagłówek `X-Goog-User-Project` wymaga `serviceusage.services.use`, którego konto planu nie ma
   > — kwota konta serwisowego idzie domyślnie na jego własny projekt).

> [!WARNING]
> Dwa fałszywe sygnały, oba zmierzone. **`gcloud projects list` nie pokazuje skasowanego projektu w ogóle**,
> więc „nie ma go na liście" wygląda identycznie jak „nigdy go nie było" — pytaj `describe` po ID. Oraz:
> przez ~60 s po skasowaniu wywołania na projekcie **nadal przechodzą**, więc pojedyncze zielone sprawdzenie
> tuż po zdarzeniu nie znaczy nic.

### Co się dzieje z DOWODEM po odejściu członka

| | martwy projekt, wpis **został** | offboarding, wpis **usunięty** |
|---|---|---|
| raport naruszeń | członek **nadal liczony**, licznik z czasem spada do zera | **klucz członka znika w całości** |
| co to znaczy dla bramki promocji | zero naruszeń = „czyste okno" → martwy członek robi się **coraz lepszym kandydatem** | nie ma czego promować; bramka nie ma wejścia |
| wpisy w sinku | zostają | **zostają** — sink celowo nie filtruje po liście członków |
| gdzie widać te wpisy | przypisane do członka | sekcja **„Naruszenia spoza listy członków"** + wiersz w tabeli klas |

**Offboarding NIE produkuje fałszywego „czystego okna".** Dowód nie znika i nie zeruje się — zmienia
przypisanie z „ten członek" na „projekt spoza listy", a raport podaje liczbę wprost. Fałszywe czyste okno
powstaje **wyłącznie** w wariancie odwrotnym: wpis zostaje, projekt znika.

**Powrót nie dziedziczy stażu.** `dry_run_since` odchodzi razem z wpisem; ponowny onboarding ustawia je na
dzisiaj, więc okno obserwacji liczy się od zera. Kierunek bezpieczny.

### Prerekwizyty przy powrocie — to są WYMAGANIA WOBEC WNIOSKODAWCY

Powrót idzie **normalnym onboardingiem**, nie rewertem PR-a offboardingowego. Warunki poniżej wnioskodawca
ma spełnić **przed** złożeniem wniosku; pre-flight je **sprawdza** i odrzuca wniosek, gdy ich nie ma —
**nie naprawia ich za wnioskodawcę** (DEC-5, DEC-24).

| prerekwizyt | czyj | co robi repozytorium perimetru |
|---|---|---|
| projekt istnieje i jest `ACTIVE`, numer zgadza się z `project_id` | zespół właścicielski projektów | `projects describe` — check pre-flightu |
| konto rozliczeniowe podpięte | właściciel projektu | check pre-flightu, werdykt **`UWAGA`, nie czerwony** (konto `plan` nie czyta billingu) |
| **Private Google Access** na podsieciach | dywizja / zespół sieciowy | `networks/subnets list` — check pre-flightu |
| **prywatna strefa DNS** na restricted VIP (`199.36.153.4/30`); dla profili notebookowych osobno `private.googleapis.com` (`199.36.153.8/30`) | dywizja / zespół sieciowy | `dns managed-zones list` — check pre-flightu |
| tożsamości z reguł (konta serwisowe) istnieją | dywizja | ACM i tak odrzuci całą zmianę komunikatem `invalid or non-existent` |

**Dlaczego to nie jest formalność.** Projekt bez PGA i bez strefy DNS wchodzi do `dry-run` z kompletem
zielonych bramek, przechodzi całe okno obserwacji „czysto" (bo nic w nim nie chodzi) i **umiera w dniu
promocji** — ruch idzie publicznym endpointem i zostaje odcięty. Tryb awarii opóźniony o cały okres
obserwacji. Katalog gotowych snippetów jest **dokumentacją do skopiowania** przez właściciela prerekwizytu,
a nie kodem stosowanym przez nasz pipeline.

### Definition of Done

- [ ] wpis członka usunięty; `plan` po `apply` = `No changes. Your infrastructure matches the configuration.`
- [ ] `perimeters describe`: numer **nieobecny** w `status.resources` **i** `spec.resources`, przy niezerowej
      kontroli anty-tautologicznej na innym członku
- [ ] `drift_resources: 0`, `apply_pending_seconds: 0`, deklaracja równa granicy
- [ ] w logu `apply` poziom (jeśli kasowany) zaczyna się kasować **po** `Destruction complete` swojej reguły
- [ ] jeśli `apply` padł na `403` — wpis-nagrobek `armed: false` wrócił, `apply` znów zielony, repozytorium
      **odblokowane**
- [ ] raport naruszeń: klucz członka zniknął, wpisy widać w sekcji „spoza listy członków"
- [ ] **projektu nie kasowaliśmy** — a jeśli ma zniknąć, poszło to do zespołu właścicielskiego projektów
      i nie jest częścią tej zmiany
---

## D. Odtworzenie perimetru po utracie (DR) — krok, którego pipeline NIE wykona

**Kiedy ta część.** Perimetr przestał istnieć: `perimeters describe <PERIMETR>` odpowiada `NOT_FOUND`, albo
przebieg `apply` melduje

```
Plan: 19 to add, 0 to change, 0 to destroy.
Error: Error creating ServicePerimeter: googleapi: Error 403: The caller does not have permission
```

To nie jest awaria pipeline'u do naprawienia ponowieniem. **Konto CI nie ma i nie będzie miało prawa
utworzyć perimetru** — patrz niżej „Dlaczego". Ponawianie przebiegu daje ten sam błąd w nieskończoność.

### D.0 Czego ta część NIE dotyczy

* Perimetr **istnieje**, ale blokuje legalny ruch → część **B** (break-glass), nie ta.
* Perimetr istnieje, a rozjechał się jego **kształt** → zwykły PR + `apply`; CI ma `servicePerimeters.update`.
* Członek ma wyjść z granicy → część **C** (offboarding).

Ta część zaczyna się wyłącznie tam, gdzie **obiekt perimetru zniknął**.

### D.1 Warunki wstępne — sprawdź je ZANIM zaczniesz, nie w trakcie

| Co | Konkret | Jak sprawdzić |
|---|---|---|
| Tożsamość **człowieka** (nie CI) | rola nosząca `accesscontextmanager.servicePerimeters.create` na organizacji — u nas `roles/accesscontextmanager.policyAdmin` | `gcloud organizations get-iam-policy <ORG_ID>` |
| Zapis do stanu Terraform | prefiks `vpc-sc/perimeter` w buckecie stanu (u nas przez `roles/owner` na projekcie bucketa → `projectOwner:` w ACL) | `gcloud storage buckets get-iam-policy gs://<BUCKET>` |
| ADC lokalnie | `gcloud auth application-default login` — **nie** impersonacja konta CI: ono właśnie nie może tego zrobić | `gcloud auth application-default print-access-token` |
| Wersja Terraform | ta z `.tool-versions` repozytorium | `terraform version` |

Człowiek **nie jest objęty** polityką IAM Deny `vpcsc-ci-no-destroy` — jej `deniedPrincipals` to wyłącznie
dwa konta serwisowe CI. Droga odtworzeniowa stoi więc otworem dokładnie dla tej jednej tożsamości.

### D.2 Kroki

```bash
# 1. (tylko w ćwiczeniu DR) usunięcie perimetru — w realnym incydencie ten krok już się wydarzył
gcloud access-context-manager perimeters delete <PERIMETR> --policy=<POLICY_ID>

# 2. KROK CZŁOWIEKA — sam szkielet perimetru, lokalnie, z ADC człowieka
cd terraform/
terraform init
terraform apply -target=google_access_context_manager_service_perimeter.this

# 3. reszta pipeline'em: members, reguły, access levele, monitoring, kontrakt
#    (workflow `apply.yml` na gałęzi domyślnej — normalna droga, bez wyjątków)
```

**Krok 2 jest jedynym, którego nie da się przenieść do CI**, i jest jedynym powodem, dla którego DR tej
granicy ma w ogóle człowieka w pętli.

### D.3 Ile to trwa (zmierzone, nie szacowane)

| Odcinek | Ile | Kto | Skąd |
|---|---:|---|---|
| `perimeters delete` | **2 s** | człowiek | ćwiczenie DR |
| `terraform apply -target=…service_perimeter.this` | **6 s** | **CZŁOWIEK** | ćwiczenie DR; niezależny pomiar na materiale szablonu: 12 s |
| `apply.yml` — pozostałe 18 zasobów | **130 s** | pipeline | ten sam przebieg |
| **Razem** | **~3 min** | | z czego krok wymagający człowieka: **6 s** |

Wniosek, który ma paść w rozmowie o RTO: **udział człowieka to sekundy, nie minuty.** Odzysk nie jest
wolniejszy dlatego, że ktoś musi go zacząć — jest wolniejszy o tyle, ile trwa dotarcie tej osoby do
klawiatury, a ta osoba i tak jest już w incydencie (ktoś musiał zauważyć, że granicy nie ma).

### D.4 Bramka promocji w czasie odzysku — zachowanie poprawne, wyglądające jak przeszkoda

Po utracie perimetru **żywy `status` jest pusty**. Bramka promocji porównuje deklarację z żywym stanem, więc
odbudowę każdego członka konfiguracji egzekwowanej czyta jako **promocję dry-run → enforced** i żąda jawnej
zgody — mimo że nikt niczego nie promuje, a jedynie przywraca stan sprzed minuty.

**To jest zachowanie prawidłowe i nie należy go obchodzić.** Bramka pyta o PRZEJŚCIE, a jej wejściem jest
świat żywy, nie pamięć o świecie sprzed awarii — inaczej dałoby się przemycić promocję, kasując perimetr.
W incydencie kosztuje to jedno świadome potwierdzenie; alternatywa („bramka ufa, że to odbudowa") kosztuje
całą własność, dla której bramka istnieje.

Zapisz to w zgłoszeniu incydentu jako krok, nie jako niespodziankę.

### D.5 Weryfikacja po odbudowie

Porównaj **kształt**, nie sam fakt istnienia obiektu:

```bash
gcloud access-context-manager perimeters describe <PERIMETR> --policy=<POLICY_ID> --format=json \
  | jq '{status_res: (.status.resources|length), status_ing: (.status.ingressPolicies|length),
         spec_res: (.spec.resources|length), spec_ing: (.spec.ingressPolicies|length),
         spec_eg: (.spec.egressPolicies|length)}'
```

Liczby muszą się zgadzać z migawką sprzed utraty. „Perimetr istnieje" nie jest weryfikacją — po
odtworzeniu samego szkieletu istnieje też perimetr **pusty**, czyli nic nie chroniący.

### D.6 Dlaczego zostawiamy tu człowieka (a nie dokładamy uprawnienia)

Pełne uzasadnienie: **DEC-37**. W skrócie, bo w incydencie nikt nie czyta rejestru decyzji:

* `servicePerimeters.create` byłoby uprawnieniem **stałym**, używanym **raz na katastrofę**;
* nowy perimetr utworzony poza procedurą jest **niewidoczny** dla wszystkiego, co tę granicę obserwuje —
  `drift`, sonda granicy, metryka obserwatora i raport naruszeń pytają o **konkretny** perimetr z konfiguracji;
* koszt kontroli to zmierzone **6 s** — czyli kontrola, której nikt nie ma powodu obchodzić.

Odwrotny werdykt zapadł tam, gdzie brak uprawnienia trafiał w **rutynę**: `accessLevels.delete` **dołożono**,
bo bez niego każdy offboarding dywizji z własnym poziomem kończył się stanem częściowo zastosowanym.
Różnicę robi częstotliwość i to, czy istnieje obejście — nie to, jak groźnie brzmi nazwa uprawnienia.
