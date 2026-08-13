# Uprawnienia i WIF — co zamówić u architekta i dlaczego dokładnie tyle

Dokument do **requestu o dostępy**. Każda pozycja ma: co to jest · **do jakiej operacji API jest potrzebna** ·
**co się stanie bez niej** · zakres nadania. Jeśli architekt utnie którąkolwiek pozycję, w kolumnie „bez niej"
jest napisane, co przestanie działać — to jest cała treść negocjacji.

Kontekst: **perimetr i access policy JUŻ ISTNIEJĄ**. Nie prosimy o prawo do ich tworzenia ani kasowania —
tylko o prawo do **modyfikowania zawartości** istniejącego perimetru (dokładanie projektów i reguł).

---

## 0. Fakt, który determinuje cały kształt requestu

> **Uprawnień Access Context Managera nie da się nadać na folderze ani na projekcie.** Google dopuszcza
> nadanie wyłącznie **na organizacji** albo **na konkretnej polityce dostępu** (scoped policy). Grant ACM
> zrobiony na folderze/projekcie **nie ma żadnego efektu**.
> Źródło: [Access Context Manager — access control](https://docs.cloud.google.com/access-context-manager/docs/access-control).

Konsekwencja dla rozmowy z architektem: **nie istnieje wariant „damy wam to tylko na waszym folderze"**.
Jedyne dwie dźwignie, którymi realnie zmniejszamy zakres, to:

1. **custom rola** zamiast predefiniowanej `policyEditor` (usuwamy `create` i `delete` perimetru),
2. **IAM Deny** na operacjach destrukcyjnych (twardy zakaz ponad rolą),
3. (opcjonalnie, na później) **scoped policy** — jeśli kiedyś perimetr przestanie być org-wide.

Warto to powiedzieć wprost na starcie requestu, bo pierwszą reakcją na „rola na organizacji" jest zwykle
próba zawężenia zakresu — a tu zawęża się uprawnienia, nie zasięg.

---

## 1. Trzy tożsamości, nie jedna

| Tożsamość | Kiedy działa | Czego dotyka |
|---|---|---|
| `sa-vpcsc-plan` | każdy PR (read-only) | czyta perimetr i inwentarz, nic nie zmienia |
| `sa-vpcsc-apply` | tylko environment `perimeter-apply`, a ten — tylko z gałęzi domyślnej (§5.1) | modyfikuje zawartość perimetru |
| człowiek (break-glass) | incydent, przez PAM/JIT | wyjęcie członka z konfiguracji egzekwowanej |

**DLACZEGO rozdzielone:** plan jest uruchamiany przez każdy PR, także z forka czy z gałęzi, której nikt nie
przejrzał. Gdyby plan i apply dzieliły tożsamość, prawo do zmiany granicy bezpieczeństwa całej organizacji
wisiałoby na każdym otwartym PR-ze. Rozdzielenie kosztuje jedno konto serwisowe.

---

## 1a. Widok read-only dla CZŁOWIEKA (pierwsza rzecz, o którą warto poprosić)

Zanim powstaną konta serwisowe, ktoś musi **zobaczyć**, jak wygląda organizacja: która polityka dostępu
istnieje, jak nazywa się perimetr, co już chroni, kto go dziś zmienia. To jest osobny, czysto odczytowy
request — tani do zaakceptowania i odblokowuje inwentaryzację, brownfield-import i wypełnienie `policy.yaml`
realnymi wartościami.

| Rola | Zakres | Do czego konkretnie | Bez niej |
|---|---|---|---|
| `roles/resourcemanager.organizationViewer` | **organizacja** | zobaczyć organizację w konsoli i w `gcloud organizations list`; konsola Access Context Managera wymaga jej do wyświetlenia czegokolwiek | konsola VPC-SC nie pokazuje organizacji, mimo poprawnych ról ACM |
| `roles/accesscontextmanager.policyReader` | **organizacja** | `policies list/describe`, `perimeters list/describe`, `access-levels list` — cała inwentaryzacja i `--diff` w `perimeter_to_policy.py` | `PERMISSION_DENIED` na `policies list`; nie da się nawet ustalić numeru polityki |
| `roles/browser` | organizacja | drzewo zasobów: foldery i projekty, para `project_id` ↔ `project_number` | numer projektu trzeba brać „na słowo" z ticketa — a to on trafia do perimetru |
| `roles/cloudasset.viewer` | organizacja | wyszukiwanie zasobów (`searchAllResources`): czy projekt istnieje, czy nie należy już do innego perimetru | pre-flight nie ma czym sprawdzić kandydata |
| `roles/logging.viewer` | organizacja | odczyt naruszeń VPC-SC z audit logów — raport z okna dry-run | promocja do enforced opiera się na deklaracji, nie na dowodzie |
| `roles/compute.networkViewer` | organizacja lub foldery dywizji | Private Google Access na podsieciach kandydata | patrz §2.1 — awaria ujawnia się tygodnie później |
| `roles/dns.reader` | organizacja lub foldery dywizji | prywatne strefy kierujące `*.googleapis.com` na restricted VIP | jw. |
| `roles/serviceusage.serviceUsageViewer` | organizacja lub foldery | czy w projekcie włączone są API objęte baselinem (aiplatform i reszta) | członek wchodzi do perimetru z wyłączonym API — objaw wygląda jak blokada VPC-SC, a nią nie jest |
| *(opcjonalnie)* `roles/iam.securityReviewer` | organizacja | kto **dziś** trzyma role ACM i kto może zmienić perimetr | inwentaryzacja stanu wyjściowego jest zgadywaniem |

**Minimum, jeśli architekt chce ciąć:** `organizationViewer` + `policyReader` + `browser`. Reszta jest po to,
żeby pre-flight i raport naruszeń miały czym działać — bez nich narzędzia nadal się uruchomią, tylko zgłoszą
brak dostępu zamiast wyniku.

**Dwie pułapki, które kosztują pół dnia:**

1. **Granty ACM niżej niż organizacja nie działają.** Nadanie `policyReader` na folderze albo projekcie nie ma
   żadnego efektu — dozwolone są wyłącznie organizacja albo **pojedyncza polityka** (patrz §4a). Nawet szeroki
   `roles/viewer` na organizacji nie zastępuje `policyReader`: Access Context Manager ma własne role.
2. **`gcloud` potrzebuje projektu rozliczeniowego dla tego API.** Wywołania ACM kontem użytkownika wymagają
   ustawionego quota project i uprawnienia `serviceusage.services.use` w nim
   (`roles/serviceusage.serviceUsageConsumer`):

   ```bash
   gcloud config set billing/quota_project <PROJEKT>
   gcloud access-context-manager policies list --organization <ORG_ID>
   ```

   Bez tego dostajesz błąd o braku uprawnień, który wygląda jak brak roli ACM — a rolę już masz.

Nadanie (do wklejenia architektowi; `--condition=None` świadomie, bo to role odczytowe):

```bash
for R in resourcemanager.organizationViewer accesscontextmanager.policyReader browser \
         cloudasset.viewer logging.viewer serviceusage.serviceUsageViewer; do
  gcloud organizations add-iam-policy-binding <ORG_ID> \
    --member="user:imie.nazwisko@example.com" --role="roles/$R" --condition=None
done
```

---

## 2. `sa-vpcsc-plan` — tożsamość read-only

| Rola | Zakres | Do jakiej operacji | Bez niej |
|---|---|---|---|
| `roles/accesscontextmanager.policyReader` | **organizacja** | `accessPolicies.get/list`, `servicePerimeters.get/list`, `accessLevels.get/list` — Terraform musi odczytać aktualny stan perimetru, żeby policzyć różnicę. **Ta sama rola niesie `resourcemanager.projects.get/list`**, czyli checki 1 i 2 pre-flightu (projekt istnieje, numer zgodny, brak kolizji perimetrów) | `terraform plan` pada na 403 przy odświeżaniu stanu; PR nie pokazuje, co zmienia; pre-flight nie ma czym sprawdzić kandydata |
| `roles/cloudasset.viewer` | organizacja | **DWAJ konsumenci, żaden oczywisty.** (1) **sonda granicy** (`boundary-probe.yml`): `gcloud asset search-all-resources` to wywołanie usługi **spoza** `restricted_services`, czyli kontrola pozytywna, która ma przejść ZAWSZE — bez niej „przeszło" i „nie miało prawa zapytać" stają się nieodróżnialne. (2) **detektor martwego członka** (`watch.yml`, DEC-42): to samo uprawnienie oddaje `state` **wszystkich** projektów organizacji jednym wywołaniem, więc obserwator widzi, że projekt członka przestał istnieć — czego nie widzi żadna inna warstwa. Alternatywą było `resourcemanager.projects.get`, czyli **nowe** nadanie na organizacji i koszt rosnący z liczbą członków. **Ta rola NIE jest używana przez pre-flight** — mimo że tak stało tu przez długi czas; skrypt czyta Resource Managera i ACM, a nie Cloud Asset Inventory (zmierzone). Nie zdejmuj jej „bo pre-flight jej nie potrzebuje" | sonda traci kontrolę pozytywną i każdy jej negatyw staje się niefalsyfikowalny; detektor martwego członka przestaje publikować punkty, a martwy członek wraca do bycia niewidzialnym (łapie to `condition_absent` polityki, więc głośno) |
| `roles/compute.networkViewer` | organizacja (lub foldery dywizji) | pre-flight: odczyt podsieci — czy mają włączony **Private Google Access** | onboarding „przechodzi", a workload i tak nie dogada się z API przez restricted VIP; objawia się jako awaria aplikacji tygodnie później |
| `roles/dns.reader` | organizacja (lub foldery dywizji) | pre-flight: czy istnieje prywatna strefa DNS kierująca `*.googleapis.com` na restricted VIP (i osobno `*.notebooks.googleusercontent.com` na `private.googleapis.com` dla Workbencha) | jw. — plus klasyczna pułapka Workbencha z własnym kernelem, którą łapie tylko ten check |
| `roles/storage.objectAdmin` | **tylko prefiks bucketa stanu**, nie cały bucket | backend GCS bierze **blokadę stanu** (tworzy i kasuje obiekt `.tflock`), więc sam odczyt nie wystarcza | `terraform plan` pada na braku uprawnień do locka; obejście `-lock=false` odbiera ochronę przed równoległym zapisem stanu |
| `roles/iam.workloadIdentityUser` **na `sa-vpcsc-plan`** | to konto serwisowe | pozwala tożsamości z GitHuba (pula WIF) impersonować to SA | workflow nie wymieni tokenu OIDC na dostęp — cała ścieżka keyless nie działa |

### 2.1 Co to jest „restricted VIP" i dlaczego pre-flight sprawdza DNS

**Restricted VIP** to zestaw adresów IP (`199.36.153.4/30`, IPv6 `2600:2d00:0002:1000::/56`) ukrytych pod nazwą
`restricted.googleapis.com`, przez które wołasz API Google **bez wychodzenia do internetu**. VIP = *virtual IP*:
jeden adres obsługiwany przez infrastrukturę Google, a nie przez konkretny serwer.

Google wystawia trzy warianty i **różnica między nimi jest sednem sprawy**:

| Endpoint | Zakres | Co przepuszcza |
|---|---|---|
| publiczny (`googleapis.com` → publiczne IP) | internet | wszystkie API |
| `private.googleapis.com` | `199.36.153.8/30` | wszystkie API, **także te spoza perimetru** |
| **`restricted.googleapis.com`** | **`199.36.153.4/30`** | **wyłącznie API objęte VPC-SC** |

**DLACZEGO to nas dotyczy:** perimetr kontroluje, *kto z jakiego kontekstu* woła API — ale nie zmienia tego,
*którędy* ruch wychodzi. Workload w podsieci bez odpowiedniego DNS-u rozwiąże `storage.googleapis.com` na adres
publiczny i wyjdzie do internetu. Wtedy dzieje się jedna z dwóch rzeczy, obie złe:

- ruch **omija intencję granicy** — dane wychodzą ścieżką, której perimetr nie miał chronić, albo
- po włączeniu enforce ruch **zostaje zablokowany** i objawia się jako awaria aplikacji, której nikt nie wiąże
  z perimetrem (bo „przecież nic nie zmienialiśmy w aplikacji").

Żeby ruch szedł przez restricted VIP, w projekcie dywizji muszą istnieć **trzy** rzeczy naraz:

1. **Private Google Access** na podsieci (`compute.networkViewer` to czyta) — bez tego maszyna bez publicznego
   IP w ogóle nie dosięgnie żadnego API Google,
2. **prywatna strefa DNS** `googleapis.com` z rekordami na `199.36.153.4/30` i CNAME `*.googleapis.com`
   (**`dns.reader` to czyta**) — to ona sprawia, że nazwa API rozwiązuje się na restricted VIP, a nie na
   adres publiczny,
3. **trasa i reguła firewall** dopuszczająca ruch do `199.36.153.4/30`.

Pre-flight sprawdza (1) i (2), bo to one decydują, czy onboarding ma sens — i dlatego `roles/dns.reader` jest na
liście. **Bez tej roli** nie widzimy, czy strefa istnieje i dokąd kieruje; wniosek przechodzi, ticket się
zamyka, a problem wychodzi tygodnie później jako „aplikacja przestała działać po włączeniu perimetru".

> **Wyjątek, który łapie tylko ten check:** Vertex AI Workbench z własnym kernelem wymaga, żeby
> `*.notebooks.googleusercontent.com` kierowało na **`private.googleapis.com` (199.36.153.8/30)**, a **nie** na
> restricted VIP. To jedyne znane odstępstwo od reguły „wszystko przez restricted" — pomyłka objawia się
> notebookiem, który się nie uruchamia, bez żadnego komunikatu o VPC-SC.

---

## 3. `sa-vpcsc-apply` — tożsamość zapisująca

### 3.1 Custom rola zamiast `policyEditor` (to jest sedno requestu)

Predefiniowana `roles/accesscontextmanager.policyEditor` daje **read-write na politykach i poziomach
dostępu** — czyli razem z prawem do **usunięcia perimetru**. Nie potrzebujemy tego: perimetr istnieje i ma
istnieć dalej. Prosimy o rolę custom na organizacji:

```
rola: organizations/<ORG_ID>/roles/vpcScPerimeterWriter
tytuł: VPC-SC perimeter writer (CI)
uprawnienia:
  accesscontextmanager.policies.get          # provider odczytuje politykę, w której żyje perimetr
  accesscontextmanager.policies.list         # rozwiązanie nazwy polityki org-level
  accesscontextmanager.servicePerimeters.get     # odczyt stanu przed zmianą (refresh)
  accesscontextmanager.servicePerimeters.list    # jw., przy operacjach na wielu perimetrach
  accesscontextmanager.servicePerimeters.update   # <-- JEDYNE uprawnienie zapisujące na perimetrze:
                                                  #     dodanie/usunięcie projektu i reguły ingress/egress
                                                  #     (API: servicePerimeters.patch)
  accesscontextmanager.accessLevels.get
  accesscontextmanager.accessLevels.list
  accesscontextmanager.accessLevels.create    # nowy poziom dostępu (np. nowy zakres korpo-IP)
  accesscontextmanager.accessLevels.update    # zmiana istniejącego poziomu
  accesscontextmanager.accessLevels.delete    # OSTATNI krok offboardingu dywizji z własnym poziomem
ŚWIADOMIE POMINIĘTE:
  accesscontextmanager.servicePerimeters.create   # granicy nie tworzy tożsamość automatyczna (DEC-37)
  accesscontextmanager.servicePerimeters.delete   # kasowanie = break-glass człowieka, nie CI
  accesscontextmanager.policies.create/delete/setIamPolicy  # polityka org-level nie jest naszym obiektem
```

**Dlaczego `accessLevels.delete` JEST, a `servicePerimeters.create` NIE JEST — mimo że oba brzmią groźnie**
(DEC-37; obie luki zmierzone na żywej organizacji, nie wyprowadzone z zasad):

| | `accessLevels.delete` | `servicePerimeters.create` |
|---|---|---|
| Jak często potrzebne | **każdy** offboarding dywizji z własnym poziomem | **raz w życiu granicy** — po jej utracie |
| Co się dzieje bez niego | apply pada w POŁOWIE → stan częściowo zastosowany na żywej granicy | pipeline pada na PIERWSZYM zasobie → nic nie powstaje, stan czysty |
| Czy jest obejście | nie ma — katalog poziomów rośnie w nieskończoność (limit **500 na ORGANIZACJĘ**) | jest i jest tani: **6 s** człowieka w ~3-minutowym odzysku (część D runbooka) |
| Co pilnuje kształtu | bramka OPA (DEC-33) + API (`you must first remove the reference`) | nic — nowy perimetr nie jest obserwowany przez `drift`, sondę ani raport naruszeń |
| Ta sama rola ma już | `accessLevels.update` — **groźniejsze**: przepisanie poziomu na `0.0.0.0/0` poszerza granicę cicho | `servicePerimeters.update` — ale na obiekcie pod ciągłą obserwacją |

Kontrola, która zamienia **rutynę** w interwencję człowieka, jest spłacana obejściami. Kontrola, która
wymaga człowieka **raz na katastrofę**, nie jest — bo nie ma czego obchodzić. Stąd różne werdykty.

**Zdanie do requestu:** *„Prosimy o rolę custom, a nie `policyEditor`, żeby pipeline nie miał fizycznej
możliwości skasowania perimetru ani polityki. Zakres org-level jest wymuszony przez Google (uprawnienia ACM
nie działają na folderze); zawężamy więc to, co jesteśmy w stanie zawęzić — zestaw operacji."*

> Przed wysłaniem requestu warto potwierdzić dokładny zestaw uprawnień predefiniowanej roli w waszej
> organizacji: `gcloud iam roles describe roles/accesscontextmanager.policyEditor`. Lista uprawnień bywa
> rozszerzana przez Google — porównanie jej z powyższą listą jest jednocześnie najlepszym argumentem
> („różnica to dokładnie create/delete").

### 3.2 Reszta uprawnień apply

| Rola | Zakres | Do jakiej operacji | Bez niej |
|---|---|---|---|
| `roles/storage.objectAdmin` | prefiks bucketa stanu | zapis stanu Terraform + lock | apply nie zapisze stanu → następny plan zobaczy świat niezgodny z rzeczywistością |
| custom rola `vpcScMonitoringWriter` | projekt z `monitoring.project_id` | pełny cykl życia metryk logowych i polityk alertów perimetru (`terraform/monitoring.tf`) | **apply pada zawsze**, także przy zmianie niedotyczącej monitoringu: `terraform apply` zaczyna od refreshu, więc musi PRZECZYTAĆ te zasoby (`Error 403: Permission 'logging.logMetrics.get' denied`) |
| `roles/iam.workloadIdentityUser` **na `sa-vpcsc-apply`** | to konto serwisowe | impersonacja z puli WIF, wyłącznie dla workflow apply | brak ścieżki keyless dla apply |

**Pułapka, która kosztowała dwa czerwone applye:** „konto apply zapisuje, konto plan czyta" to skrót
myślowy. `terraform apply` **zaczyna od odświeżenia stanu**, więc apply jest nadzbiorem planu i musi umieć
odczytać *wszystko*, czym zarządza — łącznie z zasobami, których w danym przebiegu nie rusza. Konto plan
czytało metryki i alerty „przypadkiem", bo ma read-only role na organizacji; konto apply nie miało do nich
żadnego prawa. Każdy nowy typ zasobu w `terraform/` domagaj się sprawdzenia po TEJ stronie tabeli, nie
tylko po stronie planu.

`vpcScMonitoringWriter` zamiast pary `roles/monitoring.editor` + `roles/logging.configWriter`: ta para
daje na całym projekcie także tworzenie **sinków** i kubełków logów, czyli ścieżkę wyprowadzenia logów,
o którą nikt nie prosił. Bierzemy dwa typy zasobów i nic poza nimi — ta sama zasada, co przy
`vpcScPerimeterWriter`. `delete` jest tu natomiast **obecne**, w przeciwieństwie do perimetru: metryka
i alert są odtwarzalne z kodu jednym apply, a część zmian `metric_descriptor` provider realizuje jako
replace; perimetru pipeline nie odtworzy, bo `servicePerimeters.create` świadomie nie należy do żadnej
roli tego pipeline'u i od DEC-37 jest dodatkowo zabronione w warstwie Deny — odtworzenie ma krok człowieka
opisany w `3-runbook-promocja-i-break-glass.md`, część D.
| (opcjonalnie) `roles/logging.viewer` | organizacja | raport naruszeń dry-run czyta audit-logi (`protoPayload.metadata.dryRun=true`) | nie da się udowodnić, że okno obserwacji było czyste — a bez tego promocja do enforced jest zgadywaniem. Można też nadać osobnej tożsamości raportującej |

### 3.3 IAM Deny — pas bezpieczeństwa ponad rolą

Osobna polityka Deny na organizacji, dla obu SA CI:

```
deniedPrincipals: sa-vpcsc-apply@..., sa-vpcsc-plan@...
deniedPermissions:
  accesscontextmanager.servicePerimeters.delete
  accesscontextmanager.servicePerimeters.create   # od DEC-37
  accesscontextmanager.policies.delete
```

**DLACZEGO mimo custom roli:** role bywają podmieniane w pośpiechu („dajmy na chwilę policyEditor, żeby
odblokować release"). Deny przeżywa taką podmianę — jest oceniane przed rolami i nie da się go obejść
nadaniem szerszej roli. To ta sama logika, którą stosujemy do nieodwracalnych operacji na kluczach KMS.

**Dlaczego `create` dołożone dopiero teraz** (DEC-37): nikt go kontu CI nie nadał — i o to chodzi.
Przed tą zmianą tworzenie perimetru blokowało **wyłącznie** pominięcie w roli, czyli dokładnie ta warstwa,
którą podmiana roli znosi. Zmierzone Policy Troubleshooter v3 na żywej organizacji, przed zmianą:

```
sa-vpcsc-apply x accessPolicies/<POLICY> x servicePerimeters.create
  allow: ALLOW_ACCESS_STATE_NOT_GRANTED
  deny : DENY_ACCESS_STATE_NOT_DENIED      <-- warstwa Deny MILCZAŁA
```

Zdanie „granicy nie tworzy tożsamość automatyczna" jest decyzją architektoniczną, a nie skutkiem ubocznym
listy uprawnień — należy więc do warstwy, która przeżywa eskalację. **`accessLevels.delete` świadomie tu
NIE trafiło**: to rutyna pipeline'u (offboarding), a Deny obejmujące rutynę zablokowałoby jedyną drogę
wdrożenia i wymagałoby `roles/iam.denyAdmin` przy każdej zmianie zdania.

---

## 4. Czy potrzebujemy uprawnień na projektach dywizji?

**Do samej operacji dodania projektu do perimetru — nie.** To zmiana obiektu polityki (org-level), a nie
operacja na projekcie. Uprawnienia na projektach dywizji potrzebuje wyłącznie **pre-flight** i tylko do
**odczytu** (`cloudasset.viewer`, `compute.networkViewer`, `dns.reader` — sekcja 2).

To dobra wiadomość do requestu: **nie prosimy o żaden dostęp zapisujący w środowiskach dywizji.** Jeśli
architekt woli, pre-flight może działać na węższym zakresie (foldery dywizji zamiast całej organizacji) —
kosztem tego, że każde nowe dołączenie dywizji spoza tych folderów wymaga rozszerzenia grantu.

> Do potwierdzenia na dev przed wysłaniem requestu: czy w waszej organizacji `servicePerimeters.patch`
> przechodzi bez `resourcemanager.projects.get` na dodawanym projekcie. Jeśli okaże się wymagane, dochodzi
> `roles/browser` (lub `resourcemanager.projects.get` w custom roli) na folderach dywizji — nadal read-only.

---

## 4a. Wariant minimalny na start: scoped policy na folderze-piaskownicy

Jeśli architekt nie chce nadawać prawa zapisu na polityce org-level, **zanim** zobaczy nasz kod w akcji, jest
ścieżka pośrednia. Access Context Manager pozwala utworzyć **scoped policy** — politykę wciąż zaczepioną na
organizacji, ale z zasięgiem ograniczonym do jednego folderu:

```bash
# robi to ktoś z uprawnieniami ORG-LEVEL, jednorazowo
gcloud access-context-manager policies create \
  --organization <ORG_ID> --scopes=folders/<FOLDER_SANDBOX> --title "VPC-SC sandbox"

# i deleguje nam admina na TEJ JEDNEJ polityce (nie na organizacji)
gcloud access-context-manager policies add-iam-policy-binding <POLICY_ID> \
  --member=serviceAccount:sa-vpcsc-apply@<PROJEKT>.iam.gserviceaccount.com \
  --role=roles/accesscontextmanager.policyEditor
```

Dlaczego to działa i czego nie zmienia:

- **Delegacja na pojedynczej polityce jest wspierana wprost.** Docs: *„permissions can only be granted at the
  organization-level or on individual policies"*, a dodatkowo *„The access control for scoped policies is
  independent of the projects or folders in their scopes"*. To znaczy: dostajemy prawo zapisu do jednej
  polityki, bez żadnych uprawnień ACM na organizacji.
- **Utworzenia i delegacji nie zrobimy sami.** *„You can only create, list, or delegate scoped policies if you
  have those permissions at the organization level."* Krok pierwszy zawsze wykonuje architekt.
- **Do wylistowania polityk nadal potrzebny jest org-level odczyt.** `policies list --organization` bez
  `policyReader` na organizacji zwraca PERMISSION_DENIED. Praktyczne wyjście: albo drobny grant
  `roles/accesscontextmanager.policyReader` na organizacji (read-only), albo architekt podaje nam numer
  polityki, a my używamy go wprost w `policy.yaml`.
- **Scope jest niezmienny** po utworzeniu (zmiana zasięgu = usuń i utwórz od nowa), a jedna scoped policy
  obejmuje **jeden** folder albo projekt. Limit: 1 polityka org-level + 50 scoped.
- **Perimetr żyje WEWNĄTRZ polityki**, nie „w folderze" — i może obejmować wyłącznie projekty spod scope'u.
  „Chronimy folder X" nadal znaczy „wyliczamy projekty pod X i dodajemy każdy z nich".

Co to nam realnie daje: **cały pipeline można przetestować end-to-end bez ani jednego prawa zapisu na
polityce produkcyjnej.** Kod jest identyczny — zmienia się jedna wartość, `organization.access_policy_name`
w `perimeter/policy.yaml`.

Czego to **nie** daje: uprawnienia na scoped policy nie pozwalają dotknąć docelowego perimetru w polityce
org-level. To jest środowisko testowe, nie etap wdrożenia — a docelowa wytyczna („jeden perimeter org-wide",
DEC-1) nadal wymaga grantu z sekcji 3.

> Do zweryfikowania eksperymentem, gdy dostaniemy piaskownicę: jak zachowuje się projekt objęty JEDNOCZEŚNIE
> perimetrem z polityki org-level i z polityki scoped. Spodziewamy się, że żądanie musi przejść oba, ale w
> dokumentacji nie znaleźliśmy zdania, które to wprost mówi — a to jest różnica między „testujemy bezpiecznie
> obok produkcji" a „testem odcinamy ruch w produkcji".

Linki: [tworzenie polityki](https://cloud.google.com/access-context-manager/docs/create-access-policy) ·
[kontrola dostępu](https://cloud.google.com/access-context-manager/docs/access-control) ·
[limity](https://cloud.google.com/vpc-service-controls/quotas)

---

## 5. WIF — jak to spiąć bez kluczy

### 5.0 Nazewnictwo: co jest czym (najczęstsze nieporozumienie w tej rozmowie)

`sa-vpcsc-plan` i `sa-vpcsc-apply` to **konta serwisowe (service accounts)**, nie WIF. Prefiks `sa-` jest
konwencją nazewniczą dla SA — nie ma czegoś takiego jak „`wif-vpcsc-plan`", bo **WIF nie jest tożsamością,
która ma role**.

| Byt | Czym jest | Przykładowa nazwa | Czy ma role IAM? |
|---|---|---|---|
| **Workload Identity Pool** | kontener zaufania dla zewnętrznego dostawcy tożsamości | `github-actions` | nie |
| **Provider** w puli | konfiguracja konkretnego IdP + **`attribute_condition`** (kto w ogóle wejdzie) | `github` | nie |
| **Principal / principalSet** | tożsamość *wywodząca się* z tokenu OIDC, adresowana `principalSet://…/attribute.repository/ORG/repo` | — | teoretycznie tak (patrz 5.2) |
| **Service account** | tożsamość Google, **na której wiszą role** | `sa-vpcsc-plan@…` | **tak — to tu są uprawnienia** |

Jednym zdaniem: **WIF to brama, SA to tożsamość.** Pula z providerem decyduje, *kto może wejść* (repo, gałąź,
environment); konto serwisowe decyduje, *co wolno zrobić po wejściu*. Dlatego request do architekta zawiera
i jedno, i drugie — pula bez SA nie daje żadnych uprawnień, a SA bez puli wymagałoby klucza.

Ta sama logika w nazwach: puli i providera **nie** nazywamy per-ścieżkę (`…-plan`, `…-apply`), bo to jedna
pula i jeden provider dla całego repozytorium. Rozróżnienie plan/apply robią dwie rzeczy: **warunek**
(`attribute_condition`) i to, **które SA wolno impersonować**.

### 5.1 Konfiguracja

**WIF sam z siebie nie ma żadnych uprawnień.** Uprawnienia ma konto serwisowe; pula WIF tylko pozwala
tożsamości z GitHuba je impersonować. To rozróżnienie warto powiedzieć architektowi wprost, bo skraca
dyskusję: prosimy o **dwa SA z rolami z sekcji 2 i 3** oraz o **pulę, która wpuszcza dokładnie jedno repo**.

```
Workload Identity Pool:      github-actions
Provider (OIDC):             github  →  issuer: https://token.actions.githubusercontent.com
mapowanie atrybutów:
  google.subject       = assertion.sub
  attribute.repository = assertion.repository
  attribute.ref        = assertion.ref
  attribute.event      = assertion.event_name
  attribute.environment = assertion.environment
```

**Jeden warunek na providerze, granica plan/apply na wiązaniach `principalSet`** — i to rozróżnienie jest
ważniejsze, niż wygląda. Tabela opisująca „dwa warunki wejścia" wymieniała ograniczenia, których w kodzie
nie ma (`event_name`, `ref`), więc czytelnik brał za bramkę coś, czego nikt nie egzekwuje. Stan faktyczny:

| Ścieżka | Co realnie odcina dostęp do konta | Impersonuje |
|---|---|---|
| plan (PR) | `attribute_condition` providera: `assertion.repository == 'ORG/gcp-vpc-sc'`, plus `principalSet` po `attribute.repository`. To jest **każdy** workflow z tego repozytorium, także z pull requesta — i dlatego to konto jest read-only. | `sa-vpcsc-plan` |
| apply | ten sam `attribute_condition`, plus `principalSet` po `attribute.environment/perimeter-apply`. **Gałęzi w tym warunku NIE MA** — ref odcina dopiero polityka gałęzi environment (§5.1). | `sa-vpcsc-apply` |

**Bez `attribute_condition` (albo z warunkiem `true`):** dowolny workflow w **dowolnym repozytorium waszej
organizacji GitHub** może wymienić swój token OIDC na dostęp do perimetru całej organizacji GCP. To nie jest
teoretyczne — to najczęstszy realny błąd konfiguracji WIF i najmocniejszy argument, żeby warunek był w
requestcie zapisany dosłownie, a nie „dopracowany później".

Wiązanie po stronie SA (kto może impersonować):

```
sa-vpcsc-plan   ← roles/iam.workloadIdentityUser dla
  principalSet://iam.googleapis.com/projects/<NUM>/locations/global/workloadIdentityPools/github-actions/attribute.repository/ORG/gcp-vpc-sc
sa-vpcsc-apply  ← roles/iam.workloadIdentityUser dla tej samej puli,
                  ale ścieżkę zawęża principalSet po attribute.environment (perimeter-apply)
```

**Uwaga na to, czego w tym warunku NIE MA — gałęzi.** `attribute_condition` providera pinuje repozytorium,
a `principalSet` konta apply pinuje nazwę environment. Ani jedno, ani drugie nie mówi „`refs/heads/main`",
więc job z `environment: perimeter-apply` uruchomiony na **dowolnej** gałęzi wymienia token na to samo
konto. Ref odcina dopiero **polityka gałęzi environment** (`deployment_branch_policy`) po stronie GitHuba —
i to ona, a nie warunek WIF, jest zdaniem „perimetr zmienia się wyłącznie z gałęzi domyślnej". Ustawia ją
`tools/bootstrap_github.sh`; działa na każdym planie GitHuba.

Druga warstwa po stronie GitHuba: environment `perimeter-apply` z **required reviewers** (zespół sieciowy +
security). To bramka niezależna od CODEOWNERS — nawet zmergowany PR nie zaaplikuje się, dopóki człowiek nie
zatwierdzi uruchomienia. **Jest to funkcja płatna**: na planach, które jej nie mają, API odrzuca ustawienie
(`Please ensure the billing plan supports the required reviewers protection rule`), a environment zostaje
bez ani jednej reguły ochrony — wyglądając w kodzie na bramkę. Odczytaj stan, zanim uznasz, że istnieje:

```bash
gh api repos/<ORG>/<REPO>/environments/perimeter-apply --jq '.protection_rules'
```

Pusta tablica = bramki ludzkiej nie ma. Wtedy zapisz to jako świadome odstępstwo z powodem i z listą
kontroli, które ją zastępują (`docs/1`, etap 4) — nie zostawiaj rozjazdu między dokumentacją a stanem.

### 5.2 „Skoro mamy WIF, po co jeszcze konta serwisowe?"

Pytanie pada prawie zawsze i jest zasadne, bo GCP ma **dwa** warianty:

| Wariant | Jak wygląda | Kiedy |
|---|---|---|
| **Impersonacja SA** (nasz wybór) | token OIDC → `principalSet` → impersonuje `sa-vpcsc-apply` → role wiszą na SA | domyślnie |
| **Direct resource access** | rola nadana **wprost** tożsamości federowanej (`principalSet://…`), bez żadnego SA | gdy usługa to wspiera i chcemy usunąć warstwę pośrednią |

**Dlaczego mimo wszystko SA:**

1. **Nie każde API akceptuje tożsamość federowaną bezpośrednio** — Google utrzymuje listę produktów z
   ograniczeniami i zaleca dla nich impersonację SA
   ([docs](https://docs.cloud.google.com/iam/docs/federated-identity-supported-services)). Dla Access Context
   Managera **trzeba to sprawdzić na tej liście przed wyborem** wariantu direct; jeśli ACM tam jest, wariant
   bez SA po prostu nie zadziała i dowiesz się o tym dopiero z 403 przy pierwszym apply.
2. **SA jest punktem, w którym da się odciąć dostęp jednym ruchem** — wyłączenie konta unieważnia wszystkie
   ścieżki naraz, niezależnie od tego, ile pul i warunków istnieje.
3. **Audyt jest czytelniejszy** — w logach widać stałą tożsamość (`sa-vpcsc-apply@…`), a nie długi
   `principalSet` różny dla każdego repozytorium.
4. **Architekt to zna** — impersonacja SA jest wzorcem, który ma już opisany w politykach; direct access
   wymagałby osobnej rozmowy o tym, jak audytować i odbierać dostęp.

Cena: jedno dodatkowe wiązanie (`roles/iam.workloadIdentityUser` na SA). **Czego to NIE zmienia:** kluczy SA
nadal nie ma — jest tylko token OIDC wymieniany na krótkotrwałe poświadczenie SA.

---

## 6. Gotowa lista do wklejenia w ticket

```
Prosimy o (środowisko: <org GCP>, repozytorium: ORG/gcp-vpc-sc):

1. SA sa-vpcsc-plan@<proj>.iam.gserviceaccount.com
   - roles/accesscontextmanager.policyReader        [ORGANIZACJA]  — odczyt perimetru do terraform plan
   - roles/cloudasset.viewer                        [ORGANIZACJA]  — kontrola pozytywna sondy granicy
                                                                     + detektor martwego członka (stan
                                                                     cyklu życia projektów, DEC-42).
                                                                     WYMAGA też włączonego
                                                                     cloudasset.googleapis.com w projekcie
                                                                     konta plan (kwota SA idzie na jego
                                                                     projekt-właściciela)
   - roles/compute.networkViewer, roles/dns.reader  [ORG lub foldery] — pre-flight: Private Google Access
                                                                       + prywatna strefa DNS kierująca
                                                                       googleapis.com na restricted VIP
                                                                       199.36.153.4/30 (patrz §2.1)
   - roles/storage.objectAdmin                      [prefiks bucketa stanu] — blokada stanu TF

2. SA sa-vpcsc-apply@<proj>.iam.gserviceaccount.com
   - custom rola vpcScPerimeterWriter               [ORGANIZACJA]  — servicePerimeters.update + accessLevels.create/update/delete
                                                                     (BEZ create/delete perimetru — patrz uzasadnienie)
   - roles/storage.objectAdmin                      [prefiks bucketa stanu] — zapis stanu TF
   - custom rola vpcScMonitoringWriter              [PROJEKT monitoringu] — logMetrics.* + alertPolicies.*
                                                                     (tylko te dwa typy; BEZ sinków i kubełków logów.
                                                                      apply odświeża stan, więc bez tego pada na 403
                                                                      przy każdej zmianie, także niedotyczącej monitoringu)
   - (opcjonalnie) roles/logging.viewer             [ORGANIZACJA]  — raport naruszeń dry-run

3. IAM Deny [ORGANIZACJA] dla obu SA:
   accesscontextmanager.servicePerimeters.delete, accesscontextmanager.policies.delete

4. Workload Identity Pool `github-actions` + provider OIDC GitHub z attribute_condition
   ograniczającym do repozytorium ORG/gcp-vpc-sc; rozdział plan/apply na wiązaniach principalSet
   (plan: attribute.repository; apply: attribute.environment==perimeter-apply — BEZ warunku o gałęzi,
   ten daje polityka gałęzi environment po stronie GitHuba)

5. Bucket stanu Terraform: versioning + soft-delete, BEZ retention-lock
   (WORM na aktywnie nadpisywanym stanie łamie backend).

Czego NIE prosimy:
   - żadnych uprawnień zapisujących w projektach dywizji,
   - prawa do tworzenia ani usuwania perimetru/polityki,
   - żadnych kluczy SA (dostęp wyłącznie keyless przez WIF).
```

---

## 7. Uzasadnienie w trzech zdaniach (gdyby architekt chciał wersję krótką)

> Prosimy o **dwa konta serwisowe** (to na nich wiszą uprawnienia) i o **pulę WIF z warunkiem** (to ona
> decyduje, kto może te konta impersonować) — WIF sam z siebie nie nadaje żadnych uprawnień.
> Perimetr i polityka już istnieją — prosimy wyłącznie o prawo do **modyfikowania zawartości** perimetru
> (`servicePerimeters.update`) plus zarządzanie poziomami dostępu. Google nie pozwala nadać uprawnień ACM
> niżej niż organizacja, więc zamiast zawężać zasięg, zawężamy zestaw operacji: rola custom bez
> `create`/`delete` plus IAM Deny na kasowaniu. Dostęp jest keyless (WIF), rozdzielony na read-only dla PR-ów
> i zapisujący wyłącznie dla `main` za bramką ludzkiego zatwierdzenia w environment.
