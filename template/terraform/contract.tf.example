# Kontrakt — wąski JSON publikowany po każdym apply dla repozytoriów zespołów.
#
# DLACZEGO nie data source: provider NIE MA `data` source dla service perimetra (ani `google`, ani
# `google-beta` — są tylko access_policy, access_policy_iam_policy i supported_service/s). Treść perimetru
# jest dostępna wyłącznie przez zasób, a odczyt przez API wymagałby `servicePerimeters.get` na organizacji,
# czyli wglądu w CAŁĄ granicę: reguły i tożsamości wszystkich dywizji.
#
# DLACZEGO nie `terraform_remote_state`: HashiCorp odradza to wprost — kto może czytać outputy, ten ma dostęp
# do całego snapshotu stanu. Nasz state to pełna mapa granicy. Rekomendacja z docs brzmi: „explicitly
# publishing data for external consumption to a separate location instead of accessing it via remote state".
#
# Ten plik jest realizacją tej rekomendacji. Pola są wypisane JAWNIE, pole po polu — nigdy
# `jsonencode(local.everything)`. Gdyby kiedyś do kontraktu trafiło cokolwiek wrażliwego, bucket kontraktów
# staje się równorzędną powierzchnią co bucket stanu i musi mieć ten sam reżim (CMEK, Data Access logi).

locals {
  contract_enabled = contains(keys(local.policy), "contract")

  # Atrapa z KOMPLETEM kluczy, nie `null` i nie `{}`, gdy sekcji `contract` nie ma w policy.yaml.
  # `count = 0` na zasobie NIE wystarcza z dwóch niezależnych powodów: blok `locals` niżej liczy się zawsze
  # (`lookup(null, …)` = błąd), a `terraform validate` sprawdza typy wyrażeń w atrybutach zasobu również
  # wtedy, gdy nie powstanie ani jedna instancja (`{}` nie ma atrybutu `bucket`). Efekt bez atrapy: repo bez
  # kontraktu nie przechodzi walidacji, czyli sekcja opisana jako opcjonalna jest w praktyce obowiązkowa.
  # Dokument policzy się wtedy „na sucho" i nigdzie nie trafi, bo publikuje go zasób za `count`.
  contract = local.contract_enabled ? local.policy.contract : {
    bucket = ""
    path   = ""
  }

  # Zużycie budżetu atrybutów — TA SAMA wartość co w `attribute_estimate` (outputs.tf), bo obie czytają
  # `local.attribute_usage_*` z locals.tf. Zespół widzi, ile miejsca zostało, zanim poprosi o profil,
  # który je zje, i widzi DOKŁADNIE tę liczbę, na którą pada guard CI — nie drugie wyliczenie tego samego.
  contract_budget = {
    limit_per_config = local.policy.attribute_budget.limit_per_config
    used_dry_run     = local.attribute_usage_dry_run
    used_enforced    = local.attribute_usage_enforced
  }

  contract_document = {
    schema_version = 1
    perimeter_name = local.perimeter_full_name

    # Lista usług objętych granicą — zespół musi wiedzieć, czy usługa, której używa, jest w ogóle chroniona.
    restricted_services = local.restricted_services

    # Parametry okna obserwacji: ile dni potrwa, zanim jego projekt zostanie objęty ochroną.
    onboarding = local.policy.onboarding

    # TYLKO NAZWY access levels. Zawartość (zakresy IP, device policy) zostaje w repo — zespół ma wskazać
    # warunek kontekstu, nie znać naszą topologię sieci.
    access_levels = sort(keys(local.access_levels))

    # Katalog profili: nazwa, ryzyko, opis i nazwy parametrów do wypełnienia. Bez treści reguł — te są
    # implementacją, a zespół potrzebuje interfejsu.
    profiles = [for name, p in local.profiles : {
      name       = name
      risk       = lookup(p, "risk", "unknown")
      summary    = lookup(p, "summary", "")
      parameters = [for param in lookup(p, "parameters", []) : param.name]
      has_egress = length(lookup(p, "egress", [])) > 0
    }]

    # Mapowanie repo→projekty. Zespół sprawdza u siebie, czy wolno mu wnioskować o dany projekt, ZANIM wyśle
    # zgłoszenie. UWAGA: to jest kopia informacyjna — decyzję i tak podejmuje reguła OPA po naszej stronie na
    # podstawie pliku w repo. Gdyby kontrakt był źródłem decyzji, wystarczyłoby go podmienić.
    contributors = [for c in local.contributors : {
      repository       = c.repository
      division         = c.division
      allowed_projects = c.allowed_projects
    }]

    # Czy lista członków w ogóle jest publikowana. Bez tego pola pusta lista jest dwuznaczna („nikogo jeszcze
    # nie ma" kontra „nie publikujemy"), a konsument, który sprawdza na niej „czy mój projekt już jest",
    # dostawałby ciche zielone przy wyłączonej publikacji — czyli bramkę, która nie jest bramką.
    members_published = local.contract_enabled && lookup(local.contract, "publish_members", true)

    # Członkowie: wyłącznie dywizja, projekt i etap. Zero reguł, zero tożsamości, zero access levels.
    members = lookup(local.contract, "publish_members", true) ? [
      for k, m in local.members : {
        division   = m.division
        project_id = m.project_id
        stage      = m.stage
      }
    ] : []

    attribute_budget = local.contract_budget
  }
}

