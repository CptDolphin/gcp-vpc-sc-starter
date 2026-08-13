# Karta wejścia — co musimy wiedzieć o organizacji, zanim cokolwiek ruszy

Ten dokument **wysyła się**, a nie czyta. To lista pytań z miejscem na odpowiedź; wypełnia go architekt
albo zespół sieciowy organizacji docelowej. Odpowiedzi wpisuje się potem **wprost** w konkretne pola
konfiguracji — mapa „odpowiedź → knob" jest na końcu (§G) i jest sprawdzalna: każda pozycja wskazuje plik
i klucz, a nie „ustalenie".

**Po co osobny dokument, skoro jest [`2-uprawnienia-i-wif.md`](2-uprawnienia-i-wif.md).** Tamten opisuje,
o co **my prosimy**. Ten pyta o **stan zastany i cudze procesy** — czyli o rzeczy, których nie da się
wywnioskować z własnego repozytorium, a które decydują o kształcie wdrożenia. Jeden i drugi jedzie do tego
samego ticketu.

**Przy każdym pytaniu jest zdanie „jeśli nie".** To nie jest ozdoba: bez niego dokument jest ankietą,
a z nim jest narzędziem decyzyjnym — widać, co dokładnie zmienia się w harmonogramie, kiedy odpowiedź
brzmi „nie mamy", „nie wiemy" albo „nie dostaniecie". Brak odpowiedzi **też** jest odpowiedzią: §H spisuje,
co przyjmiemy za prawdę, jeśli pytanie zostanie bez reakcji.

## Jak czytać znaczniki

| znacznik | znaczenie |
|---|---|
| **`[D0]`** | **musi być przed dniem zero** — bez tego nie da się nawet zaplanować pierwszego `apply` |
| **`[PÓŹNIEJ]`** | można ustalić w trakcie; brak odpowiedzi opóźnia jedną funkcję, nie całe wdrożenie |

Pytania `[D0]` to §A w całości, większość §B, §C1–C4, §D1–D6 i §E. Jeśli macie czas na jedną rundę,
odpowiedzcie najpierw na nie.

---

## A. Stan zastany granicy

Wszystko w tej sekcji jest **`[D0]`**: od tych odpowiedzi zależy, czy wchodzimy ścieżką brownfield
(dokładamy do istniejącego perimetru), czy greenfield (stawiamy nowy) — a to dwa różne harmonogramy
i dwa różne zestawy uprawnień.

### A1 · Czy organizacja ma już **access policy** Access Context Managera? Ile ich jest i jakie mają numery? `[D0]`

Prosimy o wynik: `gcloud access-context-manager policies list --organization=<ORG_ID>`.
Interesuje nas polityka **org-level** (bez `scopes`) oraz ewentualne polityki **scoped** (przypięte
do folderów).

**Odpowiedź:** `______________________________________________________________`

**Jeśli nie ma żadnej:** utworzenie polityki org-level jest jednorazowym krokiem **człowieka**
z uprawnieniami org-level; nasz pipeline tego nie zrobi i nie powinien. Bez niej nie ma gdzie postawić
perimetru — to blokada twarda, nie opóźnienie.

**Jeśli jest więcej niż jedna:** musimy wiedzieć, **która** jest tą właściwą, zanim cokolwiek wpiszemy —
pomyłka kieruje wszystkie zapisy do polityki, której nikt nie obserwuje.

> **Dlaczego to jest pierwsze pytanie.** Access levele należą do **polityki**, nie do perimetru, i limit
> na nie jest **na organizację** (§A6). Skasowanie polityki zabiera perimetr **i wszystkie access levele
> naraz** — to jedyny obiekt w tym torze, którego utrata nie ma taniego odzysku.

### A2 · Czy perimetr już istnieje? Jaka jest jego **nazwa techniczna** i **tytuł**? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli TAK:** wchodzimy w tryb brownfield — `perimeter.manage_skeleton: false`, dokładamy wyłącznie
członków i reguły, treść perimetru zostaje u obecnego właściciela. Przejęcie szkieletu jest **krokiem
osobnym i późniejszym** ([`4-brownfield-import.md`](4-brownfield-import.md)); idzie przez `import`, więc
**nie ma momentu bez ochrony** — zmierzone: zero wpisów `UpdateServicePerimeter` w oknie planu i importu.

**Jeśli NIE:** greenfield, `manage_skeleton: true` — ale wtedy ktoś **człowiek** musi mieć
`accesscontextmanager.servicePerimeters.create` (§B3). Konto pipeline'u go świadomie nie ma i mieć nie
będzie.

**Tytuł jest osobnym pytaniem**, bo ACM pilnuje jego unikalności: przy kolizji dostaniemy
`INVALID_ARGUMENT: Service Perimeter with title '…' already exists`.

### A3 · Jaka jest lista `restrictedServices` i `vpcAccessibleServices` **żywego** perimetru? `[D0]`

Prosimy o surowy zrzut: `gcloud access-context-manager perimeters describe <PERIMETR> --policy=<POLICY> --format=json`.

**Odpowiedź:** *(załącznik / wklejony JSON)* `_______________________________________`

**Jeśli nie dostaniemy:** krok 1 procedury brownfield — bramka „czy `policy.yaml` opisuje rzeczywistość" —
nie ma z czym porównać. Apply po imporcie **wyrównuje chmurę do repo**, więc każda przemilczana różnica
wraca jako **zmiana zakresu ochrony**, a nie jako czerwony plan. Bez tego zrzutu przejęcie szkieletu
jest zablokowane; sam brownfield (dokładanie członków) działa dalej.

**Uwaga na kolejność:** listy porównujemy jako **zbiory**. Zmierzone: API zwraca `restrictedServices`
w innej kolejności niż wysłane, przy identycznej zawartości — asercja na liście dałaby fałszywy alarm.

