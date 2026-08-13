# violations-sink — naruszenia VPC-SC z całej organizacji w jednym miejscu

Sink org-level, który zbiera **wszystkie** naruszenia VPC-SC (dry-run **i** egzekwowane) do jednego kubełka
logów w projekcie administracyjnym. `violations-report.yml` czyta go **jednym** zapytaniem.

**Applikuje człowiek** z org-level `roles/logging.configWriter`, nie pipeline perimetru — z tego samego
powodu, dla którego `iam-bootstrap` nie oddaje CI roli tworzącej sinki: para uprawnień „sink + kubełek”
jest ścieżką wyprowadzenia logów gdziekolwiek.

```
terraform init && terraform apply
```

## Po co — problem, który to usuwa

Wpis audytowy VPC-SC ląduje w logu **projektu-właściciela** chronionego zasobu, nie organizacji.
Zmierzone 2026-08-10 i powtórzone 2026-08-11:

| zakres odczytu | wpisów |
|---|---|
| `--organization=<ORG_ID>` | **0** |
| `--project=<członek A>` | **41** |
| `--project=<członek B>` | **24** |

Raport czytał więc **każdy projekt członkowski osobno**. Przy kilkuset projektach to kilkaset wywołań
`logging read` na przebieg — a jeden projekt bez uprawnień wywracał całość. To nie jest tylko wolne:
`violations.json` jest **dowodem** dla reguły `promotion_gate`, więc jego niekompletność przepuszcza
promocję, która nie powinna przejść.

## Dlaczego kubełek logów, a nie BigQuery

**Koszt nie rozstrzyga** — oba wychodzą 0 EUR przy tej skali (rachunek niżej). Rozstrzyga kształt danych
i powierzchnia awarii:

| kryterium | kubełek logów | BigQuery |
|---|---|---|
| kształt wejścia dla raportu | ten sam JSON, który parser już czyta | `protoPayload.metadata` → kolumna STRING `metadataJson`, trzeba odparsować z powrotem |
| zmiany w `violations_report.py` | **zero linii logiki** | nowa ścieżka parsowania na drodze DOWODU |
| fail-closed | kod wyjścia `gcloud logging read` — 1:1 jak dotąd | druga powierzchnia uprawnień (ACL datasetu) |
| jednostka dostępu | **widok** z własnym IAM (`logging.viewAccessor`) | ACL datasetu; per wiersz dopiero row-level security |
| trend / raport per dywizja bez skryptu | trzeba policzyć w raporcie (~40 linii, już istnieją i mają testy) | SQL |
| retencja | jedno pole, 1–3650 dni | wygasanie partycji |

Jedyną realną przewagą BigQuery jest trend — a tego nie wymaga żadne kryterium odbioru i wymagałby własnego
zadania (nowy artefakt = nowa bramka + decyzja). Kosztowałby za to re-parsowanie `metadataJson` i drugą
powierzchnię uprawnień **na ścieżce niosącej dowód promocji**. Stąd kubełek.

## Koszt — policzony, nie oszacowany

Ceny z **Cloud Billing Catalog API** (`cloudbilling.googleapis.com/v1/services/…/skus`, EUR, 2026-08-11),
nie z pamięci:

| SKU | cena |
|---|---|
| Log Storage cost | **0 EUR do 50 GiB/mies.**, powyżej 0,438900 EUR/GiB |
| Log Retention cost (powyżej 30 dni) | 0,008778 EUR/GiB-mies. |
| BigQuery Active Logical Storage | 0 EUR do 10 GiB/mies., powyżej 0,020189 EUR/GiB-mies. |
| BigQuery Analysis | 0 EUR do 1 TiB/mies., powyżej 6,58 EUR/TiB |

Zmierzony rozmiar wpisu na żywych danych: **3267 B** (średnia z 16 wpisów) ≈ 3,19 KiB.

* **Próg płatności:** 50 GiB ÷ 3,19 KiB = **~16,4 mln naruszeń miesięcznie** przed pierwszym centem.
  To ~6,3 naruszenia na sekundę nieprzerwanie w całej organizacji; przy takim ruchu problemem nie jest
  rachunek za logi.
* **Skala docelowa** (kilkaset projektów, +50/mies.), pesymistycznie 500 projektów × 1000 naruszeń/mies.
  = 500 tys. wpisów = **1,52 GiB/mies. = 3,0 % darmowego przydziału → 0 EUR.**
