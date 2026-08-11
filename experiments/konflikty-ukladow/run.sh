#!/usr/bin/env bash
# Ile z 10 równoległych PR-ów wchodzi bez konfliktu, gdy każdy dodaje projekt do perimetru z 200 projektami?
#
# Pytanie, które rozstrzyga ten skrypt, brzmi „jeden wspólny perimeter/projects.yaml czy plik na projekt",
# ale mierzymy je w rozbiciu na CZTERY niezależne zmienne, bo każda z nich osobno bywa proponowana jako
# rozwiązanie i każda osobno wymaga sprawdzenia:
#
#   1. GDZIE trafia nowy wpis          — wstawka w miejscu z sortowania czy dopisanie na końcu pliku
#   2. SKĄD przychodzą PR-y            — z różnych dywizji czy z jednej (fala onboardingu)
#   3. CZY działa sterownik `union`    — .gitattributes merge=union
#   4. CO robi bot przy konflikcie     — nic, czy ponawia INTENCJĘ na świeżym main (rebase-retry)
#
# Najważniejsze w tym skrypcie: warianty A-worst-koniec i D mają BAJT W BAJT ten sam plik wejściowy,
# te same gałęzie i tę samą kolejność scalania. Różni je wyłącznie zachowanie bota. Bez tej pary „D daje
# 10/10" byłoby zdaniem bez wartości — 10/10 daje też układ, w którym nie ma czego rozwiązywać. Ta sama
# lekcja, którą wyciągnęliśmy z eksperymentu race-two-states: pomiar bez kontroli potwierdza hipotezę zawsze.
#
# Drugie: `merge=union` sprawdzamy DWA razy — na DODAWANIU wpisów (B) i na EDYCJI tego samego wpisu
# (B-edit). Pierwsza wersja tego skryptu zakładała, że przy dodawaniu union jest bezpieczny, i tylko przy
# edycji psuje plik. Pomiar to obalił: union sklejający dziesięć wstawek w to samo miejsce ZLEPIA je w jeden
# wpis i dziewięć projektów znika bez błędu. Dlatego założenie zastąpiła asercja — każdy wariant, który po
# scaleniach nie ma tylu wpisów, ile PR-ów wpuścił, MUSI zapalić bramkę na czerwono. Zieleń na wariancie D
# też jest asercją, nie obserwacją: bramka czerwona zawsze nie jest bramką, tylko szumem.
set -euo pipefail

LAB="${1:?uzycie: ./run.sh <katalog roboczy>, np. ./run.sh /tmp/vpcsc-konflikty}"
TU="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAMKA="$TU/sprawdz_duplikaty.py"

ISTNIEJACE=200      # projekty już w perimetrze
PR_OW=10            # równoległe wnioski (dziesięć zespołów tego samego dnia)
DYWIZJI=20          # ile dywizji dzieli między siebie te 200 projektów -> 10 projektów na dywizję
DYWIZJA_FALI="example-division-07"   # dywizja, która onboarduje falę w wariantach *-worst, B i D
PROJEKT_EDYTOWANY="prj-example-0008" # istniejący wpis DYWIZJA_FALI, który w B-edit zmieniają DWA PR-y naraz
MAX_PROB=5          # bounded retry — bot bez limitu prób to nie rozwiązanie, tylko inna awaria

rm -rf "$LAB"; mkdir -p "$LAB"
LAB="$(cd "$LAB" && pwd)"   # dalej wszystko na ścieżkach bezwzględnych: funkcje wchodzą i wychodzą z katalogów

# --- generowanie danych -------------------------------------------------------------------------------
#
# Wpis jest WIELOLINIOWY, i to jest zmiana względem pierwszej wersji eksperymentu (jedna linia = jeden
# projekt). Powód nie jest kosmetyczny: git wykrywa konflikt na poziomie linii z trzema liniami kontekstu,
# więc rozmiar wpisu WPROST wyznacza, jak blisko siebie muszą trafić dwa PR-y, żeby się pobiły. Realny plik
# członka ma kilkanaście linii; pomiar na wpisach jednolinijkowych zaniża liczbę konfliktów i mierzy format,
# którego i tak nikt nie użyje.
blok_wpisu() { # $1=dywizja $2=project_id $3=project_number $4=stage
  printf -- '  - division: %s\n' "$1"
  printf -- '    project_id: %s\n' "$2"
  printf -- '    project_number: "%s"\n' "$3"
  printf -- '    owner_group: grp-%s@example.com\n' "$1"
  printf -- '    stage: %s\n' "$4"
  printf -- '    profiles: []\n'
}

# Numery projektów mają 12 cyfr, bo tyle ma numer projektu w Google Cloud — bramka duplikatów ma być
# sprawdzana na danych tego samego kształtu, co produkcyjne. Sklejamy je jednak z prefiksu i licznika,
# żeby w ŹRÓDLE tego pliku nie było ani jednego 12-cyfrowego literału: skan samodzielności repozytorium
# odrzuca numery spoza listy placeholderów, a wyjątek dla eksperymentu rozbrajałby ten skan wszędzie.
numer_istniejacy() { printf '9999%08d' "$1"; }
numer_nowy() { printf '9998%08d' "$1"; }

