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
            key           = "${mkey}--${p.name}--${rule.title}"
            member        = mkey
            stage         = m.stage
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

  baseline_rules_all = {
    for r in flatten([
      for mkey, m in local.members : [
        for rule in local.baseline_ingress : {
          key           = "${mkey}--baseline--${rule.title}"
          member        = mkey
          stage         = m.stage
          title         = "${mkey}--baseline--${rule.title}"
          identities    = rule.identities
          access_levels = [for a in lookup(rule, "access_levels", []) : "accessPolicies/${local.policy_id}/accessLevels/${a}"]
          resources     = ["projects/${m.project_number}"]
          operations    = rule.operations
        }
      ]
    ]) : r.key => r
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
  # Trzymamy je w osobnych locals tylko po to, żeby plan i testy pokazywały, skąd reguła się wzięła.
  ingress_rules_effective = merge(local.ingress_rules_all, local.baseline_rules_all)

  ingress_rules_enforced = { for k, r in local.ingress_rules_effective : k => r if r.stage == "enforced" }
  egress_rules_enforced  = { for k, r in local.egress_rules_all : k => r if r.stage == "enforced" }
}