resource "google_storage_bucket_object" "contract" {
  count = local.contract_enabled ? 1 : 0

  bucket = local.contract.bucket
  name   = local.contract.path

  # jsonencode na JAWNIE zbudowanym obiekcie — nie na locals „wszystko".
  content      = jsonencode(local.contract_document)
  content_type = "application/json"

  # Cache-Control: no-store — konsument ma zawsze dostać aktualną wersję. Kontrakt jest mały, a stary
  # kontrakt oznacza, że zespół waliduje wobec profili, które mogły już zniknąć.
  cache_control = "no-store"

  lifecycle {
    # Bucket kontraktów MUSI być inny niż bucket stanu. Wspólny bucket oznacza, że jeden błąd w warunku IAM
    # odsłania state — a state to pełna mapa granicy, nie 4 KB metadanych.
    precondition {
      condition     = local.contract.bucket != lookup(local.contract, "state_bucket", "")
      error_message = "Kontrakt i stan Terraform NIE MOGĄ leżeć w tym samym buckecie (perimeter/policy.yaml §contract)."
    }
  }
}

# --- druga publikacja: ten sam kontrakt jako asset release'u --------------------------------------------
#
# DLACZEGO DWA MIEJSCA. Pobranie kontraktu z bucketa wymaga od repozytorium dywizji TOŻSAMOŚCI W GCP
# (WIF + konto serwisowe) i grantu na prefiksie kontraktu. Przy trzydziestu dywizjach to trzydzieści grantów
# po to, żeby przeczytać 4 KB — a zdanie „zespół nie dostaje ŻADNYCH uprawnień w GCP" przestaje być faktem
# dokładnie w tym miejscu. Asset release'u pobiera się tokenem GitHuba, który zespół i tak musi mieć: paczka
# bramek (`gates.tar.gz`) jedzie tą samą drogą i tym samym `contents: read`. Druga publikacja NIE dokłada
# więc ani jednego nowego uprawnienia po żadnej ze stron. Bucket zostaje dla konsumentów maszynowych spoza
# GitHuba (skrypty, joby w GCP) — tam nic się nie zmienia.
#
# DLACZEGO OUTPUT CZYTA ATRYBUT ZASOBU, a nie liczy `jsonencode(local.contract_document)` po raz drugi:
# drugie wyliczenie jest DRUGIM RENDEREM tych samych danych, a dwa rendery mogą się rozjechać (inne wejście,
# inny apply, apply przerwany w połowie). Tutaj bajty assetu to DOKŁADNIE te bajty, które Terraform wysłał
# do bucketa. To jest cała treść wymagania „jedna publikacja, dwa miejsca": rozjazd nie jest mało
# prawdopodobny — jest niewyrażalny, bo nie ma drugiego źródła, z którego mógłby powstać.
#
# `one(...)` zamiast `[0]`: przy wyłączonej sekcji `contract` zasobu nie ma, więc output jest `null`,
# a krok apply mówi wprost „nie ma czego publikować". `[0]` wywracałby wtedy apply na indeksie — czyli
# sekcja opisana jako opcjonalna znowu byłaby obowiązkowa (ten sam błąd co z atrapą `local.contract` wyżej).
output "contract_json" {
  description = "Treść opublikowanego kontraktu — DOKŁADNIE te bajty, które poszły do bucketa. null, gdy policy.yaml nie ma sekcji `contract`."
  # `sensitive` NIE dlatego, że kontrakt jest sekretem (nie jest — to jawna wewnętrznie lista interfejsów),
  # tylko dlatego, że atrybut `content` jest sensitive w providerze. Bez tej flagi `terraform validate`
  # odmawia eksportu wartości pochodzącej z wrażliwego atrybutu.
  sensitive = true
  value     = one(google_storage_bucket_object.contract[*].content)
}

# Suma kontrolna POLICZONA PRZEZ GCS z obiektu, który realnie wylądował w buckecie (atrybut `computed`,
# wypełniany odpowiedzią API). Krok apply porównuje ją z sumą pliku, który wgrywa do release'u — dzięki temu
# weryfikacja patrzy na DRUGĄ STRONĘ publikacji, a nie sama na siebie. Własne `md5(jsonencode(...))` byłoby
# tautologią: zgadzałoby się także wtedy, gdyby do bucketa nie poszło nic.
output "contract_md5" {
  description = "Base64 MD5 obiektu kontraktu, policzone przez GCS. null przy wyłączonej sekcji `contract`."
  value       = one(google_storage_bucket_object.contract[*].md5hash)
}
