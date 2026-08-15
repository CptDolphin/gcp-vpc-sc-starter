# Testy bramek na plan-JSON. Wejście to uproszczony, ale REALNY kształt `terraform show -json`:
# planned_values.root_module.resources[] + resource_changes[].

package vpcsc.perimeter

import rego.v1

good_rule := {
	"address": "google_access_context_manager_service_perimeter_ingress_policy.rule[\"x\"]",
	"type": "google_access_context_manager_service_perimeter_ingress_policy",
	"values": {
		"ingress_from": [{"identities": ["serviceAccount:a@b.iam.gserviceaccount.com"], "sources": [{"access_level": "accessPolicies/1/accessLevels/corp_network"}]}],
		"ingress_to": [{"resources": ["projects/111111111111"], "operations": [{"service_name": "aiplatform.googleapis.com", "method_selectors": [{"method": "google.cloud.aiplatform.v1.PredictionService.Predict"}]}]}],
	},
}

plan_with(resources) := {"planned_values": {"root_module": {"resources": resources}}, "resource_changes": []}

test_good_rule_passes if {
	count(deny) == 0 with input as plan_with([good_rule])
}

test_any_identity_denied if {
	bad := json.patch(good_rule, [{"op": "add", "path": "/values/ingress_from/0/identity_type", "value": "ANY_IDENTITY"}])
	count(deny) > 0 with input as plan_with([bad])
}

test_empty_identities_denied if {
	bad := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_from/0/identities", "value": []}])
	count(deny) > 0 with input as plan_with([bad])
}

# Literówki, które ACM odrzuca dopiero przy apply (`invalid or non-existent`) — każda przechodziła przez
# wszystkie bramki startera do 2026-08-07 (Issue #1904).
test_malformed_identity_denied if {
	every zly in [
		"serviceAccount:a@b.iam.gserviceaccounts.com", # domena przez „s"
		"serviceAccount:a@b.iam.gserviceaccount", # ucięta domena
		"serviceAccount:a-bez-domeny", # sam login
		"a@b.iam.gserviceaccount.com", # brak prefiksu typu
		"serviceAccount:", # pusty adres
		"user:ktos", # user bez domeny
	] {
		bad := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_from/0/identities", "value": [zly]}])
		count(deny) > 0 with input as plan_with([bad])
	}
}

# Kształty POPRAWNE muszą przejść. Bramka odrzucająca konto domyślne albo federację blokuje onboarding,
# a to jest droższe niż literówka wykryta przy apply — stąd świadomie luźny wzorzec domeny.
test_valid_identity_shapes_pass if {
	every dobry in [
		"serviceAccount:sa-example@prj-example.iam.gserviceaccount.com", # konto użytkownika
		"serviceAccount:123456789012-compute@developer.gserviceaccount.com", # domyślne konto Compute
		"serviceAccount:prj-example@appspot.gserviceaccount.com", # domyślne konto App Engine
		"serviceAccount:service-123456789012@gcp-sa-aiplatform.iam.gserviceaccount.com", # konto Google
		"user:example.person@example.com",
		"group:grp-example-ds@example.com",
		"principalSet://iam.googleapis.com/projects/123456789012/locations/global/workloadIdentityPools/example/*",
	] {
		ok := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_from/0/identities", "value": [dobry]}])
		count(deny) == 0 with input as plan_with([ok])
	}
}

# `*` w metodach zamienia „wywołaj predict" w „rób z tym API co chcesz".
test_wildcard_method_denied if {
	bad := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_to/0/operations/0/method_selectors/0/method", "value": "*"}])
	count(deny) > 0 with input as plan_with([bad])
}

# Wyjątek dla usług, dla których API nie publikuje metod. `*` jest tam JEDYNĄ wartością, jaką ACM przyjmuje,
# więc bramka musi ją przepuścić — inaczej profil dla Vertex AI nie ma jak powstać (zmierzone, Issue #1904).
test_wildcard_allowed_for_service_without_published_methods if {
	bad := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_to/0/operations/0/method_selectors/0/method", "value": "*"}])
	count(deny) == 0 with input as plan_with([bad])
		with data.services_without_method_selectors as ["aiplatform.googleapis.com"]
}

