# iam-bootstrap — tożsamości i uprawnienia dla repozytorium perimetru

**Applikuje: zespół IAM / architekt** (uprawnienia org-admin). **Nie** pipeline perimetru — to jest kod,
który *nadaje* uprawnienia, więc nie może go stosować tożsamość, która z nich korzysta.

Osobny katalog = osobny state i osobny właściciel. Cały stack jest jednorazowy: po apply repozytorium
perimetru działa samo, a ten katalog rusza się tylko przy zmianie modelu dostępów.

## Co powstaje

| Zasób | Po co |
|---|---|
| `sa-vpcsc-plan` | read-only; uruchamiane przez **każdy** pull request |
| `sa-vpcsc-apply` | jedyna tożsamość modyfikująca perimetr; wyłącznie token z environment `perimeter-apply` — a to, że pochodzi z `main`, wymusza polityka gałęzi tego environment, nie ten stack |
| custom rola `vpcScPerimeterWriter` | `servicePerimeters.get/list/**update**` + access levels — **bez** create/delete |
| custom rola `vpcScMonitoringWriter` (gdy `monitoring_project_id` niepuste) | metryki logowe i polityki alertów perimetru w JEDNYM projekcie, dla `apply`. `terraform apply` zaczyna od **refreshu**, więc bez tego pada na 403 nawet wtedy, gdy monitoringu nie dotyka |
| 4 role read-only na org dla `plan` | `policyReader` (plan), `cloudasset.viewer` + `compute.networkViewer` + `dns.reader` (pre-flight) |
| custom rola `vpcScPositiveControlReader` (gdy `positive_control_project_id` niepuste) | odczyt wpisów logu w **jednym** projekcie sondującym — kontrola pozytywna sondy granicy. Zastępuje rolę org-wide: dowód „reguła baseline **wpuszcza**" przestaje kosztować prawo odczytu każdego logu w organizacji, a liczba nadań nie rośnie z liczbą członków |
| `storage.objectAdmin` na **prefiksie** stanu | backend GCS bierze blokadę (`.tflock`), sam odczyt nie wystarcza nawet dla `plan` |
| pula WIF + provider z `attribute_condition` | dostęp keyless; warunek pinuje **jedno** repozytorium |
| custom rola `vpcScDenyReader` | `iam.denypolicies.get/list` — **jedyny** sposób, żeby ktokolwiek w organizacji odpowiedział „czy Deny stoi"; org-admin tego prawa nie ma z urzędu |
| IAM Deny na `servicePerimeters.delete` / `policies.delete` (gdy `manage_deny_policy`) | twardy zakaz ponad rolami; zapis do tej warstwy wymaga `roles/iam.denyAdmin` i nie da się go zawęzić |

## Trzy rzeczy, które warto podnieść przy zatwierdzaniu requestu

**1. To NIE jest `policyEditor`.** Predefiniowana rola daje read-write na politykach razem z prawem
usunięcia perimetru. Perimetr już istnieje i ma istnieć dalej, więc bierzemy wyłącznie `update`. Różnicę
widać jednym poleceniem:

```bash
gcloud iam roles describe roles/accesscontextmanager.policyEditor --format='value(includedPermissions)'
```

