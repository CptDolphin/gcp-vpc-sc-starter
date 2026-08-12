# Decyzje, na których stoi ten starter (DEC-1…DEC-23)

Dwadzieścia trzy rozstrzygnięcia, które określają kształt repozytorium. Kod odsyła tutaj skrótem `DEC-1`…`DEC-23` — jeśli komentarz

---

# Decyzje, na których stoi ten starter

Rozstrzygnięcia, które określają kształt repozytorium. Kod odsyła tutaj skrótem `DEC-<numer>` — jeśli komentarz
w pliku mówi „(DEC-4)", to znaczy: „powód tej linijki jest opisany w DEC-4, nie zmieniaj jej bez przeczytania".
Liczby w nagłówku świadomie nie ma: przez pół roku stała tu wartość mniejsza od realnej i nikt tego nie zauważył,
bo nic jej nie mierzyło. Kompletności rejestru pilnują dwie bramki — `tools/decisions_check.py` (każda **cytowana**
decyzja ma sekcję) i `starter-drift` w trybie `--wzgledem` (zbiór decyzji pokrywa zbiór startera, DEC-20).

Każda pozycja ma tę samą strukturę: **decyzja** · **dlaczego** · **co odrzucono i dlaczego**. Odrzucone warianty są
tu celowo — bez nich decyzja wygląda na jedyną możliwą, a była wyborem. Jeśli któryś z nich wróci jako propozycja,
odpowiedź jest już zapisana.

---

## DEC-1 — Jeden perimeter org-wide, baseline chroni Vertex AI od dnia zero

**Decyzja.** Jeden regularny perimeter w org-level access policy (`accessPolicies/<numer>/servicePerimeters/<nazwa>`).
Bez perimetrów per zespół, bez perimetrów typu bridge. `restricted_services` zawiera `aiplatform.googleapis.com`
razem z usługami, których Vertex realnie używa (`storage`, `bigquery`, `artifactregistry`, `notebooks`,
`logging`, `monitoring`); ta sama lista idzie do `vpc_accessible_services`. Baseline jest własnością centralną
(CODEOWNERS: sieć + security); zespoły dokładają członkostwo i reguły z katalogu profili, nigdy nie ruszają
`restricted_services`.

**Dlaczego.** Samo `aiplatform` nie wystarcza: Vertex czyta model z GCS, dane z BigQuery, obrazy treningowe
z Artifact Registry, notebooki przez `notebooks` (`colab.googleapis.com` NIE jest wspierane przez VPC-SC —
Colab Enterprise podlega granicy przez `aiplatform`, bo runtime jest zasobem Vertex AI). Perimeter chroniący wyłącznie `aiplatform` zostawia dane
w miejscu, z którego i tak da się je wyprowadzić — i wygląda przy tym w konsoli na włączony.

**Trade-off do wypowiedzenia wprost.** Wewnątrz perimetru nie ma granic: dwa zespoły po dołączeniu są w tej samej
strefie zaufania, bo VPC-SC nie ogranicza ruchu intra-perimeter. Jedyną ochroną między nimi zostaje IAM. Perimetru
nie wolno komunikować jako izolacji **między** zespołami.

**Kryterium rewizji** (dowolne z trzech uruchamia nową decyzję, nie doraźny podział): (a) wymóg izolacji między
zespołami → ścieżka pierwszego wyboru to *scoped policy*; (b) rezydencja danych wymuszająca granicę regionalną;
(c) zużycie budżetu atrybutów > 70% w którejkolwiek konfiguracji → drugi perimeter.

**Odrzucone.**
- *Perimeter per zespół + bridge'y.* Bridge to reguły egress/ingress plus access levels do utrzymania i triażu,
  a nie chroni niczego, czego jeden perimeter by nie ochronił, dopóki właścicielem granicy jest jeden zespół.
  Liczba par rośnie kwadratowo, a każde nowe połączenie to nowy wniosek — dokładne zaprzeczenie self-service.
- *Scoped policy per zespół od razu.* Delegacja administracji granicy zespołowi, który dopiero poznaje VPC-SC,
  przenosi na niego blast-radius, którego nie umie oszacować. Zostaje ścieżką wyjścia dla dojrzałego zespołu.
