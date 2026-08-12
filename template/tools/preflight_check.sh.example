#!/usr/bin/env bash
# Pre-flight: czy projekt członka JEST GOTOWY na wejście do perimetru. Wyłącznie odczyt — ten skrypt
# niczego nie naprawia (granica własności, DEC-5: naprawia właściciel projektu, nie repo perimetru).
#
# Każdy check zamyka konkretny tryb awarii:
#   1. projekt istnieje, jest ACTIVE i numer zgadza się z ID → literówka w numerze dodałaby do perimetru
#      CUDZY projekt, a projekt w trakcie kasowania (soft-delete, 30 dni) wnosi do niego MARTWY NUMER
#   2. projekt nie jest w innej konfiguracji EGZEKWOWANEJ → twarde ograniczenie ACM; apply padłby po review
#   3. podsieci mają Private Google Access        → bez tego ruch do API nie pójdzie przez restricted VIP
#   4. strefa DNS kieruje googleapis.com na restricted VIP → jw., najczęstsza cicha awaria onboardingu
#   5. (ostrzeżenie) istnieją już endpointy Vertex → endpoint utworzony PRZED wejściem do perimetru
#      sprawia, że późniejszy deploy modelu na niego zawodzi; to nie blokuje PR-a, ale musi być powiedziane
#   6. konta serwisowe z reguł ISTNIEJĄ → ACM waliduje tożsamości po swojej stronie i odrzuca CAŁĄ zmianę
#      komunikatem `invalid or non-existent`, czyli literówka wywraca apply po review, na obiekcie org-plane
#
# TRZY WERDYKTY, NIE DWA. Check może stwierdzić, że wymóg jest spełniony (OK), że jest złamany (BŁĄD)
# albo że **nie dotyczy tego projektu** (N/D). Czwartego stanu — „nie udało się sprawdzić" — nie zamiatamy
# pod OK: nieodczytany check jest raportowany jako BŁĄD z powodem. Pre-flight, który mówi „OK" o czymś,
# czego nie odczytał, jest gorszy od braku pre-flightu, bo produkuje fałszywe poczucie sprawdzenia.
#
# DLACZEGO checki 3 i 4 są WARUNKOWE (N/D na projekcie bez sieci). VPC-SC działa na płaszczyźnie API —
# członkostwo w perimetrze nie wymaga ani jednej maszyny ani sieci VPC. Private Google Access i prywatna
# strefa DNS opisują wyłącznie to, jak ruch Z WNĘTRZA sieci projektu trafia do googleapis.com; w projekcie,
# który sieci nie ma, nie ma czego routować i wymóg jest bezprzedmiotowy. Twardy wymóg „zawsze" kazałby
# poprawnemu kandydatowi zbudować sieć, której nie potrzebuje, a — co gorsze — zamieniłby check w alarm
# odpalający się przy każdym onboardingu. Odruchową reakcją na check, który zawsze krzyczy, jest
# `--warn-only`, czyli wyciszenie RÓWNIEŻ tego przypadku, w którym PGA naprawdę brakuje. Check, który
# woła „wilk", rozbraja sam siebie.
#
# Uprawnienia (read-only): cloudasset.viewer, compute.networkViewer, dns.reader, iam.serviceAccountViewer
# — docs/2-uprawnienia-i-wif.md
set -euo pipefail

# DLACZEGO to jest pierwsza linijka kodu, a nie szczegół. gcloud, natrafiając na wyłączone API, proponuje
# JEGO WŁĄCZENIE: „API [...] not enabled on project [...]. Would you like to enable and retry? (y/N)".
# Pytanie idzie na **stderr**, a checki niżej stderr przechwytują — więc na terminalu skrypt po prostu
# stawałby w miejscu bez widocznego powodu, a odpowiedź „y" WŁĄCZYŁABY usługę w CUDZYM projekcie.
# Narzędzie deklarowane jako wyłącznie odczytowe (DEC-5) nie ma prawa niczego proponować.
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

PROJECT_ID=""
PROJECT_NUMBER=""
VERTEX_REGION="europe-west4"
STRICT=1
IDENTITIES=()

