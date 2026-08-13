# Perimetr już istnieje — jak go przejąć pod Terraform, nie zrywając ochrony

Domyślny tryb startera jest **brownfield**: `perimeter.manage_skeleton: false` w `perimeter/policy.yaml`.
Terraform dokłada wtedy wyłącznie **członków i reguły**, a treść perimetru (`restricted_services`,
`vpc_accessible_services`) zostaje u obecnego właściciela.

Ten dokument opisuje krok **następny**: przejęcie szkieletu, czyli przejście do `manage_skeleton: true`
na perimetrze, którego **nie tworzyliśmy**.

> **Stan dowodu.** Procedura niżej została **przelotowana od zera na żywym Access Context Managerze**
> (perimetr jednorazowy zbudowany `gcloud`-em, z cudzymi tytułami reguł i cudzą listą usług). Pomiar
> znalazł **cztery defekty**, które ta wersja naprawia — przed nim procedura nie kończyła się `No changes`
> ani razu, bo nie mogła. Liczby: w repozytorium wdrożenia, sekcja „przejęcie brownfieldowe".

## Najważniejsza odpowiedź: czy jest moment bez ochrony

**Nie ma — pod warunkiem, że idziesz przez `import`, a nie przez „utwórz".**

Powód jest mechaniczny, nie deklaratywny:

| krok | co robi z chmurą | dowód |
|---|---|---|
| `perimeter_to_policy.py --diff` | tylko `GET` | brak wpisu w audit-logu |
| blok `import {}` + `plan` | tylko `GET` — import zapisuje **stan Terraforma**, nie perimetr | **zero** wpisów `UpdateServicePerimeter` w oknie planu |
| `apply` pustego planu | jeden `UpdateServicePerimeter`, treść **egzekwowana identyczna** | zbiór `restrictedServices` przed = po; `resources`, `ingressPolicies`, `egressPolicies` bez zmian |

Ochrona nie znika, bo **nie ma kroku, który by ją zdejmował**: nie kasujemy perimetru, nie zawężamy
`restricted_services`, nie usuwamy reguł. `import` jest operacją na pliku stanu.