**2. Zakres org-level nie jest naszym wyborem.** Uprawnienia Access Context Managera można nadać wyłącznie
na organizacji albo na konkretnej polityce — grant na folderze lub projekcie **nie ma żadnego efektu**
([docs](https://docs.cloud.google.com/access-context-manager/docs/access-control)). Dlatego zawężamy zestaw
operacji (custom rola + Deny), a nie zasięg. To pierwsze pytanie, które padnie na review.

**3. `_member`, nigdy `_binding`.** `google_organization_iam_binding` jest **authoritative** dla całej roli
na organizacji: przejąłby ją i przy pierwszym apply usunął wszystkie inne przypisania tej roli w firmie.
W tym kodzie jest wyłącznie `google_organization_iam_member`.

## Uruchomienie

```bash
cp terraform.tfvars.sample terraform.tfvars    # uzupełnij 4 wartości
terraform init
terraform plan     # <- to jest artefakt do review; przeczytać PRZED apply
terraform apply
```

## Weryfikacja po apply (dowód, nie założenie)

```bash
# custom rola ma dokładnie 9 uprawnień i ani jednego create/delete
gcloud iam roles describe vpcScPerimeterWriter --organization=<ORG_ID> \
  --format='value(includedPermissions)' | tr ',' '\n'

# konto plan realnie czyta perimetr
gcloud access-context-manager perimeters list --policy=<POLICY> \
  --impersonate-service-account=sa-vpcsc-plan@<PROJ>.iam.gserviceaccount.com

# konto plan NIE może nic zmienić (ma się nie udać — to jest ten test, który potwierdza podział)
gcloud access-context-manager perimeters update <PERIMETER> --policy=<POLICY> \
  --add-resources=projects/<NUM> \
  --impersonate-service-account=sa-vpcsc-plan@<PROJ>.iam.gserviceaccount.com

# konto apply też nie skasuje perimetru
gcloud access-context-manager perimeters delete <PERIMETER> --policy=<POLICY> \
  --impersonate-service-account=sa-vpcsc-apply@<PROJ>.iam.gserviceaccount.com
```

Dwa ostatnie polecenia **mają zakończyć się błędem**. Jeśli przejdą, podział uprawnień nie działa i nie ma
sensu iść dalej — a dowiedzieć się o tym z testu jest tanio, z incydentu drogo.

**Czego to ostatnie polecenie NIE dowodzi.** Odmowa przychodzi z **braku roli** — `vpcScPerimeterWriter`
świadomie nie zawiera `servicePerimeters.delete` — a nie z warstwy Deny. Wynik byłby identyczny, gdyby
polityki deny nie było wcale. Deny istnieje na wypadek, że ktoś tę rolę **podmieni** („dajmy na chwilę
`policyEditor`, żeby odblokować release"), więc uczciwy test musi odtworzyć tę sytuację — opisuje go
sekcja niżej.

## Test warstwy Deny — jak sprawdzić, że zakaz BIJE rolę

Rzecz, która wywraca naiwną wersję tego testu, i którą trzeba znać **przed** jego zaplanowaniem:
**odmowa z warstwy Deny wygląda w API dokładnie tak samo jak odmowa z braku roli.** Wywołanie odbite
polityką deny kończy się dosłownie tym:

```
ERROR: (gcloud.access-context-manager.perimeters.delete) PERMISSION_DENIED: The caller does not have permission.
```

Ani nazwy polityki, ani reguły, ani słowa „deny". Grepowanie komunikatu nie jest dowodem i nie da się na
nim oprzeć bramki. Rozstrzyga **Policy Troubleshooter v3**, bo rozkłada odpowiedź na dwie niezależne części:

```bash
gcloud services enable policytroubleshooter.googleapis.com --project=<PROJ>

cat > tuple.json <<'JSON'
{"accessTuple":{
  "principal":"sa-vpcsc-apply@<PROJ>.iam.gserviceaccount.com",
  "fullResourceName":"//accesscontextmanager.googleapis.com/accessPolicies/<POLICY>/servicePerimeters/<PERIMETER>",
  "permission":"accesscontextmanager.googleapis.com/servicePerimeters.delete"}}
JSON

curl -sS -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" -H "x-goog-user-project: <PROJ>" -d @tuple.json \
  https://policytroubleshooter.googleapis.com/v3/iam:troubleshoot
```

Dowodem jest **para** pól, nigdy jedno:

| pole | wartość dowodząca | co znaczy |
|---|---|---|
| `allowPolicyExplanation.allowAccessState` | `ALLOW_ACCESS_STATE_GRANTED` | tożsamość **ma** to uprawnienie z roli |
| `denyPolicyExplanation.denyAccessState` | `DENY_ACCESS_STATE_DENIED` | mimo to zakaz ją odbija |
| `overallAccessState` | `CANNOT_ACCESS` | wynik: Deny bije allow |

Samo `CANNOT_ACCESS` niczego nie dowodzi — dokładnie tak wygląda też zwykły brak roli. Dopiero
`GRANTED` **razem z** `DENIED` mówi, że warstwa zadziałała. `denyPolicyExplanation` niesie przy tym nazwę
polityki i dopasowaną regułę (`PERMISSION_PATTERN_MATCHED`, `MEMBERSHIP_MATCHED`), więc odpowiedź wskazuje
konkretny zakaz zamiast „coś zabroniło".

**Kontrola pozytywna jest częścią testu, nie dodatkiem.** Powtórz to samo wywołanie dla uprawnienia,
którego polityka NIE wymienia — `accesscontextmanager.googleapis.com/servicePerimeters.update` — i oczekuj
`CAN_ACCESS` + `DENY_ACCESS_STATE_NOT_DENIED`. Bez tej drugiej krotki test przechodzi także wtedy, gdy
zepsuta jest impersonacja albo samo narzędzie i odpowiada „nie wolno" na wszystko.

Test „na żywo" (realna próba skasowania) wymaga trzech rzeczy naraz, więc jest ćwiczeniem pod nadzorem,
a nie krokiem listy kontrolnej:

1. tymczasowej roli **zawierającej** `servicePerimeters.delete` dla konta `apply` (np.
   `roles/accesscontextmanager.policyEditor`) — odbieranej w tym samym oknie,
2. **perimetru jednorazowego** — nigdy produkcyjnego; to jest operacja kasująca i nie ma cofnięcia,
3. okna czasowego: **propagacja polityki deny nie jest natychmiastowa.** Na żywej organizacji pierwsza
   ważna próba wypadła 7 min 31 s po utworzeniu polityki i była już odbita — to jest **górna granica**,
   nie pomiar punktowy. Planuj minuty, nie sekundy, i nie raportuj „nie działa" po pierwszej próbie.

## Kto ma trzymać `roles/iam.denyAdmin`

**Nie właściciel perimetru.** Cała wartość tej warstwy polega na tym, że przeżywa podmianę roli przez
operatora perimetru. Jeśli ta sama osoba lub grupa może zakaz zdjąć, warstwa nie stoi **ponad** rolami,
tylko **obok** nich: chroni przed cudzym błędem, ale nie przed własnym — a to drugie jest częstsze.

| kto | co dostaje | dlaczego akurat tyle |
|---|---|---|
| zespół IAM / bezpieczeństwa org | `roles/iam.denyAdmin` | jedyna rola z `denypolicies.create`; ma być **rozłączna** z właścicielami `iam-bootstrap` i repozytorium perimetru. Grupa, nie osoba |
| właściciel perimetru | `vpcScDenyReader` | ma **umieć sprawdzić**, że zakaz stoi (i mieć czysty `terraform plan`), bez prawa jego zmiany |
| pipeline perimetru | nic z rodziny `denypolicies` | jest po stronie **zakazywanej**, nie zarządzającej |

Gdy rozdzielenie jest niewykonalne (mała organizacja, jedna osoba na org), poprawnym wariantem jest
**nadanie `denyAdmin` na czas zmiany i odebranie po niej**. `manage_deny_policy = true` i
`terraform plan = No changes` utrzymują się wtedy na samym odczycie (`vpcScDenyReader`), a każda modyfikacja
warstwy wymaga świadomego ponownego nadania — czyli break-glass dla samego guardrailu. To jedyna wersja
rozdziału obowiązków osiągalna bez drugiego człowieka i trzeba ją zapisać, bo inaczej „nadaliśmy na chwilę"
po cichu zamienia się w „mamy na stałe".

## Czy guardrail w ogóle istnieje — jedno polecenie

Najgroźniejsza właściwość tej warstwy: **`403` jest nierozróżnialny od „nie ma"**. `iam.denypolicies.*` nie
należy do żadnej roli org-admina, więc domyślną odpowiedzią na pytanie „czy Deny stoi" jest odmowa odczytu —
i `terraform plan` dostaje dokładnie to samo, przez co w nieskończoność pokazuje `1 to add` niezależnie od
stanu faktycznego. Odpowiedź musi więc przyjść spoza Terraforma:

```bash
terraform output -raw deny_policy_check   # wypisuje gotowe polecenie
tools/deny_check.sh --org <ORG_ID>        # to samo z rozłącznymi kodami wyjścia (0 jest / 1 nie ma / 2 nie wiadomo)
```

Wymaga roli `vpcScDenyReader` (tworzy ją ten stack, §5a) — nadaj ją przez `deny_reader_principals`. Bez niej
odpowiedzią jest `403`, czyli brak odpowiedzi; raportowanie tego jako „nie ma" jest błędem, nie skrótem.

**Zapisu tej warstwy nie da się zawęzić** — zmierzone, nie założone: `iam.denypolicies.get`/`.list` wolno
umieścić w roli własnej, ale `create`/`update`/`delete` mają `customRolesSupportLevel = NOT_SUPPORTED`,
a jedyną rolą predefiniowaną, która je niesie, jest `roles/iam.denyAdmin` (razem z prawem skasowania
**każdej** polityki deny w organizacji). Wdrożenie, które takiego grantu nie chce, ustawia
`manage_deny_policy = false` i **odnotowuje to jako świadomy brak warstwy** — zamiast trzymać w repo
deklarację, której nikt nie zastosował.

## Do potwierdzenia na dev przed apply

- czy `servicePerimeters.patch` wymaga u was `resourcemanager.projects.get` na dodawanym projekcie
  (jeśli tak → dochodzi `roles/browser` na folderach dywizji, nadal read-only),
- nazwy zespołów i projekt tożsamości — wpisane w `terraform.tfvars`.