- *Perimeter bez `restricted_services` na start („najpierw wpuśćmy wszystkich, potem dokręcimy").* Pusty perimeter
  jest security no-op, a jednocześnie wygląda na włączoną ochronę — najgorszy rodzaj awarii, bo niemy.

---

## DEC-2 — System ticketowy jest front-doorem, Git jest źródłem prawdy, pipeline jest jedynym mutatorem

**Decyzja.** System ticketowy nie ma żadnych uprawnień w GCP: zero kont serwisowych, zero federacji tożsamości,
zero wywołań API Access Context Managera. Jego rolą jest formularz, rejestr zgody, approval i widoczność statusu.
Po approvalu woła `workflow_dispatch` (wcześniej `repository_dispatch` — zmienione z tego samego powodu co kanał
dywizji: tamten trigger wymagał od integracji `contents: write`, czyli prawa zapisu do KODU perimetru);
workflow **oddzwania do API systemu ticketowego** i weryfikuje, że ticket
istnieje, jest zatwierdzony, approver należy do właściwej grupy, a treść zgadza się z payloadem. Bot otwiera PR
z jednym plikiem członka i **nie zatwierdza własnego PR-a**. Jedynym bytem mutującym perimeter jest pipeline
z tożsamością WIF keyless, applyujący **artefakt planu przypięty SHA256**, w environment z required reviewers.

**Dlaczego.** Integracja ticket→API daje szybkość i odbiera trzy rzeczy, bez których granica bezpieczeństwa się nie
utrzymuje: **audyt** (dlaczego ta reguła istnieje i kto ją zaakceptował), **rollback** (`git revert` zamiast
rekonstrukcji stanu z pamięci) i **wykrywanie dryfu** (bez deklaratywnego źródła nie ma z czym porównać stanu
realnego). Prędkość, którą kupuje, jest zresztą nieistotna przy zmianie, która i tak czeka 14 dni w oknie dry-run.

**Zasada nadrzędna.** *Payload webhooka to dane, nigdy autoryzacja.*

**Odrzucone.**
- *System ticketowy woła API bezpośrednio.* Traci audyt, rollback i dryf, a sam staje się częścią płaszczyzny
  sterowania bezpieczeństwem.
- *Bot commituje prosto na gałąź główną (bez PR).* Usuwa jedyny moment, w którym człowiek widzi diff granicy przed
  zastosowaniem. Bramki maszynowe łapią kształt, nie intencję („ten projekt nie należy do tego zespołu").
- *Zaufanie payloadowi zgłoszenia bez oddzwonienia.* Dispatch jest tak wiarygodny jak token, który go
  wysłał — a tokeny wyciekają. Weryfikacja u źródła zamienia „ufam wiadomości" w „ufam systemowi rekordu".
- *Apply z laptopa operatora.* Brak przypiętego planu i powtarzalności; przy org-plane singletonie każdy ręczny
  apply to potencjalny wyścig z pipeline'em (DEC-6).

---

## DEC-3 — Katalog profili zamiast surowych reguł

**Decyzja.** Zespół wybiera **profil** z katalogu (`perimeter/profiles/*.yaml`), nie pisze reguł. Profil to
wersjonowany szablon reguł ingress/egress, sparametryzowany danymi członka (numer projektu, konta serwisowe, access
level). Reguły renderuje Terraform z pary (członek × profil) — nikt spoza zespołu platformy nie edytuje HCL.

> **SPROSTOWANIE (DEC-22, 2026-08-12).** Ta decyzja opisywała drugą ścieżkę: *„ścieżka wyjątku istnieje jawnie
> (`exceptions[]` w pliku członka, approval security, uzasadnienie); trzeci taki sam wyjątek to sygnał do
> stworzenia profilu"*. **Ta ścieżka nigdy nie działała.** Pole było w schemacie, miało regułę OPA na długość
> uzasadnienia i wpis w CODEOWNERS obiecujący udział Security — a `grep -rn "exceptions" terraform/` dawał
> **zero**: renderer nie tworzył z niego ani jednej reguły. Dywizja deklarowała wyjątek, dostawała zielony pull
> request, merge, apply — i nie powstawało nic. Awaria była fail-closed (ruch nadal zablokowany), więc nie
> zagrażała danym; zagrażała zaufaniu i przepustowości, bo zawór ucieczki miał pochłaniać wszystko, czego katalog
> nie pokrywa. **Pole zostało usunięte** (schemat, reguła OPA, renderer wpisów, CODEOWNERS). Jedyną drogą
> dołożenia reguły spoza katalogu jest dziś **nowy profil** — w `perimeter/profiles/`, pod CODEOWNERS Security.
> Zdanie „trzeci taki sam wyjątek to sygnał do stworzenia profilu" zostaje jako zasada projektowania katalogu;
> zmienia się to, że pierwszy też nim jest.

**Dlaczego — dwa powody, oba twarde.**
1. **Limit atrybutów.** Perimeter ma 6 000 atrybutów na konfigurację, liczonych **osobno** dla egzekwowanej
   i dry-run. Każda tożsamość, zasób, usługa, metoda i access level w regule zjada z tego budżetu. Trzydzieści
   zespołów piszących własne reguły zapcha limit — i zrobi to cicho.
2. **Review się nie skaluje.** Reviewer nie oceni poprawności n-tej surowej reguły egress napisanej przez kogoś,
   kto pierwszy raz widzi VPC-SC. Oceni natomiast jeden profil, raz.

**Odrzucone.**
- *Surowe reguły we wniosku.* Zapycha budżet, przenosi ciężar oceny na reviewera przy każdym wniosku i wymaga od
  wnioskodawcy znajomości VPC-SC — czyli likwiduje self-service, dla którego cały mechanizm powstaje.
- *Generowanie reguł automatycznie z naruszeń dry-run („co się złamało, to dopiszmy").* Automat nie odróżnia
  przepływu legalnego od eksfiltracji, która akurat zadziałała, i zamienia perimeter w odbicie stanu faktycznego
  zamiast intencji. Naruszenia zostają **wejściem do projektowania profilu**, nie źródłem reguł.
- *Jeden szeroki profil „vertex-all".* Znosi rozróżnienie między servingiem a treningiem i między maszyną
  a człowiekiem, więc każdy członek dostaje maksimum uprawnień, jakich potrzebuje ktokolwiek.

---

## DEC-4 — Dwustopniowy onboarding: dry-run, potem enforced

**Decyzja.** Plik członka ma pole `stage` o dwóch wartościach. Wniosek tworzy członka **zawsze** ze `stage: dry-run`
— projekt trafia do konfiguracji dry-run, jego naruszenia są logowane, nic nie jest blokowane. Okno obserwacji:
**minimum 14 dni ORAZ zero naruszeń w ostatnich 7** (oba warunki, nie alternatywa). Promocja to **osobny PR
z człowiekiem**. Offboarding jest odwrotnością: usunięcie pliku wyprowadza projekt z obu konfiguracji, a break-glass
usuwa go wyłącznie z egzekwowanej, zostawiając dry-run — incydent nie kasuje wiedzy o przepływach.

**Dlaczego.** To nie jest ostrożnościowy dodatek, tylko konsekwencja mechaniki VPC-SC: perimeter może mieć
jednocześnie konfigurację egzekwowaną i dry-run, a projekt może należeć do jednej egzekwowanej i jednej dry-run.
Wrzucenie nowego zespołu od razu do konfiguracji egzekwowanej odcina mu produkcję w minutę po merge'u — bo nikt,
łącznie z nim, nie zna wszystkich jego przepływów przed pomiarem. Dry-run to jedyny sposób, żeby je **zmierzyć**
zamiast zgadywać.

**Dlaczego 14 dni, a nie „zielono od trzech".** Dry-run łapie wyłącznie przepływy, które faktycznie zaszły.
Miesięczny batch, kwartalny audyt i recertyfikacja nie pojawią się w krótkim oknie i złamią się dopiero po promocji.

**Odrzucone.**
- *Wejście od razu do konfiguracji egzekwowanej.* Pierwszy poważny wniosek kończy się incydentem produkcyjnym
  cudzego zespołu, po czym perimeter dostaje etykietę „to, co psuje deploye" — i zaczyna się kupowanie wyjątków.
- *Osobny perimeter „staging" dla nowych członków.* Mechanizm dry-run w tym samym perimetrze daje ten sam efekt bez
  drugiej granicy do utrzymania i bez ryzyka, że ktoś zostanie w stagingu na zawsze.
- *Promocja automatyczna po czystym oknie.* „Zero naruszeń" dowodzi, że nic się nie złamało w oknie — nie że
  whitelist jest kompletna. Ostatnia ocena należy do człowieka, który zna kalendarz zespołu.
- *Rezygnacja z jawnej treści dry-run (dziedziczenie z egzekwowanej).* Bez `use_explicit_dry_run_spec = true` nie da
  się mieć członka istniejącego wyłącznie w dry-run, czyli nie da się etapować onboardingu.

---

## DEC-5 — Granica własności: weryfikujemy prereq, nie provisionujemy cudzej infrastruktury

**Decyzja.** To repozytorium jest właścicielem wyłącznie **granicy**: perimetru, `restricted_services`,
`vpc_accessible_services`, członkostwa, reguł z profili i access levels. Nie tworzy i nie modyfikuje projektów, VPC,
podsieci, tras, stref DNS, endpointów Vertex ani bucketów. Prereq sieciowy jest **egzekwowany** bramką pre-flight
(read-only, przeciw żywemu API), ale naprawia go właściciel projektu. Gotowe snippety leżą w `docs/` jako
dokumentacja do skopiowania, nie jako kod applyowany przez ten pipeline.

**Co sprawdza pre-flight:** projekt istnieje, należy do organizacji i zgadza się z deklarowanym numerem · projekt
**nie należy już do innej konfiguracji egzekwowanej** (twarde ograniczenie API) · podsieci mają Private Google
Access · istnieje strefa DNS kierująca ruch API na restricted VIP · dla profili notebookowych osobny check na
`private.googleapis.com` dla `*.notebooks.googleusercontent.com` · ostrzeżenie (nie blokada) o istniejących
endpointach Vertex, bo muszą powstać **po** wejściu projektu do perimetru.

**Gdzie ten pre-flight realnie stoi — patrz DEC-24.** Słowo „egzekwowany" w akapicie wyżej opisuje *rolę*
narzędzia, a nie jego wpięcie: przez pewien czas ta rola była wyłącznie zapisana, bo `preflight_check.sh`
nie miał ŻADNEGO wyzwalacza. DEC-24 opisuje bramkę, która to zdanie czyni prawdziwym, i mówi wprost, czego
ta bramka NIE obejmuje (check `--identity`, zmiana wpisu członka już obecnego w granicy).

**Dlaczego.** Wymaganie „po approvalu tworzą się automatycznie odpowiednie zasoby" kusi, by onboarding provisionował
także sieć i projekty wnioskodawcy. Wtedy repozytorium perimetru staje się właścicielem cudzych VPC — a razem
z własnością przychodzi każdy incydent, każdy dyżur i każda zmiana w cudzym środowisku.

**Odrzucone.**
- *Onboarding provisionuje sieć wnioskodawcy.* Wymaga uprawnień administratora sieci w każdym projekcie
  członkowskim, czyli zamienia konto serwisowe perimetru w najbardziej uprzywilejowaną tożsamość w organizacji.
- *Brak pre-flight, poleganie na dokumentacji.* Tryb awarii jest cichy i opóźniony (ruch idzie publicznym
  endpointem albo notebook nie startuje), a winą obarczany jest perimeter. Sprawdzaj istnienie realnej
  konfiguracji, nie deklarację, że ktoś ją zrobił.
- *Pre-flight jako ostrzeżenie zamiast blokady.* Ostrzeżenie w PR-ze, który i tak scala bot, nie jest bramką.
  Ostrzeżeniem zostaje wyłącznie kolejność tworzenia endpointów — tam stan da się naprawić po fakcie.

---

## DEC-6 — Granularne zasoby ACM i single-flight apply

**Decyzja.** Zasób perimetru niesie **wyłącznie szkielet**: `title`, `perimeter_type`, `restricted_services`,
`vpc_accessible_services`, `use_explicit_dry_run_spec = true` oraz `lifecycle.ignore_changes` na listach
zarządzanych granularnie. Członkostwo i reguły to **osobne zasoby**, generowane `for_each` z plików YAML: każdy
członek dostaje warianty dry-run, a członek ze `stage: enforced` **dodatkowo** warianty egzekwowane. Klucze
`for_each` są deterministyczne i stabilne (`<zespół>-<projekt>-<profil>`), nigdy indeks listy. Apply jest
**single-flight** (`concurrency` bez `cancel-in-progress`) na jednym stanie.

**Dlaczego granularnie.** PR generuje plan na 2–3 zasoby zamiast przepisania całego perimetru, więc reviewer widzi
realny diff; usunięcie pliku to czysty destroy jednego zasobu; równoległe wnioski nie kolidują w tym samym bloku
HCL. Miarą sukcesu tej decyzji jest to, że `plan` w PR pokazuje wyłącznie zasoby danego członka.

**Dlaczego single-flight — uzasadnienie SKORYGOWANE pomiarem (2026-08-07).** Pierwotnie stało tu, że dwa
równoległe apply „nadpisują się nawzajem, a w logach widać dwa poprawne `update`". **To jest nieprawda —
zdanie zostało obalone pomiarem i nie należy go powtarzać w rozmowie o architekturze.**

Access Context Manager ma **optymistyczną kontrolę współbieżności na eTagach**. Przy nałożeniu w czasie
przegrany apply pada GŁOŚNO — `Error 400: The eTag provided '…' does not match the eTag` — a reguła zwycięzcy
zostaje. Przy przebiegu bez nałożenia oba kończą się `rc=0` i obie reguły są obecne. **Nic nie znika po cichu.**

Single-flight zostaje słuszny, ale argumentem jest **niezawodność, nie cicha utrata danych**: bez niego
~80-100% równoległych apply kończy się błędem, czyli platforma, w której co drugi merge losowo pada. Różnica
jest praktyczna, a nie akademicka — **przy eTagu retry pomaga**, przy cichej utracie by nie pomógł. Gdyby
utrata była cicha, samo `concurrency` też by nie wystarczyło: trzeba by weryfikować stan po każdym apply.

Skąd korekta: eksperyment [`experiments/race-two-states/`](../experiments/race-two-states/README.md) był
**zepsuty w sposób, który zawsze potwierdzał tezę** — używał fikcyjnych kont, które ACM odrzuca, więc oba
applye padały, a werdykt nie odróżniał „apply padł" od „reguła zniknęła". Po podmianie na realne tożsamości:
5/5 przebiegów = konflikt eTagu, zero cichych utrat. Eksperyment jest dziś sparametryzowany tożsamościami
i rozróżnia trzy wyniki — uruchom go, zanim ktoś podejmie tę decyzję na podstawie czyjejkolwiek opinii,
łącznie z tą zapisaną wyżej.

**Dlaczego `ignore_changes` jest obowiązkowe.** Bez tego szkielet i zasoby per-członek biją się o te same listy:
każdy apply usuwa to, co dodał poprzedni — flapping granicy bezpieczeństwa. Konsekwencja do zapamiętania: dopisanie
projektu albo reguły wprost do bloku szkieletu jest od tej chwili **cicho ignorowane**.

**Odrzucone.**
- *Monolityczny blok perimetru z listami z `locals`.* Każdy wniosek przepisuje całość, plan przestaje być czytelny,
  równoległe wnioski konfliktują. Zostaje właściwym kształtem tam, gdzie perimeter ma jednego właściciela i stabilną
  treść — czyli nie tutaj.
- *Mieszanie obu podejść bez `ignore_changes`.* To nie kompromis, tylko błąd; dokumentacja providera ostrzega wprost.
- *Zarządzanie perimetrem przez `gcloud` w skrypcie CI.* Traci plan, stan i wykrywanie dryfu — czyli dokładnie te
  własności, dla których DEC-2 wybrał Git jako źródło prawdy.

---

## DEC-7 — Trzy kanały wejścia, jeden mutator

**Decyzja.** Zmienia się wyłącznie to, **skąd przychodzi PR**; apply pozostaje jeden, na jednym stanie.

| Kanał | Kto | Dowód autoryzacji |
|---|---|---|
| `snow:` | ludzie bez Terraforma | ticket zweryfikowany **oddzwonieniem** do API systemu ticketowego |
| `manual:` | architekci, sieć | approval CODEOWNERS + wymagane statusy na chronionej gałęzi |
| `pr:` | repozytoria zespołów | mapowanie repo→projekty w `perimeter/contributors.yaml` (token: `actions: write`, bez prawa zapisu kodu) |

Pole opisujące podstawę zmiany nazywa się `change_ref` i ma trzy warianty (`snow:…`, `pr:ORG/repo#123`,
`manual:<uzasadnienie ≥20 znaków>`). Kanał `pr:` **nie aplikuje niczego** — repozytorium zespołu waliduje deklarację
u siebie i **uruchamia** `external-intake.yml` (`workflow_dispatch`, wniosek w `inputs`); PR otwiera
workflow po stronie perimetru. Zespół potrzebuje prawa uruchomienia tego workflowa (`actions: write`),
nie prawa zapisu do repo perimetru i nie uprawnień w GCP.

**Dlaczego `workflow_dispatch`, a nie `repository_dispatch`.** Wyboru nie robi elegancja, tylko
uprawnienie. `POST /repos/{o}/{r}/dispatches` wymaga `contents: write` — prawa zapisu do KODU perimetru
(zmierzone: `contents: read` + `pull-requests: write` → 403). Bramki treści wiszą na `pull_request`,
a apply rusza z pushu na gałąź domyślną, więc tam, gdzie ta gałąź nie jest chroniona, poświadczenie
dywizji jest ścieżką do zmiany granicy z pominięciem wszystkiego. `workflow_dispatch` chodzi po osi
`actions`, rozłącznej z `contents` w obie strony (`actions: write` → 204, `contents: write` bez `actions`
→ 403), więc token uruchamiający kanał nie zapisze ani jednego bajtu. **Jeden kanał, nie dwa:**
`repository_dispatch: vpc-sc-external` został usunięty, a nie zostawiony „na okres przejściowy" — dopóki
oba są czynne, wymogiem realnym pozostaje to szersze uprawnienie i zawężenie nic nie daje.

**Dlaczego mapowanie repo→projekty mieszka w repo perimetru.** Listę swoich dozwolonych projektów zespół
rozszerzyłby tym samym commitem, którym dodaje projekt. To jedyna rzecz, której kanał `pr:` nie może o sobie orzec.

**Dlaczego jedno pole zamiast opcjonalnego numeru ticketu.** Pole, które dla dwóch z trzech kanałów jest puste albo
fikcyjne, przestaje być czytane — a to ono odpowiada na pytanie „na jakiej podstawie ta reguła istnieje".

**„Bezpośrednio" znaczy *bez formularza*, nie *bez bramek*.** Wymagane statusy obowiązują też administratorów
(`enforce_admins: true`).

**Odrzucone.**
- *Każde repo zespołu aplikuje własnym stanem.* Wyścig na polityce org-level, N pisarzy z uprawnieniami do granicy
  całej organizacji, utrata sensu `attribute_condition`. Wraca do gry wyłącznie jako scoped policy — a to łamie DEC-1.
- *Repo perimetru jako moduł Terraform w rejestrze.* Moduł nie rozwiązuje ani wyścigu, ani uprawnień; przenosi
  tylko kod, a problemem jest stan i tożsamość.
- *Monorepo z submodule'ami repozytoriów zespołów.* Żeby zobaczyć zmianę, monorepo musi zbumpować wskaźnik
  submodule'a, czyli i tak potrzebny jest PR — zysk zerowy, kruchość większa.

---

## DEC-8 — Kontrakt zamiast dostępu do repozytorium

**Decyzja.** Repozytorium perimetru publikuje **kontrakt**: wąski JSON (~4 KB) generowany przy każdym apply
i wystawiany w **dwóch miejscach naraz** — jako obiekt w dedykowanym buckecie (konsumenci maszynowi spoza
GitHuba) i jako **asset release'u `contract`** w repozytorium perimetru (repozytoria dywizji). Zawiera nazwę
perimetru, `restricted_services`, parametry okna onboardingu, **nazwy** access
levels, katalog profili (nazwa, ryzyko, opis, nazwy parametrów), mapowanie repo→projekty i listę członków
ograniczoną do trójki `zespół/projekt/etap`. **Nie zawiera** ani jednej tożsamości, ani jednego zakresu IP, ani
jednej reguły. Bramki jadą osobno, jako artefakt release'u (`schemas/` + `policy/` + skrypt walidujący) — to reguły,
nie dane.

**Dlaczego DWA miejsca, a nie sam bucket.** Sam bucket kosztował dywizję tożsamość w GCP: federację WIF, konto
serwisowe i grant `roles/storage.objectViewer` na prefiksie — po to, żeby przeczytać 4 KB JSON-a. Przy trzydziestu
dywizjach to trzydzieści grantów, a zdanie „zespół nie dostaje żadnych uprawnień w GCP" przestawało być faktem
dokładnie w tym miejscu. Asset release'u pobiera się tym samym tokenem GitHuba, którym dywizja i tak pobiera
paczkę bramek — druga droga **nie dokłada ani jednego uprawnienia po żadnej ze stron** (odczyt release'u
mieści się w tym, co token ma już na wysyłkę zgłoszenia, punkt 3 niżej).
Bucket zostaje, bo konsument spoza GitHuba (job w GCP, skrypt operacyjny) nie ma jak sięgnąć po release.

**Niezbywalne: obie publikacje wychodzą z JEDNEGO kroku apply.** Bajty assetu to output `contract_json`, czyli
atrybut zasobu `google_storage_bucket_object.contract` zapisanego przez ten sam apply — nie drugie wyliczenie
`jsonencode(...)`. Dwa rendery mogłyby się rozjechać; jeden render nie ma z czym. Krok dodatkowo porównuje md5
pliku wgrywanego do release'u z sumą, którą **GCS policzył** z obiektu w buckecie — czyli patrzy na drugą stronę
publikacji, nie sam na siebie. Odrzucone: publikacja w `publish-gates.yml` (inny wyzwalacz = gwarantowany
rozjazd) i osobny job `needs: apply` (zielony apply z czerwoną publikacją zostawia rozjazd na stałe).

**Kontrakt jest jedyną rzeczą w tym łańcuchu, której NIE WOLNO przypinać.** Bramki są regułami — pin daje
powtarzalną walidację. Kontrakt jest stanem świata: przypięty pokazuje profile i access levels, których już nie
ma, czyli daje u dywizji zielono na wejściu, które repo perimetru odrzuci. Stąd ruchomy tag `contract` po jednej
stronie i `Cache-Control: no-store` po drugiej.

**Cztery własności, których nie wolno stracić.**
1. **Pola wypisane jawnie, pole po polu.** Nigdy `jsonencode(<coś zbiorczego>)` — jedna taka linia zamienia kontrakt
   w drugą kopię stanu. Egzekwowane testem w selfteście.
2. **Kontrakt trafia do INNEGO bucketa niż stan.** Wspólny bucket oznacza, że jeden błąd w warunku IAM odsłania
   state, a state to pełna mapa granicy. Egzekwowane `precondition` w `contract.tf`.
3. **Dwa rozłączne ACL:** writer = konto apply na prefiksie kontraktu; reader = konsumenci maszynowi spoza
   GitHuba, read-only. Konsument nie może podmienić danych, którym ufa kolejny konsument. **Po stronie GitHuba
   ta rozłączność też istnieje, ale trzeba było jej poszukać:** kanał dywizji szedł `repository_dispatch`-em,
   a ten wymaga `contents: write` na repo perimetru — czyli prawa zapisu do KODU (zmierzone: `contents: read`
   + `pull-requests: write` → HTTP 403 `Resource not accessible by integration`). Kanał został przestawiony
   na `workflow_dispatch`, który chodzi po osi `actions`: `actions: write` → 204, `contents: write` bez
   `actions` → 403. Token dywizji czyta kontrakt i bramki `Contents: Read-only`, a zgłoszenie wysyła
   `Actions: Read and write` — **nie mając prawa zapisu ani jednego bajtu** (szczegóły w `contrib/README.md`
   §„Zakres tokenu"). Granicy i tak nie pilnuje zakres tokenu, tylko `contributors.yaml` po stronie
   perimetru, payload traktowany jako dane, apply wyłącznie z gałęzi domyślnej i **ochrona tej gałęzi**
   (prerekwizyt wdrożenia — `docs/1-wdrozenie.md` §Etap 4).
4. **Kontrakt jest informacją, nie źródłem decyzji.** Reguła sprawdzająca, czy repozytorium może wnioskować o dany
   projekt, czyta plik **z repo**, nie z kontraktu. Gdyby decyzja zależała od kontraktu, wystarczyłoby go podmienić.

**Dlaczego nie `data` source.** Provider go nie ma — ani w `google`, ani w `google-beta` (są tylko `access_policy`,
`access_policy_iam_policy` i `supported_service/s`). Gdyby powstał, wymagałby `servicePerimeters.get` na
organizacji, czyli wglądu w całą granicę: reguły i tożsamości wszystkich zespołów.

**Dlaczego nie `terraform_remote_state`.** HashiCorp odradza to wprost: kto może czytać outputy, ma dostęp do całego
snapshotu stanu. Rekomendacja z dokumentacji brzmi — publikuj dane do konsumpcji zewnętrznej osobno.

**Odrzucone.**
- *Submodule z całym repo.* Oddaje `members/` wszystkich zespołów i zakresy IP po to, żeby zwalidować jeden plik.
  Raz udostępnione dane wracają w każdym klonowaniu i w każdej kopii CI.
- *Sparse checkout submodule'a.* Ogranicza working tree, nie historię — `git log`/`git show` nadal dosięga
  wszystkiego. Wygląda na ograniczenie, nie będąc nim.
- *Dokumentacja z listą profili na wiki.* Rozjedzie się w pierwszym tygodniu, a walidacja lokalna wymaga danych
  maszynowo czytelnych, nie tabelki.
- *Publikowanie kontraktu do Secret Managera.* Kontrakt nie jest sekretem; jest publiczną-wewnętrznie listą
  interfejsów, a Secret Manager dokłada rotację i limity, których nie potrzebuje.
- *Tylko asset release'u, bez bucketa.* Kusi jako uproszczenie („skoro dywizje i tak czytają z GitHuba"), ale
  odcina konsumenta, który GitHuba nie ma: job w GCP, skrypt operacyjny, hurtownia. Kopia w buckecie nic nie
  kosztuje, dopóki obie powstają z jednego kroku.
- *Osobny workflow publikujący asset po apply.* Wygląda na czystszy podział odpowiedzialności, a jest dokładnie
  tym trybem awarii, którego unikamy: drugi wyzwalacz, drugi odczyt stanu i cicha rozbieżność dwóch kopii,
  której konsument nie ma jak zauważyć.

---

## DEC-9 — Rozjazd ze starterem wykrywa bramka porównująca WSKAŹNIK, nie drzewo

**Problem.** Repozytorium perimetru to rozpakowany starter plus wartości środowiska. Defekty znajdują się przy
pomiarach na żywej organizacji, poprawki idą do startera — bo tam jest ich miejsce — a produkcja zostaje w tyle
do następnego ręcznego przeniesienia. Przy jednym operatorze to koszt; przy zespole to gwarancja, że granica
chodzi na innym kodzie niż źródło.

To nie jest hipoteza. W jednym dniu wystąpiły **dwa** rozjazdy i oba dotyczyły tego samego pliku, który jest
DOWODEM dla bramki promocji:

| Rozjazd | Co robiła wersja na produkcji |
|---|---|
| przypisanie naruszeń | `0 z 26` naruszeń przypisanych do członka → raport „czysto" |
| zakres odczytu logów | `0` wpisów na zakresie organizacji przy `30` w projekcie członka → raport „czysto" |

W obu przypadkach `promotion_gate` przechodził, a promocja do `enforced` opierałaby się na dowodzie, o którym
dziś wiadomo, że kłamał. Wniosek: opóźnienie synchronizacji nie jest długiem estetycznym — jest zieloną bramką
zbudowaną na przestarzałym narzędziu.

**Decyzja.** Bramka `starter-drift` w repozytorium perimetru porównuje **commit startera zapisany w
`.starter-sync`** z `main` startera i wypisuje listę commitów pomiędzy. Harmonogram tygodniowy (poniedziałek,
przed PR-ami promocyjnymi) + `workflow_dispatch`. Rozjazd = czerwony workflow **i** Issue aktualizowane
w miejscu. Runbook promocji ma to jako **krok 0**, przed uruchomieniem raportu.

**Dlaczego wskaźnik, a nie porównanie drzewa z wyjściem `install.sh`.** Repo perimetru **legalnie** różni się od
szablonu: numer organizacji, polityka dostępu, buckety, konta, projekty. Porównanie bajt w bajt świeciłoby na
czerwono zawsze i w ciągu tygodnia nauczyłoby wszystkich je ignorować — a bramka, którą się ignoruje, jest
gorsza niż jej brak, bo daje poczucie pokrycia. Wskaźnik jest jednoznaczny: albo commit się zgadza, albo nie,
i od razu widać, CO trzeba przenieść.

**Dlaczego to nie blokuje każdego pull requesta.** PR o access level nie ma nic wspólnego z tym, że starter
poszedł do przodu; oblewanie go byłoby szumem, a szum to sposób, w jaki bramki umierają. Blokowana jest
**jedna** operacja — promocja do `enforced` — bo to jest ta, której dowód jest nic niewart, gdy narzędzia
produkujące dowód są przestarzałe.

**Dlaczego bramka mieszka w repozytorium perimetru, a nie w starterze.** Starter jest publiczny, perimetr
prywatny. Bramka po stronie startera musiałaby dostać poświadczenia do prywatnego repo — czyli repozytorium
publiczne trzymałoby klucz do prywatnego, żeby powiedzieć mu o zaległym merge'u. Odwrotny kierunek nie wymaga
ani jednego sekretu: publiczny starter czyta się anonimowo.

**Odrzucone.**
- *Automatyczne otwieranie PR-a z poprawkami.* Synchronizacja jest **trójstronnym merge'em** z drzewem repo jako
  „ours", z ręcznym rozstrzygnięciem konfliktów tam, gdzie ta sama poprawka weszła niezależnie po obu stronach.
  Bot generujący „sync PR" ślepym nadpisaniem skasowałby wartości środowiska — czyli zamienił problem
  „przestarzała bramka" na problem „granica wskazuje cudzą organizację".
- *Świadome przyjęcie, że sync jest ręczny, i sam zapis prerekwizytu w runbooku.* Prerekwizyt w runbooku został
  (krok 0), ale sam z siebie nie wystarcza: nie ma sygnału, dopóki ktoś nie przeczyta runbooka, a oba rozjazdy
  z tego dnia wykryto przypadkiem, przy pomiarze czegoś innego. Zapisany wymóg bez sygnału to założenie.
- *Codzienny harmonogram.* Starter zmienia się seriami po kilka poprawek; codzienne przypomnienie o tym samym
  rozjeździe to szum. Tydzień + `workflow_dispatch` przed promocją pokrywa realny rytm.

---

## DEC-10 — Baseline to JEDNA reguła z listą zasobów; reguły profilowe zostają per członek

**Problem.** Perimetr ma limit **6000 atrybutów na konfigurację**, liczony osobno dla `spec` (dry-run)
i `status` (egzekwowana). Atrybutem jest każda tożsamość, każde źródło, każdy zasób w `ingress_to.resources`,
każda nazwa usługi i każdy selektor metody. Renderer początkowo produkował regułę baseline **dla każdego
członka osobno**, więc cała treść reguły — tożsamości, źródło, usługi, metody — powielała się tyle razy, ilu
było członków, choć różniła się wyłącznie jedną pozycją: numerem projektu.

Policzone niezależnie z odpowiedzi `servicePerimeters.get` na żywej organizacji (dwie reguły baseline:
skaner i pipeline raportu naruszeń):

```
security-scanner-read     = 1 tożsamość + 1 źródło + 1 zasób + 4 usługi +  9 metod = 16
platform-violations-read  = 1 tożsamość + 1 źródło + 1 zasób + 1 usługa  +  1 metoda =  5
                                                                 razem  = 21 NA CZŁONKA
6000 / (21 + koszt reguł profilowych) → sufit ~230 członków
```

Organizacja o kilkuset projektach przekracza ten próg **w trakcie wdrożenia**, nie po nim — a objaw jest
paskudny: apply pada na `Error 400` przy dodawaniu kolejnego członka, czyli po review i po tym, jak dywizja
usłyszała „zrobione". Limit dotyczy KONFIGURACJI, więc nie da się go obejść dzieleniem PR-ów.

**Decyzja.** `baseline_ingress` renderuje się jako **jedna reguła na tytuł**, klucz i tytuł `baseline--<tytuł>`,
a przynależność członka wyraża **jedna pozycja w `ingress_to.resources`**. Konfiguracja egzekwowana dostaje
ten sam kształt z listą zawężoną do członków `stage: enforced`. Koszt spada z `treść_reguły × członkowie`
na `treść_reguły + członkowie`:

```
przed:  21 × N          500 członków → 10 500 atrybutów  (konfiguracja NIE POWSTAJE)
po:     19 + 2 × N      500 członków →  1 019 atrybutów  (~6× zapasu do limitu)
```

**Reguły profilowe zostają per członek — świadomie, nie z zaniedbania.** Kolaps ma sens tylko tam, gdzie
treść jest wspólna Z DEFINICJI. Baseline taki jest: to maszyneria perimetru (skaner, raport naruszeń), ta
sama dla każdego. Profile są odwrotnością — różnią się tożsamościami wołającego, access levelami i metodami,
bo różnią się zespoły. Zbicie ich w jedną regułę wymagałoby albo sumowania tożsamości (reguła autoryzowałaby
konto jednej dywizji na projekcie drugiej — cicha eskalacja uprawnień), albo grupowania po identycznym
kształcie (klucz zależny od treści, czyli przetasowanie cudzych zasobów przy każdej zmianie parametru).

**Cena, którą płacimy.** Jedna reguła = **jeden blast-radius**: zła zmiana baseline'u dotyka wszystkich
członków naraz, a nie jednego. Poprzedni kształt dawał też audytowalność „kto ma co" wprost w nazwie zasobu.
Bilans: budżet atrybutów jest limitem **twardym** (API odmawia), a audytowalność ma tańsze zamienniki —
`ingress_to.resources` nadal wymienia każdego członka po numerze, a `terraform plan` pokazuje dopisanie
projektu do listy równie czytelnie jak powstanie nowej reguły. Wymóg wynikający z tej ceny: zmiana
`baseline_ingress` jest zmianą dotykającą wszystkich i tak ma być recenzowana (CODEOWNERS security).

**Migracja istniejącego wdrożenia NIE JEST refaktorem adresu — zmierzone.** Naturalny odruch to bloki
`moved{}` (zmiana kształtu renderowania zmienia adresy w stanie). Tutaj **nie pomagają i plan jest z nimi
identyczny**: w providerze `hashicorp/google` (zmierzone na 7.43) `title` ORAZ `ingress_to.resources`
w `google_access_context_manager_service_perimeter[_dry_run]_ingress_policy` są **ForceNew**, więc
przeniesiony zasób i tak jest zastępowany (`# forces replacement`). Do tego `moved` jest z definicji 1:1,
a kolaps jest N→1. Wniosek: plan **zawsze** pokaże `N to add, N×M to destroy` i nie jest to błąd konfiguracji.
Bezpieczeństwo migracji zapewnia **kolejność, nie plan**:

1. `terraform apply -target='...ingress_policy.rule["baseline--<tytuł>"]'` dla każdej reguły zbiorczej —
   krok czysto **addytywny** (`N to add, 0 to destroy`). Od tej chwili baseline jest w konfiguracji DWA razy:
   zbiorczo i po staremu. Autoryzacja jest nadzbiorem, więc nie ma okna bez pokrycia.
2. Pełny apply — usuwa reguły per-członkowe, których treść już niesie reguła zbiorcza.

Kroku 1 nie da się pominąć „bo to tylko sekunda": reguły ACM to osobne obiekty w tej samej liście, a Terraform
nie porządkuje usunięcia jednego względem powstania drugiego. Przy pojedynczym apply istnieje moment, w którym
członek nie ma reguły baseline — czyli dokładnie ta awaria, po którą baseline istnieje. Dla wdrożenia, które
jeszcze nikogo nie promowało, prościej jest zrobić kolaps **przed pierwszą promocją**: w konfiguracji
egzekwowanej nie ma wtedy żadnej reguły baseline, a dry-run niczego nie blokuje. Migrację warto uruchomić
z `-parallelism=1`: każda reguła to osobny PATCH na tym samym obiekcie org-level, chroniony eTagiem.

**Odrzucone.**
- *Zostawić kształt per członek i podnieść limit.* Limit 6000 nie jest kwotą do podniesienia w konsoli —
  to ograniczenie konfiguracji perimetru.
- *Drugi perimetr po przekroczeniu progu.* Dzielenie organizacji na perimetry jest decyzją o modelu ochrony
  (co z czym może rozmawiać), a nie sposobem na budżet. Podejmowana pod presją zapchanego licznika daje
  granice przebiegające tam, gdzie skończyło się miejsce. Kryterium rewizji z DEC-1 zostaje — tylko przestaje
  być wymuszane arytmetyką renderera.
- *Kolaps także reguł profilowych.* Patrz wyżej: sumowanie tożsamości między dywizjami to cicha eskalacja
  uprawnień, a klucz zależny od treści przetasowuje cudze zasoby.
- *Grupowanie baseline'u po access levelu / etapie zamiast po tytule.* Dawałoby regułę, której skład zmienia
  się przy promocji dowolnego członka — czyli replace reguły wspólnej w najgorszym możliwym momencie.
  Rozdział dry-run/enforced na dwa warianty tej samej reguły trzyma tę zmienność w liście zasobów.

> **CIĄG DALSZY W DEC-11.** Ostatni akapit powyżej opisuje problem, którego ta decyzja **nie rozwiązała do
> końca**: lista zasobów została w regule, a `ingress_to.resources` jest `ForceNew`, więc replace reguły
> wspólnej wracał przy **każdym** wniosku. Liczby „19 + 2 × N" i „2 atrybuty na członka" są więc historyczne —
> aktualny kształt (`resources = ["*"]`, koszt baseline stały) opisuje DEC-11.

---

## DEC-11 — Reguła baseline celuje w `*`, a nie w listę członków

**Problem — defekt, który powstał razem z DEC-10.** Kolaps zdjął powielanie CAŁEJ reguły baseline na każdego
członka, ale zostawił w niej listę, która nadal rośnie z każdym wnioskiem: `ingress_to.resources`. To pole jest
w providerze `hashicorp/google` (zmierzone na 7.43.0) **`ForceNew`**, więc dopisanie jednej pozycji nie jest
aktualizacją reguły, tylko jej **zastąpieniem**. Zmierzone — stan żywy trzech członków plus jeden nowy członek
w konfiguracji, `terraform plan -refresh=false`:

```
# …dry_run_ingress_policy.rule["baseline--platform-violations-read"] must be replaced
      ~ resources = [ # forces replacement
# …dry_run_ingress_policy.rule["baseline--security-scanner-read"]    must be replaced
      ~ resources = [ # forces replacement
Plan: 4 to add, 1 to change, 2 to destroy.
```

W konfiguracji **dry-run** replace jest nieszkodliwy: ta konfiguracja niczego nie autoryzuje. Znaczenie ma
**konfiguracja egzekwowana**. Terraform kasuje przed utworzeniem, więc każda promocja (i każdy wniosek po
pierwszej promocji, bo zmienia listę obu wariantów reguły) otwierała okno, w którym **żaden** promowany członek
nie ma reguły skanera ani reguły raportu naruszeń. To jest dokładnie ta awaria, po którą baseline istnieje —
z tą różnicą, że **powtarzalna przy każdym wniosku**, a nie jednorazowa jak sama migracja z DEC-10. Przy
50 wnioskach miesięcznie to ~50 okien miesięcznie na całej granicy.

**Decyzja.** `ingress_to.resources = ["*"]` w obu wariantach reguły baseline (`baseline_rules_all`,
`baseline_rules_enforced`). Dokumentacja VPC-SC (ingress-egress-rules) opisuje to pole wprost: `*` dopasowuje
**wszystkie zasoby wewnątrz perimetru**, a `spec` i `status` to dwie osobne konfiguracje perimetru, każda
z własną listą `resources`. Reguła zbiorcza w `spec` obejmuje więc członków dry-run, ta sama reguła
w `status` — wyłącznie promowanych. To jest ta sama granica, którą do tej pory wypisywaliśmy ręcznie —
z tą różnicą, że **reguła przestaje zależeć od członkostwa, więc nie ma czego replace'ować**.

**Co się przy tym poszerza — dokładnie jedna rzecz.** Lista wypisana ręcznie obejmowała projekty
**zadeklarowane w tym repo**; `*` obejmuje zasoby, które **w perimetrze są**. Przy `manage_skeleton: false`
(brownfield, domyślnie) właścicielem szkieletu jest ktoś inny i może dołożyć zasób poza tym repo — `*` obejmie
go automatycznie. Świadomie: baseline to skaner i raport naruszeń, więc „zasób w perimetrze, którego nie
skanujemy" jest gorszym stanem niż „skanujemy też cudzy wpis". Poszerzenie idzie **wyłącznie po stronie celu**;
tożsamości i operacje zostają bez zmian, więc reguła wpuszcza dokładnie te same konta na dokładnie te same
metody. Przy wdrożeniu, w którym to repo jest jedynym pisarzem, zbiór autoryzacji jest **identyczny** —
sprawdzalne przez rozłożenie obu stron na krotki `(tożsamość, źródło, usługa, metoda, projekt)`.

**Zysk poboczny, policzony.** Koszt baseline spada ze „stały + 1 na regułę na członka" do **stałego**:
`(15 + 1) + (4 + 1) = 21` atrybutów, czyli **0 na członka**. Sufit rośnie z ~521 do **~629** członków przy
realistycznej mieszance profili i z 854 do **~1195** przy monoprofilu; próg ostrzegawczy 70 % przesuwa się
z ~365 na **~439** członków.

**Bramka OPA rozróżnia baseline od reguły profilowej PO TREŚCI, nie po nazwie.** `resources = ["*"]` w regule
dywizji zostaje zakazane bezwarunkowo — znaczyłoby „reguła napisana dla jednego zespołu działa na projektach
wszystkich". Wyjątek dostaje wyłącznie reguła, dla której istnieje w `perimeter/policy.yaml` (plik pod
CODEOWNERS security) deklaracja o tym samym tytule, tych samych tożsamościach, tych samych usługach i tych
samych selektorach — **i która ma źródło**. Historia tej bramki jest historią coraz słabszych nazw: najpierw
podciąg `--baseline--` (obchodzony profilem o tytule `-baseline--…`), potem dokładny tytuł z `policy.yaml`
(obchodzalny plikiem członka nazwanym `baseline.yaml`, bo klucz członka bierze się z nazwy pliku). Zgodność
co do treści tej furtki nie ma: reguła, która ją spełnia, **jest** baselinem i nie daje autorowi niczego ponad
to, co daje baseline. Brak `--data perimeter/policy.yaml` = brak deklaracji = **każda** gwiazdka odrzucona.

**Egress zostaje bez zmian i to nie jest przeoczenie.** `egress_to.resources` jest `ForceNew` tak samo
(zmierzone), ale reguły egress **nie są skolapsowane** — klucz to `(członek × profil × tytuł)`, więc nowy
członek dokłada własną regułę i nie dotyka cudzych; replace zdarza się wyłącznie w regule, którą dany wniosek
zmienia. Gdyby ktoś kiedyś skolapsował egress „dla budżetu", defekt wróci — a poprawka z ingressu **nie będzie
dostępna**: `egress_to.resources = ["*"]` nie znaczy „dowolny zasób w perimetrze", tylko „dowolny zasób **poza**
nim", czyli zniesienie granicy w kierunku, dla którego ta granica istnieje. Bramka OPA odrzuca ten kształt
bezwarunkowo i ma tak zostać.

**Migracja.** Sama poprawka też jest zmianą pola `ForceNew`, więc robi replace — **raz**. Przy pustej
konfiguracji egzekwowanej (typowy stan przed pierwszą promocją) dotyka wyłącznie dry-run, czyli niczego nie
blokuje. Przy niepustej obowiązuje kolejność z DEC-10: najpierw krok addytywny na regułach zbiorczych
(`-target`, `-parallelism=1`), potem pełny apply.

**Odrzucone.**
- *`create_before_destroy` na regułach baseline.* Nie jest to opcja techniczna, tylko pozorna: **wszystkie
  granularne reguły mają w stanie ten sam `id`** — sam perimetr (`accessPolicies/<n>/servicePerimeters/<nazwa>`),
  bo provider realizuje je jako read-modify-write na jednej liście `ingressPolicies`. „Nowy obok starego" znaczy
  więc dwie reguły o tym samym tytule w jednej liście, a następujące po nich usunięcie dopasowuje się do jednej
  z nich. Zamiana pewnego, krótkiego okna na niepewny stan obiektu org-plane — i to bez zdjęcia kosztu
  atrybutów, bo lista nadal rosłaby z każdym członkiem.
- *Powrót do reguł baseline per członek.* Cofa cały zysk DEC-10 (21 atrybutów na członka, sufit ~230)
  i **nie usuwa problemu**: promocja nadal zmieniałaby zbiór reguł egzekwowanych, tylko po jednej na członka.
- *Dwie reguły baseline zamieniane naprzemiennie (`baseline-a` / `baseline-b`).* Utrzymuje ciągłość pokrycia
  kosztem podwojenia liczby reguł baseline w konfiguracji, wprowadza stan („która jest teraz aktywna"), którego
  Git nie widzi, a przy równoległych wnioskach wymaga zamka poza Terraformem. Rozwiązuje objaw (okno) i zostawia
  przyczynę (cel reguły zależny od członkostwa).
- *`lifecycle { ignore_changes = [ingress_to] }`.* Zatrzymałoby replace i zarazem zatrzymało aktualizacje —
  nowy członek nigdy nie trafiłby do reguły baseline, a plan meldowałby zielono. Cichy brak pokrycia jest gorszy
  niż głośne okno.
- *Podniesienie limitu 6000.* Nie dotyczy problemu (replace nie ma nic wspólnego z budżetem) i nie jest kwotą
  do podniesienia w konsoli.

---

## DEC-12 — Członkostwo w JEDNYM `perimeter/projects.yaml`, jako lista, z bramką duplikatu i rebase-retry

**Decyzja.** Członkowie perimetru mieszkają w jednym pliku `perimeter/projects.yaml`, pod kluczem `members`,
jako **lista** wpisów. Renderer kluczuje członka po TREŚCI — `"${division}-${project_id}"` — czyli dokładnie
tym samym ciągiem, którym wcześniej była nazwa pliku. Kanał wejściowy **dopisuje wpis na końcu** listy zamiast
tworzyć plik. Układ jednoplikowy wchodzi **razem** z bramką duplikatu (cztery warstwy, fail-closed)
i rebase-retry w bocie (`.github/workflows/intake-rebase.yml`). **`merge=union` NIE wchodzi** — pomiar
niżej pokazał, że gubi wpisy; gdyby kiedyś wszedł, wolno mu wyłącznie razem z kompletem bramki, nigdy samemu.

**To jest ODWRÓCENIE wcześniejszej decyzji** (plik na projekt) i odwrócenie oparte na pomiarze, który nadal
jest prawdziwy — patrz `docs/6-uklad-repozytoriow.md` i `experiments/konflikty-ukladow/`. Powód nie jest taki,
że tamten pomiar był zły, tylko że jego koszt dało się **domknąć**, a koszty układu wieloplikowego rosły
z każdym członkiem.

**Dlaczego jeden plik.** Trzy rzeczy, z których żadnej plik-na-projekt nie dawał:
* „Kto jest w perimetrze" jest pytaniem o PLIK, nie o katalog. Każdy wniosek jest diffem na tle pozostałych
  wpisów, a nie nowym plikiem, do którego review nie ma czego przyłożyć.
* Duplikat projektu przestał być łapany wyłącznie regułą porównującą pliki. Najgroźniejszy przypadek —
  **powtórne zgłoszenie tego samego projektu** — nie był dla tamtej reguły widoczny, bo tam plik był jeden
  i ten sam; bronił przed nim `out.exists()`, czyli warunek o systemie plików, nie o członkostwie.
* Sharding po dywizji, gdyby kiedyś był potrzebny, i tak wymagał zmiany renderera i przeadresowania zasobów
  w stanie. Płaski katalog nie był etapem w drodze do niego — miał ten sam koszt wyjścia co układ jednoplikowy.

**Dlaczego LISTA, a nie mapa `klucz → wpis`.** Zmierzone, nie wybrane: **duplikat klucza mapy jest CICHY**.
`yamldecode` Terraforma 1.15.5 bierze ostatni wpis i nie mówi nic; `yaml.safe_load` zachowuje się identycznie.
Przy pliku wspólnym duplikat nie jest egzotyką, tylko normalnym wynikiem scalenia — a „cicho wygrywa ostatni"
znaczy tu: promocja do `enforced` po cichu cofnięta do `dry-run`, czyli projekt bez ochrony przy zielonym
planie. W liście ten sam przypadek jest twardym błędem, zanim powstanie jakikolwiek zasób:
`Error: Duplicate object key — Two different items produced the key "div-aaa" in this 'for' expression`.

**Dlaczego klucz z treści, a nie nowe pole `key:`.** Klucz `for_each` JEST adresem zasobu w stanie Terraforma,
a granularne reguły ACM nie mają w wariancie dry-run aktualizacji w miejscu (DEC-11) — przeadresowanie to
`destroy` + `create` na żywej granicy. Wyliczenie klucza z `division` i `project_id` odtwarza dawną nazwę pliku
1:1, więc **migracja nie miała w planie ani jednego `destroy`**. Osobne pole `key:` byłoby drugim źródłem
prawdy do zsynchronizowania i polem, którym wnioskodawca mógłby wskazać cudzy adres.

**Dlaczego wpis dopisujemy NA KOŃCU, a nie w miejscu z sortowania.** Posortowana lista kładzie wpisy jednej
dywizji obok siebie, a dywizje onboardują się falami — to jest dokładnie układ, który w eksperymencie dał
1/10 scaleń bez konfliktu. Kolejność w pliku nic nie znaczy, bo klucz pochodzi z treści.

**Dlaczego postać kanoniczna pliku jest BRAMKĄ.** Plik zapisuje wyłącznie `tools/projects_file.py`, więc
`dump(load(x)) == x`, a `validate.yml` to sprawdza. Bez tego przepisanie pliku przez sweeper albo break-glass
dawałoby diff na 200 wpisów i chowało prawdziwą zmianę w szumie — akurat w commicie awaryjnym. Cena zapisana
wprost: **w tym pliku nie ma komentarzy**, bo `yaml.safe_dump` ich nie zna i pierwszy zapis bota skasowałby je
bez śladu. Uzasadnienia mieszkają w `change_ref` i w opisie pull requesta.

**Niezmiennik, który musiał przetrwać zmianę układu.** Kanał wejściowy nie nadpisuje istniejącego członka.
Przy pliku na projekt realizował to `out.exists()`; przy pliku wspólnym „plik istnieje" jest prawdą zawsze,
więc warunek pyta teraz o WPIS — po `project_id` **oraz** po `project_number`, bo literówka w dywizji daje
inny klucz przy tym samym projekcie. Bez tego powtórne zgłoszenie zapisałoby `stage: dry-run` członkowi, który
jest `enforced`: projekt traci ochronę pull requestem wyglądającym na onboarding, przechodzącym wszystkie
bramki i kwalifikującym się do auto-merge'a.

**Odrzucone.**
- *Mapa `klucz → wpis` w YAML-u.* Czytelniejsza i z kluczem zapisanym wprost, ale duplikat klucza jest w niej
  cichy w OBU parserach, których używamy (zmierzone). Wybór między mapą a listą jest wyborem między cichą
  wygraną ostatniego a zatrzymaniem planu — nie stylem.
- *Jeden plik bez rebase-retry.* Wiersz „1/10" z eksperymentu opisuje przypadek normalny, nie skrajny.
  Bez bota dziewięć z dziesięciu wniosków tej samej dywizji trafia do człowieka.
- *`merge=union` na pliku członków — ODRZUCONE POMIAREM, nie z ostrożności.* Miało załatwić kolizje przy
  dopisywaniu („weź oba wnioski"). Zmierzone 2026-08-11 na tym samym wejściu, na którym bot daje 10/10:
  **10/10 zielonych scaleń i 201 wpisów zamiast 210.** Union scala LINIE, nie YAML, a wpisy członków mają
  identyczną strukturę — dziesięć bloków zlepia się w jeden wpis z dziesięcioma polami `project_id`;
  dziewięć zatwierdzonych projektów nie trafia do perimetru i nikt nie dostaje błędu. Przy EDYCJI (promocja
  + zmiana właściciela) oba scalenia przechodzą, a we wpisie zostają podwojone `stage` i `owner_group` —
  `yaml.safe_load` czyta to bez błędu i bierze ostatnie, czyli zatwierdzona promocja wraca do `dry-run`
  po merge'u, który przeszedł review i CI. Union nie kupuje więc nic: konflikt WIDOCZNY zamienia na plik,
  który bramka duplikatu i tak odrzuci — tyle że po scaleniu. Bez bramki byłaby to cicha utrata. Warunek
  na przyszłość (pilnowany przez selftest): włączenie union wymaga kompletu czterech warstw bramki.
- *`git rebase` w bocie zamiast ponowienia intencji.* Rebase odtwarza PATCH, a patch dopisujący linie na końcu
  pliku, do którego ktoś inny też dopisał, to dokładnie ten konflikt, który mamy usunąć. Wpis jest DANYMI —
  ponowienie polega na usiądnięciu na nowym `main` i dopisaniu go jeszcze raz.
- *Sharding katalogowy `perimeter/projects/<dywizja>.yaml` od razu.* Rozwiązuje konflikty i CODEOWNERS per
  dywizja, ale wymaga renderera na `**/*.yaml` i klucza z podmianą separatora — czyli innego adresu w stanie
  niż dziś, więc `moved{}` dla WSZYSTKICH członków w tym samym kroku co zmiana źródła. Zostaje jako zapisane
  wyjście, gdy self-service per dywizja stanie się wymaganiem; wtedy własnym pull requestem.
- *`uniqueItems: true` w JSON Schema zamiast reguł OPA.* Porównuje CAŁE elementy, więc dwa wpisy o tym samym
  projekcie i różnym właścicielu przechodzą — czyli dokładnie ten duplikat, który boli.

---

## DEC-13 — Alert na WIEK niezastosowanej zmiany, nie na nieudany przebieg; obserwator z własną tożsamością

**Decyzja.** Cztery objawy zepsutej granicy (`apply` nie doszedł · budżet atrybutów · dryf · członek po
terminie) mają alerty w Cloud Monitoring, karmione metrykami z workflowa `watch.yml` (co godzinę,
`tools/perimeter_watch.py`). Alert o `apply` jest **dead-man's-switchem na WIEKU niezastosowanej zmiany**,
a nie nasłuchem zdarzenia „workflow failed", i ma drugi warunek na **BRAK danych**. Progi, kanały i baza
URL runbooka mieszkają w **osobnym pliku** `perimeter/alerting.yaml`. Publikacja metryk idzie **trzecią
tożsamością** `sa-vpcsc-watch`, z jednym uprawnieniem (`monitoring.timeSeries.create`).

**Dlaczego alert o wieku, a nie o nieudanym przebiegu.** Tryby awarii `apply` są trzy i tylko pierwszy
generuje zdarzenie: (a) przebieg **padł** — jest `conclusion: failure`; (b) przebieg **się nie odpalił** —
zły filtr `paths`, wyłączone Actions, brak minut, awaria GitHuba: nie ma ŻADNEGO zdarzenia, więc nasłuch
nie ma czego usłyszeć; (c) przebieg **wisi** — zdarzenia nie będzie przez 6 godzin (limit joba), a przy
environment z wymaganym recenzentem przez 30 dni. Wszystkie trzy dają jeden objaw: minął czas, a zmiana
z gałęzi domyślnej nie jest w chmurze. Reguła o wieku pokrywa więc trzy tryby jedną liczbą, a udany apply
zeruje ją bez żadnego dodatkowego kroku. Czwarty tryb — **zepsuł się sam obserwator** — domyka warunek
`condition_absent` w tej samej polityce: bez niego martwy `watch.yml` daje wykres zamrożony na ostatniej
dobrej wartości, czyli ciszę nie do odróżnienia od zdrowia.

**Dlaczego osobny plik konfiguracji.** `policy.yaml` odpowiada na pytanie CO GRANICA PRZEPUSZCZA: zmienia
się przy każdym wniosku dywizji i recenzuje go właściciel granicy. `alerting.yaml` odpowiada na pytanie
KOGO BOLI, GDY MASZYNERIA PADNIE: zmienia się przy zmianie dyżuru i recenzuje go SRE. Trzymanie ich razem
znaczy, że zmiana adresu e-mail wpada w tę samą ścieżkę review co dopuszczenie projektu do granicy —
i odwrotnie, że każdy wniosek dywizji konfliktuje z każdą zmianą dyżuru na tym samym pliku.

**Dlaczego trzecia tożsamość.** Publikacja metryki jest ZAPISEM, a konto `plan` nie może mieć ani jednego
uprawnienia zapisującego — to niezmiennik całego stacku (DEC-2). Konto `plan` może impersonować **każdy
pull request**; gdyby dostało `timeSeries.create`, autor dowolnego PR-a opublikowałby „budżet 5%, zaległość
apply 0" i uciszył cztery alerty naraz, nie dotykając ani granicy, ani gałęzi domyślnej. `sa-vpcsc-watch`
jest za to związane refem `refs/heads/<gałąź domyślna>`, czyli **węziej** niż `plan`, mimo że robi mniej.

**Dlaczego budżet liczymy z ŻYWEJ granicy, a nie z deklaracji.** `tools/attribute_budget.py` liczy koszt
z plików YAML i modeluje renderer. Na pull requeście to jest właściwe źródło — pytanie brzmi „czy ZMIANA,
którą proponuję, się zmieści", a zmiany w chmurze jeszcze nie ma. Jako źródło ALERTU ta sama liczba jest
strukturalnie ślepa na wszystko, co jest w granicy, a czego nie ma w deklaracji: zdublowane reguły po
nieudanym odzysku stanu, ręczne dopiski w konsoli, dryf. Alert zbudowany na deklaracji milczałby więc
dokładnie w tym scenariuszu, w którym sufit zostaje przekroczony bez niczyjej wiedzy — czyli w jedynym,
który boli. Obserwator czyta `servicePerimeters.get` i liczy atrybuty na obiekcie z API; deklaracja zostaje
jako KONTROLA (rozjazd obu liczb ląduje w podsumowaniu przebiegu i jest tym samym objawem, o którym mówi
alert o dryfie). Ten sam wybór rozstrzyga wymiar predykcyjny: nachylenie liczone z deklaracji pokazywałoby
tempo naszych pull requestów, a nie tempo rośnięcia granicy. Zmierzone przy wdrożeniu: oba modele dają dziś
tę samą liczbę (`spec` 48, `status` 0), więc zmiana źródła zmienia ZNACZENIE metryki, a nie jej wartość —
i właśnie dlatego trzeba ją było zrobić od razu, a nie „gdy liczby się rozjadą".

**Korekta z 2026-08-12: rozjazd obu liczb NIE jest „tym samym objawem, o którym mówi alert o dryfie".**
Tak brzmiało zdanie wyżej i było błędem — nie w mechanizmie, tylko w tym, co ta kontrola mówi człowiekowi.
Rozjazd ma dwie przyczyny i dwie procedury, a przy tej częstszej **oba** alerty, do których odsyłał,
milczą z definicji: gdy `apply` zalega, `dryf_z_planu` zwraca 0 celowo (dyskryminator „zmiana spoza Gita
vs opóźnienie propagacji"), a alert o wieku `apply` czeka do progu `apply_pending_seconds`. Przez pierwszą
godzinę po merge'u ta adnotacja jest więc **jedynym** sygnałem, a odsyłacz prowadził do dwóch kontroli
z czystą tablicą — czyli uczył dyżurnego, że to fałszywy alarm. Zmierzone na żywym wdrożeniu (przebiegi
`watch` `31565377821` i `31565606010`): „granica ma 48 atrybutów, deklaracja opisuje 53" przy
`drift_resources = 0` i `apply_pending_seconds = 72`; przyczyną był `apply`, który padł na numerze
projektu nieistniejącego w organizacji. Kontrola zadziałała — zawiodło jej zdanie. Od tej poprawki
`komunikat_rozjazdu()` rozróżnia prefiksem treści: **ROZJAZD OCZEKIWANY** (apply zalega) → „idź do
historii przebiegów `apply`, nie do granicy"; **ROZJAZD NIEOCZEKIWANY** (apply nie zalega) → „zmiana poza
pipeline'em albo rozjazd arytmetyki modeli — rozstrzyga porównanie regułą po regule". Oba jako
`::warning::`: adnotacja poziomu error mogłaby (niezmierzone) sczerwienić `measure`, a wtedy `publish`
nie rusza przez `needs` i obserwator milknie w stanie, w którym ma krzyczeć — wagę niesie prefiks. To jest ta sama klasa defektu, którą DEC-13
naprawiał u siebie (puste `notificationChannels`): kontrola obecna, celująca w pustkę, brana za spokój.

**Gdy żywej granicy nie da się odczytać, metryka budżetu NIE POWSTAJE.** Podstawienie liczby z deklaracji
dałoby wartość, która wygląda poprawnie i opisuje co innego — dokładnie ten tryb awarii, który ten
mechanizm ma tropić. Brak punktu jest uczciwszy niż zły punkt.

**Dlaczego dwa kanały.** Alert pojemnościowy czyta się w godzinach pracy; alert o zmianie granicy poza
Gitem jest sygnałem obejścia procesu. Jeden kanał na oba kończy się wyuczoną obojętnością: dziewięć na
dziesięć wiadomości nie wymaga reakcji, więc dziesiąta też jej nie dostanie.

**Gdzie te alerty żyją i co je zabije.** Stoją w projekcie monitoringu, obok stanu Terraforma. Alerty
z audit-logów (`monitoring.tf`) przeżyją zamknięcie tego projektu w granicy egzekwowanej, bo logi powstają
po stronie Google. Alerty z metryk (`alerts.tf`) — nie: zapis idzie z GitHuba, czyli spoza granicy. Trzy
z nich zamilkną, a czwarty (`apply`) ODPALI warunkiem o braku danych, i będzie to prawda, bo w tym samym
momencie apply też nie zadziała (stan leży w tym samym projekcie). **Ryzyko szczątkowe nazwane wprost:**
skasowanie projektu monitoringu albo wyłączenie mu billingu nie odpala niczego. Zamknięcie tej luki wymaga
obserwatora poza organizacją — i jest przedmiotem osobnej decyzji, **DEC-14**.

**Odrzucone.**
- *Nasłuch na `workflow_run` z `conclusion: failure` (GitHub → webhook → alert).* Najprostsze i najczęściej
  spotykane, łapie **jeden z trzech** trybów awarii. Przebieg, który się nie odpalił, nie generuje zdarzenia
  — a to właśnie ten tryb sprawia, że granica psuje się najciszej.
- *Znacznik czasu ostatniego udanego apply w obiekcie GCS.* Kusi, bo daje dead-man's-switch bez GitHub API.
  Wymaga jednak własnego prefiksu i własnych grantów (zapis dla `apply`, odczyt dla obserwatora), a przy
  grancie zbyt szerokim — na tym samym prefiksie co stan — **konto dostępne z pull requesta mogłoby
  podrobić znacznik**. Historia przebiegów w GitHub API daje tę samą odpowiedź bez nowego magazynu i bez
  nowego IAM. Gdy GitHub jest niedostępny, obserwator nie chodzi, więc odpala warunek o braku danych —
  degradacja idzie w stronę bezpieczną.
- *Plik historii budżetu w GCS pod regresję.* Cloud Monitoring trzyma metryki własne przez 6 tygodni, więc
  historia do prognozy już istnieje. Osobny magazyn byłby drugą kopią tych samych danych, z własnym IAM,
  własnym trybem awarii i własnym rozjazdem.
- *Jeden alert pojemnościowy zamiast pary WARNING/CRITICAL.* Polityka Cloud Monitoring ma jedną `severity`,
  a „zbliżamy się" i „w tym miesiącu uderzysz w limit" to dwie różne decyzje operacyjne. Sklejone w jedną
  politykę dają albo krzyk przy 70%, albo szept przy 25 dniach.
- *Sumowanie budżetu `spec` i `status` do jednej liczby.* Limit 6000 jest **na konfigurację**. Suma alarmuje
  przy dwóch zdrowych konfiguracjach, a maksimum ukrywa tę, która właśnie się zapycha — myli w obie strony.
- *Kadencja co 5 minut.* `terraform plan` na tej konfiguracji trwa ~40 s; 288 przebiegów na dobę to koszt
  minut Actions bez zysku, bo objawy, o których mowa, trwają godzinami. Kadencja jest za to ZWIĄZANA
  z `alignment_period` w politykach — okno krótsze od kadencji daje puste kubełki, w których żaden warunek
  nie utrzyma się przez wymagany czas.

## DEC-14 — Ostatnią warstwą obserwacji jest dead-man's-switch POZA tą organizacją, a jego poświadczenie mieszka w repozytorium perimetru

**Decyzja.** Job `publish` w `watch.yml` wysyła po udanej publikacji metryk jeden `GET` na URL checka
u zewnętrznego dostawcy dead-man's-switch. Dostawca alarmuje własnym kanałem, gdy sygnał ustanie. URL to
**sekret repozytorium** `DMS_PING_URL` — poziom repozytorium, nie environment — podawany **wyłącznie**
jobowi `publish`. Okno ciszy u dostawcy jest związane z `watchdog_absent_seconds` (period = kadencja
`watch.yml`, grace = 2× kadencja). Brak sekretu nie wywraca przebiegu, ale melduje się adnotacją
i wierszem w podsumowaniu. Bramka `heartbeat DMS we właściwym jobie` w `validate.yml` pilnuje konstrukcji.

**Dlaczego w ogóle piąta warstwa, skoro DEC-13 ma warunek na brak danych.** Bo warunek o BRAKU danych też
jest ewaluowany przez silnik, który stoi **w tym samym projekcie** co stan Terraform, pula WIF i buckety
kontraktów. Cztery polityki alertów odpowiadają na pytanie „czy maszyneria działa"; żadna nie odpowiada na
pytanie „czy projekt, w którym te pytania są zadawane, jeszcze istnieje". Skasowanie projektu albo
wyłączenie mu billingu nie odpala niczego — nie ma czego ewaluować. Zostaje cisza nieodróżnialna od
zdrowia, i to na granicy bezpieczeństwa: przez ten czas review, `git revert` i raport zgodności mówią
o konfiguracji, o której nikt nie wie, czy jest w chmurze. Obserwator, który umiera razem z obserwowanym,
nie jest obserwatorem — jest jego częścią.

**Dlaczego ping za publikacją, a nie na starcie joba.** Ma znaczyć „cały łańcuch żyje", nie „runner
wstał". Wysłany na końcu dowodzi po kolei: GitHub odpalił workflow → `measure` odczytał stan Terraform
z bucketa w projekcie monitoringu → dostawca tożsamości wydał token → `timeSeries.create` przeszedł.
Pęknięte którekolwiek ogniwo = brak pingu = obserwator odzywa się sam. Ping wysyłany wcześniej meldowałby
zdrowie martwej maszynerii, czyli robiłby dokładną odwrotność tego, po co warstwa istnieje.

**Dlaczego cisza jest jedynym sygnałem — bez pingu `/fail`.** Kolizja blokady stanu z trwającym `apply`
wywraca `measure` CELOWO i jest zdarzeniem znanym, tolerowanym i samonaprawialnym. Ping porażki alarmowałby
na nim natychmiast, czyli nauczyłby dyżurnego ignorować kanał, który ma odezwać się raz na nigdy. Ceną jest
związanie okna: musi tolerować dwa pominięte przebiegi, stąd grace = 2× kadencja i ta sama liczba co
`watchdog_absent_seconds`. Trzy liczby (cron, okno u dostawcy, próg w `alerting.yaml`) opisują JEDNĄ
decyzję i zmieniają się razem.

**Dlaczego sekret w repozytorium, a nie w magazynie sekretów w chmurze.** Konsumentem jest runner GitHuba.
Każde ogniwo pośrednie — magazyn w chmurze, klaster, pośrednik — dokłada rzecz, która może paść sama
z siebie i wyprodukować alarm o granicy wtedy, gdy granica ma się dobrze. Gorzej: magazyn **wewnątrz tej
samej organizacji** znika razem z projektem, czyli w dokładnie tym scenariuszu, dla którego warstwa
powstała. Poziom repozytorium, a nie environment, bo `watch` nie używa żadnego environment, a environment
z wymaganym recenzentem zatrzymałby heartbeat na review — dead-man's-switch czekający na zatwierdzenie
melduje śmierć, której nie ma.

**Dlaczego sekret NIE trafia do joba `measure`.** URL pingu jest poświadczeniem: kto go ma, ten potrafi
UCISZYĆ dead-man's-switch. `measure` chodzi na koncie `plan`, impersonowalnym z każdego pull requesta —
sekret podany tam pozwoliłby autorowi dowolnego PR-a podtrzymywać heartbeat przy martwej maszynerii. To ta
sama granica, dla której `watch.yml` w ogóle ma dwa joby (DEC-13), więc łamiąc ją tutaj, unieważnia się ją
i tam. Dlatego pilnuje jej bramka czytająca zparsowany YAML, a nie komentarz.

**Brak sekretu = degradacja bezpieczna, ale WIDOCZNA.** Przebieg nie pada — metryki są zapisane, cztery
alerty działają. Ale cicho nieuzbrojony dead-man's-switch to kontrola obecna w konfiguracji i nieosiągalna
w działaniu, czyli spokój wzięty z niczego. Stąd adnotacja i wiersz w podsumowaniu zamiast `echo` ginącego
w logu. Kolejność uzbrajania też jest samosprawdzająca: check założony PRZED wpięciem sekretu zaczyna
odliczać od razu, więc uzbrojenie porzucone w połowie zgłasza się samo.

**Odrzucone.**
- *Piąty alert w Cloud Monitoring — cokolwiek by mierzył.* Każda polityka w tym projekcie dzieli los
  projektu. Nie da się zbudować wewnątrz obiektu kontroli nad jego zniknięciem.
- *Alert w DRUGIM projekcie tej samej organizacji.* Tańszy i pozornie wystarczający, ale nie pokrywa
  scenariuszy organizacyjnych (zawieszone konto rozliczeniowe, wyłączony billing na poziomie konta,
  utrata dostępu do organizacji), a te są dokładnie tą klasą zdarzeń, której nie widać od środka.
- *Nasłuch po stronie dostawcy na „workflow failed" zamiast heartbeatu.* Ta sama wada co w DEC-13, tylko
  przeniesiona na zewnątrz: przebieg, który się nie odpalił, nie generuje zdarzenia. Heartbeat mierzy stan.
- *Ping `/start` i `/fail` obok pingu sukcesu.* Daje ładniejszy wykres czasu trwania i alarmuje szybciej —
  na zdarzeniach, które są tolerowane z założenia. Kanał, który odzywa się przy normalnej pracy, przestaje
  być kanałem ostatniej instancji.
- *Ping z joba `measure`, „bo i tak zawsze się wykonuje".* Właśnie dlatego nie: zawsze się wykonuje, więc
  meldowałby zdrowie także wtedy, gdy publikacja metryk pada. Plus sekret w jobie impersonowalnym z PR-a.
- *Heartbeat z osobnego workflowa na tym samym cronie.* Wysyłałby ping niezależnie od tego, czy `watch`
  cokolwiek zmierzył — czyli mierzyłby dostępność GitHub Actions, a nie żywotność maszynerii granicy.

---

---

## DEC-15 — `combining_function: OR` wymaga napisanego powodu; pusty warunek nie jest już doklejany

**Decyzja.** Access level z `combining_function: OR` musi nieść pole `or_reason` (min. 20 znaków) i mieć co
najmniej dwa warunki do połączenia; poziom bez ani jednego warunku jest odrzucany. Renderuje to trzy niezależne
warstwy: `schemas/access-level.schema.json` (`if/then/else`), reguły `vpcsc.onboarding` na deklaracjach
i `precondition` w `terraform/perimeter.tf`. Osobno: renderer przestał wysyłać PUSTY warunek do poziomu
złożonego wyłącznie z `required_access_levels`.

**Dlaczego.** Dwa problemy tej samej klasy — „wygląda inaczej, niż działa".

*OR.* `combiningFunction` łączy warunki poziomu. Przy `AND` poziom `corp_network_and_region` znaczy „region PL/DE
**oraz** korpo-sieć". Przestawienie jednego słowa na `OR` daje „region PL/DE **albo** korpo-sieć", czyli wpuszcza
dowolny adres z regionu — a diff to jedna linia wyglądająca na przeredagowanie. Po stronie API nie ma na czym
oprzeć wykrycia: ZMIERZONE na żywym ACM (2026-08-11), `POST` z `combiningFunction: OR` na poziomie złożonym
kończy się `200` i tą samą wartością w odpowiedzi, bez ostrzeżenia i bez śladu, że polityka osłabła.
`or_reason` zamienia jednosłowny diff w zdanie o osłabieniu — recenzent czyta powód zamiast domyślać się intencji.

*Pusty warunek.* Blok `conditions` renderował się bezwarunkowo, więc kompozycja bez własnych atrybutów dostawała
doklejony warunek `{}`, a ACM odrzucał całość jako `AccessLevel definition has a trivial condition`. Materiał
zapisał ten wynik jako właściwość API („kompozycja musi nieść własny warunek") i na tej podstawie blokował
`corp_network AND corp_managed_device` — najmocniejszy wariant dostępu człowieka. ZMIERZONE: ten sam poziom
wysłany surowym `POST`-em (`{"basic":{"conditions":[{"requiredAccessLevels":[…]}]}}`) POWSTAJE. Ograniczenie
było nasze. Po poprawce `dynamic "conditions"` renderuje dokładnie jeden warunek — i dopiero teraz brak
warunków w ogóle nie ma żadnej bariery po stronie API, dlatego pojawia się `precondition` na ten przypadek.

**Co odrzucono i dlaczego.**
- *Zakaz `OR`.* Wzorzec „korpo-sieć **albo** zarządzane urządzenie" jest poprawny i częsty (laptop na
  zarządzanym sprzęcie pracuje spoza sieci firmowej). Zakaz wypchnąłby go do `custom_expression`, czyli do
  wyrażenia CEL — nieporównywalnie trudniejszego do zaudytowania niż lista warunków.
- *Flaga `or_is_intentional: true` zamiast tekstu.* Boolean odhacza się bez myślenia i nie zostawia w pliku
  żadnej informacji dla następnego czytelnika. To samo rozstrzygnięcie co przy `control_plane_exception`.
- *Bramka wyłącznie na plan-JSON (`vpcsc.perimeter`), zgodnie z zasadą „waliduj plan, nie YAML".* Reguły planu
  dostają `--data perimeter/policy.yaml`, a nie katalog poziomów, więc nie widziałyby `or_reason` — furtka
  byłaby niewyrażalna. `precondition` renderera daje tę samą własność (leży NA ścieżce planu i apply,
  nie da się go pominąć nie uruchamiając conftesta) i widzi deklarację razem z uzasadnieniem.
- *Ostrzeżenie zamiast odmowy przy `OR` na jednym warunku.* Taki zapis nic nie robi, więc kusi, żeby go
  tolerować. Ożywa jednak w dniu, w którym ktoś dołoży `required_access_levels`: osłabienie wchodzi wtedy
  bez żadnego diffu przy `combining_function`, bo to słowo stało w pliku od dawna.
---

## DEC-16 — Bramka należy do MUTATORA, nie do zdarzenia `pull_request`

**Decyzja.** Wszystkie bramki treści (schematy JSON, reguły `vpcsc.onboarding` wraz z
`control_plane_projects`, testy jednostkowe reguł, budżet atrybutów, guardy repozytorium) oraz obie bramki
żywe (lista usług wspieranych przez VPC-SC, właściciel bucketa stanu) mają **jedną definicję** — akcje
złożone `.github/actions/bramki-tresci` i `.github/actions/bramki-zywe` — wołaną przez **oba tory**:
`validate.yml`/`plan.yml` na pull requeście oraz `apply.yml` na ścieżce mutatora. W `apply.yml` podział
idzie po TOŻSAMOŚCI: bramki treści w osobnym jobie `bramki` (zero poświadczeń, brak `environment`, job
applikujący zależy od niego przez `needs:`), bramki żywe w jobie applikującym, **tożsamością `apply`**.

**Problem, który to zamyka.** `apply.yml` wyzwala się na push do gałęzi domyślnej i wykonywał: `plan` →
reguły `vpcsc.perimeter` na plan-JSON → `apply`. **Ani jednej bramki treści.** Gałąź domyślna repozytorium
perimetru bywa bez ochrony — na darmowym planie dla repo prywatnego API odpowiada `403 Upgrade to GitHub
Pro`, więc jest to odstępstwo zapisane, nie przeoczone (patrz niezmiennik o ochronie gałęzi w `AGENTS.md`).
Commit wypchnięty prosto na tę gałąź omijał więc **cały** tor `pull_request` i szedł do apply.

**Zmierzone.** Bramka `control_plane_projects` — jedyna kontrola przed awarią, której `git revert` NIE
cofa (konto apply odcięte od własnego stanu, wyjście wymaga człowieka z uprawnieniami org-level na żywej
polityce) — istniała **wyłącznie** w `validate.yml`. `terraform plan` przepuszczał tę samą zmianę na
zielono, bo reguły `vpcsc.perimeter` nie wiedzą nic o płaszczyźnie sterowania: opisują kształt reguł
ingress/egress, nie to, czyj projekt wchodzi do granicy. Kontrola stojąca **obok** ścieżki, którą realnie
zmienia się granicę, jest kontrolą celującą w pustkę.

**Dlaczego jedna definicja, a nie skopiowane kroki.** Kopia rozjeżdża się przy pierwszej zmianie —
i wtedy wraca dokładnie ten defekt, tylko ciszej, bo „te same bramki" przestają być te same, a nic tego
nie mierzy. Nowa deklaracja (`perimeter/alerting.yaml` przyszła tydzień po poprzedniej) dopisana do
jednego z dwóch zestawów odtworzyłaby lukę dzień po jej zasypaniu. Selftest mierzy **zawieranie zbiorów**:
każda akcja bramkowa wołana przez tor pull requesta musi być wołana także przez mutatora, z premisą
odrzucającą zbiór pusty.

**Dlaczego akcja złożona, a nie `workflow_call`.** Reusable workflow to osobny JOB: własny runner, własny
checkout, własna wymiana tokenu WIF i własna przestrzeń robocza. Kroki bramek muszą widzieć drzewo
wywołującego (`declarations.json`, pobrany artefakt dowodu naruszeń), a na ścieżce apply — wykonać się
przed wejściem w environment. Akcja złożona działa **wewnątrz** joba wywołującego: dzieli katalog roboczy
i nie dokłada ani jednego uwierzytelnienia.

**Dlaczego bramki są osobnym JOBEM, a nie krokami przed `terraform apply`.** Job `apply` deklaruje
`environment: perimeter-apply` z polityką gałęzi. Na gałęzi spoza tej polityki GitHub odrzuca **cały job**,
zanim ruszy pierwszy krok — bramki umieszczone tam byłyby więc **nietestowalne inaczej niż na żywej
granicy**. Osobny job bez `environment` uruchamia się `workflow_dispatch`-em z gałęzi testowej, więc da się
ZOBACZYĆ, że odrzuca, zamiast twierdzić, że odrzuci. Dodatkowo czerwona bramka zatrzymuje przebieg przed
wymianą tokenu na tożsamość zapisującą, a `needs:` jest twarde: job applikujący nie startuje wcale.

**Dlaczego bramki żywe pytają kontem `apply`, mimo że to KOSZTUJE.** Bramka żywa opisuje stan świata,
który za moment zostanie zmieniony. Zapytana kontem `plan` opisywałaby świat widziany przez KOGOŚ INNEGO
niż mutator, a różnica między tymi dwoma widokami wyszłaby dopiero jako czerwony apply — czyli tam, gdzie
nie ma już czego sprawdzać. `terraform apply` zaczyna od REFRESHU, więc jest nadzbiorem planu: konto
`apply` musi umieć przeczytać wszystko, czym zarządza, i to samo dotyczy teraz obu bramek żywych.

Cena jest realna i nazywamy ją wprost: **uprawnienie, którego kontu `apply` zabraknie, nie osłabia granicy
— ZATRZYMUJE jedyną drogę wdrożenia.** Ten tryb awarii już tu wystąpił (rola org-wide niosła uprawnienie,
bez którego refresh monitoringu padał `403` przy KAŻDEJ zmianie). Dlatego warunek konieczny jest sprawdzony
w kodzie, nie założony: `iam-bootstrap/main.tf` nadaje `roles/storage.legacyBucketReader` na buckecie stanu
**obu** kontom tym samym `for_each` — a to jest dokładnie `storage.buckets.get`, z którego żyje
`control_plane_check.py --live`. Odwrotna strona tej zależności jest zdrowa: zdjęcie tego grantu zatrzymuje
apply niezależnie od bramki, bo apply przestaje widzieć własny stan.

**Ryzyko szczątkowe tej decyzji, zmierzone i nazwane.** Drugiej bramki żywej
(`gcloud access-context-manager supported-services list`) NIE dało się przed wdrożeniem sprawdzić kontem
`apply` inaczej niż uruchomieniem na gałęzi domyślnej: wiązanie WIF wydaje tę tożsamość WYŁĄCZNIE tokenowi
z roszczeniem `attribute.environment/perimeter-apply`, a polityka gałęzi tego environment dopuszcza samą
gałąź domyślną. Nie istnieje więc gałąź testowa, na której dałoby się to zmierzyć — pierwszy przebieg na
gałęzi domyślnej JEST pomiarem. Konsekwencja przyjęta świadomie: pierwszy apply po tej zmianie ogląda się
na żywo, a wycofanie to jedno cofnięcie kroku.

**Dowód naruszeń idzie tą samą drogą — i to nie jest detal.** `promotion_gate` jest fail-closed: bez mapy
`violations_last_window` odrzuca KAŻDEGO członka `enforced`. Gdyby artefakt raportu pobierał wyłącznie tor
pull requesta, bramki przed apply byłyby OSTRZEJSZE niż te, które przepuściły review — zmergowana promocja
z kompletnym dowodem nie zostałaby zastosowana **nigdy**, a przebieg wyglądałby na „bramka zadziałała".
Dlatego `apply.yml` ma `actions: read` i pobiera ten sam artefakt.

**Czego to NIE zastępuje.** Ochrona gałęzi domyślnej zostaje prerekwizytem wdrożenia. Bramki na ścieżce
mutatora sprawiają, że zła treść nie zostanie **zastosowana**; ochrona gałęzi sprawia, że w ogóle nie
**wyląduje** na gałęzi domyślnej — czyli że historia repozytorium nadal opisuje to, co przeszło review.
To dwie różne własności i jedna nie kupuje drugiej.

**Ryzyko szczątkowe nazwane wprost.** Wyzwalacz `apply.yml` obejmuje `perimeter/**` i `terraform/**`
(i musi być zgodny z tym, co obserwuje `watch.yml` — patrz DEC-13). Push zmieniający SAME reguły
(`policy/**`) nie uruchamia więc apply w tej samej chwili; rozbrojenie reguły wychodzi dopiero przy
NASTĘPNYM apply, gdzie łapią je testy jednostkowe `conftest verify` w tym samym jobie bramek. Poszerzenie
wyzwalacza oznaczałoby apply przy zmianie, która nie zmienia granicy — koszt bez zysku, bo okno zamyka
się przy pierwszej realnej zmianie.

**Koszt.** Jeden dodatkowy job na apply: ~60-90 s (instalacja narzędzi, wymiana tokenu, dwa wywołania
API). Płacony raz na apply, nie raz na pull request.

**Odrzucone.**
- *Włączyć ochronę gałęzi zamiast przenosić bramki.* Funkcja płatna na repo prywatnym (`403 Upgrade to
  GitHub Pro`), a upublicznienie repozytorium nie jest obejściem — jego treść to mapa dostępów. Nawet
  z ochroną gałęzi rozwiązaniem właściwym jest bramka na mutatorze: ochrona gałęzi wymusza review, a nie
  wykonanie kontroli.
- *Skopiować kroki z `validate.yml` do `apply.yml`.* Najkrótszy diff, najkrótsza żywotność: pierwsza
  bramka dopisana po jednej stronie odtwarza lukę, a zielony przebieg wygląda identycznie.
- *Reusable workflow (`workflow_call`).* Osobna przestrzeń robocza i osobne uwierzytelnienie dla kroków,
  które muszą czytać drzewo wywołującego; wymagałby przenoszenia artefaktów między jobami tylko po to,
  żeby bramki zobaczyły to, co i tak leży obok.
- *Bramki jako kroki w jobie `apply`.* Nietestowalne poza gałęzią domyślną (polityka gałęzi environment
  odrzuca cały job), czyli jedyny dowód działania pochodziłby z żywej granicy.
- *Bramki żywe tożsamością `plan` (read-only) w jobie bez environment.* Kuszące, bo testowalne z gałęzi
  testowej i bez ryzyka zatrzymania wdrożenia. Odrzucone: bramka pytałaby innym kontem niż to, które
  zmienia granicę, więc jej zielony wynik nie byłby zdaniem o mutatorze. Testowalność kupujemy inaczej —
  bramki treści (w tym ta, która motywowała całą zmianę) stoją w jobie bez poświadczeń i bez environment.

---

## DEC-17 — Promocja do `enforced` zatrzymuje apply; zgodą jest ręczne uruchomienie z listą promowanych

**Decyzja.** `apply.yml` porównuje na ścieżce mutatora dwie rzeczy: kto jest **zadeklarowany** jako
`stage: enforced` w `perimeter/projects.yaml` i kto jest **realnie egzekwowany** w żywym perimetrze
(`status.resources` z API). Różnica — członkowie, których ten apply zacząłby egzekwować — **zatrzymuje
przebieg przed `terraform plan`**. Jedyne, co go zwalnia, to ręczne uruchomienie workflowa
(`workflow_dispatch`) z polem `promocje` wypełnionym listą kluczy członków **równą** tej różnicy.
Zdejmowanie egzekwowania (`enforced` → `dry-run`, rewert, offboarding, break-glass) **nie jest bramkowane**
i jedzie automatem. Kod: `tools/promotion_hold.py` + akcja `.github/actions/bramka-promocji`.

**Problem, który to zamyka.** Bez tego merge JEST egzekwowaniem. Pull request z jednowyrazowym diffem
(`stage: dry-run` → `stage: enforced`) po scaleniu wyzwala `apply.yml` na push do gałęzi domyślnej
i granica zaczyna odmawiać — bez kroku, na którym człowiek cokolwiek naciska. `promotion_gate` (reguły
OPA) sprawdza warunki merytoryczne promocji: minimum dni w dry-run, czyste okno obserwacji, istniejący
raport naruszeń — ale sprawdza je **automatem**. Zgoda człowieka istniała wyłącznie w dokumentacji.

**Dlaczego akurat ta zmiana zasługuje na bramkę, skoro reszta repozytorium jedzie automatem.** Bo jest
jedyną, której skutkiem jest **odmowa ruchu**, i jedyną, w której cofnięcie konfiguracji nie równa się
cofnięciu skutku. **Zmierzone przy rollbacku pierwszej promocji: 46 s do zakończenia `apply`, ale 78 s do
powrotu ruchu** — konfiguracja wraca natychmiast, skutek propaguje się ~20 s dłużej i w tym oknie
wywołujący dostają odmowę. Nowy członek w dry-run, reguła ingress, access level ani zmiana budżetu nie
odbierają nikomu dostępu. Promocja tak — i robi to na podstawie diffa, który w review wygląda na kosmetykę.

**Ograniczenie, którego nie da się ominąć ustawieniem — zmierzone, nie założone.** Naturalny mechanizm
(required reviewers na environment `perimeter-apply`) jest **funkcją płatną dla repozytoriów prywatnych**.
Na planie bez niej API przyjmuje `PUT` i zostawia environment **bez ani jednej reguły ochrony** — dlatego
`tools/bootstrap_github.sh` odczytuje stan z powrotem i odmawia zameldowania sukcesu przy braku bramki
(`--no-human-gate "<powód>"` jako świadome odstępstwo). Ta sama granica planu odpowiada `403 Upgrade to
GitHub Pro or make this repository public to enable this feature` na ochronie gałęzi **i** na regułach
repozytorium (rulesets) — zmierzone na obu endpointach. Bramka opisana tutaj jest więc jedyną warstwą
ludzką, która działa **na każdym planie**, i celowo nie wymaga żadnego ustawienia repozytorium.

**Dlaczego porównanie ze stanem świata, a nie diff commitów.** Diff (`before..after` przy push,
`base..head` na pull requeście) opisuje ZDARZENIE i znika razem z nim. Trzy przebiegi stosują dokładnie tę
samą treść, nie mając żadnego diffa: ręczne `workflow_dispatch`, ponowienie przebiegu (`gh run rerun`)
i apply po apply, który padł. Bramka na diffie byłaby więc nieobecna dokładnie tam, gdzie nikt nie patrzy
na treść. Porównanie deklaracji ze stanem granicy jest prawdziwe przy każdym wyzwalaczu — także wtedy, gdy
ktoś rozbije promocję na dwa commity albo wypchnie ją prosto na gałąź domyślną z pominięciem review.
Jest to nadal wykrycie **po treści deklaracji** (`stage:`), a nie po nazwie gałęzi ani po etykiecie:
nazwa i etykieta są pod kontrolą autora zmiany.

**Dlaczego równość zbiorów, a nie flaga „zatwierdzam".** Pole `promocje` wymaga wypisania, KOGO ten
przebieg zacznie odcinać — „zatwierdzam wszystko" nie jest w tym języku wyrażalne. Gdy między spojrzeniem
na repozytorium a uruchomieniem dojdzie druga promocja, zbiory przestają być równe i bramka staje ponownie,
zamiast przepuścić przy okazji coś, czego zatwierdzający nie widział. Zatwierdzenie wskazujące członka
spoza zbioru oczekujących też jest błędem: opisuje inny stan repozytorium niż stosowany.

**Dlaczego bramka jest asymetryczna.** Zatrzymujemy wyłącznie ruch w stronę `enforced`. Bramka na drodze
powrotnej wydłużałaby każdą awarię o czas szukania człowieka — a to jest ta sama pomyłka, co procedura
awaryjna wymagająca zatwierdzenia. Rewert promocji jedzie więc automatem i jest pełnoprawną drugą drogą
wyjścia z zatrzymanego apply (obok naciśnięcia bramki).

**Zgoda ma jedno źródło i jest to własność wykonywalna, nie konwencja.** `promotion_hold.py` odrzuca
zatwierdzenie przyniesione przez zdarzenie inne niż `workflow_dispatch`. Wpisanie listy na stałe w plik
workflowa (albo doklejenie jej do wyzwalacza `push`) nie jest więc obejściem: byłaby to zgoda, której nikt
nie wyraża w momencie skutku, zdejmowalna jednym commitem wyglądającym w diffie na konfigurację.

**Perimetr, którego nie ma, znaczy „nikt nie jest egzekwowany" — a nie awarię.** Przy pierwszym apply na
świeżej organizacji perimetr powstaje w tym samym przebiegu; gdyby brak obiektu był błędem, bramka
zatrzymywałaby wdrożenie idące dokumentowaną ścieżką (wszyscy członkowie w `dry-run`). **Każdy inny błąd
odczytu przerywa apply**: „nie wiem, kto jest egzekwowany" nie może zdegradować się do „pewnie nikt".

**Skutek uboczny, nazwany wprost.** Wstrzymana promocja leży na gałęzi domyślnej jako zmiana
NIEZASTOSOWANA, więc po `apply_pending_seconds` odpala alert wieku niezastosowanej zmiany (DEC-13). Jest to
zamierzone: bramka nie jest miejscem parkowania. Promocja albo zostaje naciśnięta, albo zrewertowana —
trzeciego stanu nie ma, a alert jest tym, co go nie pozwala udawać.

**Koszt.** Jedno wywołanie API na apply, przed wzięciem zamka stanu — przebieg wstrzymany nie blokuje
niczyjego apply i nie zostawia po sobie zablokowanego stanu.

**Odrzucone.**
- *Required reviewers na environment jako jedyna warstwa.* Nie istnieje na planie bez niej, a jej brak
  jest cichy (API przyjmuje żądanie, environment zostaje bez reguł). Warstwy się nie wykluczają: tam,
  gdzie plan ją ma, zostaje włączona i **dokłada** rozdział tożsamości, którego ta bramka nie daje.
- *Drugi workflow („promote.yml") z własnym `terraform apply`.* Druga kopia mutatora: własny checkout,
  własna wymiana tokenu WIF, własna publikacja kontraktu. Rozjedzie się z pierwszą przy pierwszej zmianie,
  a rozjazd mutatora jest awarią, o której dowiadujesz się na żywej granicy. Zamiast tego jeden workflow
  ma dwa tryby, rozróżniane wejściem, którego GitHub nie wyprodukuje sam.
- *Wspólna akcja z wejściem `blokuj: true|false`.* Bramka zdejmowalna przestawieniem jednej flagi
  w jednym miejscu, nadal wyglądająca w drzewie na obecną. Osobna akcja czyni asymetrię (mutator tak,
  pull request nie) widoczną w układzie plików.
- *Bramka „dwóch kluczy": zatwierdzenie tożsamością inną niż autor zmiany.* Właściwy kierunek i realny
  rozdział obowiązków — odrzucony jako **mechanizm podstawowy**, bo w repozytorium z jedną tożsamością
  z prawem zapisu jest niespełnialny, a bramka niespełnialna zostaje wyłączona przy pierwszej potrzebie
  i wraca stan wyjściowy. Rozdział tożsamości należy do warstwy ustawień repozytorium (required reviewers),
  gdzie jest egzekwowany przez GitHuba, a nie do skryptu, który tę samą tożsamość porównuje sam ze sobą.
- *Wykrycie po etykiecie pull requesta albo po nazwie gałęzi (`promocja/*`).* Jedno i drugie jest pod
  kontrolą autora zmiany i znika przy push prosto na gałąź domyślną — czyli bramka nie działa dokładnie
  w tym przypadku, dla którego powstała.
- *Przeniesienie repozytorium na plan płatny.* Rozwiązuje inne zadanie (ochrona gałęzi, rozdział
  tożsamości) i warto je rozważyć osobno — ale samo w sobie nie stawia punktu zatrzymania **na wykonaniu**:
  required reviewers wstrzymują deploy do environment niezależnie od tego, czy zmiana jest promocją, czy
  literówką w komentarzu. Bramka, która pyta o zgodę przy każdym apply, jest bramką, która przestaje być
  czytana.

---

## DEC-18 — Bramka promocji pyta o PRZEJŚCIE do `enforced`, a stanem odniesienia jest opublikowany kontrakt

**Decyzja.** Trzy warunki promocji w `policy/onboarding.rego` (minimalne okno dry-run, istnienie raportu
naruszeń, zero naruszeń w oknie) obowiązują **wyłącznie wtedy, gdy egzekwowanie dla tego członka dopiero
ma zostać włączone**. „Dopiero ma zostać" rozstrzyga porównanie deklaracji z **kontraktem** — artefaktem
publikowanym przez każdy apply (`terraform/contract.tf`: bucket + asset release'u `contract`), niosącym
`stage` per członek. Repo mówi `enforced`, kontrakt mówi cokolwiek innego (albo nie zna tego członka) =
przejście, bramka uzbrojona. Kontrakt mówi `enforced` = granica już działa, bramka milczy.
`collect_declarations.py --contract` wstawia do dokumentu dwa pola: `applied_stages` i `applied_stages_known`.

**Problem, który to zamyka.** Warunki promocji odpowiadają na pytanie **„co się zepsuje, jeśli TERAZ
włączymy egzekwowanie"**. Zadane po samym `stage: enforced` obowiązują jednak dopóki członek jest
`enforced` — czyli także długo po tym, jak decyzja zapadła i została zastosowana. A wtedy te same liczby
znaczą coś odwrotnego: liczba naruszeń przestaje być prognozą ryzyka i staje się **liczbą odmów**, czyli
miarą tego, że granica robi swoje (odmowa egzekwowana zapisuje wpis `VpcServiceControlAuditMetadata` tak
samo jak naruszenie dry-run — pole `dryRun` istnieje WYŁĄCZNIE przy dry-run, więc raport liczy oba
świadomie). Liczba dni w dry-run przestaje być oknem obserwacji, a staje się historią. Bramka mająca
chronić przed promocją bez dowodu zamieniała się w **blokadę repozytorium wyzwalaną przez poprawne
działanie granicy**.

**Zmierzone (pierwsza promocja w organizacji labu).** Po zdjęciu wyjątku `promotion_waivers` bramki dawały
**dwa odrzucenia** na wniosku, który o promocji nie mówił nic: „18 naruszeń w oknie obserwacji" oraz
„promocja do enforced po 2 dniach dry-run, wymagane minimum 14". Osiemnaście — to były odmowy, po które
promocję robiono. Druga, cichsza twarz tego samego defektu: **kanały wejścia** (`intake.yml`,
`external-intake.yml`) uruchamiają te same reguły, ale artefaktu naruszeń nie pobierają w ogóle, więc
padały na regule „brak raportu naruszeń" — każde zgłoszenie NOWEGO projektu (zawsze w dry-run) było
odrzucane przez cudzy wpis. Repozytorium stało przez pierwszą dobę wyłącznie na wyjątku założonym po to,
żeby dało się cokolwiek zmergować; wyjątek zdjęto razem z tą zmianą.

**Dlaczego stan ZASTOSOWANY, a nie diff wobec gałęzi domyślnej.** Diff jest najdosłowniejszym odczytaniem
słowa „przejście" i nie działa z dwóch niezależnych powodów. Po pierwsze te same bramki wykonują się na
dwóch torach (DEC-16), a na torze mutatora **nie ma czego z czym porównać** — apply chodzi już na gałęzi
domyślnej, po merge'u. Bramka diffowa dawałaby inny werdykt przed merge'em niż po nim, czyli dokładnie tę
asymetrię, dla której DEC-16 powstał. Po drugie diff mówi o GICIE, a nie o GRANICY: zmergowana promocja,
której apply nie zastosował (padł, czeka w kolejce single-flight), znika z diffu i przestaje być
pilnowana, choć w rzeczywistości nic jeszcze nie zostało włączone. Kontrakt opisuje to, co realnie
wyszło z ostatniego apply — więc bramka pilnuje granicy, a nie historii pliku.

**Stosunek do DEC-17 — dwa źródła „stanu zastosowanego" i to jest celowe.** DEC-17 zatrzymuje apply,
porównując deklarację z **żywym API** (`status.resources`); ta decyzja pyta o to samo, ale **kontraktem**.
Różnica bierze się z miejsca, w którym każda z bramek stoi. Bramka apply chodzi w jobie z tożsamością
i ma prawo pytać API — a musi, bo jest ostatnią kontrolą przed mutacją i nie może opierać się na
artefakcie z poprzedniego przebiegu. Bramka treści chodzi także na torze pull requesta, który świadomie
**nie ma żadnego poświadczenia w chmurze** (DEC-16); pytanie API stamtąd oznaczałoby dołożenie tożsamości
GCP do każdego PR-a — czyli oddanie autorowi dowolnej zmiany prawa odczytu granicy. Obie warstwy się
składają: kontrakt bywa o jeden apply starszy niż świat, ale **starzeje się wyłącznie w stronę
surowszą** (mówi `dry-run`, gdy granica już działa → bramka pyta dalej), a rozjazd w drugą stronę
wymagałby apply, który zmienił perimetr i nie opublikował kontraktu — ten sam krok robi jedno i drugie,
a przebieg pada, gdy suma kontrolna po obu stronach się nie zgadza.

**Fail-closed, i to nie jest szczegół.** „Nie wiem, co jest zastosowane" znaczy „to jest przejście, żądaj
dowodu". Odwrotna domyślność zamieniłaby tę bramkę w wyłącznik uruchamiany **usunięciem pliku**:
wystarczyłoby nie opublikować kontraktu (albo `publish_members: false`), żeby promować bez ani jednego
dowodu. Stąd `applied_stages_known` jest osobnym polem, a nie „pusta mapa = nie wiemy": pusta mapa jest
dwuznaczna (kontraktu nie ma / kontrakt jest i nie publikuje członków), a `default … := false` w rego
czyni brak pola równoważnym z „nie wiemy". `collect_declarations.py` ustawia tę flagę wyłącznie, gdy
kontrakt daje się przeczytać, ma znaną wersję schematu i jawnie publikuje listę członków; **każdy** inny
przypadek (uszkodzony JSON, wpis bez `stage`, nieznana wersja) daje `False` i komunikat na stderr —
ale kodem wyjścia 0, bo wywrócenie narzędzia zamieniłoby uszkodzone pobranie w czerwone dla WSZYSTKICH
pull requestów, zamiast zaostrzyć jedną bramkę.

**Czego to NIE rozluźnia.** Promocja bez dowodu stoi tak samo jak wcześniej — zmienia się wyłącznie to,
jak długo pytanie jest zadawane. Testy trzymają obie strony naraz: usunięcie warunku o przejściu wywraca
cztery testy („już egzekwowany przechodzi"), a uczynienie go zawsze prawdziwym — szesnaście, w tym
wszystkie o wyjątkach. Selftest dokłada guard enumerujący **z plików** każdą ścieżkę, która uruchamia
reguły `vpcsc.onboarding` na pełnym zbiorze członków, i wymaga od niej `--contract`; guard czyta ciała
`run:`, nie tekst pliku, żeby nie dało się go zdać komentarzem.

**Co odrzucono.**
- *Rozdzielenie liczników w raporcie na „naruszenia dry-run" i „odmowy enforced".* Kusi, bo brzmi jak
  poprawka u źródła danych. Odrzucone: nadal odpowiada na pytanie o STAN, tylko innym licznikiem —
  a członek `enforced` obecny również w konfiguracji dry-run dalej produkowałby wpisy, które bramka
  czytałaby jako ryzyko. Do tego rozróżnienie stoi na **nieobecności** pola `dryRun` (przy odmowie
  egzekwowanej pola nie ma w ogóle, `dryRun="false"` nie łapie nigdy niczego — zmierzone), czyli na
  własności niepublikowanej w schemacie logu; bramka bezpieczeństwa oparta na takim szczególe zamienia
  zmianę po stronie Google'a w cichy fail-open. Rozdzielenie liczników ma sens jako **obserwacja**
  (alerty w `terraform/alerts.tf` już to robią), nie jako wejście bramki.
- *Nowe pole w deklaracji z datą promocji, a reguła liczy naruszenia sprzed tej daty.* Najprostsze —
  i jedyne, które ktoś kiedyś ustawi ręcznie na wczoraj. Pole opisujące fakt z przeszłości, edytowalne
  przez wnioskodawcę w tym samym PR-ze, w którym prosi o promocję, nie jest dowodem, tylko oświadczeniem.
  Ta sama zasada co „payload webhooka to dane, nigdy autoryzacja" (DEC-2).
- *Zawieszenie reguły na czas przez `promotion_waivers`.* To jest zatyczka, którą ta decyzja zdejmuje:
  wyjątek ma pokrywać ZMIERZONE naruszenia przy świadomej decyzji, a nie maskować bramkę zadającą złe
  pytanie. Wyjątek jako lekarstwo na własną konstrukcję reguły uczy wyłączania bramek.
- *Kontrakt pobierany z bucketa (a nie z release'u).* Wymagałby tożsamości w GCP na torze pull requesta,
  a ten zestaw bramek jest świadomie wykonywalny **bez ani jednego poświadczenia w chmurze**; asset
  release'u pobiera się tokenem, który workflow i tak ma (ta sama droga co paczka bramek, DEC-8).
- *Kontrakt niosący `project_number` członka, żeby wykluczyć podszycie się pod skasowany projekt.*
  Rozważone przy #1979 (martwy członek produkuje fałszywy dowód czystego okna). Odrzucone: identyfikatora
  projektu w GCP **nie da się użyć ponownie** po skasowaniu, więc scenariusz „ten sam `project_id`, inny
  projekt" jest niewyrażalny, a kontrakt zyskałby pole, którego nikt nie czyta.

---

## DEC-19 — Access level deklaruje UZBROJENIE, a ścieżkę pozytywną mierzy kanarek, nie log

**Decyzja.** Access level dostaje pole `armed` i trzy pola atestacyjne, a materiał dostaje **kanarka** —
parę reguł baseline różniących się wyłącznie wymaganym poziomem. Trzy warstwy, każda na inne pytanie:

1. **`armed: false` + `unarmed_reason`** — poziom mówi wprost, że dziś nie wpuszcza nikogo. Wymuszone tam,
   gdzie da się to orzec maszynowo: zakresy wyłącznie dokumentacyjne (RFC 5737 `192.0.2.0/24`,
   `198.51.100.0/24`, `203.0.113.0/24`; RFC 3849 `2001:db8::/32`) oraz kompozycja `AND` nad nieuzbrojonym
   składnikiem. Poziom nieuzbrojony **referowany przez konfigurację EGZEKWOWANĄ** wywraca plan, chyba że
   niesie `unarmed_accepted_until` z datą w przyszłości — świadomy, **wygasający** zapis.
2. **`source_of_truth` + `reviewed` + `review_interval_days`** — uzbrojony poziom z zakresami IP musi
   powiedzieć, skąd wartość i kiedy człowiek od sieci ją potwierdził. Przeterminowana atestacja czerwieni
   plan **na poziomie stojącym w konfiguracji egzekwowanej**; poza nią zostaje informacją.
3. **Kanarek** (`policy.yaml` §baseline_ingress, `boundary-probe.yml -f kanarek=…`) — dwie reguły
   read-only różniące się **wyłącznie** access levelem, wołane tą samą tożsamością pipeline'u. Jedno
   wywołanie ma przejść, drugie dostać odmowę VPC-SC.

**Problem, który to zamyka — i dlaczego nie widać go w żadnym przeglądzie.** Access level z zakresem IP ma
tryb awarii bez objawu: zakres przestaje pasować (zmienił się koncentrator VPN, doszło biuro, dostawca
przenumerował pulę NAT), a obiekt w ACM wygląda identycznie jak przedtem. `describe` pokazuje treść, którą
sami wysłaliśmy. Audit-log zapisuje **naruszenia**, nie wpuszczenia — więc „nikt tędy nie wszedł" i „nikt
nie próbował" mają w logach ten sam obraz: pusty. Dowiadujesz się w dniu promocji, gdy ruch dywizji ginie.

**Zmierzone (organizacja labu, 2026-08-12).** Wszystkie cztery poziomy stały na adresach dokumentacyjnych
albo je dziedziczyły, a jedyna reguła **członkowska** w konfiguracji EGZEKWOWANEJ wskazywała
`corp_network_and_region`, czyli `regions [PL, DE] AND corp_network(203.0.113.0/24, 198.51.100.0/24)`.
Reguła stała w konfiguracji, która realnie blokuje, i **nie autoryzowała nikogo**. To ta sama klasa co
reguła baseline bez `sources` — z jedną różnicą: tamtą dało się złapać kształtem reguły, tę widać
wyłącznie w treści danych, więc nie łapała jej żadna z bramek.

**Dlaczego ścieżki pozytywnej nie da się zmierzyć „zwykłym" sposobem.** Odmowę widać z dowolnego miejsca —
wystarczy zawołać chronione API spoza perimetru. Żeby zobaczyć **wpuszczenie**, trzeba przyjść z miejsca,
które poziom spełnia, a przy warunku `ip_subnetworks` znaczy to „z waszej sieci". Pipeline CI stoi poza
nią. Trzy kandydatury na adres, z którego dałoby się sondować, i powód odrzucenia każdej — inny:

* **Adres runnera dostawcy CI.** Nieznany przed przebiegiem i rotujący. Opublikowana lista zakresów
  obejmuje **całą flotę CI dostawcy**, więc wpisanie jej do poziomu autoryzowałoby cudze pipeline'y —
  poszerzenie granicy o rząd wielkości większe niż cokolwiek, co ta bramka chroni.
* **Stała maszyna z zarezerwowanym adresem w regionie objętym warunkiem.** Technicznie spełnia OBA
  warunki (`ip_subnetworks` i `regions`) i jest jedynym wariantem dającym uczciwy pomiar poziomu
  sieciowego. Koszt: rezerwacja adresu ~5 USD/mies. utrzymywana bez przerwy, plus maszyna. Odrzucone
  **z ceną w ręku**, nie „bo drogo": cały tor dowodowy tej granicy działa dotąd bez ani jednej maszyny,
  a stały koszt pojawia się tu wyłącznie po to, żeby raz na jakiś czas udowodnić własność, którą kanarek
  pokazuje za darmo. Wariant zostaje zapisany jako dostępny — w organizacji z własnym runnerem w sieci
  korporacyjnej znika sam z siebie, bo ten runner JUŻ tam stoi.
* **Adres człowieka/laptopa.** Jeden, nierotowalny i osobowy: spalony blokadą zostaje spalony, a wpisany
  do konfiguracji wiąże całą granicę z jedną osobą fizyczną. Nie wchodzi niezależnie od wygody.

**Dlaczego kanarek jest tożsamościowy, a mimo to nie jest obejściem kontroli sieciowej.** Poziom
autoryzujący **wyłącznie** tożsamością nie dokłada nic ponad `ingressFrom.identities` reguły — a przy
scenariuszu, dla którego access level w ogóle istnieje (skradzione poświadczenie użyte z cudzej sieci),
zdejmuje jedyną obronę. Gdyby więc kanarkiem zastąpić warunek sieciowy w regule dywizji, byłoby to
obejście, i tak to nazywamy. Kanarek jest czym innym w trzech wymiarach naraz i każdy z nich jest
sprawdzalny w pliku: (a) stoi na **własnych** regułach `canary-*`, nigdy na regule dywizji;
(b) tożsamością jest **konto pipeline'u**, nie konto aplikacji — to samo, które i tak ma regułę baseline;
(c) celem są **dwie metody read-only opisujące konfigurację logowania**, nie dane. Kanarek nie zastępuje
warunku sieciowego — mierzy **mechanizm**: czy access level, gdy jest spełniony, przepuszcza.

**Dlaczego para, a nie pojedyncza sonda.** Pojedyncze „przeszło" nie mówi nic: ta sama metoda przechodzi
też wtedy, gdy reguła jest szersza, niż wygląda, gdy perimetr nie obejmuje projektu i gdy usługa wypadła
z `restricted_services`. Para różni się **jedną** rzeczą — poziomem wymaganym przez regułę — więc każda
WSPÓLNA przyczyna (brak roli IAM, wyłączone API, zepsuty projekt, nieobecna reguła) daje ten sam wynik po
obu stronach i nie potrafi wyprodukować rozjazdu. Rozjazd może pochodzić już tylko z access levelu.
Stan `kanarek=rozbrojony` (obie sondy odmówione) jest **osobnym, zielonym** przelotem, a nie czerwonym:
„para działa" znaczy coś dopiero wtedy, gdy widzieliśmy tę samą parę również NIE działającą.

**Odpowiedź na „skąd wiadomo, że zakres jest nadal aktualny" — dwa różne narzędzia na dwie różne awarie.**
`reviewed` + `review_interval_days` wykrywa **zaniedbanie procesu**: nikt od pół roku nie potwierdził
wartości. Kanarek wykrywa **rozjazd faktyczny**: uruchomiony z runnera stojącego w sieci korporacyjnej
i celujący w poziom z realnym zakresem przestaje przechodzić w dniu, w którym zakres przestaje pasować —
zanim zobaczy to dywizja, bez czytania jakiegokolwiek logu. Zegar bez kanarka daje odhaczoną datę przy
martwym zakresie; kanarek bez zegara nie pokrywa poziomów, których nie da się sondować (break-glass,
device-trust). Dopiero razem mówią „ten poziom działa i ktoś za to odpowiada".

### Alternatywy odrzucone

- *Wykrywanie „nikt nie wszedł przez ten poziom od N dni" z logów.* Wariant pierwszego wyboru i odrzucony
  po sprawdzeniu, co w tych logach jest. VPC-SC loguje **naruszenia**; wpisu „wpuszczono, bo access level
  X pasował" nie ma. Wnioskowanie o wpuszczeniu wymagałoby **Data Access audit logs** na usługach
  chronionych w każdym projekcie członkowskim — domyślnie wyłączonych i płatnych od wolumenu, a przy
  kilkuset projektach to najdroższa pozycja całego wdrożenia. Do tego sygnał nie ma wartości
  diagnostycznej: „zero wejść w N dni" jest **normalnym** stanem poprawnie zawężonej reguły (nikt nie
  próbował), więc alert świeciłby na każdej cichej regule i zostałby wyciszony — a awaria, która nas
  interesuje, i tak nie objawia się ciszą, tylko **serią odmów**, którą istniejący tor naruszeń już widzi.
  Kanarek zamienia problem obserwacji w problem generacji: zamiast czekać na ruch, który może nigdy nie
  przyjść, produkujemy własny, deterministyczny.
- *Bramka zakazująca `ip_subnetworks` w poziomach referowanych przez konfigurację egzekwowaną.* Zamienia
  defekt danych w zakaz prymitywu. Warunek sieciowy jest tu jedyną kontrolą **strukturalnie zdolną**
  odciąć dostęp z nieznanej sieci (ani IAM Deny, ani PAB nie mają na wejściu pojęcia adresu), więc bramka
  wypychająca go z użycia osłabia granicę pod pozorem sprzątania.
- *Uznanie zakresów dokumentacyjnych za błąd także w dry-run.* Dry-run jest miejscem na konfigurację
  niedokończoną — po to istnieje. Twarda bramka tam zmusiłaby do wpisywania realnych zakresów, zanim
  ktokolwiek je potwierdzi, czyli produkowałaby dokładnie te wartości „na teraz", których ten mechanizm
  ma nie dopuścić do konfiguracji egzekwowanej.
- *Doliczenie RFC 1918 do zakresów-atrap.* Adres prywatny bywa **poprawną** wartością dla ruchu z sieci
  korporacyjnej przez interconnect. Wspólny worek zamieniłby bramkę wykrywającą placeholder w bramkę
  odrzucającą realny wzorzec — i nauczyłby ludzi ją obchodzić.
- *`armed` liczone automatycznie zamiast deklarowanego.* Maszyna umie orzec „ten zakres jest
  dokumentacyjny", nie umie orzec „ten zakres jest wasz i nadal działa". Pole wyliczane zgadywałoby
  odpowiedź na drugie pytanie i dawałoby zielone światło każdemu zakresowi, który tylko wygląda realnie —
  czyli dokładnie temu, przed czym ten mechanizm ma chronić.
- *Domknięcie przechodnie nieuzbrojenia liczone w rendererze.* HCL nie ma rekurencji, więc wyszłoby albo
  niepełne, albo rozwinięte na sztywną głębokość (a poziom „głębokość 4" pojawi się w dniu, w którym nikt
  o tej granicy nie pamięta). Warunek lokalny „rodzic nieuzbrojonego dziecka też jest nieuzbrojony"
  domyka się **indukcyjnie**, jest pełny dla dowolnego łańcucha i daje komunikat wskazujący oba poziomy.
- *Kanarek jako osobny workflow.* Wtedy jest osobnym przebiegiem, osobnym uprawnieniem i osobną rzeczą do
  zapomnienia. W `boundary-probe.yml` dokłada się do sondy, która i tak jest jedynym miejscem
  produkującym zdania o świecie, i dziedziczy jej kluczową własność: werdykt stawiany z **treści**
  odpowiedzi, nie z kodu błędu.

---

## DEC-20 — Rozjazd ze starterem mierzymy DWOMA bramkami: wskaźnikiem i POKRYCIEM ZBIORU DECYZJI

**Decyzja.** Obok porównania wskaźnika (`starter-drift`, DEC-9) stoi druga, węższa kontrola:
`tools/decisions_check.py`. Pyta o dwie rzeczy i celowo w dwóch różnych miejscach:

* **każdy numer decyzji CYTOWANY gdziekolwiek w repozytorium ma w `docs/0-decyzje.md` swoją sekcję** —
  w `.github/actions/bramki-tresci`, czyli na obu torach (pull request i apply, DEC-16). Nie potrzebuje
  ani sieci, ani startera, więc biegnie na każdym wniosku;
* **zbiór decyzji tutaj pokrywa zbiór decyzji startera** (`--wzgledem`) — w `starter-drift`, bo to
  wymaga pobrania pliku ze startera.

Bramka porównuje **ZBIÓR NUMERÓW SEKCJI, nigdy treść**.

**Problem, który to zamyka — i dlaczego wskaźnik go nie widział.** Wskaźnik odpowiada na pytanie „czy
ktoś przeniósł commity", a nie „czy przeniósł całą ich treść". Zmierzone na wdrożeniu 2026-08-12:
`.starter-sync` wskazywał aktualny `main` startera, `starter-drift` był zielony — a `docs/0-decyzje.md`
nie zawierało **dwóch całych decyzji**. Jedna z nich (DEC-16, bramka na ścieżce mutatora) była w tym
samym repozytorium cytowana w **dziewięciu miejscach**: `apply.yml`, `plan.yml`, `validate.yml`, reguły
`onboarding.rego`, akcja bramki promocji. Kod odsyłał do uzasadnienia, którego w repo nie było.

Sync commit-po-commicie nie ma jak tego zobaczyć: każdy pojedynczy przeniesiony commit wygląda na
kompletny, a niekompletność ujawnia się dopiero na zbiorze. To jest ta sama klasa błędu co bramka
czytająca nieistniejący plik — zielono, bo nie ma czego odrzucić.

**Dlaczego akurat decyzje, a nie „pliki bez placeholderów".** Kuszący wariant — porównywać treść tych
plików, które nie niosą wartości środowiska — **zmierzyliśmy i odrzuciliśmy**. Na tym wdrożeniu: 120
plików z szablonu, 35 różniących się treścią, z tego 20 bez ani jednej wartości środowiska. Ale
**12 z tych 20 różni się WYŁĄCZNIE pinami akcji**, które w repozytorium wdrożonym są NOWSZE niż
w szablonie (podbija je Dependabot i ma to robić), a kolejne kilka — lokalnymi pomiarami dopisanymi
do komentarzy. Bramka na treści tego zbioru byłaby więc czerwona od pierwszego dnia i z powodów
całkowicie legalnych, czyli byłaby dokładnie tym, czego DEC-9 unika z premedytacją. Utrzymywana
allowlista „plików porównywalnych" przenosi tylko problem: to ona zaczyna dryfować, i to po cichu.

Zbiór numerów sekcji nie ma żadnej z tych wad. Jest odporny na wartości środowiska, na piny akcji
i na lokalne przeredagowanie treści — a mierzy dokładnie to, czego brak boli: **uzasadnienie**.

**Dlaczego dwa miejsca, a nie jedno.** Decyzja może zniknąć na dwa sposoby, a każdy widzi tylko jeden:
sprawdzenie wewnętrzne łapie decyzję CYTOWANĄ (odsyłacz w pustkę), ale przepuści taką, której nikt nie
cytuje; `--wzgledem` łapie właśnie tę drugą, ale wymaga sieci, więc nie może biec na każdym wniosku.
Na wdrożeniu, które to wywołało, wystąpiły OBA warianty naraz: DEC-16 była cytowana dziewięć razy,
DEC-14 nie była cytowana ani razu.

**Fail-closed na zepsutym wejściu.** Plik pobrany ze startera bez ani jednej sekcji (404 zapisany do
pliku, pusta odpowiedź API, zła ścieżka) jest **błędem**, nie zerem różnic. Bez tego bramka milczałaby
dokładnie wtedy, gdy jej wejście przestało działać — czyli powtórzyłaby błąd, który sama zamyka.

**Czego to NIE daje.** Nie mówi, że treść decyzji jest aktualna — tylko że sekcja istnieje. Decyzja
przeniesiona jako sam nagłówek przechodzi. Świadomie: alternatywą jest porównanie treści, czyli bramka
zawsze czerwona. Bramka mówi „przeniesiono kadłub, nie przeniesiono nic" — i tyle ma mówić.

**Odrzucone.**
- *Porównanie całego drzewa z wyjściem `install.sh`.* DEC-9 wprost: czerwone zawsze i legalnie, bo
  wartości środowiska są dokładnie tym, co repozytorium wdrożone ma mieć.
- *Porównanie treści plików „bez placeholderów", z allowlistą.* Zmierzone wyżej: czerwone od pierwszego
  dnia przez piny Dependabota, a allowlista dryfuje sama i nikt tego nie mierzy.
- *Wymóg ciągłej numeracji (`DEC-1`…`DEC-N` bez dziur).* Krótsze, ale fałszywe: numery pochodzą ze
  startera i nigdy nie są przenumerowywane, więc wycofana decyzja zostawia legalną dziurę. Bramka
  pytałaby o kształt zbioru zamiast o pokrycie.
- *Reguła OPA zamiast osobnego narzędzia.* Reguły czytają `declarations.json` — dokument o granicy,
  nie o repozytorium. Dołożenie tam listy plików repo zamieniłoby wejście reguł w drugą, cichą
  reprezentację drzewa.
- *Zgłoszenie zamiast czerwieni.* To już mamy przy wskaźniku i to działa: zgłoszenie jest artefaktem
  do przeczytania przed promocją, ale nikt go nie przypisuje. Czerwony przebieg widać na stronie repo.

## DEC-21 — Akcja dywizji mieszka w PUBLICZNYM starterze, bo `uses:` rozwiązuje się bez tokenu

**Decyzja.** `contrib/action.yml` przestaje być materiałem szablonu instalowanym do repozytorium
perimetru i staje się **żywą akcją w tym repozytorium**, pod `.github/actions/contrib/`. Repozytoria
dywizji wołają ją przez `uses: ORG/gcp-vpc-sc-starter/.github/actions/contrib@<40-znakowy SHA>`.
W repozytorium perimetru zostaje **wyłącznie** `contrib/validate-local.sh` — bo ten jedzie do dywizji
w paczce bramek, czyli jako **release asset**, a nie przez `uses:`.

**Powód, zmierzony a nie wywnioskowany.** `uses:` rozwiązuje runner na etapie **`Set up job`**,
**`GITHUB_TOKEN`-em repozytorium wywołującego** — zanim wykona się jakikolwiek krok. Token aplikacji,
na którym stoi cała konstrukcja tego kanału, powstaje **w kroku**. Kolejność jest więc taka, że w miejscu,
gdzie akcja jest pobierana, poświadczenia jeszcze nie ma i **nie ma jak być**. Przy wskazaniu prywatnego
repozytorium perimetru:

```
##[error]Unable to resolve action `<org>/gcp-vpc-sc`, repository not found
```

job kończy się na `Set up job`, **zero wykonanych kroków**. Żadne uprawnienie aplikacji tego nie zmienia
— to nie jest brak dostępu, to jest zła kolejność. Ta sama aplikacja, w tym samym przebiegu, bez problemu
pobiera potem kontrakt i paczkę bramek: bo tamte są **release assetami**, ściąganymi **w kroku**.

**Podział, który z tego wynika, jest podziałem po SPOSOBIE DOSTARCZENIA, nie po treści.** Artefakt
pobierany tokenem (paczka bramek, kontrakt, `validate-local.sh`) może mieszkać w prywatnym repozytorium
perimetru i tam mieszka. Artefakt pobierany przez `uses:` musi być publiczny. Jedyny taki artefakt to
plik akcji — i tylko on się przeprowadza.

**Dlaczego nie zostawić kopii także w perimetrze.** Kopia w prywatnym repozytorium wygląda w diffie na
działającą i jest niewykonalna dla jedynego konsumenta, jaki istnieje. Dwie kopie jednego renderera to
zresztą dokładnie to, co usunęło #1947 — z tym że tutaj rozjazd byłby gorszy niż zwykły dryf: rozjechałyby
się plik, którego ktoś czyta, i plik, który się uruchamia. Bramka w selfteście pyta więc o
**NIEOBECNOŚĆ** `contrib/action.yml` w rozpakowanym repozytorium, a nie o obecność tej właściwej: to
pierwsze da się zepsuć po cichu przez dopisanie linii do `install.sh`, to drugie nie.

### Alternatywy odrzucone

**1. Poszerzenie polityki dostępu Actions repozytorium perimetru**
(`PUT /repos/{o}/{r}/actions/permissions/access` → `{"access_level":"user"}`). Jedno wywołanie API,
naprawia objaw. Odrzucone, bo działa **na całym repozytorium i dla wszystkich workflowów konta naraz**:
otwiera każdą prywatną akcję tej organizacji dla każdego workflowa, który zechce ją zawołać, żeby
rozwiązać jeden przypadek jednego pliku. Repozytorium perimetru trzyma konta usług członków
(`perimeter/projects.yaml`) i firmowe zakresy adresów (`perimeter/access-levels/`) — jest prywatne
z powodów, których nie znosi się po to, żeby udostępnić 11 KB YAML-a. Dodatkowo ustawienie jest
**niewidoczne w kodzie**: nic w repozytorium nie mówi, że kanał od niego zależy, więc następna osoba
przywracająca domyślne `none` zepsułaby onboarding dywizji bez śladu w żadnym diffie.

**2. Osobne publiczne repozytorium tylko na akcję.** Najczystsze wersjonowanie (własne tagi wydań)
i najwęższy zakres. Odrzucone, bo dokłada **trzecią powierzchnię synchronizacji** do układu, w którym dwie
już wymagały zbudowania bramek: rozjazd starter↔perimetr pilnują dziś wskaźnik (DEC-9) i pokrycie zbioru
decyzji (DEC-20). Akcja i reguły, które ona egzekwuje, muszą zmieniać się razem — rozdzielone do dwóch
repozytoriów rozjeżdżają się tak samo jak wszystko inne, tylko bez właściciela tego rozjazdu. Starter
i tak jest publiczny i i tak jest źródłem materiału perimetru — poprawki i tak powstają tutaj.

**3. Vendoring akcji do repozytorium dywizji.** Odrzucone: znosi „jedna definicja na trzy kanały" (DEC-7)
i przenosi obowiązek aktualizacji na tego, kto ma najmniej powodów, żeby o nim wiedzieć. Trzydzieści
dywizji to trzydzieści kopii walidatora, z których każda starzeje się osobno.

### Konsekwencje

* Repozytorium dywizji odwołuje się do **dwóch** repozytoriów: publicznego startera (`uses:`, bez tokenu)
  i prywatnego perimetru (release'y, tokenem aplikacji). To jest widoczne w workflow i ma być widoczne.
* Przypięcie `@<SHA>` przestaje być higieną, a staje się **granicą zaufania**: starter jest publiczny,
  więc referencja ruchoma oddaje kod uruchamiany z poświadczeniem dywizji temu, kto kontroluje gałąź.
  Selftest odrzuca `@main`, `@master` i `@v*` w przykładzie; SHA-a w szablonie nie wymaga, bo przykład
  nie może przypiąć commita, który powstanie dopiero po jego zmergowaniu.
* Organizacja, która chce mieć własne źródło akcji, publikuje **publiczną kopię startera** i wskazuje ją
  w `uses:` — nic w akcji nie nazywa organizacji, projektu ani perimetru; wszystko środowiskowe wchodzi
  wejściami (`perimeter-repo`, `member-file`, `app-token`) albo przyjeżdża w kontrakcie.

---

## DEC-22 — Kanał wejściowy MINTUJE token Appa w przebiegu; sekret trzyma KLUCZ, nie token

**Decyzja.** Trzy workflow, które w repozytorium perimetru dotykają gałęzi i pull requestów kanału
wejściowego — `intake.yml`, `external-intake.yml`, `intake-rebase.yml` — wołają
`actions/create-github-app-token` i biorą poświadczenie z jego outputu:

```yaml
- name: token instalacji Appa (gdy App jest skonfigurowany)
  id: app
  if: vars.INTAKE_APP_ID != ''
  uses: actions/create-github-app-token@<40-znakowy SHA>
  with:
    app-id: ${{ vars.INTAKE_APP_ID }}
    private-key: ${{ secrets.INTAKE_APP_KEY }}
    owner: ${{ github.repository_owner }}
    repositories: ${{ github.event.repository.name }}
# …
    token: ${{ steps.app.outputs.token || github.token }}
```

Zakres aplikacji: `Contents: Read and write` + `Pull requests: Read and write`, instalacja **wyłącznie**
na repozytorium perimetru. Sekret `INTAKE_PR_TOKEN` — miejsce na gotowy token — **znika**.

**Powód 1: token instalacji żyje GODZINĘ.** Poprzedni kształt (`secrets.INTAKE_PR_TOKEN || github.token`)
mówił „wklej tu token instalacji Appa". Taki sekret działa do końca dnia i milknie nazajutrz, bez żadnej
zmiany w kodzie ani w konfiguracji, która by to tłumaczyła. W kanale odpalanym rzadko oznacza to awarię
odkrywaną przy zgłoszeniu, którego akurat nikt nie chce debugować. Do sekretu nadaje się **klucz
prywatny** aplikacji — ważny do odwołania. Token ma powstawać na przebieg.

**Powód 2: przełącznik repozytorium NIE jest alternatywą — i to jest zmierzone, nie wywnioskowane.**
Nasuwająca się „naprawa" brzmi: włącz *Allow GitHub Actions to create and approve pull requests*
(`can_approve_pull_request_reviews`) i zostaw `GITHUB_TOKEN`. Pomiar (2026-08-11, #1977, przełącznik
włączony na kilka minut za zgodą właściciela repozytorium): PR **powstaje**, przebiegi `pull_request`
też powstają — po jednym na `validate` i `plan` — ale każdy jest `completed` / `action_required` /
`jobs: []`. Na PR-ze `check-runs.total_count` = **0**, status zbiorczy `pending` z zerem wpisów,
`gh pr checks` → „no checks reported", a PR mimo to **MERGEABLE**. Kontrola wiążąca to z TOKENEM, a nie
ze ścieżkami triggera: `action_required` wystąpiło na dokładnie tych dwóch przebiegach ze stu ostatnich,
przy ludzkich PR-ach tego samego dnia z zielonymi `validate`+`plan`.

Przełącznik zamienia więc kanał **niedziałający** na kanał **omijający wszystkie bramki** — schema, OPA,
budżet i `plan` wiszą na `pull_request`. Naiwna naprawa jest gorsza od usterki, więc
`can_approve_pull_request_reviews` zostaje `false`, a poświadczenie zmienia się zamiast ustawienia.

**Powód 3: fallback jest częścią decyzji, nie niedoróbką.** Krok mintujący jest warunkowy, bo bez tego
repozytorium bez aplikacji wywracałoby się na `Set up job` zamiast paść tam, gdzie pada dziś — na kroku
otwarcia PR-a, głośno, ze sprzątnięciem wypchniętej gałęzi. Warunek stoi na **zmiennej**, nie na sekrecie,
bo kontekst `secrets` nie jest dostępny w `if:` kroku. Wyrażenie `steps.app.outputs.token || github.token`
znosi krok pominięty: odczyt pola nieobecnego w kontekście daje w wyrażeniach GitHub Actions wartość
pustą, a nie błąd.

**Kontrola, bez której ten fallback jest deklaracją** i którą wykonuje się na wdrożeniu **przed**
założeniem aplikacji: przelot kanału ma dać **ten sam** wynik co przed zmianą — kroki walidacyjne
zielone, stop dokładnie na kroku otwarcia PR-a z komunikatem
`GitHub Actions is not permitted to create or approve pull requests`, gałąź sprzątnięta. Inny wynik —
w szczególności padnięcie na `Set up job` albo na kroku mintującym — znaczy, że warunek albo wyrażenie
tokenu nie znoszą braku aplikacji. Zapis pomiaru należy do dokumentacji wdrożenia, nie do szablonu.

**Powód 4: dwie ścieżki uwierzytelnienia to dwa tryby awarii.** Rozważone i **odrzucone**: zostawić
`secrets.INTAKE_PR_TOKEN` jako drugą drogę (`steps.app.outputs.token || secrets.INTAKE_PR_TOKEN ||
github.token`). Kosztuje jedną linijkę i dokłada pytanie „którym poświadczeniem poszedł ten przebieg"
do **każdej** diagnozy kanału — przy czym odpowiedzi nie widać w logu, bo obie wartości są maskowane.
Sekret bez właściciela i bez daty ważności żyje w ustawieniach repozytorium latami; ten akurat trzymałby
`Contents: write` na granicy. Jedna droga, jeden tryb awarii.

### Alternatywy odrzucone

**1. Personal Access Token człowieka w sekrecie.** Działa od ręki i nie wymaga zakładania aplikacji.
Odrzucone: wiąże zmianę granicy z **kontem osoby** (odejście z zespołu = cichy zanik kanału), ma zakres
konta, a nie repozytorium, i wygasa w terminie, o którym nie wie nikt poza jego właścicielem. PR-y
kanału podpisywałaby wtedy osoba, która ich nie widziała.

**2. Jedna aplikacja do wszystkiego (ta sama, co w kanale dywizji).** Odrzucone i to jest granica
bezpieczeństwa, nie porządek: aplikacja dywizji ma klucz **w repozytorium dywizji**. Dołożenie jej
`Contents: write` na repo perimetru dałoby dywizji prawo zapisu do kodu granicy, obok bramek wiszących
na `pull_request` — dokładnie ta ścieżka, którą zamknęło zawężenie kanału do `workflow_dispatch`.
Dwa różne zakresy mieszkają w dwóch różnych miejscach; rozdzielenie kluczy jest tu całą różnicą.

**3. `Pull requests: Write` bez `Contents: Write`.** Odrzucone po przeczytaniu tego, co robi krok:
`create-pull-request` najpierw **wypycha gałąź**, a dopiero potem woła API pull requestów, a
`intake-rebase.yml` dodatkowo force-pushuje gałęzie kanału. Bez `Contents: write` kanał padałby o krok
wcześniej niż dziś. `Pull requests` zostaje `Read and write` — token może PR-a otworzyć, a **nie może go
zatwierdzić ani zmergować**: bot proponuje, bramki oceniają, człowiek merguje.

### Konsekwencje

* Wdrożenie ma dwie pozycje „wymaga człowieka" zamiast jednej: aplikacji nie da się utworzyć przez API.
  Do czasu, aż powstanie, kanał **jest niedziałający i wygląda na niedziałający** — to stan świadomy.
* Zmienna `INTAKE_APP_ID` jest jawna z premedytacją. To identyfikator, nie poświadczenie, a warunek na
  czymś jawnym jest jedyną drogą do warunkowego kroku (`secrets` nie ma w `if:`).
* `owner`/`repositories` czytane z kontekstu przebiegu zawężają token do jednego repozytorium także
  wtedy, gdy ktoś zainstaluje aplikację szerzej — konfiguracja instalacji nie jest wtedy jedyną obroną.
* Selftest pilnuje trzech własności naraz: każdy z trzech workflowów mintuje token, każdy ma warunkowy
  krok i wyrażenie z fallbackiem, i **żaden** workflow nie czyta gotowego tokenu z własnego sekretu.

---

## DEC-23 — Zgoda Security na wypuszczenie danych poza Google Cloud jest WPISEM w pliku, którego Security jest właścicielem, a nie approvalem w GitHubie

**Decyzja.** Wpis członka, który wybiera profil `risk: high` (czyli taki, którego reguła egress ma
`to_external_from` — cel poza Google Cloud) i podaje niepusty cel, jest **odrzucany**, dopóki
`perimeter/policy.yaml` §`egress_approvals` nie niesie **ważnej** zgody nazywającej tego członka, ten profil
i **dokładnie te cele**. Zgoda ma obowiązkowe `expires` i uzasadnienie ≥ 40 znaków. Egzekwuje to reguła
`vpcsc.onboarding`, uruchamiana przez akcję `bramki-tresci`, czyli **na obu torach — pull request i apply**.

Razem z tym: `risk` przestaje być etykietą opisową i staje się **wejściem bramki**, więc druga reguła nie
pozwala mu zaniżyć kształtu (egress poza Google Cloud ⇒ `high`; jakikolwiek egress ⇒ nie `low`). Pole
`exceptions[]` w pliku członka **znika** (sprostowanie do DEC-3). CODEOWNERS przestaje obiecywać ścieżkę,
której nie ma, a `tools/codeowners_check.py` pilnuje jedynej własności, na której ten układ stoi.

**Kontekst — co było zmierzone.** `perimeter/projects.yaml` ma w CODEOWNERS wyłącznie zespół sieciowy.
Profil `bq-omni-external-read` jest jedyną regułą w katalogu, która pozwala danym opuścić Google Cloud,
a wchodzi do granicy **edycją tego pliku**. Cztery miejsca twierdziły, że wymaga to zgody Security
(komentarz `risk` w profilu — *„steruje ścieżką review (validate.yml)"*, nagłówek `bq-omni-external-read`,
`docs/5-servicenow-intake.md`, DEC-3), a mechanicznie nie robiło tego nic:
`grep -rn "risk" terraform/ policy/ .github/` → publikacja w kontrakcie, enum w schemacie, asercja w tftest.
**Zero bramek.** Ten sam defekt drugi raz: `exceptions[]` miało schemat, regułę OPA i wpis w CODEOWNERS,
a `grep -rn "exceptions" terraform/` → zero. Zadeklarowana kontrola, której nie ma, jest gorsza od jej braku,
bo produkuje fałszywe poczucie pokrycia — i jest to dokładnie ta klasa, którą rozpoznaje DEC-20.

### Dlaczego reguła, a nie CODEOWNERS

**1. Rozdzielenie idzie po ZAWARTOŚCI, nie po ścieżce.** Wniosek o profil zewnętrzny i wniosek o zwykły
serving to ta sama linia w tym samym pliku. CODEOWNERS dopasowuje **ścieżki**, więc albo Security recenzuje
wszystkie wnioski (przy ~50 miesięcznie: recenzja, która najpierw staje się pieczątką, a potem znika), albo
żaden. Rozdzielenie po treści jest z definicji regułą polityki, nie regułą własności pliku.

**2. Bez ochrony gałęzi CODEOWNERS nie jest egzekwowany przez NIC.** Na repozytorium prywatnym w darmowym
planie `branches/main/protection` i `rulesets` odpowiadają `403 Upgrade to GitHub Pro`, więc
`require_code_owner_reviews` nie ma gdzie zadziałać, a commit wypchnięty prosto na gałąź domyślną omija cały
tor pull requesta. Reguła jedzie w `bramki-tresci`, czyli **także na ścieżce apply** (DEC-16) — zatrzymanie
następuje u **mutatora**, a nie przy przycisku w GitHubie. To jest ta sama konstrukcja, którą DEC-17 zastosował
do promocji: rozpoznanie po **treści deklaracji**, zatrzymanie na ścieżce, którą realnie zmienia się granicę.

**3. Zgoda ma być artefaktem, nie kliknięciem.** Approval w GitHubie nie ma daty ważności, nie mówi CZEGO
dotyczył i znika z historii przy pierwszym force-pushu. Wpis w `policy.yaml` jest diffowalny, wygasa sam
i wymienia cele — a `policy.yaml` **jest** plikiem Security w CODEOWNERS.

### Dlaczego nie rozszerzenie bramki promocji (DEC-17)

Kusi, bo problem wygląda podobnie: nieodwracalny skutek, którego `git revert` nie cofa. Ale tamta bramka pyta
o **MOMENT** („czy wykonanie tego apply, teraz, zacznie komuś odmawiać") i zwalnia ją pole formularza
`workflow_dispatch`, wpisywane przez osobę **uruchamiającą apply**, czyli zespół sieciowy. Zgoda Security
przeniesiona do tamtego pola byłaby zgodą wpisywaną przez zatwierdzanego — czyli dokładnie defektem, który ta
decyzja zamyka, tylko przeniesionym o jeden plik dalej. Dodatkowo treść pola formularza nie zostaje w repo:
nie ma daty ważności, nie da się jej zrecenzować przed uruchomieniem ani odtworzyć po fakcie.

To jest pytanie o **TREŚĆ** deklaracji, więc mieszka tam, gdzie reszta pytań o treść, i wykonuje się na obu
torach. Rozdział „treść kontra moment" pozostaje dokładnie tam, gdzie postawił go DEC-16.

### Dlaczego bramka pyta o STAN, a nie o PRZEJŚCIE (i dlaczego to nie łamie DEC-18)

DEC-18 przestawił bramkę promocji na pytanie o przejście, bo jej dowód **odwraca znaczenie**: po promocji te
same naruszenia są odmowami, czyli miarą sukcesu — reguła pytająca o stan zamieniała się w blokadę repo
wyzwalaną przez poprawne działanie granicy (zmierzone: 2 odrzucenia na wnioskach niezwiązanych z promocją).

Tutaj nic się nie odwraca. „Ta dywizja może wysyłać dane do `s3://X`" jest uprawnieniem **stojącym** i musi
być pokryte tak długo, jak długo reguła stoi w granicy. To jest klasa `review_by`, nie klasa dowodu naruszeń:
wygaśnięcie zgody **ma** zatrzymać repozytorium, bo zatrzymanie jest tańsze niż niepokryta droga wyjścia
danych. Konsekwencja jest realna i świadoma: przeoczona data odnowienia czerwieni każdy pull request, dopóki
ktoś nie odnowi zgody jednolinijkowym PR-em w `policy.yaml`. Dlatego wzorcem w szablonie jest `expires` równe
`review_by` członka — uprawnienie do wyprowadzania danych nie ma prawa przeżyć przeglądu wpisu, który je nosi.

### Zakres — co bramkujemy, a czego świadomie nie

| zmiana | bramka maszynowa | dlaczego |
|---|---|---|
| wpis członka wybiera profil `risk: high` z niepustym celem | **TAK** | jedyna droga wypłynięcia danych poza Google Cloud; plik jest osiągalny dla trzech kanałów wejścia, a Security nie jest jego właścicielem |
| profil dostaje regułę egress poza Google Cloud (osobny PR) | **TAK, tą samą regułą** | reguła siedzi na deklaracjach, więc członkowie tego profilu stają się wnioskami wysokiego ryzyka w tej samej sekundzie — bez PR-a u siebie |
| `risk` profilu zaniżony do `low`/`medium` | **TAK** | to jest najtańsze obejście bramki: jedna linia w katalogu |
| egress **w granicach** Google Cloud (`to_projects_from`) | nie | cel zostaje w audycie Google, pod IAM i org-policy organizacji; objęcie tego bramką wciągnęłoby profil treningowy, czyli rutynę — a bramka na rutynie zostaje wyłączona |
| zmiana `restricted_services`, `contributors.yaml`, `control_plane_projects`, `access-levels/` | nie | **żaden kanał wejścia nie pisze do tych plików** — pisze do nich wyłącznie zespół platformy, a pliki są już pod CODEOWNERS obu zespołów. Bramka byłaby Security bramkującym Security. Zmiany `restricted_services` w dół pilnuje osobno reguła baseline'u (aiplatform), a `control_plane_projects` — `control_plane_check.py` |

Kryterium jest jedno i warto je nazwać wprost: **bramka stoi tam, gdzie zmianę może wywołać ktoś inny niż
właściciel kontroli.** Gdzie autor i właściciel to ten sam zespół, dokładamy szum, nie kontrolę.

### Co zrobiliśmy z `risk` i `exceptions`

* **`risk` — podpięte.** Uruchamia wymóg zgody Security i samo jest sprawdzane wobec kształtu profilu.
  Komentarz *„steruje ścieżką review (validate.yml)"* stał się prawdziwy, bo `validate.yml` woła
  `bramki-tresci`, a te wołają regułę. Usunięcie pola byłoby drugą opcją, ale `risk` jedzie w kontrakcie do
  dywizji wybierających profil — jest im potrzebne, więc taniej jest uczynić je prawdziwym niż wyciąć.
* **`exceptions` — usunięte.** Podpięcie wymagałoby zbudowania w rendererze **drugiej ścieżki renderowania
  reguł** (surowy ingress/egress per członek, poza katalogiem) — przy czterech profilach i zerowym użyciu pola
  to jest dokładnie ten gold-plating, który to repozytorium odrzuca. Usunięcie jest przy tym **zacieśnieniem**,
  a nie sprzątaniem: schemat dopuszczał tam `kind: egress` z dowolnym `to_projects`, dowolnymi tożsamościami
  i progiem uzasadnienia 20 znaków, **bez** własności Security. Gdyby ktoś kiedyś „dokończył" renderer, najszersza
  droga wyjścia danych w całym systemie byłaby tą z najsłabszą kontrolą. `additionalProperties: false` zamienia
  cichą atrapę w twardą odmowę wskazującą katalog profili.

### Odrzucone

* **Security jako CODEOWNER `perimeter/projects.yaml`.** Najprostsze i pozornie oczywiste. Odrzucone: nie
  odróżnia wniosku wysokiego ryzyka od rutynowego (jeden plik, jedna ścieżka), więc przy ~50 wnioskach
  miesięcznie produkuje recenzję, którą pierwszy pośpiech zamienia w pieczątkę — a drugi w usunięcie linii.
  I tak nie działa bez ochrony gałęzi.
* **Zgoda jako pole w pliku członka** (`security_approved_by:`). Odrzucone z tego samego powodu, dla którego
  `promotion_waivers` nie mieszkają w pliku członka: dywizja zwalniałaby się z bramki własnym pull requestem.
* **Zgoda jako etykieta pull requesta albo nazwa gałęzi.** Odrzucone — rozpoznanie musi iść z **treści**, nie
  z metadanych, których autor wniosku jest właścicielem. Ta sama lekcja co bramka baseline'u rozpoznawana po
  tytule; metadanych nie widać też na ścieżce apply.
* **Flaga `risk: high` sama jako bramka, bez sprawdzania kształtu.** Odrzucone: obejściem byłaby jedna linia
  w profilu, a bramka, którą wyłącza się edycją etykiety, jest bramką tylko z nazwy.
* **Zgoda bez `destinations`** („ten członek może używać tego profilu"). Odrzucone: cel jest całym ryzykiem,
  a jego podmiana byłaby rutynowym diffem w pliku członka, przechodzącym pod zgodą wydaną na coś innego.
* **Twardy błąd na placeholderach `@your-org/*` w CODEOWNERS.** Odrzucone: na koncie prywatnym zespołów
  GitHuba **nie da się utworzyć**, więc byłaby to bramka, którą w jej własnym środowisku testowym trzeba
  trwale wyłączyć — czyli wyłącznik z dobrą opinią. `codeowners_check.py` nazywa je przy każdym przebiegu
  jako niedokończoną konfigurację, a twardo pilnuje **relacji zbiorów właścicieli**, która jest prawdziwa
  także na placeholderach i przeżywa każde przemianowanie zespołów.

### Konsekwencje

* Zgoda Security jest **czytelna dla audytora bez dostępu do GitHuba**: jeden plik, wiersz na decyzję, z datą
  ważności i wymienionymi celami.
* Wygasła zgoda zatrzymuje **każdy** pull request w repozytorium — świadomie. Odnowienie to jednolinijkowy PR
  w pliku, którego właścicielem jest Security.
* Katalog profili staje się **jedyną** drogą dołożenia reguły. Pierwszy przypadek spoza katalogu wymaga
  profilu, nie pola w pliku wnioskodawcy.
* CODEOWNERS przestaje być mechanizmem, na którym stoi jakakolwiek własność bezpieczeństwa tego repozytorium,
  i mówi to o sobie wprost. Na GitHub Enterprise, gdzie ochrona gałęzi istnieje, dokłada drugą warstwę —
  ale pierwsza działa bez niego.

---

## DEC-24 — Pre-flight jest bramką na OBU torach, pyta tożsamością `plan` i tylko o WCHODZĄCYCH

**Decyzja.** `tools/preflight_check.sh` przestaje być narzędziem bez wyzwalacza. Uruchamia go
`tools/preflight_gate.py` przez akcję złożoną `.github/actions/bramka-preflightu`, wołaną z **osobnego
joba** w `plan.yml` (tor pull requesta) i w `apply.yml` (mutator); `plan` i `apply` mają ten job w `needs`,
więc czerwony pre-flight zostawia je w stanie `skipped`. Bramka pyta o **członków wchodzących do granicy** —
zadeklarowanych w `perimeter/projects.yaml`, których numeru nie ma jeszcze ani w `spec.resources`, ani
w `status.resources` żywego perimetru. Uwierzytelnia się kontem **`plan`** na obu torach. Nie przekazuje
`--identity`.

**Dlaczego to w ogóle wymaga decyzji.** Bo przez cały czas istnienia tego repozytorium pre-flight
**nie był wołany przez nic**: `grep -rn preflight_check` po `.github/`, `tools/` i pre-commicie dawał zero
trafień w czymkolwiek wykonywalnym, a cztery różne miejsca w materiale — w tym opis pull requesta, który
czyta recenzent — twierdziły, że jedzie automatycznie. Sam DEC-5 nazywał go bramką *egzekwowaną* i odrzucał
wariant „pre-flight jako ostrzeżenie" zdaniem *„ostrzeżenie w PR-ze, który i tak scala bot, nie jest bramką"* —
a on nie był wtedy nawet ostrzeżeniem. Narzędzie zdążyło doczekać się **dwóch rund poprawek** (pięć defektów,
potem cichy no-op checku kolizji przy więcej niż jednym zasobie w konfiguracji), czyli poprawiano skrypt,
którego nikt nie uruchamiał. To jest wzorzec „kontrola celująca w pustkę" w najczystszej postaci: kontrola,
która wygląda na obecną, kosztuje utrzymanie i nie zamyka ani jednego trybu awarii.

Tryb awarii, który ma zamykać, jest przy tym cichy i **opóźniony o cały okres obserwacji**: projekt bez
Private Google Access i bez prywatnej strefy DNS wchodzi do dry-run z kompletem zielonych bramek, przechodzi
okno „czysto" (bo nic w nim nie chodzi) i **umiera w dniu promocji** — ruch idzie publicznym endpointem
i zostaje odcięty. Wygląda to wtedy jak „VPC-SC zepsuł nam deploy", a nie jak brakujący prereq sprzed
dwóch tygodni.

### Dlaczego zbiorem pracy jest RÓŻNICA ZE ŚWIATEM, a nie diff commitów

    zadeklarowani w perimeter/projects.yaml        ⟶  KTO MA BYĆ członkiem
    `spec.resources` ∪ `status.resources` (API)    ⟶  KTO JUŻ JEST w granicy
    różnica                                        ⟶  KOGO pyta pre-flight

Trzy niezależne powody:

1. **Diff znika razem ze zdarzeniem.** `workflow_dispatch`, `gh run rerun` i apply po nieudanym apply nie
   mają żadnego diffa, a stosują dokładnie tę samą treść. Bramka na diffie byłaby nieobecna w tych trzech
   przebiegach — czyli tam, gdzie człowiek patrzy najmniej. Ten sam argument stoi za DEC-17.
2. **Diff zablokowałby własne lekarstwo.** Pull request USUWAJĄCY martwego członka (projekt skasowany,
   `DELETE_REQUESTED`) dotyka jego wpisu, więc bramka na diffie odpaliłaby pre-flight na projekcie, którego
   już nie ma, dostała `BŁĄD` i zatrzymała jedyną zmianę naprawiającą ten stan. Pre-flight nie może być
   bramką na istnienie członków **już obecnych** — to zostało rozstrzygnięte wcześniej i tu nie wraca.
3. **Ten sam zbiór na obu torach, bez ani jednego `if`.** Porównanie ze światem daje identyczny wynik na
   pull requeście i u mutatora, więc jedna definicja bramki wystarcza (DEC-16).

Konsekwencja kosztowa jest wprost mierzalna i to ona rozstrzyga pytanie o skalę: przy ustabilizowanym
perimetrze różnica jest **pusta**, więc bramka kosztuje **jeden** odczyt ACM na przebieg — tak samo przy
pięciu członkach, jak przy pięciuset. Ten jeden odczyt (`perimeters list`) jest jednocześnie odczytem,
którego potrzebuje check kolizji perimetrów, więc jedzie do skryptu plikiem (`--lista-perimetrow`) zamiast
być powtarzany per kandydat. Przy partii 50 wniosków to różnica między 1 a 51 odczytami na limicie
500/min, który jest najciaśniejszą kwotą w tym stosie.

### Dlaczego tożsamość `plan`, skoro `bramki-zywe` pytają tożsamością mutatora

To jest świadome **odstępstwo** od reguły z DEC-16 i ma dwa oparcia.

**Pomiar.** Konto `apply` nie ma ANI JEDNEJ z ról pre-flightu — jego uprawnienia to własna rola zapisu na
perimetrze plus dostęp do bucketa stanu. Role read-only potrzebne pre-flightowi (`cloudasset.viewer`,
`compute.networkViewer`, `dns.reader`, `policyReader`) ma konto `plan`. Dołożenie ich kontu `apply`
powiększyłoby zbiór uprawnień, których brak **zatrzymuje jedyną drogę wdrożenia** — i dokładnie ten tryb
awarii już raz wywrócił apply w tym repozytorium. Bramka zabezpieczająca onboarding nie ma prawa być nową
przyczyną zatrzymania deployu.

**Argument merytoryczny.** Reguła „bramka żywa pyta tożsamością mutatora" broni przypadku, w którym
**tożsamość jest treścią pytania**: „czy JA widzę własny bucket stanu" ma inną odpowiedź dla `plan`
i dla `apply`, i różnica wyszłaby dopiero jako czerwony apply. Tutaj podmiotem jest cudzy projekt:
„czy podsieci kandydata mają Private Google Access" ma tę samą odpowiedź niezależnie od pytającego.
Odstępstwo dotyczy więc dokładnie tych bramek, dla których uzasadnienie reguły nie zachodzi.

To działa, bo `principalSet` konta `plan` celuje w `attribute.repository`, czyli w **każdy** workflow tego
repozytorium — także uruchomiony pushem na gałąź domyślną. (Komentarz w `plan.yml` twierdził wcześniej, że
provider WIF przypina to konto do `event_name == 'pull_request'`; to nieprawda i zostało poprawione w tym
samym miejscu, bo cała ta decyzja stoi na tym fakcie.)

### Co robi, gdy nie może sprawdzić — per check, i dlaczego akurat tak

Fail-open w bramce bezpieczeństwa jest gorszy od jej braku, bo wygląda na obecną. Fail-closed na cudzym
projekcie potrafi jednak zatrzymać onboarding z powodu, na który wnioskodawca nie ma wpływu. Podział idzie
więc po tym, **kto jest właścicielem naprawy**:

| sytuacja | werdykt | dlaczego |
|---|---|---|
| nie udało się odczytać listy perimetrów (bramka nie wie, KTO wchodzi) | **czerwono** | „nie wiem, kto wchodzi" ≠ „nikt nie wchodzi". Przepuszczenie dałoby dokładnie tę własność, którą ta decyzja naprawia |
| projekt nie istnieje / brak dostępu odczytu (check 1) | **czerwono** | Resource Manager tych dwóch przypadków **nie rozróżnia**; skrypt mówi to wprost i wskazuje, kto rozstrzygnie, zamiast zgadywać |
| kolizja perimetrów nieodczytana (check 2) | **czerwono** | to odczyt NASZEJ organizacji NASZĄ tożsamością; porażka jest naszym problemem, a obecność w cudzej konfiguracji egzekwowanej to twarde ograniczenie ACM — apply padłby po review |
| PGA / DNS nieodczytane (checki 3–4) | **czerwono** | brak roli u wołającego jest naprawialny i głośny; fail-open kasowałby bramkę dokładnie w tych wdrożeniach, w których zakres ról zawężono z organizacji do folderów dywizji — czyli w tych, które zrobiły więcej dla least-privilege |
| projekt bez sieci VPC (checki 3–4) | **N/D** | członkostwo w perimetrze nie wymaga ani jednej maszyny; „zawsze wymagaj" kazałoby poprawnemu kandydatowi zbudować sieć, której nie potrzebuje |
| billing nieodczytany (check 1b) | **uwaga** | hipotezę „brak billingu blokuje API" zmierzono i **obalono dwa razy**; twardy błąd zatrzymywałby kandydata poprawnego |
| endpointy Vertex nieodczytane (check 5) | **uwaga** | to ostrzeżenie o KOLEJNOŚCI tworzenia zasobów, stan naprawialny po fakcie |

### Czego ta bramka świadomie NIE robi

**Nie woła checku 6 (`--identity`).** Wymaga on `iam.serviceAccounts.get`, którego wdrożenie nie nadaje —
więc wpięty byłby fail-closed na **każdym** wniosku, z powodu leżącego w naszej konfiguracji. Nadanie
`roles/iam.serviceAccountViewer` kontu `plan` — impersonowalnemu z **każdego** pull requesta — dałoby prawo
enumeracji wszystkich kont serwisowych organizacji, i to pod check zamykający tryb awarii, który ACM już
zamyka: literówkę w adresie odrzuca przy apply komunikatem `invalid or non-existent`, wywracając **całą**
zmianę, czyli głośno i na **nietkniętej** granicy. Ceną jest nieudany apply po review; ceną alternatywy
byłoby poszerzenie modelu uprawnień. Check zostaje narzędziem recenzenta uruchamianym z ręki i tak jest
opisany w `docs/5-servicenow-intake.md`.

**Nie pilnuje zmiany wpisu członka już obecnego w granicy.** Kształtu adresów pilnuje `perimeter.rego` na
każdym pull requeście, istnienia — ACM przy apply (jak wyżej). Objęcie tego przypadku wymagałoby diffa,
czyli powrotu wszystkich trzech problemów z sekcji o zbiorze pracy.

### Odrzucone

- **Pre-flight wyłącznie na torze `pull_request`.** Najtańsze i wprost sprzeczne z DEC-16: gałąź domyślna
  bywa bez ochrony (funkcja płatna na repo prywatnym), więc commit wypchnięty prosto na nią omija cały tor
  pull requesta i idzie do apply. Bramka stojąca tylko tam chroni pull requesta, a nie granicę.
- **Krok wewnątrz joba planującego/applikującego zamiast osobnego joba.** Odwraca kolejność kosztu
  i werdyktu: najpierw pełny plan i **zamek stanu**, potem informacja, że kandydat nie ma PGA. Osobny job
  daje `skipped` na planie i apply oraz — w `apply.yml` — zostaje wykonywalny z gałęzi testowej, bo nie
  deklaruje `environment`. Bez tej drugiej własności nie dałoby się ZOBACZYĆ, że bramka odrzuca, inaczej
  niż na żywej granicy.
- **Krok w `bramki-zywe`.** Tamten zestaw pyta o rzeczy należące do tego repozytorium i pyta tożsamością
  mutatora. Ta bramka różni się trzema własnościami naraz (uprawnienia na cudzych projektach, zbiór pracy
  z żywej granicy, naprawa po stronie kogoś spoza repozytorium). Wspólny plik schowałby tę asymetrię —
  a razem z nią odstępstwo w tożsamości, które ma być widoczne.
- **Uruchamianie pre-flightu dla wszystkich zadeklarowanych członków.** Przy 500 członkach to 500 przelotów
  po API na każdy pull request, przy limicie 500 odczytów/min. Bramka, która przy normalnym rozmiarze
  wdrożenia wpada we własną kwotę, jest bramką dopóty, dopóki wdrożenie jest małe.
- **`--warn-only` na ścieżce CI.** To jest dokładnie ten wariant, który DEC-5 odrzucił: ostrzeżenie w pull
  requeście, który i tak zostanie scalony. Flaga zostaje w skrypcie do użycia z ręki i nic jej nie podaje.