### A4 · Jakie **tytuły** mają istniejące reguły ingress i egress? Prosimy o pełną listę. `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Dlaczego pytamy akurat o tytuły, a nie o treść reguł.** ACM odrzuca duplikat **po TYTULE**
(`Unable to create ServicePerimeter…IngressPolicy, existing object already found: … title:<tytuł>`),
a nasz renderer produkuje tytuły **deterministyczne**: `baseline--<nazwa>` dla reguł baseline
i `<dywizja>-<projekt>--<profil>` dla profilowych. Stąd:

| wariant | co się dzieje | okno bez autoryzacji |
|---|---|---|
| **wasze tytuły ≠ nasze wzorce** | powstają **dodatkowe** reguły, wasze zostają nietknięte | **brak — zero sekund** |
| **kolizja tytułu** | `create` pada; żeby przeszedł, trzeba **najpierw skasować waszą regułę** | **realne**: od skasowania do naszego `apply` ruch nie jest autoryzowany |

**Jeśli nie dostaniemy listy:** zakładamy kolizję i planujemy okno jak zwykłą zmianę produkcyjną
(ogłoszenie, obserwacja, gotowy rollback). To jest droższe wejście na wszelki wypadek — i jedyna rzecz,
którą ta jedna odpowiedź kupuje albo traci.

> To jest utrata **dostępności**, nie ochrony: w oknie granica jest *bardziej* szczelna, nie mniej.
> Nazywamy to precyzyjnie, bo reakcja na jedno i drugie jest inna.

### A5 · Czy perimetr ma konfigurację **dry-run** (`spec`) różną od egzekwowanej (`status`)? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli nie wiemy:** nasz pierwszy `plan` pokaże zmiany, które nie są nasze, a recenzent nie będzie miał
jak ich odróżnić od naszych. Dodatkowo: perimetr **bez** jawnego `spec` kopiuje do dry-run swoją
konfigurację egzekwowaną — zmierzone, i to ta kopia potrafi wywrócić dodanie projektu, który „przecież
nigdzie nie jest".

### A6 · Ile **access leveli** jest już w polityce i jak się nazywają? `[D0]`

`gcloud access-context-manager levels list --policy=<POLICY>`.

**Odpowiedź:** `______________________________________________________________`

**Jeśli jest ich dużo:** limit to **500 na ORGANIZACJĘ** (udokumentowany przez dostawcę, **nie** zmierzony —
API go nie eksponuje; `services quota list` zwraca wyłącznie tempo: 500 odczytów/min, 50 zapisów/min).
Podział na kilka perimetrów **tego limitu nie dzieli**, scoped policy też nie — zakresem jest polityka.
Praktycznie: wzorzec „własny access level na dywizję" wyczerpuje się przy 500 dywizjach, a przy wzorcu
złożonym (dwa poziomy na dywizję) przy **250** — czyli w tym samym rzędzie wielkości co sufit atrybutowy
(§E1). Jeśli jesteście blisko, projektujemy poziomy **współdzielone** od początku, a nie po alarmie.

**Jeśli któreś z tych poziomów są CUDZE — powiedzcie które.** Konto apply ma
`accesscontextmanager.accessLevels.delete`, bo bez niego offboarding dywizji z własnym poziomem pada
w połowie, na żywej granicy. To uprawnienie jest jednak **org-level z definicji** i sięga **każdego
nierefereowanego** poziomu w polityce — także należącego do perimetru, którego to repozytorium nie
zarządza, i także poziomu awaryjnego. Bramka po naszej stronie widzi wyłącznie referencje z **naszej**
konfiguracji. Nasze poziomy odtwarza jeden `apply` z repozytorium; **cudzych nie odtwarza nic.** Lista
cudzych poziomów pozwala nam objąć je świadomą listą wyjątków, zamiast liczyć na to, że nikt ich nie
tknie.

### A7 · Czy któryś z projektów-kandydatów należy **już** do innego perimetru? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli tak:** projekt należy do **dokładnie jednego** perimetru regularnego — również w konfiguracji
dry-run. Zmierzone: dodanie do dry-run drugiego perimetru zostaje **odrzucone**
(`A resource can be included in exactly one regular service perimeter`), i przechodzi dopiero po nadaniu
pierwszemu perimetrowi jawnego `spec`, który ten projekt wyklucza. To znaczy, że migracji „bezszwowej" nie
ma: `create_before_destroy` daje **głośną odmowę**, nie płynne przejście. Taki projekt wymaga własnego
okna i uzgodnienia z właścicielem tamtego perimetru — czyli osobnego terminu, nie kolejnego wiersza
w partii.

### A8 · Kto jest dziś **właścicielem** perimetru i **czym** go zmienia? `[D0]`

(konsola · `gcloud` z ręki · inny Terraform · inny pipeline — prosimy nazwać zespół i narzędzie)

**Odpowiedź:** `______________________________________________________________`

**Jeśli to inny Terraform:** dwa stany na jednym obiekcie — nasz drift i ich apply będą się nawzajem
cofać. To trzeba rozstrzygnąć **zanim** ruszymy, a nie po pierwszym rozjeździe.

**Jeśli to konsola albo `gcloud` z ręki:** wasze reguły zostają poza zarządzaniem Terraforma **na stałe** —
provider **nie obsługuje importu** reguł granularnych (`doesn't support import`; w stanie mają `id`
perimetru, nie własne). Chroni je `ignore_changes`, więc nic ich nie skasuje, ale: drift ich nie pilnuje,
raport naruszeń nie przypisze ich do członka, a w konsoli wyglądają identycznie jak nasze.

---

