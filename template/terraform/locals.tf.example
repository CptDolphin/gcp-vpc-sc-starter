# Wczytanie deklaracji z YAML i wyrenderowanie ich na reguły VPC-SC.
#
# TU JEST CAŁA LOGIKA STARTERA: pliki w perimeter/ są źródłem prawdy, a Terraform jest tylko rendererem.
# Dzięki temu wniosek dywizji to jeden czytelny plik YAML, a nie HCL, którego nikt poza platformą nie napisze.

locals {
  perimeter_dir = "${path.module}/../perimeter"

  policy    = yamldecode(file("${local.perimeter_dir}/policy.yaml"))
  policy_id = local.policy.organization.access_policy_name

  perimeter_full_name = "accessPolicies/${local.policy_id}/servicePerimeters/${local.policy.perimeter.name}"

  # Brownfield: gdy perimetr już istnieje i nie został przejęty importem, szkieletem zarządza ktoś inny.
  # Domyślnie false — dokładamy tylko członków i reguły (patrz perimeter.manage_skeleton w policy.yaml).
  manage_skeleton = lookup(local.policy.perimeter, "manage_skeleton", false)

  # CZŁONKOWIE SIEDZĄ W JEDNYM PLIKU `perimeter/projects.yaml`, JAKO **LISTA** WPISÓW (DEC-12).
  #
  # Było: `fileset(".../members", "*.yaml")` i klucz z nazwy pliku. Zmieniło się źródło, NIE klucz — i to
  # jest cała ostrożność tej zmiany. Klucz `<dywizja>-<project_id>` odtwarza DOKŁADNIE dawny `trimsuffix`
  # nazwy pliku (bot zapisywał `perimeter/members/<dywizja>-<projekt>.yaml`), więc adresy w stanie zostają
  # te same i `plan` po migracji nie ma czego zniszczyć. Gdyby klucz się zmienił, każda granularna reguła
  # ACM dostałaby `destroy` + `create` — na konfiguracji egzekwowanej to okno bez autoryzacji na żywej
  # granicy, a `create_before_destroy` nie jest wyjściem (DEC-11: wszystkie te zasoby mają w stanie ten sam
  # `id`, bo provider realizuje je jako read-modify-write na jednej liście).
  #
  # DLACZEGO LISTA, A NIE MAPA `project_id → wpis` — ZMIERZONE, nie wybrane z gustu. W mapie duplikat
  # klucza jest CICHY: `yamldecode` bierze ostatni wpis i nie mówi nic (sprawdzone na Terraformie 1.15.5;
  # `yaml.safe_load` w Pythonie zachowuje się identycznie). Przy pliku wspólnym duplikat nie jest egzotyką,
  # tylko normalnym wynikiem scalenia dwóch wniosków — a „cicho wygrywa ostatni" znaczy tu „promocja do
  # `enforced` została po cichu cofnięta do `dry-run`". Przy liście ten sam przypadek jest TWARDYM BŁĘDEM
  # planu, zanim powstanie jakikolwiek zasób:
  #
  #     Error: Duplicate object key
  #     Two different items produced the key "div-aaa" in this 'for' expression.
  #
  # Czyli renderer — warstwa, której nie da się pominąć ani zapomnieć uruchomić — jest ostatnią bramką
  # duplikatu. Pozostałe trzy (strict loader w `tools/projects_file.py`, reguły `vpcsc.onboarding`
  # na `members_list`, porównanie liczności mapy i listy) łapią to WCZEŚNIEJ i z lepszym komunikatem,
  # ale żadna z nich nie jest jedyna.
  #
  # `try(…, [])` NIE MA TU CELOWO. Plik bez klucza `members` albo z `members` innego kształtu ma wywrócić
  # plan, a nie wyrenderować perimetr bez ani jednego członka — to drugie jest planem, który usuwa z
  # granicy wszystkich naraz i wygląda przy tym na poprawny.
  projects_file = yamldecode(file("${local.perimeter_dir}/projects.yaml"))

  members = {
    for m in local.projects_file.members : "${m.division}-${m.project_id}" => m
  }

  profiles = {
    for f in fileset("${local.perimeter_dir}/profiles", "*.yaml") :
    trimsuffix(f, ".yaml") => yamldecode(file("${local.perimeter_dir}/profiles/${f}"))
  }

  # Mapowanie repo→dozwolone projekty (kanał `pr:`, DEC-7). Terraform czyta je WYŁĄCZNIE po to, by
  # opublikować je w kontrakcie — decyzję o dopuszczeniu zgłoszenia podejmuje reguła OPA na tym samym pliku.
  # Brak pliku = kanał zewnętrzny nieaktywny (bezpieczna degradacja: OPA odrzuci każde zgłoszenie `pr:`).
  contributors = fileexists("${local.perimeter_dir}/contributors.yaml") ? yamldecode(file("${local.perimeter_dir}/contributors.yaml")).contributors : []

  access_levels = merge([
    for f in fileset("${local.perimeter_dir}/access-levels", "*.yaml") : {
      for al in yamldecode(file("${local.perimeter_dir}/access-levels/${f}")).access_levels :
      al.name => al
    }
  ]...)

  # --- UZBROJENIE POZIOMÓW: zakresy, których nikt nie ma, wyglądają jak zakresy, które ktoś ma ------
  #
  # Zakresy DOKUMENTACYJNE nie należą do żadnego hosta na świecie, więc poziom oparty wyłącznie na nich
  # nie autoryzuje NIKOGO — a w `describe`, w konsoli i w planie wygląda dokładnie jak poziom gotowy.
  # To jest ta sama klasa defektu co reguła baseline bez `sources`: kontrola obecna i bezczynna. Różnica
  # jest taka, że tamtą dało się złapać KSZTAŁTEM reguły, a tę widać wyłącznie w TREŚCI danych.
  #
  # DOPASOWANIE PO PREFIKSIE, nie po zawieraniu się w CIDR — świadomie. HCL nie ma funkcji „czy adres
  # leży w sieci", a każdy podzakres bloku /24 z RFC 5737 zaczyna się od tych samych trzech oktetów
  # (`192.0.2.10/32` -> `192.0.2.`), więc prefiks łapie dokładnie to, co ma złapać, i da się go
  # przeczytać bez uruchamiania Terraforma. Krótszy prefiks (`192.0.0.0/16`) nie jest zakresem
  # dokumentacyjnym i celowo tu nie pasuje.
  #
  # CZEGO TU NIE MA: RFC 1918 (10/8, 172.16/12, 192.168/16). Dla ruchu z sieci korporacyjnej przez
  # interconnect adres prywatny bywa POPRAWNĄ wartością — wrzucenie go do tego samego worka zamieniłoby
  # bramkę wykrywającą placeholder w bramkę zakazującą realnego wzorca.
  documentation_prefixes = ["192.0.2.", "198.51.100.", "203.0.113.", "2001:db8:"]

  # Poziomy, które REALNIE stoją w konfiguracji EGZEKWOWANEJ — czyli tam, gdzie „nie wpuszcza nikogo"
  # przestaje być notatką w pliku i zaczyna być polityką. `*` (baseline: autoryzacja samą tożsamością)
  # nie jest nazwą poziomu i wypada z tej listy.
  access_levels_referenced_by_enforced = distinct([
    for a in flatten([for k, r in local.ingress_rules_enforced : lookup(r, "access_levels", [])]) : a
    if a != "*"
  ])

  # Domyślny okres ważności atestacji zakresu (`reviewed`). 180 dni to kompromis: krócej = zegar dzwoni
  # częściej, niż zmienia się topologia sieci, i zostaje wyciszony; dłużej = zakres zdąży się zmienić
  # dwa razy między potwierdzeniami. Poziom może nadpisać to `review_interval_days`.
  access_level_review_default_days = 180

  restricted_services = local.policy.restricted_services
  accessible_services = local.policy.vpc_accessible_services.same_as_restricted ? local.policy.restricted_services : []

  # NIEZMIENNIK BASELINE'U CZYTANY Z DEKLARACJI, NIE ZASZYTY W KODZIE (DEC-50).
  #
  # Wartość domyślna odtwarza zachowanie sprzed tej decyzji. Jest tu, a nie w `perimeter.tf`, bo czytają
  # ją DWA miejsca (precondition szkieletu i test renderera) — literał w każdym z nich rozjechałby się przy
  # pierwszej zmianie i wtedy jedna warstwa broniłaby czegoś innego niż druga, obie na zielono.
  #
  # `lookup` na CAŁYM dokumencie polityki, nie `try(local.policy.baseline_required_services, …)`: `try`
  # połknąłby także błąd typu (klucz obecny, ale np. string zamiast listy), a taki plik ma wywrócić plan,
  # a nie po cichu wrócić do domyślnej listy — czyli udawać, że deklaracja jest respektowana.
  baseline_required_services = lookup(local.policy, "baseline_required_services", ["aiplatform.googleapis.com"])

  # Usługi zadeklarowane jako niezmiennik, których w `restricted_services` NIE MA. Niepusty zbiór = błąd;
  # trzymamy go w locals, żeby komunikat bramki mógł je WYMIENIĆ zamiast mówić „coś się nie zgadza".
  baseline_services_missing = setsubtract(local.baseline_required_services, local.restricted_services)

  # Członkowie egzekwowani = ci ze `stage: enforced`. Reszta istnieje wyłącznie w konfiguracji dry-run.
  enforced_members = { for k, m in local.members : k => m if m.stage == "enforced" }

  # --- render reguł ---------------------------------------------------------------------------------
  # Dla każdej pary (członek × profil) i każdej reguły w profilu powstaje jeden obiekt. `identities_from`
  # i `access_levels_from` to nazwy parametrów — wartości przychodzą z pliku członka, więc profil pozostaje
  # bezosobowy, a członek nie zna składni VPC-SC.

  ingress_rules_profiles = {
    for r in flatten([
      for mkey, m in local.members : [
        for p in m.profiles : [
          for rule in lookup(local.profiles[p.name], "ingress", []) : {
            key    = "${mkey}--${p.name}--${rule.title}"
            member = mkey
            stage  = m.stage
            # `scope` mówi, SKĄD reguła pochodzi, i jest jedynym rozróżnieniem, po którym wolno filtrować:
            # profilowa ma właściciela (`member`), baseline'owa nie ma go od kolapsu (patrz niżej). Kod, który
            # zakłada `local.members[r.member]` dla każdej reguły, wywraca się na regule zbiorczej — a robi to
            # w teście albo w bramce, czyli tam, gdzie awaria wygląda na naruszenie niezmiennika.
            scope         = "profile"
            title         = "${mkey}--${rule.title}"
            identities    = lookup(p.params, rule.identities_from, [])
            access_levels = [for a in lookup(p.params, lookup(rule, "access_levels_from", "__none__"), []) : "accessPolicies/${local.policy_id}/accessLevels/${a}"]
            resources     = ["projects/${m.project_number}"]
            operations    = rule.operations
          }
        ]
      ]
    ]) : r.key => r
  }

  # Alias zachowany dla czytelności testów i outputów: reguły pochodzące z profili członków.
  ingress_rules_all = local.ingress_rules_profiles

  # Reguły baseline — stosowane do KAŻDEGO członka, niezależnie od jego profili (policy.yaml
  # §baseline_ingress). Skanery, monitoring i backup potrzebują dostępu do wszystkich projektów; jako profil
  # per-member pierwszy zespół, który zapomni go wybrać, wypadłby ze skanowania w momencie promocji.
  baseline_ingress = lookup(local.policy, "baseline_ingress", [])

  # `sources` REGULY INGRESS NIE JEST OPCJONALNE — regula bez zrodla nie autoryzuje niczego.
  #
  # ZMIERZONE na zywym ACM: regula baseline z `access_levels: []` i `allow_without_access_level: true`
  # stala w konfiguracji od osmiu minut, a wywolanie dokladnie tej tozsamosci na dokladnie tej metodzie
  # i tak wygenerowalo naruszenie z `violationReason: NO_MATCHING_ACCESS_LEVEL`. Renderer produkowal
  # `ingress_from` z sama lista `identities` i ZERO blokow `sources` (patrz `dynamic "sources"` w rules.tf),
  # bo lista access levels byla pusta. API nie zna ksztaltu „autoryzuj po samej tozsamosci" — brak zrodla
  # czyta jako brak dopasowania, wiec regula wyglada w konsoli na obecna i nie przepuszcza nic.
  #
  # To jest najgorszy wariant bledu w tym repo: reguly baseline istnieja WLASNIE po to, zeby przeplywy
  # platformy (skaner, raport naruszen) przezyly promocje czlonka. Bezczynne zabieraja te ochrone w chwili,
  # w ktorej zaczyna byc potrzebna, a awaria wyglada na problem z IAM, nie na skutek promocji.
  #
  # `accessLevel: "*"` to jedyny zapis, ktory realizuje intencje „dowolne pochodzenie sieciowe, autoryzacja
  # wylacznie tozsamoscia" (dokumentacja VPC-SC, ingress-egress-rules). Nie jest to poluzowanie reguly
  # „ingress zawsze z access levelem" — ta regula zyje w OPA i wymaga jawnego `allow_without_access_level`
  # z approvalem Security. Tutaj tylko przestajemy renderowac ksztalt, ktorego API nie honoruje.
  baseline_source_any = "*"

  # BASELINE RENDERUJE SIĘ JAKO **JEDNA REGUŁA NA TYTUŁ**, CELUJĄCA W `*` — „dowolny zasób w TEJ
  # konfiguracji perimetru" — A NIE W WYLICZONĄ LISTĘ PROJEKTÓW CZŁONKÓW (DEC-10 + DEC-11).
  #
  # `ingress_to.resources` przyjmuje LISTĘ projektów, a baseline jest z definicji identyczny dla każdego
  # członka: te same tożsamości, to samo źródło, te same operacje. Renderowanie go per członek powielało
  # więc CAŁĄ regułę, żeby zmienić w niej jedno pole — i to powielenie płaciło się z budżetu, którego
  # perimetr ma 6000 atrybutów NA KONFIGURACJĘ (osobno spec i status). Kolaps N reguł w jedną (DEC-10)
  # zdjął to powielenie, ale zostawił w regule listę, która nadal rośnie z każdym członkiem — i to
  # kosztowało DRUGI raz, w innej walucie niż budżet:
  #
  # `ingress_to.resources` JEST `ForceNew` w providerze `hashicorp/google` (zmierzone na 7.43.0), więc
  # dopisanie jednego projektu do listy nie jest aktualizacją reguły, tylko jej ZASTĄPIENIEM. ZMIERZONE
  # (stan żywy 3 członków + jeden nowy członek w konfiguracji, `terraform plan -refresh=false`):
  #
  #     # …dry_run_ingress_policy.rule["baseline--platform-violations-read"] must be replaced
  #           ~ resources = [ # forces replacement
  #     # …dry_run_ingress_policy.rule["baseline--security-scanner-read"]    must be replaced
  #           ~ resources = [ # forces replacement
  #     Plan: 4 to add, 1 to change, 2 to destroy.
  #
  # Terraform kasuje PRZED utworzeniem, a `create_before_destroy` nie jest tu wyjściem (DEC-11: wszystkie
  # granularne reguły mają w stanie TEN SAM `id` — sam perimetr — więc „nowy obok starego" znaczy dwie
  # reguły o tym samym tytule w jednej liście). W konfiguracji dry-run replace jest nieszkodliwy, bo ona
  # niczego nie autoryzuje. W konfiguracji EGZEKWOWANEJ to okno, w którym ŻADEN promowany członek nie ma
  # reguły skanera ani reguły raportu naruszeń — dokładnie ta awaria, po którą baseline w ogóle istnieje,
  # tyle że powtarzalna przy KAŻDYM wniosku i KAŻDEJ promocji, a nie jednorazowa jak sam kolaps.
  #
  # `*` USUWA PRZYCZYNĘ, A NIE OBJAW: reguła przestaje zależeć od członkostwa, więc nie ma czego
  # replace'ować. Dokumentacja VPC-SC (ingress-egress-rules) mówi o tym polu wprost — `*` dopasowuje
  # wszystkie zasoby WEWNĄTRZ perimetru, a `spec` i `status` to dwie osobne konfiguracje perimetru z
  # własnymi listami `resources`. Reguła zbiorcza w `spec` obejmuje więc członków dry-run, ta sama reguła
  # w `status` — wyłącznie promowanych. To jest ta sama granica, którą do tej pory wypisywaliśmy ręcznie.
  #
  # CO SIĘ PRZY TYM POSZERZA — dokładnie jedna rzecz, nazwana wprost: lista wypisana ręcznie obejmowała
  # projekty zadeklarowane W TYM REPO, `*` obejmuje zasoby, które W PERIMETRZE SĄ. Przy `manage_skeleton:
  # false` (brownfield, domyślnie) właścicielem szkieletu jest ktoś inny i może dołożyć zasób poza tym
  # repo — taki zasób baseline obejmie automatycznie. Świadomie: baseline to skaner i raport naruszeń,
  # więc „zasób w perimetrze, którego nie skanujemy" jest gorszym stanem niż „skanujemy też cudzy wpis".
  # Poszerzenie idzie WYŁĄCZNIE po stronie CELU (`ingress_to`); tożsamości i operacje zostają bez zmian,
  # więc reguła nadal wpuszcza dokładnie te same konta na dokładnie te same metody.
  #
  # ZYSK POBOCZNY, POLICZONY: koszt baseline spada z „19 + 2N" do STAŁYCH 21 atrybutów (15 + 1 oraz 4 + 1),
  # czyli **0 atrybutów na członka**. Sufit rośnie z ~521 do ~629 członków przy realistycznej mieszance
  # profili i z 854 do ~1195 przy monoprofilu.
  #
  # TRADE-OFF, ŚWIADOMY (DEC-10): jedna reguła = jeden blast-radius. Per-członkowe reguły niosły
  # audytowalność „kto ma co" w samym kształcie zasobu i pozwalały zepsuć baseline JEDNEMU członkowi.
  # Teraz zła zmiana baseline'u dotyka wszystkich naraz. Kolapsujemy WYŁĄCZNIE baseline, bo on jest wspólny
  # z definicji; reguły profilowe zostają per członek, bo tam różnice między zespołami są realne i tam
  # per-członkowa audytowalność coś znaczy. `*` w regule PROFILOWEJ jest i zostaje zakazane (bramka OPA
  # `vpcsc.perimeter`) — tam znaczyłoby „reguła jednej dywizji działa na projektach wszystkich".
  baseline_target_any = "*"

  # Kształt reguły BEZ celu — cel dokłada każda konfiguracja osobno (dry-run: wszyscy, enforced: tylko
  # promowani). Jedna definicja tożsamości/źródeł/operacji, żeby obie konfiguracje nie mogły się rozjechać.
  baseline_rules_shape = {
    for rule in local.baseline_ingress : "baseline--${rule.title}" => {
      identities = rule.identities
      # Warunek pyta o JAWNA flage, a nie tylko o pusta liste. Bramka OPA i tak nie przepusci reguly
      # baseline bez access levels i bez `allow_without_access_level: true`, ale gdyby ktos ja obszedl,
      # renderer ma sie zdegradowac w strone BEZPIECZNA (regula bez zrodla = nie autoryzuje nic),
      # a nie dorysowac `*` samemu.
      access_levels = length(lookup(rule, "access_levels", [])) > 0 ? [
        for a in rule.access_levels : "accessPolicies/${local.policy_id}/accessLevels/${a}"
        ] : (
        lookup(rule, "allow_without_access_level", false) ? [local.baseline_source_any] : []
      )
      operations = rule.operations
    }
  }

  # Warunek „w tej konfiguracji jest ktokolwiek" ZOSTAJE mimo `*`, ale pilnuje już czego innego i to jest
  # jedyny powód, dla którego wciąż tu jest. Wcześniej chronił przed regułą BEZ celu (API odrzuca ją albo
  # interpretuje szerzej, niż wygląda). Teraz chroni przed regułą, która ma cel ZBYT szeroki wobec intencji:
  # przy `manage_skeleton: false` perimetr może zawierać zasoby, których to repo nie zadeklarowało, więc
  # baseline z `*` w perimetrze BEZ ANI JEDNEGO NASZEGO CZŁONKA sięgałby wyłącznie cudzych wpisów. Zero
  # członków ma dawać BRAK reguły — tak jak dziś (ta sama bezpieczna degradacja co przy egressie bez celu).
  baseline_rules_all = {
    for k, r in local.baseline_rules_shape : k => {
      key           = k
      title         = k
      scope         = "baseline"
      member        = null # reguła zbiorcza nie ma JEDNEGO właściciela — filtruj po `scope`, nie po `member`
      stage         = null # ...i nie ma etapu: o tym, kto jest w konfiguracji, decyduje SAMA KONFIGURACJA
      identities    = r.identities
      access_levels = r.access_levels
      resources     = [local.baseline_target_any]
      operations    = r.operations
    } if length(local.members) > 0
  }

  # Wariant dla konfiguracji EGZEKWOWANEJ. TREŚĆ JEST IDENTYCZNA — po przejściu na `*` różnica między
  # konfiguracjami przestała siedzieć w regule i siedzi tam, gdzie siedziała od początku: w LIŚCIE
  # `resources` samego perimetru (`spec` = wszyscy członkowie, `status` = tylko `stage: enforced`).
  # Dwie mapy zostają, bo różnią się WARUNKIEM ISTNIENIA, a nie zawartością: reguła egzekwowana powstaje
  # dopiero, gdy jest ktokolwiek promowany. Dzięki temu `status` pustego wdrożenia zostaje pusty, a nie
  # dostaje reguły, która czeka z otwartym `*` na pierwszy zasób dołożony do perimetru spoza tego repo.
  #
  # KONSEKWENCJA, KTÓRĄ TRZEBA ZNAĆ: przy PIERWSZEJ promocji te reguły powstają (create), a `depends_on`
  # w rules.tf każe im czekać na wejście projektu do konfiguracji egzekwowanej — jest więc krótkie okno
  # „projekt chroniony, baseline jeszcze nie". Przy KAŻDEJ NASTĘPNEJ promocji reguła już istnieje i nie
  # zmienia się wcale, więc okna nie ma. To jest cała zmiana wobec stanu sprzed tej poprawki: było jedno
  # okno NA KAŻDĄ promocję (replace), jest jedno okno NA CAŁE WDROŻENIE (pierwszy create).
  baseline_rules_enforced = {
    for k, r in local.baseline_rules_shape : k => {
      key           = k
      title         = k
      scope         = "baseline"
      member        = null
      stage         = null
      identities    = r.identities
      access_levels = r.access_levels
      resources     = [local.baseline_target_any]
      operations    = r.operations
    } if length(local.enforced_members) > 0
  }

  # EGRESS ZOSTAJE PER CZŁONEK I `*` GO NIE DOTYCZY — sprawdzone, nie założone.
  #
  # `egress_to.resources` jest w providerze `ForceNew` TAK SAMO jak ingressowe (zmierzone: dopisanie
  # drugiego projektu do `data_source_projects` jednego członka dało
  # `…dry_run_egress_policy.rule[…] must be replaced / ~ resources = [ # forces replacement`).
  # Defekt „każdy wniosek replace'uje regułę wspólną" jednak tu NIE WYSTĘPUJE, bo reguły egress nie są
  # skolapsowane: klucz to `(członek × profil × tytuł)`, więc nowy członek dokłada własną regułę i nie
  # dotyka cudzych. Replace zdarza się wyłącznie wtedy, gdy członek zmienia SWOJĄ listę celów — czyli
  # dokładnie w regule, którą ten wniosek zmienia, i tylko jemu.
  #
  # GDYBY KTOŚ KIEDYŚ SKOLAPSOWAŁ EGRESS „dla budżetu", ten sam defekt wróci — i wtedy poprawka z ingressu
  # NIE JEST DOSTĘPNA: `egress_to.resources = ["*"]` nie znaczy „dowolny zasób w perimetrze", tylko
  # „dowolny zasób POZA nim", czyli zniesienie granicy w kierunku, dla którego ta granica istnieje (bramka
  # OPA odrzuca ten kształt bezwarunkowo i ma tak zostać). Wyjściem byłoby wtedy grupowanie po IDENTYCZNYM
  # celu albo pozostawienie egressu per członek — nigdy gwiazdka.
  #
  # Egress renderujemy TYLKO gdy członek podał niepusty cel — projekt W GCP (`to_projects_from`) albo zasób
  # ZEWNĘTRZNY (`to_external_from`, wyłącznie BigQuery Omni: s3:// / azure://). Pusty cel = brak reguły
  # (bezpieczna degradacja: brak egressu jest zawsze bezpieczniejszym stanem domyślnym niż szeroki egress).
  # Reguła bez ani jednego celu nie jest „regułą do niczego" — API odrzuca ją albo interpretuje szeroko.
  egress_rules_all = {
    for r in flatten([
      for mkey, m in local.members : [
        for p in m.profiles : [
          for rule in lookup(local.profiles[p.name], "egress", []) : {
            key        = "${mkey}--${p.name}--${rule.title}"
            member     = mkey
            stage      = m.stage
            title      = "${mkey}--${rule.title}"
            identities = lookup(p.params, rule.identities_from, [])
            resources  = [for proj in lookup(p.params, lookup(rule, "to_projects_from", "__none__"), []) : "projects/${proj}"]
            # Identyfikatory zewnętrzne przekazujemy DOSŁOWNIE — żadnego prefiksowania. Format narzuca API
            # (s3://BUCKET, azure://ACCOUNT.blob.core.windows.net/CONTAINER), a „pomocna" normalizacja
            # zamieniłaby literówkę w cichy dostęp do innego bucketa.
            external_resources = lookup(p.params, lookup(rule, "to_external_from", "__none__"), [])
            operations         = rule.operations
            scope              = "profile"
          } if length(lookup(p.params, lookup(rule, "to_projects_from", "__none__"), [])) > 0
          || length(lookup(p.params, lookup(rule, "to_external_from", "__none__"), [])) > 0
        ]
      ]
    ]) : r.key => r
  }

  # Konfiguracja dry-run zawiera WSZYSTKICH członków i WSZYSTKIE reguły — także tych już egzekwowanych.
  # DLACZEGO: dry-run to „proponowana przyszła konfiguracja". Gdyby zawierała tylko kandydatów, promocja
  # członka wyjmowałaby go z dry-run i wkładała do enforced, tworząc moment, w którym nie należy do żadnej
  # konfiguracji. Przy tym układzie promocja jest czysto addytywna: dochodzi zasób enforced, dry-run zostaje.
  # Reguły baseline i profilowe idą do tych samych zasobów — z punktu widzenia API to po prostu ingress.
  # Trzymamy je w osobnych locals po to, żeby plan i testy pokazywały, skąd reguła się wzięła, ORAZ dlatego,
  # że po kolapsie mają różną kardynalność: profilowe są per (członek × profil), baseline jest jeden na tytuł.
  ingress_rules_effective = merge(local.ingress_rules_all, local.baseline_rules_all)

  # Filtr po `stage` obowiązuje TYLKO reguły profilowe — one wciąż należą do jednego członka. Baseline po
  # kolapsie wchodzi do konfiguracji egzekwowanej własnym wariantem, który różni się listą zasobów.
  # Gdyby zostawić tu jeden filtr po `stage`, baseline (stage = null) wypadłby z konfiguracji egzekwowanej
  # CICHO: promocja przechodziłaby zielonym planem, a skaner i raport naruszeń traciłyby dostęp dokładnie
  # w chwili, w której zaczyna być potrzebny — dokładnie ta awaria, po którą baseline w ogóle istnieje.
  ingress_rules_enforced = merge(
    { for k, r in local.ingress_rules_all : k => r if r.stage == "enforced" },
    local.baseline_rules_enforced,
  )
  egress_rules_enforced = { for k, r in local.egress_rules_all : k => r if r.stage == "enforced" }

  # --- budżet atrybutów: JEDNA definicja liczenia ---------------------------------------------------
  #
  # Limit 6000 obowiązuje OSOBNO dla każdej konfiguracji i dotyczy atrybutów W REGUŁACH ingress/egress:
  # odwołań do projektów, sieci, access levels, selektorów metod, tożsamości i ról (docs: VPC SC quotas).
  # `restricted_services` i lista członków mają własne, osobne limity i tu się NIE liczą.
  #
  # DLACZEGO local, a nie to samo wyrażenie w dwóch miejscach: „ile atrybutów zjada ta konfiguracja" miało
  # w tym repo TRZY niezależne implementacje — output, kontrakt i `tools/attribute_budget.py`. Rozjechały
  # się dokładnie tak, jak rozjeżdżają się kopie: output liczył reguły baseline, kontrakt ich nie liczył
  # w dry-run, ale liczył w enforced (bo `ingress_rules_enforced` filtruje `ingress_rules_effective`), więc
  # promocja wszystkich członków dawała `used_enforced > used_dry_run` — liczbę, która przy dry-run
  # zawierającym WSZYSTKICH członków nie może powstać. Trzy liczby na jedno pytanie to nie redundancja,
  # tylko gwarancja, że przynajmniej dwie kłamią.
  attribute_usage_dry_run = sum(concat([0], [
    for k, r in merge(local.ingress_rules_effective, local.egress_rules_all) :
    length(r.identities) + length(lookup(r, "access_levels", [])) + length(r.resources)
    + length(lookup(r, "external_resources", []))
    + sum(concat([0], [for op in r.operations : 1 + length(lookup(op, "methods", [])) + length(lookup(op, "permissions", []))]))
  ]))

  attribute_usage_enforced = sum(concat([0], [
    for k, r in merge(local.ingress_rules_enforced, local.egress_rules_enforced) :
    length(r.identities) + length(lookup(r, "access_levels", [])) + length(r.resources)
    + length(lookup(r, "external_resources", []))
    + sum(concat([0], [for op in r.operations : 1 + length(lookup(op, "methods", [])) + length(lookup(op, "permissions", []))]))
  ]))
}