# FAIL-CLOSED: bez pliku danych (`conftest --data` zapomniane) zbiór wyjątków jest pusty i `*` leci na ziemię.
# Bramka, która przy zapomnianej fladze po cichu przepuszcza wildcardy, jest gorsza od jej braku.
test_wildcard_denied_when_data_missing if {
	bad := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_to/0/operations/0/method_selectors/0/method", "value": "*"}])
	count(deny) > 0 with input as plan_with([bad])
}

# Wyjątek jest WĄSKI: dotyczy wymienionej usługi, nie wszystkich. `*` na storage zostaje zakazane nawet wtedy,
# gdy lista wyjątków istnieje — inaczej jeden wpis otwierałby wildcardy w całym katalogu profili.
test_wildcard_still_denied_for_other_service if {
	bad := json.patch(good_rule, [
		{"op": "replace", "path": "/values/ingress_to/0/operations/0/service_name", "value": "storage.googleapis.com"},
		{"op": "replace", "path": "/values/ingress_to/0/operations/0/method_selectors/0/method", "value": "*"},
	])
	count(deny) > 0 with input as plan_with([bad])
		with data.services_without_method_selectors as ["aiplatform.googleapis.com"]
}

# Reguła DYWIZJI z gwiazdką w celu = „napisana dla jednego zespołu, działa na projektach wszystkich".
# Zakaz jest bezwarunkowy i wyjątek go nie dotyka: `good_rule` ma tytuł spoza `policy.yaml`.
test_wildcard_resources_denied if {
	bad := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_to/0/resources", "value": ["*"]}])
	count(deny) > 0 with input as plan_with([bad])
}

# Ingress bez access levelu opiera się wyłącznie na tożsamości — skradziony token działa z dowolnej sieci.
test_ingress_without_access_level_denied if {
	bad := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_from/0/sources", "value": []}])
	count(deny) > 0 with input as plan_with([bad])
}

# --- wyjątki dla baseline'u: rozpoznanie PO TREŚCI, nie po nazwie -------------------------------------
#
# Deklaracja odwzorowuje `policy.yaml §baseline_ingress` i jest WSPÓLNYM wejściem obu wyjątków (gwiazdka
# w `resources`, brak access levelu). Testy niżej mutują po jednym elemencie naraz — to jedyny sposób,
# żeby pokazać, KTÓRY warunek trzyma bramkę, a nie że „jakoś przechodzi".
baseline_declaration := [{
	"title": "security-scanner-read",
	"identities": ["serviceAccount:sa-scanner@prj-example.iam.gserviceaccount.com"],
	"operations": [{"service": "storage.googleapis.com", "methods": ["google.storage.buckets.get"]}],
}]

# Reguła zbiorcza baseline tak, jak renderuje ją `terraform/locals.tf`: tytuł `baseline--<tytuł>`,
# źródło `*` (z `allow_without_access_level`), cel `*` (nie lista projektów).
baseline_rule := {
	"address": "google_access_context_manager_service_perimeter_dry_run_ingress_policy.rule[\"baseline--security-scanner-read\"]",
	"type": "google_access_context_manager_service_perimeter_dry_run_ingress_policy",
	"values": {
		"title": "baseline--security-scanner-read",
		"ingress_from": [{
			"identities": ["serviceAccount:sa-scanner@prj-example.iam.gserviceaccount.com"],
			"sources": [{"access_level": "*"}],
		}],
		"ingress_to": [{"resources": ["*"], "operations": [{
			"service_name": "storage.googleapis.com",
			"method_selectors": [{"method": "google.storage.buckets.get", "permission": null}],
		}]}],
	},
}

test_baseline_wildcard_resources_allowed if {
	count(deny) == 0 with input as plan_with([baseline_rule])
		with data.baseline_ingress as baseline_declaration
}

