variable "org_id" {
  description = "Numer organizacji GCP. Uprawnienia Access Context Managera działają WYŁĄCZNIE na organizacji albo na polityce — grant na folderze/projekcie nie ma efektu."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{6,20}$", var.org_id))
    error_message = "org_id to sam numer (bez prefiksu organizations/)."
  }
}

variable "identity_project_id" {
  description = "Projekt, w którym żyją konta serwisowe i pula WIF. Zwykle centralny projekt tożsamości/CI, NIE projekt aplikacyjny."
  type        = string

  validation {
    # Reguła nazewnicza GCP dla project_id. Numer wklejony tu zamiast ID tworzy pulę WIF w projekcie, którego
    # nie ma — a komunikat API mówi tylko „not found", bez podpowiedzi, że pomyliły się dwa różne pola.
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.identity_project_id))
    error_message = "identity_project_id to ID projektu (6-30 znaków, małe litery/cyfry/myślniki), nie jego numer."
  }
}

variable "github_repository" {
  description = "Repozytorium w formacie ORG/REPO. Wchodzi do attribute_condition puli WIF — to jedyne repo, które wymieni token OIDC na dostęp."
  type        = string

  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repository))
    error_message = "Format: ORG/REPO (np. example-org/gcp-vpc-sc)."
  }
}

variable "apply_environment" {
  description = "Nazwa environment GitHuba wymaganego do impersonacji konta apply. Token z pull requesta go nie niesie, więc tą tożsamością nie da się posłużyć z PR-a."
  type        = string
  default     = "perimeter-apply"

  validation {
    # Pusta nazwa w `principalSet` konta apply dałaby zbiór dopasowujący KAŻDY token z tego repozytorium —
    # w tym token z pull requesta. Rozdział plan/apply przestałby istnieć, a jedyną pozostałą barierą byłaby
    # polityka gałęzi environment, o której ten stack nic nie wie.
    condition     = length(trimspace(var.apply_environment)) > 0
    error_message = "apply_environment nie może być puste — to ono odcina tokeny z pull requestów od konta apply."
  }
}

variable "break_glass_environment" {
  description = "Nazwa environment GitHuba, który wolno wymienić na konto apply DRUGĄ drogą — awaryjną (`break-glass.yml`). Musi zgadzać się z polem `environment:` w tamtym workflow; rozjazd tych dwóch nazw kończy się odmową `iam.serviceAccounts.getAccessToken` w środku incydentu."
  type        = string
  default     = "break-glass"

  validation {
    # Pusta wartość dałaby ten sam zbiór dopasowujący każdy token z repozytorium, co pusty
    # `apply_environment` — a przy tym po cichu, bo droga awaryjna jest uruchamiana rzadko.
    condition     = length(trimspace(var.break_glass_environment)) > 0
    error_message = "break_glass_environment nie może być puste — pusta nazwa dopasowuje KAŻDY token z tego repozytorium."
  }

  validation {
    # Ta sama nazwa co `apply_environment` znosi jedyną rzecz, którą osobny environment kupuje: inny
    # zestaw zatwierdzających dla awarii. Zwijanie obu do jednej nazwy ma być decyzją, nie literówką.
    condition     = trimspace(var.break_glass_environment) != trimspace(var.apply_environment)
    error_message = "break_glass_environment == apply_environment — droga awaryjna czekałaby wtedy na tych samych ludzi, co rutynowa; to znosi powód jej istnienia."
  }
}

variable "manage_alert_topic" {
  description = "Czy TEN stack tworzy temat Pub/Sub dla kanalu maszynowego alertow (razem z subskrypcja-ewidencja i prawem publikacji dla agenta powiadomien). Domyslnie WYLACZONE — temat z prawem publikacji jest sciezka wyprowadzenia danych, wiec wdrozenie ma go dostac swiadomie, a nie przy okazji. Wylaczenie zostawia alerty z samymi kanalami e-mail; wlaczenie wymaga poswiadczen do chmury juz przy `plan` (dwa zasoby serviceusage budza providera), wiec bramka bez dostepu do GCP planuje ten stack tylko przy `false`."
  type        = bool
  default     = false
}

