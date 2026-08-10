# examples/division-repo — repozytorium dywizji, kompletny przykład

To jest **druga strona granicy**: repozytorium zespołu, który prosi o zmianę w perimetrze VPC Service
Controls. Nie jest to repo perimetru i nie jest to nic, co się gdziekolwiek instaluje — to materiał
**do skopiowania do siebie**. Trzy pliki, około piętnastu minut.

```
examples/division-repo/
├── vpc-sc/request.yaml                    JEDYNY plik, który piszesz
├── github/workflows/vpc-sc-request.yml    → skopiuj do .github/workflows/ (tu bez kropki, patrz niżej)
└── README.md                              ten plik
```

> Katalog `github/` jest **bez kropki** celowo — tak samo jak w `template/` startera. Dopóki ten materiał
> leży w repozytorium, z którego się go kopiuje, ma być martwym tekstem: `.github/workflows/` ożyłoby
> tutaj jako prawdziwy workflow. Przy kopiowaniu do siebie dodajesz kropkę.

## Czego NIE dostajesz — i to jest sedno, nie zastrzeżenie

| Czego nie dostajesz | Dlaczego |
|---|---|
| **konta serwisowego w Google Cloud** | żadnego. Ani do Access Context Managera, ani do bucketa. Wszystko, czego potrzebujesz, pobierasz z release'ów repo perimetru **tokenem GitHuba** |
| **żadnej roli w Access Context Managerze** | `servicePerimeters.update` **nie da się zawęzić poniżej organizacji**. Grant „żebyście mogli sobie dodać projekt" jest w praktyce prawem zmiany granicy bezpieczeństwa całej firmy |
| **dostępu do stanu Terraform perimetru** | stan to pełna mapa granicy: wszystkie reguły, wszystkie tożsamości, wszystkie dywizje. Kto czyta stan, czyta wszystko |
| **wglądu w `perimeter/members/`** | konta serwisowe i grupy **innych** dywizji. Do zwalidowania swojego jednego pliku nie są potrzebne |
| **wglądu w `perimeter/access-levels/`** | korporacyjne zakresy IP i polityki urządzeń. Ty wskazujesz **nazwę** access levelu; jego treść jest implementacją, nie interfejsem |
| **prawa apply** | apply jest jeden, na jednym stanie, za środowiskiem z wymaganymi recenzentami |

