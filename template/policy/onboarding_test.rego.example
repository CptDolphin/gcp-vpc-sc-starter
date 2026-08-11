# Testy bramek onboardingu. Uruchamia je `conftest verify` (lub `opa test policy/`).
#
# Każda bramka ma parę testów: POZYTYWNY (poprawne wejście przechodzi) i NEGATYWNY (złe wejście PADA).
# Sam test pozytywny niczego nie dowodzi — reguła, która nigdy nie odrzuca, też go przechodzi.

package vpcsc.onboarding

import rego.v1

base_policy := {
	"restricted_services": ["aiplatform.googleapis.com", "storage.googleapis.com"],
	"onboarding": {"dry_run_min_days": 14, "clean_window_days": 7},
}

base_profiles := {"vertex-online-serving": {
	"name": "vertex-online-serving",
	"parameters": [{"name": "caller_identities", "description": "x"}, {"name": "access_levels", "description": "y"}],
	"ingress": [{"title": "online-prediction", "identities_from": "caller_identities", "access_levels_from": "access_levels", "to": "member_project", "operations": [{"service": "aiplatform.googleapis.com", "methods": ["m"]}]}],
}}

healthy_member := {
	"division": "risk",
	"project_id": "prj-example-vertex-dev",
	"project_number": "111111111111",
	"owner_group": "grp@example.com",
	"change_ref": "snow:RITM0000001",
	"approved_by": "net@example.com",
	"stage": "dry-run",
	"dry_run_since": "2026-07-01",
	"review_by": "2027-01-01",
	"profiles": [{"name": "vertex-online-serving", "params": {"caller_identities": ["serviceAccount:a@b.iam.gserviceaccount.com"], "access_levels": ["corp_network"]}}],
	"exceptions": [],
}

contributors := [{
	"repository": "ORG/example-platform",
	"division": "risk",
	"allowed_projects": ["prj-example-vertex-dev"],
}]

healthy_input := {
	"policy": base_policy,
	"profiles": base_profiles,
	"members": {"example-prj-example-vertex-dev": healthy_member},
	# `members_list` czytają WYŁĄCZNIE reguły o duplikatach i reguła o rozjeździe liczności. Pozostałe testy
	# podmieniają członka przez `object.union`/`json.patch` na `members` i nie ruszają listy — to jest
	# bezpieczne dokładnie dlatego, że tamte reguły pytają o LICZBĘ wpisów i o powtórzenia, a nie o treść.
	# Testy samych bramek duplikatu budują oba pola jawnie (sekcja niżej).
	"members_list": [healthy_member],
	"contributors": contributors,
	"today": "2026-07-20",
	"violations_last_window": {"example-prj-example-vertex-dev": 0},
}

test_healthy_member_passes if {
	count(deny) == 0 with input as healthy_input
}

# --- duplikaty wpisów w jednym pliku (DEC-12) -------------------------------------------------------
#
# Bramka, dla której cały ten układ w ogóle wymagał zabezpieczenia: przy pliku na projekt duplikat był
# widocznym konfliktem gita, przy pliku wspólnym bywa CICHYM wynikiem scalenia. Każdy test negatywny
# ma tu parę pozytywną, bo reguła odrzucająca „dwa wpisy" byłaby regułą zakazującą drugiego członka.

drugi_czlonek(nadpisania) := object.union(
	object.union(healthy_member, {
		"division": "market",
		"project_id": "prj-example-vertex-prod",
		"project_number": "222222222222",
	}),
	nadpisania,
)

# Wejście budowane OD ZERA z listy, a nie przez `object.union(healthy_input, …)`. `object.union` scala
# GŁĘBOKO, więc podmiana `members` dokładałaby klucze do tych z `healthy_input` zamiast je zastąpić —
# mapa miałaby wtedy o jeden wpis więcej niż lista i każdy test w tej sekcji przechodziłby na regule
# o rozjeździe liczności, niezależnie od tego, co miał badać. Zmierzone: dokładnie tak padły dwa
# pierwsze przebiegi tej sekcji.
# `object.union_n` zamiast comprehension `{k: v | …}` — i to NIE jest styl. Comprehension w rego wywraca
# ewaluację na duplikacie klucza (`eval_conflict_error: object keys must be unique`), więc test o duplikacie
# klucza padałby BŁĘDEM zamiast sprawdzać bramkę. `union_n` zachowuje się tak, jak `collect_declarations.py`:
# zostawia OSTATNI wpis i nie mówi nic — czyli odtwarza dokładnie ten tryb awarii, o który tu chodzi.
wejscie_z_listy(lista) := {
	"policy": base_policy,
	"profiles": base_profiles,
	"members": object.union_n(array.concat([{}], [{klucz_wpisu(m): m} | some m in lista])),
	"members_list": lista,
	"contributors": contributors,
	"today": "2026-07-20",
	"violations_last_window": object.union_n(array.concat([{}], [{klucz_wpisu(m): 0} | some m in lista])),
}