uzycie() {
  cat >&2 <<'POMOC'
użycie: preflight_check.sh --project <id> --number <numer> [--identity <spec>]… [--region <region>] [--warn-only]

  --project   ID projektu kandydata
  --number    numer projektu — MUSI zgadzać się z ID (check 1)
  --identity  tożsamość w formacie ACM (`serviceAccount:…`, `user:…`, `group:…`), powtarzalna
  --region    region, w którym szukamy endpointów Vertex (domyślnie europe-west4)
  --warn-only kod wyjścia 0 mimo błędów; NIE zmienia werdyktu, tylko go nie egzekwuje
POMOC
  exit "${1:-2}"
}

# Flaga bez wartości była wcześniej cichym `exit 1` bez jednego słowa wyjaśnienia (`shift` na pustej
# liście + `set -e`) — czyli błąd użycia nieodróżnialny od niezaliczonego checku.
wymagaj_wartosci() {
  [ "$2" -gt 0 ] || { echo "flaga $1 wymaga wartości" >&2; uzycie; }
}

while [ $# -gt 0 ]; do
  case "$1" in
    --project)  wymagaj_wartosci "$1" $(($# - 1)); PROJECT_ID="$2";     shift 2 ;;
    --number)   wymagaj_wartosci "$1" $(($# - 1)); PROJECT_NUMBER="$2"; shift 2 ;;
    # Wartość w formacie ACM — dokładnie tak, jak stoi w pliku członka, żeby nie trzeba było jej po drodze
    # przepisywać (przepisywanie to kolejna literówka).
    --identity) wymagaj_wartosci "$1" $(($# - 1)); IDENTITIES+=("$2");  shift 2 ;;
    --region)   wymagaj_wartosci "$1" $(($# - 1)); VERTEX_REGION="$2";  shift 2 ;;
    --warn-only) STRICT=0; shift ;;
    -h|--help)  uzycie 0 ;;
    *) echo "nieznany argument: $1" >&2; uzycie ;;
  esac
done
[ -n "$PROJECT_ID" ] && [ -n "$PROJECT_NUMBER" ] || uzycie

fail=0
nd=0
note()    { printf '  %s  %s\n' "$1" "$2"; }
ok()      { note "OK   " "$1"; }
uwaga()   { note "UWAGA" "$1"; }
problem() { note "BŁĄD " "$1"; fail=$((fail + 1)); }
nie_dotyczy() { note "N/D  " "$1"; nd=$((nd + 1)); }

# Uruchamia gcloud zachowując stdout, stderr i kod wyjścia ROZDZIELNIE. Poprzednia wersja wszystkich
# checków wołała `gcloud … 2>/dev/null` i wnioskowała z samej treści stdout — a stdout nieudanego
# wywołania jest pusty, więc „nie udało się zapytać" wyglądało identycznie jak „zapytałem i nic nie ma".
GOUT=""; GERR=""; GRC=0
g() {
  local plik
  plik="$(mktemp "${TMPDIR:-/tmp}/preflight.XXXXXX")"
  set +e
  GOUT="$(gcloud "$@" 2>"$plik")"
  GRC=$?
  set -e
  GERR="$(tr '\n' ' ' < "$plik" | cut -c1-240)"
  rm -f "$plik"
}

# Wyłączone API zwraca PERMISSION_DENIED — TEN SAM kod, którym odpowiada odmowa VPC-SC. Rozstrzyga
# wyłącznie treść komunikatu, nigdy kod błędu; wnioskowanie z kodu jest tu udokumentowaną pomyłką.
api_wylaczone() {
  case "$GERR" in
    *"has not been used in project"*|*"SERVICE_DISABLED"*|*"not enabled on project"*|*"API is not enabled"*) return 0 ;;
    *) return 1 ;;
  esac
}

echo "pre-flight: $PROJECT_ID ($PROJECT_NUMBER)"