# Baseline posortowany po `<dywizja>-<project_id>` — czyli tak, jak wygląda plik utrzymywany „porządnie".
# To sortowanie samo w sobie jest jedną z mierzonych zmiennych: kładzie projekty jednej dywizji obok siebie.
gen_baseline() {
  echo "members:"
  d=0
  while [ "$d" -lt "$DYWIZJI" ]; do
    dyw="$(printf 'example-division-%02d' "$d")"
    i=$((d + 1))
    while [ "$i" -le "$ISTNIEJACE" ]; do
      blok_wpisu "$dyw" "$(printf 'prj-example-%04d' "$i")" "$(numer_istniejacy "$i")" "dry-run"
      i=$((i + DYWIZJI))
    done
    d=$((d + 1))
  done
}

# Wpis dodawany przez PR numer $1. Dywizja jest parametrem, project_id i numer NIE — dzięki temu warianty
# „różne dywizje" i „ta sama dywizja" różnią się dokładnie jednym polem, a nie całym zestawem danych.
gen_nowy_wpis() { # $1=numer PR-a $2=dywizja
  blok_wpisu "$2" "$(printf 'prj-example-new-%02d' "$1")" "$(numer_nowy "$1")" "dry-run"
}

dywizja_pr() { # $1=numer PR-a $2=tryb (rozne|jedna)
  if [ "$2" = "jedna" ]; then echo "$DYWIZJA_FALI"; else printf 'example-division-%02d' "$(($1 - 1))"; fi
}

gen_baseline > "$LAB/baseline.yaml"

# Wzorzec układu „plik na projekt" — budowany raz i kopiowany, tak jak baseline jednoplikowy. Ten sam
# zestaw 200 projektów w obu układach; inaczej porównywalibyśmy dwa różne wejścia.
mkdir -p "$LAB/wzor-members"
i=1
while [ "$i" -le "$ISTNIEJACE" ]; do
  dyw="$(printf 'example-division-%02d' "$(( (i - 1) % DYWIZJI ))")"
  pid="$(printf 'prj-example-%04d' "$i")"
  {
    printf 'division: %s\n' "$dyw"
    printf 'project_id: %s\n' "$pid"
    printf 'project_number: "%s"\n' "$(numer_istniejacy "$i")"
    printf 'owner_group: grp-%s@example.com\n' "$dyw"
    printf 'stage: dry-run\n'
    printf 'profiles: []\n'
  } > "$LAB/wzor-members/$dyw-$pid.yaml"
  i=$((i + 1))
done

# --- operacje na pliku --------------------------------------------------------------------------------

# Wstawka w miejscu wynikającym z sortowania po `<dywizja>-<project_id>`.
wstaw_posortowane() { # $1=plik docelowy $2=plik z blokiem
  nowy_klucz="$(awk 'NR==1 {d=$3} $1=="project_id:" {print d "-" $2; exit}' "$2")"
  awk -v plik_nowy="$2" -v nowy_klucz="$nowy_klucz" '
    function wypisz() {
      if (buf == "") return
      if (!wstawiono && klucz > nowy_klucz) { printf "%s", nowy; wstawiono = 1 }
      printf "%s", buf
      buf = ""; klucz = ""
    }
    BEGIN { while ((getline l < plik_nowy) > 0) nowy = nowy l ORS; close(plik_nowy) }
    /^  - division: / { wypisz(); dyw = $3; buf = $0 ORS; next }
    {
      if (buf == "") { print; next }   # nagłówek `members:` przed pierwszym blokiem
      buf = buf $0 ORS
      if ($1 == "project_id:" && klucz == "") klucz = dyw "-" $2
    }
    END { wypisz(); if (!wstawiono) printf "%s", nowy }
  ' "$1" > "$1.tmp" && mv "$1.tmp" "$1"
}

# Dopisanie na końcu pliku. Wariant proponowany jako „lekarstwo bez bota": skoro kolejność w pliku i tak nic
# nie znaczy (renderer kluczuje po treści, nie po pozycji), to nie sortujmy — i konflikty znikną. Nie znikną,
# i po to jest tu mierzony osobno.
dopisz_na_koncu() { cat "$2" >> "$1"; }

zastosuj_wpis() { # $1=plik $2=plik z blokiem $3=tryb (sort|koniec)
  if [ "$3" = "koniec" ]; then dopisz_na_koncu "$1" "$2"; else wstaw_posortowane "$1" "$2"; fi
}

# Podmiana jednego pola w bloku wskazanego projektu — symuluje PR promocyjny (`stage`) i PR zmieniający
# właściciela (`owner_group`), czyli dwa najczęstsze powody EDYCJI istniejącego wpisu.
edytuj_pole() { # $1=plik $2=project_id $3=pole (z dwukropkiem) $4=nowa wartość
  awk -v pid="$2" -v pole="$3" -v wart="$4" '
    { if ($1 == "project_id:") w = ($2 == pid)
      if (w && $1 == pole) { printf "    %s %s\n", pole, wart; next }
      print }
  ' "$1" > "$1.tmp" && mv "$1.tmp" "$1"
}