**Jedno prawo, które dostajesz: doprowadzić do powstania pull requesta** — przez GitHub App na repo
perimetru. Zakres tego tokenu jest zmierzony i wychodzi inaczej, niż podpowiada intuicja: patrz sekcja
[Zakres tokenu](#zakres-tokenu--zmierzony-nie-wywnioskowany) niżej.

Co dostajesz w zamian za to, czego nie dostajesz: **walidację u siebie**. Twój pipeline mówi „ten profil
nie istnieje", „brakuje parametru", „ten projekt już jest w perimetrze" w kilka sekund — bez czekania
na czyjeś review i bez dostępu do czegokolwiek.

## Zakres tokenu — zmierzony, nie wywnioskowany

Intuicja podpowiada, że skoro kanał kończy się pull requestem, to token potrzebuje `pull_requests: write`.
Jest odwrotnie, w obie strony. Pomiar: `GITHUB_TOKEN` z `permissions:` zawężonym per job (ten sam model
uprawnień co instalacja GitHub Appa), cztery wywołania:

| Uprawnienia tokenu | Wywołanie | HTTP |
|---|---|---|
| `contents: read` + `pull-requests: write` | `POST /repos/{o}/{r}/dispatches` | **403** `Resource not accessible by integration` |
| `contents: write` | `POST /repos/{o}/{r}/dispatches` | **204** |
| `actions: write` | `POST /repos/{o}/{r}/actions/workflows/{plik}/dispatches` | **204** |
| `contents: write` **bez** `actions` | `POST /repos/{o}/{r}/actions/workflows/{plik}/dispatches` | **403** |

Czyli:

- **`repository_dispatch` wymaga `contents: write`** na repo perimetru. To jest ostatni krok akcji `contrib`
  i bez tego uprawnienia kończy się 403 — kanał nie działa.
- **`pull_requests` nie jest potrzebne w ogóle.** Pull requesta otwiera po swojej stronie
  `external-intake.yml`, własnym `GITHUB_TOKEN`-em repozytorium perimetru. Token dywizji nie woła ani
  jednego endpointu PR-owego.

**To jest niewygodne i lepiej to napisać, niż przemilczeć:** `contents: write` znaczy prawo zapisu do
repozytorium perimetru — więcej niż „otworzyć PR". Uprawnienia GitHuba nie mają ziarna „wyślij zdarzenie",
więc granica nie stoi na zakresie tokenu, tylko na trzech rzeczach poza nim:

1. `perimeter/contributors.yaml` **leży po tamtej stronie** — repozytorium dywizji nie może rozszerzyć
   własnej listy dozwolonych projektów, bo nie ma jej u siebie.
2. Payload dispatcha jest **danymi, nie autoryzacją**: repo perimetru konfrontuje `change_ref` z nadawcą
   zdarzenia i odrzuca rozjazd.
3. Apply wychodzi wyłącznie z gałęzi domyślnej repozytorium perimetru, przez environment `perimeter-apply`
   z polityką gałęzi.

Wiersze 3–4 tabeli pokazują wariant **węższy**, który istnieje: `workflow_dispatch` chodzi po osi `actions`,
a `actions` i `contents` są rozłączne w obie strony — token wysyłający zgłoszenie nie miałby wtedy prawa
zapisu do kodu. Kosztuje to zmianę po OBU stronach kanału (`contrib/action.yml` i `external-intake.yml`)
i ograniczenie payloadu do `inputs` workflowa, więc nie jest to poprawka w tym pliku. Zapisane jako
świadomy dług, nie przeoczenie.

## Dlaczego to NIE jest moduł Terraform wołany z waszego stanu

To jest najczęstsza kontrpropozycja i brzmi rozsądnie: „opublikujcie moduł, my go zawołamy u siebie —
kod jeden, a każdy zarządza swoim". Odpowiedź: **moduł przenosi KOD, a problemem jest STAN i TOŻSAMOŚĆ.**

- **Stan.** Access Context Manager modyfikuje politykę organizacji **jako całość** (read-modify-write).
  Dwa stany Terraform aplikujące równolegle do jednej polityki nie „scalają" swoich reguł — zapisują
  swoją wersję całości. Zmierzone: dwa równoległe apply na jednej polityce kończą się
  `Error 400: The eTag provided ... does not match` w **5/5 przebiegów**. Moduł tego nie zmienia:
  ten sam kod, wołany z dwóch stanów, daje dokładnie ten sam wyścig.
- **Tożsamość.** Żeby zawołać taki moduł, wasze konto potrzebuje `servicePerimeters.update` **na
  organizacji** — patrz tabela wyżej. Moduł nie zmniejsza tego wymagania ani o jedno uprawnienie.

Ten sam eksperyment można powtórzyć u siebie: `experiments/race-two-states/` w starterze uruchamia
oba apply równolegle, czyta perimetr z API i sprząta. Zero kosztu — ACM jest darmowy. Warto to zrobić,
zanim ktoś rozstrzygnie sprawę opinią.

Dwie inne odrzucone drogi, dla kompletu:

- **Submodule repo perimetru u was.** Oddaje CAŁE repozytorium — `members/` wszystkich dywizji
  i zakresy IP z `access-levels/` — po to, żeby zwalidować jeden wasz plik. Sparse checkout tego nie
  naprawia: ogranicza working tree, nie historię, więc `git log`/`git show` nadal sięga wszystkiego.
- **Kopiowanie listy profili do dokumentacji.** Rozjedzie się w pierwszym tygodniu, a walidacja lokalna
  potrzebuje danych maszynowo czytelnych, nie tabelki. Stąd kontrakt.

## Co robi ten przykład, krok po kroku

1. Piszesz **`vpc-sc/request.yaml`** — jeden plik, tylko to, co wiesz o sobie: dywizja, projekt i jego
   numer, grupa właścicielska, wybrany **profil** z parametrami. Nie piszesz reguł ingress/egress.
2. Otwierasz PR. Job `walidacja` pobiera **paczkę bramek** (reguły) i **kontrakt** (lista dostępnych
   profili, nazw access levels i twoich projektów) z release'ów repo perimetru i sprawdza deklarację
   u ciebie.
3. Po merge'u job `zgloszenie` woła akcję `contrib`, która waliduje jeszcze raz (kontrakt mógł się
   w międzyczasie zmienić) i wysyła `repository_dispatch` do repo perimetru.