variable "alert_topic_name" {
  description = "Nazwa tematu Pub/Sub dla kanalu maszynowego alertow (musi zgadzac sie z `channels.machine.pubsub_topic` w perimeter/alerting.yaml). Kanal jest OPCJONALNY po stronie perimetru, ale temat powstaje razem z projektem monitoringu — nieuzywany temat nic nie kosztuje, a brakujacy blokuje utworzenie kanalu."
  type        = string
  default     = "vpcsc-alerts"

  validation {
    # Sama nazwa, nie pelna sciezka. Pelna sciezka wklejona tutaj dalaby temat o nazwie zawierajacej
    # ukosniki — API go odrzuci, ale dopiero na apply.
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9._~%+-]{2,254}$", var.alert_topic_name))
    error_message = "alert_topic_name to SAMA nazwa tematu, bez prefiksu projects/<projekt>/topics/."
  }
}

variable "watch_ref" {
  description = "Ref GitHuba, z którego wolno impersonować konto `watch` (obserwator granicy, `watch.yml`). Domyślnie gałąź domyślna. WĘŻEJ niż konto `plan`, mimo że `watch` robi mniej: `plan` jest read-only, a `watch` MA prawo zapisu metryki — czyli prawo do skłamania o stanie granicy. Token z pull requesta niesie `refs/pull/N/merge`, więc do tej wartości nie pasuje."
  type        = string
  default     = "refs/heads/main"

  validation {
    # Sama nazwa gałęzi (`main`) zamiast pełnego refa dałaby `principalSet` dopasowujący NIC — grant
    # powstaje, workflow pada na `unable to impersonate`, a diagnoza schodzi na WIF i role. Wymuszamy
    # kształt, w którym ta pomyłka nie przechodzi przez `plan`.
    condition     = startswith(var.watch_ref, "refs/")
    error_message = "watch_ref to PEŁNY ref (np. `refs/heads/main`), nie sama nazwa gałęzi."
  }
}

variable "state_bucket" {
  description = "Bucket ze stanem Terraform repozytorium perimetru (versioning + soft-delete, BEZ retention-lock — lock łamie backend przy pierwszym zapisie)."
  type        = string

  validation {
    # Nazwa bucketa, nie URL. `gs://` wklejone z konsoli daje warunek IAM na zasobie o nazwie zawierającej
    # dwukropki — grant powstaje, ale nie dotyczy niczego, co istnieje.
    condition     = can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", var.state_bucket))
    error_message = "state_bucket to sama nazwa bucketa, bez prefiksu gs:// i bez ścieżki."
  }
}

variable "state_prefix" {
  description = "Prefiks obiektów stanu. Warunek IAM zawęża dostęp kont do tego prefiksu, a nie do całego bucketa."
  type        = string
  default     = "vpc-sc/perimeter"

  # DWA TRYBY AWARII PREFIKSU — komentarz WSPÓLNY dla `state_prefix` i `contract_prefix`. Oba robią dokładnie
  # jedno: wklejają się do tego samego wyrażenia IAM `resource.name.startsWith(".../objects/<prefiks>")`.
  # Psują się w PRZECIWNE strony, więc jeden warunek musi łapać oba naraz:
  #
  #   1. Wiodący `/` → `objects//vpc-sc/...`, co nie pasuje do żadnego obiektu. Warunek przestaje cokolwiek
  #      DOPUSZCZAĆ: apply jest zielony, a konsument dostaje 403 i nie wie dlaczego. Awaria GŁOŚNA — boli
  #      od razu, ktoś ją w końcu zgłosi.
  #   2. Pusty (lub sam whitespace) → wyrażenie degeneruje się do `.../objects/`, czyli pasuje do KAŻDEGO
  #      obiektu w buckecie. Grant nie znika — po CICHU ROZSZERZA się na cały bucket. Nic nie pada, nikt nie
  #      zgłasza, a zawężenie do prefiksu (jedyny powód, dla którego ten warunek w ogóle istnieje) przestaje
  #      działać. To ten tryb jest groźniejszy, dokładnie dlatego, że nie boli.
  #
  # DLACZEGO KOPIA WARUNKU, A NIE JEDNA FUNKCJA: Terraform nie ma funkcji użytkownika — blok `function` to
  # OpenTofu (sprawdzone na 1.15.5: „Blocks of type function are not expected here"), a `validation` nie
  # sięga po `locals`. Wspólny jest więc ten komentarz, a zgodności obu bliźniaków pilnuje selftest
  # (`test_iam_bootstrap`) — planem i odczytem gotowego warunku, nie porównaniem tekstu. Brak takiego
  # spinacza jest tym, co pozwoliło `contract_prefix` przez cały czas nie mieć ŻADNEJ walidacji (#1912).
  validation {
    condition     = !startswith(var.state_prefix, "/") && length(trimspace(var.state_prefix)) > 0
    error_message = "state_prefix nie może być pusty ani zaczynać się od /."
  }
}