* **Retencja 30 dni = sufit darmowy.** Dlatego `retention_days = 30`, a nie „na wszelki wypadek 90”:
  trzyma odpowiedź „0 EUR” **dokładną**. Każde kolejne 30 dni retencji przy 1,52 GiB kosztowałoby
  0,013 EUR/mies. — pomijalne, ale to już nie jest zero, więc wymaga decyzji, nie odruchu.
* **Przydział 50 GiB liczy się per projekt**, a kubełek leży w projekcie administracyjnym, który poza tym
  prawie nic nie loguje — cały przydział jest realnie dostępny.

## Kto czyta — węziej niż raport, świadomie

Raport (`violations.md`/`violations.json`) mówi „członek X ma N naruszeń” i jest artefaktem CI: widzi go
każdy z dostępem do repozytorium. **Kubełek niesie surowe odmowy z całej organizacji** — tożsamości, metody,
nazwy zasobów po obu stronach granicy, tokeny troubleshootera. To jest mapa tego, kto próbuje sięgać gdzie,
łącznie z projektami, które członkami nie są. Dlatego:

| kto | co dostaje | czym |
|---|---|---|
| tożsamość sinka | zapis **do jednego kubełka** (warunek IAM), nic więcej | `logging.bucketWriter` + condition |
| konto raportu (`plan`) | odczyt **jednego widoku** | `logging.viewAccessor` na widoku |
| `violations_reader_principals` | odczyt tego samego widoku, imiennie | `logging.viewAccessor` na widoku |
| konto `apply` | **nic** — nie potrzebuje i nie dostaje | — |

**Świadomy brak:** `restricted_fields` (ukrycie `principalEmail`). Raport musi nazwać wołającego, żeby
właściciel dywizji wiedział, który workload przestanie działać po promocji; ukrycie tego pola zamieniłoby
dowód w statystykę.

**Dług DOMKNIĘTY:** `iam-bootstrap` nie daje już kontu `plan` org-level `roles/logging.viewer`. Raport
czyta widok (`roles/logging.viewAccessor`, nadawany niżej w tym stacku), a jedyne, czego potrzebuje ponad
to, jest odczyt **konfiguracji** sinka dla guarda „sink istnieje i ma ten sam filtr" — rola własna
`vpcScSinkReader` z JEDNYM uprawnieniem `logging.sinks.get`. Zakres pozostaje org-level, bo sink org-level
nie ma innego rodzica, ale `logging.logEntries.list` na organizacji zniknęło całkowicie.

Zapowiadana tu wcześniej przeszkoda (`logging.logMetrics.get` potrzebne `terraform plan` do odświeżenia
metryk z `terraform/monitoring.tf`) **przestała istnieć** przy okazji innej zmiany: metryki log-based
zostały z tamtego pliku usunięte, bo strukturalnie nie potrafią policzyć wpisów przyniesionych przez sink.
Stack perimetru nie zarządza dziś ani jedną `google_logging_metric`, więc podmiana na wąskie uprawnienie
w projekcie monitoringu okazała się niepotrzebna.

## Pułapki ZMIERZONE — nie odkrywaj ich ponownie

1. **Sink, który nie dostarcza, wygląda identycznie jak czyste okno.** Przy zakładaniu: zanim grant
   `logging.bucketWriter` dla tożsamości sinka się rozpropagował, **9 z 18 wpisów przepadło bezpowrotnie**
   (ponowny odczyt tego samego, zamkniętego okna 3 minuty później dał te same 9 braków), a
   `gcloud logging sinks describe` przez cały czas raportował sink jako zdrowy. Po utworzeniu albo zmianie
   sinka **potwierdź DOSTARCZANIE** (`terraform output delivery_check`), a okno obserwacji do promocji licz
   dopiero **od tego potwierdzenia**. Kontrolny przebieg po propagacji: 11/11 i 16/16 wpisów.
2. **Filtr widoku nie może powtórzyć filtra sinka.** `Error 400: Invalid view filter. View filters may only
   contain restrictions on log source, valid resource types, apphub fields, user-defined labels, or log ID` —
   `protoPayload.metadata."@type"` nie należy do żadnej z tych kategorii. Widok zawężamy przez
   `LOG_ID("cloudaudit.googleapis.com/policy")`.