# TA SAMA REGUŁA, ALE W KSZTAŁCIE Z PLANU BEZ ZMIAN — i to jest test na zmierzony tryb awarii, nie na
# wariant składni.
#
# Nieustawiony selektor przychodzi w planie TWORZĄCYM zasób jako `null` (fixture wyżej), a w planie,
# który go tylko odczytał ze stanu (`No changes`), jako **pusty string**. Przed poprawką `uprawnienia_z_planu`
# liczyło `""` jako ustawione uprawnienie, więc porównanie z pustą deklaracją w `policy.yaml` przestawało
# się zgadzać, wyjątek dla baseline'u przestawał obowiązywać i bramka odrzucała regułę, która nie zmieniła
# się ani o bajt. ZMIERZONE na żywym planie repozytorium perimetru: bramka była zielona na pull requeście,
# który wprowadzał `*` (tam wszystko było `create`), i czerwona na każdym następnym.
#
# Werdykt bramki nie może zależeć od tego, czy zasób właśnie powstaje, czy już stoi — dlatego oba kształty
# mają tu własny test, a nie jeden „reprezentatywny".
test_baseline_wildcard_allowed_takze_w_planie_bez_zmian if {
	ze_stanu := json.patch(baseline_rule, [{
		"op": "replace",
		"path": "/values/ingress_to/0/operations/0/method_selectors/0/permission",
		"value": "",
	}])
	count(deny) == 0 with input as plan_with([ze_stanu])
		with data.baseline_ingress as baseline_declaration
}

# ANTY-TAUTOLOGIA do powyższego: pusty string ma być traktowany jak „nie ustawiono", a NIE jak „wszystko
# przechodzi". Realne uprawnienie spoza deklaracji nadal musi odbierać wyjątek.
test_baseline_wildcard_denied_for_extra_permission if {
	podszywka := json.patch(baseline_rule, [{
		"op": "replace",
		"path": "/values/ingress_to/0/operations/0/method_selectors/0",
		"value": {"method": "google.storage.buckets.get", "permission": "storage.objects.delete"},
	}])
	count(deny) > 0 with input as plan_with([podszywka])
		with data.baseline_ingress as baseline_declaration
}

# Reguła baseline WOLNO mieć bez access levelu — ten sam predykat rozstrzyga oba wyjątki.
test_baseline_without_access_level_allowed if {
	bez_zrodla := json.patch(baseline_rule, [
		{"op": "replace", "path": "/values/ingress_from/0/sources", "value": []},
		{"op": "replace", "path": "/values/ingress_to/0/resources", "value": ["projects/111111111111"]},
	])
	count(deny) == 0 with input as plan_with([bez_zrodla])
		with data.baseline_ingress as baseline_declaration
}

# ANTY-OBEJŚCIE nr 1 (historyczne). Poprzednia generacja bramki szukała PODCIĄGU `--baseline--`, a tytuł
# reguły profilowej powstaje jako `<członek>--<tytuł z profilu>` — więc profil nazwany `-baseline--cokolwiek`
# wyłączał sobie wymóg access levelu plikiem, który dywizja pisze sama.
test_baseline_lookalike_title_denied if {
	bez_zrodla := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_from/0/sources", "value": []}])
	podszywka := json.patch(bez_zrodla, [{"op": "add", "path": "/values/title", "value": "dywizja---baseline--wlasna-regula"}])
	count(deny) > 0 with input as plan_with([podszywka])
		with data.baseline_ingress as baseline_declaration
}

# ANTY-OBEJŚCIE nr 2 (to, które zamyka ta zmiana). Klucz członka bierze się z NAZWY PLIKU w
# treści wpisu w `perimeter/projects.yaml`, więc dywizja `baseline` + profil o tytule z baseline dawał tytuł
# DOKŁADNIE równy `baseline--security-scanner-read`. Sam tytuł przestał więc wystarczać: reguła musi zgadzać
# się z deklaracją także TOŻSAMOŚCIAMI. Tu zgadza się wszystko poza nimi — i to ma wystarczyć do odmowy,
# bo inaczej dywizja wpuszczałaby WŁASNE konto na projekty wszystkich pozostałych.
test_baseline_wildcard_denied_for_foreign_identity if {
	podszywka := json.patch(baseline_rule, [{
		"op": "replace",
		"path": "/values/ingress_from/0/identities",
		"value": ["serviceAccount:sa-dywizji@prj-example.iam.gserviceaccount.com"],
	}])
	count(deny) > 0 with input as plan_with([podszywka])
		with data.baseline_ingress as baseline_declaration
}

# Ta sama tożsamość i ten sam tytuł, ale SZERSZY zakres operacji niż zatwierdzony. Bez tego testu wyjątek
# przepuszczałby „baseline plus jedna metoda ekstra" — czyli poszerzenie zakresu ukryte pod nazwą baseline'u.
test_baseline_wildcard_denied_for_extra_method if {
	podszywka := json.patch(baseline_rule, [{
		"op": "add",
		"path": "/values/ingress_to/0/operations/0/method_selectors/-",
		"value": {"method": "google.storage.objects.delete", "permission": null},
	}])
	count(deny) > 0 with input as plan_with([podszywka])
		with data.baseline_ingress as baseline_declaration
}