variable "wif_pool_id" {
  description = "ID puli Workload Identity Federation."
  type        = string
  default     = "github-actions"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{3,30}[a-z0-9]$", var.wif_pool_id))
    error_message = "wif_pool_id: 4-32 znaki, małe litery/cyfry/myślniki, zaczyna się literą."
  }
}

variable "wif_provider_id" {
  description = "ID providera OIDC w puli."
  type        = string
  default     = "github"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{3,30}[a-z0-9]$", var.wif_provider_id))
    error_message = "wif_provider_id: 4-32 znaki, małe litery/cyfry/myślniki, zaczyna się literą."
  }
}

variable "grant_logging_viewer" {
  description = "Czy nadać kontu plan roles/logging.viewer na organizacji. Bez tego workflow violations-report nie odczyta naruszeń dry-run, a wtedy promocja do enforced opiera się na deklaracji zamiast na dowodzie. DRUGI, MNIEJ OCZYWISTY SKUTEK ustawienia na false: przy włączonej sekcji `monitoring` w policy.yaml ta sama rola daje kontu plan `logging.logMetrics.get`, bez którego KAŻDY `terraform plan` pada na odświeżeniu metryk — czyli wyłączenie raportu wyłącza też planowanie."
  type        = bool
  default     = true
}

variable "manage_deny_policy" {
  description = "Czy TEN stack tworzy politykę IAM Deny (sekcja 5b main.tf). `true` wymaga, żeby tożsamość applikująca miała `roles/iam.denyAdmin` — JEDYNĄ rolę w Google Cloud niosącą `iam.denypolicies.create`, a przy okazji `.delete` na każdej polityce deny w organizacji; roli własnej z tymi uprawnieniami zbudować się nie da (`NOT_SUPPORTED`). `false` = warstwa zostaje poza tym stackiem świadomie i przestaje udawać wdrożoną."
  type        = bool
  default     = true

  # DLACZEGO DOMYŚLNIE `true`, skoro część wdrożeń tego grantu nie dostanie: domyślna wartość ma opisywać
  # stan POŻĄDANY, nie najczęstszy. Guardrail ma istnieć; rezygnacja z niego jest decyzją, więc ma
  # kosztować jedną linijkę w tfvars i zostawiać ślad w diffie — a nie być stanem, w który wchodzi się
  # przez nieuzupełnienie pliku.
}

