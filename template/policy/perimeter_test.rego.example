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