wejscie_dwoch(a, b) := wejscie_z_listy([a, b])

# ANTY-TAUTOLOGIA — bez tego testu reguła „są dwa wpisy, więc odrzuć" przeszłaby wszystkie negatywy niżej.
test_dwoch_roznych_czlonkow_przechodzi if {
	count(deny) == 0 with input as wejscie_dwoch(healthy_member, drugi_czlonek({}))
}

# Ten sam projekt (numer) pod dwoma wpisami: dwie dywizje uważałyby się za właściciela, a każdy apply
# kasowałby wpis tej drugiej.
test_duplikat_project_number_denied if {
	count(deny) > 0 with input as wejscie_dwoch(healthy_member, drugi_czlonek({"project_number": "111111111111"}))
}

# Ten sam `project_id` przy różnych numerach = literówka w numerze, czyli CUDZY projekt dopisany do
# perimetru pod właściwie wyglądającą nazwą.
test_duplikat_project_id_denied if {
	count(deny) > 0 with input as wejscie_dwoch(healthy_member, drugi_czlonek({"project_id": "prj-example-vertex-dev"}))
}

# Dwa RÓŻNE projekty dające ten sam klucz `<dywizja>-<project_id>` — czyli jeden adres zasobu w stanie
# Terraform. Nie wynika z reguł wyżej: id i numery są tu różne. Terraform odrzuciłby to dopiero na planie,
# komunikatem o wyrażeniu `for`, którego wnioskodawca nigdy nie zobaczy.
# TRZY TESTY NIŻEJ PYTAJĄ O TREŚĆ KOMUNIKATU, A NIE O `count(deny) > 0`. Powód jest konkretny: wejście
# z duplikatem klucza łamie JEDNOCZEŚNIE regułę o kluczu i regułę o rozjeździe liczności (mapa zjada wpis),
# więc samo „coś odrzuciło" nie odróżnia bramki działającej od bramki, której nie ma. Asercja na treści
# przypina test do reguły, którą ma badać.
test_duplikat_klucza_przy_roznych_projektach_denied if {
	a := object.union(healthy_member, {"division": "risk-eu", "project_id": "prj-example-alpha"})
	b := drugi_czlonek({"division": "risk", "project_id": "eu-prj-example-alpha"})
	msgs := deny with input as wejscie_dwoch(a, b)
	some m in msgs
	contains(m, "dają ten sam klucz")
}

# BACKSTOP: mapa zjadła wpis (duplikat klucza w YAML-u, błąd kolektora, przyszła zmiana kluczowania).
# Reguła nie pyta DLACZEGO — pyta, czy liczby się zgadzają, i to jest cała jej wartość.
test_rozjazd_licznosci_mapy_i_listy_denied if {
	bad := object.union(healthy_input, {"members_list": [healthy_member, healthy_member]})
	msgs := deny with input as bad
	some m in msgs
	contains(m, "został po cichu zgubiony")
}

# Brak `members_list` w dokumencie (stare narzędzie, ręcznie sklecony declarations.json) ma ZATRZYMAĆ PR,
# a nie po cichu wyłączyć bramki duplikatu. To jest kontrola na fail-open — najgroźniejszy tryb awarii
# bramki, bo wygląda dokładnie tak samo jak jej brak przyczyny do zadziałania.
test_brak_members_list_denied if {
	bad := json.remove(healthy_input, ["members_list"])
	msgs := deny with input as bad
	some m in msgs
	contains(m, "został po cichu zgubiony")
}

test_missing_aiplatform_denied if {
	bad := object.union(healthy_input, {"policy": object.union(base_policy, {"restricted_services": ["storage.googleapis.com"]})})
	count(deny) > 0 with input as bad
}

