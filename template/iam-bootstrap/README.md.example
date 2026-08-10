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
polityki deny nie było wcale, i przez jakiś czas dokładnie tak było. Deny istnieje na wypadek, że ktoś tę
rolę **podmieni** („dajmy na chwilę `policyEditor`, żeby odblokować release"), więc jedynym uczciwym testem
jest odtworzenie tej sytuacji: nadać kontu `apply` rolę **zawierającą** `servicePerimeters.delete`, powtórzyć
polecenie i sprawdzić, że odmowa **nadal** przychodzi — tym razem z komunikatem o polityce deny. To jest
ćwiczenie pod nadzorem (wymaga `roles/iam.denyAdmin` i tymczasowego grantu), a nie krok listy kontrolnej.

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