variable "deny_reader_principals" {
  description = "Kto może ODCZYTAĆ polityki deny na organizacji (rola własna `vpcScDenyReader`, sekcja 5a). Pełne principale IAM, np. `group:grp-example-iam@example.com`. Pusta lista jest dopuszczalna, ale znaczy, że NIKT nie odpowie na pytanie „czy guardrail stoi”: odmowa odczytu jest w tym API nieodróżnialna od braku zasobu — jedno i drugie to `403`."
  type        = list(string)
  default     = []

  validation {
    # Pełny principal, nie sam adres — ODWROTNIE niż `contract_reader_groups` niżej, i to jest świadome.
    # Tamta zmienna karmi JEDEN zasób, który potrafi zbudować wyłącznie grupę, więc prefiks jest tam
    # niewyrażalny z definicji. Odczyt warstwy deny bierze trzy różne typy tożsamości (człowiek dyżurny,
    # grupa audytu, konto skanera), więc typ MUSI być widoczny w wartości — inaczej ta sama linijka
    # znaczyłaby co innego zależnie od tego, co domyśli się sobie main.tf.
    #
    # `domain:` i `allUsers` odrzucone osobno: obie formy PRZESZŁYBY IAM i dały odczyt mapy guardraili
    # całej domenie albo internetowi. Polityka deny wymienia z nazwy konta, które mają być zablokowane,
    # i uprawnienia, o które toczy się gra — to instrukcja obejścia dla kogoś, kto jej nie powinien znać.
    condition = alltrue([
      for p in var.deny_reader_principals :
      can(regex("^(user|group|serviceAccount):[^:@\\s]+@[^:@\\s]+\\.[a-zA-Z]{2,}$", p))
    ])
    error_message = "deny_reader_principals: pełny principal IAM z adresem — `user:…@…`, `group:…@…` albo `serviceAccount:…@…`. Bez `domain:` i bez allUsers/allAuthenticatedUsers."
  }
}

variable "monitoring_project_id" {
  description = "Projekt, w którym repozytorium perimetru tworzy metryki i alerty — musi zgadzać się z `monitoring.project_id` w perimeter/policy.yaml. Puste = sekcja `monitoring` wyłączona, żaden grant nie powstaje (bezpieczna degradacja)."
  type        = string
  default     = ""

  validation {
    # Puste = monitoring wyłączony (świadomie dopuszczone, tak samo jak przy `contracts_bucket`).
    # Niepuste musi być ID projektu — numer wklejony tu zamiast ID tworzy granty w projekcie, którego nie ma,
    # a API mówi tylko „not found", bez podpowiedzi, że pomyliły się dwa różne pola.
    condition     = var.monitoring_project_id == "" || can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.monitoring_project_id))
    error_message = "monitoring_project_id to ID projektu (6-30 znaków, małe litery/cyfry/myślniki) albo pusty string, gdy sekcja monitoring w policy.yaml jest wyłączona."
  }
}

variable "contracts_bucket" {
  description = "Bucket na kontrakt publikowany dla repozytoriów zespołów. MUSI być inny niż bucket stanu — wspólny bucket oznacza, że jeden błąd w warunku IAM odsłania state. Puste = kanał zewnętrzny nieaktywny (bezpieczna degradacja)."
  type        = string
  default     = ""

  validation {
    # Puste = kanał wyłączony (świadomie dopuszczone). Niepuste musi być nazwą bucketa.
    condition     = var.contracts_bucket == "" || can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", var.contracts_bucket))
    error_message = "contracts_bucket to sama nazwa bucketa (albo pusty string, gdy kanał zewnętrzny ma być nieaktywny)."
  }
}

variable "contract_prefix" {
  description = "Prefiks obiektów kontraktu. Warunek IAM zawęża oba ACL do tego prefiksu, nie do całego bucketa."
  type        = string
  default     = "vpc-sc/"

  validation {
    # Warunek identyczny jak przy `state_prefix` — oba tryby awarii opisane TAM, przy pierwszym z bliźniaków.
    # RÓŻNICA JEST W CENIE trybu cichego (pusty prefiks). Bucket stanu należy do tego jednego stacku, a
    # `contracts_bucket` z założenia dzielimy z konsumentami spoza niego. Pusty prefiks daje tu grupom
    # z `contract_reader_groups` odczyt WSZYSTKIEGO w tym buckecie, a `sa-vpcsc-apply` (objectAdmin) — zapis
    # wszędzie w nim, także na obiektach, których ten stack nie publikuje i o których nic nie wie. Kontrakt
    # miał być jedyną rzeczą wystawioną na zewnątrz; bez tego warunku staje się nią cały bucket.
    condition     = !startswith(var.contract_prefix, "/") && length(trimspace(var.contract_prefix)) > 0
    error_message = "contract_prefix nie może być pusty ani zaczynać się od /."
  }
}

