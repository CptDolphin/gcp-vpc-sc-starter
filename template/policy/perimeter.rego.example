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

# `method_selectors` ma DWA pola i tylko jedno z nich bylo pilnowane. Selektor `permission` jest druga,
# rownolegla droga wyrazenia zakresu operacji — regula zapisana permisjami omijala wiec bramke wyzej
# w calosci. WYJATEK dla uslug bez selektorow NIE dotyczy tej sciezki: tam `*` jest jedyna wartoscia,
# jaka API przyjmuje w polu `method`, a nie w polu `permission`.
#
# ZMIERZONE na zywym ACM (2026-08-11): `permission: "*"` na bigquery konczy sie
# `Error 400: PERMISSION '*' is not supported in bigquery.googleapis.com`, czyli API i tak tego nie
# przyjmuje. Bramka istnieje mimo to, bo „API i tak odrzuci" znaczy „odrzuci PO review, na obiekcie
# org-plane" — dokladnie ta zamiana, ktora ten katalog bramek ma cofac.
deny contains msg if {
	some r in planned
	some to_block in array.concat(
		object.get(r.values, "ingress_to", []),
		object.get(r.values, "egress_to", []),
	)
	some op in object.get(to_block, "operations", [])
	some sel in object.get(op, "method_selectors", [])
	sel.permission == "*"
	msg := sprintf("%s: permission=\"*\" na %s — wypisz uprawnienia jawnie (API i tak odrzuca ten zapis)", [r.address, op.service_name])
}

# --- zasięg -----------------------------------------------------------------------------------------

# `resources = ["*"]` po stronie ingress oznacza „dowolny zasób w tej konfiguracji perimetru".
#
# DLA REGUŁY DYWIZJI TO JEST ZAKAZANE i było zakazane bezwarunkowo: reguła napisana dla jednego zespołu
# działałaby wtedy na projektach wszystkich pozostałych — cicha eskalacja, bo w konsoli wygląda identycznie
# jak reguła wąska. DLA REGUŁY BASELINE to jest jej DOSŁOWNA intencja (skaner i raport naruszeń mają
# obejmować każdego członka z definicji), a wypisywanie tej samej listy ręcznie kosztowało replace obu reguł
# baseline przy każdym wniosku — patrz DEC-11 i komentarz w terraform/locals.tf.
#
# PO CZYM ROZRÓŻNIAMY — I DLACZEGO NIE PO NAZWIE. Poprzednia generacja tej bramki rozpoznawała baseline po
# PODCIĄGU `--baseline--` w tytule i była sprawdzalnie obchodzalna (tytuł reguły profilowej powstaje jako
# `<członek>--<tytuł z profilu>`, więc profil nazwany `-baseline--cokolwiek` wyłączał dywizji wymóg access
# levelu jej własnym plikiem). Sam DOKŁADNY tytuł też nie wystarcza: klucz członka bierze się z NAZWY PLIKU
# z TREŚCI wpisu w `perimeter/projects.yaml`, więc wpis o dywizji `baseline` plus profil o tytule z baseline dałby
# regułę o tytule `baseline--<tytuł>` — czyli tę samą furtkę, tylko dalej.
#
# Rozstrzyga więc ZGODNOŚĆ CO DO TREŚCI z deklaracją w `perimeter/policy.yaml` (plik pod CODEOWNERS
# security, wstrzykiwany przez `conftest --data perimeter/policy.yaml`): tytuł, zbiór tożsamości, zbiór
# usług i zbiór selektorów muszą się zgadzać w komplecie. Reguła, która to spełnia, NIE DAJE swojemu autorowi
# niczego ponad to, co daje prawdziwy baseline — bo jest prawdziwym baselinem. Reguła, która tego nie
# spełnia, gwiazdki nie dostaje, choćby nazywała się jak baseline.
#
# BRAK `--data` = pusty `data.baseline_ingress` = zero dozwolonych wyjątków = każda gwiazdka odrzucona.
# Fail-closed jest tu celowy, tak samo jak przy `uslugi_bez_selektorow_metod`.
deny contains msg if {
	some r in planned
	some to_block in object.get(r.values, "ingress_to", [])
	"*" in object.get(to_block, "resources", [])
	not gwiazdka_dozwolona(r)
	msg := sprintf(
		"%s: ingress_to.resources=[\"*\"] — celuj w konkretny projekt członka (gwiazdka wyłącznie dla reguł baseline zadeklarowanych w policy.yaml)",
		[r.address],
	)
}

