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

# --- PRZEJŚCIE kontra STAN (kontrakt = etapy zastosowane) -------------------------------------------
#
# Bramki wyżej mają sens WYŁĄCZNIE dla członka, dla którego egzekwowanie dopiero ma zostać włączone.
# Zadane po samym `stage: enforced` obowiązują też po zastosowaniu promocji — a wtedy naruszenia w oknie
# są ODMOWAMI (granica działa), a liczba dni w dry-run jest historią. Skutek: członek działający zgodnie
# z przeznaczeniem odrzuca każdy niezwiązany pull request.
#
# CZTERY OSIE, KTÓRE MUSZĄ BYĆ TESTOWANE RAZEM, bo każda z osobna daje się „zdać" złą regułą:
#   * przejście z dowodem przechodzi, przejście bez dowodu PADA (inaczej to jest wyłącznik bramki);
#   * członek JUŻ egzekwowany przechodzi mimo odmów (inaczej naprawa nie naprawia niczego);
#   * brak wiedzy o stanie zastosowanym zachowuje się jak przejście (inaczej wyłącznikiem bramki jest
#     usunięcie artefaktu);
#   * członka NIEOBECNEGO w kontrakcie też traktujemy jak przejście (pierwszy apply).

# `applied_stages_known` osobno od mapy — pusta mapa przy `known: true` znaczy „kontrakt jest i tego
# członka w nim nie ma", co jest czymś innym niż „nie wiemy nic".
ze_stanem(etapy, znany) := {"applied_stages": etapy, "applied_stages_known": znany}

# Członek promowany „na świeżo", z brudnym oknem: 30 wpisów w raporcie i 2 dni w dry-run zamiast 14.
# Ten sam wpis obsługuje oba reżimy — różni je WYŁĄCZNIE zawartość kontraktu.
swiezo_promowany := object.union(healthy_member, {"stage": "enforced", "dry_run_since": "2026-07-18"})

wejscie_z_kontraktem(etapy, znany) := object.union(
	object.union(healthy_input, {
		"members": {"example-prj-example-vertex-dev": swiezo_promowany},
		"violations_last_window": {"example-prj-example-vertex-dev": 30},
	}),
	ze_stanem(etapy, znany),
)

# 1. PRZEJŚCIE BEZ DOWODU DALEJ PADA. To jest cała treść bramki: kontrakt mówi `dry-run`, repo prosi
#    o `enforced`, w oknie 30 naruszeń i 2 dni obserwacji — decyzja jest przed nami i stoi.
test_przejscie_bez_dowodu_dalej_odrzucone if {
	count(deny) > 0 with input as wejscie_z_kontraktem({"example-prj-example-vertex-dev": "dry-run"}, true)
}

# 2. TEN SAM WPIS, GDY GRANICA JUŻ DZIAŁA, PRZECHODZI. 30 wpisów to teraz odmowy, a nie prognoza — i nie
#    mają prawa czerwienić pull requesta o czymkolwiek innym. Bez tego testu „naprawa" mogłaby polegać na
#    poluzowaniu progu i nikt by nie zauważył, że pyta nadal o stan.
test_juz_egzekwowany_z_odmowami_przechodzi if {
	count(deny) == 0 with input as wejscie_z_kontraktem({"example-prj-example-vertex-dev": "enforced"}, true)
}

# 3. FAIL-CLOSED: bez wiedzy o stanie zastosowanym zachowujemy się jak przy przejściu. Gdyby było
#    odwrotnie, wyłącznikiem tej bramki byłoby NIEPODANIE `--contract` — czyli brak pliku.
test_brak_wiedzy_o_stanie_zachowuje_sie_jak_przejscie if {
	count(deny) > 0 with input as wejscie_z_kontraktem({}, false)
}

# 3b. Ta sama domyślność, gdy pól nie ma w wejściu W OGÓLE (stare narzędzie, ręcznie sklecony JSON).
#     Odwołanie do brakującego klucza jest w rego NIEZDEFINIOWANE, a niezdefiniowany warunek unieważnia
#     całą regułę — czyli bez `default` brak pola PRZEPUSZCZAŁBY promocję. Ten test tego pilnuje.
test_brak_pol_stanu_zachowuje_sie_jak_przejscie if {
	bad := object.union(healthy_input, {
		"members": {"example-prj-example-vertex-dev": swiezo_promowany},
		"violations_last_window": {"example-prj-example-vertex-dev": 30},
	})
	count(deny) > 0 with input as bad
}

