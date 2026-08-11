# Bramki na KSZTAŁCIE reguł — działają na plan-JSON (`terraform show -json plan.out`).
#
# DLACZEGO na planie, a nie na YAML-u: YAML mówi, co ktoś napisał; plan mówi, co realnie poleci do API po
# przejściu przez renderer. Reguła, która przeszła przez profil i lookup parametrów, może wyglądać inaczej
# niż deklaracja — a to plan jest tym, co zmieni granicę bezpieczeństwa (zasada „waliduj efekt, nie referencję").

package vpcsc.perimeter

import rego.v1

rule_resources := {
	"google_access_context_manager_service_perimeter_ingress_policy",
	"google_access_context_manager_service_perimeter_dry_run_ingress_policy",
	"google_access_context_manager_service_perimeter_egress_policy",
	"google_access_context_manager_service_perimeter_dry_run_egress_policy",
}

planned contains r if {
	some r in input.planned_values.root_module.resources
	r.type in rule_resources
}

# --- tożsamości -------------------------------------------------------------------------------------

# ANY_IDENTITY / ANY_SERVICE_ACCOUNT / ANY_USER_ACCOUNT znoszą sens granicy: reguła autoryzuje wtedy
# każdego, kto zdobędzie odpowiedni token. Dla części operacji (np. eksport sinka do GCS) wildcard w ogóle
# NIE autoryzuje wywołującego — więc bywa jednocześnie zbyt szeroki i nieskuteczny.
deny contains msg if {
	some r in planned
	some block in array.concat(
		object.get(r.values, "ingress_from", []),
		object.get(r.values, "egress_from", []),
	)
	block.identity_type != null
	block.identity_type != ""
	msg := sprintf("%s: identity_type=%q — używaj imiennych tożsamości, nigdy ANY_*", [r.address, block.identity_type])
}

# Reguła bez ani jednej tożsamości nie ogranicza wywołującego w żaden sposób.
deny contains msg if {
	some r in planned
	some block in array.concat(
		object.get(r.values, "ingress_from", []),
		object.get(r.values, "egress_from", []),
	)
	count(object.get(block, "identities", [])) == 0
	msg := sprintf("%s: reguła bez identities — nie ma czego autoryzować", [r.address])
}

# ACM waliduje ISTNIENIE tożsamości po swojej stronie i odrzuca CAŁĄ zmianę:
# `The email address ... is invalid or non-existent` (zmierzone na żywym API, Issue #1904). Literówka w koncie
# serwisowym wywraca więc apply dopiero PO review, na obiekcie org-plane — a wygląda jak problem z uprawnieniami.
#
# Istnienia konta nie da się sprawdzić bez chmury, ale KSZTAŁT adresu tak — i to on łapie najczęstszą pomyłkę
# (zjedzone `.iam`, `gserviceaccounts.com` przez „s", adres bez domeny). Resztę domyka `tools/preflight_check.sh
# --identity`, który pyta API o istnienie i wymaga poświadczeń.
#
# ŚWIADOMIE nie walidujemy nazwy projektu w adresie ani nie wymagamy domeny `*.iam.gserviceaccount.com`:
# konta domyślne i zarządzane przez Google mieszkają pod `developer.`, `appspot.`, `cloudbuild.`. Bramka
# odrzucająca poprawne konto blokuje onboarding, a to kosztuje więcej niż jedna literówka wykryta przy apply.
deny contains msg if {
	some r in planned
	some block in array.concat(
		object.get(r.values, "ingress_from", []),
		object.get(r.values, "egress_from", []),
	)
	some identity in object.get(block, "identities", [])
	not identity_ma_poprawny_ksztalt(identity)
	msg := sprintf(
		"%s: tożsamość %q ma nieprawidłowy kształt — ACM odrzuci apply komunikatem `invalid or non-existent`",
		[r.address, identity],
	)
}

identity_ma_poprawny_ksztalt(identity) if {
	regex.match(`^serviceAccount:[^@\s]+@[^@\s]+\.gserviceaccount\.com$`, identity)
}

identity_ma_poprawny_ksztalt(identity) if {
	regex.match(`^(user|group):[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$`, identity)
}

# Federacja tożsamości (Workforce/Workload Identity) ma kształt URI, nie adresu e-mail. Dopuszczamy bez
# dalszej walidacji: bramka, która tej formy nie zna, odrzuciłaby poprawną konfigurację.
identity_ma_poprawny_ksztalt(identity) if {
	some prefix in ["principal://", "principalSet://", "principalHierarchy://"]
	startswith(identity, prefix)
}

# --- metody -----------------------------------------------------------------------------------------

# Usługi, dla których Access Context Manager NIE PUBLIKUJE listy metod (`supportedMethods` puste). Lista
# przychodzi z `policy.yaml` przez `conftest --data perimeter/policy.yaml`, czyli jest deklaracją pod
# CODEOWNERS security — a `tools/check_supported_services.py` w `plan.yml` konfrontuje ją z żywym API.
#
# BRAK pliku danych = pusty zbiór = każdy `*` odrzucony. Fail-closed jest tu celowy: bramka, która przy
# zapomnianym `--data` po cichu przepuszcza wildcardy, jest gorsza od jej braku.
#
# `default` daje pustą listę, gdy ścieżki nie ma. Bez niej reguła byłaby NIEZDEFINIOWANA i `deny` przestałby
# się wykonywać w ogóle — czyli zapomniane `--data` otwierałoby wszystkie wildcardy zamiast je zamykać.
default uslugi_bez_selektorow_metod := []