**Czego to NIE dowodzi.** „Zero okna" dotyczy ścieżki importu. Istnieje ścieżka, która okno **ma** —
przejmowanie **cudzych reguł** (niżej, §„Czego nie da się przejąć"). Tam okno jest realne i trzeba
je zaplanować.

## Krok 0 — inwentarz, zanim cokolwiek dotkniesz

Zrzut stanu faktycznego jest jedyną rzeczą, która pozwoli cofnąć pomyłkę. Zrób go **przed** wszystkim
i zachowaj poza repo.

```bash
gcloud access-context-manager perimeters describe <PERIMETR> \
  --policy=<POLICY_ID> --format=json > przed-przejeciem.json
```

Zapisz z niego trzy liczby — będą asercją na końcu: ile usług w `status.restrictedServices`,
ilu członków w `status.resources`, ile reguł `ingressPolicies` + `egressPolicies`.

> **`etag` NIE jest asercją.** Należy do **access policy**, nie do perimetru: zapis do *sąsiedniego*
> perimetru w tej samej polityce zmienia `etag` twojego, bez jednego bajtu różnicy w treści. Zmierzone.
> Porównuj **treść**, nie `etag` — inaczej zobaczysz „zmianę", której nie było, i cofniesz coś, co stoi dobrze.

## Krok 1 — bramka: czy `policy.yaml` opisuje rzeczywistość

To jest **bramka**, nie sprawdzenie z uprzejmości. Apply po imporcie wyrównuje chmurę do repo — więc
każda różnica, którą tu przemilczysz, wraca jako zmiana zakresu ochrony.

```bash
./tools/brownfield_import.sh --policy-id <POLICY_ID> --perimeter <PERIMETR>
```

Trzy możliwe wyjścia i **trzy różne reakcje** — nie myl ich:

| wyjście | znaczenie | co robisz |
|---|---|---|
| `ZGODNE` | pola porównywane przez skrypt się zgadzają | idziesz dalej, **czytając plan** |
| `STOP — policy.yaml NIE opisuje rzeczywistości` | są różnice, wypisane co do usługi | krok 2 |
| `AWARIA` (kod 3) | **porównanie się nie odbyło** | napraw narzędzie/uprawnienia; **to nie jest werdykt o perimetrze** |

Trzeci wiersz istnieje, bo go zabrakło: wrapper brał każdy niezerowy kod wyjścia za „są różnice",
a narzędzie porównujące **nie parsowało się w ogóle**. Operator dostawał wtedy wiarygodnie wyglądający
`STOP`, poprawiał `policy.yaml` i dostawał ten sam `STOP` — w nieskończoność, bo werdykt nie pochodził
z porównania. `403` z braku uprawnienia, brak perimetru i odmowa VPC-SC wyglądają w kodzie wyjścia tak
samo; rozstrzyga **treść**.

## Krok 2 — przepisz rzeczywistość DO pliku (nigdy odwrotnie)

```bash
python3 tools/perimeter_to_policy.py --policy-id <POLICY_ID> --perimeter <PERIMETR> > /tmp/live.yaml
```

Przenieś z `/tmp/live.yaml` do `perimeter/policy.yaml`: `perimeter.name`, `restricted_services`
i **`vpc_accessible_services`**. Powtarzaj krok 1, aż zobaczysz `ZGODNE`.

> **Kierunek jest całą treścią tego kroku.** Kusi, żeby „poprawić" chmurę do repo — to jest dokładnie
> ta zmiana, po której perimetr wygląda w konsoli na włączony, a nie chroni usług, o których nikt nie
> wiedział. Jeśli lista w chmurze jest **zła**, to osobna zmiana, z własnym ticketem i własnym apply —
> nie produkt uboczny przejęcia.

### Kiedy Twoje niezmienniki nie pasują do cudzego perimetru

Repo niesie twarde niezmienniki baseline'u — u nas „baseline musi zawierać `aiplatform.googleapis.com`",
egzekwowane w **trzech** miejscach naraz (`precondition` w `terraform/perimeter.tf`, `policy/perimeter.rego`,
`policy/onboarding.rego`). Na cudzym perimetrze, który chroni inne usługi, **plan nie ruszy**:

```
Error: Resource precondition failed
Baseline musi zawierać aiplatform.googleapis.com — bez niego perimetr nie chroni Vertex AI.
```

To nie jest usterka — to niezmiennik robiący swoją robotę. Masz dwie uczciwe drogi i **żadna nie polega
na usunięciu bramki**:

1. **Zmienić niezmiennik na własny** — jeśli przejmowany perimetr chroni co innego, opisz to w ADR
   i podmień usługę we wszystkich trzech miejscach. Niezmiennik ma zostać, ma tylko mówić prawdę.
2. **Poszerzyć baseline przejmowanego perimetru** — jeśli usługa faktycznie ma być chroniona.
   To **zmiana zakresu ochrony**, nie krok techniczny: własny ticket, własna zgoda, własne okno.

Czego nie robić: kasować `precondition`, żeby plan przeszedł. Wtedy przejęcie „się udaje", a granica
przestaje obiecywać cokolwiek.

## Krok 3 — blok `import` i przełącznik

```bash
./tools/brownfield_import.sh --policy-id <POLICY_ID> --perimeter <PERIMETR> --write-import
```

Zapisuje `terraform/zz_import_generated.tf` (blok `import {}`, widoczny w **planie** — reviewer nie musi
wierzyć, że ktoś uruchomił właściwą komendę CLI). W tym samym PR-ze ustaw `manage_skeleton: true`.

**Bez `manage_skeleton: true` zasób ma `count = 0` i import nie ma czego zaimportować.**

## Krok 4 — plan. To jest asercja, nie formalność

```bash
terraform -chdir=terraform plan -input=false -detailed-exitcode
```

| kod | znaczenie |
|---|---|
| **0** | pusto — dokładnie to, co chcesz |
| **2** | są zmiany — **czytaj pozycja po pozycji** |
| **1** | awaria — to nie jest różnica |

Przy pierwszym przejęciu kod **2** jest normalny i ma dokładnie jedną dopuszczalną treść:
**dodanie konfiguracji `spec` (dry-run)** wraz z `use_explicit_dry_run_spec = false -> true`. Perimetr
postawiony ręcznie zwykle nie ma `spec` w ogóle, a renderer ją tworzy. To zmiana **dokładająca
konfigurację logującą** — `status`, czyli ta realnie blokująca, zostaje nietknięta.

Każda inna pozycja planu jest sygnałem, że `policy.yaml` nadal nie opisuje rzeczywistości. W szczególności
**`- "…googleapis.com"` w bloku `status`** znaczy „apply zdejmie ochronę tej usługi" — wróć do kroku 2.

## Krok 5 — apply i **pomiar efektu**

```bash
terraform -chdir=terraform apply /tmp/brownfield.tfplan
```

Potem — i to jest część procedury, nie sprzątanie — **zmierz żywy obiekt**, nie `phase` operacji:

```bash
gcloud access-context-manager perimeters describe <PERIMETR> \
  --policy=<POLICY_ID> --format=json > po-przejeciu.json

python3 - <<'EOF'
import json
a=json.load(open('przed-przejeciem.json'))['status']
b=json.load(open('po-przejeciu.json'))['status']
# ZBIÓR, nie lista: API zwraca restrictedServices w NIEUSTALONEJ kolejności i sama zmiana
# kolejności jest normalna. Porównanie list dałoby tu fałszywy alarm.
print('uslugi  ZBIOR identyczny:', set(a['restrictedServices'])==set(b['restrictedServices']))
print('czlonkowie identyczni  :', a.get('resources')==b.get('resources'))
print('ingress identyczne     :', a.get('ingressPolicies')==b.get('ingressPolicies'))
print('egress  identyczne     :', a.get('egressPolicies')==b.get('egressPolicies'))
EOF
```

**Cztery razy `True` = przejęcie nie zmieniło ochrony.** Jedno `False` = apply zrobił coś, czego nie
zamawiałeś; masz `przed-przejeciem.json`, żeby to cofnąć.

Kontrola niezależna od Terraforma — kto realnie pisał do perimetru:

```bash
gcloud logging read \
  'logName:"cloudaudit.googleapis.com%2Factivity"
   AND protoPayload.resourceName:"servicePerimeters/<PERIMETR>"' \
  --organization=<ORG_ID> --freshness=1h \
  --format="value(timestamp,protoPayload.methodName)"
```

W oknie planu i importu **nie ma tu być ani jednego wpisu**. Pierwszy pojawia się dopiero przy `apply`.
To jest dowód, że import nie dotknął chmury.

## Krok 6 — sprzątnięcie

Usuń `terraform/zz_import_generated.tf` **w tym samym PR-ze**. Zostawiony blok jest idempotentny i nie
szkodzi, ale sugeruje następnej osobie, że import jest wciąż do zrobienia.

Po nim `plan` ma dawać **`No changes`**. Jeśli nie daje — patrz niżej.

## Czego NIE da się przejąć: reguły ingress/egress

`terraform import` **nie działa** na regułach granularnych:

```
Error: resource google_access_context_manager_service_perimeter_dry_run_ingress_policy
       doesn't support import
```

W stanie mają `id` równy identyfikatorowi **perimetru**, nie własnemu — nie ma czego zaadresować.
Konsekwencja dla przejęcia: **cudze reguły zostają poza zarządzaniem Terraforma**, na zawsze, dopóki
ktoś ich nie odtworzy jako deklaracji.

Chroni je `ignore_changes` na szkielecie (`status[0].ingress_policies`, `egress_policies` i odpowiedniki
w `spec`) — zmierzone: po przejęciu cudze reguły są **co do bajtu te same**. Ale:

- **drift detection ich nie pilnuje** (nie znamy stanu oczekiwanego),
- **raport naruszeń nie przypisze ich do członka**,
- w konsoli wyglądają identycznie jak nasze.

### Jeśli mimo to chcesz je przejąć — tu jest okno bez autoryzacji

Odtworzenie reguły jako deklaracji oznacza `create`. API odrzuca duplikat **po TYTULE**:

```
Error: Unable to create ServicePerimeterDryRunIngressPolicy, existing object already found:
       … title:<tytuł>
```

Stąd dwa warianty i tylko jeden z nich jest bezpieczny:

| wariant | co się dzieje | okno |
|---|---|---|
| **nasz tytuł ≠ cudzy tytuł** | powstaje **druga** reguła o tym samym skutku; cudza zostaje | **brak okna** — ruch autoryzowany przez cały czas. Cudzą kasujesz **po** potwierdzeniu, że nasza działa |
| **ten sam tytuł** | `create` pada na duplikacie; żeby przeszedł, trzeba **najpierw skasować cudzą** | **okno realne**: od skasowania cudzej do `apply` naszej ruch **nie jest autoryzowany** |

**Rób pierwszy wariant.** Drugi jest jedynym miejscem w całym przejęciu, gdzie granica przestaje
przepuszczać ruch, który przepuszczała — i jeśli musisz go wybrać, zaplanuj okno jak zwykłą zmianę
produkcyjną (ogłoszenie, obserwacja, gotowy rollback).

To **nie jest** utrata ochrony (granica jest wtedy *bardziej* szczelna, nie mniej) — to utrata
**dostępności** dla ruchu, który reguła autoryzowała. Nazywaj to precyzyjnie, bo reakcja jest inna.

### Sierota po przerwanym apply

`apply` przerwany w locie zostawia regułę w chmurze, ale nie w stanie. Każde ponowienie pada tym samym
`existing object already found`, a `import` jej nie odzyska. Odzysk — listą **bez** sieroty:

```bash
gcloud access-context-manager perimeters describe <PERIMETR> --policy=<POLICY_ID> --format=json \
| python3 -c "
import sys,json,yaml
sp=(json.load(sys.stdin).get('spec') or {})
keep=[p for p in sp.get('ingressPolicies',[]) if p.get('title')!='<TYTUL_SIEROTY>']
yaml.safe_dump(keep,sys.stdout,sort_keys=False,allow_unicode=True)
" > bez-sieroty.yaml

gcloud access-context-manager perimeters dry-run update <PERIMETR> \
  --policy=<POLICY_ID> --set-ingress-policies=bez-sieroty.yaml
```

Potem `apply` przechodzi. Zmierzone.

## Uprawnienia — co musi mieć kto

- **`servicePerimeters.create` NIE jest potrzebne.** Perimetr już istnieje; przejęcie go nie tworzy.
  Decyzja o nieprzyznawaniu `create` kontu pipeline'u **zostaje w mocy** i nie blokuje brownfielda.
- **`servicePerimeters.update` JEST potrzebne** — apply przejęcia to `UpdateServicePerimeter`. Rola
  pipeline'u już je ma.
- **Odczyt** (`accesscontextmanager.policyReader`) — do kroku 0, 1 i pomiaru z kroku 5.
- **Krok człowieka** to nie import, tylko **decyzja z kroku 2**: co jest prawdą, gdy repo i chmura mówią
  co innego. Tego nie da się delegować pipeline'owi, bo to nie jest pytanie techniczne.

## Pułapka spoza VPC-SC: `403`, który nie ma z granicą nic wspólnego

Pierwszy `plan` z lokalnej maszyny potrafi paść tak:

```
Error 403: Your application is authenticating by using local Application Default Credentials.
The accesscontextmanager.googleapis.com API requires a quota project…    reason: SERVICE_DISABLED
```

To **nie** odmowa VPC-SC i **nie** brak roli — to brak projektu rozliczeniowego dla ADC. Lekarstwo:

```bash
export USER_PROJECT_OVERRIDE=true GOOGLE_BILLING_PROJECT=<PROJEKT_ADMINISTRACYJNY>
```

Wpisane tutaj, bo `403` w tym torze ma **trzy** różne przyczyny i identyczny kod wyjścia.

## Czego NIE robić

- **Nie ustawiaj `manage_skeleton: true` bez importu.** Terraform próbuje wtedy **utworzyć** perimetr,
  który istnieje. Zmierzone — kończy się **bezpiecznie**:
  `Error 409: Perimeter '…' already exists and cannot be created`, a treść perimetru zostaje **nietknięta**
  (potwierdzone próbkowaniem w trakcie). To najczęstsza pomyłka operatora i dobra wiadomość: jest
  fail-closed. Zła: komunikat nie podpowiada, że brakuje importu.
- **Nie „naprawiaj" niepustego planu przez apply.** Niepusty plan to informacja, nie przeszkoda.
- **Nie importuj przy okazji innego PR-a.** Import zmienia stan, nie kod — własna zmiana, własny opis,
  własny moment w czasie.
- **Nie porównuj `etag`ów** — patrz krok 0.

## Kiedy warto przejąć szkielet

Gdy zespół perimetru staje się jego właścicielem także formalnie — wtedy baseline podlega temu samemu
review i tej samej historii co reszta. Do tego czasu każda zmiana baseline'u jest robiona przez obecnego
właściciela poza tym repo, więc **drift detection jej nie wykryje** (nie znamy stanu oczekiwanego).

## Co działa w trybie brownfield (bez przejęcia)

Wszystko poza zarządzaniem baseline'em: członkostwo (dry-run i enforced), reguły z profili, access levels,
bramki OPA, budżet atrybutów, raport naruszeń, drift detection (na zasobach, które kontrolujemy), break-glass.

`restricted_services` w `policy.yaml` pełni wtedy rolę **dokumentacji i wejścia dla guardów** — reguła
`onboarding.rego` nadal odrzuci wyjęcie usługi baseline'owej, mimo że ta lista nie leci do API.

**Członkowie, których nie zadeklarowaliśmy, zostają.** Zmierzone: perimetr z cudzymi członkami przechodzi
przejęcie z `status.resources` bez zmian, a zadeklarowanie istniejącego członka jako `stage: dry-run`
dokłada go do `spec` i **nie rusza** konfiguracji egzekwowanej.