# 4. Kontrakt czytelny i kompletny, ale członka w nim nie ma — to pierwszy apply tego wpisu, czyli
#    przejście z niczego do `enforced`. Najostrzejszy z możliwych stanów, a wygląda jak „brak danych".
test_czlonek_nieobecny_w_kontrakcie_to_przejscie if {
	count(deny) > 0 with input as wejscie_z_kontraktem({"example-inny-projekt": "enforced"}, true)
}

# 5. ANTY-TAUTOLOGIA DLA `granica_juz_wlaczona`: wpis `enforced` w kontrakcie pod INNYM etapem nie może
#    zwalniać. Bez tego testu reguła „kontrakt zna tego członka" przechodziłaby jako „kontrakt mówi
#    enforced", a wtedy sama obecność w perimetrze (w dry-run!) zdejmowałaby bramkę promocji.
test_kontrakt_z_dry_run_nie_zwalnia if {
	count(deny) > 0 with input as wejscie_z_kontraktem({"example-prj-example-vertex-dev": "dry-run"}, true)
	count(deny) == 0 with input as wejscie_z_kontraktem({"example-prj-example-vertex-dev": "enforced"}, true)
}

# 6. Okno obserwacji to też warunek PRZEJŚCIA, nie własność członka. Bez tego pierwsza promocja przed
#    upływem okna (za zgodą, przez waiver) blokowałaby repo jeszcze przez resztę tego okna — po decyzji,
#    na którą nikt już nie ma wpływu. Wejście ma CZYSTE okno (0 naruszeń), żeby mierzyć samą regułę dni.
test_okno_dry_run_nie_obowiazuje_po_wlaczeniu if {
	czyste := object.union(
		object.union(healthy_input, {
			"members": {"example-prj-example-vertex-dev": swiezo_promowany},
			"violations_last_window": {"example-prj-example-vertex-dev": 0},
		}),
		ze_stanem({"example-prj-example-vertex-dev": "enforced"}, true),
	)
	count(deny) == 0 with input as czyste

	# Para anty-tautologiczna: ten sam wpis przy kontrakcie `dry-run` MUSI paść na oknie.
	przejscie := object.union(czyste, ze_stanem({"example-prj-example-vertex-dev": "dry-run"}, true))
	count(deny) > 0 with input as przejscie
}