# 1. projekt ISTNIEJE, JEST ŻYWY i numer się zgadza — trzy pytania, JEDEN odczyt.
#
# `lifecycleState` NIE JEST OZDOBĄ, tylko jedynym sygnałem odróżniającym projekt żywy od skasowanego.
# ZMIERZONE: `gcloud projects delete` to soft-delete z oknem 30 dni, a przez te 30 dni `projects describe`
# odpowiada NORMALNIE i zwraca numer — tyle że z `lifecycleState: DELETE_REQUESTED`. Check pytający o sam
# `projectNumber` mówił więc „projekt istnieje, numer zgodny" o projekcie, który jest w drodze do kasowania.
# To jest najgorszy możliwy werdykt pre-flightu: cicho POZYTYWNY. Wpis wchodzi do perimetru, projekt znika,
# a numer zostaje jako martwy — i nie da się go potem dopasować do niczego w diffie.
#
# ZMIERZONE PO DRUGIEJ STRONIE (co robi API, gdy numer już nie wskazuje na projekt tej organizacji):
# ACM odrzuca taką zmianę dopiero przy `apply` na gałęzi domyślnej — czyli PO review, na obiekcie
# org-level — i robi to DWOMA różnymi komunikatami z jednego wywołania:
#     Error 400: Invalid resources for Service Perimeter '<perimetr>': Project(s), folder(s), or
#     parent(s) of 'projects/<numer>', are not members of the parent of the Service Perimeter.
#     Error 400: com.google.apps.framework.request.NotFoundException: Project, projects/<numer>,
#     does not exist.
# Pierwszy pochodzi z zapisu CZŁONKOSTWA i brzmi jak problem z przynależnością organizacyjną; drugi
# z zapisu REGUŁY i mówi wprost „nie istnieje". Oba to `Error 400`. Kod błędu nie rozstrzyga niczego —
# i dokładnie ten koszt ten check ma zdjąć z recenzenta.
#
# CZWARTY STAN RAPORTUJEMY DOSŁOWNIE, ZAMIAST ZGADYWAĆ. `projects describe` na projekcie, którego nie ma,
# i na projekcie, do którego wołający nie ma dostępu, odpowiada TAK SAMO — Resource Manager sam tych dwóch
# przypadków nie rozróżnia. Nie udajemy więc, że rozróżniamy: wypisujemy treść odpowiedzi (tak jak checki
# 2–4) i mówimy wprost, kto to rozstrzygnie. Pre-flight, który wybiera jedną z dwóch możliwości i podaje ją
# jako fakt, wysyła recenzenta w złą stronę — a „brak uprawnień" i „projektu nie ma" naprawia kto inny.
g projects describe "$PROJECT_ID" --format='value(projectNumber,lifecycleState)'
if [ "$GRC" -ne 0 ] || [ -z "$GOUT" ]; then
  problem "projekt $PROJECT_ID: odczyt nie powiódł się — projekt NIE ISTNIEJE albo brak dostępu odczytu (Resource Manager nie rozróżnia tych dwóch; rozstrzygnie ktoś z dostępem do organizacji): $GERR"
else
  # awk, nie `cut`: `cut -f2` na linii bez tabulatora zwraca CAŁĄ linię, więc brakujące pole udawałoby
  # odczytany stan. awk daje pusty łańcuch i pusty łańcuch jest tu osobnym, jawnie obsłużonym werdyktem.
  numer_realny="$(printf '%s' "$GOUT" | awk -F'\t' '{print $1}')"
  stan_projektu="$(printf '%s' "$GOUT" | awk -F'\t' '{print $2}')"
  if [ "$numer_realny" != "$PROJECT_NUMBER" ]; then
    problem "numer projektu nie zgadza się: deklarowany $PROJECT_NUMBER, realny $numer_realny"
  elif [ -z "$stan_projektu" ]; then
    # Nieodczytany stan NIE JEST stanem ACTIVE. Ta gałąź istnieje, bo `--format` bez pola albo zmiana
    # w API dałaby puste pole, a wtedy „nie wiem" wpadłoby cicho do gałęzi pozytywnej — czyli dokładnie
    # ten defekt, który ten check naprawia, wróciłby inną drogą.
    problem "projekt $PROJECT_ID: nie odczytałem lifecycleState — nie wiem, czy projekt jest żywy, a nieodczytanego stanu nie zamiatam pod OK"
  elif [ "$stan_projektu" != "ACTIVE" ]; then
    problem "projekt $PROJECT_ID jest w stanie $stan_projektu, nie ACTIVE — to projekt SKASOWANY (soft-delete, okno 30 dni). Numer zostanie w perimetrze jako martwy; powrót wyłącznie przez gcloud projects undelete, który NIE przywraca konta rozliczeniowego"
  else
    ok "projekt istnieje, jest ACTIVE, numer zgodny"
  fi
