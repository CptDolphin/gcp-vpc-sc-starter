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

output "config_view_name" {
  description = "Widok zmian konfiguracji granicy (ACM). To jest wejście alertu „konfiguracja zmieniona poza pipeline'em” — obserwator czyta ten widok, bo log-based metryka tego wpisu ZOBACZYĆ NIE MOŻE (leży w `_Required` organizacji, a metryki log-based istnieją tylko per projekt)."
  value       = "${local.bucket_name}/views/${local.config_view_name}"
}

output "network_view_name" {
  description = "Widok zdarzeń sterujących Compute (osobny kubełek). To jest wejście detektora okna „świeża sieć w członku egzekwowanym” — wartość wpisuje się do `violations_source.network_view` w `perimeter/alerting.yaml`. Puste, gdy `network_window_detector = false`."
  value       = var.network_window_detector ? local.network_view_name : ""
}

output "network_bucket_id" {
  description = "Nazwa kubełka zdarzeń sterujących Compute — wartość dla `violations_source.network_bucket`. Puste, gdy detektor wyłączony."
  value       = var.network_window_detector ? local.network_bucket_id : ""
}

output "network_delivery_check" {
  description = "Czy DRUGI sink dostarcza. Zwraca 0, dopóki nikt w organizacji nie utworzy sieci ani maszyny — a zero jest tu nieodróżnialne od braku prawa zapisu, więc potwierdza się to CZYNNIE: utwórz sieć w projekcie testowym i powtórz komendę. Sink, który nie dostarcza, wygląda dokładnie jak czyste okno."
  value = var.network_window_detector ? join(" ", [
    "gcloud logging read '${local.compute_sink_filter}'",
    "--project=${var.sink_project_id}",
    "--bucket=${local.network_bucket_id}",
    "--location=${var.bucket_location}",
    "--view=${local.network_bucket_id}",
    "--freshness=1h --format='value(protoPayload.methodName,protoPayload.resourceName)'",
  ]) : "detektor okna swiezej sieci WYLACZONY (network_window_detector = false)"
}

output "config_delivery_check" {
  description = "Czy sink dostarcza WPISY O ZMIANIE GRANICY. Zwraca 0 dopóki nikt nie tknie ACM — żeby to potwierdzić, zmień cokolwiek w granicy spoza pipeline'u i powtórz."
  value       = "gcloud logging read 'protoPayload.serviceName=\"accesscontextmanager.googleapis.com\"' --project=${var.sink_project_id} --bucket=${var.bucket_id} --location=${var.bucket_location} --view=${local.config_view_name} --freshness=1h --format='value(protoPayload.methodName)' | wc -l"
}