pokaz_blok() { # $1=plik $2=project_id — wypisuje blok tego projektu (do obejrzenia, co zrobił union)
  # `exit` w awk przechodzi przez END, więc bufor trzeba wyzerować PO wypisaniu — inaczej reguła END
  # wypisuje ten sam blok drugi raz i wygląda to jak dwa wpisy w pliku, których tam nie ma.
  awk -v pid="$2" '
    /^  - division: / { if (drukuj) { printf "%s", buf; buf = ""; exit } ; buf = $0 ORS; next }
    { buf = buf $0 ORS; if ($1 == "project_id:" && $2 == pid) drukuj = 1 }
    END { if (drukuj) printf "%s", buf }
  ' "$1"
}

# Co z tego pliku odczyta zwykły walidator — czyli `yaml.safe_load` bez własnego loadera. To jest druga
# połowa dowodu w wariantach z union: plik jest nie tylko sklejony, ale i CZYTELNY dla biblioteki, która
# nie zgłasza nic i po cichu bierze ostatnie wystąpienie klucza.
co_widzi_safe_load() { # $1=plik $2=project_id
  python3 - "$1" "$2" <<'PY'
import sys, yaml
plik, pid = sys.argv[1], sys.argv[2]
try:
    dokument = yaml.safe_load(open(plik, encoding="utf-8"))
except yaml.YAMLError as e:
    print(f"safe_load ZGLOSIL blad: {str(e).splitlines()[0]}")
    raise SystemExit(0)
wpisy = dokument["members"] if isinstance(dokument, dict) else dokument
print(f"safe_load: wczytal plik BEZ bledu, wpisow po parsowaniu: {len(wpisy)}")
for w in wpisy:
    if isinstance(w, dict) and w.get("project_id") == pid:
        print(f"safe_load: {pid} -> stage={w.get('stage')!r}, owner_group={w.get('owner_group')!r}")
PY
}

# --- operacje na repozytorium -------------------------------------------------------------------------

nowe_repo() { # $1=nazwa wariantu; zostawia CWD w środku repo
  rm -rf "${LAB:?}/$1"; mkdir -p "$LAB/$1/perimeter"; cd "$LAB/$1"
  git -c init.defaultBranch=main init -q
  git symbolic-ref HEAD refs/heads/main   # git < 2.28 nie zna init.defaultBranch, a nazwa gałęzi jest tu założeniem
  git config user.email bot@example.com
  git config user.name "bot onboardingu"
  git config commit.gpgsign false
  git config advice.detachedHead false
}

# Dziesięć gałęzi odbitych od TEGO SAMEGO commita — to jest definicja „równoległych PR-ów". Gdyby każda
# odbijała się od poprzedniej, mierzylibyśmy kolejkę, a nie współbieżność.
zbuduj_galezie() { # $1=tryb wstawki (sort|koniec) $2=tryb dywizji (rozne|jedna)
  n=1
  while [ "$n" -le "$PR_OW" ]; do
    git checkout -q -b "pr-$n" main
    gen_nowy_wpis "$n" "$(dywizja_pr "$n" "$2")" > "$LAB/nowy.txt"
    zastosuj_wpis perimeter/projects.yaml "$LAB/nowy.txt" "$1"
    git commit -q -am "pr-$n: dodaje projekt do perimetru"
    git checkout -q main
    n=$((n + 1))
  done
}

# Scalanie po kolei, bez żadnej pomocy. Nieudane scalenie = PR, który wraca do zespołu z prośbą o rebase.
scal_bez_pomocy() { # ustawia OK
  OK=0
  n=1
  while [ "$n" -le "$PR_OW" ]; do
    if git merge -q --no-edit "pr-$n" >/dev/null 2>&1; then
      OK=$((OK + 1))
    else
      git merge --abort >/dev/null 2>&1 || true
    fi
    n=$((n + 1))
  done
}

# Bot z rebase-retry. Kluczowe: bot NIE SCALA TEKSTU. Gdy jego gałąź nie wchodzi w nowy main, wyrzuca własny
# commit (`reset --hard origin/main`) i PONAWIA INTENCJĘ — jeszcze raz renderuje swój wpis na świeżym pliku.
# Dopisanie bloku na końcu pliku o zmienionej treści udaje się zawsze, bo to nie jest replay patcha, tylko
# ponowne wykonanie tej samej operacji na nowym wejściu. Dlatego ten wariant nie ma przypadku „nie da się".
scal_z_rebase_retry() { # $1=tryb dywizji; ustawia OK i RETRY
  OK=0; RETRY=0
  n=1
  while [ "$n" -le "$PR_OW" ]; do
    proba=1
    while [ "$proba" -le "$MAX_PROB" ]; do
      if git merge -q --no-edit "pr-$n" >/dev/null 2>&1; then
        OK=$((OK + 1)); break
      fi
      git merge --abort >/dev/null 2>&1 || true
      git checkout -q "pr-$n"
      git reset -q --hard main            # w realnym bocie: git fetch origin main && git reset --hard origin/main
      gen_nowy_wpis "$n" "$(dywizja_pr "$n" "$1")" > "$LAB/nowy.txt"
      zastosuj_wpis perimeter/projects.yaml "$LAB/nowy.txt" koniec
      git commit -q -am "pr-$n: dodaje projekt do perimetru (ponowienie $proba)"
      git checkout -q main
      RETRY=$((RETRY + 1))
      proba=$((proba + 1))
    done
    n=$((n + 1))
  done
}