test_unknown_profile_denied if {
	m := object.union(healthy_member, {"profiles": [{"name": "nie-ma-takiego", "params": {}}]})
	bad := object.union(healthy_input, {"members": {"example-prj-example-vertex-dev": m}})
	count(deny) > 0 with input as bad
}

test_missing_profile_param_denied if {
	m := object.union(healthy_member, {"profiles": [{"name": "vertex-online-serving", "params": {"caller_identities": ["serviceAccount:a@b.iam.gserviceaccount.com"]}}]})
	bad := object.union(healthy_input, {"members": {"example-prj-example-vertex-dev": m}})
	count(deny) > 0 with input as bad
}

test_typo_in_param_name_denied if {
	m := object.union(healthy_member, {"profiles": [{"name": "vertex-online-serving", "params": {"caller_identities": ["serviceAccount:a@b.iam.gserviceaccount.com"], "access_levels": ["corp_network"], "acces_levels": ["corp_network"]}}]})
	bad := object.union(healthy_input, {"members": {"example-prj-example-vertex-dev": m}})
	count(deny) > 0 with input as bad
}

# Promocja po 5 dniach zamiast wymaganych 14 — najczęstsza presja („zespół czeka").
test_promotion_before_window_denied if {
	m := object.union(healthy_member, {"stage": "enforced", "dry_run_since": "2026-07-15"})
	bad := object.union(healthy_input, {"members": {"example-prj-example-vertex-dev": m}})
	count(deny) > 0 with input as bad
}

test_promotion_after_window_passes if {
	m := object.union(healthy_member, {"stage": "enforced", "dry_run_since": "2026-06-01"})
	ok := object.union(healthy_input, {"members": {"example-prj-example-vertex-dev": m}})
	count(deny) == 0 with input as ok
}

# Brak raportu ≠ zero naruszeń. Bez tego testu łatwo „naprawić" bramkę przez nieuruchomienie raportu.
# UWAGA na `object.union`: robi GŁĘBOKIE scalenie, więc `{"violations_last_window": {}}` nie usunęłoby
# istniejącego wpisu — trzeba `json.patch` z operacją remove. Ten test złapał dokładnie tę pomyłkę.
test_promotion_without_report_denied if {
	bad := json.patch(healthy_input, [
		{"op": "replace", "path": "/members/example-prj-example-vertex-dev/stage", "value": "enforced"},
		{"op": "replace", "path": "/members/example-prj-example-vertex-dev/dry_run_since", "value": "2026-06-01"},
		{"op": "remove", "path": "/violations_last_window/example-prj-example-vertex-dev"},
	])
	count(deny) > 0 with input as bad
}

test_promotion_with_violations_denied if {
	m := object.union(healthy_member, {"stage": "enforced", "dry_run_since": "2026-06-01"})
	bad := object.union(healthy_input, {"members": {"example-prj-example-vertex-dev": m}, "violations_last_window": {"example-prj-example-vertex-dev": 3}})
	count(deny) > 0 with input as bad
}

# --- wyjątek od bramki promocji (onboarding.promotion_waivers) --------------------------------------
#
# Wyjątek jest bramką samą w sobie — więc każdy test pozytywny ma tu parę negatywną. Wyjątek, który
# przepuszcza wszystko, jest wyłącznikiem bramki pod inną nazwą.

waiver(nadpisania) := object.union(
	{
		"member": "example-prj-example-vertex-dev",
		"justification": "projekt utworzony pod pomiar; okno obserwacji liczone od zera, ruch w oknie pochodzi wylacznie z wlasnych sond",
		"approved_by": "sec@example.com",
		"expires": "2026-08-01",
	},
	nadpisania,
)

polityka_z_wyjatkiem(w) := object.union(base_policy, {"onboarding": object.union(base_policy.onboarding, {"promotion_waivers": [w]})})

promowany := object.union(healthy_member, {"stage": "enforced", "dry_run_since": "2026-07-15"})

wejscie_promocji(w, naruszen) := object.union(healthy_input, {
	"policy": polityka_z_wyjatkiem(w),
	"members": {"example-prj-example-vertex-dev": promowany},
	"violations_last_window": {"example-prj-example-vertex-dev": naruszen},
})