## B. Uprawnienia — łącznie z tym, czego NIE dostaniemy

Uprawnienia Access Context Managera działają **wyłącznie na organizacji albo na konkretnej polityce**.
Grant na folderze lub projekcie **nie ma żadnego efektu** — to ograniczenie dostawcy, nie nasz wybór.
Dlatego cała redukcja ryzyka idzie w **zestaw operacji** (rola własna bez `create`/`delete` + warstwa Deny),
a nie w zawężanie zasięgu.

### B1 · Czy dostaniemy **read-only na organizacji** dla zespołu i konta `plan`? `[D0]`

`organizationViewer` · `accesscontextmanager.policyReader` · `browser` · `cloudasset.viewer` ·
`logging.viewer` · `serviceusage.serviceUsageViewer`

**Odpowiedź:** `______________________________________________________________`

**Jeśli nie:** nie zrobimy inwentarza z §A, więc wejście brownfield jest **niewykonalne** — nie
„utrudnione". Zostaje wariant awaryjny: **scoped policy** na folderze-piaskownicy z `policyEditor` na tej
jednej polityce. Kupuje pełny test pipeline'u, ale oznacza **osobny perimetr**, czyli rezygnację z wymogu
„jeden perimetr" i z jednego obrazu granicy.

### B2 · Potwierdzenie: **NIE** dostajemy `resourcemanager.projects.create` ani `.delete`. Zgadza się? `[D0]`

**Odpowiedź:** ☐ zgadza się ☐ dostaniecie — jakie dokładnie: `_______________________`

**Jeśli faktycznie nie** (zakładamy to domyślnie): cykl życia projektu nie należy do tego repozytorium.
Offboarding kończy się **na granicy** — usuwamy projekt z perimetru i z access leveli, i na tym nasza
odpowiedzialność się kończy. Nasze narzędzia nie sprzątają po projekcie i nie mają jak.

**Jeśli jednak dostaniemy — powiedzcie wprost.** Zmienia to zakres i blast-radius na tyle, że wolimy
wiedzieć o tym przed wdrożeniem niż przy pierwszym incydencie.

### B3 · Kto ma `accesscontextmanager.servicePerimeters.create` (praktycznie: `roles/accesscontextmanager.policyAdmin` na organizacji)? `[D0]`

Prosimy o **grupę** (nie osobę) i o to, jak ją dosięgnąć poza godzinami pracy.

**Odpowiedź:** `______________________________________________________________`