uslugi_bez_selektorow_metod := data.services_without_method_selectors

# `*` w metodach zamienia wąską regułę (predict) w prawo do całego API usługi (trening, eksport modelu,
# odczyt datasetów). To najczęstszy skrót, po którym profil przestaje cokolwiek ograniczać.
#
# WYJĄTEK — i to nie jest poluzowanie, tylko granica reguły: dla usług bez opublikowanych metod (Vertex AI,
# Notebooks, Monitoring) `*` jest JEDYNĄ wartością, jaką API przyjmuje. Wypisanie metod jawnie kończy się
# `Error 400: METHOD ... is not supported`, czyli regułą, która nie powstaje. Wybór jest między `*`
# a brakiem ochrony tej usługi — nie między `*` a czymś węższym. Zmierzone na żywym ACM (Issue #1904).
deny contains msg if {
	some r in planned
	some to_block in array.concat(
		object.get(r.values, "ingress_to", []),
		object.get(r.values, "egress_to", []),
	)
	some op in object.get(to_block, "operations", [])
	some sel in object.get(op, "method_selectors", [])
	sel.method == "*"
	not op.service_name in uslugi_bez_selektorow_metod
	msg := sprintf("%s: method=\"*\" na %s — wypisz metody jawnie", [r.address, op.service_name])
}

# --- zasięg -----------------------------------------------------------------------------------------

# `resources = ["*"]` po stronie ingress oznacza „dowolny projekt w perimetrze", czyli regułę napisaną dla
# jednej dywizji, która działa na wszystkich. Dozwolone wyłącznie razem z access levelem, i tak niechętnie.
deny contains msg if {
	some r in planned
	some to_block in object.get(r.values, "ingress_to", [])
	"*" in object.get(to_block, "resources", [])
	msg := sprintf("%s: ingress_to.resources=[\"*\"] — celuj w konkretny projekt członka", [r.address])
}

# Ingress spoza perimetru bez access levelu opiera się wyłącznie na tożsamości: skradziony token działa
# wtedy z dowolnej sieci. Access level dokłada warunek kontekstu, którego token nie niesie.
#
# WYJĄTEK: reguły baseline (skanery, monitoring) wołają z własnej infrastruktury dostawcy i nie spełnią
# korporacyjnego access levelu. Muszą być oznaczone `allow_without_access_level: true` w policy.yaml —
# czyli świadomie, w pliku pod CODEOWNERS security, a nie przez pominięcie pola w cichym PR-ze.
#
# ROZPOZNAJEMY JE PO DOKŁADNYM TYTULE Z `policy.yaml`, NIE PO PODCIĄGU. Renderer nadaje regule zbiorczej
# postać `baseline--<tytuł>` (jedna reguła na tytuł, lista zasobów wszystkich członków). Poprzedni warunek
# szukał podciągu `--baseline--` w tytule i był SPRAWDZALNIE OBCHODZALNY: tytuł reguły profilowej powstaje
# jako `<członek>--<tytuł z profilu>`, więc profil z tytułem zaczynającym się od `-baseline--` dawał tytuł
# zawierający ten podciąg — i dywizja wyłączała sobie wymóg access levelu własnym plikiem. Porównanie ze
# zbiorem tytułów zadeklarowanych w `policy.yaml` (plik pod CODEOWNERS security) tej furtki nie ma.
baseline_titles contains t if {
	some r in data.baseline_ingress
	t := sprintf("baseline--%s", [r.title])
}

deny contains msg if {
	some r in planned
	r.type in {
		"google_access_context_manager_service_perimeter_ingress_policy",
		"google_access_context_manager_service_perimeter_dry_run_ingress_policy",
	}
	some block in object.get(r.values, "ingress_from", [])
	count(object.get(block, "sources", [])) == 0
	not object.get(r.values, "title", "") in baseline_titles
	msg := sprintf("%s: ingress bez access levelu — dodaj warunek kontekstu (sieć / urządzenie)", [r.address])
}

# --- baseline w planie ------------------------------------------------------------------------------

# Gdy Terraform zarządza szkieletem (greenfield / po imporcie), plan MUSI nadal chronić Vertex AI.
# Przy brownfield ten zasób w planie nie występuje i regułę pokrywa onboarding.rego na policy.yaml.
deny contains msg if {
	some r in input.planned_values.root_module.resources
	r.type == "google_access_context_manager_service_perimeter"
	some cfg in array.concat(
		object.get(r.values, "status", []),
		object.get(r.values, "spec", []),
	)
	not "aiplatform.googleapis.com" in object.get(cfg, "restricted_services", [])
	msg := sprintf("%s: konfiguracja perimetru bez aiplatform.googleapis.com w restricted_services", [r.address])
}

# --- operacje destrukcyjne --------------------------------------------------------------------------

# Usunięcie perimetru albo access levelu to operacja break-glass, nie rutyna PR-owa. CI nie powinien mieć
# nawet uprawnienia do `servicePerimeters.delete` (IAM Deny), ale bramka jest tańsza niż wykrycie po fakcie.
deny contains msg if {
	some rc in input.resource_changes
	rc.type in {
		"google_access_context_manager_service_perimeter",
		"google_access_context_manager_access_level",
	}
	"delete" in rc.change.actions
	msg := sprintf("%s: plan usuwa obiekt polityki dostępu — to ścieżka break-glass, nie zwykły PR", [rc.address])
}