test_waiver_przepuszcza_promocje_przed_oknem if {
	count(deny) == 0 with input as wejscie_promocji(waiver({"accept_dry_run_days_below_minimum": true}), 0)
}

# Wyjątek wygasły ma NIE działać — inaczej `expires` jest komentarzem, nie warunkiem.
test_waiver_wygasly_nie_przepuszcza if {
	count(deny) > 0 with input as wejscie_promocji(waiver({"accept_dry_run_days_below_minimum": true, "expires": "2026-07-19"}), 0)
}

# Uzasadnienie poniżej progu = wyjątek nieważny. Bez tego pole degeneruje się do „ok".
test_waiver_bez_uzasadnienia_nie_przepuszcza if {
	count(deny) > 0 with input as wejscie_promocji(waiver({"accept_dry_run_days_below_minimum": true, "justification": "bo tak"}), 0)
}

# Wyjątek dla członka A nie zwalnia członka B — inaczej jedna decyzja rozlewa się na całą organizację.
test_waiver_innego_czlonka_nie_przepuszcza if {
	count(deny) > 0 with input as wejscie_promocji(waiver({"accept_dry_run_days_below_minimum": true, "member": "example-inny-projekt"}), 0)
}

# `accept_violations_up_to` jest LICZBĄ: pokrywa 2, nie pokrywa 3.
test_waiver_pokrywa_naruszenia_do_limitu if {
	count(deny) == 0 with input as wejscie_promocji(waiver({"accept_dry_run_days_below_minimum": true, "accept_violations_up_to": 2}), 2)
}

test_waiver_nie_pokrywa_powyzej_limitu if {
	count(deny) > 0 with input as wejscie_promocji(waiver({"accept_dry_run_days_below_minimum": true, "accept_violations_up_to": 2}), 3)
}

# Wyjątek na naruszenia NIE zwalnia z okna obserwacji — dwa warunki, dwie zgody.
test_waiver_na_naruszenia_nie_zwalnia_z_okna if {
	count(deny) > 0 with input as wejscie_promocji(waiver({"accept_violations_up_to": 5}), 1)
}

# Wyjątek NIE zwalnia z obowiązku posiadania raportu: „nie zmierzyliśmy" nie jest stanem, o którym da się
# podjąć decyzję. Bez tego testu wyjątek stałby się wyłącznikiem całej bramki.
test_waiver_nie_zastepuje_raportu if {
	bad := json.patch(wejscie_promocji(waiver({"accept_dry_run_days_below_minimum": true, "accept_violations_up_to": 9}), 0), [
		{"op": "remove", "path": "/violations_last_window/example-prj-example-vertex-dev"},
	])
	count(deny) > 0 with input as bad
}

# Literówka w nazwie członka ma być głośna. Cichy no-op wygląda jak działający wyjątek.
test_waiver_na_nieistniejacego_czlonka_denied if {
	bad := object.union(healthy_input, {"policy": polityka_z_wyjatkiem(waiver({"accept_dry_run_days_below_minimum": true, "member": "nie-ma-takiego"}))})
	count(deny) > 0 with input as bad
}

# Wyjątek, który nie zwalnia z niczego, wygląda w diffie jak decyzja i nie robi nic.
test_waiver_pusty_denied if {
	bad := object.union(healthy_input, {"policy": polityka_z_wyjatkiem(waiver({}))})
	count(deny) > 0 with input as bad
}

# BRAK wyjątku musi zostawić bramkę uzbrojoną. To jest kontrola na fail-open: gdyby predykaty wyjątku
# były niezdefiniowane zamiast domyślnych, całe reguły `deny` przestałyby się wykonywać i promocja
# przechodziłaby zawsze — bramka wyglądająca na obecną, przepuszczająca wszystko.
test_bez_wyjatku_bramka_dalej_odrzuca if {
	count(deny) > 0 with input as object.union(healthy_input, {"members": {"example-prj-example-vertex-dev": promowany}})
}

test_expired_review_denied if {
	m := object.union(healthy_member, {"review_by": "2026-07-01"})
	bad := object.union(healthy_input, {"members": {"example-prj-example-vertex-dev": m}})
	count(deny) > 0 with input as bad
}