4. Repo perimetru sprawdza, czy **to repozytorium** ma ten projekt na liście dozwolonych
   (`perimeter/contributors.yaml`) i czy dywizja się zgadza — po czym otwiera u siebie PR.
5. Sieć i security zatwierdzają. Apply dodaje projekt do konfiguracji **dry-run**: nic nie jest
   blokowane i nic nie jest jeszcze chronione.
6. Po oknie obserwacji dostajesz raport naruszeń. Promocja do stanu chronionego to **osobny PR
   z człowiekiem** — nigdy automat, nigdy pole w twoim pliku.

## Czterech pól nie ma w `request.yaml` celowo

`stage`, `dry_run_since`, `review_by`, `change_ref` — wypełnia je **druga strona granicy**. Powody są
w komentarzu w samym pliku; dwa najważniejsze:

- **`stage`** decyduje, czy projekt trafia do konfiguracji egzekwowanej. Gdyby wnioskodawca mógł podać
  `enforced`, ominąłby całą dwustopniowość onboardingu jednym polem — i odciąłby sobie ruch w minutę
  po merge'u, zanim ktokolwiek zmierzył jego przepływy.
- **`dry_run_since`** to data startu okna obserwacji. Data wsteczna sprawia, że bramka promocji liczy
  okno jako dawno minione — czyli kasuje pomiar, dla którego cały mechanizm istnieje. **Pole opisujące
  czas pomiaru nie może pochodzić od mierzonego.**

Wniosek jest więc **węższy** niż plik członka w repo perimetru. To celowe: pola, których nie
kontrolujesz, wpisywane „żeby przeszło", są dokładnie tymi, których nikt potem nie czyta.

## Zanim to zadziała u ciebie

| Co | Gdzie | Kto ustawia |
|---|---|---|
| GitHub App zainstalowana na obu repozytoriach (`contents: write` na repo perimetru — patrz §„Zakres tokenu"; `pull_requests` NIE jest potrzebne) | `vars.VPCSC_APP_ID`, `secrets.VPCSC_APP_KEY` | ty, raz, **przez interfejs GitHuba** — aplikacji nie da się utworzyć przez API |
| wpis w `perimeter/contributors.yaml`: to repozytorium → twoja dywizja → dozwolone projekty | repo perimetru | **zespół sieciowy**, PR z approvalem |
| podmiana `ORG/gcp-vpc-sc` i `<SHA_WYDANIA>` w workflow | ten przykład | ty |

Drugi wiersz jest tym, którego nie da się załatwić u siebie — i to nie jest biurokracja. Gdybyś trzymał
listę swoich dozwolonych projektów we własnym repozytorium, rozszerzyłbyś ją **tym samym commitem**,
którym dodajesz projekt. To jedyna rzecz, której ten kanał nie może orzec sam o sobie.

## Walidacja bez pipeline'u

```bash
gh release download --repo ORG/gcp-vpc-sc --pattern gates.tar.gz --clobber && tar -xzf gates.tar.gz
gh release download contract --repo ORG/gcp-vpc-sc --pattern contract.json --clobber
./gates/validate-local.sh --member vpc-sc/request.yaml --gates ./gates --contract ./contract.json
```

Sam `gh`, żadnego `gcloud`. Sprawdza: strukturę pliku, istnienie profilu, komplet parametrów, istnienie
access levels, twoje uprawnienie do projektu i to, czy projekt nie jest już członkiem perimetru.
**Nie sprawdza** pre-flightu sieciowego (Private Google Access, strefa DNS na restricted VIP) ani kolizji
z inną konfiguracją egzekwowaną — jedno i drugie wymaga odczytu z żywego Google Cloud i robi to repo
perimetru.

Pełna instrukcja kanału, razem z tabelą najczęstszych odrzuceń, jest w `contrib/README.md` repozytorium
perimetru (w starterze: `template/contrib/README.md.example`).