fi

# 2. kolizja perimetrów — projekt może należeć tylko do JEDNEJ konfiguracji EGZEKWOWANEJ.
#
# Konfiguracja dry-run (`spec`) i egzekwowana (`status`) to dwie różne rzeczy i mylenie ich kosztuje
# dwa razy: obecność w cudzym `status` BLOKUJE onboarding (twarde ograniczenie ACM), a obecność we
# WŁASNYM `spec` jest normalnym, zamierzonym etapem dwustopniowego wejścia. Poprzednia wersja szukała
# numeru `grep`em w surowym JSON-ie całej listy, więc nie odróżniała ani jednego od drugiego, ani nawet
# tego, w KTÓRYM perimetrze projekt siedzi — i mówiła „sprawdź, czy to NASZ perimetr", nie podając nazwy.
# SEPARATOR JEST WYPISANY JAWNIE I TO NIE JEST KOSMETYKA — ZMIERZONE NA ŻYWEJ ORGANIZACJI.
# `list()` bez argumentu skleja elementy PRZECINKIEM, a awk niżej rozcinał pole po ŚREDNIKU. Skutek:
# porównanie trafiało wyłącznie wtedy, gdy konfiguracja miała DOKŁADNIE JEDEN zasób — przy dwóch i więcej
# `zawiera()` porównywało cały sklejony łańcuch z pojedynczym `projects/<numer>` i nie trafiało NIGDY.
# Zmierzone na perimetrze z trzema członkami: projekt BĘDĄCY w konfiguracji dry-run dostawał werdykt
# „brak kolizji — projektu nie ma w żadnej konfiguracji". Groźniejsza połowa tego samego defektu dotyczy
# konfiguracji EGZEKWOWANEJ: check istnieje po to, żeby złapać projekt siedzący w cudzym `status`
# (twarde ograniczenie ACM, apply pada po review) — i przy każdym realnym rozmiarze perimetru milczał.
# Test w selfteście używał JEDNEGO zasobu w atrapie, więc zieleniał na jedynym przypadku, który działał.
g access-context-manager perimeters list \
  --format='value(name,status.resources.list(separator=";"),spec.resources.list(separator=";"))'
if [ "$GRC" -ne 0 ]; then
  problem "nie zweryfikowano kolizji perimetrów (odczyt listy nie powiódł się): $GERR"
else
  # awk z jawnym FS='\t' — `read` z IFS=$'\t' ZWIJA sąsiadujące taby (tab jest znakiem białym w IFS),
  # więc perimetr z pustą konfiguracją egzekwowaną przesuwałby kolumny i członek dry-run byłby
  # raportowany jako EGZEKWOWANY. Zmierzone; to nie jest hipotetyczne.
  kolizja="$(printf '%s\n' "$GOUT" | awk -F'\t' -v cel="projects/$PROJECT_NUMBER" '
    function zawiera(pole,   i, n, a) {
      n = split(pole, a, ";")
      for (i = 1; i <= n; i++) { gsub(/^[ \t]+|[ \t]+$/, "", a[i]); if (a[i] == cel) return 1 }
      return 0
    }
    NF == 0 { next }
    zawiera($2) { print "ENFORCED\t" $1; next }
    zawiera($3) { print "DRYRUN\t" $1 }
  ')"
  zbadane="$(printf '%s' "$GOUT" | grep -c . || true)"
  enforced="$(printf '%s\n' "$kolizja" | awk -F'\t' '$1=="ENFORCED"{print $2}' | tr '\n' ' ')"
  dryrun="$(printf '%s\n' "$kolizja" | awk -F'\t' '$1=="DRYRUN"{print $2}' | tr '\n' ' ')"
  if [ -n "${enforced// /}" ]; then
    problem "projekt jest już w EGZEKWOWANEJ konfiguracji perimetru: ${enforced% } → ACM nie dopuszcza drugiej"
  elif [ -n "${dryrun// /}" ]; then
    uwaga "projekt jest w konfiguracji DRY-RUN perimetru: ${dryrun% } → to etap onboardingu, nie kolizja; potwierdź, że to ten perimetr"
  else
    ok "brak kolizji — projektu nie ma w żadnej konfiguracji (zbadano perimetrów: $zbadane)"
  fi