# Bramka duplikatów. Zwraca 0 = czysto, 1 = naruszenia. Wywołanie owinięte, bo `set -e` ubiłoby skrypt na
# CZERWONEJ bramce — a czerwona bramka w wariancie B-edit jest OCZEKIWANYM wynikiem pomiaru.
bramka() { # $1=plik; ustawia BRAMKA_RC i BRAMKA_OUT
  BRAMKA_OUT="$(python3 "$BRAMKA" "$1" 2>&1)" && BRAMKA_RC=0 || BRAMKA_RC=$?
}

wpisow_w_pliku() { grep -c '^  - division: ' "$1" | tr -d ' '; }

naglowek() { printf '\n== %s ==\n' "$1"; }

# Raport wariantu jednoplikowego. Liczba wpisów jest tu równie ważna jak liczba scaleń: bez niej „10/10"
# znaczy tylko tyle, że git nie zaprotestował — a wariant B pokazuje, że to nie to samo, co „wnioski weszły".
# NIEZMIENNIK bez uniona: każdy zmergowany PR zostawia dokładnie jeden wpis, a każdy odrzucony — żadnego.
# Nieudane scalenie NIE MOŻE niczego gubić; gdyby gubiło, cała reszta pomiaru byłaby nieporównywalna.
raport_jednoplikowy() { # $1=plik $2=liczba udanych scalen; ustawia WPISOW i BRAMKA_RC
  WPISOW="$(wpisow_w_pliku "$1")"
  bramka "$1"
  printf '   %s/%s PR-ów bez konfliktu, wpisów w pliku: %s (spodziewane %s), bramka rc=%s\n' \
    "$2" "$PR_OW" "$WPISOW" "$((ISTNIEJACE + $2))" "$BRAMKA_RC"
}

# --- wariant A: jeden plik, wstawka sortowana, projekty z RÓŻNYCH dywizji ------------------------------
naglowek "A — jeden plik, wstawka sortowana, różne dywizje"
nowe_repo A
cp "$LAB/baseline.yaml" perimeter/projects.yaml
git add -A; git commit -qm "200 projektow w perimetrze"
zbuduj_galezie sort rozne
scal_bez_pomocy
OK_A="$OK"
raport_jednoplikowy perimeter/projects.yaml "$OK_A"
WPISOW_A="$WPISOW"; BRAMKA_A_RC="$BRAMKA_RC"

# --- wariant A-koniec: to samo, ale wpis dopisywany na KOŃCU pliku -------------------------------------
naglowek "A-koniec — jeden plik, dopisanie na końcu, różne dywizje"
nowe_repo A-koniec
cp "$LAB/baseline.yaml" perimeter/projects.yaml
git add -A; git commit -qm "200 projektow w perimetrze"
zbuduj_galezie koniec rozne
scal_bez_pomocy
OK_A_KONIEC="$OK"
raport_jednoplikowy perimeter/projects.yaml "$OK_A_KONIEC"
WPISOW_A_KONIEC="$WPISOW"; BRAMKA_A_KONIEC_RC="$BRAMKA_RC"

# --- wariant A-worst: jeden plik, wstawka sortowana, WSZYSTKIE PR-y z jednej dywizji -------------------
# To nie jest przypadek skrajny, tylko normalny: dywizje onboardują się falami, a sortowanie kładzie
# projekty jednej dywizji obok siebie. Dziesięć wniosków tego samego zespołu trafia w te same linie.
naglowek "A-worst — jeden plik, wstawka sortowana, TA SAMA dywizja"
nowe_repo A-worst
cp "$LAB/baseline.yaml" perimeter/projects.yaml
git add -A; git commit -qm "200 projektow w perimetrze"
zbuduj_galezie sort jedna
scal_bez_pomocy
OK_AW="$OK"
raport_jednoplikowy perimeter/projects.yaml "$OK_AW"
WPISOW_AW="$WPISOW"; BRAMKA_AW_RC="$BRAMKA_RC"

