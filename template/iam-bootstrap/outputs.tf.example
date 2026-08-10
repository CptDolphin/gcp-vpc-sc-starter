# Wyjścia tego stacku to NIE są dane do dalszego przetwarzania — to są zdania, które po apply mają dać
# operatorowi odpowiedź na pytania, na które sam Terraform odpowiedzieć nie umie.
#
# Powód istnienia tego pliku jest konkretny: `terraform plan` nie rozstrzyga, czy warstwa IAM Deny stoi.
# Odmowa odczytu i brak zasobu to w tym API ten sam `403`, więc plan pokazuje `1 to add` w obu wypadkach.
# Pytanie „czy guardrail istnieje” musi więc mieć odpowiedź POZA Terraformem — i musi być jednym
# poleceniem, bo procedura z czterech kroków jest procedurą, której nikt nie wykona w trakcie incydentu.

output "deny_policy_check" {
  description = "Jedno polecenie rozstrzygające, czy guardrail perimetru ISTNIEJE. Wymaga roli `vpcScDenyReader` (sekcja 5a main.tf) — bez niej odpowiedzią jest `403`, czyli brak odpowiedzi. Trzy wyniki: treść polityki = stoi; `NOT_FOUND` = NIE MA; `PERMISSION_DENIED` = nie wiesz i nie wolno tego raportować jako „nie ma”."
  value       = "gcloud iam policies get ${local.deny_policy_name} --attachment-point=cloudresourcemanager.googleapis.com/organizations/${var.org_id} --kind=denypolicies"
}

output "deny_policy_managed_here" {
  description = "Czy warstwa deny jest własnością TEGO stacku (`manage_deny_policy`). `false` znaczy, że guardrail — o ile istnieje — powstał poza tym repozytorium i `terraform plan` nic o nim nie powie; wtedy jedynym źródłem prawdy jest polecenie z `deny_policy_check`."
  value       = var.manage_deny_policy
}

output "deny_reader_role_id" {
  description = "Pełne ID roli własnej do odczytu warstwy deny — do nadania kolejnym osobom bez wchodzenia w ten stack (`gcloud organizations add-iam-policy-binding <ORG_ID> --member=… --role=<ta wartość>`)."
  value       = google_organization_iam_custom_role.deny_reader.id
}