variable "contract_reader_groups" {
  description = "Grupy Google konsumentów SPOZA GitHuba (joby w GCP, skrypty operacyjne), które mogą CZYTAĆ kontrakt z bucketa — read-only. SAM adres grupy, BEZ prefiksu `group:`: prefiks dokłada main.tf. Repozytoria dywizji tu NIE należą: pobierają kontrakt jako asset release'u, tokenem GitHuba. Pusta lista = poprawne, domyślne ustawienie."
  type        = list(string)
  default     = []

  # DLACZEGO GRUPY, A NIE KONTA POJEDYNCZYCH OSÓB: zespół utrzymujący tych konsumentów zmienia skład dużo
  # częściej niż ten stack. Człowiek wpisany tutaj odchodzi z firmy i zostawia grant, którego nikt nie
  # sprząta, bo nikt już nie pamięta, że istnieje. Adres grupy przeżywa rotację — dostęp nadaje się i odbiera
  # w katalogu, tam gdzie i tak zarządza się składem zespołu, BEZ zmiany w Terraformie i bez apply przez
  # zespół IAM (to on jest właścicielem tego stacku, więc każda taka zmiana to osobna kolejka i przegląd).
  #
  # KONTRAKT TEJ ZMIENNEJ: sam adres, prefiks dokłada main.tf. Trzy miejsca muszą mówić to samo — walidacja
  # niżej, `member` w main.tf i przykład w terraform.tfvars.sample. Rozjazd któregokolwiek z nich daje albo
  # `group:group:...`, albo goły adres jako principala; jedno i drugie to grant, który nie działa. Pilnuje
  # tego selftest, bo przy `default = []` sam plan tej wartości nigdy nie dotyka.

  validation {
    # Dwukropek w wartości znaczy, że ktoś wkleił gotowego principala z konsoli albo z dokumentacji IAM.
    # Odrzucamy KAŻDY prefiks, także taki, którego dziś nie znamy — adres grupy nigdy nie zawiera dwukropka,
    # więc ten warunek się nie zestarzeje, a lista dozwolonych prefiksów zestarzałaby się po cichu.
    # `allUsers`/`allAuthenticatedUsers` dwukropka nie mają, więc dostają własny człon: kontrakt niesie nazwy
    # projektów, dywizji i profili, a te dwa wpisy pokazałyby je całej organizacji albo internetowi.
    #
    # DLACZEGO osobno od kształtu adresu niżej, skoro tamten warunek odrzuciłby to samo: chodzi o KOMUNIKAT.
    # „to nie jest adres e-mail" nad wpisem `group:grp-...@example.com` czyta się jak błąd narzędzia — nikt
    # nie widzi w nim prefiksu, bo prefiks wygląda na część adresu.
    condition = alltrue([
      for g in var.contract_reader_groups :
      !strcontains(g, ":") && !contains(["allUsers", "allAuthenticatedUsers"], g)
    ])
    error_message = "contract_reader_groups przyjmuje SAM adres grupy (grp-...@example.com): bez prefiksu `group:`, bez user:/serviceAccount:/domain: i bez allUsers."
  }

  validation {
    # Kształt adresu. Bez tego literówka („grp-example-division-cloud" bez domeny) przechodzi plan i wraca
    # jako błąd API dopiero przy apply — u zespołu IAM, który nie wie, jaki adres miał tu być, bo prosił
    # o niego zespół z drugiej strony kontraktu. Taniej odrzucić to tutaj, komunikatem niosącym nazwę zmiennej.
    condition = alltrue([
      for g in var.contract_reader_groups :
      can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9][a-zA-Z0-9.-]*\\.[a-zA-Z]{2,}$", g))
    ])
    error_message = "contract_reader_groups: każdy wpis to adres e-mail grupy Google (np. grp-example-division-cloud@example.com)."
  }
}