# ...i to samo dla DRUGIEGO pola `methodSelectors`. Pilnowanie tylko `method` było już raz luką w tym pliku.
test_baseline_wildcard_denied_for_extra_permission if {
	podszywka := json.patch(baseline_rule, [{
		"op": "add",
		"path": "/values/ingress_to/0/operations/0/method_selectors/-",
		"value": {"method": null, "permission": "storage.objects.delete"},
	}])
	count(deny) > 0 with input as plan_with([podszywka])
		with data.baseline_ingress as baseline_declaration
}

# Dołożona USŁUGA też musi wywrócić wyjątek — zbiór metod porównuje pary (usługa, metoda), więc usługa
# bez ani jednego selektora przeszłaby przez porównanie metod niezauważona.
test_baseline_wildcard_denied_for_extra_service if {
	podszywka := json.patch(baseline_rule, [{
		"op": "add",
		"path": "/values/ingress_to/0/operations/-",
		"value": {"service_name": "bigquery.googleapis.com", "method_selectors": []},
	}])
	count(deny) > 0 with input as plan_with([podszywka])
		with data.baseline_ingress as baseline_declaration
}

# Gwiazdka BEZ źródła to najgorszy możliwy kształt: maksymalny zasięg i zerowa autoryzacja (zmierzone —
# `NO_MATCHING_ACCESS_LEVEL` mimo obecnej reguły). Zgodność z deklaracją go NIE ratuje.
test_baseline_wildcard_denied_without_sources if {
	bez_zrodla := json.patch(baseline_rule, [{"op": "replace", "path": "/values/ingress_from/0/sources", "value": []}])
	count(deny) > 0 with input as plan_with([bez_zrodla])
		with data.baseline_ingress as baseline_declaration
}

# Bez `--data perimeter/policy.yaml` deklaracji nie ma, więc żaden wyjątek nie obowiązuje nikogo. Zapomniane
# `--data` ma zamykać furtkę, nie otwierać ją wszystkim (ta sama zasada co przy `uslugi_bez_selektorow_metod`).
test_baseline_exception_closed_without_data if {
	count(deny) > 0 with input as plan_with([baseline_rule])
}

test_baseline_without_access_level_closed_without_data if {
	bez_zrodla := json.patch(baseline_rule, [
		{"op": "replace", "path": "/values/ingress_from/0/sources", "value": []},
		{"op": "replace", "path": "/values/ingress_to/0/resources", "value": ["projects/111111111111"]},
	])
	count(deny) > 0 with input as plan_with([bez_zrodla])
}

szkielet_z(uslugi) := {
	"address": "google_access_context_manager_service_perimeter.this[0]",
	"type": "google_access_context_manager_service_perimeter",
	"values": {"status": [{"restricted_services": uslugi}], "spec": [{"restricted_services": uslugi}]},
}

# Bez `with data …` — czyli ścieżka DOMYŚLNA (brak deklaracji = zachowanie sprzed DEC-50).
test_perimeter_without_aiplatform_denied if {
	count(deny) > 0 with input as plan_with([szkielet_z(["storage.googleapis.com"])])
}

test_perimeter_with_aiplatform_passes if {
	count(deny) == 0 with input as plan_with([szkielet_z(["aiplatform.googleapis.com"])])
}

# PARA ANTY-TAUTOLOGICZNA (DEC-50): cudzy perimetr chroniący co innego MA PRZEJŚĆ, gdy deklaracja to
# mówi — i MA PAŚĆ, gdy plan gubi zadeklarowaną usługę. Sama pierwsza asercja niczego by nie dowiodła
# (reguła wyłączona przechodzi tak samo), sama druga też nie (reguła odrzucająca wszystko przechodzi ją).
test_perimeter_obcy_baseline_przechodzi if {
	count(deny) == 0 with input as plan_with([szkielet_z(["sqladmin.googleapis.com", "storage.googleapis.com"])])
		with data.baseline_required_services as ["sqladmin.googleapis.com"]
}