3. **Lokalizacja kubełka podlega `constraints/gcp.resourceLocations`.** W organizacji z `in:eu-locations`
   wartość `global` pada na apply komunikatem o polityce, a nie o złej wartości pola.
4. **Odmowa EGZEKWOWANA nie ma pola `dryRun`** — jest tylko przy dry-run (`true`). Filtr `dryRun="false"`
   nie łapie **nigdy niczego**. Zmierzone na tych samych 25 wpisach: sam filtr po typie → 16 dry-run
   + 9 egzekwowanych; z `dryRun="false"` → 0.
5. **Odczyt logów członka sam generował naruszenie** (`logging.googleapis.com` jest w `restricted_services`,
   a pipeline woła spoza granicy) — narzędzie brudziło dowód, który zbiera, i po pierwszej promocji straciłoby
   do niego dostęp. Sink to usuwa: raport czyta kubełek w projekcie administracyjnym, który **członkiem nie
   jest**, więc odczyt nie przechodzi przez granicę i nie produkuje wpisów. Reguła `platform-violations-read`
   w `perimeter/policy.yaml` staje się przez to zbędna — jej zdjęcie to osobna zmiana w plikach perimetru.

## Drugi strumień: okno świeżej sieci (DEC-32)

Ten sam stack tworzy **drugi** sink org-level i **drugi** kubełek — na zdarzenia sterujące Compute
(`v1.compute.networks.insert`, `v1.compute.instances.insert`). Wyłącznik: `network_window_detector = false`.

**Po co.** Świeża sieć VPC w projekcie będącym członkiem konfiguracji **egzekwowanej** przez pierwsze
minuty nie jest dla perimetru „wewnątrz": maszyna w niej wychodzi poza granicę **bez odmowy i bez ani
jednego wpisu audytowego** (nic nie jest odrzucane, więc nie ma czego logować). Jedynym pewnym sygnałem
jest zdarzenie **sterujące**, a dla członka egzekwowanego jego log leży za granicą — musi go wynieść sink.

**Dlaczego OSOBNY kubełek, a nie trzeci widok tego samego.** Pułapka 2 niżej mówi, że filtr widoku wolno
oprzeć wyłącznie na źródle logu, typie zasobu, polach apphub, etykietach i identyfikatorze logu. Wpisy ACM
i wpisy Compute mają **ten sam** identyfikator logu (`activity`), a `protoPayload.methodName` nie jest
legalną restrykcją widoku — rozłączny widok w jednym kubełku musiałby więc zawęzić **działający** widok
`-config`, czyli jedyną detekcję edycji granicy w konsoli. Drugi kubełek daje rozłączność z konstrukcji.

**Koszt.** Darmowy przydział ingestu Cloud Logging to 50 GiB/projekt/miesiąc, a wpis audytowy waży ~3,3 KB
(zmierzone na tym kubełku) — czyli ~15 mln wpisów miesięcznie w cenie zero. Retencja ≤ 30 dni jest darmowa
niezależnie od wolumenu.

**Konsument.** `tools/perimeter_watch.py` publikuje z tego strumienia `network_inserts_enforced` (kontekst,
bez alertu) i `network_window_workload` (alert CRITICAL). Współrzędne wpisuje się do
`perimeter/alerting.yaml` → `violations_source.network_bucket` / `network_view`; biorą się z wyjść
`network_bucket_id` i `network_view_name`.

## Weryfikacja po apply

```
terraform output delivery_check          # ile wpisów naruszeń dotarło w ostatniej godzinie
terraform output read_command            # dokładnie to, co robi violations-report.yml
terraform output network_delivery_check  # czy DRUGI sink dostarcza (zero = też sprawdź czynnie, patrz pułapka 1)
```

Dowód równoważności (tak został wykonany): ustal okno, przeczytaj sink **oraz** każdy projekt osobno na tym
samym oknie i porównaj **zbiory `insertId`** — nie same liczby. Zmierzone 2026-08-11, okno 11m47s, 3 usługi,
2 projekty członkowskie: sink 16 wpisów w 1 zapytaniu = suma per projekt 16 wpisów w 3 zapytaniach, zbiory
identyczne, `brak = 0`, `nadmiar = 0`.
