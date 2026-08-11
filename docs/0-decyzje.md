# Decyzje, na których stoi ten starter (DEC-1…DEC-8)

Osiem rozstrzygnięć, które określają kształt repozytorium. Kod odsyła tutaj skrótem `DEC-1`…`DEC-8` — jeśli komentarz
w pliku mówi „(DEC-4)", to znaczy: „powód tej linijki jest opisany w DEC-4, nie zmieniaj jej bez przeczytania".

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
Po approvalu woła `repository_dispatch`; workflow **oddzwania do API systemu ticketowego** i weryfikuje, że ticket
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
- *Zaufanie payloadowi `repository_dispatch` bez oddzwonienia.* Dispatch jest tak wiarygodny jak token, który go
  wysłał — a tokeny wyciekają. Weryfikacja u źródła zamienia „ufam wiadomości" w „ufam systemowi rekordu".
- *Apply z laptopa operatora.* Brak przypiętego planu i powtarzalności; przy org-plane singletonie każdy ręczny
  apply to potencjalny wyścig z pipeline'em (DEC-6).

---

## DEC-3 — Katalog profili zamiast surowych reguł

**Decyzja.** Zespół wybiera **profil** z katalogu (`perimeter/profiles/*.yaml`), nie pisze reguł. Profil to
wersjonowany szablon reguł ingress/egress, sparametryzowany danymi członka (numer projektu, konta serwisowe, access
level). Reguły renderuje Terraform z pary (członek × profil) — nikt spoza zespołu platformy nie edytuje HCL. Ścieżka
wyjątku istnieje jawnie (`exceptions[]` w pliku członka, approval security, uzasadnienie); **trzeci taki sam wyjątek
to sygnał do stworzenia profilu**, nie do czwartego wyjątku.

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