test_perimeter_obcy_baseline_bez_uslugi_denied if {
	msgs := deny with input as plan_with([szkielet_z(["storage.googleapis.com"])])
		with data.baseline_required_services as ["sqladmin.googleapis.com"]
	some m in msgs
	contains(m, "sqladmin.googleapis.com")
}

# Pusta deklaracja jest odrzucana WPROST, a nie zastępowana wartością domyślną — inaczej komunikat mówiłby
# o `aiplatform` komuś, kto tej usługi nie chroni.
test_perimeter_pusty_baseline_denied if {
	msgs := deny with input as plan_with([szkielet_z(["storage.googleapis.com"])])
		with data.baseline_required_services as []
	some m in msgs
	contains(m, "pustą listą")
}

# Kasowanie perimetru przez pipeline to ścieżka break-glass, nie zwykły PR — nawet gdy IAM na to pozwala.
test_perimeter_delete_denied if {
	inp := {
		"planned_values": {"root_module": {"resources": []}},
		"resource_changes": [{
			"address": "google_access_context_manager_service_perimeter.this[0]",
			"type": "google_access_context_manager_service_perimeter",
			"change": {"actions": ["delete"]},
		}],
	}
	count(deny) > 0 with input as inp
}

# --- kasowanie access levelu: rozstrzyga REFEROWANIE, nie sam fakt usunięcia -------------------------
#
# Gałąź access levelu tej bramki NIE MIAŁA ANI JEDNEGO TESTU do 2026-08-13 — jedyny przypadek dotyczył
# perimetru. Dlatego zrównanie obu obiektów przeżyło w szablonie tak długo: nic nie opisywało, co ma się
# stać z poziomem, którego nikt już nie używa.

skasowanie_poziomu(nazwa) := {
	"address": sprintf("google_access_context_manager_access_level.level[%q]", [nazwa]),
	"type": "google_access_context_manager_access_level",
	"change": {
		"actions": ["delete"],
		"before": {"name": sprintf("accessPolicies/1/accessLevels/%s", [nazwa])},
	},
}

# Poziom osierocony przez offboarding — ostatni krok wyprowadzenia dywizji, NIE break-glass.
test_access_level_delete_allowed_when_orphaned if {
	inp := {
		"planned_values": {"root_module": {"resources": [good_rule]}},
		"resource_changes": [skasowanie_poziomu("odchodzaca_dywizja")],
	}
	count(deny) == 0 with input as inp
}

# Kontrola anty-tautologiczna do testu wyżej: RÓŻNICA to sama nazwa poziomu. `good_rule` referuje
# `corp_network`, więc ta sama zmiana z tą jedną nazwą podmienioną MUSI zostać odrzucona — inaczej test
# „dozwolone" przechodziłby dlatego, że bramka nie działa wcale.
test_access_level_delete_denied_when_referenced_by_rule if {
	inp := {
		"planned_values": {"root_module": {"resources": [good_rule]}},
		"resource_changes": [skasowanie_poziomu("corp_network")],
	}
	count(deny) > 0 with input as inp
}

# Referencją jest też kompozycja: `required_access_levels` w innym poziomie. Renderer tej zależności nie
# zna (nazwa jest stringiem z YAML-a), więc gdyby bramka jej nie liczyła, składnik kompozycji dałoby się
# skasować pull requestem i wywrócić poziom nadrzędny.
test_access_level_delete_denied_when_referenced_by_composition if {
	kompozycja := {
		"address": "google_access_context_manager_access_level.level[\"corp_network_and_region\"]",
		"type": "google_access_context_manager_access_level",
		"values": {
			"name": "accessPolicies/1/accessLevels/corp_network_and_region",
			"basic": [{"conditions": [{"required_access_levels": ["accessPolicies/1/accessLevels/skladnik"]}]}],
		},
	}
	inp := {
		"planned_values": {"root_module": {"resources": [kompozycja]}},
		"resource_changes": [skasowanie_poziomu("skladnik")],
	}
	count(deny) > 0 with input as inp
}

# FAIL-CLOSED: plan bez nazwy usuwanego poziomu nie pozwala orzec o referowaniu — bramka odmawia.
test_access_level_delete_denied_without_name if {
	inp := {
		"planned_values": {"root_module": {"resources": []}},
		"resource_changes": [{
			"address": "google_access_context_manager_access_level.level[\"bezimienny\"]",
			"type": "google_access_context_manager_access_level",
			"change": {"actions": ["delete"], "before": {}},
		}],
	}
	count(deny) > 0 with input as inp
}

