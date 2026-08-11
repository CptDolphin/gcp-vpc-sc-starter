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

test_wildcard_resources_denied if {
	bad := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_to/0/resources", "value": ["*"]}])
	count(deny) > 0 with input as plan_with([bad])
}

# Ingress bez access levelu opiera się wyłącznie na tożsamości — skradziony token działa z dowolnej sieci.
test_ingress_without_access_level_denied if {
	bad := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_from/0/sources", "value": []}])
	count(deny) > 0 with input as plan_with([bad])
}

# Reguła baseline WOLNO mieć bez access levelu — ale tylko ta, której tytuł stoi w `policy.yaml`.
test_baseline_without_access_level_allowed if {
	bez_zrodla := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_from/0/sources", "value": []}])
	baseline := json.patch(bez_zrodla, [{"op": "add", "path": "/values/title", "value": "baseline--security-scanner-read"}])
	count(deny) == 0 with input as plan_with([baseline])
		with data.baseline_ingress as [{"title": "security-scanner-read"}]
}

# ANTY-OBEJŚCIE. Poprzedni warunek szukał podciągu `--baseline--`, a tytuł reguły profilowej powstaje jako
# `<członek>--<tytuł z profilu>` — więc profil nazwany `-baseline--cokolwiek` produkował tytuł zawierający
# ten podciąg i wyłączał sobie wymóg access levelu plikiem, który dywizja pisze sama. Tytuł spoza
# `policy.yaml` MUSI być odrzucony, choćby wyglądał baseline'owo.
test_baseline_lookalike_title_denied if {
	bez_zrodla := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_from/0/sources", "value": []}])
	podszywka := json.patch(bez_zrodla, [{"op": "add", "path": "/values/title", "value": "dywizja---baseline--wlasna-regula"}])
	count(deny) > 0 with input as plan_with([podszywka])
		with data.baseline_ingress as [{"title": "security-scanner-read"}]
}

# Bez `--data perimeter/policy.yaml` zbiór tytułów jest PUSTY, więc wyjątek nie obowiązuje nikogo. Zapomniane
# `--data` ma zamykać furtkę, nie otwierać ją wszystkim (ta sama zasada co przy `uslugi_bez_selektorow_metod`).
test_baseline_exception_closed_without_data if {
	bez_zrodla := json.patch(good_rule, [{"op": "replace", "path": "/values/ingress_from/0/sources", "value": []}])
	baseline := json.patch(bez_zrodla, [{"op": "add", "path": "/values/title", "value": "baseline--security-scanner-read"}])
	count(deny) > 0 with input as plan_with([baseline])
}

test_perimeter_without_aiplatform_denied if {
	skeleton := {
		"address": "google_access_context_manager_service_perimeter.this[0]",
		"type": "google_access_context_manager_service_perimeter",
		"values": {"status": [{"restricted_services": ["storage.googleapis.com"]}], "spec": [{"restricted_services": ["storage.googleapis.com"]}]},
	}
	count(deny) > 0 with input as plan_with([skeleton])
}

test_perimeter_with_aiplatform_passes if {
	skeleton := {
		"address": "google_access_context_manager_service_perimeter.this[0]",
		"type": "google_access_context_manager_service_perimeter",
		"values": {"status": [{"restricted_services": ["aiplatform.googleapis.com"]}], "spec": [{"restricted_services": ["aiplatform.googleapis.com"]}]},
	}
	count(deny) == 0 with input as plan_with([skeleton])
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