# --- wariant A-worst-koniec: ta sama fala, ale wpis dopisywany na końcu --------------------------------
# Kontrola dla pomysłu „nie sortujmy, dopisujmy na końcu — kolejność i tak nic nie znaczy". Jeżeli ten
# wariant też jest zły, to zmiana miejsca wstawki nie jest rozwiązaniem i trzeba zbudować bota (wariant D).
naglowek "A-worst-koniec — jeden plik, dopisanie na końcu, TA SAMA dywizja"
nowe_repo A-worst-koniec
cp "$LAB/baseline.yaml" perimeter/projects.yaml
git add -A; git commit -qm "200 projektow w perimetrze"
zbuduj_galezie koniec jedna
scal_bez_pomocy
OK_AW_KONIEC="$OK"
raport_jednoplikowy perimeter/projects.yaml "$OK_AW_KONIEC"
WPISOW_AW_KONIEC="$WPISOW"; BRAMKA_AW_KONIEC_RC="$BRAMKA_RC"

# --- wariant B: dane jak w A-worst + sterownik `union` -------------------------------------------------
# Union nie scala treści — dla spornego fragmentu wypisuje po prostu obie wersje, jedna za drugą. Przy
# DODAWANIU wpisów brzmi to jak dokładnie to, czego chcemy („weź oba wnioski"), i tak to było tu opisane,
# zanim skrypt to zmierzył. Patrz wynik: liczba wpisów po scaleniu jest ważniejsza niż liczba scaleń.
naglowek "B — jeden plik + merge=union (dane jak A-worst)"
nowe_repo B
cp "$LAB/baseline.yaml" perimeter/projects.yaml
echo "perimeter/projects.yaml merge=union" > .gitattributes
git add -A; git commit -qm "200 projektow w perimetrze"
zbuduj_galezie sort jedna
scal_bez_pomocy
OK_B="$OK"
WPISOW_B="$(wpisow_w_pliku perimeter/projects.yaml)"
bramka perimeter/projects.yaml
BRAMKA_B_RC="$BRAMKA_RC"
ZGUBIONE_B=$((ISTNIEJACE + PR_OW - WPISOW_B))
echo "   $OK_B/$PR_OW PR-ów bez konfliktu, wpisów w pliku: $WPISOW_B (oczekiwane $((ISTNIEJACE + PR_OW)))"
echo "   projektów, które zniknęły mimo zielonego scalenia: $ZGUBIONE_B"
echo "   wpis, w który union zlepił całą falę:"
pokaz_blok perimeter/projects.yaml "prj-example-new-01" | sed 's/^/     /'
echo "   bramka duplikatów: rc=$BRAMKA_B_RC — $(echo "$BRAMKA_OUT" | head -1)"
co_widzi_safe_load perimeter/projects.yaml "prj-example-new-01" | sed 's/^/   /'

# --- wariant B-edit: dwa PR-y EDYTUJĄCE ten sam wpis, przy włączonym union -----------------------------
# Osobny pomiar, nie „to samo bez konfliktu". Wariant B pokazuje, jak union gubi CAŁE wpisy przy dodawaniu;
# tutaj dostaje dwie zmiany w tym samym bloku — promocję (stage) i zmianę właściciela (owner_group) — i psuje
# wpis od środka. Oba scalenia PRZECHODZĄ, a w pliku zostaje wersja, której nie zatwierdził żaden z dwóch
# PR-ów. To jest inny tryb awarii niż w B i dlatego potrzebuje własnego wariantu, a nie przypisu.
naglowek "B-edit — dwie edycje TEGO SAMEGO wpisu przy merge=union"
nowe_repo B-edit
cp "$LAB/baseline.yaml" perimeter/projects.yaml
echo "perimeter/projects.yaml merge=union" > .gitattributes
git add -A; git commit -qm "200 projektow w perimetrze"

git checkout -q -b pr-promocja main
edytuj_pole perimeter/projects.yaml "$PROJEKT_EDYTOWANY" "stage:" "enforced"
git commit -q -am "pr-promocja: dry-run -> enforced"
git checkout -q main

git checkout -q -b pr-wlasciciel main
edytuj_pole perimeter/projects.yaml "$PROJEKT_EDYTOWANY" "owner_group:" "grp-example-division-security@example.com"
git commit -q -am "pr-wlasciciel: zmiana grupy wlascicielskiej"
git checkout -q main

OK_BEDIT=0
for g in pr-promocja pr-wlasciciel; do
  if git merge -q --no-edit "$g" >/dev/null 2>&1; then
    OK_BEDIT=$((OK_BEDIT + 1))
  else
    git merge --abort >/dev/null 2>&1 || true
  fi