fi

# Jedno pytanie, na którym wiszą checki 3 i 4: czy w tym projekcie JEST co routować do googleapis.com.
# Pytamy raz, bo dwa niezależne odczyty mogłyby dać dwie różne odpowiedzi na to samo pytanie — a to
# dokładnie ten rozjazd, który sprawiał, że check 3 mówił OK, a check 4 BŁĄD o tym samym projekcie.
SIEC="nieznane"; SIEC_POWOD=""
g compute networks list --project="$PROJECT_ID" --format='value(name)'
if [ "$GRC" -eq 0 ] && [ -n "$GOUT" ]; then
  SIEC="jest"
elif [ "$GRC" -eq 0 ]; then
  SIEC="brak"; SIEC_POWOD="projekt nie ma ani jednej sieci VPC"
elif api_wylaczone; then
  # To jest ODPOWIEDŹ, nie brak odpowiedzi: sieci VPC nie da się utworzyć przy wyłączonym Compute API.
  SIEC="brak"; SIEC_POWOD="Compute API wyłączone — sieci VPC w projekcie nie ma"
else
  SIEC_POWOD="$GERR"
fi

# 3. Private Google Access na podsieciach
case "$SIEC" in
  brak)
    nie_dotyczy "Private Google Access nie dotyczy — $SIEC_POWOD" ;;
  nieznane)
    problem "nie zweryfikowano Private Google Access (nie wiadomo, czy projekt ma sieć): $SIEC_POWOD" ;;
  *)
    g compute networks subnets list --project="$PROJECT_ID" --format='value(name,privateIpGoogleAccess)'
    if [ "$GRC" -ne 0 ]; then
      problem "nie zweryfikowano Private Google Access (odczyt podsieci nie powiódł się): $GERR"
    elif [ -z "$GOUT" ]; then
      nie_dotyczy "Private Google Access nie dotyczy — sieć istnieje, ale nie ma w niej ani jednej podsieci"
    else
      bez_pga="$(printf '%s\n' "$GOUT" | awk -F'\t' '$2=="False"{print $1}' | tr '\n' ' ')"
      if [ -n "${bez_pga// /}" ]; then
        problem "podsieci bez Private Google Access: ${bez_pga% }"
      else
        ok "Private Google Access włączony na wszystkich podsieciach"
      fi
    fi ;;
esac

# 4. DNS na restricted VIP (199.36.153.4/30) — jeden odczyt stref obsługuje też 4b.
#
# 4b: Workbench z własnymi kernelami wymaga private.googleapis.com (199.36.153.8/30) dla
#     *.notebooks.googleusercontent.com — jedyny wyjątek od reguły „wszystko przez restricted".
case "$SIEC" in
  brak)
    nie_dotyczy "prywatna strefa DNS na restricted VIP nie dotyczy — $SIEC_POWOD" ;;
  nieznane)
    problem "nie zweryfikowano stref DNS (nie wiadomo, czy projekt ma sieć): $SIEC_POWOD" ;;
  *)
    g dns managed-zones list --project="$PROJECT_ID" --format='value(dnsName)'
    if [ "$GRC" -ne 0 ]; then
      problem "nie zweryfikowano stref DNS (odczyt nie powiódł się): $GERR"
    else
      if printf '%s\n' "$GOUT" | grep -q 'googleapis\.com'; then
        ok "istnieje prywatna strefa dla googleapis.com"
      else
        problem "brak prywatnej strefy DNS dla googleapis.com → ruch do API nie pójdzie przez restricted VIP"
      fi
      if printf '%s\n' "$GOUT" | grep -q 'notebooks\.googleusercontent\.com'; then
        ok "strefa dla notebooks.googleusercontent.com obecna (Workbench)"
      else
        uwaga "brak strefy notebooks.googleusercontent.com → Workbench z własnym kernelem nie wstanie"
      fi
    fi ;;