# Gwiazdka jest dozwolona, gdy reguła JEST baselinem z `policy.yaml` ORAZ ma źródło.
#
# Warunek „ma źródło" nie jest ozdobą: reguła z `ingress_from` bez ani jednego `sources` nie autoryzuje
# NICZEGO (zmierzone na żywym ACM — `NO_MATCHING_ACCESS_LEVEL` mimo obecnej reguły, #1941), więc gwiazdka
# w takiej regule daje kształt „maksymalny zasięg, zerowa autoryzacja" — najgorszy możliwy do zostawienia
# w konfiguracji, bo wygląda na pokrycie, którego nie ma. Reguły baseline renderują `accessLevel: "*"`
# na podstawie jawnego `allow_without_access_level` (approval Security), więc warunek spełniają.
gwiazdka_dozwolona(r) if {
	regula_odpowiada_baseline(r)
	liczba_zrodel(r) > 0
}

# BLIZNIAK REGULY WYZEJ PO STRONIE EGRESS — i przez pol roku go NIE BYLO.
#
# ZMIERZONE (2026-08-11, mutacja planu + conftest): ta sama gwiazdka w `egress_to.resources` PRZECHODZILA,
# podczas gdy `ingress_to.resources` byla odrzucana. Asymetria jest tym gorsza, ze egressowa gwiazdka
# znaczy WIECEJ: ingress `"*"` to „dowolny projekt W perimetrze" (zbior zamkniety, ktory sami
# kontrolujemy), a egress `"*"` to „dowolny zasob POZA perimetrem" — czyli dokladne zniesienie granicy
# w kierunku, dla ktorego ta granica istnieje.
#
# Renderer takiego ksztaltu dzis nie produkuje (`resources` powstaje jako `projects/<numer>`), wiec bramka
# jest obrona przed zmiana renderera i przed regula pisana wprost w HCL — tak samo jak jej ingressowy
# blizniak, ktory z tego samego powodu byl uznany za wart utrzymania.
deny contains msg if {
	some r in planned
	some to_block in object.get(r.values, "egress_to", [])
	"*" in object.get(to_block, "resources", [])
	msg := sprintf("%s: egress_to.resources=[\"*\"] — to znosi granice w kierunku wyjscia; wypisz projekty docelowe", [r.address])
}

# `egress_to.roles` to TRZECIA droga wyrazenia zakresu (obok `method` i `permission`) i zadna z bramek
# na metody jej nie widzi: rola IAM opisuje zbior operacji, ktorego nie da sie porownac z lista metod.
# Renderer tego pola NIE USTAWIA nigdy — jego obecnosc w planie znaczy, ze regula nie powstala
# z deklaracji w `perimeter/`. Fail-closed: odrzucamy zamiast zgadywac, co ta rola obejmuje.
deny contains msg if {
	some r in planned
	some to_block in object.get(r.values, "egress_to", [])
	count(object.get(to_block, "roles", [])) > 0
	msg := sprintf(
		"%s: egress_to.roles jest ustawione — renderer tego pola nie produkuje, a bramki na metody go nie widza. Wyraz zakres metodami albo uprawnieniami",
		[r.address],
	)
}