test_exception_without_justification_denied if {
	m := object.union(healthy_member, {"exceptions": [{"title": "temp", "justification": "bo tak"}]})
	bad := object.union(healthy_input, {"members": {"example-prj-example-vertex-dev": m}})
	count(deny) > 0 with input as bad
}

# --- projekty płaszczyzny sterowania (anty-samo-zablokowanie) ---------------------------------------
#
# Bramka na jedyny tryb awarii, którego `git revert` nie cofa: projekt z bucketem stanu wciągnięty do
# perimetru odcina konto apply od jego własnego stanu. Testów jest tu więcej niż przy innych regułach,
# bo koszt cichej dziury jest tu najwyższy — naprawa wymaga człowieka z uprawnieniami org-level.

control_plane_input(lista) := json.patch(healthy_input, [{
	"op": "add",
	"path": "/policy/control_plane_projects",
	"value": lista,
}])

test_control_plane_project_denied if {
	count(deny) > 0 with input as control_plane_input(["prj-example-vertex-dev"])
}

# Lista przyjmuje ID albo numer. Gdyby dopasowanie szło tylko po ID, bramkę omijałoby się wpisaniem numeru —
# czyli formatem, który policy.yaml wprost dopuszcza.
test_control_plane_project_by_number_denied if {
	count(deny) > 0 with input as control_plane_input(["111111111111"])
}

# ANTY-TAUTOLOGIA: niepusta lista wskazująca INNY projekt musi przepuścić zwykłego członka. Bez tego testu
# reguła odrzucająca wszystko przechodziłaby test negatywny i wyglądała na działającą.
test_control_plane_other_project_passes if {
	count(deny) == 0 with input as control_plane_input(["prj-example-tfstate-admin"])
}

# Furtka: jawny wyjątek z uzasadnieniem przepuszcza wpis — po to, żeby nikt nie musiał WYŁĄCZAĆ bramki
# (usunięcie projektu z listy rozbraja ją dla wszystkich członków naraz).
test_control_plane_exception_passes if {
	ok := json.patch(control_plane_input(["prj-example-vertex-dev"]), [{
		"op": "add",
		"path": "/members/example-prj-example-vertex-dev/control_plane_exception",
		"value": {"justification": "stan Terraform przeniesiony do bucketa poza perimetrem, apply czyta go spoza granicy"},
	}])
	count(deny) == 0 with input as ok
}

# Uzasadnienie „ok" zamienia furtkę w skrót klawiszowy przed nieodwracalną awarią.
test_control_plane_exception_too_short_denied if {
	bad := json.patch(control_plane_input(["prj-example-vertex-dev"]), [{
		"op": "add",
		"path": "/members/example-prj-example-vertex-dev/control_plane_exception",
		"value": {"justification": "ok"},
	}])
	count(deny) > 0 with input as bad
}

# Wyjątek „na zapas" na projekcie spoza listy: gdyby był dozwolony, dopisanie go do wszystkich plików
# członków rozbroiłoby bramkę zawczasu, a późniejsze rozszerzenie listy nic by nie dało.
test_control_plane_exception_without_listing_denied if {
	bad := json.patch(control_plane_input([]), [{
		"op": "add",
		"path": "/members/example-prj-example-vertex-dev/control_plane_exception",
		"value": {"justification": "wyjatek wpisany zawczasu, zanim projekt trafil na liste sterowania"},
	}])
	count(deny) > 0 with input as bad
}

# Numer bez cudzysłowów to w YAML-u liczba, a project_number jest stringiem — bramka wyglądałaby na
# uzbrojoną i nie łapała niczego. Ten test pilnuje, żeby cichy no-op był głośnym błędem.
test_control_plane_number_not_string_denied if {
	count(deny) > 0 with input as control_plane_input([111111111111])
}

# --- kanały wejścia ---------------------------------------------------------------------------------

# Repo zespołu zgłaszające SWÓJ projekt — przechodzi.
test_external_channel_allowed_project_passes if {
	ok := json.patch(healthy_input, [{
		"op": "replace",
		"path": "/members/example-prj-example-vertex-dev/change_ref",
		"value": "pr:ORG/example-platform#42",
	}])
	count(deny) == 0 with input as ok
}

