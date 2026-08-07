#!/usr/bin/env bash
# Ile PR-ow z 10 wchodzi bez konfliktu, gdy wszystkie dodaja projekt do perimetru?
# Trzy warianty: (A) jeden projects.yml, (B) jeden plik + merge=union, (C) plik per projekt.
set -euo pipefail
LAB="$1"; rm -rf "$LAB"; mkdir -p "$LAB"; cd "$LAB"

mk_repo() {  # $1 = nazwa wariantu
  rm -rf "$1"; mkdir "$1"; cd "$1"; git init -q; git config user.email t@t; git config user.name t
}

# 200 istniejacych projektow, posortowane, jeden wpis = jedna linia
gen_baseline() { for i in $(seq -w 1 200); do echo "  - {division: div-$((10#$i % 20)), project: prj-$i, number: \"1000000000$i\"}"; done; }

report() { printf '%-42s %s/%s PR-ow bez konfliktu\n' "$1" "$2" "$3"; }

# --- A: jeden plik, bez sztuczek -------------------------------------------------------------
mk_repo A
{ echo "members:"; gen_baseline; } > projects.yml
git add -A; git commit -qm base
ok=0
for n in $(seq 1 10); do
  git checkout -q -b pr-$n main 2>/dev/null || git checkout -q -b pr-$n master
  # kazdy zespol dopisuje SWOJ projekt w miejscu wynikajacym z sortowania
  awk -v new="  - {division: div-$n, project: prj-2$n, number: \"20000000$n\"}" \
      'BEGIN{done=0} /^  - / && !done && $0 > new {print new; done=1} {print} END{if(!done) print new}' \
      projects.yml > t && mv t projects.yml
  git commit -qam "pr-$n"
  git checkout -q - 2>/dev/null || true
done
git checkout -q master 2>/dev/null || git checkout -q main
for n in $(seq 1 10); do
  if git merge -q --no-edit pr-$n >/dev/null 2>&1; then ok=$((ok+1)); else git merge --abort 2>/dev/null || true; fi
done
report "A. jeden projects.yml" "$ok" 10
cd ..

# --- B: jeden plik + sterownik scalania `union` ------------------------------------------------
mk_repo B
{ echo "members:"; gen_baseline; } > projects.yml
echo "projects.yml merge=union" > .gitattributes
git add -A; git commit -qm base
ok=0
for n in $(seq 1 10); do
  git checkout -q -b pr-$n master 2>/dev/null || git checkout -q -b pr-$n main
  awk -v new="  - {division: div-$n, project: prj-2$n, number: \"20000000$n\"}" \
      'BEGIN{done=0} /^  - / && !done && $0 > new {print new; done=1} {print} END{if(!done) print new}' \
      projects.yml > t && mv t projects.yml
  git commit -qam "pr-$n"; git checkout -q - >/dev/null 2>&1 || true
done
git checkout -q master 2>/dev/null || git checkout -q main
for n in $(seq 1 10); do
  if git merge -q --no-edit pr-$n >/dev/null 2>&1; then ok=$((ok+1)); else git merge --abort 2>/dev/null || true; fi
done
report "B. jeden plik + merge=union" "$ok" 10
echo "   (wpisow po scaleniu: $(grep -c '^  - ' projects.yml), duplikatow: $(grep '^  - ' projects.yml | sort | uniq -d | wc -l | tr -d ' '))"
cd ..

# --- C: plik per projekt ----------------------------------------------------------------------
mk_repo C
mkdir -p members
for i in $(seq -w 1 200); do printf 'division: div-%s\nproject: prj-%s\nnumber: "1000000000%s"\n' "$((10#$i % 20))" "$i" "$i" > "members/prj-$i.yaml"; done
git add -A; git commit -qm base
ok=0
for n in $(seq 1 10); do
  git checkout -q -b pr-$n master 2>/dev/null || git checkout -q -b pr-$n main
  printf 'division: div-%s\nproject: prj-2%s\nnumber: "20000000%s"\n' "$n" "$n" "$n" > "members/prj-2$n.yaml"
  git add -A; git commit -qm "pr-$n"; git checkout -q - >/dev/null 2>&1 || true
done
git checkout -q master 2>/dev/null || git checkout -q main
for n in $(seq 1 10); do
  if git merge -q --no-edit pr-$n >/dev/null 2>&1; then ok=$((ok+1)); else git merge --abort 2>/dev/null || true; fi
done
report "C. plik per projekt (200 plikow)" "$ok" 10
echo "   (plikow w katalogu: $(ls members | wc -l | tr -d ' '), rozmiar katalogu: $(du -sh members | cut -f1))"