# Wymiana poziomu (ForceNew: `delete` + `create` w jednym `actions`) NIE jest wyjęta spod tej bramki.
# Między zniszczeniem a utworzeniem jest okno, w którym poziom nie istnieje, a reguły nadal go wskazują —
# czyli dokładnie ten sam błąd API, tylko trudniejszy do zauważenia w planie.
test_access_level_replace_denied_when_referenced if {
	wymiana := json.patch(skasowanie_poziomu("corp_network"), [{
		"op": "replace",
		"path": "/change/actions",
		"value": ["delete", "create"],
	}])
	inp := {
		"planned_values": {"root_module": {"resources": [good_rule]}},
		"resource_changes": [wymiana],
	}
	count(deny) > 0 with input as inp
}

# --- egress: te same bramki, ten sam ksztalt wejscia --------------------------------------------------
#
# Do 2026-08-11 ten plik nie mial ANI JEDNEGO przypadku egressowego. Bramki na tozsamosci i metody
# faktycznie obejmowaly oba kierunki (`array.concat(ingress_from, egress_from)`), ale wiedzialo sie o tym
# z lektury regul, nie z testu — a dwie bramki (`resources: ["*"]` i `roles`) obu kierunkow NIE obejmowaly
# i nikt tego nie zauwazyl, bo nie bylo czym zauwazyc.
good_egress := {
	"address": "google_access_context_manager_service_perimeter_dry_run_egress_policy.rule[\"x\"]",
	"type": "google_access_context_manager_service_perimeter_dry_run_egress_policy",
	"values": {
		"egress_from": [{"identities": ["serviceAccount:a@b.iam.gserviceaccount.com"], "sources": []}],
		"egress_to": [{
			"resources": ["projects/222222222222"],
			"external_resources": [],
			"operations": [{"service_name": "storage.googleapis.com", "method_selectors": [{"method": "google.storage.objects.get"}]}],
		}],
	},
}

test_good_egress_passes if {
	count(deny) == 0 with input as plan_with([good_egress])
}

# Regula egress NIE ma `sources` i to jest poprawne — bramka „ingress bez access levelu" nie moze na nia
# spasc. Bez tego testu kazde rozszerzenie tamtej bramki na oba kierunki wywracaloby KAZDY egress.
test_egress_bez_sources_przechodzi if {
	count(deny) == 0 with input as plan_with([good_egress])
}

test_egress_any_identity_denied if {
	bad := json.patch(good_egress, [{"op": "add", "path": "/values/egress_from/0/identity_type", "value": "ANY_IDENTITY"}])
	count(deny) > 0 with input as plan_with([bad])
}

test_egress_empty_identities_denied if {
	bad := json.patch(good_egress, [{"op": "replace", "path": "/values/egress_from/0/identities", "value": []}])
	count(deny) > 0 with input as plan_with([bad])
}

test_egress_malformed_identity_denied if {
	bad := json.patch(good_egress, [{"op": "replace", "path": "/values/egress_from/0/identities", "value": ["serviceAccount:a@b.iam.gserviceaccounts.com"]}])
	count(deny) > 0 with input as plan_with([bad])
}

test_egress_wildcard_method_denied if {
	bad := json.patch(good_egress, [{"op": "replace", "path": "/values/egress_to/0/operations/0/method_selectors/0/method", "value": "*"}])
	count(deny) > 0 with input as plan_with([bad])
}

# LUKA ZMIERZONA 2026-08-11: przechodzilo, podczas gdy ingressowy blizniak byl odrzucany. Egress `"*"`
# znaczy „dowolny zasob POZA perimetrem", czyli wiecej niz ingressowe „dowolny projekt W perimetrze".
test_egress_wildcard_resources_denied if {
	bad := json.patch(good_egress, [{"op": "replace", "path": "/values/egress_to/0/resources", "value": ["*"]}])
	count(deny) > 0 with input as plan_with([bad])
}