# 7. Brak raportu naruszeń po włączeniu granicy nie może wywracać repozytorium. Raport bywa nieosiągalny
#    (artefakt wygasł, przebieg padł), a kanały wejścia nie pobierają go nigdy — więc reguła pytająca
#    o stan zamieniała ich zgłoszenia w czerwone przez CUDZY wpis.
test_brak_raportu_nie_blokuje_juz_wlaczonego if {
	bez_raportu := object.union(
		json.patch(healthy_input, [
			{"op": "replace", "path": "/members/example-prj-example-vertex-dev/stage", "value": "enforced"},
			{"op": "remove", "path": "/violations_last_window/example-prj-example-vertex-dev"},
		]),
		ze_stanem({"example-prj-example-vertex-dev": "enforced"}, true),
	)
	count(deny) == 0 with input as bez_raportu

	# Para anty-tautologiczna: przy kontrakcie `dry-run` brak raportu nadal zatrzymuje promocję.
	count(deny) > 0 with input as object.union(bez_raportu, ze_stanem({"example-prj-example-vertex-dev": "dry-run"}, true))
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

# Testu `exceptions:` tu nie ma, bo nie ma już pola (DEC-23). Sprawdzał on długość uzasadnienia reguły,
# której renderer nigdy nie tworzył — czyli był testem zielonym na bramce mierzącej opis niebytu.
# Wpis niosący dziś `exceptions:` odrzuca `additionalProperties: false` w `schemas/member.schema.json`,
# a selftest startera ma na to osobny przypadek negatywny (schema, nie rego).

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
	# `risk: high` NIE JEST tu ozdobą fixture'a — od DEC-23 jest wejściem bramki (profil z celem poza
	# Google Cloud wymaga zgody Security) i zarazem przedmiotem osobnej reguły, która nie pozwala tej
	# etykiecie zaniżyć kształtu. Fixture bez `risk` odpalałby tę drugą regułę i każdy test w tej sekcji
	# padałby z powodu, o który nie pyta.
	"risk": "high",
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

zgoda_na(resources) := {
	"member": "example-prj-example-vertex-dev",
	"profile": "bq-omni-external-read",
	"destinations": resources,
	"approved_by": "sec@example.com",
	"expires": "2027-01-01",
	"justification": "hurtownia dywizji stoi w S3, wyplywaja wylacznie wyniki zapytan",
}

# Wejście BEZ zgody Security — czyli dokładnie to, co repozytorium przyjmowało do DEC-23.
omni_input_bez_zgody(resources) := object.union(healthy_input, {
	"profiles": object.union(base_profiles, omni_profile),
	"members": {"example-prj-example-vertex-dev": object.union(healthy_member, {"profiles": [{
		"name": "bq-omni-external-read",
		"params": {"query_identities": ["serviceAccount:a@b.iam.gserviceaccount.com"], "external_resources": resources},
	}]})},
})

# Wejście ZE zgodą pokrywającą dokładnie te cele. Wszystkie testy tej sekcji, które badają coś innego niż
# samą zgodę, jadą na tym wariancie — inaczej każdy z nich przechodziłby na braku zgody i nie mówiłby nic
# o tym, co miał zbadać.
omni_input(resources) := object.union(
	omni_input_bez_zgody(resources),
	{"policy": object.union(base_policy, {"egress_approvals": [zgoda_na(resources)]})},
)

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

# --- access levels: OR, uzasadnienie i poziom bez warunku -------------------------------------------
#
# ZMIERZONE na zywym ACM (2026-08-11): API przyjmuje `combiningFunction: OR` na poziomie zlozonym
# i zwraca 200 z ta wartoscia w odpowiedzi. Po tamtej stronie nie ma zadnego ostrzezenia, na ktore
# mozna liczyc — wiec albo zlapie to bramka przed apply, albo nikt.
#
# Kazdy negatyw ma tu pare pozytywna. Regula odrzucajaca KAZDY poziom przeszlaby same negatywy,
# a rozniloby ja od poprawnej dopiero to, ze zdrowy poziom u niej NIE przechodzi.

poziomy(al) := object.union(healthy_input, {"access_levels": al})

kompozycja_and := {
	"name": "corp_network_and_region",
	"title": "Corporate network AND allowed region",
	"combining_function": "AND",
	"regions": ["PL", "DE"],
	"required_access_levels": ["corp_network"],
}

test_kompozycja_and_passes if {
	count(deny) == 0 with input as poziomy({"corp_network_and_region": kompozycja_and})
}

test_poziom_prosty_bez_combining_passes if {
	count(deny) == 0 with input as poziomy({"corp_network": {
		"name": "corp_network",
		"title": "Corporate network",
		"ip_subnetworks": ["198.51.100.0/24"],
	}})
}

# NEGATYW: samo przestawienie AND -> OR. To jest dokladnie ten diff, ktory w review wyglada kosmetycznie.
test_or_bez_uzasadnienia_denied if {
	zly := object.union(kompozycja_and, {"combining_function": "OR"})
	count(deny) > 0 with input as poziomy({"corp_network_and_region": zly})
}

# POZYTYW DO POWYZSZEGO: ten sam OR z napisanym powodem przechodzi. Bez tej pary „bramka odrzuca OR"
# znaczyloby tylko „bramka odrzuca wszystko, co ma OR" — czyli zakaz, a nie swiadoma decyzja.
test_or_z_uzasadnieniem_passes if {
	dobry := object.union(kompozycja_and, {
		"combining_function": "OR",
		"or_reason": "laptop na zarzadzanym sprzecie pracuje spoza korpo-sieci i ma miec dostep",
	})
	count(deny) == 0 with input as poziomy({"corp_network_and_region": dobry})
}

# NEGATYW: uzasadnienie za krotkie degeneruje furtke do „ok" i przestaje byc decyzja.
test_or_z_krotkim_uzasadnieniem_denied if {
	zly := object.union(kompozycja_and, {"combining_function": "OR", "or_reason": "bo tak"})
	count(deny) > 0 with input as poziomy({"corp_network_and_region": zly})
}

# NEGATYW: uzasadnienie, ktore przezylo powrot do AND. W pliku wyglada na aktualny opis polityki.
test_uzasadnienie_bez_or_denied if {
	zly := object.union(kompozycja_and, {"or_reason": "kiedys bylo OR, zostalo po rewercie i nikt nie usunal"})
	count(deny) > 0 with input as poziomy({"corp_network_and_region": zly})
}

# NEGATYW: OR na poziomie z jednym warunkiem nic nie robi — dopoki ktos nie dolozy drugiego warunku.
test_or_przy_jednym_warunku_denied if {
	zly := {
		"name": "eu_only",
		"title": "Requests from the EU only",
		"combining_function": "OR",
		"or_reason": "powod napisany, ale i tak nie ma czego laczyc alternatywa",
		"regions": ["DE", "FR", "NL"],
	}
	count(deny) > 0 with input as poziomy({"eu_only": zly})
}

# NEGATYW: poziom, ktory nie sprawdza NICZEGO. W regule ingress wyglada jak kazdy inny access level.
test_poziom_bez_warunku_denied if {
	zly := {"name": "pusty", "title": "Level with no condition at all"}
	count(deny) > 0 with input as poziomy({"pusty": zly})
}

# POZYTYW DO POWYZSZEGO — i osobno wazny: kompozycja BEZ wlasnego warunku jest LEGALNA. API ja tworzy
# (zmierzone raw REST 2026-08-11), a odrzucal ja wylacznie nasz renderer, ktory doklejal pusty warunek.
test_kompozycja_bez_wlasnego_warunku_passes if {
	dobry := {
		"name": "corp_network_and_device",
		"title": "Corporate network AND managed device",
		"required_access_levels": ["corp_network", "corp_managed_device"],
	}
	count(deny) == 0 with input as poziomy({"corp_network_and_device": dobry})
}

# --- zgoda Security na profil wypuszczający dane poza Google Cloud (DEC-23) --------------------------
#
# PARA ANTY-TAUTOLOGICZNA JEST TU WARUNKIEM SENSU, a nie dobrym zwyczajem. Bramka odrzucająca każdy
# wniosek z profilem `risk: high` byłaby zakazem tego profilu (i przeszłaby wszystkie negatywy niżej);
# bramka odrzucająca każdy wniosek w ogóle przeszłaby je tym bardziej. Dlatego każdemu „czerwono"
# odpowiada tu „zielono" różniące się DOKŁADNIE jednym elementem wejścia.

# NEGATYW — to jest stan, w którym repozytorium było do 2026-08-12: profil wypuszczający dane poza Google
# Cloud, cel podany, zero śladu Security. Przechodziło.
test_high_risk_bez_zgody_denied if {
	count(deny) > 0 with input as omni_input_bez_zgody(["s3://approved-bucket"])
}

# POZYTYW — ten sam wpis, jedna zmiana: zgoda w policy.yaml. Bez tego testu poprzedni dowodziłby tylko,
# że coś jest czerwone.
test_high_risk_ze_zgoda_passes if {
	count(deny) == 0 with input as omni_input(["s3://approved-bucket"])
}

# POZYTYW SZEROKI — rutyna nie może płacić za tę bramkę. Wniosek bez egressu (`vertex-online-serving`,
# `risk` nieustawione w fixture, czyli na pewno nie `high`) przechodzi bez ani jednej zgody. To jest ten
# test, który odróżnia „bramka na wąską klasę" od „Security recenzuje 50 wniosków miesięcznie".
test_onboarding_bez_egressu_nie_wymaga_zgody if {
	count(deny) == 0 with input as healthy_input
}

# NEGATYW — zgoda jest, ale na inny cel. Bez tej reguły podmiana bucketa byłaby rutynowym diffem w pliku
# członka, przechodzącym pod zgodą wydaną na coś zupełnie innego: zgoda opisywałaby zdolność wysyłania,
# a nie kierunek wypływu, który jest całym przedmiotem decyzji.
test_zgoda_na_inny_cel_denied if {
	zle := object.union(
		omni_input_bez_zgody(["s3://approved-bucket"]),
		{"policy": object.union(base_policy, {"egress_approvals": [zgoda_na(["s3://zupelnie-inny-bucket"])]})},
	)
	count(deny) > 0 with input as zle
}

# NEGATYW — zgoda wygasła. `expires` jest obowiązkowe właśnie po to, żeby ten przypadek istniał: zgoda
# bezterminowa na wyprowadzanie danych poza Google Cloud to obniżenie baseline pod inną nazwą.
test_zgoda_wygasla_denied if {
	wygasla := object.union(zgoda_na(["s3://approved-bucket"]), {"expires": "2026-07-19"})
	zle := object.union(
		omni_input_bez_zgody(["s3://approved-bucket"]),
		{"policy": object.union(base_policy, {"egress_approvals": [wygasla]})},
	)
	count(deny) > 0 with input as zle
}

# NEGATYW — zgoda bez uzasadnienia. Próg 40 znaków ten sam co przy `promotion_waivers`: bez niego pole
# degeneruje się do „ok" i jedyna bramka przed nieodwracalnym wypływem przechodzi na skrót klawiszowy.
test_zgoda_bez_uzasadnienia_denied if {
	pusta := object.union(zgoda_na(["s3://approved-bucket"]), {"justification": "bo tak"})
	zle := object.union(
		omni_input_bez_zgody(["s3://approved-bucket"]),
		{"policy": object.union(base_policy, {"egress_approvals": [pusta]})},
	)
	count(deny) > 0 with input as zle
}

# NEGATYW — zgoda na członka, którego nie ma. Zwykle literówka w kluczu; cichy no-op wyglądałby jak
# działająca zgoda do dnia, w którym ktoś zdziwi się, czemu wniosek stoi.
test_zgoda_na_nieistniejacego_czlonka_denied if {
	widmo := object.union(zgoda_na(["s3://approved-bucket"]), {"member": "nie-ma-takiego"})
	zle := object.union(
		omni_input(["s3://approved-bucket"]),
		{"policy": object.union(base_policy, {"egress_approvals": [zgoda_na(["s3://approved-bucket"]), widmo]})},
	)
	count(deny) > 0 with input as zle
}

# NEGATYW — zgoda „na zapas": członek istnieje, ale dziś nie renderuje żadnego celu dla tego profilu.
# Gdyby wolno ją było trzymać, ktoś mógłby wydać zgody dla wszystkich członków z góry, a późniejsze
# dopisanie bucketa przeszłoby bez ani jednej bramki. Ta sama pułapka co `control_plane_exception`
# trzymany na projekcie spoza listy.
test_zgoda_na_zapas_denied if {
	zle := object.union(healthy_input, {"policy": object.union(base_policy, {"egress_approvals": [zgoda_na(["s3://approved-bucket"])]})})
	count(deny) > 0 with input as zle
}

# NEGATYW — pusty cel NIE wymaga zgody, a zgoda wydana na taki wpis jest wpisem-widmem. To jest para do
# testu wyżej i zarazem asercja o bezpiecznej degradacji: profil bez wartości parametru nie renderuje
# reguły, więc nie ma czego zatwierdzać.
test_high_risk_bez_celu_nie_wymaga_zgody if {
	count(deny) == 0 with input as omni_input_bez_zgody([])
}

# --- `risk` musi opisywać KSZTAŁT profilu ------------------------------------------------------------
#
# Bez tych dwóch reguł obejściem całej sekcji wyżej byłaby jedna linia w profilu.

# NEGATYW — profil wypuszcza dane poza Google Cloud i nazywa się `low`. Zgoda Security przestałaby być
# wymagana, a reguła nadal wypuszczałaby dane. To jest najtańsze możliwe obejście i dlatego ma własny test.
test_external_egress_z_risk_low_denied if {
	zly := {"bq-omni-external-read": object.union(omni_profile["bq-omni-external-read"], {"risk": "low"})}
	zle := object.union(omni_input(["s3://approved-bucket"]), {"profiles": object.union(base_profiles, zly)})
	count(deny) > 0 with input as zle
}

# NEGATYW — ten sam profil nazwany `medium`. Osobno od testu wyżej, bo `medium` jest etykietą LEGALNĄ dla
# egressu wewnątrz Google Cloud: reguła musi rozróżniać kształt, a nie tylko odrzucać `low`.
test_external_egress_z_risk_medium_denied if {
	zly := {"bq-omni-external-read": object.union(omni_profile["bq-omni-external-read"], {"risk": "medium"})}
	zle := object.union(omni_input(["s3://approved-bucket"]), {"profiles": object.union(base_profiles, zly)})
	count(deny) > 0 with input as zle
}

# POZYTYW — egress W GRANICACH Google Cloud (`to_projects_from`) z etykietą `medium` przechodzi i NIE
# wymaga zgody Security. To jest granica wąskiej klasy: gdyby ta bramka obejmowała każdy egress, objęłaby
# profil treningowy, czyli rutynę, i zostałaby wyłączona przy pierwszym pośpiechu.
test_egress_wewnatrz_gcp_medium_passes if {
	batch := {"vertex-batch-training": {
		"name": "vertex-batch-training",
		"risk": "medium",
		"parameters": [{"name": "training_identities", "description": "x"}, {"name": "data_source_projects", "description": "y"}],
		"egress": [{
			"title": "read-approved-dataset",
			"identities_from": "training_identities",
			"to_projects_from": "data_source_projects",
			"operations": [{"service": "storage.googleapis.com", "methods": ["google.storage.objects.get"]}],
		}],
	}}
	dobre := object.union(healthy_input, {
		"profiles": object.union(base_profiles, batch),
		"members": {"example-prj-example-vertex-dev": object.union(healthy_member, {"profiles": [{
			"name": "vertex-batch-training",
			"params": {"training_identities": ["serviceAccount:a@b.iam.gserviceaccount.com"], "data_source_projects": ["222222222222"]},
		}]})},
	})
	count(deny) == 0 with input as dobre
}

# NEGATYW — ten sam profil treningowy nazwany `low`. Etykieta ma nie móc kłamać także tam, gdzie nie
# uruchamia zgody Security: `risk` jedzie do kontraktu, który dywizje czytają, wybierając profil.
test_egress_wewnatrz_gcp_z_risk_low_denied if {
	batch := {"vertex-batch-training": {
		"name": "vertex-batch-training",
		"risk": "low",
		"parameters": [{"name": "training_identities", "description": "x"}, {"name": "data_source_projects", "description": "y"}],
		"egress": [{
			"title": "read-approved-dataset",
			"identities_from": "training_identities",
			"to_projects_from": "data_source_projects",
			"operations": [{"service": "storage.googleapis.com", "methods": ["google.storage.objects.get"]}],
		}],
	}}
	zle := object.union(healthy_input, {
		"profiles": object.union(base_profiles, batch),
		"members": {"example-prj-example-vertex-dev": object.union(healthy_member, {"profiles": [{
			"name": "vertex-batch-training",
			"params": {"training_identities": ["serviceAccount:a@b.iam.gserviceaccount.com"], "data_source_projects": ["222222222222"]},
		}]})},
	})
	count(deny) > 0 with input as zle
}

# NEGATYW — PROFIL ZMIENIA `risk` PÓŹNIEJ, BEZ ANI JEDNEGO PULL REQUESTA U CZŁONKA. To jest edge case,
# dla którego reguła siedzi na DEKLARACJACH, a nie jednorazowo przy onboardingu: profil dostaje regułę
# egress poza Google Cloud w osobnym PR-ze, a członkowie, którzy go już mają, w tej samej sekundzie
# stają się wnioskami wysokiego ryzyka. Wejście różni się od `healthy_input` wyłącznie treścią KATALOGU.
test_profil_dostaje_egress_pozniej_denied if {
	byl_bez_egressu := {"vertex-online-serving": object.union(base_profiles["vertex-online-serving"], {
		"risk": "high",
		"egress": [{
			"title": "swiezy-egress",
			"identities_from": "caller_identities",
			"to_external_from": "caller_identities",
			"operations": [{"service": "bigquery.googleapis.com", "permissions": ["externalResource.read"]}],
		}],
	})}
	zle := object.union(healthy_input, {"profiles": byl_bez_egressu})
	count(deny) > 0 with input as zle
}