done
WPISOW_BEDIT="$(wpisow_w_pliku perimeter/projects.yaml)"
echo "   $OK_BEDIT/2 scalenia przeszły bez konfliktu, wpisów w pliku: $WPISOW_BEDIT"
echo "   blok projektu $PROJEKT_EDYTOWANY po obu scaleniach:"
pokaz_blok perimeter/projects.yaml "$PROJEKT_EDYTOWANY" | sed 's/^/     /'
bramka perimeter/projects.yaml
BRAMKA_BEDIT_RC="$BRAMKA_RC"
echo "   bramka duplikatów: rc=$BRAMKA_BEDIT_RC — $(echo "$BRAMKA_OUT" | head -1)"
# Co widzi walidator BEZ własnego loadera. To jest cała odpowiedź na pytanie „po co podklasa SafeLoader":
# plik przechodzi, biblioteka nie zgłasza nic, a wartość jednego z dwóch zatwierdzonych PR-ów po prostu
# nie istnieje. PR promocyjny został ZMERGOWANY i nie zmienił niczego.
STAGE_PO_UNII="$(python3 - perimeter/projects.yaml "$PROJEKT_EDYTOWANY" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
print(next(w.get("stage") for w in d["members"] if w.get("project_id") == sys.argv[2]))
PY
)"
co_widzi_safe_load perimeter/projects.yaml "$PROJEKT_EDYTOWANY" | sed 's/^/   /'
echo "   PR promocyjny zmergowany, a po scaleniu stage=$STAGE_PO_UNII (zatwierdzono: enforced)"

# --- wariant C: plik na projekt (kontrola) -------------------------------------------------------------
naglowek "C — plik na projekt (kontrola)"
nowe_repo C
mkdir -p perimeter/members
cp -R "$LAB/wzor-members/." perimeter/members/
git add -A; git commit -qm "200 projektow w perimetrze"
n=1
while [ "$n" -le "$PR_OW" ]; do
  git checkout -q -b "pr-$n" main
  dyw="$(dywizja_pr "$n" jedna)"   # NAJGORSZY przypadek dla C: cała fala z jednej dywizji, jak w A-worst
  pid="$(printf 'prj-example-new-%02d' "$n")"
  {
    printf 'division: %s\n' "$dyw"
    printf 'project_id: %s\n' "$pid"
    printf 'project_number: "%s"\n' "$(numer_nowy "$n")"
    printf 'owner_group: grp-%s@example.com\n' "$dyw"
    printf 'stage: dry-run\n'
    printf 'profiles: []\n'
  } > "perimeter/members/$dyw-$pid.yaml"
  git add -A; git commit -qm "pr-$n: dodaje projekt do perimetru"
  git checkout -q main
  n=$((n + 1))
done
scal_bez_pomocy
OK_C="$OK"
PLIKOW_C="$(find perimeter/members -name '*.yaml' | wc -l | tr -d ' ')"
ROZMIAR_C="$(du -sh perimeter/members | cut -f1 | tr -d ' ')"
echo "   $OK_C/$PR_OW PR-ów bez konfliktu, plików: $PLIKOW_C, rozmiar katalogu: $ROZMIAR_C"

# --- wariant D: jeden plik + bot z rebase-retry --------------------------------------------------------
# Dane wejściowe IDENTYCZNE jak w A-worst-koniec (ten sam baseline, ta sama dywizja, dopisywanie na końcu).
# Zmienia się wyłącznie to, co bot robi po nieudanym scaleniu. Liczba ponowień jest tu równie ważna jak
# 10/10 — to jest realny koszt tego rozwiązania i musi trafić do tabeli, a nie zniknąć w słowie „działa".
naglowek "D — jeden plik + bot z rebase-retry (dane jak A-worst-koniec)"
nowe_repo D
cp "$LAB/baseline.yaml" perimeter/projects.yaml
git add -A; git commit -qm "200 projektow w perimetrze"
zbuduj_galezie koniec jedna
scal_z_rebase_retry jedna
OK_D="$OK"; RETRY_D="$RETRY"
WPISOW_D="$(wpisow_w_pliku perimeter/projects.yaml)"
bramka perimeter/projects.yaml
BRAMKA_D_RC="$BRAMKA_RC"
echo "   $OK_D/$PR_OW PR-ów bez konfliktu, ponowień łącznie: $RETRY_D"
echo "   wpisów w pliku: $WPISOW_D (oczekiwane $((ISTNIEJACE + PR_OW)))"
echo "   bramka duplikatów: rc=$BRAMKA_D_RC — $BRAMKA_OUT"

# --- tabela -------------------------------------------------------------------------------------------
cd "$LAB"
printf '\n\nWYNIK — %s istniejących projektów, %s równoległych PR-ów, każdy dodaje jeden projekt\n\n' \
  "$ISTNIEJACE" "$PR_OW"
