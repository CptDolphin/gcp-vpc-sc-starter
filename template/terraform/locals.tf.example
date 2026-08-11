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

  # Katalog członków i profili. `fileset` czyta stan katalogu przy planie — dodanie pliku przez bota
  # jest równoważne dodaniu zasobu, bez żadnej listy do ręcznej aktualizacji.
  members = {
    for f in fileset("${local.perimeter_dir}/members", "*.yaml") :
    trimsuffix(f, ".yaml") => yamldecode(file("${local.perimeter_dir}/members/${f}"))
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

  restricted_services = local.policy.restricted_services
  accessible_services = local.policy.vpc_accessible_services.same_as_restricted ? local.policy.restricted_services : []

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

  # BASELINE RENDERUJE SIĘ JAKO **JEDNA REGUŁA NA TYTUŁ**, Z LISTĄ ZASOBÓW WSZYSTKICH CZŁONKÓW.
  #
  # `ingress_to.resources` przyjmuje LISTĘ projektów, a baseline jest z definicji identyczny dla każdego
  # członka: te same tożsamości, to samo źródło, te same operacje. Renderowanie go per członek powielało
  # więc CAŁĄ regułę, żeby zmienić w niej jedno pole — i to powielenie płaciło się z budżetu, którego
  # perimetr ma 6000 atrybutów NA KONFIGURACJĘ (osobno spec i status).
  #
  # ZMIERZONE na żywym perimetrze (`perimeters describe`, niezależne policzenie z odpowiedzi API):
  #   przed:  2 reguły baseline × 2 członków = 42 atrybuty, czyli 21 NA CZŁONKA
  #           (security-scanner-read 16 = ident 1 + źródło 1 + zasób 1 + 4 usługi + 9 metod,
  #            platform-violations-read 5 = ident 1 + źródło 1 + zasób 1 + 1 usługa + 1 metoda)
  #   po:     (15 + N) + (4 + N) = 19 + 2N, czyli **2 atrybuty na członka** — po jednym zasobie na regułę.
  # Przy 500 członkach: 10500 atrybutów przed (limit 6000 — konfiguracja NIE POWSTAJE), 1019 po.
  #
  # TRADE-OFF, ŚWIADOMY (DEC-10): jedna reguła = jeden blast-radius. Per-członkowe reguły niosły
  # audytowalność „kto ma co" w samym kształcie zasobu i pozwalały zepsuć baseline JEDNEMU członkowi.
  # Teraz zła zmiana baseline'u dotyka wszystkich naraz. Kolapsujemy WYŁĄCZNIE baseline, bo on jest wspólny
  # z definicji; reguły profilowe zostają per członek, bo tam różnice między zespołami są realne i tam
  # per-członkowa audytowalność coś znaczy.
  #
  # `sort()` daje kolejność niezależną od kolejności iteracji mapy: bez niego dodanie członka potrafi
  # przetasować listę i wyprodukować diff w regule, w której nic się nie zmieniło.
  baseline_targets_all      = sort([for mkey, m in local.members : "projects/${m.project_number}"])
  baseline_targets_enforced = sort([for mkey, m in local.enforced_members : "projects/${m.project_number}"])

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

  # Warunek `length(...) > 0` NIE jest kosmetyką: reguła ingress bez ani jednego zasobu jest przez API
  # odrzucana albo — gorzej — interpretowana szerzej, niż wygląda. Zero członków musi dawać BRAK reguły,
  # nie regułę bez celu (ta sama bezpieczna degradacja co przy egressie bez celu niżej).
  baseline_rules_all = {
    for k, r in local.baseline_rules_shape : k => {
      key           = k
      title         = k
      scope         = "baseline"
      member        = null # reguła zbiorcza nie ma JEDNEGO właściciela — filtruj po `scope`, nie po `member`
      stage         = null # ...i nie ma etapu: o tym, kto jest w konfiguracji, decyduje lista `resources`
      identities    = r.identities
      access_levels = r.access_levels
      resources     = local.baseline_targets_all
      operations    = r.operations
    } if length(local.baseline_targets_all) > 0
  }

  # Wariant dla konfiguracji EGZEKWOWANEJ — ta sama reguła, ale celuje wyłącznie w członków `stage: enforced`.
  # DLACZEGO osobna mapa, a nie filtr po `stage` jak przy profilach: po kolapsie reguła nie należy do jednego
  # członka, więc „etap reguły" przestał istnieć jako pojęcie. Różnica między konfiguracjami siedzi teraz
  # w LIŚCIE ZASOBÓW i tylko tam — inaczej perimetr autoryzowałby w statusie projekt, którego w statusie nie ma.
  baseline_rules_enforced = {
    for k, r in local.baseline_rules_shape : k => {
      key           = k
      title         = k
      scope         = "baseline"
      member        = null
      stage         = null
      identities    = r.identities
      access_levels = r.access_levels
      resources     = local.baseline_targets_enforced
      operations    = r.operations
    } if length(local.baseline_targets_enforced) > 0
  }

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
    + sum(concat([0], [for op in r.operations : 1 + length(op.methods)]))
  ]))

  attribute_usage_enforced = sum(concat([0], [
    for k, r in merge(local.ingress_rules_enforced, local.egress_rules_enforced) :
    length(r.identities) + length(lookup(r, "access_levels", [])) + length(r.resources)
    + length(lookup(r, "external_resources", []))
    + sum(concat([0], [for op in r.operations : 1 + length(op.methods)]))
  ]))
}
