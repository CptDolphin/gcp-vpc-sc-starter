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
    # Pusta nazwa environment w `attribute_condition` puli WIF dałaby warunek, który spełnia KAŻDY token z
    # tego repozytorium — w tym token z pull requesta. Cała bramka ludzkiego zatwierdzenia przestałaby istnieć.
    condition     = length(trimspace(var.apply_environment)) > 0
    error_message = "apply_environment nie może być puste — to ono odcina tokeny z pull requestów od konta apply."
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

  validation {
    # Wiodący `/` daje prefiks `//vpc-sc/...`, który nie pasuje do żadnego obiektu — warunek IAM przestaje
    # cokolwiek dopuszczać, a backend dostaje 403 przy pierwszym zapisie stanu.
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
  description = "Czy nadać kontu plan roles/logging.viewer na organizacji. Bez tego workflow violations-report nie odczyta naruszeń dry-run, a wtedy promocja do enforced opiera się na deklaracji zamiast na dowodzie."
  type        = bool
  default     = true
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