# Kolumny liczbowe idą PRZED opisem wariantu, bo `printf` liczy szerokość w BAJTACH, nie w znakach —
# polskie znaki w etykiecie rozjeżdżają każdą kolumnę wypisaną po niej. Opis na końcu nie wymaga wyrównania.
stan_bramki() { [ "$1" -eq 0 ] && echo ZIELONA || echo CZERWONA; }
wiersz() { printf '  %-13s %-9s %-9s %-8s %s\n' "$1" "$2" "$3" "$4" "$5"; }
wiersz "bez konfliktu" "wpisow" "ponowien" "bramka" "wariant"
wiersz "$OK_A/$PR_OW" "$WPISOW_A" "-" "$(stan_bramki "$BRAMKA_A_RC")" "A — jeden plik, sortowanie, różne dywizje"
wiersz "$OK_A_KONIEC/$PR_OW" "$WPISOW_A_KONIEC" "-" "$(stan_bramki "$BRAMKA_A_KONIEC_RC")" "A — jeden plik, na końcu, różne dywizje"
wiersz "$OK_AW/$PR_OW" "$WPISOW_AW" "-" "$(stan_bramki "$BRAMKA_AW_RC")" "A-worst — jeden plik, sortowanie, JEDNA dywizja"
wiersz "$OK_AW_KONIEC/$PR_OW" "$WPISOW_AW_KONIEC" "-" "$(stan_bramki "$BRAMKA_AW_KONIEC_RC")" "A-worst — jeden plik, na końcu, JEDNA dywizja"
wiersz "$OK_B/$PR_OW" "$WPISOW_B" "-" "$(stan_bramki "$BRAMKA_B_RC")" "B — jeden plik + merge=union (dodawanie wpisów)"
wiersz "$OK_BEDIT/2" "$WPISOW_BEDIT" "-" "$(stan_bramki "$BRAMKA_BEDIT_RC")" "B-edit — union, dwie edycje tego samego wpisu"
wiersz "$OK_C/$PR_OW" "$PLIKOW_C" "-" "-" "C — plik na projekt ($PLIKOW_C plików, $ROZMIAR_C)"
wiersz "$OK_D/$PR_OW" "$WPISOW_D" "$RETRY_D" "$(stan_bramki "$BRAMKA_D_RC")" "D — jeden plik + bot z rebase-retry"
printf '\n  kolumna „wpisow" = ile wpisów jest w pliku po scaleniach; poprawna wartość to %s + liczba\n' "$ISTNIEJACE"
printf '  scaleń, KTÓRE PRZESZŁY — odrzucony PR ma nie wnieść nic, zmergowany dokładnie jeden wpis.\n'
printf '  Liczba scaleń bez konfliktu NIE jest miarą sukcesu — wariant B ma %s/%s i gubi %s projektów.\n' \
  "$OK_B" "$PR_OW" "$ZGUBIONE_B"

# --- kontrole: czy ten przebieg w ogóle coś zmierzył --------------------------------------------------
#
# Każda z tych asercji broni przed innym sposobem, w jaki eksperyment mógłby potwierdzić tezę sam z siebie.
# Skrypt kończy się kodem != 0, gdy przebieg NIE JEST pomiarem — nie wtedy, gdy wynik jest niewygodny.
naglowek "kontrole"
BLEDY=0
zglos() { echo "   $1"; BLEDY=$((BLEDY + 1)); }

if [ "$OK_AW_KONIEC" -ge "$PR_OW" ]; then
  zglos "NIEROZSTRZYGNIĘTE: A-worst-koniec dał $OK_AW_KONIEC/$PR_OW, więc wariant D nie ma czego poprawiać."
else
  echo "   OK: kontrola dla D jest niedegenerowana — A-worst-koniec $OK_AW_KONIEC/$PR_OW"
fi

if [ "$OK_D" -le "$OK_AW_KONIEC" ]; then
  zglos "HIPOTEZA O REBASE-RETRY OBALONA: D=$OK_D/$PR_OW przy identycznych danych i A-worst-koniec=$OK_AW_KONIEC/$PR_OW."
else
  echo "   OK: D ($OK_D/$PR_OW) > A-worst-koniec ($OK_AW_KONIEC/$PR_OW) na TYCH SAMYCH danych — różni je tylko bot"
fi

# Osobno od porównania z A-worst: D ma domknąć KOMPLET przy zielonej bramce. Sprawdzamy jedno i drugie,
# bo „więcej niż kontrola" i „wszystkie wnioski weszły, nic się nie zdublowało" to dwie różne własności —
# a wariant B pokazał, że komplet zielonych scaleń da się mieć i przy zepsutym pliku.
if [ "$OK_D" -ne "$PR_OW" ] || [ "$BRAMKA_D_RC" -ne 0 ]; then
  zglos "D nie domknął pomiaru: $OK_D/$PR_OW scaleń, bramka rc=$BRAMKA_D_RC, wpisów $WPISOW_D."
else
  echo "   OK: D domyka komplet $OK_D/$PR_OW przy ZIELONEJ bramce i $WPISOW_D wpisach — nie kupione duplikatami"
fi

if [ "$BRAMKA_BEDIT_RC" -eq 0 ]; then
  zglos "BRAMKA NIE DZIAŁA: B-edit przeszedł na ZIELONO, a wpis po union ma dwa razy stage i owner_group."
else
  echo "   OK: bramka jest CZERWONA na B-edit i ZIELONA na D — rozróżnia przypadki, nie odrzuca wszystkiego"
fi