# To samo repo zgłaszające CUDZY projekt — musi paść. Bez tej reguły wniosek wyglądałby tak samo legalnie
# jak każdy inny, a projekt trafiłby do perimetru na wniosek zespołu, który nim nie zarządza.
test_external_channel_foreign_project_denied if {
	bad := json.patch(healthy_input, [
		{"op": "replace", "path": "/members/example-prj-example-vertex-dev/change_ref", "value": "pr:ORG/example-platform#42"},
		{"op": "replace", "path": "/members/example-prj-example-vertex-dev/project_id", "value": "prj-inna-dywizja-prod"},
	])
	count(deny) > 0 with input as bad
}

# Repo przypisane do dywizji `risk` deklarujące wpis dywizji `market` — musi paść: właścicielem wpisu
# (i adresatem raportu naruszeń) zostałby ktoś, kto o niczym nie wie.
test_external_channel_division_mismatch_denied if {
	bad := json.patch(healthy_input, [
		{"op": "replace", "path": "/members/example-prj-example-vertex-dev/change_ref", "value": "pr:ORG/example-platform#42"},
		{"op": "replace", "path": "/members/example-prj-example-vertex-dev/division", "value": "other-division"},
	])
	count(deny) > 0 with input as bad
}

# Zgłoszenie z repozytorium, którego w ogóle nie ma w contributors.yaml — musi paść (brak mapowania
# to brak uprawnienia, nie „domyślnie wolno").
test_external_channel_unknown_repo_denied if {
	bad := json.patch(healthy_input, [{
		"op": "replace",
		"path": "/members/example-prj-example-vertex-dev/change_ref",
		"value": "pr:ORG/nieznane-repo#7",
	}])
	count(deny) > 0 with input as bad
}

# --- reguły baseline --------------------------------------------------------------------------------

baseline_ok := [{
	"title": "security-scanner-read",
	"identities": ["serviceAccount:scanner@vendor.iam.gserviceaccount.com"],
	"access_levels": [],
	"allow_without_access_level": true,
	"operations": [{"service": "storage.googleapis.com", "methods": ["google.storage.buckets.get"]}],
}]

test_baseline_with_explicit_flag_passes if {
	ok := json.patch(healthy_input, [{"op": "add", "path": "/policy/baseline_ingress", "value": baseline_ok}])
	count(deny) == 0 with input as ok
}

# Pominięcie pola NIE MOŻE dawać tego samego skutku co jego ustawienie — inaczej reguła bez warunku kontekstu
# dla wszystkich członków przechodzi w cichym PR-ze.
test_baseline_without_access_level_and_without_flag_denied if {
	rule := json.remove(baseline_ok[0], ["allow_without_access_level"])
	bad := json.patch(healthy_input, [{"op": "add", "path": "/policy/baseline_ingress", "value": [rule]}])
	count(deny) > 0 with input as bad
}

# Baseline mnoży się przez liczbę członków, więc `*` kosztuje tu najwięcej i daje skanerowi prawo do
# wszystkiego w KAŻDYM chronionym projekcie.
test_baseline_wildcard_method_denied if {
	rule := json.patch(baseline_ok[0], [{"op": "replace", "path": "/operations/0/methods", "value": ["*"]}])
	bad := json.patch(healthy_input, [{"op": "add", "path": "/policy/baseline_ingress", "value": [rule]}])
	count(deny) > 0 with input as bad
}

# --- egress do zasobów poza Google Cloud ------------------------------------------------------------

omni_profile := {"bq-omni-external-read": {
	"name": "bq-omni-external-read",
	"parameters": [{"name": "query_identities", "description": "x"}, {"name": "external_resources", "description": "y"}],
	"egress": [{
		"title": "read-external-omni-tables",
		"identities_from": "query_identities",
		"to_external_from": "external_resources",
		# Jedyny ksztalt, ktory zywe API przyjmuje przy `external_resources` — zmierzone 2026-08-11.
		# Poprzednio stalo tu `methods: [...]`, czyli regula, ktorej nie da sie zaplikowac.
		"operations": [{"service": "bigquery.googleapis.com", "permissions": ["externalResource.read"]}],
	}],
}}

omni_input(resources) := object.union(healthy_input, {
	"profiles": object.union(base_profiles, omni_profile),
	"members": {"example-prj-example-vertex-dev": object.union(healthy_member, {"profiles": [{
		"name": "bq-omni-external-read",
		"params": {"query_identities": ["serviceAccount:a@b.iam.gserviceaccount.com"], "external_resources": resources},
	}]})},
})