# Ingress spoza perimetru bez access levelu opiera się wyłącznie na tożsamości: skradziony token działa
# wtedy z dowolnej sieci. Access level dokłada warunek kontekstu, którego token nie niesie.
#
# WYJĄTEK: reguły baseline (skanery, monitoring) wołają z własnej infrastruktury dostawcy i nie spełnią
# korporacyjnego access levelu. Muszą być oznaczone `allow_without_access_level: true` w policy.yaml —
# czyli świadomie, w pliku pod CODEOWNERS security, a nie przez pominięcie pola w cichym PR-ze.
#
# ROZPOZNAJEMY JE PO ZGODNOŚCI Z DEKLARACJĄ, NIE PO NAZWIE — patrz `regula_odpowiada_baseline` niżej.
# Historia tej bramki jest historią coraz słabszych nazw: najpierw podciąg `--baseline--` (obchodzony
# profilem o tytule `-baseline--…`), potem dokładny tytuł z `policy.yaml` (obchodzalny plikiem członka
# nazwanym `baseline.yaml`). Nazwa nie jest własnością bezpieczeństwa — treść jest.
deny contains msg if {
	some r in planned
	r.type in {
		"google_access_context_manager_service_perimeter_ingress_policy",
		"google_access_context_manager_service_perimeter_dry_run_ingress_policy",
	}
	some block in object.get(r.values, "ingress_from", [])
	count(object.get(block, "sources", [])) == 0
	not regula_odpowiada_baseline(r)
	msg := sprintf("%s: ingress bez access levelu — dodaj warunek kontekstu (sieć / urządzenie)", [r.address])
}

# --- czym JEST reguła baseline w planie ---------------------------------------------------------------
#
# Jedyne miejsce w tym pliku, które odpowiada na pytanie „czy ta reguła to baseline". Obie bramki
# przyznające baseline'owi wyjątek (gwiazdka w `resources`, brak access levelu) pytają WYŁĄCZNIE tutaj —
# inaczej rozjechałyby się przy pierwszej zmianie, a rozjazd bramek bezpieczeństwa jest niemy.
#
# Reguła odpowiada baseline'owi, gdy istnieje w `policy.yaml` deklaracja o TYM SAMYM tytule, TYCH SAMYCH
# tożsamościach, TYCH SAMYCH usługach i TYCH SAMYCH selektorach (metody i uprawnienia osobno — to dwa
# różne pola `methodSelectors`, a pilnowanie tylko jednego było już raz luką w tym pliku).
#
# `resources` ŚWIADOMIE NIE JEST porównywane: to jedyne pole, w którym reguła zbiorcza ma prawo różnić się
# od deklaracji (deklaracja nie zna członków, renderer wstawia `*`). Gdyby je tu porównywać, predykat
# odpowiadałby na pytanie „czy renderer zrobił to, co zrobił", a nie „czy ta treść jest zatwierdzona".
regula_odpowiada_baseline(r) if {
	some b in data.baseline_ingress
	object.get(r.values, "title", "") == sprintf("baseline--%s", [b.title])
	tozsamosci_z_planu(r) == {i | some i in b.identities}
	uslugi_z_planu(r) == {op.service | some op in b.operations}
	metody_z_planu(r) == metody_zadeklarowane(b)
	uprawnienia_z_planu(r) == uprawnienia_zadeklarowane(b)
}

tozsamosci_z_planu(r) := {i |
	some block in object.get(r.values, "ingress_from", [])
	some i in object.get(block, "identities", [])
}

liczba_zrodel(r) := count([s |
	some block in object.get(r.values, "ingress_from", [])
	some s in object.get(block, "sources", [])
])

uslugi_z_planu(r) := {op.service_name |
	some to_block in object.get(r.values, "ingress_to", [])
	some op in object.get(to_block, "operations", [])
}

# `method_selectors` w plan-JSON ma OBA pola, a nieużywane jest `null` — stąd jawne odfiltrowanie.
metody_z_planu(r) := {[op.service_name, sel.method] |
	some to_block in object.get(r.values, "ingress_to", [])
	some op in object.get(to_block, "operations", [])
	some sel in object.get(op, "method_selectors", [])
	sel.method != null
}

uprawnienia_z_planu(r) := {[op.service_name, sel.permission] |
	some to_block in object.get(r.values, "ingress_to", [])
	some op in object.get(to_block, "operations", [])
	some sel in object.get(op, "method_selectors", [])
	sel.permission != null
}

metody_zadeklarowane(b) := {[op.service, m] |
	some op in b.operations
	some m in object.get(op, "methods", [])
}

uprawnienia_zadeklarowane(b) := {[op.service, p] |
	some op in b.operations
	some p in object.get(op, "permissions", [])
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
