# Perimetr już istnieje — jak się podłączyć bez psucia cudzej konfiguracji

Domyślny tryb startera jest **brownfield**: `perimeter.manage_skeleton: false` w `perimeter/policy.yaml`.
Terraform dokłada wtedy wyłącznie **członków i reguły**, a treść perimetru (`restricted_services`,
`vpc_accessible_services`) zostaje u obecnego właściciela.

## Dlaczego to jest tryb domyślny

Pierwszy apply na cudzym, żywym perimetrze ma dwa możliwe kształty:

1. **Dokładamy zasoby** (członkowie, reguły) — najgorszy błąd to reguła, która nie zadziała.
2. **Przejmujemy szkielet** — najgorszy błąd to **nadpisanie listy chronionych usług** treścią z naszego
   `policy.yaml`, czyli wyłączenie ochrony dla usług, o których nie wiedzieliśmy. Perimetr dalej wygląda
   w konsoli na włączony.

Drugi wariant jest odwracalny tylko wtedy, gdy ktoś ma zapisany poprzedni stan. Dlatego zaczynamy od
pierwszego — a przejęcie szkieletu jest osobną, świadomą decyzją.

## Co działa w trybie brownfield

Wszystko poza zarządzaniem baseline'em: członkostwo (dry-run i enforced), reguły z profili, access levels,
bramki OPA, budżet atrybutów, raport naruszeń, drift detection (na zasobach, które kontrolujemy), break-glass.

`restricted_services` w `policy.yaml` pełni wtedy rolę **dokumentacji i wejścia dla guardów** — reguła
`onboarding.rego` nadal odrzuci wyjęcie `aiplatform`, mimo że ta lista nie leci do API.

## Kiedy warto przejąć szkielet

Gdy zespół perimetru staje się jego właścicielem także formalnie — bo wtedy baseline zaczyna podlegać temu
samemu review i tej samej historii co reszta. Do tego czasu każda zmiana baseline'u jest robiona przez
obecnego właściciela poza tym repo, więc **drift detection jej nie wykryje** (nie znamy stanu oczekiwanego).

## Procedura przejęcia (jednorazowa, za bramką człowieka)

1. **Zrzuć stan faktyczny** i przepisz go do `policy.yaml` — nie odwrotnie:

```bash
gcloud access-context-manager perimeters describe ai_core \
  --policy=<ACCESS_POLICY_NUMBER> --format=yaml > /tmp/live-perimeter.yaml
```

Przenieś z niego `restrictedServices` i `vpcAccessibleServices` do `perimeter/policy.yaml` **dosłownie**.

2. **Zaimportuj** zasób szkieletu:

```bash
# manage_skeleton: true w policy.yaml PRZED importem
terraform -chdir=terraform import 'google_access_context_manager_service_perimeter.this[0]' \
  accessPolicies/<ACCESS_POLICY_NUMBER>/servicePerimeters/ai_core
```

3. **Plan MUSI pokazać zero zmian.** To jest jedyny akceptowalny wynik — dowodzi, że `policy.yaml` opisuje
   rzeczywistość, a nie nasze wyobrażenie o niej.

```bash
terraform -chdir=terraform plan -detailed-exitcode   # oczekiwany kod wyjścia: 0
```

Jeśli plan chce cokolwiek zmienić: **nie applikuj**. Różnica oznacza, że coś w żywym perimetrze jest inne
niż w pliku — dopisz to do `policy.yaml` i powtórz, aż plan będzie pusty.

4. Dopiero teraz zostaw `manage_skeleton: true` i zmerguj PR z tą zmianą.

## Czego NIE robić

- **Nie ustawiaj `manage_skeleton: true` bez importu.** Terraform spróbuje utworzyć perimetr, który już
  istnieje — w najlepszym razie apply padnie, w gorszym trafisz na obiekt o tej samej nazwie w innej polityce.
- **Nie „naprawiaj" niepustego planu po imporcie przez apply.** To jest moment, w którym nadpisuje się cudzą
  konfigurację. Niepusty plan to informacja, nie przeszkoda.
- **Nie importuj przy okazji innego PR-a.** Import zmienia stan, a nie kod — powinien być własną zmianą,
  z własnym opisem i własnym momentem w czasie.