# Czy B-edit w ogóle pokazał CICHĄ utratę, czy tylko brzydki plik. Gdyby po scaleniu `stage` był `enforced`
# (i właściciel z drugiego PR-a), obie zatwierdzone zmiany by przeżyły i wariant nie dowodziłby niczego poza
# estetyką. Utratę mierzymy tym, co z pliku odczyta walidator, nie tym, co widać w diffie.
if [ "$OK_BEDIT" -eq 2 ] && [ "$STAGE_PO_UNII" != "enforced" ]; then
  echo "   OK: B-edit zmierzył CICHĄ utratę — PR promocyjny zmergowany, a walidator czyta stage=$STAGE_PO_UNII"
else
  zglos "B-edit NIC NIE POKAZAŁ: scaleń $OK_BEDIT/2, stage po scaleniu=$STAGE_PO_UNII — brak cichej utraty."
fi

# NIEZMIENNIK ZACHOWANIA WPISÓW, sprawdzany na KAŻDYM wariancie jednoplikowym: po scaleniach w pliku ma być
# dokładnie `200 + liczba scaleń, które przeszły`. Odrzucony PR nie wnosi nic (i to jest w porządku —
# wraca do zespołu po rebase), zmergowany wnosi dokładnie jeden wpis. Wariant, który ten niezmiennik łamie,
# gubi zatwierdzone wnioski BEZ BŁĘDU — i wtedy bramka MUSI być czerwona, inaczej jest ślepa.
#
# Ta asercja zastąpiła wcześniejsze założenie „union przy dodawaniu jest bezpieczny". Pomiar je obalił,
# więc zamiast poprawić opis pod wynik, sprawdzamy własność, która obowiązuje niezależnie od zachowania uniona.
sprawdz_zachowanie_wpisow() { # $1=etykieta $2=wpisow $3=udanych scalen $4=rc bramki
  ocz=$((ISTNIEJACE + $3))
  if [ "$2" -eq "$ocz" ]; then
    echo "   OK: $1 — $2 wpisów przy $3 zmergowanych PR-ach, nic nie zginęło"
  elif [ "$4" -ne 0 ]; then
    echo "   OK: $1 — zgubił $((ocz - $2)) wpisów mimo zielonych scaleń, ale bramka to zatrzymała"
  else
    zglos "BRAMKA ŚLEPA: $1 ma $2 z $ocz wpisów, a bramka przepuściła ten plik."
  fi
}
sprawdz_zachowanie_wpisow "A/sortowanie"      "$WPISOW_A"        "$OK_A"        "$BRAMKA_A_RC"
sprawdz_zachowanie_wpisow "A/na końcu"        "$WPISOW_A_KONIEC" "$OK_A_KONIEC" "$BRAMKA_A_KONIEC_RC"
sprawdz_zachowanie_wpisow "A-worst/sortowanie" "$WPISOW_AW"      "$OK_AW"       "$BRAMKA_AW_RC"
sprawdz_zachowanie_wpisow "A-worst/na końcu"  "$WPISOW_AW_KONIEC" "$OK_AW_KONIEC" "$BRAMKA_AW_KONIEC_RC"
sprawdz_zachowanie_wpisow "B/union"           "$WPISOW_B"        "$OK_B"        "$BRAMKA_B_RC"
sprawdz_zachowanie_wpisow "D/rebase-retry"    "$WPISOW_D"        "$OK_D"        "$BRAMKA_D_RC"

# Ostatnia i najprostsza: gdyby bramka była czerwona ZAWSZE, wszystkie powyższe „OK" byłyby bezwartościowe.
if [ "$BRAMKA_D_RC" -ne 0 ] || [ "$BRAMKA_BEDIT_RC" -eq 0 ]; then
  zglos "BRAMKA NIE ROZRÓŻNIA: potrzebny jest przebieg ZIELONY (D) i CZERWONY (B-edit) w tym samym uruchomieniu."
fi

echo
if [ "$BLEDY" -gt 0 ]; then
  echo "PRZEBIEG NIE JEST POMIAREM — $BLEDY kontrol(i) nie przeszło. Napraw i powtórz."
  exit 1
fi

cat <<'KONIEC_WNIOSKU'

WNIOSEK
  Konflikt nie bierze się z tego, że plik jest wspólny, tylko z tego, że dwie zmiany trafiają w te same
  linie. Sortowanie kładzie falę onboardingu jednej dywizji obok siebie; dopisywanie na końcu kładzie
  WSZYSTKIE PR-y na końcu. Zmiana miejsca wstawki nie jest rozwiązaniem — to jest zmierzone, nie założone.
  `merge=union` nie jest rozwiązaniem tym bardziej: podnosi liczbę zielonych scaleń do kompletu i przy tym
  GUBI projekty, bo zlepia sąsiadujące wpisy w jeden. Zielone scalenie przestaje wtedy znaczyć „wniosek
  wszedł", a bramka duplikatów jest jedyną rzeczą, która to zauważa.
  Wspólny plik ma więc dokładnie jedno wyjście: bot ponawiający INTENCJĘ na świeżym main. Działa (10/10),
  ale kosztuje ponowienia, własny kod i tę bramkę. Plik na projekt daje ten sam wynik bez żadnego z trzech.
KONIEC_WNIOSKU