# WYJATEK BASELINE'U NIE PRZECIEKA NA EGRESS — i to jest asymetria SWIADOMA, nie przeoczenie. Ingressowe
# `*` znaczy „dowolny zasob W perimetrze" (zbior zamkniety, ktory sami kontrolujemy), egressowe `*` znaczy
# „dowolny zasob POZA nim". Regula o tytule i tresci baseline'u, ale w kierunku wyjscia, ma byc odrzucona.
test_egress_wildcard_resources_denied_nawet_dla_baseline if {
	bad := json.patch(good_egress, [
		{"op": "add", "path": "/values/title", "value": "baseline--security-scanner-read"},
		{"op": "replace", "path": "/values/egress_to/0/resources", "value": ["*"]},
	])
	count(deny) > 0 with input as plan_with([bad])
		with data.baseline_ingress as baseline_declaration
}

# LUKA ZMIERZONA 2026-08-11: `roles` to trzecia droga wyrazenia zakresu i zadna bramka na metody jej nie widzi.
test_egress_roles_denied if {
	bad := json.patch(good_egress, [{"op": "add", "path": "/values/egress_to/0/roles", "value": ["roles/owner"]}])
	count(deny) > 0 with input as plan_with([bad])
}

# Selektor `permission` omijal bramke wildcardu w calosci — pilnowala wylacznie pola `method`.
test_egress_wildcard_permission_denied if {
	bad := json.patch(good_egress, [{"op": "replace", "path": "/values/egress_to/0/operations/0/method_selectors", "value": [{"permission": "*"}]}])
	count(deny) > 0 with input as plan_with([bad])
}

# Ksztalt, ktory JAKO JEDYNY dziala dla zasobow zewnetrznych (zmierzone na zywym ACM) — musi przechodzic,
# inaczej bramka blokuje jedyna poprawna regule BigQuery Omni.
test_egress_omni_permission_przechodzi if {
	omni := json.patch(good_egress, [
		{"op": "replace", "path": "/values/egress_to/0/resources", "value": []},
		{"op": "replace", "path": "/values/egress_to/0/external_resources", "value": ["s3://przyklad"]},
		{"op": "replace", "path": "/values/egress_to/0/operations", "value": [{
			"service_name": "bigquery.googleapis.com",
			"method_selectors": [{"permission": "externalResource.read"}],
		}]},
	])
	count(deny) == 0 with input as plan_with([omni])
}


# --- niezmiennik regul baseline po stronie PLANU (#2066) ----------------------------------------------
#
# Para: ten sam plan, jedyna roznica to obecnosc wyrenderowanej reguly. Bez drugiego testu pierwszy
# dowodzilby wylacznie, ze cos jest czerwone.

plan_z_baseline := {"planned_values": {"root_module": {"resources": [{
	"type": "google_access_context_manager_service_perimeter_dry_run_ingress_policy",
	"values": {
		"title": "baseline--security-scanner-read",
		"ingress_from": [{"identities": ["serviceAccount:s@x.iam.gserviceaccount.com"], "sources": [{"access_level": "*"}]}],
		"ingress_to": [{"resources": ["*"], "operations": [{"service_name": "storage.googleapis.com", "method_selectors": [{"method": "google.storage.buckets.get"}]}]}],
	},
}]}}}

test_baseline_wymagany_tytul_obecny_w_planie_przechodzi if {
	count(deny) == 0 with input as plan_z_baseline
		with data.baseline_required_ingress_titles as ["security-scanner-read"]
		with data.baseline_ingress as [{
			"title": "security-scanner-read",
			"identities": ["serviceAccount:s@x.iam.gserviceaccount.com"],
			"operations": [{"service": "storage.googleapis.com", "methods": ["google.storage.buckets.get"]}],
		}]
}

# SEDNO: deklaracja zostaje, regula znika z planu. Bramka deklaracyjna tego NIE WIDZI.
test_baseline_wymagany_tytul_nieobecny_w_planie_denied if {
	pusty := {"planned_values": {"root_module": {"resources": []}}}
	count(deny) > 0 with input as pusty
		with data.baseline_required_ingress_titles as ["security-scanner-read"]
}

# Brak deklaracji = zero asercji (wdrozenie sprzed #2066 po synchronizacji nie moze zaczerwieniec).
test_baseline_bez_deklaracji_tytulow_plan_przechodzi if {
	pusty := {"planned_values": {"root_module": {"resources": []}}}
	count(deny) == 0 with input as pusty
}