test_external_resource_s3_passes if {
	count(deny) == 0 with input as omni_input(["s3://approved-bucket"])
}

test_external_resource_azure_passes if {
	count(deny) == 0 with input as omni_input(["azure://acct.blob.core.windows.net/container"])
}

# To jest ta pomyłka, dla której ta bramka istnieje: ARN wygląda poprawnie dla człowieka z AWS, a API go nie zna.
test_external_resource_arn_denied if {
	count(deny) > 0 with input as omni_input(["arn:aws:s3:::approved-bucket"])
}

test_external_resource_bare_bucket_denied if {
	count(deny) > 0 with input as omni_input(["approved-bucket"])
}

# Zasoby zewnętrzne + usługa inna niż BigQuery = reguła, która wygląda na działającą i nie działa.
test_external_resources_non_bigquery_denied if {
	bad_profile := {"bq-omni-external-read": object.union(omni_profile["bq-omni-external-read"], {"egress": [{
		"title": "read-external-omni-tables",
		"identities_from": "query_identities",
		"to_external_from": "external_resources",
		"operations": [{"service": "aiplatform.googleapis.com", "permissions": ["externalResource.read"]}],
	}]})}
	bad := object.union(omni_input(["s3://approved-bucket"]), {"profiles": object.union(base_profiles, bad_profile)})
	count(deny) > 0 with input as bad
}



# ZMIERZONE 2026-08-11: `methods` przy `external_resources` konczy sie
# `Error 400: With 'external_resources' set, MethodSelector is only allowed to have permission`.
# Profil w katalogu mial dokladnie ten ksztalt od dnia powstania i nie dal sie zaplikowac ani razu.
test_external_resource_z_methods_denied if {
	zly := {"bq-omni-external-read": object.union(omni_profile["bq-omni-external-read"], {"egress": [{
		"title": "read-external-omni-tables",
		"identities_from": "query_identities",
		"to_external_from": "external_resources",
		"operations": [{"service": "bigquery.googleapis.com", "methods": ["JobService.Query"]}],
	}]})}
	bad := object.union(omni_input(["s3://approved-bucket"]), {"profiles": object.union(base_profiles, zly)})
	count(deny) > 0 with input as bad
}

# ZMIERZONE: odrzucone zostaly `bigquery.jobs.create`, `bigquery.tables.getData`, `bigquery.tables.get`
# i `*` — mimo ze trzy pierwsze SA na liscie `supported-services`. Przyjete zostalo wylacznie
# `externalResource.read`, ktorego na tej liscie NIE MA.
test_external_resource_zle_uprawnienie_denied if {
	every zle in ["bigquery.jobs.create", "bigquery.tables.getData", "*"] {
		zly := {"bq-omni-external-read": object.union(omni_profile["bq-omni-external-read"], {"egress": [{
			"title": "read-external-omni-tables",
			"identities_from": "query_identities",
			"to_external_from": "external_resources",
			"operations": [{"service": "bigquery.googleapis.com", "permissions": [zle]}],
		}]})}
		bad := object.union(omni_input(["s3://approved-bucket"]), {"profiles": object.union(base_profiles, zly)})
		count(deny) > 0 with input as bad
	}
}

# CICHY NO-OP, ZMIERZONY: pole przechodzilo schemat i bramki, budzet je liczyl, a renderer je gubil.
test_egress_access_levels_from_denied if {
	zly := {"bq-omni-external-read": object.union(omni_profile["bq-omni-external-read"], {"egress": [{
		"title": "read-external-omni-tables",
		"identities_from": "query_identities",
		"access_levels_from": "access_levels",
		"to_external_from": "external_resources",
		"operations": [{"service": "bigquery.googleapis.com", "permissions": ["externalResource.read"]}],
	}]})}
	bad := object.union(omni_input(["s3://approved-bucket"]), {"profiles": object.union(base_profiles, zly)})
	count(deny) > 0 with input as bad
}

# Reguła „jeden projekt = jeden wpis" ma testy wyżej, w sekcji o duplikatach w jednym pliku — razem
# z przypadkami, które przy pliku na projekt nie mogły powstać (ten sam klucz, mapa gubiąca wpis).