esac

# 5. kolejność tworzenia endpointów Vertex (ostrzeżenie, nie blokada)
#
# Region jest parametrem i jest WYPISYWANY. Wcześniej był zaszyty na sztywno i check milczał zawsze —
# i gdy endpointów nie było, i gdy były w innym regionie, i gdy odczyt padł. Check, który w komplecie
# przypadków nie mówi nic, jest nieodróżnialny od checku, którego nie ma.
g ai endpoints list --project="$PROJECT_ID" --region="$VERTEX_REGION" --format='value(name)'
if [ "$GRC" -ne 0 ]; then
  if api_wylaczone; then
    nie_dotyczy "Vertex AI API wyłączone → endpointów sprzed wejścia do perimetru nie ma"
  else
    uwaga "nie zweryfikowano endpointów Vertex w regionie $VERTEX_REGION: $GERR"
  fi
elif [ -n "$GOUT" ]; then
  uwaga "istnieją endpointy Vertex ($VERTEX_REGION) sprzed wejścia do perimetru — deploy modelu na nie zawiedzie; odtwórz je po dołączeniu"
else
  ok "brak endpointów Vertex sprzed wejścia do perimetru (sprawdzony region: $VERTEX_REGION)"
fi

# 6. tożsamości z reguł istnieją
#
# DLACZEGO tutaj, a nie wyłącznie w bramce OPA: `perimeter.rego` sprawdza KSZTAŁT adresu na plan-JSON i robi
# to na każdym PR bez żadnych poświadczeń — ale adres poprawny składniowo i wskazujący na nieistniejące konto
# przechodzi tam bez zająknięcia. ACM odrzuca go dopiero przy apply, komunikatem `invalid or non-existent`,
# i wywraca CAŁĄ zmianę, nie jedną regułę. Ten check wymaga poświadczeń, więc żyje w pre-flighcie recenzenta.
for spec in ${IDENTITIES+"${IDENTITIES[@]}"}; do
  case "$spec" in
    serviceAccount:*)
      sa="${spec#serviceAccount:}"
      g iam service-accounts describe "$sa" --format='value(email)'
      if [ "$GRC" -eq 0 ]; then
        ok "konto serwisowe istnieje: $sa"
      else
        problem "konto serwisowe NIE ISTNIEJE albo brak dostępu odczytu: $sa → ACM odrzuci apply"
      fi
      ;;
    user:*|group:*)
      # Świadomie bez werdyktu: istnienia użytkownika i grupy nie da się potwierdzić uprawnieniami GCP —
      # to Directory API Workspace, czyli inna domena administracyjna i inne poświadczenia. Bramka, która
      # udawałaby, że sprawdza, byłaby gorsza od jawnego „nie wiem".
      uwaga "nie weryfikuję z GCP: $spec (Workspace Directory API) — ACM sprawdzi przy apply"
      ;;
    *)
      problem "tożsamość bez znanego prefiksu typu: $spec (oczekiwane serviceAccount:/user:/group:)"
      ;;
  esac
done

if [ "$nd" -gt 0 ]; then
  echo "  (checków nie dotyczących tego projektu: $nd — patrz N/D wyżej)"
fi

if [ "$fail" -gt 0 ]; then
  # `--warn-only` zmienia WYŁĄCZNIE kod wyjścia. Werdykt zostaje ten sam: poprzednia wersja kończyła się
  # słowem „zaliczony" mimo błędów, czyli linią, którą czyta się w logu CI i w podsumowaniu recenzenta.
  echo "pre-flight NIEZALICZONY ($fail błędów) — naprawia właściciel projektu, nie repo perimetru" >&2
  if [ "$STRICT" -eq 1 ]; then
    exit 1
  fi
  echo "kod wyjścia 0 na żądanie (--warn-only) — werdykt powyżej NIE zmienia się" >&2
  exit 0
fi
echo "pre-flight zaliczony"
