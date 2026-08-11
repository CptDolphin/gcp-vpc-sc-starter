# Wyjścia tego stacku to POLECENIA, nie dane. `terraform plan` nie rozstrzyga, czy sink realnie dostarcza
# wpisy: sink bez prawa zapisu jest w stanie `zdrowy` i dostarcza zero, a zero jest nieodróżnialne od
# czystego okna. Pytanie „czy to działa" musi mieć odpowiedź POZA Terraformem i musi być jedną komendą.

output "read_command" {
  description = "Odczyt dowodu z sinka — dokładnie to, co robi `violations-report.yml` (JEDNO wywołanie zamiast N per projekt)."
  value = join(" ", [
    "gcloud logging read '${local.sink_filter}'",
    "--project=${var.sink_project_id}",
    "--bucket=${var.bucket_id}",
    "--location=${var.bucket_location}",
    "--view=${var.bucket_id}",
    "--freshness=14d --format=json",
  ])
}

output "delivery_check" {
  description = "Czy sink DOSTARCZA. Pusty wynik przy niepustym odczycie per projekt = sink nie ma prawa zapisu albo filtr nie łapie; sam `sinks describe` tego NIE rozstrzyga."
  value       = "gcloud logging read '${local.sink_filter}' --project=${var.sink_project_id} --bucket=${var.bucket_id} --location=${var.bucket_location} --view=${var.bucket_id} --freshness=1h --format='value(insertId)' | wc -l"
}

output "writer_identity" {
  description = "Tożsamość, którą sink pisze do kubełka. Musi mieć `logging.bucketWriter` na kubełku docelowym — nadaje to ten stack, ale przy imporcie brownfield warto sprawdzić ręcznie."
  value       = google_logging_organization_sink.violations.writer_identity
}

output "view_name" {
  description = "Pełna nazwa widoku — jednostka, na której nadaje się dostęp do surowego strumienia odmów."
  value       = local.view_name
}