**Po co, skoro sami o to nie prosimy.** Perimetru nie tworzy tożsamość automatyczna — to świadoma decyzja,
podparta warstwą Deny (czyli przeżywa nawet „dajmy CI na chwilę `policyEditor`, żeby odblokować release").
Ale po utracie granicy ktoś musi ją odtworzyć: to **~6 s pracy człowieka** w ~3-minutowym odzysku
(procedura: [`3-runbook-promocja-i-break-glass.md`](3-runbook-promocja-i-break-glass.md), część D).
Uprawnienie potrzebne **raz na katastrofę**, a nie w rutynie — dlatego nie jest spłacane obejściami.

**Jeśli nikt go nie ma** (albo nie da się go dosięgnąć w nocy): odzysk granicy nie ma wykonawcy. Mamy wtedy
procedurę bez osoby, a to nie jest procedura.

### B4 · Kto ma org-level `roles/logging.configWriter`? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Po co.** Stack `violations-sink/` — kubełki logów, sinki **org-level** z `include_children`, widoki
i granty `logging.viewAccessor` — applikuje **człowiek** z tą rolą. Konto pipeline'u jej świadomie nie ma:
para „sink + kubełek" to gotowa ścieżka wyprowadzenia logów gdzie indziej.

**Jeśli nikt:** granica **stoi i działa**, ale obserwator nie ma czego czytać — raport naruszeń i detektor
okna świeżej sieci milczą. Zgłosi to dopiero dead-man's-switch po `watchdog_absent_seconds`; **nic
wcześniej**. Alternatywa (org-wide `roles/logging.viewer` dla konta planu) działa, ale jest szersza:
to prawo odczytu logów **wszystkich** projektów organizacji, nie tylko członków granicy.

### B5 · Czy dostaniemy `roles/cloudasset.viewer` **na organizacji**? `[D0]`

**Odpowiedź:** ☐ tak ☐ nie ☐ tylko na folderze: `_____________________`

**Jeśli nie:** nie wykryjemy **martwego członka** jednym wywołaniem. Dziś robi to jedno zapytanie Asset
Inventory o całą organizację (`asset search-all-resources --asset-types=…/Project`), z odczytem pola
`state`. Bez tego zostaje pytanie **per projekt** (`resourcemanager.projects.get`) — czyli nowe nadanie
na organizacji, kilkaset wywołań na przebieg i **ani jednego stanu więcej**.

**Dlaczego to jest ważne akurat u was:** patrz §C1. Projekt skasowany po wejściu do granicy jest
niewidoczny dla **wszystkich** pozostałych warstw: `terraform plan` mówi `No changes`, `apply` mówi
`0 added, 0 changed, 0 destroyed`, budżet atrybutów nadal go liczy, a raport naruszeń nadal go widzi.
Soft-delete trwa **30 dni** i ACM przyjmuje taki projekt bez słowa.

### B6 · Który projekt **członkowski** będzie projektem sondującym kontroli pozytywnej? `[D0]`

**Odpowiedź:** `_____________________` (ID projektu; musi być członkiem konfiguracji **egzekwowanej**)

**Po co to pytanie.** Sonda granicy ma jedną sondę, która musi **przejść** — dowód, że reguła baseline
kogoś **wpuszcza**, a nie tylko że granica odmawia. Bez niej „wszystko odmówione" jest nieodróżnialne od
zepsutego środowiska. Ta sonda potrzebuje prawa odczytu logów **w sondowanym projekcie**.

**Jeśli nie wskażecie żadnego:** kontrola pozytywna celuje w projekt z wejścia przelotu, a wtedy prawo
odczytu musi obejmować **każdego** członka — czyli w praktyce org-wide `roles/logging.viewer`, prawo
odczytu treści każdego logu w organizacji dla konta CI. Przy setkach członków rozsianych po drzewie
nadanie per-folder jest tym samym w przebraniu, a per-członek — listą nie do utrzymania.

**Czego to pytanie NIE wymaga:** org-wide `roles/logging.viewer`. Konto `plan` go nie dostaje —
raport naruszeń czyta **widok** sinka (§B4), guard sinka ma rolę własną `vpcScSinkReader` z jednym
uprawnieniem `logging.sinks.get` (konfiguracja, nie treść), a kontrola pozytywna ma nadanie
**per-projekt** w tym jednym wskazanym tu projekcie.

**Ustawia:** `positive_control_project_id` w `iam-bootstrap/terraform.tfvars` **oraz** zmienną repo
`POSITIVE_CONTROL_PROJECT` (obie muszą mieć tę samą wartość — rozjazd znaczy „sonda pyta o projekt,
w którym nie ma prawa czytać").

### B7 · Kto ma `roles/iam.denyAdmin`? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Po co.** Warstwa IAM Deny to jedyna kontrola przeżywająca podmianę roli własnej — zakaz **ponad** rolami.
`roles/iam.denyAdmin` jest **jedyną** rolą niosącą `iam.denypolicies.create`; roli własnej z tym
uprawnieniem **zbudować się nie da** (`customRolesSupportLevel = NOT_SUPPORTED`).

**Jeśli nikt po naszej stronie:** `manage_deny_policy = false` i warstwa zostaje poza wdrożeniem
**świadomie** — trzeba to zapisać tam, gdzie opisujecie architekturę, bo diagram z Deny i wdrożenie bez
Deny wyglądają w repo **identycznie**.

**Kto powinien ją trzymać:** zespół IAM **rozłączny** z właścicielem perimetru — inaczej warstwa nie stoi
ponad rolami, tylko obok nich. Nam wystarcza odczyt (`deny_reader_principals`): `terraform plan` schodzi
do `No changes` na samym odczycie polityki.

### B8 · Czy wolno założyć **pulę WIF** (OIDC dla GitHub Actions) i w którym projekcie? `[D0]`

**Odpowiedź:** projekt tożsamości: `____________________` ☐ WIF OK ☐ tylko klucze SA

**Jeśli nie:** nie ma ścieżki keyless. Klucz konta serwisowego to ten sam dostęp, tylko **bez daty
ważności i bez powiązania z repozytorium** — jeśli taka jest decyzja, chcemy ją mieć na piśmie, razem
z właścicielem rotacji.

### B9 · Kto tworzy **bucket na stan Terraform** i gdzie? `[D0]`

Wymogi: versioning **tak**, soft-delete **tak**, retention-lock **nie**.

**Odpowiedź:** `______________________________________________________________`

**Jeśli z retention-lock:** stanu nie da się nadpisać, czyli pipeline nie zapisze wyniku żadnego apply.
To nie jest zaostrzenie polityki — to wyłączenie narzędzia.

**Uwaga na prefiksy:** bucket może być wspólny, ale **prefiksy muszą być różne** dla stanu perimetru
i stanu stacku nadającego uprawnienia. Inaczej konta CI mogą nadpisać stan tego, co je uprawnia.

### B10 · Który projekt jest **projektem monitoringu** granicy? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli żaden:** sekcja `monitoring` zostaje pusta i wdrożenie degraduje się bezpiecznie — nic się nie
psuje, ale granica jest **świadomie ślepa**. Wtedy zapiszcie, kto zamiast tego patrzy na Security Command
Center, bo inaczej „ktoś patrzy" jest założeniem, nie ustaleniem.

**Ustawia:** `monitoring.project_id` w `perimeter/policy.yaml` **oraz** `monitoring_project_id`
w `iam-bootstrap/` — obie wartości muszą być identyczne.

### B11 · Czy projekty administracyjne granicy mogą **zostać poza** perimetrem? `[D0]`

(projekt bucketa stanu · projekt bucketa kontraktów · projekt monitoringu)

**Odpowiedź:** `______________________________________________________________`

**Jeśli nie mogą:** to jedyny tryb awarii tego rozwiązania, którego **`git revert` nie cofa**. Gdy projekt
ze stanem Terraforma trafi do konfiguracji egzekwowanej, a `storage.googleapis.com` jest wśród usług
chronionych, konto apply traci dostęp do **własnego stanu** — bo pipeline woła spoza granicy. Rewert nie
pomaga, bo apply rewertu też potrzebuje stanu. Z tej pętli wychodzi wyłącznie człowiek z uprawnieniami
org-level, ręcznie na żywej polityce.

**Ustawia:** `control_plane_projects` — i wpisujemy tam **oba** identyfikatory (ID i numer), bo bramka
dopasowuje jeden albo drugi, a wniosek może nieść dowolny.

---

## C. Cudze procesy, od których zależy nasza ścieżka

### C1 · Kto kasuje projekty w tej organizacji i **czy nas o tym powiadamia**? `[D0]`

**Odpowiedź:** zespół: `__________________` kanał powiadomienia: `__________________`

**Jeśli nie powiadamia** — a to jest przypadek domyślny, gdy cykl życia projektu należy do innego zespołu
(§B2): **martwy członek granicy jest normalnym trybem pracy, nie incydentem.** Skutek jest gorszy niż
nieaktualny wpis:

> Martwy projekt przestaje generować naruszenia. Po kilku tygodniach jego licznik naruszeń w oknie
> obserwacji spada do **zera** — a zero naruszeń to dokładnie to, co bramka promocji przyjmuje za
> **dowód czystego okna**. Martwy członek staje się z czasem **coraz lepszym kandydatem do promocji**.

Dlatego pytamy też o **kanał**: ticket, mail, temat Pub/Sub, feed Asset Inventory. Mając kanał, wiążemy go
z detektorem; nie mając — detektor chodzi cyklicznie (dziś: **co godzinę**) i wykrywa fakt po czasie,
nie w chwili zdarzenia.

### C2 · Czy istnieje **fabryka projektów** (landing zone)? Jak wygląda ścieżka „nowy projekt → PGA → DNS na restricted VIP → aktywny billing"? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli nie ma:** nasz kanał **nie tworzy** projektu, sieci, podsieci, Private Google Access, wpisów DNS
ani powiązania z kontem rozliczeniowym. Bez tego projekt wejdzie do perimetru i po promocji jego
workloady **stracą łączność z API dostawcy**, mimo że wszystkie reguły VPC-SC będą poprawne — awaria
wygląda wtedy jak awaria aplikacji, nie jak polityka.

To są **wymagania wobec wnioskodawcy**, które my **weryfikujemy**, a nie spełniamy. Granica jest tu
świadoma: gdyby jeden wniosek miał robić oba kroki, to jest integracja **dwóch** automatów (fabryka
projektów + nasz kanał), a tworzenie projektu ma inny blast-radius niż dodanie go do granicy.

Bramka pre-flight sprawdza to maszynowo przed każdym wejściem i zostawia `plan`/`apply` w stanie
`skipped` przy czerwonym werdykcie. Prerekwizyt jest **warunkowy**: projekt bez sieci VPC (same zbiory
BigQuery, buckety, endpoint wołany z zewnątrz) dostaje **N/D**, a nie błąd.

### C3 · Gdzie leżą projekty-kandydaci: w jednym folderze czy są rozsiane? Ile folderów? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli są rozsiane** (a tak zwykle jest): nadanie uprawnień „tylko na naszym folderze" jest **org-wide
w przebraniu** — żeby pokrycie było kompletne, trzeba objąć wszystkie foldery, czyli faktycznie całą
organizację, tylko zapisaną jako N nadań zamiast jednego. Wariant „nadania per projekt" rośnie
o tyle pozycji, ile projektów wchodzi miesięcznie, i wymaga wiedzy o zdarzeniu, o którym nikt nas nie
informuje (§C1).

> Odniesienie z naszego wdrożenia: **cztery projekty leżały już w dwóch różnych folderach.** Przy
> kilkuset projektach zakładamy rozrzut po całej organizacji, dopóki nie usłyszymy inaczej.

### C4 · Kto zatwierdza wnioski **sieciowe**, a kto **security**? Prosimy o nazwy grup. `[D0]`

**Odpowiedź:** sieć: `__________________________` security: `__________________________`

**Jeśli nie dostaniemy nazw:** nazwa grupy zatwierdzającej wchodzi do allowlisty kanału wejściowego
(kontrola „zatwierdzone przez właściwą grupę"). Bez niej kanał nie odróżni zatwierdzenia od jego braku,
a bramka fail-closed odrzuci **każdy** wniosek.

### C5 · Czy w waszym procesie **zatwierdzający może być wnioskodawcą**? `[PÓŹNIEJ]`

**Odpowiedź:** ☐ nie, rozdzielone ☐ tak, dopuszczalne

**Jeśli „tak, dopuszczalne":** nasza kontrola odrzuca samo-zatwierdzenie porównaniem tożsamości —
i będzie odrzucać wnioski, które u was są **poprawne**. Trzeba ją wtedy albo zdjąć świadomie (z zapisem
gdzie i dlaczego), albo przenieść do waszego procesu zatwierdzania.

### C6 · Kto jest adresatem alertu, gdy granica **zablokuje ruch produkcyjny**? `[D0]`

**Odpowiedź:** kanał: `__________________` osoba/dyżur: `__________________`

**Jeśli nikt:** alert bez kanału to alert, którego nikt nie widzi. Konfiguracja przechodzi, granica działa,
a pierwsza informacja o blokadzie przychodzi od użytkownika.

**Ustawia:** `monitoring.notification_channels` w `perimeter/policy.yaml`.

### C7 · Czy jest kanał **niezależny od tej organizacji**, którym da się potwierdzić doręczenie alertu? `[PÓŹNIEJ]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli nie:** dead-man's-switch traci sens — obserwator wewnątrz obserwowanego systemu milczy razem
z nim. Zostajemy z alertami, o których wiemy, że są **skonfigurowane**, ale nie że **docierają**
(DEC-14, DEC-28).

### C8 · Skąd bierzemy **właściciela** (grupę) każdego projektu wchodzącego do granicy? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli „z GCP":** nie da się. Zmierzone na wszystkich projektach naszej organizacji: etykiety projektu
niosą cokolwiek w **2 z 8** przypadków i **w żadnym** nie niosą właściciela; folder-rodzic jest proxy
**dywizji**, nie grupy; wiązanie `roles/owner` istnieje, ale wskazuje **osobę**, nie grupę — zły typ.
**Żaden kanał po stronie chmury nie produkuje tej odpowiedzi.** Mieszka ona w CMDB / systemie ticketowym
albo nigdzie — a jest adresatem raportu naruszeń i przeglądu wpisu, więc „nigdzie" znaczy „nikt nie
odbierze".

---

## D. Kanał wejścia

### D1 · Jakiego systemu ticketowego używacie? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli to nie ServiceNow:** kanał ticketowy trzeba napisać od nowa — mapowanie pól i weryfikację ticketu.
Dwa pozostałe kanały (ręczny pull request architekta i kanał repozytorium zespołu) działają niezależnie
od tej odpowiedzi i wystarczają do uruchomienia granicy (DEC-7).

### D2 · (ServiceNow) Nazwa instancji i czy **Table API** `sc_req_item` jest dostępne dla konta integracyjnego? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli nie jest:** nie ma jak zweryfikować ticketu **u źródła**, więc jedyną informacją o zatwierdzeniu
byłby payload zgłoszenia — czyli dane, które sam nadawca kontroluje. Kanał zostaje wtedy w trybie
testowym, a jedynym kanałem produkcyjnym jest ręczny pull request.

### D3 · (ServiceNow) Jak nazywa się **wasze** pole z identyfikatorem projektu? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Dlaczego to pytanie w ogóle istnieje.** Nasz kontrakt zakłada `u_project_id`, a prefiks `u_` znaczy
**pole własne** — czyli nazwa jest wasza, nie platformy. Żadna instancja developerska dostawcy tego nie
potwierdzi.

**Jeśli nazywa się inaczej:** poprawiamy listę `sysparm_fields` i fixture'y. To jedna linijka — pod
warunkiem, że wiemy o tym **przed** uruchomieniem, a nie po pierwszym odrzuconym wniosku.

### D4 · (ServiceNow) Jakie wartości przyjmuje pole `approval` po zatwierdzeniu? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli inne niż `approved`:** zbiór wartości zależy od procesu w instancji, nie od platformy. Kontrola
porównuje wartość dosłownie, więc przy innym słowniku **odrzuci każdy zatwierdzony ticket**.

### D5 · (ServiceNow) Czy grupa zatwierdzająca przychodzi jako `assignment_group.name`, i czy uwierzytelnienie **Basic** przejdzie? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Dlaczego pytamy o kształt, a nie o dostęp.** Table API zwraca pola **dot-walk** (`assignment_group.name`)
**wyłącznie wtedy, gdy zostały jawnie zamówione** w `sysparm_fields`; bez tego referencja przychodzi jako
`{"link": …, "value": <sys_id>}`, a klucza z kropką w odpowiedzi **nie ma w ogóle**. Wcześniejsza wersja
naszego narzędzia czytała pole, którego jej własne zapytanie nie zamawiało — na żywej instancji
odrzuciłaby **każdy** ticket, a fixture świecił na zielono.

**Jeśli Basic nie przejdzie** (MFA, OAuth, ACL na tabeli): potrzebujemy uzgodnienia sposobu
uwierzytelnienia **przed** wdrożeniem — to nie jest szczegół implementacyjny, tylko warunek istnienia
kanału.

### D6 · (ServiceNow) Kto po waszej stronie wykona **jeden odczyt** z instancji docelowej i porówna go z naszym kontraktem? `[D0]`

**Odpowiedź:** `______________________________________________________________`

To jedna komenda `curl` (pełna treść: [`5-servicenow-intake.md`](5-servicenow-intake.md) §8.4), nie
projekt. Do czasu tego odczytu kanał ticketowy wolno uruchamiać **wyłącznie w trybie testowym** — który
sam mówi o sobie, czym jest (DEC-43).

**Jeśli nikt:** kanał zostaje w trybie testowym bezterminowo. Nasz symulator sprawdza **kontrakt
platformy** (semantyka `sysparm_fields`, kształt referencji, pusta tablica zamiast 404) i celowo łamie
założenia — ale **nie zna** waszych pól `u_*`, waszego przepływu approvali ani waszej wersji API. Tego
nie zamknie żadna symulacja.

### D7 · Czy wolno użyć **GitHuba** (Actions + environment) jako mutatora? `[D0]`

**Odpowiedź:** ☐ tak ☐ nie — nasz forge: `__________________`

**Jeśli nie:** cała ścieżka apply stoi na GitHub Actions, WIF i `environment` jako bramce zatwierdzenia.
Inny forge znaczy: przepisanie mutatora i inna postać `attribute_condition` puli WIF. Reszta — schematy,
reguły OPA, Terraform, katalog profili — przenosi się bez zmian.

**Pytanie dodatkowe:** czy wasz plan GitHuba pozwala na **ochronę gałęzi** i wymaganego recenzenta
na environment? Bez nich `CODEOWNERS` nie jest egzekwowany przez forge w ogóle, a jedyną barierą zostają
bramki uruchamiane przez mutatora (DEC-16). Działa, ale to inny model zaufania i trzeba go nazwać.

---

## E. Pojemność i tempo

### E1 · Ile projektów wchodzi w **pierwszej fazie**, a ile miesięcznie potem? `[D0]`

**Odpowiedź:** faza pierwsza: `__________` tempo: `__________` / mies.

**Dlaczego to nie jest pytanie o harmonogram, tylko o architekturę.** Perimetr ma limit **6 000 atrybutów
na KONFIGURACJĘ** (`spec` i `status` liczone osobno). Przy naszej gęstości profili koszt krańcowy wynosi
**9,87 atrybutu na członka** (zmierzone między punktami 300 i 500 członków):

| próg | atrybuty | członków |
|---|---:|---:|
| warning 70 % | 4 200 | **~435** |
| critical 85 % | 5 100 | ~525 |
| **ŚCIANA** — API odrzuca wnioski na `apply` | 6 000 | **~620** |

**Jeśli pierwsza faza przekracza ~440 projektów:** wchodzicie **od razu na warning** i zapas starczy na
kwartał. To jest punkt zatrzymania — partii się wtedy nie zaczyna, tylko najpierw sięga po dźwignię
z §E2.

**Jeśli docelowa skala przekracza ~620:** decyzja „jeden perimetr" wraca na stół. Żadna z tańszych
dźwigni nie zmienia wtedy rzędu wielkości.

**Czas trwania partii — do wpisania w okno zmiany** (ekstrapolacja z pomiaru, nie pomiar na tej skali):
300 członków ≈ **24 min** samego `apply`, 500 ≈ **41 min**. Zapisy do perimetru **szeregują się** —
dziesięciokrotne zwiększenie równoległości Terraforma dało **1,25×** przyspieszenia. Pre-flight liczy się
osobno: **11 s na projekt**, czyli 300 projektów szeregowo to **55 min**.

### E2 · Ile jest dywizji i czy członkowie jednej dywizji dzielą **tożsamość wołającą** oraz **access level**? `[D0]`

**Odpowiedź:** dywizji: `______` wspólny SA w dywizji: ☐ tak ☐ nie ☐ różnie

**Jeśli tak:** dostępna jest jedyna dźwignia, która realnie przesuwa ścianę — kolaps reguł profilowych do
poziomu dywizji. Dla dywizji o 40 członkach: **44 atrybuty zamiast 200**, koszt na członka spada
z ~9,9 do ~1,75, sufit rośnie z ~620 do **~3 300** członków.

**Cena, nazwana wprost:** pole `resources` reguły ingress jest `ForceNew` — dopisanie członka **zastępuje**
regułę całej dywizji, więc każdy onboarding otwiera okno, w którym **cała dywizja** traci tę regułę.
Minuty, nie sekundy. Dlatego to jest dźwignia druga, nie pierwsza.

**Jeśli nie dzielą tożsamości:** dźwignia jest niedostępna i sufit ~620 zostaje twardy.

### E3 · Jaki wzorzec access leveli planujecie: własny na dywizję czy współdzielone? `[PÓŹNIEJ]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli własny na dywizję:** patrz §A6 — limit 500 na organizację, przy wzorcu złożonym efektywnie 250
dywizji. To sufit **niezależny** od atrybutowego i nie znika po podziale perimetrów.

### E4 · Które usługi mają być objęte granicą? `[D0]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli inne niż nasz baseline:** repo niesie twardy niezmiennik „baseline musi zawierać *usługę X*",
egzekwowany w **trzech** miejscach naraz (precondition Terraforma i dwie reguły OPA). Na perimetrze
chroniącym co innego `plan` **nie ruszy**: `Error: Resource precondition failed`. Dwie uczciwe drogi:
zmienić niezmiennik na wasz (z zapisem decyzji) **albo** poszerzyć baseline przejmowanego perimetru jako
osobną, zatwierdzoną zmianę zakresu ochrony. Kasowanie bramki nie jest jedną z nich — po nim przejęcie
„się udaje", a granica przestaje cokolwiek obiecywać.

**Ustawia:** `restricted_services` i `vpc_accessible_services` w `perimeter/policy.yaml`.

---

## F. Okno obserwacji i promocja

### F1 · Jakie okno dry-run przed włączeniem egzekwowania? `[PÓŹNIEJ]`

**Odpowiedź:** minimum dni w dry-run: `______` dni czystego okna: `______`

**Jeśli chcecie „od razu enforced":** formularz takiej opcji nie ma świadomie. Promocja jest osobnym
pull requestem i osobnym ręcznym uruchomieniem apply z listą promowanych (DEC-17) — bo włączenie blokowania
bez okna obserwacji to zgadywanie, kogo odetniemy.

**Ustawia:** `onboarding.dry_run_min_days`, `onboarding.clean_window_days`.

### F2 · Czy istnieje ruch **między projektami członkowskimi**? `[PÓŹNIEJ]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli tak:** okno dry-run go **nie widzi** — ruch wewnątrz perimetru nie jest naruszeniem, więc czyste
okno **nie jest dowodem** dla tej klasy przepływów. Trzeba je zinwentaryzować osobno, zanim ktokolwiek
uzna zero naruszeń za gotowość.

### F3 · Czy któraś dywizja wypuszcza dane **poza chmurę dostawcy**? Kto to zatwierdza? `[PÓŹNIEJ]`

**Odpowiedź:** `______________________________________________________________`

**Jeśli tak:** zgoda materializuje się jako **wpis w pliku**, którego właścicielem jest Security —
z wymienionym członkiem, profilem, dokładnymi celami i **datą wygaśnięcia** równą dacie przeglądu wpisu
(DEC-23). Bez wpisu bramka odrzuca wniosek na **obu** torach, więc nie da się jej ominąć commitem prosto
na gałąź domyślną. Zgoda w tickecie nie wystarcza — ticket nie jest czytany przez bramkę.

---

## G. Mapowanie odpowiedzi na konfigurację

Ta tabela istnieje po to, żeby odpowiedzi dało się **wpisać**, a nie interpretować.

| Pytanie | Co ustawia | Gdzie |
|---|---|---|
| A1 | `organization.org_id`, `organization.access_policy_name` | `perimeter/policy.yaml`; `org_id` też w `iam-bootstrap/terraform.tfvars` |
| A2 | `perimeter.name`, `perimeter.title`, **`perimeter.manage_skeleton`** | `perimeter/policy.yaml` |
| A3 | `restricted_services`, `vpc_accessible_services` | `perimeter/policy.yaml` |
| A4 | decyzja: apply dokładający czy okno zmiany; ewentualne prefiksy tytułów | procedura, [`4-brownfield-import.md`](4-brownfield-import.md) |
| A5, A7 | kolejność wejścia członków; czy potrzebny jawny `spec` u obecnego właściciela | plan wdrożenia |
| A6, E3 | budżet access leveli; wzorzec `perimeter/access-levels/*.yaml`; lista poziomów cudzych | `perimeter/access-levels/` |
| A8 | czy w ogóle wchodzimy w przejęcie szkieletu | decyzja przed etapem 3 |
| B1, B5, B6 | role read-only konta `plan`; **`grant_sink_reader`**, **`positive_control_project_id`** (+ zmienna repo `POSITIVE_CONTROL_PROJECT`) | `iam-bootstrap/` |
| B2 | zakres offboardingu (kończy się na granicy) | `docs/` — zapis granicy odpowiedzialności |
| B3 | wykonawca odzysku w runbooku break-glass | [`3-runbook-promocja-i-break-glass.md`](3-runbook-promocja-i-break-glass.md) |
| B4 | kto applikuje `violations-sink/` (człowiek, nie pipeline) | [`1-wdrozenie.md`](1-wdrozenie.md), tabela trzech stacków |
| B7 | **`manage_deny_policy`**, `deny_reader_principals` | `iam-bootstrap/terraform.tfvars` |
| B8 | `identity_project_id`, `wif_pool_id`, `wif_provider_id`, `github_repository` | `iam-bootstrap/terraform.tfvars` |
| B9 | `state_bucket`, `state_prefix`, `contract.state_bucket` | `iam-bootstrap/`, `terraform/versions.tf`, `perimeter/policy.yaml` |
| B10 | **`monitoring_project_id`** = `monitoring.project_id` | `iam-bootstrap/terraform.tfvars` + `perimeter/policy.yaml` |
| B11 | `control_plane_projects` (ID **i** numer) | `perimeter/policy.yaml` |
| C1 | rytm i próg detektora martwego członka | `terraform/monitoring.tf` |
| C2 | prerekwizyt pozycji katalogowej; interpretacja werdyktów pre-flightu | [`5-servicenow-intake.md`](5-servicenow-intake.md) §7 |
| C3 | zasięg nadań IAM (org vs foldery) | wniosek o dostępy |
| C4 | allowlista grup zatwierdzających | konfiguracja kanału wejściowego |
| C6 | `monitoring.notification_channels` | `perimeter/policy.yaml` |
| C8 | `owner_group` w każdym wpisie członka | `perimeter/projects.yaml` |
| D1–D7 | wybór **kanału wejścia** i lista `sysparm_fields` | `.github/workflows/`, `tools/snow_verify.py` |
| E1, E2 | próg alarmu budżetu; czy stosujemy kolaps reguł do poziomu dywizji | `attribute_budget`, katalog profili |
| E4 | `restricted_services` + niezmiennik baseline'u | `perimeter/policy.yaml`, `policy/*.rego` |
| F1 | `onboarding.dry_run_min_days`, `onboarding.clean_window_days` | `perimeter/policy.yaml` |
| F3 | `egress_approvals` | `perimeter/policy.yaml` |

---

## H. Co przyjmiemy, jeśli pytanie zostanie bez odpowiedzi

Brak odpowiedzi nie zatrzymuje wdrożenia — uruchamia **założenie**. Spisujemy je tutaj, żeby nikt nie
odkrył ich przy pierwszym incydencie.

| Pytanie | Założenie domyślne | Co to kosztuje |
|---|---|---|
| A2 | perimetr **istnieje**, `manage_skeleton: false` | nie zarządzamy baseline'em; jego zmiany są dla nas niewidoczne |
| A4 | tytuły **kolidują** | planujemy okno zmiany produkcyjnej, którego być może nie trzeba |
| A6 | w polityce nie ma cudzych access leveli | offboarding może skasować nierefereowany poziom, którego nikt nie odtworzy |
| A7 | żaden kandydat nie jest w innym perimetrze | pierwszy taki projekt zatrzyma partię głośną odmową |
| B2 | **nie mamy** `projects.create/delete` | offboarding kończy się na granicy; projekt zostaje |
| B3 | nikt nie ma `servicePerimeters.create` w gotowości | odzysk granicy nie ma wykonawcy — ryzyko zapisane, nie pokryte |
| B4 | nikt nie ma org-level `logging.configWriter` | brak raportu naruszeń → promocja bez dowodu |
| B7 | brak `iam.denyAdmin` → `manage_deny_policy = false` | warstwa Deny nie istnieje; trzeba to napisać w architekturze |
| C1 | **nie powiadamiacie** o skasowaniu projektu | martwy członek jest trybem normalnym; detektor chodzi co godzinę |
| C5 | zatwierdzający **nie może** być wnioskodawcą | wnioski samo-zatwierdzone będą odrzucane |
| C8 | `owner_group` nie da się wywnioskować | wpis bez właściciela nie przejdzie bramki — wniosek wraca do autora |
| D1 | kanał ticketowy zostaje w trybie **testowym** | produkcyjny jest ręczny pull request architekta |
| E1 | tempo nieznane → alarm budżetu tylko na progu statycznym | ostrzeżenie przyjdzie później, niż mogłoby |
| F1 | domyślne okno dry-run z `policy.yaml` | promocja możliwa dopiero po pełnym oknie |

---

## Co dołączamy do tej karty

- [`2-uprawnienia-i-wif.md`](2-uprawnienia-i-wif.md) — rola po roli, z uzasadnieniem i gotową listą do ticketu;
- diagram modelu dostępów i WIF (`docs/diagrams/D2-iam-and-wif.png`);
- katalog `iam-bootstrap/` — gotowy Terraform, który **applikuje wasz zespół**, nie nasz pipeline;
- [`4-brownfield-import.md`](4-brownfield-import.md) — jeśli odpowiedź na A2 brzmi „istnieje".
