#!/usr/bin/env python3
"""Test end-to-end startera: rozpakuj szablony → zbuduj repo → uruchom każdą bramkę na dobrym i złym wejściu.

Co ten test naprawdę sprawdza (i czego NIE):
  * TAK — że `install.sh` mapuje nazwy poprawnie i że rozpakowane pliki DZIAŁAJĄ (terraform waliduje,
    reguły rego przechodzą własne testy, narzędzia liczą na realnych deklaracjach);
  * TAK — że każda bramka PADA na złym wejściu. Bramka, która nigdy nie odrzuca, przechodzi każdy test
    pozytywny i nie chroni niczego — dlatego testy negatywne są tu ważniejsze od pozytywnych;
  * NIE — mechaniki GitHuba (needs:, environments, OIDC) ani realnego API Google. Pierwszą warstwę pokrywa
    `actionlint`, drugą dopiero pierwszy apply na środowisku docelowym.

Wymaga na PATH: terraform (1.15.5), conftest, python3 (pyyaml). Opcjonalnie: actionlint, check-jsonschema.
Uruchomienie:  python3 selftest/selftest.py
"""
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("brakuje pyyaml: pip install pyyaml")

HERE = pathlib.Path(__file__).resolve().parent
STARTER = HERE.parent
results = []
ROOT: pathlib.Path | None = None


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, bool(cond), detail))
    print(("  OK   " if cond else "  FAIL ") + name + (f"\n         [{detail}]" if detail and not cond else ""))


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def strip_heredocs(text: str) -> str:
    """Usuwa treść heredoców, zostawiając sam kod.

    DLACZEGO to istnieje: guardy w tym pliku sprawdzają, czego w kodzie NIE MA (`terraform apply`,
    `cp -R perimeter`, `google_organization_iam_binding`). Trzy razy z rzędu taki guard wywrócił się o
    WŁASNĄ DOKUMENTACJĘ — komentarz albo instrukcję dla człowieka w heredocu, która wymienia zakazaną
    konstrukcję, żeby wyjaśnić, dlaczego jej nie używamy. Test psujący się o dokumentację uczy tylko
    usuwania komentarzy, więc guardy tekstowe idą przez ten filtr.
    """
    out, skip_until = [], None
    for line in text.splitlines():
        if skip_until is not None:
            if line.strip() == skip_until:
                skip_until = None
            continue
        m = re.search(r"<<-?'?([A-Z][A-Z0-9_]*)'?\s*$", line)
        if m:
            skip_until = m.group(1)
            continue
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------- rozpakowanie
def bootstrap() -> None:
    global ROOT
    ROOT = pathlib.Path(tempfile.mkdtemp(prefix="vpcsc-starter-selftest-"))
    print(f"\n== rozpakowanie szablonow (install.sh) -> {ROOT} ==")

    p = sh(["bash", str(STARTER / "install.sh"), str(ROOT)])
    check("install.sh konczy sie sukcesem", p.returncode == 0, p.stdout + p.stderr)

    expected = {
        ".github/CODEOWNERS", ".github/pull_request_template.md",
        ".github/workflows/intake.yml", ".github/workflows/validate.yml",
        ".github/workflows/plan.yml", ".github/workflows/apply.yml",
        ".github/workflows/drift.yml", ".github/workflows/violations-report.yml",
        ".github/workflows/expiry-sweep.yml", ".github/workflows/break-glass.yml",
        ".github/workflows/external-intake.yml", ".github/workflows/publish-gates.yml",
        ".github/workflows/starter-drift.yml", ".starter-sync",
        ".github/workflows/boundary-probe.yml",
        ".github/workflows/intake-rebase.yml", ".gitattributes",
        "contrib/action.yml", "contrib/validate-local.sh", "contrib/README.md",
        ".gitignore", ".pre-commit-config.yaml", ".tool-versions",
        "perimeter/policy.yaml", "perimeter/access-levels/corp.yaml", "perimeter/contributors.yaml",
        "perimeter/projects.yaml",
        "perimeter/profiles/vertex-online-serving.yaml",
        "perimeter/profiles/vertex-batch-training.yaml",
        "perimeter/profiles/corp-user-console-access.yaml",
        "perimeter/profiles/bq-omni-external-read.yaml",
        "policy/onboarding.rego", "policy/onboarding_test.rego",
        "policy/perimeter.rego", "policy/perimeter_test.rego",
        "schemas/member.schema.json", "schemas/projects.schema.json",
        "schemas/policy.schema.json", "schemas/profile.schema.json",
        "schemas/access-level.schema.json",
        "terraform/locals.tf", "terraform/members.tf", "terraform/outputs.tf",
        "terraform/perimeter.tf", "terraform/rules.tf", "terraform/versions.tf",
        "terraform/contract.tf", "terraform/tests/renderer.tftest.hcl", "terraform/monitoring.tf",
        "iam-bootstrap/README.md", "iam-bootstrap/main.tf", "iam-bootstrap/variables.tf",
        "iam-bootstrap/versions.tf", "iam-bootstrap/terraform.tfvars.sample",
        "iam-bootstrap/outputs.tf",
        "violations-sink/README.md", "violations-sink/main.tf", "violations-sink/variables.tf",
        "violations-sink/versions.tf", "violations-sink/terraform.tfvars.sample",
        "violations-sink/outputs.tf",
        "tools/attribute_budget.py", "tools/collect_declarations.py", "tools/preflight_check.sh",
        "tools/render_member.py", "tools/projects_file.py", "tools/snow_verify.py",
        "tools/violations_report.py",
        "tools/deny_check.sh",
        "tools/bootstrap_github.sh", "docs/access-request.md",
        "tools/check_supported_services.py",
        "tools/control_plane_check.py",
        # Kompletnosc rejestru decyzji — druga bramka rozjazdu ze starterem, obok wskaznika (DEC-19).
        "tools/decisions_check.py",
        "tools/perimeter_to_policy.py", "tools/brownfield_import.sh",
        "tools/perimeter_watch.py", "terraform/alerts.tf",
        "perimeter/alerting.yaml", "schemas/alerting.schema.json",
        ".github/workflows/watch.yml",
        # Bramki treści i bramki żywe jako akcje złożone: JEDNA definicja, wołana przez tor pull requesta
        # (`validate.yml`/`plan.yml`) i przez mutatora (`apply.yml`). Patrz DEC-16.
        ".github/actions/bramki-tresci/action.yml", ".github/actions/bramki-zywe/action.yml",
        # Bramka promocji: jedyna bramka WYLACZNIE mutatora — pyta o moment skutku, nie o tresc (DEC-17).
        ".github/actions/bramka-promocji/action.yml", "tools/promotion_hold.py",
        ".tflint.hcl", ".github/dependabot.yml", "tests/README.md",
        "tests/snow-approved.json", "tests/snow-not-approved.json", "tests/snow-self-approved.json",
        "tests/snow-wrong-project.json", "tests/dispatch-example.json",
        "tests/snow-not-found.json", "tests/snow-no-approval.json",
        "tests/vpcsc-violation-dryrun.json",
    }
    # Dokumentacja jedzie razem z kodem. Wyliczamy ją z katalogu startera zamiast przepisywać listę:
    # przepisana lista wywracałaby ten test przy każdym nowym dokumencie, a to uczy dopisywania nazw
    # zamiast czytania, co się realnie zmieniło.
    expected |= {f"docs/{f.relative_to(STARTER / 'docs')}"
                 for f in (STARTER / "docs").rglob("*") if f.is_file()}
    expected.add("AGENTS.md")
    got = {str(f.relative_to(ROOT)) for f in ROOT.rglob("*") if f.is_file()}
    check("install.sh mapuje nazwy 1:1 (bez .example, github/ -> .github/)", expected == got,
          f"brakuje={sorted(expected - got)} nadmiarowe={sorted(got - expected)}")

    # Anty-tautologia do powyższego: zbiory mogą się zgadzać także wtedy, gdy docs/ jest puste po obu
    # stronach. Te dwa pliki są cytowane w treści alertu produkcyjnego i w komunikacie bramki CI —
    # jeśli ich nie ma w docelowym repo, odsyłacz prowadzi donikąd dokładnie wtedy, gdy jest potrzebny.
    check("docs/ ląduje w docelowym repo (alert i bramka CI na nie wskazują)",
          {"docs/0-decyzje.md", "docs/3-runbook-promocja-i-break-glass.md"} <= got,
          f"brakuje: {sorted({'docs/0-decyzje.md', 'docs/3-runbook-promocja-i-break-glass.md'} - got)}")

    # --only: tryb wdrożenia etapami. Obie strony muszą być pewne — kopiuje dokładnie jeden plik,
    # a wzorzec bez trafienia PADA (cichy sukces = etap uznany za wdrożony, a w repo nic nie ma).
    solo = pathlib.Path(tempfile.mkdtemp(prefix="vpcsc-only-"))
    p = sh(["bash", str(STARTER / "install.sh"), str(solo), "--only", "validate.yml"])
    got_solo = {str(f.relative_to(solo)) for f in solo.rglob("*") if f.is_file()}
    check("install.sh --only kopiuje dokladnie jeden plik",
          p.returncode == 0 and got_solo == {".github/workflows/validate.yml"}, f"{p.returncode} {got_solo}")
    p = sh(["bash", str(STARTER / "install.sh"), str(solo), "--only", "nie-ma-takiego"])
    check("install.sh --only bez trafienia PADA", p.returncode != 0, f"rc={p.returncode}")
    shutil.rmtree(solo, ignore_errors=True)

    # Szablony muszą pozostać martwe: w template/ nie ma ANI JEDNEGO pliku-kropki ani żywego .tf,
    # bo działałyby w TYM repo (pre-commit walidowałby cudzy szkielet, git czytałby cudze .gitattributes).
    dotfiles = [str(f) for f in (STARTER / "template").rglob(".*")]
    live_tf = [str(f) for f in (STARTER / "template").rglob("*.tf")]
    check("template/ nie zawiera plikow-kropek", not dotfiles, str(dotfiles))
    check("template/ nie zawiera zywych *.tf", not live_tf, str(live_tf))

    # `examples/` to material dla repozytorium DYWIZJI, a install.sh rozpakowuje repozytorium PERIMETRU.
    # Gdyby przyklad tam trafil, `examples/division-repo/github/workflows/vpc-sc-request.yml` zmapowalby sie
    # na `.github/workflows/` i stalby sie ZYWYM workflowem wysylajacym dispatch do samego siebie. Zbior
    # `expected` wyzej zlapalby to jako "nadmiarowe", ale bez nazwy powodu — a to jest decyzja, nie literowka.
    check("examples/ NIE laduje w docelowym repo (material dla repo DYWIZJI, nie perimetru)",
          not [f for f in got if f.startswith("examples/") or f.endswith("vpc-sc-request.yml")],
          str(sorted(f for f in got if f.startswith("examples/"))))
    # Ten sam niezmiennik co dla template/: dopoki przyklad lezy tutaj, ma byc martwym tekstem.
    przyklad_kropki = [str(f) for f in (STARTER / "examples").rglob(".*")]
    check("examples/ nie zawiera plikow-kropek (github/ bez kropki)", not przyklad_kropki, str(przyklad_kropki))


# --------------------------------------------------------------------- terraform
def test_terraform() -> None:
    print("\n== terraform ==")
    if not have("terraform"):
        check("terraform dostepny", False, "brak terraform na PATH — pomijam fmt/validate")
        return
    tf = ROOT / "terraform"
    p = sh(["terraform", f"-chdir={tf}", "fmt", "-check", "-recursive"])
    check("terraform fmt -check", p.returncode == 0, p.stdout + p.stderr)
    p = sh(["terraform", f"-chdir={tf}", "init", "-backend=false", "-input=false"])
    check("terraform init -backend=false", p.returncode == 0, p.stdout[-800:] + p.stderr[-800:])
    p = sh(["terraform", f"-chdir={tf}", "validate"])
    check("terraform validate", p.returncode == 0, p.stdout + p.stderr)

    # `terraform console` wymaga zainicjalizowanego BACKENDU (inaczej: „init with -reconfigure"), a startowy
    # backend to GCS z placeholderem. Podmieniamy go na lokalny plikiem *_override.tf — to zabieg wyłącznie
    # testowy, w rozpakowanej kopii; nie dotyka szablonu.
    (tf / "zz_selftest_override.tf").write_text('terraform {\n  backend "local" {}\n}\n')
    p = sh(["terraform", f"-chdir={tf}", "init", "-reconfigure", "-input=false"])
    check("init z lokalnym backendem (override na czas testu)", p.returncode == 0, p.stdout[-500:] + p.stderr[-500:])

    # Renderer musi umieć policzyć reguły BEZ dostępu do chmury — `terraform console` liczy locals lokalnie.
    p = sh(["terraform", f"-chdir={tf}", "console"], input="length(local.ingress_rules_all)\n")
    check("renderer liczy reguly ingress z YAML (terraform console)",
          p.returncode == 0 and p.stdout.strip().splitlines()[-1].strip() == "2",
          f"stdout={p.stdout!r} stderr={p.stderr[-400:]!r}")

    # Natywne testy Terraforma — to one pilnują logiki renderera (jedynego miejsca w repo, gdzie jest logika).
    p = sh(["terraform", f"-chdir={tf}", "test"])
    check("terraform test (renderer)", p.returncode == 0 and "0 failed" in p.stdout, p.stdout[-1200:])

    # Test 12 renderera porównuje LICZBĘ wyrenderowanych reguł egress z zasobem zewnętrznym z liczbą celów
    # ZADEKLAROWANYCH przez członków. Równość jest ostra w obie strony, ale gdy przykładowe deklaracje
    # przestaną tę ścieżkę w ogóle deklarować, obie strony spadają do zera i test przechodzi NIE BADAJĄC
    # niczego. Materiał startera jest jedynym miejscem, w którym ta ścieżka ma prawo być uruchomiona
    # (w prawdziwym repo nikt nie musi używać BigQuery Omni), więc tu pilnujemy, że nadal jest.
    premisa = ("length(flatten([for mkey, m in local.members : [for p in m.profiles : "
               "[for rule in lookup(local.profiles[p.name], \"egress\", []) : rule.title "
               "if length(lookup(p.params, lookup(rule, \"to_external_from\", \"__none__\"), [])) > 0]]]))")
    p = sh(["terraform", f"-chdir={tf}", "console"], input=premisa + "\n")
    ostatnia = p.stdout.strip().splitlines()[-1].strip() if p.stdout.strip() else ""
    check("przykladowe deklaracje uruchamiaja sciezke egressu zewnetrznego (test 12 nie jest pusty)",
          p.returncode == 0 and ostatnia.isdigit() and int(ostatnia) > 0,
          f"premisa={ostatnia!r} stderr={p.stderr[-300:]!r}")

    # Przykładowy członek jest w dry-run, więc konfiguracja EGZEKWOWANA musi być pusta. To pilnuje
    # najważniejszej własności startera: świeże repo nie blokuje nikomu ruchu.
    p = sh(["terraform", f"-chdir={tf}", "console"], input="length(local.ingress_rules_enforced)\n")
    check("swieze repo nie ma zadnej reguly egzekwowanej",
          p.returncode == 0 and p.stdout.strip().splitlines()[-1].strip() == "0", p.stdout + p.stderr[-300:])

    # --- BASELINE NIE ZALEZY OD CZLONKOSTWA: ani liczba regul, ani ich TRESC -------------------------
    #
    # Zmierzone na zywym ACM: przy renderowaniu per czlonek baseline kosztowal 21 atrybutow NA CZLONKA, przy
    # limicie 6000 NA KONFIGURACJE — czyli sufit ~230 czlonkow, przekraczany w trakcie wdrozenia. Kolaps
    # (DEC-10) zdjal powielanie regul, ale zostawil w regule LISTE zasobow rosnaca z kazdym czlonkiem — a to
    # pole jest `ForceNew`, wiec kazdy wniosek REPLACE'owal obie reguly baseline (`Plan: 4 to add, 1 to
    # change, 2 to destroy`), czyli w konfiguracji egzekwowanej tworzyl okno bez reguly skanera dla
    # WSZYSTKICH promowanych naraz. DEC-11 zastapil liste gwiazdka i ten test pilnuje wlasnie TEGO: drugi
    # czlonek nie moze zmienic reguly baseline ANI O JEDEN ZNAK.
    #
    # DLACZEGO TEN TEST DOKŁADA DRUGIEGO CZLONKA, a nie pyta o material startera takim, jaki jest: przy
    # JEDNYM czlonku „jedna regula na tytul" i „jedna regula na czlonek x tytul" daja TE SAMA liczbe, wiec
    # asercja przechodzilaby rowniez dla ksztaltu, ktory ten test ma wykluczyc. Rozstrzyga dopiero drugi
    # czlonek. `terraform test` nie umie podlozyc plikow deklaracji, wiec robimy to tutaj — na rozpakowanej
    # kopii, ktora i tak jest jednorazowa. Kopia znika przed nastepnymi testami, zeby nie zmieniac ich premis.
    def konsola(wyrazenie: str) -> str:
        r = sh(["terraform", f"-chdir={tf}", "console"], input=wyrazenie + "\n")
        return r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""

    # Drugi czlonek jest przy okazji `stage: enforced`, zeby ta sama podmianka pokryla DRUGA sciezke, ktorej
    # material startera nie uruchamia: `baseline_rules_enforced`. W swiezym repo nikt nie jest promowany, wiec
    # ta mapa jest PUSTA i kazda asercja o niej przechodzi trywialnie — czyli kod konfiguracji EGZEKWOWANEJ
    # wykonalby sie pierwszy raz przy pierwszej promocji, na zywej granicy. To jest dokladnie ta klasa awarii,
    # ktora perimetr zna z autopsji (regula baseline obecna i nieautoryzujaca niczego).
    # `jsonencode` calej reguly, nie jej wybranego pola: pytanie brzmi „czy dodanie czlonka zmienia regule",
    # a nie „czy zmienia dlugosc listy". Porownanie pelnej tresci lapie tez zmiane, ktorej nikt nie
    # przewidzial (np. gdyby ktos wrocil z lista pod innym polem). `md5` skraca to do jednej linii, ktora
    # helper `konsola` umie odczytac — a rozjazd i tak jest widoczny jako rozne skroty.
    klucz_all = "sort(keys(local.baseline_rules_all))[0]"
    klucz_enf = "sort(keys(local.baseline_rules_enforced))[0]"
    odcisk_all = f"md5(jsonencode(local.baseline_rules_all[{klucz_all}]))"

    czlonkowie_przed = konsola("length(local.members)")
    baseline_przed = konsola("length(local.baseline_rules_all)")
    odcisk_przed = konsola(odcisk_all)

    # Drugi czlonek dopisywany do WSPOLNEGO pliku (DEC-12), a nie jako nowy plik. Oryginal wraca w `finally`
    # z zapamietanych BAJTOW, nie z ponownego zrzutu YAML-a: material startera ma byc po tescie identyczny
    # co do bajta, inaczej selftest brudzilby drzewo, na ktorym sam orzeka o postaci kanonicznej.
    plik_czlonkow = ROOT / "perimeter/projects.yaml"
    kopia_zapasowa = plik_czlonkow.read_text()
    dokument = yaml.safe_load(kopia_zapasowa)
    dane = json.loads(json.dumps(dokument["members"][0]))
    dane["project_id"] = "prj-selftest-kopia"
    dane["project_number"] = "999999999999"
    dane["stage"] = "enforced"
    dokument["members"].append(dane)
    plik_czlonkow.write_text(yaml.safe_dump(dokument, allow_unicode=True, sort_keys=False))
    try:
        czlonkowie_po = konsola("length(local.members)")
        baseline_po = konsola("length(local.baseline_rules_all)")
        odcisk_po = konsola(odcisk_all)
        zasoby_po = konsola(f"join(\",\", local.baseline_rules_all[{klucz_all}].resources)")
        enforced_po = konsola("length(local.enforced_members)")
        baseline_enf = konsola("length(local.baseline_rules_enforced)")
        # `join`, a nie sama lista: `terraform console` drukuje liste WIELOLINIOWO, a helper czyta ostatnia
        # linie — czyli asercja badalaby nawias zamykajacy. Jedna linia jest tez porownywalna wprost.
        zasoby_enf = konsola(f"join(\",\", local.baseline_rules_enforced[{klucz_enf}].resources)")
    finally:
        plik_czlonkow.write_text(kopia_zapasowa)

    # Premisy sa czescia asercji: gdyby przykladowy czlonek albo baseline zniknal z materialu, ponizsze
    # rownosci byly by prawdziwe „bo nic nie ma", a test meldowalby zielono nie badajac niczego.
    check("kolaps baseline: premisa (jeden czlonek dry-run i niepusty baseline w materiale startera)",
          czlonkowie_przed == "1" and czlonkowie_po == "2" and enforced_po == "1"
          and baseline_przed not in ("0", "") and odcisk_przed not in ("", "null"),
          f"czlonkowie {czlonkowie_przed!r}->{czlonkowie_po!r}, enforced {enforced_po!r}, "
          f"reguly baseline {baseline_przed!r}, odcisk {odcisk_przed!r}")
    check("kolaps baseline: drugi czlonek NIE mnozy regul baseline",
          baseline_przed == baseline_po,
          f"regul baseline przy jednym czlonku={baseline_przed!r}, przy dwoch={baseline_po!r}")

    # TO JEST TEST DEC-11 i test defektu, ktory kosztowal replace obu regul baseline przy kazdym wniosku:
    # dodanie czlonka nie moze zmienic reguly baseline W OGOLE. Przed poprawka ten odcisk sie ZMIENIAL
    # (do listy `resources` dochodzil `projects/999999999999`), a `ingress_to.resources` jest ForceNew.
    check("baseline nie zalezy od czlonkostwa: drugi czlonek NIE ZMIENIA reguly zbiorczej",
          odcisk_przed == odcisk_po and odcisk_przed not in ("", "null"),
          f"odcisk reguly baseline przed={odcisk_przed!r} po={odcisk_po!r}")
    check("baseline nie zalezy od czlonkostwa: cel reguly to `*`, nie lista projektow",
          zasoby_po.strip('"') == "*", f"resources reguly baseline przy dwoch czlonkach={zasoby_po!r}")

    # KONFIGURACJA EGZEKWOWANA. Regula zbiorcza MUSI w niej powstac (inaczej promocja zabiera skanerowi
    # i raportowi naruszen dostep dokladnie w chwili, w ktorej zaczyna byc potrzebny). Zawezenie do czlonkow
    # `stage: enforced` robi od DEC-11 sam perimetr — `status.resources` zawiera wylacznie promowanych
    # (members.tf), a `*` znaczy „dowolny zasob W TEJ konfiguracji". Regula ma wiec byc IDENTYCZNA jak
    # w dry-run; rozjazd tresci miedzy konfiguracjami znaczylby, ze wrocila lista.
    check("kolaps baseline: regula zbiorcza POWSTAJE w konfiguracji egzekwowanej",
          baseline_enf == baseline_przed,
          f"regul baseline enforced={baseline_enf!r}, oczekiwane={baseline_przed!r}")
    check("baseline nie zalezy od czlonkostwa: enforced tez celuje w `*`",
          zasoby_enf.strip('"') == "*",
          f"resources reguly baseline w konfiguracji egzekwowanej={zasoby_enf!r}")

    # KOLEJNOSC DESTROY: regula ingress referuje access level po NAZWIE (string z YAML), wiec Terraform sam
    # nie zbuduje krawedzi i moze skasowac poziom przed regula — API odrzuca `you must first remove the
    # reference` (zmierzone na zywym ACM 2026-08-07, #1904). Mierzymy GRAF, ktory Terraform faktycznie
    # zbudowal, a nie obecnosc slowa `depends_on` w pliku: bez tego test potwierdzalby wlasny tekst.
    # Kontrola anty-tautologiczna: przed poprawka to samo zapytanie zwracalo 0 krawedzi.
    p = sh(["terraform", f"-chdir={tf}", "graph"])
    krawedzie = {
        (a, b)
        for a, b in re.findall(r'"([^"]+)"\s*->\s*"([^"]+)"', p.stdout)
    }
    poziom = "google_access_context_manager_access_level.level"
    for wariant in ("dry_run_ingress_policy", "ingress_policy"):
        regula = f"google_access_context_manager_service_perimeter_{wariant}.rule"
        check(f"graf: {wariant} zalezy od access levelu (kolejnosc destroy)",
              p.returncode == 0 and (regula, poziom) in krawedzie,
              f"brak krawedzi {regula} -> {poziom}; stderr={p.stderr[-300:]}")

    # Sekcje opcjonalne MUSZA byc opcjonalne NAPRAWDE. `count` na zasobie nie wystarcza: blok `locals` liczy
    # sie zawsze, wiec odwolanie do nieistniejacej sekcji wywraca `validate` — czyli funkcja opisana jako
    # opcjonalna jest w praktyce obowiazkowa. Wykryte przy pierwszym przygotowaniu prawdziwego testu na
    # organizacji, gdzie policy.yaml celowo nie mial ani kontraktu, ani monitoringu.
    polityka = ROOT / "perimeter/policy.yaml"
    oryginal = polityka.read_text()
    okrojona = yaml.safe_load(oryginal)
    for sekcja in ("contract", "monitoring", "baseline_ingress"):
        okrojona.pop(sekcja, None)
    polityka.write_text(yaml.safe_dump(okrojona, sort_keys=False, allow_unicode=True))
    p = sh(["terraform", f"-chdir={tf}", "validate"])
    check("validate przechodzi BEZ sekcji contract/monitoring/baseline_ingress",
          p.returncode == 0, p.stdout[-900:] + p.stderr[-900:])
    polityka.write_text(oryginal)


# --------------------------------------------------------------------- iam-bootstrap
def test_jeden_plik_projektow() -> None:
    """Niezmienniki układu jednoplikowego (DEC-12).

    NAJWAŻNIEJSZY test w tym pliku dotyczy jednej rzeczy: kanał wejściowy NIE MOŻE nadpisać wpisu członka,
    który już jest w perimetrze. Przy pliku na projekt pilnował tego `out.exists()` — warunek o systemie
    plików. Przy pliku wspólnym „plik istnieje" jest prawdą zawsze, więc gdyby ten warunek przeniesiono
    dosłownie, powtórne zgłoszenie zapisałoby `stage: dry-run` członkowi, który jest `enforced`: projekt
    traci ochronę pull requestem wyglądającym na onboarding, przechodzącym KAŻDĄ bramkę (nowy stan
    `dry-run` nie łamie żadnej reguły promocji) i kwalifikującym się do auto-merge'a.
    """
    print("\n== jeden plik projektow (DEC-12) ==")
    plik = ROOT / "perimeter/projects.yaml"
    kopia = plik.read_text()

    check("stary uklad zniknal: nie ma katalogu perimeter/members/",
          not (ROOT / "perimeter/members").exists())

    sys.path.insert(0, str(ROOT / "tools"))
    for modul in ("projects_file",):
        sys.modules.pop(modul, None)
    import projects_file  # noqa: E402 — modul zyje w rozpakowanym repo, nie w starterze

    try:
        wpisy = projects_file.wczytaj(ROOT)["members"]
        czlonek = wpisy[0]
        check("klucz czlonka to `<dywizja>-<project_id>` (adres w stanie Terraforma)",
              projects_file.klucz(czlonek) == f"{czlonek['division']}-{czlonek['project_id']}")

        # --- NIEZMIENNIK: powtorne zgloszenie czlonka `enforced` ---------------------------------------
        # Ustawiamy przykladowego czlonka na `enforced`, zeby test badal DOKLADNIE ten przypadek, ktory boli:
        # utrate ochrony, a nie samo „nie dubluj wpisu".
        dokument = projects_file.wczytaj(ROOT)
        dokument["members"][0]["stage"] = "enforced"
        projects_file.zapisz(ROOT, dokument)
        przed = plik.read_text()

        def zgloszenie(project_id, project_number, division=None):
            return sh([sys.executable, "tools/render_member.py",
                       "--division", division or czlonek["division"],
                       "--project-id", project_id,
                       "--project-number", str(project_number),
                       "--owner-group", "grp-example@example.com",
                       "--change-ref", "snow:RITM0000001",
                       "--approved-by", "net-approver@example.com",
                       "--profiles-json", json.dumps(czlonek["profiles"])], cwd=ROOT)

        r = zgloszenie(czlonek["project_id"], czlonek["project_number"])
        po = plik.read_text()
        check("NIEZMIENNIK: powtorne zgloszenie czlonka `enforced` jest ODRZUCANE",
              r.returncode != 0, (r.stdout + r.stderr)[-500:])
        check("NIEZMIENNIK: odrzucone zgloszenie NIE TKNELO pliku (stage nadal `enforced`)",
              po == przed and yaml.safe_load(po)["members"][0]["stage"] == "enforced",
              f"stage po probie={yaml.safe_load(po)['members'][0].get('stage')!r}")
        check("NIEZMIENNIK: komunikat mowi, ze projekt JUZ JEST czlonkiem (a nie o formacie wniosku)",
              "juz opisuje ten projekt" in (r.stdout + r.stderr))

        # Literowka w dywizji daje INNY klucz przy TYM SAMYM projekcie. Gdyby bramka pytala tylko o klucz
        # (albo tylko o `project_id`), taki wniosek przeszedlby jako onboarding nowego czlonka.
        r = zgloszenie(czlonek["project_id"], czlonek["project_number"], division="inna-dywizja")
        check("NIEZMIENNIK: ten sam projekt pod INNA dywizja tez jest odrzucany",
              r.returncode != 0 and plik.read_text() == przed, (r.stdout + r.stderr)[-400:])

        r = zgloszenie("prj-example-inny-projekt", czlonek["project_number"])
        check("NIEZMIENNIK: zgodny sam `project_number` (literowka w project_id) tez jest odrzucany",
              r.returncode != 0 and plik.read_text() == przed, (r.stdout + r.stderr)[-400:])

        # ANTY-TAUTOLOGIA: bramka, ktora odrzuca WSZYSTKO, przeszlaby trzy testy wyzej i nie bylaby bramka.
        r = zgloszenie("prj-example-nowy-czlonek", "555555555555")
        wpisy_po = projects_file.wczytaj(ROOT)["members"]
        check("ANTY-TAUTOLOGIA: zgloszenie NOWEGO projektu jest przyjmowane i dopisane na koncu",
              r.returncode == 0 and len(wpisy_po) == len(wpisy) + 1
              and wpisy_po[-1]["project_id"] == "prj-example-nowy-czlonek",
              (r.stdout + r.stderr)[-400:])
        check("dopisanie wpisu NIE PRZEPISUJE reszty pliku (bajty sprzed zmiany zostaja prefiksem)",
              plik.read_text().startswith(przed), "dopisanie zmodyfikowalo istniejaca tresc")
        check("dopisany wpis ma `stage: dry-run` niezaleznie od tresci zgloszenia",
              wpisy_po[-1]["stage"] == "dry-run")

        # --- bramka duplikatu: cztery warstwy ---------------------------------------------------------
        plik.write_text(kopia)

        # (1) strict loader — duplikat klucza mapy WEWNATRZ wpisu. To jest typowy wynik `merge=union`
        # na edycji tego samego wpisu i JEDYNY przypadek, ktorego nie widzi zadna regula o duplikatach:
        # dla parsera wpis jest jeden, tylko cicho ma inna tresc, niz wyglada.
        zdublowany_klucz = kopia.replace("  stage: dry-run\n", "  stage: dry-run\n  stage: enforced\n", 1)
        try:
            projects_file.dokument(zdublowany_klucz)
            zlapal = False
        except projects_file.BladPliku:
            zlapal = True
        check("bramka 1/4 (loader): duplikat klucza mapy w jednym wpisie RZUCA, a nie bierze ostatniego",
              zlapal)
        # ANTY-TAUTOLOGIA loadera: poprawny plik ma sie WCZYTAC.
        check("ANTY-TAUTOLOGIA: ten sam loader wczytuje poprawny plik",
              len(projects_file.dokument(kopia)["members"]) == len(wpisy))
        # I kontrola, ze `yaml.safe_load` faktycznie tego NIE lapie — czyli ze warstwa 1 nie jest ozdoba.
        check("premisa: `yaml.safe_load` na tym samym wejsciu MILCZY (bierze ostatni)",
              yaml.safe_load(zdublowany_klucz)["members"][0]["stage"] == "enforced")

        # (2) i (3) reguly OPA na surowej liscie + backstop na licznosci — przez realny kolektor.
        if have("conftest"):
            dokument = projects_file.wczytaj(ROOT)
            duplikat = json.loads(json.dumps(dokument["members"][0]))
            dokument["members"].append(duplikat)
            projects_file.zapisz(ROOT, dokument)
            decl = sh([sys.executable, "tools/collect_declarations.py"], cwd=ROOT)
            (ROOT / "duplikat.json").write_text(decl.stdout)
            r = sh(["conftest", "test", "--policy", "policy", "--namespace", "vpcsc.onboarding",
                    "duplikat.json"], cwd=ROOT)
            check("bramka 2/4 (OPA): zdublowany wpis jest ODRZUCANY",
                  decl.returncode == 0 and r.returncode != 0, r.stdout[-800:])
            check("bramka 3/4 (backstop): komunikat mowi o wpisie zgubionym przez mape",
                  "po cichu zgubiony" in r.stdout, r.stdout[-800:])

            # (4) renderer — ostatnia warstwa, ktorej nie da sie pominac ani zapomniec uruchomic.
            #
            # `terraform validate`, a NIE `terraform console`. Zmierzone przy pisaniu tego testu: console
            # jest REPL-em i przy tym samym bledzie konczy sie kodem 0, wypisujac ostrzezenie „some
            # expressions may produce unexpected results" i ZDEGRADOWANA wartosc (`1` zamiast bledu).
            # Asercja na console przechodzilaby wiec zawsze — i to jest dokladnie ten rodzaj testu, ktory
            # wyglada na uzbrojony. `validate` to zreszta ta sama komenda, ktora stoi w `validate.yml`.
            if have("terraform"):
                r = sh(["terraform", f"-chdir={ROOT / 'terraform'}", "validate", "-no-color"])
                check("bramka 4/4 (terraform): zdublowany klucz wywraca `validate` (Duplicate object key)",
                      r.returncode != 0 and "Duplicate object key" in (r.stdout + r.stderr),
                      (r.stdout + r.stderr)[-500:])
            plik.write_text(kopia)
            if have("terraform"):
                # ANTY-TAUTOLOGIA: ta sama komenda na poprawnym pliku MUSI byc zielona — inaczej mierzylibysmy
                # zepsute srodowisko, a nie bramke.
                r = sh(["terraform", f"-chdir={ROOT / 'terraform'}", "validate", "-no-color"])
                check("ANTY-TAUTOLOGIA: `validate` na poprawnym pliku jest ZIELONY",
                      r.returncode == 0, (r.stdout + r.stderr)[-400:])

        # --- postac kanoniczna ------------------------------------------------------------------------
        check("material startera jest w postaci kanonicznej",
              projects_file.zrzut(projects_file.dokument(kopia)) == kopia)
        niekanoniczny = "# komentarz, ktory pierwszy zapis bota skasowalby bez sladu\n" + kopia
        check("ANTY-TAUTOLOGIA: plik z komentarzem NIE jest kanoniczny (guard ma co lapac)",
              projects_file.zrzut(projects_file.dokument(niekanoniczny)) != niekanoniczny)

        # --- `merge=union` — NIEOBECNY, i to jest sprzezenie do pilnowania ----------------------------
        #
        # ZMIERZONE (`experiments/konflikty-ukladow/`): union przy DODAWANIU wpisow daje 10/10 zielonych
        # scalen i 201 wpisow zamiast 210 — zlepia bloki o identycznej strukturze w jeden wpis z dziesiecioma
        # polami `project_id`. Nie kupuje wiec nic: konflikt WIDOCZNY zamienia na plik, ktory bramka i tak
        # odrzuci, tyle ze po scaleniu. Kolizje rozwiazuje bot (`intake-rebase.yml`), nie sterownik scalania.
        #
        # Test pilnuje SPRZEZENIA, nie samej nieobecnosci: gdyby ktos kiedys union wlaczyl, wszystkie cztery
        # warstwy bramki duplikatu musza byc na miejscu. Dzis warunek jest spelniony trywialnie (union nie
        # ma), a asercja czeka na dzien, w ktorym przestanie byc trywialny.
        attrs = (ROOT / ".gitattributes").read_text()
        rego = (ROOT / "policy/onboarding.rego").read_text()
        aktywne = [w for w in attrs.splitlines()
                   if "merge=union" in w and not w.lstrip().startswith("#")]
        bramka = "members_list" in rego and "po cichu zgubiony" in rego
        check("`merge=union` NIE jest wlaczony na pliku czlonkow (zmierzone: gubi wpisy przy dodawaniu)",
              not aktywne, str(aktywne))
        check("gdyby `merge=union` byl wlaczony, bramka duplikatu MUSI istniec (sprzezenie)",
              (not aktywne) or bramka, f"union={bool(aktywne)} bramka_duplikatu={bramka}")
        check(".gitattributes TLUMACZY, dlaczego union jest nieobecny (odpowiedz na wracajaca propozycje)",
              "merge=union" in attrs and "201" in attrs and "intake-rebase" in attrs)
    finally:
        plik.write_text(kopia)
        for tymczasowy in ("duplikat.json",):
            (ROOT / tymczasowy).unlink(missing_ok=True)


def test_iam_bootstrap() -> None:
    """Stack nadający uprawnienia jest osobny (applikuje go zespół IAM), ale psuje się tak samo łatwo."""
    print("\n== iam-bootstrap ==")
    if not have("terraform"):
        check("terraform dostepny", False, "brak terraform na PATH")
        return
    d = ROOT / "iam-bootstrap"
    p = sh(["terraform", f"-chdir={d}", "fmt", "-check", "-recursive"])
    check("iam-bootstrap: fmt -check", p.returncode == 0, p.stdout + p.stderr)
    p = sh(["terraform", f"-chdir={d}", "init", "-backend=false", "-input=false"])
    check("iam-bootstrap: init -backend=false", p.returncode == 0, p.stdout[-600:] + p.stderr[-600:])
    p = sh(["terraform", f"-chdir={d}", "validate"])
    check("iam-bootstrap: validate", p.returncode == 0, p.stdout + p.stderr)

    # Guardy niżej liczą `terraform plan`, a ten wymaga ZAINICJALIZOWANEGO backendu — startowy jest GCS
    # z placeholderem, więc podmieniamy go na lokalny plikiem `*_override.tf`. Zabieg wyłącznie testowy,
    # w rozpakowanej kopii; `versions.tf` zostaje nietknięty i to on jest badany przez guard backendu niżej.
    # Ten sam mechanizm co w `test_terraform()` — patrz komentarz tam.
    (d / "zz_selftest_override.tf").write_text('terraform {\n  backend "local" {}\n}\n')
    p = sh(["terraform", f"-chdir={d}", "init", "-reconfigure", "-input=false"])
    check("iam-bootstrap: init z lokalnym backendem (override na czas testu)",
          p.returncode == 0, p.stdout[-500:] + p.stderr[-500:])

    body = (d / "main.tf").read_text()
    # NAJGROŹNIEJSZY footgun tego stacku: *_iam_binding jest authoritative dla roli na CAŁEJ organizacji
    # i przy pierwszym apply usunąłby wszystkie inne jej przypisania w firmie.
    # Szukamy DEKLARACJI zasobu, nie nazwy w tekście — plik zawiera komentarz ostrzegawczy z tą nazwą,
    # a test, który wywraca się na własnej dokumentacji, uczy tylko usuwania komentarzy.
    declared_bindings = re.findall(r'^resource\s+"(google_\w*_iam_binding)"', body, re.M)
    check("iam-bootstrap: zero zasobow *_iam_binding (tylko _member)",
          not declared_bindings, str(declared_bindings))
    # Custom rola nie może nieść operacji, których świadomie nie prosimy.
    for forbidden in ("servicePerimeters.create", "servicePerimeters.delete", "accessLevels.delete"):
        in_perms = f'"accesscontextmanager.{forbidden}",' in body
        check(f"iam-bootstrap: custom rola BEZ {forbidden}", not in_perms)
    # Guardrail WIF: warunek musi pinować repozytorium, nigdy `true`.
    check("iam-bootstrap: attribute_condition pinuje repozytorium",
          "assertion.repository ==" in body and 'attribute_condition = "true"' not in body)
    # Deny na SA używa formatu principal:// (allow-owy "serviceAccount:" tu NIE działa).
    check("iam-bootstrap: deny uzywa principal://.../serviceAccounts/",
          "principal://iam.googleapis.com/projects/-/serviceAccounts/" in body)

    # --- kontrakt zmiennej contract_reader_groups ----------------------------------------------------
    # DLACZEGO ten guard istnieje: zmienna ma `default = []`, więc `for_each` nie tworzy ANI JEDNEJ
    # instancji i ani fmt, ani validate, ani plan nigdy nie dotykają jej wartości. Trzy miejsca opisujące
    # jej format — walidacja w variables.tf, `member` w main.tf i przykład w terraform.tfvars.sample —
    # rozjechały się dokładnie dlatego, że nic ich ze sobą nie porównywało: walidacja WYMAGAŁA prefiksu
    # `group:`, main.tf ten sam prefiks DOKLEJAŁ, a przykład go NIE MIAŁ. Każda niepusta wartość była
    # zepsuta w jedną albo w drugą stronę (`group:group:...` w IAM albo błąd walidacji przy odkomentowaniu
    # przykładu), a selftest przez cały ten czas świecił na zielono.
    #
    # Guard mierzy EFEKT — to, co realnie wyszłoby do IAM — a nie tekst plików. Dzięki temu przeżyje
    # ŚWIADOME odwrócenie kontraktu (prefiks może mieszkać po stronie zmiennej albo po stronie main.tf)
    # i mimo to odrzuci obie kombinacje sprzeczne: podwójny prefiks ORAZ goły adres jako principala.
    #
    # SYGNAŁEM JEST `plan`, NIE `console`: zmierzone na tym stacku — `terraform console` kończy się kodem 0
    # MIMO odrzuconej walidacji (wypisuje błąd i liczy dalej). Test oparty na jego kodzie wyjścia
    # przepuszczałby wszystko, czyli byłby dokładnie tą bramką-atrapą, której brak wpuścił tu sprzeczność.
    # `plan` działa bez poświadczeń GCP, bo stan jest pusty i wszystkie zasoby są `create` — provider nie
    # woła API.
    sample = (d / "terraform.tfvars.sample").read_text()
    m = re.search(r"^#\s*contract_reader_groups\s*=\s*\[(.*?)\]", sample, re.M)
    przyklady = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    check("iam-bootstrap: tfvars.sample pokazuje przyklad contract_reader_groups",
          bool(przyklady), "brak zakomentowanego przykladu — nie ma czego porownac z walidacja")

    baza = ["-var=org_id=123456789012", "-var=identity_project_id=prj-example-identity",
            "-var=github_repository=example-org/gcp-vpc-sc", "-var=state_bucket=bkt-example-tf-state",
            "-var=contracts_bucket=bkt-example-contracts"]

    def plan_grup(wartosci, out=None):
        cmd = ["terraform", f"-chdir={d}", "plan", "-no-color", "-input=false", "-lock=false"]
        cmd += [f"-out={out}"] if out else []
        return sh(cmd + baza + [f"-var=contract_reader_groups={json.dumps(wartosci)}"])

    if przyklady:
        # 1. Przykład z sample'a MUSI przejść walidację. To pilnuje trzeciego miejsca: dokumentacja, którą
        #    czytelnik odkomentowuje, nie może padać na bramce z pliku obok.
        p = plan_grup(przyklady, out="zz_selftest.tfplan")
        check("iam-bootstrap: przyklad z tfvars.sample przechodzi walidacje contract_reader_groups",
              p.returncode == 0, (p.stdout[-400:] + p.stderr[-700:]))

        # 2. Renderowany principal musi nieść prefiks `group:` DOKŁADNIE RAZ. Oczekiwanie liczymy z tego
        #    samego przykładu, więc guard nie przyklepuje jednej ze stron sporu — sprawdza ich ZGODNOŚĆ.
        member = ""
        if p.returncode == 0:
            s = sh(["terraform", f"-chdir={d}", "show", "-json", "zz_selftest.tfplan"])
            zasoby = json.loads(s.stdout)["planned_values"]["root_module"].get("resources", [])
            member = next((r["values"]["member"] for r in zasoby
                           if r["type"] == "google_storage_bucket_iam_member"
                           and r["name"] == "contract_reader"), "")
        oczekiwany = "group:" + przyklady[0].removeprefix("group:")
        check("iam-bootstrap: walidacja i main.tf zgodne co do prefiksu group: (dokladnie jeden)",
              member == oczekiwany,
              f"member={member!r}, oczekiwano={oczekiwany!r} — walidacja i renderowanie rozjechaly sie")
        (d / "zz_selftest.tfplan").unlink(missing_ok=True)

        # 3. Forma PRZECIWNA do przykładu musi być odrzucona. Gdyby przechodziły obie, ten sam kontrakt
        #    renderowałby się raz dobrze, a raz z podwójnym prefiksem — zależnie od tego, skąd kto skopiował
        #    wartość. Jeden dopuszczalny format, nie dwa.
        wzor = przyklady[0]
        przeciwna = wzor.removeprefix("group:") if wzor.startswith("group:") else "group:" + wzor
        p = plan_grup([przeciwna])
        check("iam-bootstrap: przeciwna forma wpisu contract_reader_groups jest ODRZUCANA",
              p.returncode != 0, f"rc={p.returncode} dla {przeciwna!r} — walidacja przepuszcza oba formaty")

    # 4. Intencja bezpieczeństwa, niezależna od tego, po której stronie mieszka prefiks: kontrakt niesie
    #    nazwy projektów, dywizji i profili, więc principal otwarty na świat albo przypięty do konkretnego
    #    człowieka nie ma prawa tędy wejść.
    for zly in ["allUsers", "allAuthenticatedUsers", "user:ktos@example.com", "domain:example.com"]:
        check(f"iam-bootstrap: contract_reader_groups ODRZUCA {zly}",
              plan_grup([zly]).returncode != 0, "principal spoza grup przeszedl walidacje")

    # --- prefiksy obiektow: state_prefix i contract_prefix -------------------------------------------
    # DLACZEGO OBA NARAZ, TYM SAMYM KODEM: to bliźniaki. Jedyne, co robią, to wklejenie się do tego samego
    # wyrażenia IAM `resource.name.startsWith(".../objects/<prefiks>")`. Mimo to rozjechały się — `state_prefix`
    # miał walidację od początku, `contract_prefix` nie miał ŻADNEJ (#1912). Terraform nie ma funkcji
    # użytkownika (blok `function` to OpenTofu), więc warunku nie da się wyciągnąć do jednego miejsca w HCL
    # i jedynym spinaczem obu jest TEN guard. Pętla po nazwach, nie dwa osobne testy: test dopisany wyłącznie
    # dla jednej zmiennej odtworzyłby dokładnie tę asymetrię, która ten defekt wpuściła.
    #
    # DWA TRYBY AWARII, PRZECIWNE — i dlatego sprawdzamy oba:
    #   * wiodący `/`  -> warunek nie pasuje do NICZEGO. Pada GŁOŚNO (403 u konsumenta), więc ktoś to zgłosi;
    #   * pusty string -> warunek degeneruje się do `.../objects/`, czyli pasuje do KAŻDEGO obiektu w buckecie.
    #     Grant nie znika — po CICHU ROZSZERZA się na cały bucket. Nic nie pada, więc nikt nie zgłasza.
    #     Ten tryb jest groźniejszy i to on jest powodem, dla którego guard niżej mierzy TREŚĆ warunku,
    #     a nie sam kod wyjścia: „plan przeszedł" nie odróżnia zawężenia od jego braku.
    #
    # `plan`, nie `console` — ta sama lekcja co przy contract_reader_groups: `terraform console` kończy się
    # kodem 0 MIMO odrzuconej walidacji, więc test na jego kodzie wyjścia byłby bramką-atrapą.
    dobre_prefiksy = {"state_prefix": "vpc-sc/perimeter", "contract_prefix": "vpc-sc/"}

    def plan_prefiksy(wartosci, out=None):
        cmd = ["terraform", f"-chdir={d}", "plan", "-no-color", "-input=false", "-lock=false"]
        cmd += [f"-out={out}"] if out else []
        return sh(cmd + baza + [f"-var={k}={v}" for k, v in wartosci.items()])

    for zmienna, dobra in dobre_prefiksy.items():
        p = plan_prefiksy({**dobre_prefiksy, zmienna: "/" + dobra})
        check(f"iam-bootstrap: {zmienna} ODRZUCA wiodacy / (warunek IAM nie pasowalby do zadnego obiektu)",
              p.returncode != 0, f"rc={p.returncode} — plan przeszedl mimo prefiksu '/{dobra}'")
        p = plan_prefiksy({**dobre_prefiksy, zmienna: ""})
        check(f"iam-bootstrap: {zmienna} ODRZUCA pusty string (grant rozszerzylby sie na CALY bucket)",
              p.returncode != 0, f"rc={p.returncode} — plan przeszedl mimo pustego prefiksu")

    # ANTY-TAUTOLOGIA + POMIAR EFEKTU jednym przebiegiem. Same odrzucenia nie dowodzą niczego: walidacja
    # odrzucająca wszystko przeszłaby je w komplecie. Wartości poprawne muszą PRZEJŚĆ, a zrenderowany warunek
    # — ten, który realnie wylądowałby w IAM — musi NIEŚĆ prefiks. Czytamy go z `terraform show -json`, bo
    # guard tekstowy („czy w variables.tf stoi blok validation") przeszedłby także wtedy, gdyby warunek
    # pilnował czegoś zupełnie innego niż zawężenie zasięgu.
    p = plan_prefiksy(dobre_prefiksy, out="zz_prefiksy.tfplan")
    check("iam-bootstrap: poprawne prefiksy PRZECHODZA plan (test anty-tautologiczny)",
          p.returncode == 0, (p.stdout[-400:] + p.stderr[-700:]))
    warunki = {}
    if p.returncode == 0:
        s = sh(["terraform", f"-chdir={d}", "show", "-json", "zz_prefiksy.tfplan"])
        for r in json.loads(s.stdout)["planned_values"]["root_module"].get("resources", []):
            if r["type"] == "google_storage_bucket_iam_member":
                for c in r["values"].get("condition") or []:
                    warunki.setdefault(r["name"], []).append(c["expression"])
    (d / "zz_prefiksy.tfplan").unlink(missing_ok=True)

    # `state_list` NIE jest tu wymieniony celowo: to grant `legacyBucketReader` na LISTOWANIE bucketa,
    # który warunku mieć NIE MOŻE, bo zasobem tego wywołania jest bucket, a nie obiekt (WHY w main.tf).
    for zasob, zmienna in (("state", "state_prefix"),
                           ("contract_writer", "contract_prefix"),
                           ("contract_reader_plan", "contract_prefix")):
        koncowka = f'/objects/{dobre_prefiksy[zmienna]}")'
        wyrazenia = warunki.get(zasob, [])
        check(f"iam-bootstrap: warunek IAM `{zasob}` niesie prefiks z {zmienna} (nie konczy sie na /objects/)",
              bool(wyrazenia) and all(w.endswith(koncowka) for w in wyrazenia),
              f"expressions={wyrazenia!r}, oczekiwana koncowka={koncowka!r}")

    # --- backend: stan tego stacku NIE MOZE byc zapisywalny przez pipeline perimetru -----------------
    # DLACZEGO TEN GUARD ISTNIEJE: `iam-bootstrap/versions.tf` przez caly czas nie mial bloku `backend`,
    # wiec stan byl lokalny — czyli w praktyce zaden. Na wdrozeniu tego materialu `plan` ze swiezego klonu
    # pokazal 23 zasoby DO UTWORZENIA przy dwoch zamierzonych: Terraform nie znal ani jednego z zywych kont,
    # rol i puli WIF. `apply` z takiego klonu tworzy warstwe uprawnien od nowa, czesciowo padajac na
    # „already exists". Cala reszta selftestu byla wtedy zielona, bo `init -backend=false` (potrzebny, zeby
    # bramki chodzily bez chmury) nie odroznia „backend zdalny" od „backendu nie ma".
    #
    # DRUGA POLOWA GUARDU JEST WAZNIEJSZA OD PIERWSZEJ. Sam zdalny backend nie wystarczy: prefiks musi byc
    # ROZLACZNY z tym, ktory `main.tf` oddaje kontom CI. Konta `plan`/`apply` maja `storage.objectAdmin`
    # z warunkiem `resource.name.startsWith(".../objects/<state_prefix>")` — wspolny prefiks znaczy, ze
    # pipeline perimetru moze NADPISAC stan stacku, ktory nadaje mu uprawnienia. Warunek to `startsWith`,
    # nie rownosc, wiec „prawie rozlaczny" (`vpc-sc/perimeter-iam` przy `vpc-sc/perimeter`) jest po cichu
    # NIEROZLACZNY i to jest realny tryb awarii, nie teoria.
    #
    # Porownujemy z warunkiem WYRENDEROWANYM przez plan (`warunki["state"]` wyzej), a nie z tekstem
    # variables.tf: mierzymy to, co realnie wyladuje w IAM.
    def backend_gcs(plik: pathlib.Path) -> dict | None:
        m = re.search(r'backend\s+"gcs"\s*\{(.*?)\n\s*\}', plik.read_text(), re.S)
        return dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', m.group(1))) if m else None

    be = backend_gcs(d / "versions.tf")
    check("iam-bootstrap: ma ZDALNY backend gcs (stan lokalny = stanu nie ma)", be is not None,
          "brak bloku backend \"gcs\" w iam-bootstrap/versions.tf")
    # Prefiks oddany kontom CI czytamy z wyrenderowanego warunku IAM, nie z pliku zmiennych.
    nadany = next((re.search(r'/objects/(.*)"\)$', w).group(1) for w in warunki.get("state", [])
                   if re.search(r'/objects/(.*)"\)$', w)), None)
    check("iam-bootstrap: znany prefiks oddany kontom CI (z warunku IAM, nie z tekstu)", nadany is not None)
    if be is not None and nadany is not None:
        check("iam-bootstrap: prefiks stanu ROZLACZNY z tym, ktory maja konta CI perimetru",
              not be.get("prefix", "").startswith(nadany),
              f"backend prefix={be.get('prefix')!r} wpada pod warunek IAM startsWith({nadany!r})")

    # ANTY-TAUTOLOGIA: guard musi PASC po rozbrojeniu. Bez tego „rozlaczny" przechodziloby takze wtedy,
    # gdyby regex nic nie znajdowal — a to jest dokladnie ten sposob, w jaki bramka staje sie ozdoba.
    oryginal_versions = (d / "versions.tf").read_text()
    if be is not None and nadany is not None:
        kolizja = oryginal_versions.replace(f'prefix = "{be["prefix"]}"', f'prefix = "{nadany}-iam"')
        (d / "versions.tf").write_text(kolizja)
        zly = backend_gcs(d / "versions.tf")
        check("iam-bootstrap: guard rozlacznosci PADA na prefiksie wpadajacym pod warunek (anty-tautologia)",
              zly is not None and zly.get("prefix", "").startswith(nadany),
              f"po podmianie prefix={zly and zly.get('prefix')!r} — guard nie zauwazylby kolizji")
        (d / "versions.tf").write_text(re.sub(r'\n\s*backend\s+"gcs"\s*\{.*?\n\s*\}\n', "\n",
                                              oryginal_versions, flags=re.S))
        check("iam-bootstrap: guard backendu PADA po usunieciu bloku (anty-tautologia)",
              backend_gcs(d / "versions.tf") is None,
              "regex znalazl backend w pliku, z ktorego zostal usuniety")
        (d / "versions.tf").write_text(oryginal_versions)

    # --- monitoring: konto apply musi UMIEC ODCZYTAC to, czym zarzadza -------------------------------
    # DLACZEGO TEN GUARD ISTNIEJE: `terraform apply` zaczyna od REFRESHU, wiec apply jest nadzbiorem planu
    # i musi czytac takze zasoby, ktorych w danym przebiegu nie zmienia. Przez caly czas konto apply nie
    # mialo do metryk i alertow ZADNEGO prawa — plan byl zielony (org-level role read-only konta plan),
    # a apply padal na `403 logging.logMetrics.get`, i to przy KAZDEJ zmianie. Zaden test tego nie widzial,
    # bo wszystkie mierzyly plan.
    #
    # Guard mierzy EFEKT z plan-JSON: kto dostaje role i jakie uprawnienia ta rola niesie. Guard tekstowy
    # („czy w main.tf stoi google_project_iam_member") przeszedlby takze wtedy, gdyby rola trafila do
    # niewlasciwego konta albo nie niosla uprawnien odczytu.
    mon_projekt = "prj-example-monitoring"

    def plan_monitoring(wartosc, out):
        cmd = ["terraform", f"-chdir={d}", "plan", "-no-color", "-input=false", "-lock=false", f"-out={out}"]
        return sh(cmd + baza + [f"-var=monitoring_project_id={wartosc}"])

    def zasoby_planu(out):
        s = sh(["terraform", f"-chdir={d}", "show", "-json", out])
        return json.loads(s.stdout)["planned_values"]["root_module"].get("resources", [])

    # 1. BEZPIECZNA DEGRADACJA: puste = sekcja monitoring w policy.yaml wylaczona, zero grantow.
    #    Bez tego wariantu wdrozenie bez monitoringu dostawaloby granty w projekcie, ktorego nie ma.
    p = plan_monitoring("", "zz_mon_off.tfplan")
    zasoby = zasoby_planu("zz_mon_off.tfplan") if p.returncode == 0 else []
    check("iam-bootstrap: puste monitoring_project_id NIE tworzy zadnego grantu monitoringu",
          p.returncode == 0 and not [r for r in zasoby if "monitoring" in r["name"]],
          f"rc={p.returncode}, zasoby={[r['address'] for r in zasoby if 'monitoring' in r['name']]}")
    (d / "zz_mon_off.tfplan").unlink(missing_ok=True)

    # 2. WLACZONE: rola istnieje, niesie uprawnienia ODCZYTU (nie tylko zapisu) i idzie do konta APPLY.
    p = plan_monitoring(mon_projekt, "zz_mon_on.tfplan")
    check("iam-bootstrap: niepuste monitoring_project_id PRZECHODZI plan (test anty-tautologiczny)",
          p.returncode == 0, (p.stdout[-400:] + p.stderr[-700:]))
    rola, przypisania = {}, []
    if p.returncode == 0:
        for r in zasoby_planu("zz_mon_on.tfplan"):
            if r["type"] == "google_project_iam_custom_role" and r["name"] == "monitoring_writer":
                rola = r["values"]
            if r["type"] == "google_project_iam_member" and r["name"] == "apply_monitoring":
                przypisania.append(r["values"])
    (d / "zz_mon_on.tfplan").unlink(missing_ok=True)

    perms = set(rola.get("permissions") or [])
    # Uprawnienia ODCZYTU sa tu rownie obowiazkowe jak zapis — to na nich padal refresh.
    for perm in ("logging.logMetrics.get", "monitoring.alertPolicies.get"):
        check(f"iam-bootstrap: rola monitoringu niesie {perm} (bez tego pada REFRESH, nie zapis)",
              perm in perms, f"permissions={sorted(perms)}")
    check("iam-bootstrap: rola monitoringu jest WASKA (bez sinkow i kubelkow logow)",
          perms and not {p for p in perms if p.startswith(("logging.sinks", "logging.buckets", "logging.views"))},
          f"permissions={sorted(perms)}")
    check("iam-bootstrap: rola monitoringu powstaje w projekcie z monitoring_project_id",
          rola.get("project") == mon_projekt, f"project={rola.get('project')!r}")

    # ANTY-TAUTOLOGIA po drugiej stronie: konto plan ma zostac read-only. Gdyby rola trafila do obu,
    # guard wyzej nadal by przeszedl, a niezmiennik „plan nie ma ani jednego uprawnienia zapisujacego"
    # zniknalby bez sladu.
    czlonkowie = [a.get("member", "") for a in przypisania]
    check("iam-bootstrap: rola monitoringu idzie do konta APPLY",
          any("sa-vpcsc-apply@" in m for m in czlonkowie), f"member={czlonkowie!r}")
    check("iam-bootstrap: rola monitoringu NIE idzie do konta plan (plan zostaje read-only)",
          not any("sa-vpcsc-plan@" in m for m in czlonkowie), f"member={czlonkowie!r}")

    # --- warstwa deny: odczyt zawezony, zapis za flaga ------------------------------------------------
    # DLACZEGO TEN GUARD ISTNIEJE: `403` z `denypolicies.get` jest NIEODROZNIALNY od braku zasobu, wiec
    # przez caly czas nie dalo sie powiedziec, czy guardrail stoi — `terraform plan` pokazywal `1 to add`
    # w obu przypadkach, a `import` padal. Odczyt (rola wlasna) i zapis (`roles/iam.denyAdmin`, jedyna
    # rola z `denypolicies.create`) maja tu wiec ROZNYCH wlascicieli i to jest niezmiennik, nie detal.
    def plan_deny(flaga, out):
        cmd = ["terraform", f"-chdir={d}", "plan", "-no-color", "-input=false", "-lock=false", f"-out={out}"]
        return sh(cmd + baza + [f"-var=manage_deny_policy={flaga}"])

    wyniki = {}
    for flaga in ("true", "false"):
        out = f"zz_deny_{flaga}.tfplan"
        p = plan_deny(flaga, out)
        wyniki[flaga] = zasoby_planu(out) if p.returncode == 0 else None
        check(f"iam-bootstrap: plan przechodzi przy manage_deny_policy={flaga}",
              p.returncode == 0, (p.stdout[-300:] + p.stderr[-600:]))
        (d / out).unlink(missing_ok=True)

    def typy(flaga, typ):
        return [r for r in (wyniki[flaga] or []) if r["type"] == typ]

    # ANTY-TAUTOLOGIA W OBIE STRONY: guard sprawdzajacy tylko `false` przeszedlby takze wtedy, gdyby zasob
    # zniknal z pliku na zawsze — czyli chwalilby usuniecie warstwy, ktorej pilnuje.
    check("iam-bootstrap: manage_deny_policy=true TWORZY polityke deny",
          len(typy("true", "google_iam_deny_policy")) == 1)
    check("iam-bootstrap: manage_deny_policy=false NIE tworzy polityki deny (swiadoma rezygnacja)",
          not typy("false", "google_iam_deny_policy"))
    # Odczyt zostaje TAKZE przy wylaczonym zapisie — i to jest sedno. Wdrozenie bez `roles/iam.denyAdmin`
    # nie tworzy polityki, ale musi umiec sprawdzic, czy ktos nie utworzyl jej obok, poza tym stackiem.
    czytelnik = [r for r in (wyniki["false"] or [])
                 if r["type"] == "google_organization_iam_custom_role" and r["name"] == "deny_reader"]
    check("iam-bootstrap: rola ODCZYTU deny powstaje takze przy manage_deny_policy=false",
          len(czytelnik) == 1)

    perms_deny = set((czytelnik[0]["values"].get("permissions") if czytelnik else []) or [])
    check("iam-bootstrap: rola odczytu deny niesie get+list", {"iam.denypolicies.get", "iam.denypolicies.list"} <= perms_deny,
          f"permissions={sorted(perms_deny)}")
    # Te trzy maja `customRolesSupportLevel = NOT_SUPPORTED`: dopisanie ich tutaj nie daje zapisu, tylko
    # wywraca apply. Guard jest wiec ostrzezeniem przed pozorna „naprawa" braku uprawnien do apply.
    # `perms_deny` MUSI byc niepuste, inaczej ten guard przechodzi takze wtedy, gdy plan padl albo rola
    # zniknela z pliku — czyli chwali brak roli za to, ze nie ma w niej uprawnien zapisu.
    zapisujace = {p for p in perms_deny if p.startswith("iam.denypolicies.") and not p.endswith((".get", ".list"))}
    check("iam-bootstrap: rola odczytu deny BEZ uprawnien zapisu (i tak NOT_SUPPORTED w roli wlasnej)",
          bool(perms_deny) and not zapisujace, f"permissions={sorted(perms_deny)}, zapisujace={sorted(zapisujace)}")

    # Kontrakt `deny_reader_principals` — ten sam tryb awarii co przy `contract_reader_groups`: `default = []`
    # sprawia, ze zadna sciezka planu nigdy nie dotyka wartosci, wiec walidacja i przyklad w tfvars moga sie
    # rozjechac w ciszy. Mierzymy WYNIK planu, nie tekst.
    def plan_principals(wartosc):
        return sh(["terraform", f"-chdir={d}", "plan", "-no-color", "-input=false", "-lock=false"]
                  + baza + [f"-var=deny_reader_principals={json.dumps(wartosc)}"])

    check("iam-bootstrap: deny_reader_principals PRZYJMUJE pelnego principala (test anty-tautologiczny)",
          plan_principals(["group:grp-example-iam@example.com"]).returncode == 0)
    for zly in ("domain:example.com", "allUsers", "grp-example-iam@example.com"):
        check(f"iam-bootstrap: deny_reader_principals ODRZUCA {zly}",
              plan_principals([zly]).returncode != 0)

    sample_deny = re.search(r"^#\s*deny_reader_principals\s*=\s*\[(.*?)\]", sample, re.M)
    przyklad_deny = re.findall(r'"([^"]+)"', sample_deny.group(1)) if sample_deny else []
    check("iam-bootstrap: przyklad deny_reader_principals z tfvars.sample przechodzi walidacje",
          bool(przyklad_deny) and plan_principals(przyklad_deny).returncode == 0,
          f"przyklad={przyklad_deny!r}")


# --------------------------------------------------------------------- narzedzie deny_check
def test_deny_check() -> None:
    """Trzy werdykty narzedzia rozstrzygajacego, czy guardrail istnieje — bo dwa to za malo.

    CALA WARTOSC tego skryptu polega na tym, ze NIE MYLI `403` z `404`. Test, ktory sprawdza wylacznie
    sciezke `200`, przeszedlby takze na implementacji raportujacej odmowe odczytu jako „nie ma" — czyli
    na dokladnie tym bledzie, dla ktorego to narzedzie powstalo. Dlatego mierzymy WSZYSTKIE trzy kody.

    `curl` i `gcloud` sa tu podmienione na zaslepki: sprawdzamy LOGIKE werdyktu, a nie API Google.
    """
    print("\n== deny_check ==")
    skrypt = ROOT / "tools" / "deny_check.sh"
    check("deny_check: narzedzie rozpakowane i wykonywalne",
          skrypt.exists() and os.access(skrypt, os.X_OK))
    if not skrypt.exists():
        return

    stub = ROOT / "zz_stub_bin"
    stub.mkdir(exist_ok=True)
    (stub / "gcloud").write_text("#!/usr/bin/env bash\necho stub-token\n")
    # Zaslepka `curl` honoruje `-o <plik>` i `-w %{http_code}` — czyli dokladnie te dwa zachowania, na
    # ktorych opiera sie skrypt. Kod HTTP przychodzi ze zmiennej srodowiskowej testu.
    (stub / "curl").write_text(
        "#!/usr/bin/env bash\nout=\"\"\n"
        "while [ $# -gt 0 ]; do case \"$1\" in -o) shift; out=\"$1\";; esac; shift; done\n"
        "[ -n \"$out\" ] && printf '{\"name\":\"stub\"}' > \"$out\"\n"
        "printf '%s' \"$STUB_HTTP\"\n")
    for f in ("gcloud", "curl"):
        (stub / f).chmod(0o755)

    srodowisko = dict(os.environ, PATH=f"{stub}:{os.environ['PATH']}")
    kody = {}
    for http, oczekiwany, opis in (("200", 0, "ISTNIEJE"), ("404", 1, "NIE MA"), ("403", 2, "NIE WIADOMO")):
        p = sh([str(skrypt), "--org", "123456789012"], env=dict(srodowisko, STUB_HTTP=http))
        kody[http] = p.returncode
        check(f"deny_check: HTTP {http} -> {opis} (kod {oczekiwany})", p.returncode == oczekiwany,
              f"rc={p.returncode}, out={p.stdout[-200:]}{p.stderr[-200:]}")

    # NAJWAZNIEJSZA ASERCJA TEGO TESTU: gdyby ktos „uproscil" skrypt do dwoch werdyktow, guardy wyzej
    # moglyby zostac przepisane pod nowe kody, a ten warunek nadal odrzuci sklejenie odmowy z brakiem.
    check("deny_check: 403 i 404 daja ROZNE kody wyjscia (odmowa to nie „nie ma”)",
          kody.get("403") != kody.get("404"), f"kody={kody}")
    shutil.rmtree(stub, ignore_errors=True)

    # --- procedura testu warstwy Deny: MUSI niesc kontrole pozytywna ---------------------------------
    # DLACZEGO TO JEST GUARD, A NIE AKAPIT W DOKUMENTACJI. Zmierzone na zywej organizacji: odmowa
    # z polityki deny wyglada w API DOKLADNIE tak samo jak brak roli —
    #   PERMISSION_DENIED: The caller does not have permission.
    # bez nazwy polityki, reguly i bez slowa „deny". Procedura oparta na „komenda ma pasc" przechodzi
    # wiec rowniez na wdrozeniu, ktore tej warstwy NIE MA — to jest ten falszywy dowod, ktory stal
    # w tym README, dopoki polityki nie bylo. Rozstrzyga Policy Troubleshooter, i dopiero PARA krotek:
    # zakazana (allow GRANTED + deny DENIED) oraz kontrolna (uprawnienie spoza polityki -> CAN_ACCESS).
    # Sama krotka zakazana przeszlaby takze przy zepsutej impersonacji, ktora odmawia wszystkiego.
    readme = (ROOT / "iam-bootstrap/README.md").read_text()
    check("README deny: procedura wskazuje Policy Troubleshooter, nie tresc komunikatu bledu",
          "policytroubleshooter.googleapis.com/v3/iam:troubleshoot" in readme)
    check("README deny: dowodem jest PARA pol (allow GRANTED + deny DENIED), nie samo CANNOT_ACCESS",
          "ALLOW_ACCESS_STATE_GRANTED" in readme and "DENY_ACCESS_STATE_DENIED" in readme)
    check("README deny: procedura niesie KONTROLE POZYTYWNA (test anty-tautologiczny)",
          "CAN_ACCESS" in readme
          and "DENY_ACCESS_STATE_NOT_DENIED" in readme
          and "servicePerimeters.update" in readme)
    # Odpowiedz na pytanie, ktore pada przy kazdym wdrozeniu i decyduje, czy ta warstwa cokolwiek znaczy.
    check("README deny: zapisane, KTO trzyma roles/iam.denyAdmin (rozlacznie z wlascicielem perimetru)",
          "Kto ma trzymać `roles/iam.denyAdmin`" in readme)


# --------------------------------------------------------------------- kontrakt
def test_contract() -> None:
    """Kontrakt zastępuje submodule — jego wartość polega na tym, CZEGO w nim nie ma."""
    print("\n== kontrakt ==")
    body = (ROOT / "terraform/contract.tf").read_text()

    # Pola wypisane jawnie. `jsonencode(local.<coś-ogólnego>)` to dokładnie ten błąd, po którym kontrakt
    # zamienia się w drugą kopię state'u.
    check("kontrakt buduje dokument JAWNIE (bez jsonencode na zbiorczym locals)",
          "jsonencode(local.contract_document)" in body and "jsonencode(local.policy)" not in body)

    # Nie publikujemy treści access levels (zakresy IP, device policy) — tylko nazwy.
    check("kontrakt publikuje tylko NAZWY access levels",
          "sort(keys(local.access_levels))" in body)

    # Reguły i tożsamości nie wychodzą na zewnątrz: sekcja members ma dokładnie trzy pola.
    members_block = body[body.find("members = lookup"):body.find("attribute_budget = local.contract_budget")]
    for forbidden in ("identities", "operations", "access_levels ="):
        check(f"kontrakt: sekcja members bez `{forbidden.strip(' =')}`", forbidden not in members_block)

    # Guard na wspólny bucket — jeden błąd w IAM nie może odsłonić state'u.
    check("kontrakt: precondition na bucket inny niz bucket stanu",
          "precondition" in body and 'lookup(local.contract, "state_bucket", "")' in body)

    # Paczka bramek wypuszcza REGUŁY, nie dane. Gdyby ktoś dodał tam perimeter/, wracamy do problemu
    # submodule'a — dlatego to jest test, nie komentarz.
    gates = (ROOT / ".github/workflows/publish-gates.yml").read_text()
    # Szukamy INSTRUKCJI KOPIOWANIA, nie wzmianki: plik zawiera komentarz wyjaśniający, dlaczego perimeter/
    # do paczki NIE wchodzi. Guard dopasowujący tekst trafiałby w tę dokumentację.
    copies_perimeter = re.search(r"^\s*cp\s+(-R\s+)?perimeter", strip_heredocs(gates), re.M)
    check("paczka bramek NIE kopiuje katalogu perimeter/", copies_perimeter is None,
          copies_perimeter.group(0) if copies_perimeter else "")
    check("paczka bramek zawiera schemas i policy",
          "cp -R schemas" in gates and "cp -R policy" in gates)

    # Pusta lista czlonkow jest dwuznaczna („nikogo nie ma" kontra „nie publikujemy"), a konsument sprawdza
    # na niej, czy jego projekt juz jest w perimetrze. Bez flagi ta bramka bylaby cicho nieobecna.
    check("kontrakt niesie flage members_published (pusta lista nie jest dwuznaczna)",
          "members_published = local.contract_enabled &&" in body)

    # Action zespołu nie może już wymagać submodule'a.
    action = (ROOT / "contrib/action.yml").read_text()
    check("contrib/action: brak zaleznosci od submodule", "submodules: true" not in action)
    # Kontrakt i bramki jada TA SAMA droga: release repozytorium perimetru. `gcloud` w tym pliku oznaczalby
    # powrot do wymagania tozsamosci w GCP po stronie dywizji — czyli do stanu, ktory ta konstrukcja usuwa.
    check("contrib/action: pobiera kontrakt i paczke bramek z release'ow (bez gcloud)",
          "gh release download contract" in action and "gates.tar.gz" in action and "gcloud" not in action,
          f"kontrakt={'gh release download contract' in action} gcloud={'gcloud' in action}")

    # Do czego kontrakt SLUZY po stronie zespolu: rozstrzyga „czy moge o to wnioskowac" i „czy to juz jest
    # w perimetrze" BEZ dostepu do repo perimetru. Uruchamiamy realny blok walidacji z validate-local.sh
    # (wyciety z heredoca), zeby to byla bramka, a nie akapit w dokumentacji.
    vlocal = (ROOT / "contrib/validate-local.sh").read_text()
    # split po znaczniku, a potem po pierwszym newline: za `<<'PY'` stoi jeszcze reszta linii powłoki
    # (`|| fail=…`), ktora nie jest Pythonem i wywalilaby import na IndentationError.
    blok = vlocal.split("<<'PY'", 1)[1].split("\n", 1)[1].split("\nPY\n", 1)[0]
    (ROOT / "sprawdz_kontrakt.py").write_text(blok)
    kontrakt = {
        "members_published": True,
        "access_levels": ["corp"],
        "profiles": [{"name": "vertex-online-serving", "parameters": [], "risk": "low"}],
        "contributors": [{"repository": "example-org/example-repo", "division": "example-division",
                          "allowed_projects": ["prj-example-vertex-dev"]}],
        "members": [{"division": "example-division", "project_id": "prj-example-vertex-dev",
                     "stage": "enforced"}],
    }
    (ROOT / "kontrakt.json").write_text(json.dumps(kontrakt))
    zgloszenie = {"division": "example-division", "project_id": "prj-example-vertex-dev",
                  "stage": "dry-run", "profiles": [{"name": "vertex-online-serving", "params": {}}]}
    (ROOT / "zgloszenie.yaml").write_text(json.dumps(zgloszenie))  # JSON jest poprawnym YAML-em

    # GITHUB_REPOSITORY wyczyszczone celowo: blok pyta o nie, zeby sprawdzic wpis w contributors, a test ma
    # dowodzic reguly o CZLONKOSTWIE. Zostawione, w CI wskazywaloby biezace repozytorium i zaszumialo wynik.
    srodowisko = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
    p = sh([sys.executable, "sprawdz_kontrakt.py", "zgloszenie.yaml", "kontrakt.json"], cwd=ROOT, env=srodowisko)
    check("kontrakt ODRZUCA zgloszenie projektu, ktory juz jest czlonkiem",
          p.returncode != 0 and "jest już członkiem perimetru" in p.stdout, p.stdout + p.stderr)

    # POZYTYW: ten sam blok musi przepuszczac projekt, ktorego jeszcze nie ma — inaczej „odrzuca" znaczy
    # „odrzuca wszystko" i test wyzej niczego nie dowodzi.
    kontrakt["members"] = []
    (ROOT / "kontrakt.json").write_text(json.dumps(kontrakt))
    p = sh([sys.executable, "sprawdz_kontrakt.py", "zgloszenie.yaml", "kontrakt.json"], cwd=ROOT, env=srodowisko)
    check("kontrakt PRZEPUSZCZA projekt, ktorego jeszcze nie ma (test anty-tautologiczny)",
          p.returncode == 0, p.stdout + p.stderr)


# ------------------------------------------------------- kontrakt: dwa miejsca, jeden krok apply
def test_kontrakt_dwie_publikacje() -> None:
    """Kontrakt jedzie do bucketa I do release'u — ale MUSI wychodzić z jednego kroku apply.

    DLACZEGO to jest test, a nie komentarz: dwie publikacje w dwóch krokach to najłatwiejszy refaktor
    świata („wydzielmy publikację do osobnego joba, będzie czytelniej") i najcichszy tryb awarii, jaki
    ta konstrukcja ma. Dwa kroki = dwa wyzwalacze i dwa odczyty stanu, więc prędzej czy później opublikują
    różną treść, a konsument nie ma jak zauważyć, że czyta starszą kopię. Test parsuje workflow jako YAML
    i patrzy na STRUKTURĘ kroków — grep po tekście przeszedłby także wtedy, gdyby obie komendy stały
    w dwóch różnych stepach obok siebie.
    """
    print("\n== kontrakt: dwa miejsca, jeden krok ==")

    body = (ROOT / "terraform/contract.tf").read_text()
    # Liczymy na KODZIE, nie na całym pliku: komentarz WHY nad outputem tłumaczy, dlaczego drugiego
    # `jsonencode(...)` tu nie ma — i sam zawiera tę nazwę. Guard liczący wystąpienia w tekście wywracałby
    # się o własną dokumentację (ta sama lekcja co `strip_heredocs` wyżej: uczy usuwania komentarzy).
    kod = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    # Output czyta ATRYBUT ZASOBU. Drugie `jsonencode(local.contract_document)` byłoby drugim renderem
    # tych samych danych — a dwa rendery da się rozjechać. Jeden nie ma z czym.
    check("output kontraktu czyta atrybut zasobu, nie renderuje po raz drugi",
          "one(google_storage_bucket_object.contract[*].content)" in kod
          and kod.count("jsonencode(local.contract_document)") == 1,
          f"jsonencode w kodzie x{kod.count('jsonencode(local.contract_document)')}")
    # `one()`, nie `[0]`: przy wyłączonej sekcji `contract` zasobu nie ma i `[0]` wywracałby apply,
    # czyli sekcja opisana jako opcjonalna znowu byłaby obowiązkowa.
    check("output kontraktu znosi wylaczona sekcje `contract` (one(), nie [0])",
          "google_storage_bucket_object.contract[0]" not in body)
    # Suma kontrolna do porównania pochodzi z GCS (atrybut computed), nie z naszej zmiennej — inaczej
    # weryfikacja byłaby tautologią i zgadzałaby się nawet wtedy, gdyby do bucketa nie poszło nic.
    check("kontrakt eksportuje md5 policzone przez GCS (nie wlasne md5 z locals)",
          "one(google_storage_bucket_object.contract[*].md5hash)" in body and "md5(local." not in body)

    apply_yml = yaml.safe_load((ROOT / ".github/workflows/apply.yml").read_text())
    steps = apply_yml["jobs"]["apply"]["steps"]
    kroki_apply = [s for s in steps if "terraform -chdir=terraform apply" in s.get("run", "")]
    kroki_release = [s for s in steps if "gh release upload" in s.get("run", "")]

    check("apply.yml: dokladnie jeden krok applikuje i dokladnie jeden publikuje asset",
          len(kroki_apply) == 1 and len(kroki_release) == 1,
          f"apply={len(kroki_apply)} release={len(kroki_release)}")
    # SEDNO: to musi być TEN SAM obiekt kroku. Dwa sąsiednie stepy przeszłyby każdy grep po treści pliku.
    check("apply.yml: obie publikacje kontraktu wychodza z TEGO SAMEGO kroku",
          bool(kroki_apply) and kroki_apply == kroki_release,
          f"nazwy: apply={[s.get('name') for s in kroki_apply]} release={[s.get('name') for s in kroki_release]}")

    krok = kroki_apply[0]["run"] if kroki_apply else ""
    # Bajty assetu pochodzą z outputu TEGO apply, nie z pliku zrenderowanego obok (trzecia kopia).
    check("apply.yml: tresc assetu bierze sie z outputu tego apply",
          "terraform -chdir=terraform output -json contract_json" in krok)
    check("apply.yml: md5 assetu porownane z suma obiektu w buckecie",
          "contract_md5" in krok and "hashlib.md5" in krok)
    check("apply.yml: token workflowa moze tworzyc release (contents: write)",
          "contents: write" in (ROOT / ".github/workflows/apply.yml").read_text())

    # Anty-tautologia do „TEN SAM krok": test musi UMIEĆ ZOBACZYĆ rozdzielenie. Rozbijamy krok na dwa
    # i sprawdzamy, że asercja wtedy PADA — inaczej porównanie `kroki_apply == kroki_release` mogłoby
    # przechodzić z powodu, którego nie kontrolujemy (np. obie listy puste).
    rozbity = json.loads(json.dumps(apply_yml))  # głęboka kopia bez zależności
    kroki = rozbity["jobs"]["apply"]["steps"]
    i = next(n for n, s in enumerate(kroki) if "terraform -chdir=terraform apply" in s.get("run", ""))
    tresc = kroki[i]["run"]
    ciecie = tresc.index("gh release view")
    kroki[i] = {"name": "apply", "run": tresc[:ciecie]}
    kroki.insert(i + 1, {"name": "publikacja osobno", "run": tresc[ciecie:]})
    a = [s for s in kroki if "terraform -chdir=terraform apply" in s.get("run", "")]
    r = [s for s in kroki if "gh release upload" in s.get("run", "")]
    check("test LAPIE rozdzielenie apply i publikacji na dwa kroki (anty-tautologia)",
          a != r and len(a) == 1 and len(r) == 1, f"a={len(a)} r={len(r)}")


# ------------------------------------------------------------ przyklad repozytorium dywizji
def buduj_kontrakt(root: pathlib.Path) -> dict:
    """Odtwarza kontrakt z plików rozpakowanego repo — te same pola, które publikuje `contract.tf`.

    DLACZEGO z plików, a nie ręcznie wpisany słownik: kontrakt wpisany w test zamarza w chwili napisania,
    więc dzień po dodaniu profilu przykład dywizji nadal „przechodzi" wobec katalogu, którego już nie ma.
    Czytając te same YAML-e co renderer, testujemy przykład wobec AKTUALNEJ zawartości startera.
    """
    policy = yaml.safe_load((root / "perimeter/policy.yaml").read_text())
    profile = [yaml.safe_load(f.read_text()) for f in sorted((root / "perimeter/profiles").glob("*.yaml"))]
    poziomy = []
    for f in sorted((root / "perimeter/access-levels").glob("*.yaml")):
        poziomy += [al["name"] for al in yaml.safe_load(f.read_text())["access_levels"]]
    contributors = yaml.safe_load((root / "perimeter/contributors.yaml").read_text())["contributors"]
    return {
        "schema_version": 1,
        "perimeter_name": "accessPolicies/000000000000/servicePerimeters/test",
        "restricted_services": policy["restricted_services"],
        "onboarding": policy["onboarding"],
        "access_levels": sorted(poziomy),
        "profiles": [{"name": p["name"], "risk": p.get("risk", "unknown"), "summary": p.get("summary", ""),
                      "parameters": [x["name"] for x in p.get("parameters", [])],
                      "has_egress": bool(p.get("egress"))} for p in profile],
        "contributors": [{"repository": c["repository"], "division": c["division"],
                          "allowed_projects": c["allowed_projects"]} for c in contributors],
        "members_published": True,
        "members": [],
    }


def test_przyklad_repo_dywizji() -> None:
    """`examples/division-repo/` ma być DZIAŁAJĄCYM przykładem, nie ilustracją.

    Dlatego nie sprawdzamy tu obecności plików ani fraz w dokumentacji, tylko URUCHAMIAMY na przykładzie
    ten sam `validate-local.sh`, który pobiera u siebie zespół dywizji. Przykład, który „wygląda dobrze",
    a nie przechodzi własnej bramki, jest gorszy od jego braku: uczy kształtu, który zostanie odrzucony.
    """
    print("\n== przyklad repozytorium dywizji ==")
    przyklad = STARTER / "examples/division-repo"
    request = przyklad / "vpc-sc/request.yaml"
    check("examples/division-repo ma trzy pliki (request, workflow, README)",
          request.exists() and (przyklad / "github/workflows/vpc-sc-request.yml").exists()
          and (przyklad / "README.md").exists())
    if not request.exists():
        return

    dekl = yaml.safe_load(request.read_text())
    # NIEZMIENNIK PEDAGOGICZNY: wniosek jest WĘŻSZY niż plik członka. Cztery pola należą do perimetru —
    # `stage` decyduje o etapie (jedno pole omijałoby dwustopniowy onboarding), a `dry_run_since` wyznacza
    # okno obserwacji (data wsteczna od wnioskodawcy kasuje pomiar, dla którego to okno istnieje).
    obce = [k for k in ("stage", "dry_run_since", "review_by", "change_ref") if k in dekl]
    check("request.yaml NIE zawiera pol nalezacych do perimetru", not obce, f"znalezione: {obce}")
    check("request.yaml zawiera komplet pol, ktorych wlascicielem jest dywizja",
          {"schema_version", "division", "project_id", "project_number", "owner_group", "approved_by",
           "profiles"} <= set(dekl), f"jest: {sorted(dekl)}")

    # Workflow nie może wysyłać zgłoszenia z otwartego PR-a: dispatch ma konsekwencje po drugiej stronie
    # granicy, więc wychodzi dopiero po merge'u. Sprawdzamy STRUKTURĘ (warunek joba), nie tekst.
    wf = yaml.safe_load((przyklad / "github/workflows/vpc-sc-request.yml").read_text())
    zgloszenie = wf["jobs"]["zgloszenie"]
    check("workflow wysyla zgloszenie DOPIERO po merge",
          "merged == true" in str(zgloszenie.get("if", "")), str(zgloszenie.get("if")))
    uzywa_akcji = [s for s in zgloszenie["steps"] if "contrib@" in str(s.get("uses", ""))]
    check("workflow wola akcje contrib (a nie kopiuje jej logiki)", len(uzywa_akcji) == 1)
    check("job walidacji NIE wola akcji wysylajacej dispatch",
          not [s for s in wf["jobs"]["walidacja"]["steps"] if "contrib@" in str(s.get("uses", ""))])

    # Ten workflow ma zostac SKOPIOWANY do cudzego repozytorium — skladnia musi byc poprawna tutaj, bo
    # tam pierwszym testem bylby czerwony przebieg u kogos innego. `test_workflows` lintuje wylacznie
    # workflowy ROZPAKOWANEGO repo, wiec przyklad wymaga osobnego wywolania.
    if have("actionlint"):
        p = sh(["actionlint", str(przyklad / "github/workflows/vpc-sc-request.yml")])
        check("actionlint na workflow przykladu", p.returncode == 0, p.stdout[-800:])
    else:
        print("  SKIP  actionlint niedostepny lokalnie (workflow przykladu nie zostal zlintowany)")

    # Nazwa repozytorium dywizji istnieje WYŁĄCZNIE po stronie perimetru — w `contributors.yaml`. Nie ma
    # jej w żadnym pliku przykładu i to nie jest przeoczenie: repozytorium nie deklaruje, czym jest ani
    # o co wolno mu prosić. Dlatego stoi tutaj jako stała, a nie jest wyciągana z materiału dywizji.
    REPO_PRZYKLADU = "ORG/example-division-vertex"

    # Mapowanie repo→projekty MUSI istnieć po stronie perimetru — bez niego przykład jest niekompletny
    # i pierwszy realny wniosek odbije się o „repozytorium nie ma wpisu w contributors".
    wpisy = yaml.safe_load((ROOT / "perimeter/contributors.yaml").read_text())["contributors"]
    wpis = next((c for c in wpisy if c["repository"] == REPO_PRZYKLADU), None)
    check("contributors.yaml mapuje repo dywizji na projekt i dywizje z przykladu",
          wpis is not None and dekl["project_id"] in wpis["allowed_projects"]
          and wpis["division"] == dekl["division"],
          f"wpis: {wpis}")
    if wpis is None:
        return
    repo_przykladu = REPO_PRZYKLADU

    if not (have("check-jsonschema") and have("conftest")):
        print("  SKIP  brak check-jsonschema albo conftest — pomijam uruchomienie validate-local.sh")
        return

    # E2E: realny skrypt, realne bramki, realny plik przykładu. `--gates ROOT`, bo rozpakowane repo ma
    # `schemas/` i `policy/` dokładnie tam, gdzie paczka bramek trzyma je u zespołu.
    (ROOT / "kontrakt-przykladu.json").write_text(json.dumps(buduj_kontrakt(ROOT)))
    srodowisko = dict(os.environ, GITHUB_REPOSITORY=repo_przykladu)
    p = sh(["bash", str(ROOT / "contrib/validate-local.sh"), "--member", str(request),
            "--gates", str(ROOT), "--contract", "kontrakt-przykladu.json"], cwd=ROOT, env=srodowisko)
    check("validate-local.sh PRZEPUSZCZA przykladowy request.yaml (bez stage i dat)",
          p.returncode == 0, (p.stdout + p.stderr)[-900:])

    # NEGATYW: ten sam plik zgłoszony z repozytorium, które nie ma tego projektu na liście. Bramka, która
    # przepuszcza wszystko, przeszłaby test wyżej i nie chroniłaby niczego — to jest jedyny dowód, że
    # `contributors.yaml` cokolwiek rozstrzyga.
    srodowisko["GITHUB_REPOSITORY"] = "ORG/example-division-obca"
    p = sh(["bash", str(ROOT / "contrib/validate-local.sh"), "--member", str(request),
            "--gates", str(ROOT), "--contract", "kontrakt-przykladu.json"], cwd=ROOT, env=srodowisko)
    check("validate-local.sh ODRZUCA ten sam wniosek z CUDZEGO repozytorium",
          p.returncode != 0 and "contributors" in (p.stdout + p.stderr),
          (p.stdout + p.stderr)[-900:])


# --------------------------------------------------- kanal dywizji: ktorym zdarzeniem i jakim prawem
#
# DLACZEGO to jest osobny test, a nie linijka w test_workflows(): przedmiotem jest UPRAWNIENIE, ktorego
# selftest zobaczyc nie moze — nie ma API GitHuba i nie ma tokenu. Widzi za to jedyna rzecz, ktora to
# uprawnienie WYZNACZA: endpoint wolany przez akcje i zdarzenie, na ktore nasluchuje druga strona.
# `POST /repos/{o}/{r}/dispatches` wymaga `contents: write`, czyli prawa zapisu do KODU perimetru;
# `POST /repos/{o}/{r}/actions/workflows/{plik}/dispatches` wymaga `actions: write`, ktore nie zapisuje
# nic (zmierzone w obie strony, tabela w contrib/README.md). Powrot do pierwszego endpointu poszerza wiec
# poswiadczenie DYWIZJI o prawo pisania w repozytorium perimetru — cicho, jedna linijka i bez sladu
# w dokumentacji. To jest dokladnie ten rodzaj regresji, ktory ma padac tutaj.
def kanal_zgloszenia(tekst: str) -> str:
    """Ktorym endpointem akcja `contrib` wysyla zgloszenie — czytane z KODU, nie z komentarzy.

    Komentarze sa wycinane, bo ten plik ma ich wiecej niz kodu i oba endpointy sa w nich OPISANE.
    Detektor czytajacy komentarz twierdzilby, ze kanal jest jednoczesnie jednym i drugim.
    """
    kod = "\n".join(l for l in tekst.splitlines() if not l.lstrip().startswith("#"))
    wf = re.search(r"/actions/workflows/\S*?/dispatches", kod) is not None
    # Adres workflow-dispatcha KONCZY SIE na `/dispatches` i zawiera `repos/`, wiec bez wyciecia go
    # najpierw kazdy `workflow_dispatch` wygladalby rowniez jak `repository_dispatch`.
    bez_wf = re.sub(r"\S*/actions/workflows/\S*?/dispatches", "", kod)
    repo = re.search(r"repos/\S*?/dispatches", bez_wf) is not None
    if wf and repo:
        return "oba"
    if wf:
        return "workflow_dispatch"
    if repo:
        return "repository_dispatch"
    return "brak"


def klucze_inputs_akcji(tekst: str) -> set:
    """Nazwy `inputs`, ktore akcja realnie wysyla — z parowania nawiasow, nie z listy w tescie."""
    start = tekst.find('"inputs": {')
    if start < 0:
        return set()
    i = tekst.index("{", start + len('"inputs"'))
    glebokosc, j = 0, i
    while j < len(tekst):
        if tekst[j] == "{":
            glebokosc += 1
        elif tekst[j] == "}":
            glebokosc -= 1
            if glebokosc == 0:
                break
        j += 1
    return set(re.findall(r'"([a-z_]+)"\s*:', tekst[i:j + 1]))


def test_kanal_dywizji() -> None:
    print("\n== kanal dywizji (workflow_dispatch, nie repository_dispatch) ==")
    akcja = (ROOT / "contrib/action.yml").read_text()
    ext_tekst = (ROOT / ".github/workflows/external-intake.yml").read_text()
    ext = yaml.safe_load(ext_tekst)
    # `on:` w YAML-u jest wartoscia logiczna True (YAML 1.1), a nie napisem — stad ten odczyt.
    zdarzenia = set((ext.get(True) or ext.get("on") or {}).keys())

    check("contrib: zgloszenie idzie workflow_dispatch-em (endpoint /actions/workflows/.../dispatches)",
          kanal_zgloszenia(akcja) == "workflow_dispatch", f"wykryto: {kanal_zgloszenia(akcja)}")
    check("contrib: akcja NIE wola POST /repos/{o}/{r}/dispatches (to wymagaloby contents: write)",
          kanal_zgloszenia(akcja) not in ("repository_dispatch", "oba"))

    # ANTY-TAUTOLOGIA. Detektor, ktory zawsze mowi „workflow_dispatch", zazielenilby obie asercje wyzej
    # i nie chronilby niczego. Karmimy go wiec czterema probkami o znanym werdykcie — w tym DOKLADNIE tym
    # kodem, ktory stal w tej akcji przed zawezeniem kanalu.
    probki = [
        ("stan po zmianie", 'gh api --method POST "repos/${R}/actions/workflows/${W}/dispatches" --input -',
         "workflow_dispatch"),
        ("ROZBROJONY: stary kod sprzed zawezenia", 'gh api --method POST "repos/${R}/dispatches" --input -',
         "repository_dispatch"),
        ("oba naraz (okres przejsciowy = szersze uprawnienie nadal wymagane)",
         'gh api --method POST "repos/${R}/actions/workflows/${W}/dispatches"\n'
         'gh api --method POST "repos/${R}/dispatches"', "oba"),
        ("sam komentarz o dispatchu to nie kanal", '# POST /repos/{o}/{r}/dispatches wymaga contents: write',
         "brak"),
    ]
    for nazwa, probka, oczekiwane in probki:
        check(f"detektor kanalu rozpoznaje: {nazwa}", kanal_zgloszenia(probka) == oczekiwane,
              f"oczekiwano {oczekiwane}, wyszlo {kanal_zgloszenia(probka)}")

    check("external-intake: nasluchuje workflow_dispatch", "workflow_dispatch" in zdarzenia, str(zdarzenia))
    # JEDEN kanal, nie dwa. Dopoki `repository_dispatch` jest czynny, nadawca i tak MUSI miec `contents:
    # write` — a wtedy zawezenie po drugiej stronie jest wylacznie zmiana w dokumentacji.
    check("external-intake: repository_dispatch WYCOFANY (dwa czynne wejscia = szersze uprawnienie zostaje)",
          "repository_dispatch" not in zdarzenia, str(zdarzenia))

    deklarowane = set(((ext.get(True) or ext.get("on"))["workflow_dispatch"] or {}).get("inputs", {}))
    wysylane = klucze_inputs_akcji(akcja)
    # Producent i konsument musza mowic o TYCH SAMYCH nazwach. Oba zbiory czytamy z plikow — wpisane
    # w test byly kopia konfiguracji, a badanym trybem awarii jest wlasnie ich rozjazd (ta sama choroba,
    # ktora wywrocila raz artefakt raportu naruszen).
    check("kanal: nazwy inputs u nadawcy = nazwy inputs u odbiorcy",
          wysylane and wysylane == deklarowane, f"akcja={sorted(wysylane)} workflow={sorted(deklarowane)}")
    # Limit GitHuba to 10 wejsc. Przekroczenie nie jest bledem skladni — objawia sie odrzuceniem
    # zgloszenia u tej dywizji, ktorej wniosek akurat ma jedno pole za duzo.
    check("kanal: liczba inputs miesci sie w limicie GitHuba (<= 10)", len(deklarowane) <= 10,
          f"{len(deklarowane)}")

    # Endpoint dispatcha przyjmuje `ref` i uruchamia workflow W WERSJI Z TEGO REFA. Nadawca ten ref wybiera.
    # Utworzyc galezi nie moze (`actions: write` nie zapisuje kodu), ale galezie po otwartych PR-ach istnieja
    # — a wersja tego pliku na takiej galezi nie jest wersja, ktora przeszla review.
    check("external-intake: odmawia obslugi poza galezia domyslna",
          "github.event.repository.default_branch" in ext_tekst and "GITHUB_REF_NAME" in ext_tekst)
    check("contrib: ref brany z API (galaz domyslna perimetru), nie wpisany na sztywno",
          re.search(r'gh api "repos/\$\{PERIMETER_REPO\}" --jq \.default_branch', akcja) is not None)

    # REKURENCJA. Zmierzone: `workflow_dispatch` wyslany GITHUB_TOKEN-em URUCHAMIA workflow — inaczej niz
    # mowi intuicja o blokadzie rekurencji dla zdarzen z tego tokenu. Petla jest wiec mozliwa i musi byc
    # wykluczona konstrukcja: ten workflow nie wysyla zadnego dispatcha i nie nasluchuje na push/PR.
    check("external-intake: sam nie wysyla dispatcha (petla wykluczona konstrukcja)",
          kanal_zgloszenia(ext_tekst) == "brak", kanal_zgloszenia(ext_tekst))
    check("external-intake: nie nasluchuje na push ani pull_request (jedno wejscie)",
          not ({"push", "pull_request", "pull_request_target"} & zdarzenia), str(zdarzenia))

    # Payload jest DANYMI. `${{ inputs.member }}` wstawione do `run:` albo do nazwy galezi bylo tresci
    # zgloszenia dana jako KOD — dlatego deklaracja jedzie zmienna srodowiskowa, a nazwy galezi i tytul
    # PR-a biora sie z outputow kroku, ktory ja rozparsowal.
    check("external-intake: deklaracja czytana ze zmiennej srodowiskowej, nie wstawiana w kod",
          "MEMBER_JSON: ${{ inputs.member }}" in ext_tekst
          and 'json.loads(os.environ["MEMBER_JSON"])' in ext_tekst)
    check("external-intake: nazwa galezi i tytul PR-a z outputow kroku, nie z inputs",
          "steps.render.outputs.division" in ext_tekst
          and "inputs.member }}-" not in ext_tekst)
    # Grupa concurrency powstaje z PLASKIEGO project_id, zanim cokolwiek sie uruchomi. Gdyby nazywala inny
    # projekt niz deklaracja, dwa zgloszenia o jeden projekt szlyby rownolegle, WYGLADAJAC na zserializowane.
    check("external-intake: plaski project_id konfrontowany z deklaracja",
          'os.environ["PROJECT_ID"]' in ext_tekst and "sys.exit" in ext_tekst)

    # Ochrona galezi domyslnej po stronie perimetru jest PREREKWIZYTEM tego kanalu, nie higiena: bramki
    # tresci wisza na `pull_request`, a apply rusza z pushu na te galaz. Selftest nie ma jak sprawdzic
    # ustawienia repozytorium — moze sprawdzic, czy skrypt, ktory je zaklada, traktuje jego brak jako blad.
    boot = (ROOT / "tools/bootstrap_github.sh").read_text()
    check("bootstrap: ochrona galezi domyslnej ODCZYTYWANA z API, nie zakladana po PUT",
          re.search(r'gh api "repos/\$SLUG/branches/\$GALAZ_DOMYSLNA/protection"', boot) is not None)
    check("bootstrap: brak ochrony galezi konczy sie bledem bez jawnego odstepstwa",
          "--no-branch-protection" in boot and "NO_BRANCH_PROTECTION" in boot
          and re.search(r'if \[ -z "\$NO_BRANCH_PROTECTION" \]; then\n\s*echo[^\n]*\n\s*exit 1', boot)
          is not None)
    check("bootstrap: przyczyna 'plan bez ochrony galezi' NAZWANA, nie przemilczana",
          "pgrade to GitHub" in boot)


# --------------------------------------------------------------------- kanal ticketowy
def bez_komentarzy(tekst: str) -> str:
    """Tekst pliku BEZ linii komentarza.

    Powod jest zmierzony, nie estetyczny: asercja „w tym pliku nie ma juz `yaml.safe_dump(member)`"
    zapalila sie na czerwono, bo tak wlasnie brzmi KOMENTARZ tlumaczacy, co robil stary renderer.
    Detektor czytajacy komentarze twierdzi, ze kod robi to, co dokumentacja mowi, ze robil kiedys.
    """
    return "\n".join(l for l in tekst.splitlines() if not l.lstrip().startswith("#"))


def kroki(workflow: dict) -> list:
    """Nazwy krokow JEDYNEGO joba workflowa, w kolejnosci wykonania."""
    job = list(workflow["jobs"].values())[0]
    return [s.get("name") or s.get("uses", "") for s in job["steps"]]


def test_kanal_ticketowy() -> None:
    """Trzeci bok tezy „trzy kanaly, jeden mutator": kanal ticketowy ma miec TE SAME wlasnosci.

    Ten test powstal po przejsciu kanalu end-to-end po raz pierwszy. Kazda asercja nizej odpowiada
    czemus, czego kanal NIE mial, a nie czemus, co juz dzialalo.
    """
    print("\n== kanal ticketowy (intake.yml) ==")
    tekst = (ROOT / ".github/workflows/intake.yml").read_text()
    wf = yaml.safe_load(tekst)
    # `on:` w YAML 1.1 parsuje sie na True, nie na napis — stad ten odczyt.
    zdarzenia = set((wf.get(True) or wf.get("on") or {}).keys())

    check("intake: nasluchuje workflow_dispatch", "workflow_dispatch" in zdarzenia, str(zdarzenia))
    # `repository_dispatch` wymusza na nadawcy `contents: write`, czyli prawo zapisu do KODU perimetru.
    # Zlozone z galezia domyslna bez ochrony i z apply ruszajacym z pushu na nia, poswiadczenie integracji
    # ticketowej jest sciezka do zmiany granicy z pominieciem WSZYSTKICH bramek tresci — te wisza na
    # `pull_request`. Argument „ale to nasz wlasny system" nie zmienia zasiegu wycieku TOKENU.
    check("intake: repository_dispatch WYCOFANY (wymuszal contents: write na nadawcy)",
          "repository_dispatch" not in zdarzenia, str(zdarzenia))
    check("intake: nie nasluchuje na push ani pull_request (jedno wejscie)",
          not ({"push", "pull_request", "pull_request_target"} & zdarzenia), str(zdarzenia))
    check("intake: sam nie wysyla dispatcha (petla wykluczona konstrukcja)",
          kanal_zgloszenia(tekst) == "brak", kanal_zgloszenia(tekst))
    check("intake: odmawia obslugi poza galezia domyslna",
          "github.event.repository.default_branch" in tekst and "GITHUB_REF_NAME" in tekst)

    # DEC-2: system ticketowy NIE DOTYKA GCP. Zero tozsamosci, zero wywolan ACM. Sprawdzamy to na
    # workflowie, a nie w dokumentacji, bo to jedyne miejsce, w ktorym da sie ta wlasnosc zlamac.
    kod = "\n".join(l for l in tekst.splitlines() if not l.lstrip().startswith("#"))
    check("intake: zero tozsamosci w GCP (DEC-2 — brak id-token, auth, gcloud)",
          "id-token" not in kod and "google-github-actions" not in kod and "gcloud " not in kod)

    # BRAMKI PRZED PR-em, i to jest asercja o KOLEJNOSCI, nie o obecnosci. Bramka wykonana po kroku,
    # ktory moze paść, nie jest bramka tego kroku — a krok „otworz PR" realnie pada, dopoki PR otwiera
    # `GITHUB_TOKEN` (patrz komentarz przy nim). Wczesniej `intake.yml` nie mial tych krokow w ogóle
    # i cala jego walidacja wisiala na PR-ze, ktory moze nie powstac.
    nazwy = kroki(wf)
    for etap in ("schema", "ownership and onboarding rules"):
        check(f"intake: krok {etap!r} istnieje", etap in nazwy, str(nazwy))
    if "schema" in nazwy and "open the pull request" in nazwy:
        check("intake: bramki tresci PRZED otwarciem PR-a",
              nazwy.index("schema") < nazwy.index("open the pull request")
              and nazwy.index("ownership and onboarding rules") < nazwy.index("open the pull request"),
              str(nazwy))

    # JEDEN RENDERER NA TRZY KANALY. Kanal dywizji mial WLASNA kopie w heredocu i kopia sie rozjechala:
    # `yaml.safe_dump(member)` zapisywalo caly slownik z payloadu, wiec przechodzilo przez nia kazde
    # dodatkowe pole wnioskodawcy — w tym `control_plane_exception` (furtka w bramce chroniacej przed
    # samo-zablokowaniem) i `exceptions` (wymagaja approvalu Security). `render_member.py` sklada plik
    # z LISTY DOZWOLONYCH POL, wiec te pola nie maja ktoredy wejsc.
    ext = (ROOT / ".github/workflows/external-intake.yml").read_text()
    for plik, tresc in ((".github/workflows/intake.yml", tekst),
                        (".github/workflows/external-intake.yml", ext)):
        check(f"{plik}: renderuje przez tools/render_member.py", "render_member.py" in tresc)
    # Komentarz w tym workflowie CYTUJE stary kod (`yaml.safe_dump(member)`), zeby wyjasnic, co przez
    # niego przechodzilo — wiec detektor musi czytac KOD, nie komentarze. Pierwsza wersja tej asercji
    # zapalila sie na czerwono wlasnie na wlasnym komentarzu.
    check("external-intake: NIE ma drugiego renderera (nie zrzuca payloadu do YAML-a)",
          "yaml.safe_dump(member" not in bez_komentarzy(ext))

    # ANTY-TAUTOLOGIA dla asercji wyzej: uruchamiamy renderer z polami, ktorych wnioskodawca nie ma prawa
    # ustawiac, i sprawdzamy, ze ich w wyniku NIE MA. Asercja „nie ma stringa w pliku workflow" byloby
    # tu za malo — mowi o ksztalcie kodu, nie o tym, co kod produkuje.
    plik_czlonkow = ROOT / "perimeter/projects.yaml"
    przed_renderem = plik_czlonkow.read_text()
    p = sh([sys.executable, "tools/render_member.py", "--division", "d1", "--project-id", "prj-alw-test",
            "--project-number", "123456789012", "--owner-group", "g@example.com",
            "--change-ref", "snow:RITM0000123", "--approved-by", "n@example.com",
            "--profiles-json", '[{"name":"vertex-online-serving","params":{}}]'], cwd=ROOT)
    # Renderer dopisuje wpis do WSPOLNEGO pliku (DEC-12), wiec „co wyprodukowal" to roznica wobec stanu
    # sprzed wywolania — czyli dokladnie ten sam fragment, ktory zobaczy review w diffie pull requesta.
    wynik = plik_czlonkow.read_text()[len(przed_renderem):] if p.returncode == 0 else ""
    plik_czlonkow.write_text(przed_renderem)
    check("render_member.py sklada wpis z listy dozwolonych pol (stage zawsze dry-run)",
          p.returncode == 0 and "stage: dry-run" in wynik, p.stdout + p.stderr)
    check("render_member.py NIE przepuszcza control_plane_exception ani niepustych exceptions",
          "control_plane_exception" not in wynik and "exceptions: []" in wynik, wynik[:300])

    # TRYB TESTOWY. Bramka na nazwe fixture'a decyduje o tym, CO zostanie uznane za odpowiedz systemu
    # rekordu — wiec musi byc kotwiczonym dopasowaniem, a nie wzorcem powloki (`snow-[a-z0-9-]*`
    # dopasowuje pierwszy znak z klasy, a `*` juz wszystko, wiec `snow-a/../..` przechodzi).
    krok_fixture = next((s for s in list(wf["jobs"].values())[0]["steps"]
                         if s.get("name") == "test mode - resolve the fixture"), None)
    check("intake: krok trybu testowego istnieje", krok_fixture is not None)
    if krok_fixture:
        skrypt = ROOT / "krok-fixture.sh"
        skrypt.write_text(krok_fixture["run"])
        for wartosc, oczekiwany, opis in [
            ("", 0, "pusty = tryb normalny"),
            ("snow-approved", 0, "fixture z tests/"),
            ("snow-a/../../etc/passwd", 1, "traversal przez podkatalog"),
            ("../tests/snow-approved", 1, "traversal na poczatku"),
            ("/etc/passwd", 1, "sciezka absolutna"),
            ("snow-a; echo WSTRZYKNIETE", 1, "wstrzykniecie polecenia"),
            ("snow-nie-ma-takiego", 1, "fixture nie istnieje"),
        ]:
            srodowisko = dict(os.environ, FIXTURE=wartosc,
                              GITHUB_OUTPUT=str(ROOT / "gh_out"), GITHUB_STEP_SUMMARY=str(ROOT / "gh_sum"))
            r = sh(["bash", str(skrypt)], cwd=ROOT, env=srodowisko)
            check(f"intake fixture — {opis}", r.returncode == oczekiwany,
                  f"rc={r.returncode}, oczekiwano {oczekiwany}: {r.stdout[-200:]}")
            # Dowodem wykonania jest LINIA rowna wyjsciu `echo`, nie wystapienie napisu gdziekolwiek:
            # komunikat bledu cytuje wartosc fixture'a, wiec zawiera ten napis takze wtedy, gdy nic
            # sie nie wykonalo. Pierwsza wersja tej asercji zglaszala wlasnie taki falszywy alarm.
            if wartosc.startswith("snow-a;"):
                check("intake fixture — polecenie z nazwy NIE zostalo wykonane",
                      not any(l.strip() == "WSTRZYKNIETE" for l in r.stdout.splitlines()), r.stdout[-200:])

    # KTORY TOKEN OTWIERA PR, DECYDUJE CZY PR JEST SPRAWDZANY. Z `GITHUB_TOKEN` utworzenie PR-a jest
    # odmawiane (`GitHub Actions is not permitted to create or approve pull requests`), a nawet po
    # wlaczeniu tamtego ustawienia PR utworzony tym tokenem nie uruchamia workflowow `pull_request`.
    for plik, tresc in ((".github/workflows/intake.yml", tekst),
                        (".github/workflows/external-intake.yml", ext)):
        check(f"{plik}: PR-a otwiera token instalacji Appa, gdy jest (INTAKE_PR_TOKEN)",
              "secrets.INTAKE_PR_TOKEN" in tresc)
        # Bez stanu posredniego: `create-pull-request` wypycha galaz ZANIM wola API PR-ow, wiec odmowa
        # zostawia galaz z plikiem czlonka i bez PR-a — niewidoczna na liscie PR-ow.
        check(f"{plik}: po odmowie PR-a kasuje galaz, ktora wypchnal",
              "steps.pr.outcome == 'failure'" in tresc and "git/refs/heads" in tresc)

    # snow_verify.py: cztery checki, cztery fixture'y. `snow-not-found` domyka punkt 1 („ticket
    # istnieje"), ktory przez caly czas byl JEDYNYM bez pokrycia — ta galaz kodu nie wykonala sie
    # w zadnym tescie. `snow-no-approval` dokłada dowod, ze NIEZNANY ksztalt odpowiedzi degraduje sie
    # do odmowy, a nie do zgody.
    for fixture, opis in [("tests/snow-not-found.json", "ticket nie istnieje w systemie rekordu"),
                          ("tests/snow-no-approval.json", "ticket bez zadnego sladu zatwierdzenia")]:
        p = sh([sys.executable, "tools/snow_verify.py", "--ticket", "RITM0000001",
                "--expect-project", "prj-x-test", "--offline-fixture", fixture], cwd=ROOT)
        check(f"snow_verify.py ODRZUCA: {opis}", p.returncode != 0, p.stdout + p.stderr)

    # Brak konfiguracji systemu rekordu to ODMOWA Z KOMUNIKATEM, nie traceback. Kod wyjscia byl niezerowy
    # tak czy siak, ale tryb awarii, ktorego nikt nie umie odczytac, konczy sie „to chyba flaka, puscmy
    # jeszcze raz" — czyli sciezka, na ktorej ludzie zaczynaja szukac obejscia bramki zamiast przyczyny.
    czyste = {k: v for k, v in os.environ.items() if k not in ("SNOW_INSTANCE", "SNOW_USER", "SNOW_TOKEN")}
    p = sh([sys.executable, "tools/snow_verify.py", "--ticket", "RITM0000001",
            "--expect-project", "prj-x-test"], cwd=ROOT, env=czyste)
    check("snow_verify.py bez konfiguracji SNOW: odmowa z komunikatem, nie traceback",
          p.returncode == 2 and "ODRZUCONE" in p.stderr and "Traceback" not in p.stderr,
          f"rc={p.returncode}: {p.stderr[-200:]}")


# --------------------------------------------------------------------- monitoring
def test_monitoring() -> None:
    """Perimetr bez alertu to granica, o której dowiadujesz się od użytkownika."""
    print("\n== monitoring ==")
    body = (ROOT / "terraform/monitoring.tf").read_text()

    # Dwie metryki muszą być ROZŁĄCZNE: enforced page'uje, dry-run informuje. Wspólna metryka oznacza alert
    # odpalający przy normalnej pracy okna obserwacji — czyli alert, który po tygodniu jest ignorowany.
    # NEGACJA, nie `dryRun="false"`. Wpis o odmowie EGZEKWOWANEJ nie ma pola `dryRun` w ogóle — pojawia się
    # ono wyłącznie przy naruszeniach dry-run, z wartością `true` (zmierzone na żywej organizacji przy
    # pierwszej realnej odmowie). Poprzednia asercja pilnowała więc, żeby filtr pozostał taki, przy którym
    # metryka „ktoś jest blokowany TERAZ" nie policzy nigdy niczego — test strzegł defektu.
    check("metryka enforced filtruje NEGACJA dryRun=true (pola nie ma przy enforced)",
          'NOT protoPayload.metadata.dryRun=\\"true\\"' in body and 'dryRun=\\"false\\"' not in body)
    check("metryka dry-run filtruje dryRun=true", 'dryRun=\\"true\\"' in body)

    # Alert bez runbooka to zgadywanie o 3:00 (zasada repo: każdy critical niesie procedurę).
    critical = body[body.find('display_name = "VPC-SC: ruch odrzucony'):]
    check("alert enforced ma severity CRITICAL", 'severity     = "CRITICAL"' in critical[:600])
    check("alert enforced ma dokumentacje z procedura",
          "documentation {" in critical and "break-glass" in critical)
    check("alert enforced grupuje po tozsamosci (nie zalewa organizacji)",
          'group_by_fields      = ["metric.label.principal"]' in critical)

    # Alert o zmianach poza pipeline'em musi wykluczać WŁASNE konto apply — inaczej odpala przy każdym apply
    # i uczy ignorowania.
    check("alert out-of-band wyklucza konto apply",
          "principalEmail!=" in body and "apply_service_account" in body)

    # Metryki i alerty są opcjonalne (count), ale przykładowa policy MA je włączać — starter pokazuje
    # kompletne wdrożenie, nie minimalne.
    check("monitoring jest opcjonalny (count), ale wlaczony w przykladzie",
          "local.monitoring_enabled ? 1 : 0" in body
          and "monitoring:" in (ROOT / "perimeter/policy.yaml").read_text())


# --------------------------------------------------------------------- alerty granicy
def test_alerty() -> None:
    """Cztery objawy zepsutej granicy mają mieć alert, runbook i producenta, który liczy to samo.

    Ten test istnieje, bo w tym systemie WSZYSTKIE dotychczasowe defekty alertingu wyglądały identycznie:
    konfiguracja obecna, wartość nigdy nie osiągalna, cisza brana za spokój (`dryRun="false"`, kanał pusty,
    reguła bez źródła). Asercje celują więc w OSIĄGALNOŚĆ warunku, nie w jego obecność.
    """
    print("\n== alerty granicy ==")
    alerts = (ROOT / "terraform/alerts.tf").read_text()
    watch_py = (ROOT / "tools/perimeter_watch.py").read_text()
    runbook = (ROOT / "docs/7-alerty.md").read_text()

    # 1. PRODUCENT I KONSUMENT MUSZĄ MÓWIĆ O TEJ SAMEJ METRYCE. Rozjazd tych dwóch list daje alert
    # obserwujący metrykę, do której nikt nie pisze — czyli ciszę nie do odróżnienia od zdrowia. To jest
    # jedyna bramka, która ten rozjazd łapie, bo `terraform validate` widzi tylko jedną stronę.
    typy_tf = set(re.findall(r'"(custom\.googleapis\.com/vpcsc/[a-z_]+)"', alerts))
    typy_py = set(re.findall(r'"(custom\.googleapis\.com/vpcsc/[a-z_]+)"', watch_py))
    check("nazwy metryk zgodne miedzy alerts.tf a perimeter_watch.py", typy_tf == typy_py,
          f"tylko w tf={sorted(typy_tf - typy_py)} tylko w py={sorted(typy_py - typy_tf)}")
    check("pieć metryk obserwatora (apply/budzet%/budzet-dni/dryf/wygasli)", len(typy_tf) == 5,
          str(sorted(typy_tf)))

    # 2. KAŻDY ALERT MA RUNBOOK NA ISTNIEJĄCĄ KOTWICĘ. Kotwica, której nie ma, ląduje na początku
    # dokumentu — czyli o 3:00 daje spis treści zamiast procedury. Sprawdzamy OBA pliki z alertami.
    kotwice_doc = set(re.findall(r'<a id="([a-z0-9-]+)"></a>', runbook))
    monitoring = (ROOT / "terraform/monitoring.tf").read_text()
    uzyte = set(re.findall(r'\$\{local\.runbook\}#([a-z0-9-]+)"', alerts + monitoring))
    check("kazda kotwica z alertow istnieje w docs/7-alerty.md", uzyte and uzyte <= kotwice_doc,
          f"uzyte={sorted(uzyte)} w dokumencie={sorted(kotwice_doc)}")

    polityki = re.findall(r'resource "google_monitoring_alert_policy" "(\w+)"(.*?)\n}\n',
                          alerts + monitoring, re.S)
    check("znaleziono polityki alertow", len(polityki) >= 7, str([n for n, _ in polityki]))
    bez_linku = [n for n, tresc in polityki if "links {" not in tresc]
    check("ZADNA polityka alertu nie jest bez runbook-linku", not bez_linku, str(bez_linku))
    bez_kanalu = [n for n, tresc in polityki if "notification_channels" not in tresc]
    check("ZADNA polityka alertu nie jest bez kanalu", not bez_kanalu, str(bez_kanalu))

    # 2b. DWA DEFEKTY ZMIERZONE NA PIERWSZYM APPLY, oba niewidoczne dla `validate` i `plan`:
    #   * `evaluation_missing_data` wymaga NIEZEROWEGO `duration` (Error 400 z API);
    #   * deskryptor metryki nie jest widoczny dla walidacji polityki od razu po utworzeniu (Error 404
    #     „Cannot find metric(s)" na deskryptorze utworzonym w TYM SAMYM przebiegu) — `depends_on` tego
    #     nie rozwiązuje, bo zależność jest spełniona, a zasób jeszcze nie istnieje dla konsumenta.
    # Bez tych dwóch bramek wdrożenie OD ZERA kończy się częściowo, a ponowiony apply świeci zielono
    # i nikt się nie dowiaduje, że pierwszy raz nie zadziałał.
    for nazwa, tresc in polityki:
        for war in re.findall(r"condition_threshold \{(.*?)\n    \}", tresc, re.S):
            if "evaluation_missing_data" not in war:
                continue
            okno = re.search(r'duration\s+= "(\S+?)"', war)
            check(f"{nazwa}: evaluation_missing_data ma NIEZEROWE okno (wymog API)",
                  okno is not None and okno.group(1) not in ("0s", "0"), war[:200])
    czekanie = re.search(r'resource "time_sleep" "(\w+)"', alerts)
    check("jest oczekiwanie na propagacje deskryptorow metryk", czekanie is not None)
    if czekanie:
        wlasne = [n for n, t in polityki if "custom.googleapis.com" in t or "local.metryka" in t]
        bez_czekania = [n for n, t in polityki
                        if n in wlasne and f"time_sleep.{czekanie.group(1)}" not in t]
        check("KAZDA polityka na metryce wlasnej czeka na propagacje deskryptora",
              not bez_czekania, str(bez_czekania))

    # 3. ALERT O APPLY ŁAPIE TRZY TRYBY AWARII — warunek o WIEKU, nie nasłuch zdarzenia — plus czwarty
    # (martwy obserwator) przez BRAK danych. Bez drugiego warunku martwy `watch.yml` daje wykres zamrożony
    # na ostatniej dobrej wartości, czyli ciszę wyglądającą na zdrowie.
    apply_pol = next(t for n, t in polityki if n == "vpcsc_apply_stale")
    check("alert apply ma warunek progowy na WIEKU niezastosowanej zmiany",
          "apply_pending_seconds" in apply_pol and "COMPARISON_GT" in apply_pol)
    check("alert apply ma warunek na BRAK danych (martwy obserwator)", "condition_absent" in apply_pol)
    check("alert apply jest CRITICAL", 'severity     = "CRITICAL"' in apply_pol)

    # 4. BUDŻET LICZONY OSOBNO DLA `spec` I `status` — limit 6000 jest NA KONFIGURACJĘ. Grupowanie po
    # etykiecie zamiast dwóch polityk, żeby incydent NIÓSŁ W SOBIE, o którą konfigurację chodzi.
    budzet = next(t for n, t in polityki if n == "vpcsc_attribute_budget")
    check("alert budzetu grupuje po etykiecie config (spec vs status osobno)",
          'group_by_fields      = ["metric.label.config"]' in budzet)
    # Sprawdzamy REFERENCJE do locali, nie literalne nazwy metryk: w HCL filtr jest interpolowany
    # (`${local.metryka.budzet_procent}`), więc literał `attribute_budget_percent` w tym zasobie nie
    # występuje i asercja o nim przechodziłaby tylko wtedy, gdyby ktoś zdublował nazwę na sztywno.
    check("alert budzetu ma OBA wymiary: statyczny prog i prognoze",
          "local.metryka.budzet_procent" in budzet and "local.metryka.budzet_dni" in budzet)
    krytyczny = next(t for n, t in polityki if n == "vpcsc_attribute_budget_exhaustion")
    check("prognoza krytyczna jest OSOBNA polityka (polityka ma jedna severity)",
          'severity     = "CRITICAL"' in krytyczny and "days_to_limit_critical" in krytyczny)

    # 5. DRYF NIE MOŻE STRZELAĆ PO KAŻDYM APPLY. Zmierzone: konfiguracja w ACM wraca natychmiast, SKUTEK
    # propaguje się ~20 s dłużej. Reguła z zerowym oknem trwania opisywałaby normalną pracę pipeline'u.
    dryf = next(t for n, t in polityki if n == "vpcsc_drift")
    okno = re.search(r'duration\s+= "\$\{local\.progi\.drift_persist_seconds\}s"', dryf)
    check("alert dryfu wymaga TRWANIA (okno z alerting.yaml, nie 0s)", okno is not None, dryf[:400])
    progi = yaml.safe_load((ROOT / "perimeter/alerting.yaml").read_text())["thresholds"]
    check("okno dryfu >= 600 s (30x zmierzona propagacja skutku ~20 s)",
          progi["drift_persist_seconds"] >= 600, str(progi["drift_persist_seconds"]))
    check("prog ostrzegawczy prognozy > krytycznego (inaczej warning nigdy nie wyprzedzi)",
          progi["days_to_limit_warning"] > progi["days_to_limit_critical"], str(progi))
    check("watchdog tolerancyjniejszy niz prog zaleglosci apply",
          progi["watchdog_absent_seconds"] > progi["apply_pending_seconds"], str(progi))

    # 6. DWA KANAŁY, ROZŁĄCZNIE UŻYTE. Alert o obejściu procesu w tej samej skrzynce co „zbliżasz się do
    # 70%" kończy się wyuczoną obojętnością na całą kategorię.
    check("dryf idzie na kanal BEZPIECZENSTWA", "local.kanal_bezpieczenstwo" in dryf)
    check("budzet idzie na kanal POJEMNOSCIOWY", "local.kanal_pojemnosc" in budzet)
    oob = next(t for n, t in polityki if n == "vpcsc_out_of_band_change")
    check("zmiana poza pipeline'em: kanal bezpieczenstwa i CRITICAL",
          "local.kanal_bezpieczenstwo" in oob and 'severity = "CRITICAL"' in oob)

    # 7. FILTR `dryRun="false"` NIE MA PRAWA WRÓCIĆ — nigdzie. Pole `dryRun` przy odmowie EGZEKWOWANEJ
    # nie istnieje, więc ten filtr nie dopasowuje NICZEGO. Siedział jednocześnie w metryce, w sondzie
    # i w asercji selftestu, która go utrwalała; skanujemy więc CAŁE repo, nie jeden plik.
    # SZUKAMY PEŁNEJ ŚCIEŻKI POLA, NIE SAMEGO `dryRun="false"` — i to jest różnica między bramką a bramką,
    # która uczy kasowania komentarzy. Krótka postać występuje legalnie w KILKUNASTU miejscach: w komentarzu
    # nad poprawnym filtrem, w treści alertu, w docstringu raportu, w runbooku. To są zdania OSTRZEGAJĄCE
    # przed tym filtrem; guard, który je zgłasza, każe usunąć dokładnie tę wiedzę, dla której powstał.
    # Defektem jest FILTR, a filtr w tym systemie zawsze niesie prefiks `protoPayload.metadata.`.
    #
    # Skanujemy wyłącznie ŹRÓDŁA i pomijamy `.terraform/`: leży tam pobrany provider (~200 MB w jednym
    # pliku binarnym), a `read_text()` na nim zawieszał ten test na minuty. Bramka, która trwa tyle, że
    # przestaje się ją uruchamiać, jest bramką tylko z nazwy.
    rozszerzenia = {".tf", ".yaml", ".yml", ".json", ".py", ".sh", ".md", ".rego", ".hcl"}
    zly = 'protoPayload.metadata.dryRun="false"'
    trafienia = []
    poprawny_filtr = False
    for f in ROOT.rglob("*"):
        if not f.is_file() or f.suffix not in rozszerzenia or ".terraform" in f.parts:
            continue
        tresc = f.read_text(errors="ignore").replace('\\"', '"')
        if zly in tresc:
            trafienia.append(str(f.relative_to(ROOT)))
        if 'NOT protoPayload.metadata.dryRun="true"' in tresc:
            poprawny_filtr = True
    check("nigdzie w repo nie ma filtru dryRun=false (nie lapie NIGDY niczego)", not trafienia,
          str(trafienia))
    # ANTY-TAUTOLOGIA: powyższe przeszłoby także wtedy, gdyby w repo nie było ŻADNEGO filtru na naruszenia.
    check("poprawna postac filtru (NEGACJA dryRun=true) jest obecna", poprawny_filtr)

    # 8. CZYSTE FUNKCJE PRODUCENTA — liczby, nie kształt pliku. To jest jedyne miejsce, w którym sprawdzamy,
    # że dyskryminator „dryf vs opóźnienie propagacji" i sentynela prognozy realnie działają.
    sys.path.insert(0, str(ROOT / "tools"))
    import perimeter_watch as pw

    plan_ze_zmiana = {"resource_changes": [{"change": {"actions": ["update"]}},
                                           {"change": {"actions": ["no-op"]}}]}
    check("dryf liczy tylko realne zmiany", pw.dryf_z_planu(plan_ze_zmiana, False) == 1)
    check("dryf = 0, gdy w Gicie czeka niezastosowana zmiana (dyskryminator propagacji)",
          pw.dryf_z_planu(plan_ze_zmiana, True) == 0)

    check("brak historii => sentynela, nie falszywy alarm",
          pw.dni_do_sciany([], 42.0) == pw.BRAK_PROGNOZY_DNI)
    plaska = [(1_700_000_000 + i * 86400, 40.0) for i in range(30)]
    check("plaski wykres => sentynela (nie dzielimy przez zero)",
          pw.dni_do_sciany(plaska, 40.0) == pw.BRAK_PROGNOZY_DNI)
    # 1 punkt procentowy na dobę, stan 70% => do 100% zostaje 30 dni.
    rosnaca = [(1_700_000_000 + i * 86400, 40.0 + i) for i in range(31)]
    dni = pw.dni_do_sciany(rosnaca, 70.0)
    check("prognoza liczona z nachylenia 30 dni (1 pp/dobe, 70% => ~30 dni)", abs(dni - 30.0) < 0.5,
          f"policzone {dni}")
    krotka = [(1_700_000_000 + i * 86400, 40.0 + i) for i in range(3)]
    check("za krotka historia => sentynela (nie prognozuj z trzech punktow)",
          pw.dni_do_sciany(krotka, 70.0) == pw.BRAK_PROGNOZY_DNI)

    doc = {"members": [{"review_by": "2020-01-01"}, {"review_by": "2099-01-01"}]}
    check("wygasli liczy wpisy po review_by",
          pw.wygasli_czlonkowie(doc, datetime.date(2026, 8, 11)) == 1)

    # 8b. BUDZET LICZONY Z ZYWEJ GRANICY, NIE Z DEKLARACJI. `attribute_budget.py` modeluje renderer na
    # podstawie plikow YAML — wlasciwie na pull requescie („czy MOJA zmiana sie zmiesci"), ale strukturalnie
    # slepo na wszystko, co jest w granicy, a czego nie ma w deklaracji: zdublowane reguly po nieudanym
    # odzysku stanu, reczne dopiski, dryf. Alert na tej liczbie milczalby dokladnie w tym scenariuszu,
    # w ktorym sufit zostaje przekroczony bez niczyjej wiedzy.
    check("obserwator czyta ZYWA granice z Access Context Managera",
          "accesscontextmanager.googleapis.com" in watch_py and "def pobierz_perimetr" in watch_py)
    check("metryka budzetu liczy sie z obiektu API, nie z declarations.json",
          "procenty_budzetu(perimetr, limit)" in watch_py)
    # FAIL-CLOSED: gdy zywej granicy nie da sie odczytac, NIE podstawiamy liczby z deklaracji. Wartosc
    # z YAML-i wygladalaby poprawnie i opisywala co innego — czyli dokladnie ten tryb awarii, ktory ten
    # plik ma tropic. Brak punktu jest uczciwszy niz zly punkt.
    check("brak odczytu granicy => ZADNEGO punktu budzetu (nie podstawiamy deklaracji)",
          "procenty, prognoza = {}, {}" in watch_py)

    zywa = {
        "ingressPolicies": [{
            "ingressFrom": {"identities": ["serviceAccount:a@b.iam.gserviceaccount.com"],
                            "sources": [{"accessLevel": "*"}]},
            "ingressTo": {"resources": ["projects/1"],
                          "operations": [{"serviceName": "storage.googleapis.com",
                                          "methodSelectors": [{"method": "*"}]}]},
        }],
        "egressPolicies": [{
            "egressFrom": {"identities": ["serviceAccount:a@b.iam.gserviceaccount.com"]},
            "egressTo": {"externalResources": ["s3://kubelek"],
                         "operations": [{"serviceName": "bigquery.googleapis.com",
                                         "methodSelectors": [{"permission": "bigquery.tables.get"}]}]},
        }],
    }
    # ingress: 1 tozsamosc + 1 zrodlo + 1 zasob + (1 usluga + 1 selektor) = 5
    # egress:  1 tozsamosc + 1 zasob zewnetrzny + (1 usluga + 1 selektor)  = 4
    check("koszt zywej konfiguracji liczy tozsamosci, zrodla, cele i selektory",
          pw.koszt_konfiguracji(zywa) == 9, str(pw.koszt_konfiguracji(zywa)))
    check("zasoby zewnetrzne (BigQuery Omni) tez konsumuja budzet",
          pw.koszt_konfiguracji({"egressPolicies": [{"egressTo": {"externalResources": ["s3://x", "s3://y"]}}]}) == 2)
    check("pusta konfiguracja kosztuje zero (a nie wywraca sie na braku kluczy)",
          pw.koszt_konfiguracji({}) == 0)
    check("procenty licza sie OSOBNO dla spec i status",
          pw.procenty_budzetu({"spec": zywa, "status": {}}, 900) == {"spec": 1.0, "status": 0.0},
          str(pw.procenty_budzetu({"spec": zywa, "status": {}}, 900)))

    # 9. PRODUCENT MUSI PATRZEĆ NA TE SAME KATALOGI, CO WYZWALACZ `apply.yml`. Rozjazd znaczy: zmiana
    # w katalogu, który uruchamia apply, nie jest liczona jako zaległa (albo odwrotnie — wieczna zaległość
    # od pliku, którego apply nigdy nie zastosuje).
    apply_wf = yaml.safe_load((ROOT / ".github/workflows/apply.yml").read_text())
    sciezki_apply = {p.split("/")[0] for p in apply_wf[True]["push"]["paths"]}
    domyslne = re.search(r'"--sciezki", default="([^"]+)"', watch_py)
    check("obserwator patrzy na te same katalogi co wyzwalacz apply.yml",
          domyslne and set(domyslne.group(1).split(",")) == sciezki_apply,
          f"apply={sorted(sciezki_apply)} watch={domyslne.group(1) if domyslne else None}")

    # 10. DWA JOBY, DWIE TOŻSAMOŚCI. Gdyby liczył i pisał jeden job, konto `plan` — impersonowalne
    # z KAŻDEGO pull requesta — zyskałoby `timeSeries.create`, czyli prawo do uciszenia wszystkich alertów.
    watch_wf = yaml.safe_load((ROOT / ".github/workflows/watch.yml").read_text())
    joby = watch_wf["jobs"]
    konta = {j: [k["with"]["service_account"] for k in joby[j]["steps"]
                 if isinstance(k, dict) and "google-github-actions/auth" in str(k.get("uses", ""))]
             for j in joby}
    check("job measure uzywa konta PLAN (read-only)",
          konta["measure"] == ["${{ vars.PLAN_SERVICE_ACCOUNT }}"], str(konta))
    check("job publish uzywa OSOBNEGO konta WATCH (jedyny zapis)",
          konta["publish"] == ["${{ vars.WATCH_SERVICE_ACCOUNT }}"], str(konta))

    iam = (ROOT / "iam-bootstrap/main.tf").read_text()
    check("konto watch dostaje WYLACZNIE metricWriter", 'role    = "roles/monitoring.metricWriter"' in iam)
    check("konto watch zwiazane refem (wezej niz plan, ktory bierze caly repository)",
          "attribute.ref/${var.watch_ref}" in iam)
    # PUŁAPKA #1975 W FORMIE ASERCJI: konto apply zaczyna od REFRESHU, więc musi umieć PRZECZYTAĆ każdy
    # zasób, którym zarządza. Brak `get`/`list` na nowym typie wywraca KAŻDY apply, także niezwiązany.
    for uprawnienie in ("monitoring.notificationChannels.get", "monitoring.notificationChannels.list",
                        "monitoring.metricDescriptors.get", "monitoring.metricDescriptors.list"):
        check(f"rola apply umie CZYTAC {uprawnienie} (refresh przed zmiana)",
              f'"{uprawnienie}"' in iam)


# --------------------------------------------------------------------- brownfield
def test_brownfield() -> None:
    """Przejęcie cudzego perimetru to moment, w którym najłatwiej nadpisać cudzą konfigurację."""
    print("\n== brownfield ==")

    imp = (ROOT / "tools/brownfield_import.sh").read_text()
    p = sh(["bash", "-n", str(ROOT / "tools/brownfield_import.sh")])
    check("brownfield_import.sh: skladnia", p.returncode == 0, p.stderr[-300:])

    # Bez argumentów MUSI paść — skrypt operujący na cudzym perimetrze nie może mieć domyślnych wartości.
    p = sh(["bash", str(ROOT / "tools/brownfield_import.sh")])
    check("brownfield_import.sh bez argumentow PADA", p.returncode != 0, f"rc={p.returncode}")

    # Kolejność jest istotą tej procedury: porównanie PRZED importem. Gdyby import był pierwszy, apply
    # wyrównałby żywy perimetr do treści repo.
    idx_diff = imp.find("--diff")
    idx_import = imp.find("import {")
    check("porownanie policy.yaml wykonuje sie PRZED blokiem import",
          -1 < idx_diff < idx_import, f"diff@{idx_diff} import@{idx_import}")

    # Skrypt nie może applikować — od apply jest człowiek po przeczytaniu planu.
    # Kod, nie dokumentacja: skrypt POKAZUJE człowiekowi komendę apply w instrukcji, ale sam jej nie wywołuje.
    imp_code = strip_heredocs(imp)
    check("brownfield_import.sh NIE applikuje",
          not re.search(r"^\s*terraform .*\bapply\b", imp_code, re.M),
          "znaleziono wywołanie apply w KODZIE (nie w instrukcji)")

    # Niepusty plan musi kończyć się kodem błędu, nie zachętą do apply.
    check("niepusty plan (kod 2) konczy sie bledem", 'exit 2' in imp)

    conv = (ROOT / "tools/perimeter_to_policy.py").read_text()
    # Kierunek jest jednoznaczny: rzeczywistość → plik. Skrypt, który nadpisuje policy.yaml automatycznie,
    # zamieniłby „przeczytaj różnicę" w „zaakceptuj różnicę".
    check("perimeter_to_policy.py nie nadpisuje policy.yaml",
          "w\")" not in conv and "write_text" not in conv)
    check("perimeter_to_policy.py bierze konfiguracje EGZEKWOWANA (status)",
          'live.get("status"' in conv)


# --------------------------------------------------------------------- rego
def test_external_egress_and_guard() -> None:
    """Egress poza GCP + guard na komendę, która promuje CAŁĄ konfigurację dry-run naraz.

    Guard sprawdzamy BEHAWIORALNIE, nie przez grep po treści workflowa: interesuje nas, czy wzorzec
    (a) nie trafia w siebie na czystym repo i (b) łapie realne wywołanie. Sam fakt istnienia stepa o
    właściwej nazwie nie dowodzi niczego — trzy razy w tym pliku guard tekstowy wywrócił się o dokumentację.
    """
    print("\n== egress zewnetrzny + guard dry-run ==")

    prof = (ROOT / "perimeter/profiles/bq-omni-external-read.yaml").read_text()
    check("profil zewnetrzny: tylko BigQuery w operacjach",
          "bigquery.googleapis.com" in prof and "aiplatform.googleapis.com" not in prof)
    check("profil zewnetrzny: risk high (jedyna regula wypuszczajaca dane z GCP)", "risk: high" in prof)

    member = (ROOT / "perimeter/projects.yaml").read_text()
    check("przykladowy czlonek uzywa profilu zewnetrznego (sciezka jest TESTOWANA)",
          "bq-omni-external-read" in member and "s3://" in member)

    rules = (ROOT / "terraform/rules.tf").read_text()
    check("external_resources renderowane w OBU konfiguracjach",
          rules.count("external_resources = each.value.external_resources") == 2,
          f"znaleziono {rules.count('external_resources = each.value.external_resources')}")

    # Wzorzec guardu wyciągamy z tego, co REALNIE się wykonuje (workflow + wołane akcje lokalne), żeby
    # test i CI sprawdzały DOKŁADNIE to samo wyrażenie na dokładnie tej samej powierzchni.
    wf = tekst_wykonywany("validate.yml")
    m = re.search(r"grep -rnE '([^']+)' tools \.github\b", wf)
    check("guard no-dry-run-commit istnieje na torze validate", m is not None)
    if not m:
        return
    pattern = m.group(1)

    def guard_hits() -> str:
        found = sh(["grep", "-rnE", pattern, "tools", ".github"], cwd=ROOT).stdout
        # ta sama filtracja komentarzy co w workflow
        return "\n".join(l for l in found.splitlines()
                          if not re.match(r"^[^:]+:[0-9]+:\s*#", l))

    check("guard nie trafia w SIEBIE na czystym repo", guard_hits() == "", guard_hits()[:300])

    bad = ROOT / "tools/zz_guard_probe.sh"
    bad.write_text("#!/usr/bin/env bash\ngcloud access-context-manager perimeters dry-run enforce p --policy=1\n")
    try:
        check("guard lapie realne wywolanie komendy commitujacej dry-run", guard_hits() != "")
    finally:
        bad.unlink()

    runbook = (STARTER / "docs/3-runbook-promocja-i-break-glass.md").read_text()
    check("runbook tlumaczy, DLACZEGO ta komenda jest zakazana",
          "perimeters dry-run enforce" in runbook and "trzydzieści dywizji" in runbook)


def test_lint_and_pinning() -> None:
    """tflint (jeśli jest) + guardy na to, czego brak nie widać w zielonym przebiegu.

    Dwa realne tryby awarii, oba złapane przy wdrażaniu tej bramki:
      * `tflint --chdir=X` szuka `.tflint.hcl` w X, nie w korzeniu repo — bez `--config` konfiguracja jest
        cicho ignorowana i przebieg jest zielony na domyślnym presecie, bez pluginu google;
      * akcje przypięte ruchomym tagiem to mutowalna referencja: kto kontroluje tag, kontroluje kod
        wykonywany z naszym tokenem OIDC — a job apply może zmienić perimetr całej organizacji.
    """
    print("\n== tflint i pinowanie akcji ==")

    cfg = ROOT / ".tflint.hcl"
    check("jest .tflint.hcl", cfg.exists())
    if cfg.exists():
        body = cfg.read_text()
        check("tflint: plugin google wlaczony", 'plugin "google"' in body and "enabled = true" in body)
        check("tflint: preset recommended", 'preset  = "recommended"' in body or 'preset = "recommended"' in body)

    wf = (ROOT / ".github/workflows/validate.yml").read_text()
    check("CI uruchamia tflint na obu stackach",
          wf.count("tflint --chdir=") == 2, f"wystapien: {wf.count('tflint --chdir=')}")
    # To jest guard NA GUARD: bez --config krok „tflint" istnieje i nic nie sprawdza.
    check("CI przekazuje tflint --config (inaczej konfiguracja jest ignorowana)",
          wf.count('--config="$PWD/.tflint.hcl"') == 2)
    check("CI ustawia prog severity na notice (regulyo dokumentacji sa Notice)",
          "--minimum-failure-severity=notice" in wf)
    check("pre-commit ma hook terraform_tflint",
          "terraform_tflint" in (ROOT / ".pre-commit-config.yaml").read_text())

    # Pinowanie: każda akcja third-party z pełnym SHA. Wzorzec ten sam co w guardzie CI.
    #
    # `.github/actions/*/action.yml` JEST na tej liście, bo akcje złożone też wołają akcje obce (bramki
    # treści pobierają `setup-python`). Lista, która ich nie obejmuje, zostawiłaby bez guardu pliki
    # wykonujące najwięcej — a to ta sama luka, którą zamyka DEC-16, tylko o piętro niżej.
    uses = []
    for f in (list((ROOT / ".github/workflows").glob("*.yml"))
              + sorted((ROOT / ".github/actions").glob("*/action.yml"))
              + [ROOT / "contrib/action.yml"]):
        # Zakotwiczone na początku linii: `uses:` pojawia się też WEWNĄTRZ wzorca grepa w guardzie CI,
        # a niezakotwiczony wzorzec wyciągał stamtąd fragmenty regexa i zgłaszał je jako nieprzypięte akcje.
        uses += re.findall(r"^\s*-?\s*uses:\s*(\S+)", f.read_text(), re.M)
    third_party = [u for u in uses if not u.startswith("./") and not u.startswith("ORG/")]
    unpinned = [u for u in third_party if not re.search(r"@[0-9a-f]{40}$", u)]
    check("wszystkie akcje third-party przypiete SHA-em", not unpinned, f"bez SHA: {unpinned}")
    check("guard na pinowanie jest w CI", "actions pinned to a SHA" in tekst_wykonywany("validate.yml"))
    check("jest dependabot (pin bez aktualizacji to martwy pin)",
          (ROOT / ".github/dependabot.yml").exists())

    # `have()` nie wystarcza: `tflint` bywa shimem menedżera wersji, który istnieje na PATH i pada przy
    # uruchomieniu (brak przypiętej wersji). Wtedy FAIL mówiłby o konfiguracji tflinta, nie o kodzie startera.
    # `have()` nie wystarcza: `tflint` bywa shimem menedżera wersji, który istnieje na PATH i pada przy
    # uruchomieniu (brak przypiętej wersji). Wtedy FAIL mówiłby o konfiguracji tflinta, nie o kodzie startera.
    runnable = have("tflint") and sh(["tflint", "--version"]).returncode == 0
    if not runnable:
        print("  SKIP  tflint nieobecny albo nieuruchamialny — zainstaluj i przypnij wersje")
        return

    # BEZ `--init` plugin `google` nie jest pobrany, `tflint` konczy sie bledem „plugin not found", a kod
    # nizej drukowal na to SKIP i szedl dalej. Efekt: linter byl instalowany w CI, opisany w komentarzu
    # workflow jako nosny — i NIGDY nie uruchamiany. Dwie asercje istnialy w kodzie i nie wykonaly sie ani
    # razu. To jest dokladnie ta klasa bledu, ktora ten starter tropi gdzie indziej: bramka, ktora nie ma
    # jak sie wykonac, nie jest bramka. `--init` jest wiec CZESCIA testu, z wlasna asercja.
    init = sh(["tflint", "--init", f"--config={ROOT}/.tflint.hcl"], cwd=ROOT)
    check("tflint --init pobiera plugin google (bez niego linter milczy zamiast sprawdzac)",
          init.returncode == 0, (init.stdout + init.stderr)[-500:])
    if init.returncode != 0:
        return

    for stack in ["terraform", "iam-bootstrap"]:
        p = sh(["tflint", f"--chdir={stack}", f"--config={ROOT}/.tflint.hcl",
                "--minimum-failure-severity=notice"], cwd=ROOT)
        # Po udanym `--init` „plugin not found" nie jest juz stanem srodowiska, tylko realna awaria bramki —
        # dlatego NIE ma tu sciezki cichego pominiecia. Kazdy inny wynik to werdykt lintera o starterze.
        check(f"tflint czysty: {stack}", p.returncode == 0, (p.stdout + p.stderr)[-600:])


def test_acm_naming() -> None:
    """Nazwy obiektów ACM: litera na początku, dalej tylko alfanumeryczne i `_`.

    DLACZEGO osobny test, skoro pilnuje tego schema: `check-jsonschema` jest opcjonalny i lokalnie się
    SKIPuje — i dokładnie dlatego przez kilka commitów siedział tu `ai-core` oraz `corp-network`, czyli nazwy,
    które API odrzuca. Ten test używa wyłącznie stdlib, więc nie ma jak się nie wykonać. Myślnik w `title`
    jest w porządku — ograniczenie dotyczy tylko short_name.
    """
    print("\n== nazwy obiektow ACM ==")
    acm_name = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,49}$")

    policy = yaml.safe_load((ROOT / "perimeter/policy.yaml").read_text())
    peri_name = policy["perimeter"]["name"]
    check(f"nazwa perimetru {peri_name!r} zgodna z API (bez myslnika)", bool(acm_name.match(peri_name)))

    levels = []
    for f in sorted((ROOT / "perimeter/access-levels").glob("*.yaml")):
        levels += yaml.safe_load(f.read_text())["access_levels"]
    check("katalog access levels nie jest pusty", len(levels) > 0)
    bad = [al["name"] for al in levels if not acm_name.match(al["name"])]
    check("nazwy access levels zgodne z API", not bad, f"niepoprawne: {bad}")

    # Nazwy w kompozycji muszą wskazywać istniejący poziom — literówka daje błąd API, nie planu.
    known = {al["name"] for al in levels}
    dangling = [(al["name"], req) for al in levels for req in al.get("required_access_levels", []) if req not in known]
    check("required_access_levels wskazuja istniejace poziomy", not dangling, f"wiszace: {dangling}")

    # Poziomy używane przez członków i baseline też muszą istnieć — inaczej reguła autoryzuje nieistniejący kontekst.
    used = set()
    for czlonek in yaml.safe_load((ROOT / "perimeter/projects.yaml").read_text())["members"]:
        for prof in czlonek.get("profiles", []):
            used |= set(prof.get("params", {}).get("access_levels", []))
    for rule in policy.get("baseline_ingress", []):
        used |= set(rule.get("access_levels", []))
    check("poziomy uzywane w projects.yaml/baseline istnieja w katalogu", used <= known, f"brakuje: {sorted(used - known)}")


# --------------------------------------------------- access levels: kompozycja i combining_function
def test_access_levels_ksztalt() -> None:
    """Osłabienia access levelu, których NIE WIDAĆ w diffie — i jedno ograniczenie, które było nasze.

    DLACZEGO ten test mierzy PLAN, a nie tekst YAML-a: pytanie brzmi „co poleci do API", a między
    deklaracją a wywołaniem stoi renderer. Dokładnie tam siedział defekt, przez który materiał przez
    kilka miesięcy twierdził coś nieprawdziwego o API Google: blok `conditions` renderował się
    BEZWARUNKOWO, więc poziom złożony wyłącznie z `required_access_levels` dostawał doklejony PUSTY
    warunek, a ACM odrzucał go jako `AccessLevel definition has a trivial condition`. Wniosek zapisany
    wtedy w komentarzach („kompozycja musi nieść własny warunek") był wnioskiem o NASZYM kodzie.
    ZMIERZONE 2026-08-11 na żywym ACM: ten sam poziom wysłany surowym POST-em POWSTAJE bez błędu.

    Druga połowa testu pilnuje `combining_function: OR`. To jest jednosłowny diff, po którym polityka
    jest SŁABSZA („region ORAZ korpo-sieć" → „region ALBO korpo-sieć"), a API przyjmuje go bez
    ostrzeżenia (zmierzone: odpowiedź 200 z `combiningFunction: OR`). Każdy negatyw ma tu parę
    pozytywną — bez niej „bramka odrzuca OR" znaczyłoby tylko „bramka odrzuca wszystko".
    """
    print("\n== access levels: kompozycja i combining_function ==")
    if not have("terraform"):
        check("terraform dostepny (access levels)", False, "brak terraform na PATH — pomijam")
        return

    tf = ROOT / "terraform"
    probe = ROOT / "perimeter/access-levels/zz-selftest-poziomy.yaml"
    out = "zz_poziomy.tfplan"

    def plan(poziom: str, zapisz: bool = False):
        probe.write_text("schema_version: 1\naccess_levels:\n" + textwrap.indent(textwrap.dedent(poziom).strip(), "  ") + "\n")
        cmd = ["terraform", f"-chdir={tf}", "plan", "-no-color", "-input=false", "-lock=false"]
        if zapisz:
            cmd.append(f"-out={out}")
        return sh(cmd)

    kompozycja_bez_wlasnego_warunku = """
        - name: zz_kompozycja
          title: "Composition without a condition of its own"
          combining_function: AND
          required_access_levels:
            - corp_network
    """

    try:
        # 1. KOMPOZYCJA BEZ WŁASNEGO WARUNKU — legalna po stronie API, więc plan ma przejść…
        p = plan(kompozycja_bez_wlasnego_warunku, zapisz=True)
        check("access level: kompozycja bez wlasnego warunku PRZECHODZI plan",
              p.returncode == 0, p.stdout[-500:] + p.stderr[-700:])

        # …i renderować DOKŁADNIE JEDEN warunek. To jest właściwa asercja: sam zielony plan przeszedłby
        # także na kodzie doklejającym pusty warunek (Terraform go akceptuje, odrzuca dopiero ACM).
        warunki = None
        if p.returncode == 0:
            s = sh(["terraform", f"-chdir={tf}", "show", "-json", out])
            if s.returncode == 0:
                for r in json.loads(s.stdout)["planned_values"]["root_module"].get("resources", []):
                    if r["type"] == "google_access_context_manager_access_level" and "zz_kompozycja" in r["address"]:
                        warunki = r["values"]["basic"][0]["conditions"]
        (tf / out).unlink(missing_ok=True)
        check("access level: kompozycja renderuje DOKLADNIE JEDEN warunek (bez pustego)",
              warunki is not None and len(warunki) == 1 and warunki[0].get("required_access_levels"),
              f"conditions={warunki!r}")

        # 2. OR BEZ UZASADNIENIA — plan ma paść, i to z nazwą poziomu w komunikacie. Bramka, która pada
        #    z komunikatem o wyrażeniu HCL, nie mówi wnioskodawcy, który poziom poprawić.
        or_bazowy = """
            - name: zz_or
              title: "Region OR corporate network"
              combining_function: OR
              {reason}regions: [PL, DE]
              required_access_levels:
                - corp_network
        """
        p = plan(or_bazowy.format(reason=""))
        check("access level: OR bez or_reason ODRZUCONY na planie",
              p.returncode != 0 and "or_reason" in (p.stdout + p.stderr) and "zz_or" in (p.stdout + p.stderr),
              (p.stdout[-400:] + p.stderr[-400:]))

        # 3. ANTY-TAUTOLOGIA: ten sam OR z napisanym powodem PRZECHODZI. Furtka ma działać — inaczej to
        #    jest zakaz OR-a, a wtedy poprawny wzorzec „korpo-sieć ALBO zarządzane urządzenie" ucieka
        #    do `custom_expression`, czyli w miejsce trudniejsze do audytu.
        p = plan(or_bazowy.format(reason='or_reason: "zarzadzany laptop pracuje spoza korpo-sieci i ma miec dostep"\n              '))
        check("access level: TEN SAM OR z or_reason PRZECHODZI (anty-tautologia)",
              p.returncode == 0, p.stdout[-400:] + p.stderr[-700:])

        # 4. Uzasadnienie skrócone do „ok" degeneruje furtkę do pola do odhaczenia.
        p = plan(or_bazowy.format(reason='or_reason: "bo tak"\n              '))
        check("access level: OR z uzasadnieniem ponizej progu ODRZUCONY",
              p.returncode != 0, p.stdout[-300:] + p.stderr[-300:])

        # 5. OR przy JEDNYM warunku nie robi nic — `combiningFunction` łączy warunki, a nie atrybuty
        #    w jednym warunku. W pliku wygląda jak decyzja i ożywa jako osłabienie w dniu, w którym ktoś
        #    dołoży `required_access_levels`.
        p = plan("""
            - name: zz_or_jeden
              title: "EU only with a pointless OR"
              combining_function: OR
              or_reason: "powod napisany, ale nie ma czego laczyc alternatywa"
              regions: [DE, FR, NL]
        """)
        check("access level: OR przy jednym warunku ODRZUCONY",
              p.returncode != 0, p.stdout[-300:] + p.stderr[-300:])

        # 6. Poziom bez ANI JEDNEGO warunku. Do naprawy z p.1 chronił nas przed nim przypadek (pusty
        #    warunek odrzucało API); teraz jedyną barierą jest `precondition`, więc ona musi być mierzona.
        p = plan("""
            - name: zz_pusty
              title: "Level with no condition at all"
        """)
        check("access level: poziom bez zadnego warunku ODRZUCONY",
              p.returncode != 0 and "zz_pusty" in (p.stdout + p.stderr),
              p.stdout[-300:] + p.stderr[-300:])
    finally:
        # Plik-sonda MUSI zniknąć: kolejne testy czytają `perimeter/access-levels/` jako deklaracje repo
        # i policzyłyby sondę jako poziom materiału.
        probe.unlink(missing_ok=True)
        (tf / out).unlink(missing_ok=True)

    # KONTROLA, że sprzątanie zadziałało — inaczej ten test cicho zatruwa wszystkie następne.
    p = sh(["terraform", f"-chdir={tf}", "plan", "-no-color", "-input=false", "-lock=false"])
    check("access level: po sprzatnieciu sondy plan repo jest znowu zielony", p.returncode == 0,
          p.stdout[-300:] + p.stderr[-500:])


def test_rego() -> None:
    print("\n== reguly OPA ==")
    if not have("conftest"):
        check("conftest dostepny", False, "brak conftest na PATH — pomijam reguly")
        return

    p = sh(["conftest", "verify", "--policy", "policy"], cwd=ROOT)
    passed = "0 failures" in p.stdout
    check("conftest verify (testy jednostkowe regul)", p.returncode == 0 and passed, p.stdout[-1500:])

    # Realne deklaracje ze startera muszą przechodzić bramki onboardingu.
    decl = sh([sys.executable, "tools/collect_declarations.py", "--today", "2026-07-28"], cwd=ROOT)
    check("collect_declarations.py dziala", decl.returncode == 0, decl.stderr[-500:])

    # --- odczyt stanu ZASTOSOWANEGO z kontraktu ------------------------------------------------------
    #
    # `applied_stages_known` jest wejściem bramki bezpieczeństwa, więc każdy powód, dla którego kontraktu
    # nie da się zaufać, musi dawać `False` — i musi to robić CICHO POD WZGLĘDEM KODU WYJŚCIA, a głośno
    # w treści. Wywrócenie narzędzia zamieniłoby uszkodzony artefakt pobierany po sieci w czerwone
    # WSZYSTKIM pull requestom; `False` czyni surowszą wyłącznie bramkę promocji.
    def etapy_dla(kontrakt, plik: str) -> tuple[dict, bool, int]:
        (ROOT / plik).write_text(json.dumps(kontrakt) if not isinstance(kontrakt, str) else kontrakt)
        r = sh([sys.executable, "tools/collect_declarations.py", "--contract", plik], cwd=ROOT)
        if r.returncode != 0:
            return {}, False, r.returncode
        d = json.loads(r.stdout)
        return d.get("applied_stages", {}), d.get("applied_stages_known"), r.returncode

    dobry_kontrakt = {
        "schema_version": 1,
        "members_published": True,
        "members": [{"division": "example-division", "project_id": "prj-x", "stage": "enforced"},
                    {"division": "example-division", "project_id": "prj-y", "stage": "dry-run"}],
    }
    etapy, znany, rc = etapy_dla(dobry_kontrakt, "kontrakt-ok.json")
    check("collect_declarations --contract: etapy odczytane, klucz jak w projects_file.klucz()",
          rc == 0 and znany is True
          and etapy == {"example-division-prj-x": "enforced", "example-division-prj-y": "dry-run"},
          f"rc={rc} znany={znany} etapy={etapy}")

    # Bez flagi w ogóle — stan nieznany, bramka uzbrojona. To jest zachowanie każdej ścieżki, która
    # kontraktu nie poda (pre-commit u dewelopera, repo przed pierwszym apply).
    d = json.loads(decl.stdout)
    check("collect_declarations bez --contract: applied_stages_known = false",
          d.get("applied_stages_known") is False and d.get("applied_stages") == {},
          str({k: d.get(k) for k in ("applied_stages", "applied_stages_known")}))

    # Cztery powody nieufności. Każdy osobno, bo każdy da się „naprawić" tak, że pozostałe nadal przechodzą.
    for opis, kontrakt, plik in (
        ("publish_members: false (pusta lista jest dwuznaczna)",
         dict(dobry_kontrakt, members_published=False, members=[]), "kontrakt-bez-listy.json"),
        ("nieznana wersja schematu (pole `stage` moze znaczyc co innego)",
         dict(dobry_kontrakt, schema_version=99), "kontrakt-zla-wersja.json"),
        ("wpis czlonka bez `stage` (czesciowa mapa = poprawny werdykt ze zlego powodu)",
         dict(dobry_kontrakt, members=[{"division": "d", "project_id": "p"}]), "kontrakt-bez-stage.json"),
        ("plik nieczytelny (uszkodzone pobranie)", '{"schema_version": 1, "mem', "kontrakt-uszkodzony.json"),
    ):
        etapy, znany, rc = etapy_dla(kontrakt, plik)
        check(f"collect_declarations --contract: {opis} -> stan NIEZNANY",
              rc == 0 and znany is False and etapy == {}, f"rc={rc} znany={znany} etapy={etapy}")

    # ANTY-TAUTOLOGIA dla całej czwórki wyżej: narzędzie, które zawsze mówi „nie wiem", przeszłoby je
    # wszystkie. Pozytyw jest o linijkę wyżej, ale bez tej asercji łatwo go usunąć razem z regresją.
    check("collect_declarations --contract: dobry kontrakt DAJE znany stan (test anty-tautologiczny)",
          etapy_dla(dobry_kontrakt, "kontrakt-ok2.json")[1] is True)
    (ROOT / "declarations.json").write_text(decl.stdout)
    p = sh(["conftest", "test", "--policy", "policy", "--namespace", "vpcsc.onboarding", "declarations.json"], cwd=ROOT)
    check("przykladowy czlonek przechodzi bramki onboardingu", p.returncode == 0, p.stdout[-1200:])

    # NEGATYW: promocja do enforced dzień po wejściu do dry-run musi zostać odrzucona.
    doc = json.loads(decl.stdout)
    name = next(iter(doc["members"]))
    doc["members"][name]["stage"] = "enforced"
    doc["violations_last_window"] = {name: 0}
    (ROOT / "bad-promotion.json").write_text(json.dumps(doc))
    p = sh(["conftest", "test", "--policy", "policy", "--namespace", "vpcsc.onboarding", "bad-promotion.json"], cwd=ROOT)
    check("promocja przed oknem obserwacji jest ODRZUCANA", p.returncode != 0, p.stdout[-800:])

    # NEGATYW: usunięcie aiplatform z baseline'u musi zostać odrzucone (to jest powód istnienia perimetru).
    doc2 = json.loads(decl.stdout)
    doc2["policy"]["restricted_services"] = [s for s in doc2["policy"]["restricted_services"]
                                             if s != "aiplatform.googleapis.com"]
    (ROOT / "bad-baseline.json").write_text(json.dumps(doc2))
    p = sh(["conftest", "test", "--policy", "policy", "--namespace", "vpcsc.onboarding", "bad-baseline.json"], cwd=ROOT)
    check("baseline bez aiplatform jest ODRZUCANY", p.returncode != 0, p.stdout[-800:])

    # --- anty-samo-zablokowanie: projekty płaszczyzny sterowania -------------------------------------
    # Jedyny tryb awarii tego repozytorium, którego `git revert` NIE COFA: projekt z bucketem stanu wciągnięty
    # do perimetru odcina konto apply od jego własnego stanu (apply woła spoza granicy), a apply rewertu też
    # potrzebuje stanu. Dlatego bramka ma tu więcej testów niż inne — cicha dziura kosztuje interwencję
    # człowieka z uprawnieniami org-level, a nie kolejny commit.
    czlonek = json.loads(decl.stdout)["members"][name]

    def onboarding_na(doc: dict, plik: str):
        (ROOT / plik).write_text(json.dumps(doc))
        return sh(["conftest", "test", "--policy", "policy", "--namespace", "vpcsc.onboarding", plik], cwd=ROOT)

    doc = json.loads(decl.stdout)
    doc["policy"]["control_plane_projects"] = [czlonek["project_id"]]
    p = onboarding_na(doc, "bad-control-plane.json")
    check("czlonek na liscie control_plane_projects jest ODRZUCANY", p.returncode != 0, p.stdout[-800:])
    # Komunikat MUSI tłumaczyć konsekwencję: samo „odrzucone" nie mówi czytelnikowi, czym ryzykuje ani
    # dlaczego nie wystarczy zmergować i cofnąć.
    check("komunikat bramki tlumaczy konsekwencje (stan, brak rewertu, org-level)",
          all(s in p.stdout for s in ("bucketa stanu", "NIE cofa", "org-level")), p.stdout[-600:])

    # ANTY-TAUTOLOGIA: niepusta lista wskazująca INNY projekt musi przepuścić zwykłego członka. Bez tego
    # testu reguła odrzucająca wszystko przechodziłaby test negatywny i wyglądała na działającą.
    doc = json.loads(decl.stdout)
    doc["policy"]["control_plane_projects"] = ["prj-example-tfstate-admin"]
    p = onboarding_na(doc, "ok-control-plane.json")
    check("zwykly projekt PRZECHODZI mimo niepustej listy (test anty-tautologiczny)",
          p.returncode == 0, p.stdout[-600:])

    # Lista przyjmuje project_id ALBO numer — bramka, którą omija się wyborem formatu, nie jest bramką.
    doc = json.loads(decl.stdout)
    doc["policy"]["control_plane_projects"] = [czlonek["project_number"]]
    p = onboarding_na(doc, "bad-control-plane-numer.json")
    check("dopasowanie po NUMERZE projektu tez ODRZUCA", p.returncode != 0, p.stdout[-600:])

    # Numer wpisany w YAML-u bez cudzysłowów jest liczbą, a `project_number` jest zawsze stringiem —
    # porównanie nigdy by nie trafiło. Bramka wyglądałaby na uzbrojoną i nie łapała niczego.
    doc = json.loads(decl.stdout)
    doc["policy"]["control_plane_projects"] = [int(czlonek["project_number"])]
    p = onboarding_na(doc, "bad-control-plane-typ.json")
    check("numer NIE-string jest ODRZUCANY (inaczej bramka jest cichym no-opem)",
          p.returncode != 0, p.stdout[-600:])

    # Furtka istnieje po to, żeby nikt nie musiał WYŁĄCZAĆ bramki: usunięcie projektu z listy rozbraja ją
    # dla wszystkich członków naraz i wygląda w diffie jak sprzątanie.
    doc = json.loads(decl.stdout)
    doc["policy"]["control_plane_projects"] = [czlonek["project_id"]]
    doc["members"][name]["control_plane_exception"] = {
        "justification": "stan Terraform przeniesiony poza perimetr, apply czyta go spoza granicy"}
    p = onboarding_na(doc, "ok-control-plane-wyjatek.json")
    check("jawny control_plane_exception PRZEPUSZCZA wpis (furtka zamiast wylaczania bramki)",
          p.returncode == 0, p.stdout[-600:])

    # Wyjątek „na zapas" na projekcie spoza listy rozbrajałby bramkę zawczasu: dopisany do wszystkich plików
    # członków sprawia, że późniejsze rozszerzenie control_plane_projects nie odpala ani razu.
    doc = json.loads(decl.stdout)
    doc["members"][name]["control_plane_exception"] = {
        "justification": "wyjatek wpisany zanim projekt trafil na liste plaszczyzny sterowania"}
    p = onboarding_na(doc, "bad-control-plane-zapas.json")
    check("wyjatek 'na zapas' (projekt spoza listy) jest ODRZUCANY", p.returncode != 0, p.stdout[-600:])

    # Sekcja musi ZOSTAĆ w policy.yaml: brak sekcji i pusta lista dają ten sam skutek, więc różnicę wymusza
    # `required` w schemacie. check-jsonschema jest jednak opcjonalny i lokalnie się SKIPuje — ta asercja
    # używa samego YAML-a, więc nie ma jak się nie wykonać (ta sama lekcja co w test_acm_naming).
    polityka = yaml.safe_load((ROOT / "perimeter/policy.yaml").read_text())
    check("policy.yaml deklaruje sekcje control_plane_projects (nie da sie jej po cichu usunac)",
          isinstance(polityka.get("control_plane_projects"), list), str(sorted(polityka.keys())))

    # --- bramka promocji pyta o PRZEJŚCIE, nie o stan (kontrakt = etapy zastosowane) -----------------
    #
    # Reguła związana wyłącznie z `stage: enforced` obowiązuje DOPÓKI członek jest enforced — także długo
    # po tym, jak decyzja zapadła. A wtedy naruszenia w oknie są ODMOWAMI (granica działa), więc członek
    # działający zgodnie z przeznaczeniem odrzuca każdy niezwiązany pull request. Trzy przebiegi niżej
    # trzymają razem trzy własności, których żadna z osobna nie odróżnia naprawy od wyłączenia bramki.
    def z_kontraktem(doc: dict, etapy, znany: bool) -> dict:
        d = json.loads(json.dumps(doc))
        d["applied_stages"] = etapy
        d["applied_stages_known"] = znany
        return d

    promowany = json.loads(decl.stdout)
    promowany["members"][name]["stage"] = "enforced"
    # Brudne okno: 30 wpisów. Przed promocją to prognoza ryzyka, po niej — liczba odmów.
    promowany["violations_last_window"] = {name: 30}

    p = onboarding_na(z_kontraktem(promowany, {name: "dry-run"}, True), "przejscie-bez-dowodu.json")
    check("PRZEJSCIE do enforced bez czystego okna jest ODRZUCANE (kontrakt mowi dry-run)",
          p.returncode != 0, p.stdout[-800:])

    p = onboarding_na(z_kontraktem(promowany, {name: "enforced"}, True), "juz-egzekwowany.json")
    check("czlonek JUZ egzekwowany nie blokuje niezwiazanego wniosku mimo 30 odmow",
          p.returncode == 0, p.stdout[-800:])

    # FAIL-CLOSED. Gdyby brak wiedzy o stanie zastosowanym przepuszczał, wyłącznikiem tej bramki byłoby
    # NIEPOBRANIE kontraktu — czyli usunięcie pliku. Degradacja ma iść w stronę surowszą.
    p = onboarding_na(z_kontraktem(promowany, {}, False), "stan-nieznany.json")
    check("brak wiedzy o stanie zastosowanym zachowuje sie jak PRZEJSCIE (fail-closed)",
          p.returncode != 0, p.stdout[-800:])

    # Kontrakt czytelny, ale członka w nim nie ma — pierwszy apply tego wpisu. „Nie ma go" nie może
    # znaczyć „już włączony": to najostrzejszy możliwy stan, a wygląda jak brak danych.
    p = onboarding_na(z_kontraktem(promowany, {"inna-dywizja-inny-projekt": "enforced"}, True),
                      "stan-bez-czlonka.json")
    check("czlonek NIEOBECNY w kontrakcie tez jest przejsciem", p.returncode != 0, p.stdout[-800:])

    # NEGATYW na plan-JSON: reguła z ANY_IDENTITY i z method="*" musi paść.
    bad_plan = {
        "planned_values": {"root_module": {"resources": [{
            "address": "google_access_context_manager_service_perimeter_ingress_policy.rule[\"x\"]",
            "type": "google_access_context_manager_service_perimeter_ingress_policy",
            "values": {
                "ingress_from": [{"identity_type": "ANY_IDENTITY", "identities": [], "sources": []}],
                "ingress_to": [{"resources": ["*"], "operations": [
                    {"service_name": "aiplatform.googleapis.com", "method_selectors": [{"method": "*"}]}]}],
            }}]}},
        "resource_changes": [],
    }
    (ROOT / "bad-plan.json").write_text(json.dumps(bad_plan))
    p = sh(["conftest", "test", "--policy", "policy", "--namespace", "vpcsc.perimeter", "bad-plan.json"], cwd=ROOT)
    check("plan z ANY_IDENTITY / method=* / resources=* jest ODRZUCANY", p.returncode != 0, p.stdout[-800:])


# ------------------------------------------- lista plaszczyzny sterowania kontra reszta repozytorium
#
# Bramka OPA wyzej odrzuca czlonka Z LISTY `control_plane_projects`. Sama lista byla do tej pory
# deklaracja bez zadnej konfrontacji: projekt plaszczyzny sterowania, ktorego na niej NIE MA, przechodzil
# przez tamta bramke jak zwykly wniosek. Ten zestaw testuje `tools/control_plane_check.py`, czyli guard
# spojnosci tej listy — i kazdy negatyw ma tu pare anty-tautologiczna, bo guard odrzucajacy wszystko jest
# nieodrozninalny od guardu dzialajacego, dopoki nikt nie zobaczyl, jak przepuszcza.

# Atrapa `gcloud` dla JEDNEGO wywolania: `storage buckets describe`. `projectNumber` podaje WYLACZNIE przy
# `--raw` — i to nie jest kaprys atrapy, tylko odwzorowanie zmierzonej wlasnosci gcloud: bez `--raw` zwraca
# on wlasny, znormalizowany ksztalt zasobu, w ktorym tego pola NIE MA W OGOLE. Dzieki temu zdjecie `--raw`
# z narzedzia wywraca test pozytywny, zamiast po cichu zamienic bramke w „nie ustalilem, jade dalej".
ATRAPA_GCLOUD_STORAGE = '''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
if argv[:3] != ["storage", "buckets", "describe"]:
    sys.stderr.write("atrapa: nieobslugiwane wywolanie %s\\n" % argv)
    sys.exit(2)
odp = {"name": argv[3]}
if "--raw" in argv:
    odp["projectNumber"] = os.environ.get("ATRAPA_NUMER", "111111111111")
print(json.dumps(odp))
'''


def test_control_plane_lista() -> None:
    print("\n== guard spojnosci listy control_plane_projects ==")
    polityka = ROOT / "perimeter/policy.yaml"
    versions = ROOT / "terraform/versions.tf"
    tfvars = ROOT / "iam-bootstrap/terraform.tfvars"
    oryginal = polityka.read_text()

    bin_dir = ROOT / "stub-bin-storage"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "gcloud").write_text(ATRAPA_GCLOUD_STORAGE)
    (bin_dir / "gcloud").chmod(0o755)
    env_zywy = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")

    def uruchom(*extra, env=None):
        return sh([sys.executable, "tools/control_plane_check.py", *extra], cwd=ROOT, env=env)

    def podmien(stare, nowe):
        polityka.write_text(polityka.read_text().replace(stare, nowe))

    # --- 1. stan wyjsciowy: rozpakowany starter przechodzi tryb offline ---------------------------
    p = uruchom()
    check("control_plane_check offline przechodzi na rozpakowanym starterze", p.returncode == 0,
          p.stdout + p.stderr)
    # ZIELONE MA MOWIC, CZEGO NIE SPRAWDZILO. Szablon niesie placeholder w `monitoring.project_id`
    # i pusty stack tozsamosci — gdyby guard milczal o pominieciach, jego „OK" znaczyloby wiecej,
    # niz znaczy, i pierwszy odbiorca uznalby liste za skonfrontowana z czymkolwiek.
    check("zielony wynik wymienia POMINIETE (placeholder, brak tfvars, tryb offline)",
          p.stdout.count("POMINIETE") >= 3, p.stdout)

    # --- 2. bucket stanu: HCL kontra policy.yaml --------------------------------------------------
    tresc_versions = versions.read_text()
    versions.write_text(tresc_versions.replace('bucket = "<STATE_BUCKET>"', 'bucket = "bkt-inny-stan"', 1))
    p = uruchom()
    check("rozjazd backendu z contract.state_bucket jest ODRZUCANY",
          p.returncode != 0 and "rozjechany" in p.stdout, p.stdout + p.stderr)
    versions.write_text(tresc_versions)
    check("ANTY-TAUTOLOGIA: po zrownaniu nazw ta sama komenda PRZECHODZI", uruchom().returncode == 0)

    # --- 3. monitoring.project_id musi byc na liscie ----------------------------------------------
    podmien('project_id: "<MONITORING_PROJECT>"', 'project_id: "prj-example-monitoring"')
    p = uruchom()
    check("monitoring.project_id spoza listy jest ODRZUCANY",
          p.returncode != 0 and "monitoring.project_id" in p.stdout, p.stdout + p.stderr)
    podmien("control_plane_projects: []", 'control_plane_projects: ["prj-example-monitoring"]')
    check("ANTY-TAUTOLOGIA: po dopisaniu projektu do listy ta sama polityka PRZECHODZI",
          uruchom().returncode == 0, uruchom().stdout)
    polityka.write_text(oryginal)

    # --- 4. stack tozsamosci: projekt, w ktorym stoja konta i pula WIF -----------------------------
    tfvars.write_text('identity_project_id = "prj-example-vpcsc-admin"\n'
                      'state_bucket        = "<STATE_BUCKET>"\n')
    p = uruchom()
    check("identity_project_id spoza listy jest ODRZUCANY",
          p.returncode != 0 and "identity_project_id" in p.stdout, p.stdout + p.stderr)
    podmien("control_plane_projects: []", 'control_plane_projects: ["prj-example-vpcsc-admin"]')
    check("ANTY-TAUTOLOGIA: z projektem na liscie ten sam tfvars PRZECHODZI", uruchom().returncode == 0)
    polityka.write_text(oryginal)
    tfvars.unlink()

    # --- 5. tryb zywy: wlasciciel bucketa stanu z API ----------------------------------------------
    # Numer z atrapy NIE JEST na liscie -> bramka ma odrzucic i powiedziec, co dopisac. To jest jedyne
    # sprawdzenie w tym repo, ktore konfrontuje liste z rzeczywistoscia, a nie z kolejnym plikiem.
    # Placeholdery podmieniamy na wartosci wygladajace na wdrozone: w trybie zywym placeholder jest
    # osobnym bledem (test 6), a tutaj badamy sciezke, w ktorej konfiguracja JEST dokonczona.
    versions.write_text(tresc_versions.replace('"<STATE_BUCKET>"', '"bkt-example-tfstate"'))
    podmien('state_bucket: "<STATE_BUCKET>"', 'state_bucket: "bkt-example-tfstate"')
    podmien('project_id: "<MONITORING_PROJECT>"', 'project_id: "prj-example-monitoring"')
    podmien("control_plane_projects: []", 'control_plane_projects: ["prj-example-monitoring"]')
    p = uruchom("--live", env=env_zywy)
    check("tryb zywy: projekt bucketa stanu spoza listy jest ODRZUCANY",
          p.returncode != 0 and "111111111111" in p.stdout, p.stdout + p.stderr)
    podmien('control_plane_projects: ["prj-example-monitoring"]',
            'control_plane_projects: ["prj-example-monitoring", "111111111111"]')
    p = uruchom("--live", env=env_zywy)
    # Ten sam test pilnuje `--raw` w narzedziu: bez tej flagi atrapa (jak zywy gcloud) nie poda numeru
    # i bramka padnie na „API nie podalo projectNumber".
    check("ANTY-TAUTOLOGIA: z numerem projektu na liscie tryb zywy PRZECHODZI",
          p.returncode == 0 and "jest na liscie" in p.stdout, p.stdout + p.stderr)

    # --- 6. placeholder w trybie zywym = konfiguracja niedokonczona --------------------------------
    polityka.write_text(oryginal)
    versions.write_text(tresc_versions)
    podmien("control_plane_projects: []", 'control_plane_projects: ["111111111111"]')
    p = uruchom("--live", env=env_zywy)
    check("tryb zywy ODRZUCA placeholder w monitoring.project_id (offline go przepuszcza)",
          p.returncode != 0 and "placeholder" in p.stdout, p.stdout + p.stderr)
    polityka.write_text(oryginal)

    # --- 7. wpiecie w pipeline ---------------------------------------------------------------------
    # Narzedzie uruchamiane recznie nie jest bramka. Sprawdzamy oba wpiecia ORAZ sciezke `tools/**`
    # w wyzwalaczu planu: bez niej pull request zmieniajacy sam guard nie uruchamialby go ani razu.
    # Czytamy KROKI z YAML-a, nie tekst pliku: komentarz w validate.yml tlumaczy, ze tryb zywy jest
    # w plan.yml, wiec `"--live" not in tekst` wywracalo sie o WLASNA dokumentacje. Ta sama pulapka,
    # ktora w tym repo trzy razy wywrocila guardy tekstowe (patrz `strip_heredocs`).
    walidacja = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text())
    plan = tekst_wykonywany("plan.yml")
    wywolania = [str(k.get("run", "")) for k, _ in kroki_workflow(walidacja)
                 if "tools/control_plane_check.py" in str(k.get("run", ""))]
    check("validate.yml uruchamia control_plane_check.py w trybie offline",
          len(wywolania) == 1 and "--live" not in wywolania[0], str(wywolania))
    check("plan.yml uruchamia control_plane_check.py --live",
          "tools/control_plane_check.py --live" in plan)
    # OBA TORY, NIE JEDEN. Ta bramka chroni przed jedyna awaria, ktorej `git revert` nie cofa — a stala
    # wylacznie na torze pull requesta, podczas gdy granice zmienia push na galaz domyslna (DEC-16).
    stosowanie = tekst_wykonywany("apply.yml")
    check("apply.yml uruchamia control_plane_check.py w OBU trybach (offline + --live)",
          "python3 tools/control_plane_check.py\n" in stosowanie
          and "tools/control_plane_check.py --live" in stosowanie)
    wyzwalacz = plan.split("jobs:", 1)[0]
    check("plan.yml ma `tools/**` w sciezkach wyzwalacza (guard widzi zmiane samego siebie)",
          '"tools/**"' in wyzwalacz, wyzwalacz)


# --------------------------------------------------------------------- kompletnosc rejestru decyzji
def test_kompletnosc_decyzji() -> None:
    """Bramka DEC-19: rozjazd ze starterem widziany na ZBIORZE DECYZJI, nie na wskazniku.

    Kazdy przypadek negatywny odpowiada realnemu trybowi awarii zmierzonemu na wdrozeniu 2026-08-12:
    wskaznik `.starter-sync` wskazywal aktualny `main` startera (bramka `starter-drift` zielona), a repo
    nie mialo dwoch calych decyzji — jednej cytowanej w DZIEWIECIU wlasnych plikach.
    """
    print("\n== kompletnosc rejestru decyzji (DEC-19) ==")
    decyzje = ROOT / "docs/0-decyzje.md"
    oryginal = decyzje.read_text()

    def uruchom(*extra):
        return sh([sys.executable, "tools/decisions_check.py", *extra], cwd=ROOT)

    # --- 1. stan wyjsciowy: rozpakowany starter jest spojny sam ze soba ---------------------------
    p = uruchom()
    check("decisions_check przechodzi na rozpakowanym starterze", p.returncode == 0, p.stdout + p.stderr)

    # --- 2. decyzja CYTOWANA, ktorej nie ma w rejestrze -> odrzucenie z lista miejsc ---------------
    # Zdejmujemy sam NAGLOWEK sekcji (tresc zostaje), bo dokladnie tak wyglada niekompletny sync:
    # numer znika z rejestru, a odsylacze w kodzie zostaja.
    # Kandydat musi byc cytowany z KODU (workflow/rego/tf), nie tylko z dokumentacji: caly sens bramki
    # to odsylacz z pliku wykonywalnego prowadzacy w pustke, wiec test na dokumentacji mierzylby latwiejszy
    # przypadek niz ten, dla ktorego bramka powstala.
    numer_cytowany = None
    for kandydat in re.findall(r"^## (DEC-[0-9]+)", oryginal, re.M):
        cytaty = [c for c in sh(["grep", "-rl", kandydat, "."], cwd=ROOT).stdout.split()
                  if "0-decyzje.md" not in c]
        if len(cytaty) >= 2 and any(c.endswith((".yml", ".rego", ".tf")) for c in cytaty):
            numer_cytowany = kandydat
            break
    check("premisa: w materiale startera jest decyzja cytowana z KODU, nie tylko z dokumentacji",
          numer_cytowany is not None)
    if numer_cytowany:
        decyzje.write_text(re.sub(rf"^## {numer_cytowany} ", "## (naglowek zdjety) ", oryginal, count=1, flags=re.M))
        p = uruchom()
        check(f"decyzja {numer_cytowany} cytowana w kodzie, a nieobecna w rejestrze, jest ODRZUCANA",
              p.returncode != 0 and numer_cytowany in p.stdout, p.stdout + p.stderr)
        # Komunikat ma prowadzic do naprawy, a nie tylko oznajmiac problem: bez listy miejsc autor
        # zmiany nie wie, co odsyla w pustke, i pierwszym odruchem jest usuniecie odsylacza.
        check("komunikat wymienia PLIKI, ktore odsylaja w pustke",
              ".yml:" in p.stdout or ".rego:" in p.stdout or ".tf:" in p.stdout, p.stdout)
        decyzje.write_text(oryginal)
        check("ANTY-TAUTOLOGIA: po przywroceniu naglowka ta sama komenda PRZECHODZI",
              uruchom().returncode == 0)

    # --- 3. `--wzgledem`: decyzja startera, ktorej NIKT nie cytuje ---------------------------------
    # To jest druga polowa i jedyna, ktora widzi ten przypadek: sprawdzenie wewnetrzne przepuszcza
    # decyzje bez ani jednego odsylacza, bo nie ma czego rozwiazac.
    #
    # PLIK WZORCA LEZY POZA ROOT — i to nie jest kosmetyka. Wewnatrz repozytorium jego wlasna tresc
    # zostalaby policzona jako ODSYLACZ do decyzji, ktorej w rejestrze nie ma, wiec fixture testu
    # falszowalby wynik sprawdzenia wewnetrznego. `starter-drift` z tego samego powodu zapisuje
    # pobrany plik do `/tmp`, a nie do drzewa roboczego.
    wzorzec = pathlib.Path(tempfile.mkdtemp(prefix="vpcsc-wzorzec-")) / "0-decyzje-startera.md"
    wzorzec.write_text(oryginal + "\n\n## DEC-999 — decyzja obecna wylacznie w starterze\n\ntresc\n")
    p = uruchom("--wzgledem", str(wzorzec))
    check("decyzja obecna w starterze i nieobecna tutaj jest ODRZUCANA przez --wzgledem",
          p.returncode != 0 and "DEC-999" in p.stdout, p.stdout + p.stderr)
    check("sprawdzenie WEWNETRZNE tego przypadku NIE widzi (dlatego sa dwa, nie jedno)",
          uruchom().returncode == 0)

    # --- 4. ANTY-TAUTOLOGIA: zbior pokrywajacy wzorzec przechodzi ----------------------------------
    wzorzec.write_text(oryginal)
    check("ANTY-TAUTOLOGIA: rejestr pokrywajacy wzorzec PRZECHODZI",
          uruchom("--wzgledem", str(wzorzec)).returncode == 0)

    # --- 5. FAIL-CLOSED na zepsutym wejsciu --------------------------------------------------------
    # Plik bez ani jednej sekcji to nie „zero roznic", tylko zepsute wejscie (404 zapisany do pliku,
    # pusta odpowiedz API, zla sciezka). Bramka, ktora tu milczy, milczy dokladnie wtedy, gdy przestala
    # dzialac — czyli powtarza blad, ktory sama zamyka.
    wzorzec.write_text("# plik bez ani jednej sekcji decyzji\n")
    p = uruchom("--wzgledem", str(wzorzec))
    check("pusty plik wzorca jest BLEDEM, nie zerem roznic (fail-closed)", p.returncode != 0,
          p.stdout + p.stderr)
    check("brakujacy plik wzorca jest BLEDEM", uruchom("--wzgledem", str(ROOT / "nie-ma.md")).returncode != 0)
    wzorzec.unlink()

    # --- 6. BRAMKA STOI TAM, GDZIE MA STAC ---------------------------------------------------------
    # Sprawdzenie wewnetrzne nalezy do MUTATORA (DEC-16), czyli do akcji wolanej przez oba tory —
    # przeniesione do samego `validate.yml` przestaloby dzialac na pushu prosto na galaz domyslna.
    akcja = (ROOT / ".github/actions/bramki-tresci/action.yml").read_text()
    check("decisions_check stoi w akcji `bramki-tresci` (oba tory: PR i apply)",
          "tools/decisions_check.py" in akcja, akcja[-400:])
    drift = (ROOT / ".github/workflows/starter-drift.yml").read_text()
    check("starter-drift wola decisions_check z --wzgledem", "--wzgledem" in drift)
    check("starter-drift pobiera rejestr decyzji ze startera",
          "contents/docs/0-decyzje.md" in drift, drift[:400])
    # Czerwien MUSI zalezec takze od tego sprawdzenia. Bramka, ktora tylko dopisuje do podsumowania,
    # jest notatka — a to jest ten sam blad, co zgloszenie, ktorego nikt nie przypisuje.
    krok_fail = [k for k in yaml.safe_load(drift)["jobs"]["starter-drift"]["steps"]
                 if k.get("name") == "fail when behind"]
    check("premisa: starter-drift ma krok konczacy przebieg na czerwono", len(krok_fail) == 1)
    if krok_fail:
        check("czerwien starter-drift zalezy TAKZE od brakujacych decyzji, nie tylko od wskaznika",
              "decyzje.outputs.brakujace" in str(krok_fail[0].get("if", "")), str(krok_fail[0].get("if")))


# --------------------------------------------------------------------- narzedzia
def test_tools() -> None:
    print("\n== narzedzia ==")
    decl = (ROOT / "declarations.json").read_text()

    p_json = sh([sys.executable, "tools/attribute_budget.py", "--input", "declarations.json", "--format", "json"], cwd=ROOT)
    check("attribute_budget.py liczy budzet", p_json.returncode == 0, p_json.stderr[-400:])
    if p_json.returncode == 0:
        doc = json.loads(p_json.stdout)
        check("budzet: swieze repo daleko od limitu", doc["worst_pct"] < 5, json.dumps(doc)[:300])

    # NEGATYW: sztucznie zaniżony limit musi przekroczyć próg i zwrócić kod błędu. Limit wyliczamy
    # Z ZMIERZONEGO zużycia, a nie ze stałej — stała była związana z rozmiarem przykładowego repo i przy
    # mniejszym zestawie deklaracji (jeden członek, jeden profil) nie przekraczała już progu, czyli negatyw
    # cicho przestawał testować cokolwiek. Limit = zużycie zaokrąglone w dół gwarantuje >= 100% niezależnie
    # od tego, jak duży jest fixture.
    zuzycie = json.loads(p_json.stdout)["dry_run"] if p_json.returncode == 0 else 0
    over = json.loads(decl)
    over["policy"]["attribute_budget"]["limit_per_config"] = max(1, zuzycie)
    (ROOT / "over-budget.json").write_text(json.dumps(over))
    p = sh([sys.executable, "tools/attribute_budget.py", "--input", "over-budget.json"], cwd=ROOT)
    check("attribute_budget.py PADA po przekroczeniu progu", p.returncode == 1, p.stdout[-300:])

    # --- guard budzetu liczy TO, CO LADUJE W KONFIGURACJI --------------------------------------------
    #
    # Zmierzone na zywym perimetrze: narzedzie raportowalo 5 atrybutow, a `spec` w API trzymal 20. Roznica to
    # reguly baseline (locals.tf: `ingress_rules_effective`), w guardzie wtedy nieliczone. Guard, ktory
    # zaniza, mowi „jest miejsce" dokladnie wtedy, gdy go brakuje.
    #
    # Ponizsze asercje sa WLASNOSCIOWE (usun skladnik -> liczba MUSI zmalec), a nie porownaniem ze stala:
    # stala trzeba by aktualizowac przy kazdej zmianie fixture'u, a wtedy test uczy aktualizowania stalej.
    def budzet(mutacja) -> int:
        d = json.loads(decl)
        mutacja(d)
        (ROOT / "budzet-wariant.json").write_text(json.dumps(d))
        r = sh([sys.executable, "tools/attribute_budget.py", "--input", "budzet-wariant.json",
                "--format", "json"], cwd=ROOT)
        return json.loads(r.stdout)["dry_run"] if r.returncode == 0 else -1

    def bez_baseline(d):
        d["policy"]["baseline_ingress"] = []

    # Baseline jest JEDNA regula na tytul celujaca w `*` (DEC-11), wiec drugi czlonek NIE DOKLADA do niego
    # ANI JEDNEGO atrybutu. Duplikujemy czlonka i mierzymy sam przyrost.
    def dwaj_czlonkowie(d):
        nazwa, czlonek = list(d["members"].items())[0]
        d["members"][nazwa + "-kopia"] = json.loads(json.dumps(czlonek))

    def bez_baseline_dwaj(d):
        bez_baseline(d)
        dwaj_czlonkowie(d)

    # `externalResources` (BigQuery Omni) API liczy do limitu wprost. Bez tego skladnika egress poza GCP
    # bylby jedyna regula, ktora nic nie kosztuje — a to najdrozsza regula w katalogu pod wzgledem ryzyka.
    def bez_zewnetrznych(d):
        for czlonek in d["members"].values():
            for wpis in czlonek.get("profiles", []):
                wpis.get("params", {}).pop("external_resources", None)

    pelny = budzet(lambda d: None)
    goly = budzet(bez_baseline)
    podwojony = budzet(dwaj_czlonkowie)
    goly_podwojony = budzet(bez_baseline_dwaj)
    bez_s3 = budzet(bez_zewnetrznych)
    regul_baseline = len(json.loads(decl)["policy"].get("baseline_ingress", []) or [])

    check("budzet: reguly baseline_ingress SA liczone (usuniecie ich obniza wynik)", goly < pelny,
          f"pelny={pelny} bez_baseline={goly}")

    # PREMISA obu asercji nizej. Bez niej „baseline nie mnozy sie przez czlonkow" jest trywialnie prawdziwe
    # dla zera regul baseline — czyli test przechodzilby najgłosniej wtedy, gdy baseline w ogole zniknal.
    check("budzet: material startera deklaruje reguly baseline (premisa asercji o kolapsie)",
          regul_baseline > 0, f"baseline_ingress ma {regul_baseline} regul")

    # KSZTALT PO DEC-11: drugi czlonek dokłada DOKLADNIE koszt swoich regul PROFILOWYCH — czyli tyle samo,
    # ile dokłada w konfiguracji bez baselinu. Baseline celuje w `*`, wiec jego koszt jest STALY. Ta rownosc
    # jest jednoczesnie testem defektu, ktory ta zmiana usuwa: dopoki baseline trzymal liste projektow,
    # przyrost byl wiekszy o jeden atrybut na regule, a kazdy taki przyrost byl REPLACE'em reguly (ForceNew).
    check("budzet: drugi czlonek NIE dokłada do baselinu ani jednego atrybutu (cel `*`, DEC-11)",
          podwojony - pelny == goly_podwojony - goly,
          f"przyrost z baselinem={podwojony - pelny} bez baselinu={goly_podwojony - goly} regul={regul_baseline}")

    # ANTY-TAUTOLOGIA / REGRESJA. Pierwotny ksztalt (regula baseline per czlonek) dawal DOKLADNIE `2 * pelny`:
    # kazdy skladnik podwajal sie razem z czlonkiem. Od kolapsu stala czesc baselinu (tozsamosci, zrodla,
    # usługi, metody) nie podwaja sie, wiec wynik MUSI byc ostro mniejszy. Cofniecie kolapsu w rendererze
    # albo w tym narzedziu zapala te asercje, a nie tylko zmienia liczbe w raporcie.
    check("budzet: baseline NIE mnozy sie przez liczbe czlonkow", podwojony < 2 * pelny,
          f"jeden={pelny} dwaj={podwojony} (stary ksztalt dalby {2 * pelny})")

    # ...i asercja rozlaczajaca oba ksztalty, ktorych ta zmiana dotyczy. `podwojony < 2 * pelny` bylo prawda
    # RUWNIEZ dla listy zasobow (rosla o 1 na regule, a nie o caly koszt reguly), wiec sama w sobie nie
    # odroznia „lista" od „gwiazdka". Ta odroznia: koszt baselinu ma byc IDENTYCZNY przy jednym i dwoch
    # czlonkach, a mierzymy go jako roznice miedzy konfiguracja z baselinem i bez niego.
    check("budzet: koszt baselinu jest STALY (ten sam przy jednym i przy dwoch czlonkach)",
          pelny - goly == podwojony - goly_podwojony,
          f"baseline przy jednym={pelny - goly} przy dwoch={podwojony - goly_podwojony}")

    check("budzet: zasoby zewnetrzne (s3://) sa liczone", bez_s3 < pelny,
          f"pelny={pelny} bez_zewnetrznych={bez_s3}")

    # Kontrakt musi podawac TE SAMA liczbe co guard — inaczej zespol planuje wobec innego budzetu niz ten,
    # na ktorym pada CI. Egzekwowane strukturalnie: obie strony czytaja `local.attribute_usage_*`.
    ct = (ROOT / "terraform/contract.tf").read_text()
    check("kontrakt nie ma WLASNEGO wyrazenia liczacego budzet (czyta local.attribute_usage_*)",
          "local.attribute_usage_dry_run" in ct and "local.attribute_usage_enforced" in ct
          and "merge(local.ingress_rules_all" not in ct,
          ct[ct.find("contract_budget"):ct.find("contract_budget") + 300])

    # render_member.py MUSI wymuszać dry-run niezależnie od tego, co przyszło w payloadzie.
    # Renderer dopisuje wpis do WSPÓLNEGO pliku (DEC-12), więc „co wyrenderował" to przyrost jego treści.
    plik_czlonkow = ROOT / "perimeter/projects.yaml"
    przed = plik_czlonkow.read_text()
    p = sh([sys.executable, "tools/render_member.py", "--division", "x", "--project-id", "prj-x-test",
            "--project-number", "123456789012", "--owner-group", "g@example.com",
            "--change-ref", "snow:RITM0000009", "--approved-by", "n@example.com",
            "--profiles-json", '[{"name":"vertex-online-serving","params":{}}]',
            "--today", "2026-07-28"], cwd=ROOT)
    rendered = plik_czlonkow.read_text()[len(przed):] if p.returncode == 0 else ""
    plik_czlonkow.write_text(przed)
    check("render_member.py wymusza stage: dry-run", p.returncode == 0 and "stage: dry-run" in rendered,
          p.stderr[-300:] + rendered[:200])
    check("render_member.py ustawia date przegladu", "review_by: '2027-01-24'" in rendered or "review_by: 2027-01-24" in rendered,
          rendered[:300])

    # Niezmiennik „nie nadpisuj istniejącego wpisu" ma pełny zestaw testów (w tym degradację `enforced`
    # → `dry-run` i wariant z literówką w dywizji) w `test_jeden_plik_projektow`. Tutaj zostaje asercja
    # o kształcie: renderer MUSI pytać o oba pola tożsamości projektu, nie o samą nazwę klucza — bo klucz
    # zmienia się przy literówce w dywizji, a projekt nie.
    rm = (ROOT / "tools/render_member.py").read_text()
    check("render_member.py pyta o project_id ORAZ project_number (nie o sam klucz wpisu)",
          "project_id=args.project_id" in rm and "project_number=str(args.project_number)" in rm,
          rm[rm.find("znajdz"):rm.find("znajdz") + 300])

    # snow_verify.py fail-closed: ticket w innym stanie albo na inny projekt = brak PR-a.
    # Fixture'y bierzemy z tests/ — tych samych, które cytuje docs/5-servicenow-intake.md. Generowanie ich
    # w kodzie testu dawało zieloną bramkę na danych, których czytelnik dokumentacji nie ma.
    p = sh([sys.executable, "tools/snow_verify.py", "--ticket", "RITM0000001",
            "--expect-project", "prj-x-test", "--offline-fixture", "tests/snow-approved.json"], cwd=ROOT)
    check("snow_verify.py przepuszcza zatwierdzony ticket (fixture z tests/)", p.returncode == 0,
          p.stdout + p.stderr)

    for fixture, opis in [("tests/snow-not-approved.json", "approval w toku"),
                          ("tests/snow-self-approved.json", "samo-zatwierdzenie"),
                          ("tests/snow-wrong-project.json", "podmiana projektu po approvalu")]:
        p = sh([sys.executable, "tools/snow_verify.py", "--ticket", "RITM0000001",
                "--expect-project", "prj-x-test", "--offline-fixture", fixture], cwd=ROOT)
        check(f"snow_verify.py ODRZUCA: {opis}", p.returncode != 0, p.stdout + p.stderr)

    fixture_bad = {"result": [{"approval": "requested", "assignment_group.name": "network-team",
                               "u_project_id": "prj-x-test"}]}
    (ROOT / "snow-pending.json").write_text(json.dumps(fixture_bad))
    p = sh([sys.executable, "tools/snow_verify.py", "--ticket", "RITM0000009",
            "--expect-project", "prj-x-test", "--offline-fixture", "snow-pending.json"], cwd=ROOT)
    check("snow_verify.py ODRZUCA ticket bez zatwierdzenia", p.returncode == 1, p.stdout + p.stderr)

    fixture_swap = {"result": [{"approval": "approved", "assignment_group.name": "network-team",
                                "u_project_id": "prj-inny"}]}
    (ROOT / "snow-swap.json").write_text(json.dumps(fixture_swap))
    p = sh([sys.executable, "tools/snow_verify.py", "--ticket", "RITM0000009",
            "--expect-project", "prj-x-test", "--offline-fixture", "snow-swap.json"], cwd=ROOT)
    check("snow_verify.py ODRZUCA podmiane projektu w payloadzie", p.returncode == 1, p.stdout + p.stderr)

    # violations_report.py: brak wpisu != zero naruszeń — raport MUSI wypisać 0 dla każdego członka.
    (ROOT / "raw-logs.json").write_text("[]")
    p = sh([sys.executable, "tools/violations_report.py", "--logs", "raw-logs.json",
            "--declarations", "declarations.json", "--json-out", "violations.json",
            "--markdown-out", "violations.md"], cwd=ROOT)
    viol = json.loads((ROOT / "violations.json").read_text()) if (ROOT / "violations.json").exists() else {}
    check("violations_report.py wypisuje wpis dla KAZDEGO czlonka", p.returncode == 0 and len(viol) == 1,
          p.stderr[-300:] + json.dumps(viol))

    # ---- PRZYPISANIE DO CZŁONKA na REALNYM kształcie wpisu ------------------------------------------
    # Powyższy test na pustym wejściu przechodził także wtedy, gdy funkcja przypisująca była całkowicie
    # zepsuta — bo dla `[]` każdy członek ma 0 niezależnie od tego, jak liczymy. Fixture pochodzi
    # z ANONIMIZOWANYCH wpisów zdjętych z żywej organizacji i zawiera cztery kształty, na których stara
    # wersja rozjeżdżała się inaczej: `resourceNames[0]` dawał nazwę regionu, `project_id` zamiast numeru,
    # numer OBCEGO projektu (egress) i `_` z aliasu `projects/_`. Członka było na żywo widać w 0 z 26 wpisów.
    (ROOT / "violations.json").unlink(missing_ok=True)
    p = sh([sys.executable, "tools/violations_report.py", "--logs", "tests/vpcsc-violation-dryrun.json",
            "--declarations", "declarations.json", "--json-out", "violations.json",
            "--markdown-out", "violations.md"], cwd=ROOT)
    viol = json.loads((ROOT / "violations.json").read_text()) if (ROOT / "violations.json").exists() else {}
    nazwa_czlonka = "example-division-prj-example-vertex-dev"
    check("violations_report.py PRZYPISUJE naruszenia do wlasciwego czlonka (3 z realnego ksztaltu)",
          p.returncode == 0 and viol.get(nazwa_czlonka) == 3,
          p.stdout + p.stderr[-400:] + json.dumps(viol))

    # NEGATYW do powyższego: czwarty wpis fixture'a dotyczy projektu SPOZA perimeter/members/. Nie wolno
    # go doliczyć członkowi — inaczej „naruszenia" rosłyby o cudzy ruch i blokowały promocję bez powodu.
    md = (ROOT / "violations.md").read_text()
    check("violations_report.py NIE doklada czlonkowi naruszen obcego projektu",
          viol.get(nazwa_czlonka) == 3 and "Naruszenia spoza listy" in md,
          json.dumps(viol) + md[-400:])

    # ---- FAIL-CLOSED: wpis, którego nie umiemy przypisać, NIE MOŻE dać zielonego raportu -------------
    # `violations.json` jest DOWODEM dla promotion_gate. Wpis bez rozpoznanego projektu policzony jako
    # „nie nasz" to dokładnie ten mechanizm, przez który raport meldował czyste okno przy 26 naruszeniach.
    nieznany = json.loads((ROOT / "tests/vpcsc-violation-dryrun.json").read_text())[:1]
    for klucz in ("ingressViolations", "egressViolations", "resourceNames"):
        nieznany[0]["protoPayload"]["metadata"].pop(klucz, None)
    nieznany[0]["resource"]["labels"].pop("project_id", None)
    (ROOT / "raw-nieznany.json").write_text(json.dumps(nieznany))
    (ROOT / "violations.json").unlink(missing_ok=True)
    p = sh([sys.executable, "tools/violations_report.py", "--logs", "raw-nieznany.json",
            "--declarations", "declarations.json", "--json-out", "violations.json",
            "--markdown-out", "violations.md"], cwd=ROOT)
    check("violations_report.py PADA na wpisie bez rozpoznanego projektu (brak dowodu != zero)",
          p.returncode != 0 and not (ROOT / "violations.json").exists(),
          f"rc={p.returncode} istnieje={(ROOT / 'violations.json').exists()} " + p.stderr[-300:])

    # Wejście, które nie jest listą wpisów (np. obiekt błędu zapisany do pliku), też ma padać z komunikatem,
    # a nie wywracać się tracebackiem gdzieś w środku pętli.
    (ROOT / "raw-nie-lista.json").write_text('{"error": "PERMISSION_DENIED"}')
    p = sh([sys.executable, "tools/violations_report.py", "--logs", "raw-nie-lista.json",
            "--declarations", "declarations.json", "--json-out", "violations.json",
            "--markdown-out", "violations.md"], cwd=ROOT)
    check("violations_report.py ODRZUCA wejscie, ktore nie jest lista wpisow",
          p.returncode != 0 and "Traceback" not in p.stderr, f"rc={p.returncode} " + p.stderr[-300:])

    # ---- ZAKRES ODCZYTU: jedno zapytanie do sinka zamiast N do projektow -----------------------------
    # Wpis audytowy VPC-SC laduje w logu PROJEKTU-wlasciciela zasobu, wiec `--organization=` widzi 0 przy
    # 41 w projekcie czlonka (zmierzone). Odczyt kazdego czlonka osobno usuwal te slepote, ale przy kilkuset
    # projektach to kilkaset wywolan na przebieg, a JEDEN projekt bez uprawnien wywracal caly dowod.
    # Wejsciem jest teraz sink org-level; ten test pilnuje OBU wlasnosci naraz: ze krok CZYTA z sinka i ze
    # NIE robi ani jednego zapytania per projekt.
    #
    # Atrapa `gcloud` rozroznia odczyt z kubelka (`--bucket=`) od odczytu projektowego i LOGUJE kazde
    # wywolanie — dzieki temu liczba zapytan jest mierzona, a nie zakladana.
    wf_raport = yaml.safe_load((ROOT / ".github/workflows/violations-report.yml").read_text())
    krok_logow = next((k for k, _ in kroki_workflow(wf_raport)
                       if "gcloud logging read" in str(k.get("run", ""))), None)
    check("violations-report.yml ma krok czytajacy logi audytowe", krok_logow is not None)
    if krok_logow is not None:
        wpis = json.loads((ROOT / "tests/vpcsc-violation-dryrun.json").read_text())[:1]
        (ROOT / "wpis-sinka.json").write_text(json.dumps(wpis))
        bin_logi = ROOT / "stub-bin-logi"
        bin_logi.mkdir(exist_ok=True)
        (bin_logi / "gcloud").write_text(
            "#!/usr/bin/env bash\n"
            "echo \"$*\" >> \"$PWD/gcloud-calls.log\"\n"
            "case \"$*\" in\n"
            "  *\"sinks describe\"*)\n"
            "    printf '%s\\n' \"${STUB_SINK_CFG:-protoPayload.metadata.\\\"@type\\\"=\\\"type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata\\\"	True}\" ;;\n"
            "  *\"logging read\"*)\n"
            "    case \"$*\" in\n"
            "      *--bucket=*) if [ -n \"$STUB_SINK_PUSTY\" ]; then echo '[]'; else cat \"$PWD/wpis-sinka.json\"; fi ;;\n"
            # Odczyt PROJEKTOWY oddaje wpis zawsze. Gdyby krok mimo wszystko pytal projekty, zobaczymy to
            # i w liczniku wywolan, i w tresci raw.json przy rozbrojonym sinku (kontrola nizej).
            "      *) cat \"$PWD/wpis-sinka.json\" ;;\n"
            "    esac ;;\n"
            "  *) echo '[]' ;;\n"
            "esac\n")
        (bin_logi / "gcloud").chmod(0o755)
        baza_env = dict(os.environ, PATH=f"{bin_logi}:{os.environ['PATH']}",
                        ORG_ID="123456789012", DAYS="14",
                        SINK_PROJECT="prj-example-adm", SINK_BUCKET="vpcsc-violations",
                        SINK_LOCATION="eu")

        def przebieg(**nadpisz):
            (ROOT / "raw.json").unlink(missing_ok=True)
            (ROOT / "gcloud-calls.log").unlink(missing_ok=True)
            p = subprocess.run(["bash", "-e", "-c", krok_logow["run"]], cwd=ROOT,
                               env=dict(baza_env, **nadpisz), capture_output=True, text=True)
            surowe = json.loads((ROOT / "raw.json").read_text()) if (ROOT / "raw.json").exists() else []
            wywolania = (ROOT / "gcloud-calls.log").read_text().splitlines() \
                if (ROOT / "gcloud-calls.log").exists() else []
            return p, surowe, [w for w in wywolania if "logging read" in w]

        p, surowe, odczyty = przebieg()
        check("violations-report.yml czyta naruszenia Z SINKA", p.returncode == 0 and len(surowe) == 1,
              f"rc={p.returncode} wpisow={len(surowe)} " + (p.stdout + p.stderr)[-400:])
        # KPI zadania: zero zapytan per projekt. Liczymy wywolania, a nie ufamy, ze petli nie ma.
        check("violations-report.yml robi DOKLADNIE JEDNO zapytanie o logi (zero per projekt)",
              len(odczyty) == 1 and all("--bucket=" in o for o in odczyty),
              f"odczytow={len(odczyty)}: {odczyty}")

        # ---- ANTY-TAUTOLOGIA: po rozbrojeniu sinka asercja MUSI paść ---------------------------------
        # Gdyby krok czytal cokolwiek poza sinkiem, ten przebieg nadal dalby niepuste `raw.json` — bo atrapa
        # oddaje wpis na KAZDYM odczycie projektowym. Pusty wynik jest wiec dowodem, ze zrodlem jest sink,
        # a nie tym, ze test nie ma jak sie nie udac.
        p, surowe, _ = przebieg(STUB_SINK_PUSTY="1")
        check("ANTY-TAUTOLOGIA: pusty sink daje pusty raport (dane nie pochodza skadinad)",
              p.returncode == 0 and len(surowe) == 0,
              f"rc={p.returncode} wpisow={len(surowe)} " + (p.stdout + p.stderr)[-300:])

        # ---- GUARD KONFIGURACJI SINKA: sink bez `includeChildren` widzi tylko logi ORGANIZACJI --------
        # Czyli 0 wpisow przy pelnym oknie naruszen — nieodroznialne od czystego okna, a to jest DOWOD dla
        # promotion_gate. Krok ma padac, zanim wystawi taki raport.
        p, _, _ = przebieg(STUB_SINK_CFG="protoPayload.metadata.\"@type\"=\"type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata\"\tFalse")
        check("violations-report.yml PADA, gdy sink nie ma includeChildren (widzialby tylko organizacje)",
              p.returncode != 0, f"rc={p.returncode} " + (p.stdout + p.stderr)[-300:])

        p, _, _ = przebieg(STUB_SINK_CFG="severity>=ERROR\tTrue")
        check("violations-report.yml PADA, gdy sink ma inny filtr niz odczyt",
              p.returncode != 0, f"rc={p.returncode} " + (p.stdout + p.stderr)[-300:])


# --------------------------------------------------- eksperyment wyscigu (klasyfikacja wynikow)
# Atrapy `terraform` i `gcloud` pozwalaja wysterowac KAZDA z czterech kategorii werdyktu bez chmury.
# To nie jest test dla ozdoby: bledna klasyfikacja jednego przypadku ("apply padl" policzone jako "regula
# zniknela") sprawila, ze eksperyment przez tydzien produkowal wniosek odwrotny do prawdy — i ten wniosek
# poszedl do uzasadnienia decyzji architektonicznej (DEC-6, #1904).
TERRAFORM_ATRAPA = """#!/usr/bin/env bash
case "$*" in
  *" apply "*)
    case "$*" in
      *state-a*) rc="${STUB_RC_A:-0}" ;;
      *)         rc="${STUB_RC_B:-0}" ;;
    esac
    [ "$rc" != "0" ] && echo "${STUB_ERR:-blad}"
    exit "$rc" ;;
esac
exit 0
"""

GCLOUD_PERIMETR_ATRAPA = """#!/usr/bin/env bash
python3 -c "
import json
n = int('${STUB_RULES:-2}')
print(json.dumps({'spec': {'ingressPolicies': [{'title': 'race-test-%d' % i} for i in range(n)]}}))
"
"""


def test_eksperyment_wyscigu() -> None:
    print("\n== eksperyment wyscigu ==")
    exp = STARTER / "experiments/race-two-states"
    bin_dir = ROOT / "stub-bin-exp"
    bin_dir.mkdir(exist_ok=True)
    for nazwa, tresc in (("terraform", TERRAFORM_ATRAPA), ("gcloud", GCLOUD_PERIMETR_ATRAPA)):
        (bin_dir / nazwa).write_text(tresc)
        (bin_dir / nazwa).chmod(0o755)

    baza = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
                TF_VAR_policy_id="123456789012", TF_VAR_perimeter_name="test_race",
                IDENTITY_A="serviceAccount:sa-example-a@prj-example.iam.gserviceaccount.com",
                IDENTITY_B="serviceAccount:sa-example-b@prj-example.iam.gserviceaccount.com")

    def przebieg(**nadpisania):
        return sh(["bash", str(exp / "run.sh"), "1"], cwd=str(exp), env=dict(baza, **nadpisania))

    # 1. Oba apply OK, obie reguly — przebieg po prostu nie trafil w okno wyscigu.
    p = przebieg(STUB_RC_A="0", STUB_RC_B="0", STUB_RULES="2")
    check("wyscig: oba OK + 2 reguly = bez nalozenia (rc 0)",
          p.returncode == 0 and "bez nałożenia w czasie" in p.stdout, p.stdout[-500:] + p.stderr[-300:])

    # 2. JEDYNY przypadek potwierdzajacy teze o cichym nadpisaniu — i jedyny konczacy sie bledem.
    p = przebieg(STUB_RC_A="0", STUB_RC_B="0", STUB_RULES="1")
    check("wyscig: oba OK + 1 regula = CICHA UTRATA (rc != 0)",
          p.returncode != 0 and "CICHA UTRATA" in p.stdout, p.stdout[-500:] + p.stderr[-300:])

    # 3. Realne zachowanie ACM: przegrany pada na eTagu. Nic nie ginie, wiec NIE jest to utrata.
    p = przebieg(STUB_RC_A="0", STUB_RC_B="1", STUB_RULES="1",
                 STUB_ERR="Error 400: The eTag provided 'abc' does not match the eTag 'def'")
    check("wyscig: blad eTag = konflikt GLOSNY, nie utrata (rc 0)",
          p.returncode == 0 and "konflikt GŁOŚNY" in p.stdout and "CICHA UTRATA" not in p.stdout,
          p.stdout[-500:] + p.stderr[-300:])

    # 4. REGRESJA, ktora zepsula pierwotny eksperyment: apply padl z powodu NIEZWIAZANEGO ze wspolbieznoscia
    #    (tam — nieistniejaca tozsamosc). Stara logika liczyla to jako utrate reguly i potwierdzala teze.
    p = przebieg(STUB_RC_A="0", STUB_RC_B="1", STUB_RULES="1",
                 STUB_ERR="Error 403: Permission 'accesscontextmanager.policies.update' denied")
    check("wyscig: inny blad = NIEROZSTRZYGNIETE, nie utrata reguly",
          "NIEROZSTRZYGNIĘTE" in p.stdout and "CICHA UTRATA" not in p.stdout,
          p.stdout[-500:] + p.stderr[-300:])

    # 5. Tozsamosci sa PARAMETREM i sa obowiazkowe — brak = twarde zatrzymanie przed dotknieciem czegokolwiek.
    bez_tozsamosci = {k: v for k, v in baza.items() if k != "IDENTITY_A"}
    p = sh(["bash", str(exp / "run.sh"), "1"], cwd=str(exp), env=bez_tozsamosci)
    check("wyscig: brak IDENTITY_A zatrzymuje eksperyment",
          p.returncode != 0 and "IDENTITY_A" in p.stderr + p.stdout, p.stdout[-300:] + p.stderr[-300:])


# --------------------------------------------------------------------- pre-flight
# Atrapa `gcloud`: domyslnie udaje ZDROWY projekt Z SIECIA (istnieje, numer sie zgadza, PGA i DNS w
# porzadku). STUB_FAIL wymusza blad KONKRETNEGO wywolania — bez tego nie da sie sprawdzic wlasnosci,
# ktora jest tu najwazniejsza: ze pre-flight NIE ORZEKA o rzeczy, ktorej nie odczytal. Poprzednia atrapa
# konczyla kazde nieobsluzone wywolanie `exit 0` z pustym stdout, wiec „nie udalo sie zapytac" i
# „zapytalem, nic nie ma" byly w tescie tym samym stanem — dokladnie tym zlepkiem, ktory na zywym
# projekcie kazal skryptowi napisac „OK, Private Google Access wlaczony" o projekcie BEZ SIECI.
GCLOUD_ATRAPA = """#!/usr/bin/env bash
awaria() { echo "$1" >&2; exit 1; }

# Skrypt jest wylacznie do odczytu (DEC-5), wiec nie ma prawa dopuscic do pytania „czy wlaczyc API?".
# Zywy gcloud zadaje je na stderr, ktory pre-flight przechwytuje — na terminalu skrypt stalby w miejscu
# bez widocznego powodu, a „y" wlaczyloby usluge w CUDZYM projekcie. Atrapa egzekwuje to zachowaniem.
[ "${CLOUDSDK_CORE_DISABLE_PROMPTS:-}" = "1" ] || awaria "ATRAPA: pre-flight nie wylaczyl pytan gcloud"

case "$*" in
  # DWA POLA, nie jedno: `projects describe` odpowiada numerem ORAZ stanem cyklu zycia, a to drugie jest
  # jedynym sygnalem odrozniajacym projekt zywy od skasowanego (soft-delete trzyma projekt odczytywalnym
  # przez 30 dni). Atrapa oddajaca sam numer nie umialaby wyrazic tej roznicy, wiec test na nia nie mialby
  # jak powstac. STUB_PROJECT_FAIL udaje odmowe/nieistnienie — na to Resource Manager odpowiada TAK SAMO.
  "projects describe "*)
    [ "${STUB_PROJECT_FAIL:-}" = "1" ] && awaria \\
      "ERROR: (gcloud.projects.describe) User [x@example.com] does not have permission to access projects instance [prj-example:get] (or it may not exist)."
    printf '%s\\t%s\\n' "123456789012" "${STUB_LIFECYCLE-ACTIVE}" ;;
  # `beta billing projects describe` NIE wpada w galaz `projects describe ` wyzej: tamten wzorzec jest
  # zakotwiczony na poczatku `$*`, a tu `$*` zaczyna sie od `beta billing`. Trzy wartosci zamiast dwoch,
  # bo check ma trzy wyjscia: True (jest), False (nie ma) i PUSTE (nie odczytalem) — a to ostatnie musi
  # dac inny komunikat niz „nie ma", inaczej brak jednej roli u recenzenta wyglada jak wada cudzego projektu.
  *"billing projects describe "*)
    [ "${STUB_FAIL:-}" = "billing" ] && awaria \\
      "ERROR: (gcloud.beta.billing.projects.describe) PERMISSION_DENIED: caller lacks billing.resourceAssociations.list"
    printf '%s\\n' "${STUB_BILLING-True}" ;;
  *"service-accounts describe "*)
    for arg in "$@"; do case " $STUB_SA_OK " in *" $arg "*) exit 0 ;; esac; done
    exit 1 ;;
  *"perimeters list"*)
    [ "${STUB_FAIL:-}" = "perimeters" ] && awaria "ERROR: PERMISSION_DENIED: brak dostepu do polityki"
    printf '%b\\n' "${STUB_PERIMETERS-}" ;;
  *"subnets list"*)
    [ "${STUB_FAIL:-}" = "subnets" ] && awaria "ERROR: INTERNAL: backend error"
    printf '%b\\n' "${STUB_SUBNETS-subnet-a\\tTrue}" ;;
  *"networks list"*)
    [ "${STUB_FAIL:-}" = "compute-off" ] && awaria \\
      "ERROR: PERMISSION_DENIED: Compute Engine API has not been used in project prj-example before or it is disabled."
    [ "${STUB_FAIL:-}" = "compute-other" ] && awaria "ERROR: PERMISSION_DENIED: caller lacks compute.networks.list"
    printf '%b\\n' "${STUB_NETWORKS-vpc-example}" ;;
  *"managed-zones list"*)
    [ "${STUB_FAIL:-}" = "dns" ] && awaria "ERROR: INTERNAL: backend error"
    printf '%b\\n' "${STUB_ZONES-googleapis.com.\\nnotebooks.googleusercontent.com.}" ;;
  *) : ;;
esac
exit 0
"""


def test_preflight() -> None:
    print("\n== pre-flight ==")
    bin_dir = ROOT / "stub-bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "gcloud").write_text(GCLOUD_ATRAPA)
    (bin_dir / "gcloud").chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
               STUB_SA_OK="sa-example@prj-example.iam.gserviceaccount.com")
    baza = ["bash", "tools/preflight_check.sh", "--project", "prj-example", "--number", "123456789012"]

    p = sh(baza, cwd=ROOT, env=env)
    check("preflight: zdrowy projekt bez tozsamosci przechodzi", p.returncode == 0, p.stdout + p.stderr)

    # ---------------------------------------------- projekt SKASOWANY (soft-delete) NIE jest kandydatem
    # DLACZEGO TO JEST OSOBNA KLASA, A NIE ODMIANA „projektu nie ma". Kasowanie projektu w GCP to
    # soft-delete z oknem 30 dni: przez te 30 dni `projects describe` odpowiada NORMALNIE, zwraca numer
    # i konczy sie kodem 0 — rozni sie WYLACZNIE polem `lifecycleState`. Check pytajacy o sam numer
    # oglaszal wiec „projekt istnieje, numer zgodny" o projekcie w drodze do kasowania. Cicho pozytywny
    # werdykt pre-flightu jest gorszy od jego braku, bo wpis wchodzi do perimetru z blogoslawienstwem
    # kontroli, a numer zostaje w konfiguracji jako martwy, gdy projekt zniknie.
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_LIFECYCLE="DELETE_REQUESTED"))
    check("preflight: projekt DELETE_REQUESTED wywraca pre-flight (soft-delete to nie 'istnieje')",
          p.returncode != 0 and "DELETE_REQUESTED" in p.stdout and "SKASOWANY" in p.stdout,
          p.stdout + p.stderr)

    # ANTY-TAUTOLOGIA — bez tego asercja wyzej nie dowodzi niczego o TYM checku.
    # Rozbrajamy DOKLADNIE jedna linie werdyktu (podmiana calego lancucha, nie wyrazenie regularne:
    # gdy linia sie zmieni, podmiana nie zajdzie i test padnie glosno zamiast po cichu zzielieniec)
    # i puszczamy TEN SAM przypadek. Rozbrojony skrypt ma przejsc — czyli czerwien wyzej pochodzi
    # z tej linii, a nie z jakiegokolwiek innego checku, ktory przy okazji zapalil sie na atrapie.
    zrodlo = (ROOT / "tools/preflight_check.sh").read_text()
    linia_werdyktu = [w for w in zrodlo.splitlines() if 'problem "projekt $PROJECT_ID jest w stanie' in w]
    check("preflight: linia werdyktu o stanie projektu istnieje (kotwica anty-tautologii)",
          len(linia_werdyktu) == 1, str(linia_werdyktu))
    if len(linia_werdyktu) == 1:
        rozbrojony = ROOT / "tools/preflight_rozbrojony.sh"
        rozbrojony.write_text(zrodlo.replace(linia_werdyktu[0], '    ok "ROZBROJONE — bez sprawdzenia stanu"'))
        p = sh(["bash", "tools/preflight_rozbrojony.sh", "--project", "prj-example", "--number", "123456789012"],
               cwd=ROOT, env=dict(env, STUB_LIFECYCLE="DELETE_REQUESTED"))
        check("preflight: po ROZBROJENIU ten sam skasowany projekt PRZECHODZI (asercja nie jest pusta)",
              p.returncode == 0 and "ROZBROJONE" in p.stdout, p.stdout + p.stderr)
        rozbrojony.unlink()

    # Pole nieodczytane NIE JEST stanem ACTIVE. Bez tej galezi zmiana w `--format` albo w API cofnelaby
    # caly check do stanu sprzed poprawki — i zrobilaby to zielonym przebiegiem.
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_LIFECYCLE=""))
    check("preflight: PUSTY lifecycleState = BLAD 'nie odczytalem', nie ciche OK",
          p.returncode != 0 and "nie odczytałem lifecycleState" in p.stdout, p.stdout + p.stderr)

    # Nieudany odczyt projektu ma NIE wybierac jednej z dwoch mozliwosci i podawac jej jako faktu.
    # Resource Manager odpowiada tym samym komunikatem na „nie ma projektu" i „nie masz dostepu"
    # (`... does not have permission ... (or it may not exist)`), wiec pre-flight ma zacytowac odpowiedz,
    # a nie ja zinterpretowac — te dwie sytuacje naprawiaja dwie rozne osoby.
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_PROJECT_FAIL="1"))
    check("preflight: nieudany odczyt projektu cytuje odpowiedz API i nazywa obie mozliwosci",
          p.returncode != 0 and "NIE ISTNIEJE albo brak dostępu" in p.stdout
          and "or it may not exist" in p.stdout, p.stdout + p.stderr)

    # ------------------------------------------------------------------ konto rozliczeniowe (check 1b)
    # ZMIERZONE NA ZYWEJ ORGANIZACJI: przed tym checkiem projekt BEZ konta rozliczeniowego dostawal wyjscie
    # BAJT W BAJT takie samo jak projekt, ktory je ma — z linia `pre-flight zaliczony` wlacznie. Pre-flight
    # o billingu po prostu MILCZAL, wiec recenzent nie mial z czego sie dowiedziec, ze pytanie nie padlo.
    #
    # SEVERITY JEST TU CZESCIA ASERCJI, NIE SZCZEGOLEM. Sprawdzamy JEDNOCZESNIE, ze ostrzezenie pada
    # I ze kod wyjscia zostaje ZEROWY. Hipoteze „brak billingu = wywolania API sie odbijaja" zmierzono
    # i obalono (odczyt przechodzi; `services enable` na chronionej usludze konczy sie sukcesem), wiec
    # twardy BLAD zatrzymywalby kandydata POPRAWNEGO. Ta asercja istnieje po to, zeby ktos „poprawiajacy
    # przeoczenie" na `problem` wywrocil test, zamiast po cichu zamienic ostrzezenie w blokade.
    p = sh(baza, cwd=ROOT, env=env)
    check("preflight: konto rozliczeniowe PODPIETE = OK", p.returncode == 0
          and "konto rozliczeniowe podpięte" in p.stdout, p.stdout + p.stderr)

    p_bez = sh(baza, cwd=ROOT, env=dict(env, STUB_BILLING="False"))
    check("preflight: BRAK konta rozliczeniowego = UWAGA, ale pre-flight NIE JEST blokowany",
          p_bez.returncode == 0 and "UWAGA" in p_bez.stdout
          and "NIE MA konta rozliczeniowego" in p_bez.stdout, p_bez.stdout + p_bez.stderr)

    # ANTY-TAUTOLOGIA CZESC 1 — check musi CZYTAC wartosc, a nie wypisywac stalej. Gdyby byl no-opem,
    # oba przebiegi dalyby identyczne wyjscie i asercja wyzej zzielieniala by na samej obecnosci slowa.
    check("preflight: wyjscie dla projektu Z billingiem ROZNI SIE od wyjscia BEZ (check nie jest no-opem)",
          p.stdout != p_bez.stdout, p.stdout + "\n---\n" + p_bez.stdout)

    # Nieodczytany billing to NIE jest „billingu nie ma". Odczyt wymaga uprawnienia z domeny billingu,
    # ktorego read-only zestaw recenzenta swiadomie nie zawiera — wiec brak roli ma byc widoczny jako
    # osobny stan, a nie jako ostrzezenie o CUDZYM projekcie, ktorego nikt nie umie potem naprawic.
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_FAIL="billing"))
    check("preflight: NIEODCZYTANY billing cytuje odpowiedz i nie udaje 'brak billingu'",
          p.returncode == 0 and "nie zweryfikowano konta rozliczeniowego" in p.stdout
          and "billing.resourceAssociations.list" in p.stdout, p.stdout + p.stderr)

    p = sh(baza, cwd=ROOT, env=dict(env, STUB_BILLING=""))
    check("preflight: PUSTE billingEnabled = 'nie odczytalem', nie ciche OK ani 'nie ma'",
          p.returncode == 0 and "nie odczytałem pola billingEnabled" in p.stdout, p.stdout + p.stderr)

    # ANTY-TAUTOLOGIA CZESC 2 — rozbroj DOKLADNIE linie werdyktu i powtorz TEN SAM przypadek.
    # Podmiana calego lancucha, nie wyrazenie regularne: gdy linia sie zmieni, podmiana nie zajdzie
    # i test padnie glosno, zamiast po cichu zzielieniec na nieaktualnej kotwicy.
    zrodlo_b = (ROOT / "tools/preflight_check.sh").read_text()
    linia_bill = [w for w in zrodlo_b.splitlines() if 'uwaga "projekt NIE MA konta rozliczeniowego' in w]
    check("preflight: linia werdyktu o billingu istnieje (kotwica anty-tautologii)",
          len(linia_bill) == 1, str(linia_bill))
    if len(linia_bill) == 1:
        rozbrojony = ROOT / "tools/preflight_rozbrojony.sh"
        rozbrojony.write_text(zrodlo_b.replace(linia_bill[0], '  ok "ROZBROJONE — bez sprawdzenia billingu"'))
        p = sh(["bash", "tools/preflight_rozbrojony.sh", "--project", "prj-example", "--number", "123456789012"],
               cwd=ROOT, env=dict(env, STUB_BILLING="False"))
        check("preflight: po ROZBROJENIU projekt BEZ billingu nie dostaje ani slowa (asercja nie jest pusta)",
              p.returncode == 0 and "NIE MA konta rozliczeniowego" not in p.stdout
              and "ROZBROJONE" in p.stdout, p.stdout + p.stderr)
        rozbrojony.unlink()

    p = sh(baza + ["--identity", "serviceAccount:sa-example@prj-example.iam.gserviceaccount.com"], cwd=ROOT, env=env)
    check("preflight: ISTNIEJACE konto serwisowe przechodzi", p.returncode == 0, p.stdout + p.stderr)

    # NEGATYW — to jest ten defekt: adres poprawny skladniowo, konta nie ma. Bramka OPA na ksztalcie tego
    # nie zlapie, a ACM odrzuca CALA zmiane dopiero przy apply (`invalid or non-existent`, #1904).
    p = sh(baza + ["--identity", "serviceAccount:literowka@prj-example.iam.gserviceaccount.com"], cwd=ROOT, env=env)
    check("preflight: NIEISTNIEJACE konto serwisowe wywraca pre-flight",
          p.returncode != 0 and "NIE ISTNIEJE" in p.stdout, p.stdout + p.stderr)

    p = sh(baza + ["--identity", "sa-example@prj-example.iam.gserviceaccount.com"], cwd=ROOT, env=env)
    check("preflight: tozsamosc bez prefiksu typu ODRZUCONA",
          p.returncode != 0 and "prefiksu" in p.stdout, p.stdout + p.stderr)

    # user:/group: NIE moga byc raportowane jako sprawdzone — istnienia nie da sie potwierdzic z GCP.
    p = sh(baza + ["--identity", "user:example.person@example.com"], cwd=ROOT, env=env)
    check("preflight: user:/group: jawnie NIEZWERYFIKOWANE, nie 'OK'",
          p.returncode == 0 and "Workspace Directory API" in p.stdout and "UWAGA" in p.stdout,
          p.stdout + p.stderr)

    # ------------------------------------------------------------------ nie orzekaj o tym, czego nie odczytales
    # Wszystkie ponizsze przypadki nalezaly wczesniej do JEDNEJ klasy defektu: nieudane wywolanie gcloud bylo
    # wyciszane (`2>/dev/null`), a pusty stdout interpretowany jako odpowiedz. Zmierzone na zywym projekcie:
    # projekt BEZ SIECI dostawal „OK Private Google Access wlaczony na wszystkich podsieciach" (check padl
    # otwarty) i rownoczesnie „BLAD brak prywatnej strefy DNS" (check padl zamkniety) — dwa przeciwne werdykty
    # o tym samym, nieodczytanym stanie.

    # Kontrola pozytywna sily checku 3: podsiec BEZ PGA nadal ma wywracac pre-flight. Bez tej asercji
    # „nie mow OK, gdy nie wiesz" dalby sie spelnic przez zwykle wylaczenie checku.
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_SUBNETS="subnet-b\tFalse"))
    check("preflight: podsiec BEZ Private Google Access wywraca pre-flight",
          p.returncode != 0 and "subnet-b" in p.stdout, p.stdout + p.stderr)

    # Projekt bez sieci NIE JEST zlym kandydatem — VPC-SC dziala na plaszczyznie API. PGA i DNS maja byc
    # oznaczone jako niedotyczace, a nie zmyslone w ktoralkolwiek strone.
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_FAIL="compute-off"))
    check("preflight: projekt BEZ SIECI — PGA i DNS jako N/D, ani OK, ani BLAD",
          p.returncode == 0 and p.stdout.count("N/D") >= 2
          and "Private Google Access włączony" not in p.stdout
          and "brak prywatnej strefy DNS" not in p.stdout, p.stdout + p.stderr)

    # A tu roznica, ktorej stara wersja nie widziala wcale: „API wylaczone" to ODPOWIEDZ (sieci nie ma),
    # a kazdy inny blad to BRAK odpowiedzi. Ten sam kod PERMISSION_DENIED, dwa rozne wnioski — rozstrzyga
    # TRESC komunikatu, nigdy kod bledu.
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_FAIL="compute-other"))
    check("preflight: siec NIEODCZYTANA (inny blad) = BLAD 'nie zweryfikowano', nie N/D",
          p.returncode != 0 and "nie zweryfikowano" in p.stdout and "N/D" not in p.stdout,
          p.stdout + p.stderr)

    p = sh(baza, cwd=ROOT, env=dict(env, STUB_FAIL="perimeters"))
    check("preflight: nieodczytana lista perimetrow NIE jest raportowana jako 'brak kolizji'",
          p.returncode != 0 and "nie zweryfikowano kolizji" in p.stdout
          and "brak kolizji" not in p.stdout, p.stdout + p.stderr)

    # Konfiguracja EGZEKWOWANA blokuje onboarding (twarde ograniczenie ACM), DRY-RUN jest normalnym etapem
    # dwustopniowego wejscia. Stara wersja szukala numeru grepem w surowym JSON-ie calej listy, wiec mowila
    # to samo zdanie o obu — a przy promocji wlasnego czlonka byl to alarm o wlasnym perimetrze.
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_PERIMETERS="per-inny\tprojects/123456789012\t"))
    check("preflight: projekt w EGZEKWOWANEJ konfiguracji = BLAD, z nazwa perimetru",
          p.returncode != 0 and "EGZEKWOWANEJ" in p.stdout and "per-inny" in p.stdout,
          p.stdout + p.stderr)

    p = sh(baza, cwd=ROOT, env=dict(env, STUB_PERIMETERS="per-nasz\t\tprojects/123456789012"))
    check("preflight: projekt w DRY-RUN = UWAGA 'etap onboardingu', nie blokada",
          p.returncode == 0 and "DRY-RUN" in p.stdout and "per-nasz" in p.stdout
          and "EGZEKWOWANEJ" not in p.stdout, p.stdout + p.stderr)

    # WIELE ZASOBOW W KONFIGURACJI — przypadek, ktorego atrapa wczesniej nie umiala wyrazic, bo kazdy
    # przypadek testowy mial DOKLADNIE JEDEN zasob. Na jednym zasobie porownanie trafialo niezaleznie od
    # tego, czym pole jest rozcinane, wiec test zielenial na jedynym ukladzie, ktory dzialal. ZMIERZONE na
    # zywej organizacji (perimetr z trzema czlonkami): projekt BEDACY w konfiguracji dry-run dostawal
    # „brak kolizji — projektu nie ma w zadnej konfiguracji", bo `list()` skleja PRZECINKIEM, a awk
    # rozcinal po SREDNIKU. Grozniejsza polowa dotyczy konfiguracji EGZEKWOWANEJ: to jest caly powod
    # istnienia tego checku, a przy kazdym realnym rozmiarze perimetru byl cichym no-opem.
    wiele = "per-inny\tprojects/111111111111;projects/123456789012;projects/222222222222\t"
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_PERIMETERS=wiele))
    check("preflight: kolizja wykryta takze gdy konfiguracja ma WIELE zasobow (nie tylko jeden)",
          p.returncode != 0 and "EGZEKWOWANEJ" in p.stdout and "per-inny" in p.stdout,
          p.stdout + p.stderr)

    # ANTY-TAUTOLOGIA do asercji wyzej: ten sam uklad WIELU zasobow, ale bez naszego numeru, ma dawac
    # „brak kolizji". Bez tego „wykrywa kolizje" spelnialby sie takze przez check, ktory krzyczy zawsze.
    bez_nas = "per-inny\tprojects/111111111111;projects/222222222222\t"
    p = sh(baza, cwd=ROOT, env=dict(env, STUB_PERIMETERS=bez_nas))
    check("preflight: WIELE zasobow BEZ naszego numeru = brak kolizji (check nie krzyczy zawsze)",
          p.returncode == 0 and "brak kolizji" in p.stdout, p.stdout + p.stderr)

    # Separator w `--format` i separator w awk to JEDEN kontrakt rozpisany na dwie linie. Gdy ktos zmieni
    # jedna z nich, check cicho przestaje dopasowywac cokolwiek — dlatego pilnujemy obu naraz.
    zrodlo_pf = (ROOT / "tools/preflight_check.sh").read_text()
    check("preflight: format listy perimetrow ma JAWNY separator zgodny z awk",
          'separator=";"' in zrodlo_pf and 'split(pole, a, ";")' in zrodlo_pf,
          "brak jawnego separatora albo rozjazd z awk")

    # `--warn-only` ma zmieniac KOD WYJSCIA, nie werdykt. Stara wersja konczyla slowem „zaliczony" mimo
    # bledow — czyli linia, ktora czyta sie w logu CI, twierdzila dokladnie odwrotnie niz tresc raportu.
    p = sh(["bash", "tools/preflight_check.sh", "--project", "prj-example", "--number", "999999999999",
            "--warn-only"], cwd=ROOT, env=env)
    check("preflight: --warn-only NIE oglasza 'pre-flight zaliczony'",
          p.returncode == 0 and "NIEZALICZONY" in p.stdout + p.stderr
          and "pre-flight zaliczony" not in p.stdout + p.stderr, p.stdout + p.stderr)

    # Blad uzycia ma byc odrozniany od niezaliczonego checku — wczesniej `shift` na pustej liscie konczyl
    # skrypt cichym kodem 1, bez jednego slowa.
    p = sh(["bash", "tools/preflight_check.sh", "--number", "123456789012", "--project"], cwd=ROOT, env=env)
    check("preflight: flaga bez wartosci konczy sie komunikatem, nie cichym 1",
          p.returncode != 0 and "wymaga wartości" in p.stdout + p.stderr, p.stdout + p.stderr)


# --------------------------------------------------------------------- workflows
def test_workflows() -> None:
    print("\n== workflows ==")
    wf = sorted((ROOT / ".github/workflows").glob("*.yml"))
    check("czternascie workflow po rozpakowaniu", len(wf) == 14, str([f.name for f in wf]))

    if have("actionlint"):
        p = sh(["actionlint", *[str(f) for f in wf]])
        check("actionlint (skladnia + shellcheck w run:)", p.returncode == 0, p.stdout[-1500:])
    else:
        check("actionlint dostepny", False, "brak actionlint na PATH — pomijam")

    apply_yml = (ROOT / ".github/workflows/apply.yml").read_text()
    # Trzy własności apply, których utrata jest cicha i kosztowna.
    check("apply: single-flight concurrency (bez cancel-in-progress)",
          "group: vpc-sc-apply" in apply_yml and "cancel-in-progress: false" in apply_yml)
    # NAZWA TEJ ASERCJI JEST WAŻNA. Brzmiała kiedyś „environment z reviewerami" i to było kłamstwo tej samej
    # klasy, przed jaką broni reszta pliku: sprawdzamy obecność JEDNEJ LINIJKI w workflow, a nie istnienie
    # bramki ludzkiej — ta jest ustawieniem repozytorium, płatnym, poza zasięgiem selftestu. Zielona asercja
    # o nazwie „z reviewerami" czytałaby się jako dowód na coś, czego ten test nie potrafi zobaczyć.
    check("apply: job deklaruje environment perimeter-apply", "environment: perimeter-apply" in apply_yml)
    check("apply: bramki OPA uruchamiane PONOWNIE przed apply",
          "conftest test" in apply_yml and apply_yml.index("conftest test") < apply_yml.index("terraform -chdir=terraform apply"))

    intake = (ROOT / ".github/workflows/intake.yml").read_text()
    check("intake: ticket weryfikowany przez API, nie z payloadu", "snow_verify.py" in intake)

    # Raport naruszeń czyta audit-log KAŻDEGO projektu członkowskiego, a `logging.googleapis.com` jest usługą
    # chronioną — więc tożsamość, którą robi to raport, MUSI mieć regułę ingress w baseline. Inaczej system
    # zjada własny dowód: w dry-run raport dopisuje członkowi naruszenie od siebie samego (a promotion_gate
    # wymaga zera), a po pierwszej promocji ten odczyt jest odmawiany i dowodu nie ma już dla nikogo.
    #
    # Warunek czytamy Z PLIKÓW, nie z listy wpisanej w test: konto bierzemy z `service_account:` w workflow,
    # usługę z komendy, której on używa. Przepisanie ich tutaj zamieniłoby tę asercję w kopię konfiguracji —
    # zmiana raportu na inne konto przestałaby być wykrywalna, a to jest dokładnie ten rozjazd, który boli.
    raport = (ROOT / ".github/workflows/violations-report.yml").read_text()
    polityka = (ROOT / "perimeter/policy.yaml").read_text()
    czyta_logi_czlonka = "gcloud logging read" in raport and "--project=$pid" in raport
    konto_raportu = re.search(r"service_account:\s*\$\{\{\s*vars\.(\w+)\s*\}\}", raport)
    konto_planu = konto_raportu is not None and konto_raportu.group(1) == "PLAN_SERVICE_ACCOUNT"
    baseline = yaml.safe_load(polityka).get("baseline_ingress", [])
    pokryte = any(
        any("sa-vpcsc-plan@" in i for i in r.get("identities", []))
        and any(op.get("service") == "logging.googleapis.com"
                and "LoggingServiceV2.ListLogEntries" in op.get("methods", [])
                for op in r.get("operations", []))
        for r in baseline
    )
    check("baseline_ingress pokrywa tozsamosc, ktora czyta audit-log czlonkow",
          not (czyta_logi_czlonka and konto_planu) or pokryte,
          "violations-report czyta logi czlonka kontem planu, a baseline_ingress nie ma dla niego reguly "
          "na logging.googleapis.com/LoggingServiceV2.ListLogEntries")

    # `promotion_gate` odrzuca `stage: enforced` bez wpisu w `violations_last_window`. Ta mapa ma dokładnie
    # jedno źródło — artefakt `violations-report.yml` — więc jeśli `validate.yml` go nie pobiera i nie podaje
    # do `collect_declarations.py`, bramka nie jest bramką, tylko ŚCIANĄ: przepuścić się jej nie da NIGDY,
    # niezależnie od tego, jak czyste jest okno. Ściana, przez którą trzeba przejść, żeby wykonać robotę,
    # kończy się usunięciem reguły — i wtedy nie ma ani ściany, ani bramki.
    walid = tekst_wykonywany("validate.yml")
    check("validate: bramka promocji ma skad wziac dowod (--violations)",
          "--violations" in walid and "gh run download" in walid,
          "brak sciezki artefakt raportu -> collect_declarations.py --violations")
    check("validate: uprawnienie do odczytu artefaktow zadeklarowane",
          re.search(r"^\s*actions:\s*read\s*$", walid, re.M) is not None)
    # TO SAMO NA SCIEZCE APPLY. Bramka `promotion_gate` jest fail-closed: bez mapy `violations_last_window`
    # odrzuca KAZDEGO czlonka `enforced`. Gdyby dowod pobieral wylacznie tor pull requesta, bramki przed
    # apply byly by OSTRZEJSZE od tych, ktore przepuscily review — zmergowana promocja nie zostalaby
    # zastosowana nigdy, a przebieg wygladalby na „bramka zadziala".
    zastosowanie = tekst_wykonywany("apply.yml")
    check("apply: bramki na sciezce mutatora maja ten sam dowod naruszen co PR",
          "--violations" in zastosowanie and "gh run download" in zastosowanie,
          "job bramek w apply.yml nie pobiera artefaktu raportu")
    check("apply: uprawnienie do odczytu artefaktow zadeklarowane",
          re.search(r"^\s*actions:\s*read\s*$", zastosowanie, re.M) is not None)
    # Producent i konsument artefaktu muszą mówić o TEJ SAMEJ nazwie. Nazwy czytamy z obu plików, nie
    # z listy w teście — ten sam rozjazd producent/konsument wywrócił już raz bramki OPA na planie.
    nazwa_up = re.search(r"upload-artifact@[^\n]*\n(?:.*\n)*?\s*with:\s*\n\s*name:\s*(\S+)", raport)
    nazwa_down = re.search(r"gh run download[^\n]*--name\s+(\S+)", walid)
    check("validate: nazwa pobieranego artefaktu = nazwa publikowanej przez raport",
          nazwa_up is not None and nazwa_down is not None and nazwa_up.group(1) == nazwa_down.group(1),
          f"upload={nazwa_up and nazwa_up.group(1)} download={nazwa_down and nazwa_down.group(1)}")

    # DRUGIE WEJŚCIE TEJ SAMEJ BRAMKI: STAN ZASTOSOWANY (kontrakt). Bramka promocji pyta o PRZEJŚCIE do
    # `enforced`, a nie o stan — więc bez `--contract` KAŻDY członek już egzekwowany wygląda jak promocja
    # trwająca w tej chwili i odrzuca cudze wnioski własnymi odmowami.
    #
    # GUARD ENUMERUJE ŚCIEŻKI Z PLIKÓW, a nie z listy wpisanej tutaj — i to jest cała jego wartość. Ten sam
    # zestaw reguł uruchamiają dziś cztery różne miejsca (tor pull requesta, tor mutatora i dwa kanały
    # wejścia), a pominięcie wejścia w JEDNYM z nich jest niewidoczne: przebieg pada na cudzym członku,
    # komunikatem o promocji, w workflow, który promocji nie dotyczy. ZMIERZONE — dokładnie tak wyglądała
    # awaria kanału ticketowego po pierwszej promocji w organizacji. Guard z listą nazw przegapiłby piątą
    # ścieżkę dopisaną jutro; guard czytający pliki nie ma jak.
    # CZYTAMY WYŁĄCZNIE CIAŁA `run:`, nie tekst pliku. Komentarz tłumaczący, po co jest `--contract`,
    # zaliczyłby asercję tekstową także w pliku, z którego flagę usunięto — czyli guard zdawałby się na
    # własną dokumentację. To ta sama pułapka, przed którą ostrzega nagłówek `tekst_wykonywany`.
    def komendy(nazwa: str) -> str:
        wf = yaml.safe_load((ROOT / ".github/workflows" / nazwa).read_text())
        return "\n".join(str(k.get("run") or "") for k, _ in kroki_workflow(wf))

    ogladane, bez_stanu = [], []
    for plik in sorted((ROOT / ".github/workflows").glob("*.yml")):
        wykonywane = komendy(plik.name)
        # Interesują nas WYŁĄCZNIE ścieżki, które oceniają PEŁNY zbiór członków regułami onboardingu.
        # `contrib/validate-local.sh` buduje wejście po swojemu (jeden zgłaszany członek) i dlatego tu
        # nie wchodzi — tam „nie wiem" jest poprawną, najsurowszą odpowiedzią.
        if "collect_declarations.py" not in wykonywane or "--namespace vpcsc.onboarding" not in wykonywane:
            continue
        ogladane.append(plik.name)
        if "--contract" not in wykonywane:
            bez_stanu.append(plik.name)
    check("kazda sciezka uruchamiajaca bramki onboardingu podaje stan zastosowany (--contract)",
          not bez_stanu, f"bez --contract: {bez_stanu}")

    # ANTY-TAUTOLOGIA guardu wyżej: pusta pętla przechodzi każdy warunek „nie znaleziono naruszeń".
    # Ścieżki są dziś cztery (validate, apply, intake, external-intake); próg 3 zostawia miejsce na
    # świadome usunięcie jednej, a wywraca się, gdy rozpoznawanie ścieżek przestanie działać.
    check("guard stanu zastosowanego oglada co najmniej trzy sciezki (nie jest pusta petla)",
          len(ogladane) >= 3, str(ogladane))

    ext = (ROOT / ".github/workflows/external-intake.yml").read_text()
    # Kanał zewnętrzny ma dwa niezbywalne zabezpieczenia: change_ref musi wskazywać repozytorium, które
    # NAPRAWDĘ wysłało dispatch, a stage jest nadpisywany na dry-run niezależnie od treści payloadu.
    check("external-intake: change_ref sprawdzany wobec repozytorium zgłaszającego",
          'ref.startswith(f"pr:{source}#")' in ext)
    # WYMUSZENIE dry-run I ZAKAZ NADPISANIA sa nadal niezbywalne — ale od czasu ujednolicenia renderera
    # egzekwuje je `tools/render_member.py`, a nie kopia logiki w tym workflowie. Te dwie asercje szukały
    # kiedyś literalnie `member["stage"] = "dry-run"` w tekście workflowa, czyli mierzyły KSZTAŁT KODU,
    # a nie własność, która ma być prawdziwa. Po przeniesieniu tej logiki w jedno miejsce paliłyby się na
    # zielono dopiero po przywróceniu drugiego renderera — czyli nagradzałyby regresję.
    check("external-intake: renderuje przez wspolny tools/render_member.py (jeden renderer, trzy kanaly)",
          "tools/render_member.py" in ext)
    # Wlasnosci egzekwowane przez tamten skrypt sprawdza test_kanal_ticketowy(), URUCHAMIAJAC go: plik
    # wychodzi ze `stage: dry-run`, a powtorne zgloscenie istniejacego czlonka konczy sie bledem.
    check("external-intake: nie ma DRUGIEGO renderera (nie zrzuca payloadu do YAML-a)",
          "yaml.safe_dump(member" not in bez_komentarzy(ext), "zostal zrzut calego payloadu")

    # Bramki po stronie GitHuba selftest sprawdzić nie może — nie ma API. Może za to sprawdzić, czy skrypt,
    # który je zakłada, ROZRÓŻNIA wysłanie ustawienia od jego istnienia. Cała ta trójka pilnuje jednego
    # trybu awarii: environment bez ani jednej reguły ochrony, opisany w komentarzach jako bramka.
    boot = (ROOT / "tools/bootstrap_github.sh").read_text()
    check("bootstrap: polityka galezi environment ustawiana zawsze (dziala na kazdym planie)",
          "deployment-branch-policies" in boot and "custom_branch_policies" in boot)
    check("bootstrap: wymagani recenzenci ODCZYTYWANI z API, nie zakladani po PUT",
          "required_reviewers" in boot and "protection_rules" in boot)
    check("bootstrap: brak bramki ludzkiej wymaga jawnego odstepstwa (--no-human-gate)",
          "--no-human-gate" in boot and "NO_HUMAN_GATE" in boot)

    # Ślad audytowy break-glassa musi być w REPOZYTORIUM, nie tylko w metadanych przebiegu: commit jest
    # autorstwa bota, więc „kto" musi stać w treści commita i w issue postmortem. Dzielimy plik na krok
    # commitujący i krok otwierający issue, bo obecność `github.actor` w jednym z nich nic nie mówi o drugim.
    bg = (ROOT / ".github/workflows/break-glass.yml").read_text()
    przed_issue, _, po_issue = bg.partition("open the postmortem issue")
    check("break-glass: commit niesie, KTO uruchomil procedure", "github.actor" in przed_issue)
    check("break-glass: issue postmortem niesie autora i odsylacz do przebiegu",
          "github.actor" in po_issue and "github.run_id" in po_issue)

    for f in wf:
        body = f.read_text()
        # Uprawnienie wykrywamy po SAMYM KODZIE. `id-token: write` to deklaracja, nie zdanie — a komentarz
        # tłumaczący, że job tego uprawnienia NIE MA, włączał ten test i kazał szukać w nim WIF-a, którego
        # z definicji nie ma. Test padał więc o własną dokumentację; ta sama choroba co przy strip_heredocs,
        # tylko odwrotnym znakiem: nie fałszywe odrzucenie, lecz fałszywe WŁĄCZENIE bramki.
        kod = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
        if "id-token: write" in kod:
            # Warunek jest o TOŻSAMOŚCI, nie o wersji akcji: sprawdzamy, że workflow uwierzytelnia się przez
            # `auth` z `workload_identity_provider`. Wersja jest przypięta SHA-em i będzie się zmieniać
            # (Dependabot), więc wpisanie tu `@v2` robiło z tego testu detektor aktualizacji, nie bramkę.
            uses_auth = re.search(r"uses:\s*google-github-actions/auth@", kod) is not None
            check(f"{f.name}: uzywa WIF (bez kluczy SA)",
                  uses_auth and "workload_identity_provider:" in kod)
    joined = "\n".join(f.read_text() for f in wf)
    check("zaden workflow nie zawiera klucza SA ani hasla",
          "private_key" not in joined and "credentials_json" not in joined)


# ----------------------------------------------- workflowy uruchamiane TAK, JAK STOJA (nie czytane)
#
# DLACZEGO to nie jest duplikat test_workflows(): tamten czyta workflowy jak tekst, a caly selftest
# uruchamia bramki WLASNA komenda i we WLASNYM srodowisku. W tej szczelinie przezyly komplet 179 zielonych
# testow dwa defekty, ktore wywrocily PIERWSZY PR w wygenerowanym repo perimetru (#1933):
#   * `terraform test` w validate.yml padal na braku tozsamosci — provider `google` odmawia INICJALIZACJI
#     bez zadnych credentiali. Lokalnie i w selftescie bylo zielono, bo deweloper ma ADC, a selftest.yml
#     startera podaje atrape tokenu na poziomie JOBA. Szablon, ktory realnie jedzie u odbiorcy, jej nie mial;
#   * `> plan.json` w plan.yml zapisywalo plan w korzeniu repo (przekierowanie robi powloka), a conftest
#     czytal `terraform/plan.json` — bramki OPA na planie nie wykonaly sie ani razu.
# Oba widac wylacznie wtedy, gdy wykona sie DOKLADNIE to, co pojedzie w CI: ta komenda i to srodowisko.

# Atrapa terraforma dla testu sciezek: odtwarza SKUTKI komend na PLIKACH, nie planuje niczego. Badany jest
# rozjazd „gdzie plik powstaje" kontra „skad jest czytany", a bierze sie on stad, ze `-chdir` przenosi
# katalog roboczy TERRAFORMOWI, a przekierowanie `>` wykonuje POWLOKA w katalogu joba. Prawdziwy terraform
# potrzebowalby do tego poswiadczen i polaczenia z chmura; atrapa odwzorowuje sama te wlasnosc.
ATRAPA_TERRAFORM = '''#!/usr/bin/env python3
"""Atrapa terraforma na potrzeby selftestu — patrz komentarz przy ATRAPA_TERRAFORM."""
import pathlib
import sys

argv = sys.argv[1:]
chdir, reszta = "", []
for a in argv:
    if a.startswith("-chdir="):
        chdir = a[len("-chdir="):]
    else:
        reszta.append(a)
baza = pathlib.Path(chdir) if chdir else pathlib.Path(".")
polecenie = reszta[0] if reszta else ""

if polecenie == "plan":
    for a in reszta:
        if a.startswith("-out="):
            (baza / a[len("-out="):]).write_text("atrapa-planu")
elif polecenie == "show":
    plik = baza / reszta[-1]
    if not plik.exists():
        sys.stderr.write("atrapa: nie ma pliku planu %s\\n" % plik)
        sys.exit(1)
    if "-json" in reszta:
        sys.stdout.write('{"format_version": "1.2", "atrapa": true}\\n')
    else:
        sys.stdout.write("atrapa: podsumowanie planu\\n")
sys.exit(0)
'''


def akcja_lokalna(uses: str):
    """Kroki AKCJI ZLOZONEJ wolanej przez `uses: ./sciezka` — albo None, gdy to nie jest akcja lokalna.

    DLACZEGO TO JEST TU, A NIE W KAZDYM TESCIE Z OSOBNA. Odkad bramki tresci mieszkaja w jednym miejscu
    (`.github/actions/bramki-tresci`, DEC-16), workflow, ktory je uruchamia, ma w tym miejscu JEDEN krok
    `uses:` zamiast dwunastu `run:`. Test czytajacy same `jobs[*].steps` przestalby wiec widziec bramki
    — i zielenilby sie na pliku, z ktorego wszystkie usunieto. To ta sama klasa bledu, ktora ten selftest
    tropi gdzie indziej: asercja o KSZTALCIE pliku zamiast o wlasnosci, ktora ma byc prawdziwa.
    """
    if not isinstance(uses, str) or not uses.startswith("./"):
        return None
    baza = ROOT / uses[2:]
    plik = next((baza / n for n in ("action.yml", "action.yaml") if (baza / n).exists()),
                baza if baza.is_file() else None)
    if plik is None:
        return None
    return (yaml.safe_load(plik.read_text()).get("runs") or {}).get("steps") or []


def kroki_workflow(wf: dict, rozwijaj: bool = True):
    """Splaszcza workflow do par (krok, env), scalajac env z poziomu workflow -> job -> krok.

    Kroki akcji lokalnych (`uses: ./…`) sa domyslnie ROZWIJANE w miejscu — patrz `akcja_lokalna`. Dzieki
    temu kazda asercja o bramkach dziala tak samo, niezaleznie od tego, czy bramka stoi wpisana w workflow,
    czy w akcji zlozonej wolanej przez dwa workflowy.

    `rozwijaj=False` zostaje dla testow o WNETRZU JEDNEGO PLIKU — para producent/konsument pliku planu
    zyje w obrebie jednego workflowa i rozwiniete kroki akcji wspolnych sa tam szumem: `conftest test …
    declarations.json` z bramek tresci nie jest konsumentem planu, a wygladalby na niego.

    Env bierzemy WYLACZNIE z badanego pliku, nigdy ze srodowiska procesu: harness selftestu dostaje
    `GOOGLE_OAUTH_ACCESS_TOKEN` ze swojego wlasnego workflowa i przekazuje go dalej dzieciom. Test, ktory
    by z tego korzystal, zielenilby sie CUDZA konfiguracja — i to jest dokladnie ten mechanizm, ktory ukryl
    brak atrapy w szablonie validate.yml.
    """
    for job in (wf.get("jobs") or {}).values():
        for krok in job.get("steps") or []:
            env = {}
            env.update(wf.get("env") or {})
            env.update(job.get("env") or {})
            for pod in (akcja_lokalna(str(krok.get("uses", ""))) if rozwijaj else None) or []:
                yield pod, {**env, **(pod.get("env") or {})}
            env.update(krok.get("env") or {})
            yield krok, env


def tekst_wykonywany(nazwa_workflow: str) -> str:
    """Tekst workflowa RAZEM z tekstem akcji lokalnych, ktore wola.

    Asercje tekstowe (`"--violations" in ...`) pytaja o to, CO SIE WYKONA, a nie o to, w ktorym pliku
    jest to zapisane. Sklejenie obu zrodel utrzymuje je prawdziwymi po przeniesieniu kroku do akcji
    zlozonej — i nadal czerwieni je, gdy krok zniknie naprawde.
    """
    sciezka = ROOT / ".github/workflows" / nazwa_workflow
    tekst = sciezka.read_text()
    czesci = [tekst]
    for uses in re.findall(r"^\s*-?\s*uses:\s*(\./\S+)", tekst, re.M):
        plik = ROOT / uses[2:] / "action.yml"
        if plik.exists():
            czesci.append(plik.read_text())
    return "\n".join(czesci)


def srodowisko_bez_tozsamosci_google() -> dict:
    """Kopia srodowiska z WYCIETYMI wszystkimi kanalami poswiadczen Google.

    Provider `google` czyta tozsamosc ze zmiennych `GOOGLE_*`/`GCLOUD_*`/`CLOUDSDK_*`, a na koncu z pliku
    ADC. Runner GitHuba nie ma zadnego z tych zrodel, deweloper ma ADC prawie zawsze — i cala roznica
    miedzy „zielono lokalnie" a czerwonym CI siedzi w tym jednym pliku.

    HOME MUSI byc podmieniony, nie tylko `CLOUDSDK_CONFIG`: biblioteka, z ktorej korzysta provider, szuka
    ADC pod `$HOME/.config/gcloud/application_default_credentials.json` i `CLOUDSDK_CONFIG` (zmiennej gcloud)
    NIE HONORUJE. Zmierzone: przy samym `CLOUDSDK_CONFIG` test przechodzil takze z ROZBROJONA poprawka,
    czyli nie badal niczego — dokladnie ta klasa bledu, ktora ten plik tropi gdzie indziej. Rozpakowana
    kopia jest juz zainicjalizowana (`.terraform/` lezy w katalogu modulu), wiec przeniesienie HOME nie
    odbiera terraformowi providerow.
    """
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GOOGLE_", "GCLOUD_", "GCP_", "CLOUDSDK_"))}
    pusty = tempfile.mkdtemp(prefix="vpcsc-bez-adc-")
    env["HOME"] = pusty
    env["CLOUDSDK_CONFIG"] = pusty
    return env


def konsumenci_planu(kroki):
    """Sciezki, ktore kroki PO planie czytaja — wyciagane z pliku, nie wpisane w test.

    Wpisanie ich na sztywno zrobiloby z tego kopie workflowa: zmiana sciezki w JEDNYM miejscu przestalaby
    byc wykrywalna, a badanym trybem awarii jest wlasnie rozjazd producenta z konsumentem.
    """
    for krok in kroki:
        run = str(krok.get("run", ""))
        m = re.search(r"conftest test\b[^\n]*?(\S+\.json)", run)
        if m:
            yield "bramki OPA na planie (conftest)", m.group(1)
        m = re.search(r"sha256sum\s+(\S+)", run)
        if m:
            yield "przypiecie planu (sha256sum)", m.group(1)
        if "upload-artifact" in str(krok.get("uses", "")):
            sciezka = (krok.get("with") or {}).get("path")
            if sciezka:
                yield "artefakt dla apply (upload-artifact)", sciezka


def test_workflowy_wykonywalne() -> None:
    print("\n== workflowy uruchamiane tak, jak stoja ==")
    walidacja = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text())

    # --- 1. guard na pinowanie akcji: uruchamiamy JEGO WLASNY kod na wejsciu, ktorego jeszcze nie widzial.
    # Dotad guard istnial tylko jako tekst w workflowie, a selftest sprawdzal pinowanie WLASNYM wyrazeniem
    # w Pythonie — czyli druga implementacja tej samej reguly. Zgodnosc dwoch niezaleznych regexow nikt nie
    # mierzyl, wiec pierwszy bump Dependabota (`SHA` + `# vX.Y.Z`) byl pierwszym realnym wejsciem guardu.
    guard = next((k["run"] for k, _ in kroki_workflow(walidacja)
                  if "pinned to a SHA" in str(k.get("name", ""))), None)
    check("validate.yml ma krok guardu na pinowanie akcji", guard is not None)
    if guard:
        sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"  # realny SHA actions/checkout v7.0.1
        przypadki = [
            ("format Dependabota (SHA + komentarz z tagiem)", f"      - uses: actions/checkout@{sha} # v7.0.1", 0),
            ("goly SHA bez komentarza", f"      - uses: actions/checkout@{sha}", 0),
            ("akcja lokalna (./contrib) nie jest third-party", "      - uses: ./contrib", 0),
            ("ruchomy tag @v4 ODRZUCONY", "      - uses: actions/checkout@v4", 1),
            ("skrocony SHA (7 znakow) ODRZUCONY", f"      - uses: actions/checkout@{sha[:7]}", 1),
            ("branch @main ODRZUCONY", "      - uses: actions/checkout@main", 1),
        ]
        for opis, linia, oczekiwany in przypadki:
            piaskownica = pathlib.Path(tempfile.mkdtemp(prefix="vpcsc-guard-"))
            (piaskownica / ".github/workflows").mkdir(parents=True)
            (piaskownica / "contrib").mkdir()
            (piaskownica / ".github/workflows/probka.yml").write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n" + linia + "\n")
            (piaskownica / "contrib/action.yml").write_text("runs:\n  using: composite\n  steps: []\n")
            p = sh(["bash", "-e", "-c", guard], cwd=piaskownica)
            check(f"guard pinowania na zywym wejsciu: {opis}",
                  p.returncode == oczekiwany,
                  f"rc={p.returncode}, oczekiwano {oczekiwany}; {(p.stdout + p.stderr)[-300:]}")

    # --- 2. `terraform test` musi przejsc z tozsamoscia, ktora deklaruje SAM workflow — i tylko z nia.
    krok_test, env_test = next(((k, e) for k, e in kroki_workflow(walidacja)
                                if re.search(r"terraform\s+(-chdir=\S+\s+)?test\b", str(k.get("run", "")))),
                               (None, None))
    check("validate.yml ma krok `terraform test`", krok_test is not None)
    if krok_test is not None and have("terraform"):
        env = srodowisko_bez_tozsamosci_google()
        env.update({k: str(v) for k, v in env_test.items()})
        p = subprocess.run(["bash", "-e", "-c", krok_test["run"]],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        check("validate.yml: `terraform test` przechodzi BEZ ADC (tak jak na runnerze)",
              p.returncode == 0 and "0 failed" in p.stdout, (p.stdout + p.stderr)[-900:])

    # --- 3. plik, ktory krok planu ZAPISUJE, musi byc tym, ktory czytaja kroki nizej.
    #
    # OBA WORKFLOWY, NIE JEDEN. Ten test powstal dla `plan.yml` i przez ten czas `apply.yml` — z DOKLADNIE
    # ta sama para producent/konsument — nie byl badany wcale. Defekt przezyl tam poprawke o rok: `apply`
    # padal wczesniej, na uprawnieniach, wiec krok bramek nie wykonal sie ANI RAZU i nie mial jak zglosic
    # `stat terraform/plan.json: no such file or directory`. Test dopisany wylacznie dla jednego z pary
    # workflowow odtwarza dokladnie te asymetrie, ktora defekt wpuscila — stad petla, nie kopia.
    wf_kroki = {}
    for nazwa in ("plan.yml", "apply.yml"):
        wf = yaml.safe_load((ROOT / f".github/workflows/{nazwa}").read_text())
        # BEZ rozwijania akcji wspolnych: para producent/konsument pliku planu zyje w obrebie tego
        # jednego workflowa, a `conftest test … declarations.json` z bramek tresci nie jest konsumentem
        # planu — rozwiniety wygladalby na niego i czerwienil test o czyms, czego on nie bada.
        kroki = [k for k, _ in kroki_workflow(wf, rozwijaj=False)]
        wf_kroki[nazwa] = kroki
        krok_planu = next((k for k in kroki if "-out=" in str(k.get("run", ""))), None)
        check(f"{nazwa} ma krok produkujacy plan (-out=)", krok_planu is not None)
        if krok_planu is None:
            continue
        katalog_atrapy = pathlib.Path(tempfile.mkdtemp(prefix="vpcsc-atrapa-tf-"))
        (katalog_atrapy / "terraform").write_text(ATRAPA_TERRAFORM)
        (katalog_atrapy / "terraform").chmod(0o755)
        env = {**os.environ, "PATH": f"{katalog_atrapy}{os.pathsep}{os.environ['PATH']}"}
        p = subprocess.run(["bash", "-e", "-c", krok_planu["run"]],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        check(f"{nazwa}: krok planu wykonuje sie (na atrapie terraforma)",
              p.returncode == 0, (p.stdout + p.stderr)[-500:])
        powstalo = sorted(str(x.relative_to(ROOT)) for x in ROOT.glob("*.json")) + \
            sorted(str(x.relative_to(ROOT)) for x in (ROOT / "terraform").glob("*.json"))
        for opis, sciezka in konsumenci_planu(kroki):
            check(f"{nazwa}: {opis} czyta plik, ktory krok planu naprawde tworzy ({sciezka})",
                  (ROOT / sciezka).exists(), f"krok planu zostawil: {powstalo}")
        for smiec in ("terraform/plan.json", "plan.json", "terraform/tfplan.binary", "tfplan.binary"):
            (ROOT / smiec).unlink(missing_ok=True)

    # --- 3b. bramki na PR i bramki na granicy musza byc TYMI SAMYMI bramkami.
    # `apply.yml` obiecuje w naglowku, ze reguly uruchamiaja sie PONOWNIE na planie z galezi domyslnej.
    # Obietnica jest prawdziwa tylko wtedy, gdy wywolanie ma te same argumenty: `plan.yml` podawal
    # `--data perimeter/policy.yaml`, `apply.yml` nie. To wejscie mowi regulom, dla ktorych uslug API nie
    # publikuje metod — bez niego zbior jest pusty i kazda regula z `"*"` jest odrzucana. Rozjazd wychodzi
    # dopiero PO review, na granicy, czyli w miejscu, w ktorym najdrozej go zauwazyc.
    def wywolania_conftest(kroki):
        for krok in kroki:
            for linia in str(krok.get("run", "")).splitlines():
                if "conftest test" in linia:
                    # sam plik planu wycinamy: rozni sie miedzy workflowami legalnie (artefakt vs re-plan)
                    yield tuple(a for a in linia.split() if not a.endswith(".json"))

    arg = {n: sorted(wywolania_conftest(k)) for n, k in wf_kroki.items()}
    check("plan.yml i apply.yml wolaja conftest z TYMI SAMYMI argumentami (te same bramki, nie podobne)",
          bool(arg.get("plan.yml")) and arg.get("plan.yml") == arg.get("apply.yml"),
          f"plan.yml={arg.get('plan.yml')!r} apply.yml={arg.get('apply.yml')!r}")

    # --- 4. starter-drift: bramka, ktora ma ZLAPAC rozjazd, musi go realnie lapac.
    #
    # Ta bramka istnieje, bo rozjazd materialu szablonu wystapil DWA RAZY w ciagu jednego dnia, a za
    # drugim razem ukrywal raport meldujacy czyste okno przy 30 realnych naruszeniach — czyli dowod dla
    # promocji. Testujemy ja tak samo jak kazda inna: uruchamiajac krok w postaci, w jakiej stoi
    # w workflow, na atrapie `gh`. Dwa przypadki, bo bramka, ktora nigdy nie odrzuca, nie chroni niczego.
    krok_rozjazd = next((k for k, _ in kroki_workflow(
        yaml.safe_load((ROOT / ".github/workflows/starter-drift.yml").read_text()))
        if "starter-sync" in str(k.get("run", ""))), None)
    check("starter-drift.yml ma krok porownujacy wskaznik z main startera", krok_rozjazd is not None)
    if krok_rozjazd is not None:
        zapisany = "1" * 40
        bin_gh = ROOT / "stub-bin-gh"
        bin_gh.mkdir(exist_ok=True)

        def uruchom_rozjazd(head: str, status: str, ahead: int) -> subprocess.CompletedProcess:
            (bin_gh / "gh").write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                f"  *commits/main*) echo '{head}' ;;\n"
                "  *compare/*) cat <<'JSON'\n"
                + json.dumps({"status": status, "ahead_by": ahead,
                              "commits": [{"sha": "2" * 40,
                                           "commit": {"message": "fix(naruszenia): zly zakres logow"}}]})
                + "\nJSON\n  ;;\nesac\n")
            (bin_gh / "gh").chmod(0o755)
            (ROOT / ".starter-sync").write_text(
                f"repo: example-org/vpc-sc-perimeter-starter\ncommit: {zapisany}\n")
            (ROOT / "missing.md").unlink(missing_ok=True)
            return subprocess.run(
                ["bash", "-e", "-c", krok_rozjazd["run"]], cwd=ROOT, capture_output=True, text=True,
                env=dict(os.environ, PATH=f"{bin_gh}:{os.environ['PATH']}",
                         GITHUB_OUTPUT=str(ROOT / "gh-output.txt"),
                         GITHUB_STEP_SUMMARY=str(ROOT / "gh-summary.txt")))

        p = uruchom_rozjazd(zapisany, "identical", 0)
        wyjscie = (ROOT / "gh-output.txt").read_text() if (ROOT / "gh-output.txt").exists() else ""
        check("starter-drift: wskaznik rowny main startera -> zielono",
              p.returncode == 0 and "behind=0" in wyjscie, f"rc={p.returncode} {wyjscie} " + p.stderr[-300:])

        # NEGATYW: starter poszedl do przodu. Bramka ma to zglosic i wypisac, CO trzeba przeniesc —
        # sama informacja „jestes w tyle" nie mowi, ktory pull request wskoczyl po ostatnim syncu.
        (ROOT / "gh-output.txt").unlink(missing_ok=True)
        p = uruchom_rozjazd("2" * 40, "ahead", 1)
        wyjscie = (ROOT / "gh-output.txt").read_text() if (ROOT / "gh-output.txt").exists() else ""
        brakuje = (ROOT / "missing.md").read_text() if (ROOT / "missing.md").exists() else ""
        check("starter-drift: starter do przodu -> ZGLASZA rozjazd i wymienia brakujace commity",
              "behind=1" in wyjscie and "zly zakres logow" in brakuje,
              f"rc={p.returncode} {wyjscie} {brakuje[:200]} " + p.stderr[-300:])
        for smiec in (".starter-sync", "gh-output.txt", "gh-summary.txt", "missing.md", "compare.json"):
            (ROOT / smiec).unlink(missing_ok=True)


# --------------------------------------------------------------------- schematy (opcjonalnie)
def test_schemas() -> None:
    print("\n== json schema (opcjonalnie) ==")
    if not have("check-jsonschema"):
        print("  SKIP  check-jsonschema niedostepny lokalnie (CI instaluje go w validate.yml)")
        return
    pairs = [("schemas/policy.schema.json", ["perimeter/policy.yaml"]),
             ("schemas/profile.schema.json", sorted(str(p.relative_to(ROOT)) for p in (ROOT / "perimeter/profiles").glob("*.yaml"))),
             ("schemas/projects.schema.json", ["perimeter/projects.yaml"]),
             ("schemas/access-level.schema.json", sorted(str(p.relative_to(ROOT)) for p in (ROOT / "perimeter/access-levels").glob("*.yaml"))),
             ("schemas/alerting.schema.json", ["perimeter/alerting.yaml"])]
    for schema, files in pairs:
        p = sh(["check-jsonschema", "--schemafile", schema, *files], cwd=ROOT)
        check(f"schema {pathlib.Path(schema).stem} akceptuje przyklady", p.returncode == 0, p.stdout[-500:])

    # NEGATYWY DO SCHEMATU ALERTINGU. Oba przypadki są ciche na wdrożeniu: ukośnik na końcu bazy URL daje
    # `//7-alerty.md`, czyli 404 z alertu o 3:00, a brak jednego z kanałów daje politykę bez odbiorcy —
    # incydent się otwiera i nie idzie do nikogo. Jedno i drugie wygląda w konsoli na skonfigurowane.
    alerting = yaml.safe_load((ROOT / "perimeter/alerting.yaml").read_text())

    def _alerting_odrzuca(nazwa: str, mutacja) -> None:
        import copy
        zly = copy.deepcopy(alerting)
        mutacja(zly)
        sciezka = ROOT / f"alerting-{nazwa}.yaml"
        sciezka.write_text(yaml.safe_dump(zly, sort_keys=False, allow_unicode=True))
        p = sh(["check-jsonschema", "--schemafile", "schemas/alerting.schema.json",
                str(sciezka.relative_to(ROOT))], cwd=ROOT)
        check(f"schema alertingu ODRZUCA {nazwa}", p.returncode != 0, p.stdout[-300:])

    _alerting_odrzuca("ukosnik-na-koncu-runbooka",
                      lambda d: d.__setitem__("runbook_base_url", d["runbook_base_url"] + "/"))
    _alerting_odrzuca("brak-kanalu-bezpieczenstwa", lambda d: d["channels"].pop("security"))
    _alerting_odrzuca("prog-zaleglosci-ponizej-minimum",
                      lambda d: d["thresholds"].__setitem__("apply_pending_seconds", 60))

    # NEGATYWY DO SCHEMATU ACCESS LEVELI. `combining_function: OR` to jednosłowny diff, po którym warunki
    # stają się ALTERNATYWĄ — polityka jest słabsza, a wygląda na przeredagowaną. Schemat jest tu pierwszą
    # z trzech warstw (dalej reguła OPA na deklaracjach i `precondition` renderera); żadna nie jest jedyna,
    # bo `check-jsonschema` bywa niedostępny lokalnie, a reguły OPA można uruchomić z inną ścieżką.
    import copy as _copy
    poziomy_doc = yaml.safe_load((ROOT / "perimeter/access-levels/corp.yaml").read_text())

    def _poziomy_wynik(nazwa: str, mutacja) -> int:
        zly = _copy.deepcopy(poziomy_doc)
        mutacja(zly["access_levels"][0])
        sciezka = ROOT / f"poziomy-{nazwa}.yaml"
        sciezka.write_text(yaml.safe_dump(zly, sort_keys=False, allow_unicode=True))
        wynik = sh(["check-jsonschema", "--schemafile", "schemas/access-level.schema.json", sciezka.name], cwd=ROOT)
        sciezka.unlink(missing_ok=True)
        return wynik.returncode

    check("schema poziomow ODRZUCA combining_function: OR bez or_reason",
          _poziomy_wynik("or-bez-powodu", lambda al: al.__setitem__("combining_function", "OR")) != 0)
    # ANTY-TAUTOLOGIA: ta sama mutacja z uzasadnieniem MUSI przejść, inaczej schemat po prostu zakazuje OR.
    check("schema poziomow AKCEPTUJE OR z or_reason (anty-tautologia)",
          _poziomy_wynik("or-z-powodem", lambda al: al.update({
              "combining_function": "OR",
              "or_reason": "zarzadzany laptop pracuje spoza korpo-sieci i ma miec dostep"})) == 0)
    # Uzasadnienie, które przeżyło powrót do AND, w review wygląda na aktualny opis polityki.
    check("schema poziomow ODRZUCA or_reason bez OR",
          _poziomy_wynik("powod-bez-or", lambda al: al.__setitem__("or_reason", "zostalo po rewercie i nikt nie usunal")) != 0)

    # Furtka `control_plane_exception` musi przejść PRZEZ SCHEMĘ, bo validate.yml sprawdza schematy ZANIM
    # uruchomi reguły OPA (`additionalProperties: false` odrzuciłoby ją wcześniej). Gdyby jej tam brakło,
    # jedyną drogą przy realnej potrzebie byłoby usunięcie projektu z control_plane_projects — czyli
    # rozbrojenie bramki dla wszystkich członków naraz.
    czlonek = yaml.safe_load((ROOT / "perimeter/projects.yaml").read_text())["members"][0]
    czlonek["control_plane_exception"] = {
        "justification": "stan Terraform przeniesiony poza perimetr, apply czyta go spoza granicy"}
    (ROOT / "czlonek-wyjatek.yaml").write_text(yaml.safe_dump(czlonek, sort_keys=False, allow_unicode=True))
    p = sh(["check-jsonschema", "--schemafile", "schemas/member.schema.json", "czlonek-wyjatek.yaml"], cwd=ROOT)
    check("schema czlonka AKCEPTUJE control_plane_exception", p.returncode == 0, p.stdout[-400:])

    # NEGATYW do powyższego: bez progu długości furtka degeneruje się do „ok" i przestaje być decyzją.
    czlonek["control_plane_exception"] = {"justification": "ok"}
    (ROOT / "czlonek-wyjatek-krotki.yaml").write_text(yaml.safe_dump(czlonek, sort_keys=False, allow_unicode=True))
    p = sh(["check-jsonschema", "--schemafile", "schemas/member.schema.json", "czlonek-wyjatek-krotki.yaml"], cwd=ROOT)
    check("schema czlonka ODRZUCA wyjatek bez uzasadnienia (min. 20 znakow)", p.returncode != 0, p.stdout[-400:])

    # KSZTALTY REGUL SA ROZDZIELONE PER KIERUNEK — i to jest bramka, nie porzadek w pliku.
    #
    # Do 2026-08 `ingress` i `egress` dzielily jedna definicje (`ruleList`), wiec `access_levels_from`
    # przechodzilo schemat TAKZE w regule egress. Renderer sklada `egress_from` wylacznie z `identities`,
    # wiec taka deklaracja byla CICHO GUBIONA: schemat zielony, OPA zielone, budzet atrybutow LICZYL to
    # pole, a wyrenderowana regula autoryzowala z dowolnego miejsca. Zmierzone na planie: `egress_from.sources`
    # puste. To najgorszy wariant bledu w tym materiale — deklaracja mowi „wymagaj sieci korporacyjnej",
    # a granica jej nie stawia.
    #
    # Kazdy przypadek nizej to POJEDYNCZA mutacja poprawnego profilu; komplet dzisiejszych profili
    # przechodzi (asercja „schema profile.schema akceptuje przyklady" wyzej), wiec test nie moze przejsc
    # dlatego, ze schemat odrzuca wszystko.
    profil = yaml.safe_load((ROOT / "perimeter/profiles/vertex-batch-training.yaml").read_text())

    def _schema_odrzuca(nazwa: str, mutacja) -> None:
        import copy
        zly = copy.deepcopy(profil)
        mutacja(zly)
        sciezka = ROOT / f"profil-{nazwa}.yaml"
        sciezka.write_text(yaml.safe_dump(zly, sort_keys=False, allow_unicode=True))
        wynik = sh(["check-jsonschema", "--schemafile", "schemas/profile.schema.json", sciezka.name], cwd=ROOT)
        check(f"schema profilu ODRZUCA {nazwa}", wynik.returncode != 0, wynik.stdout[-400:])

    def _egress_access_level(d):
        d["egress"][0]["access_levels_from"] = "access_levels"

    def _ingress_cel_egressowy(d):
        d["ingress"][0]["to_projects_from"] = "data_source_projects"

    def _oba_selektory(d):
        d["egress"][0]["operations"][0]["permissions"] = ["externalResource.read"]

    def _bez_selektorow(d):
        del d["egress"][0]["operations"][0]["methods"]

    _schema_odrzuca("access-levels-from-w-egresie", _egress_access_level)
    _schema_odrzuca("cel-egressowy-w-ingresie", _ingress_cel_egressowy)
    _schema_odrzuca("operacje-z-methods-I-permissions", _oba_selektory)
    _schema_odrzuca("operacje-bez-zadnego-selektora", _bez_selektorow)


# ----------------------------------------------------------------- samodzielnosc materialu
def test_samodzielnosc() -> None:
    """Ten katalog ma stać sam dla siebie: bez repo, z którego pochodzi, i bez nazw konkretnej organizacji.

    DLACZEGO to jest TEST, a nie jednorazowe sprzątanie: identyfikatory wracają. Ktoś wkleja przykład
    z realnego zgłoszenia, ktoś podpiera komentarz numerem wewnętrznego ADR-a — i po trzech miesiącach
    materiał znowu opisuje konkretną firmę. Skan kosztuje sekundę i biegnie przy każdym przebiegu.

    Reguły mieszkają w `skan_samodzielnosci.py` — osobno, bo ten sam skan wpina się jako tania bramka
    tam, gdzie materiał jest publikowany (wymaga samego Pythona, w przeciwieństwie do reszty selftestu).
    """
    print("\n== samodzielnosc materialu ==")
    sys.path.insert(0, str(HERE))
    import skan_samodzielnosci as skan

    # Skanujemy ROZPAKOWANE repo (to, co realnie dostaje odbiorca) ORAZ starter, bo README i docs/
    # startera też idą na zewnątrz.
    for etykieta, base in [("rozpakowane repo", ROOT), ("starter", STARTER)]:
        trafienia = skan.skanuj_sciezke(base)
        check(f"{etykieta}: zero odsylaczy do organizacji i repo macierzystego",
              not trafienia, "; ".join(trafienia[:6]))

    # Anty-tautologia: skan, który nic nie znajduje na czystym wejściu, mógłby po prostu nie działać
    # (zły regex, pominięte rozszerzenie). Podkładamy tekst naruszający KAŻDĄ z pięciu klas reguł
    # i wymagamy kompletu trafień. Wartości w próbce są wymyślone — próbka jest częścią materiału
    # publicznego, więc nie może nieść niczego realnego.
    # Próbkę SKLEJAMY z kawałków, zamiast wpisać wprost. DLACZEGO: ten plik też podlega skanowi, więc
    # próbka napisana dosłownie zapaliłaby guard na jego własnym teście — a wtedy jedynym wyjściem jest
    # wyłączenie pliku ze skanu, czyli zrobienie w nim dziury. Sklejenie kosztuje jedną linijkę i zostawia
    # plik w pełni skanowany. Wartości są wymyślone; próbka jest częścią materiału publicznego.
    probka = (
        "Przyklad naruszenia: repo " + "labu, ADR GCP-" + "0999, klie" + "nt prosi o dostep.\n"
        "Numer projektu 987654" + "321098, zgloszenie RITM" + "0912345, dostawca: Hetz" + "ner.\n"
    )
    powody = {powod for _, _, powod in skan.skanuj_tekst(probka)}
    check("skan samodzielnosci LAPIE wszystkie szesc klas naruszen (test anty-tautologiczny)",
          len(powody) == 6, f"zlapane klasy ({len(powody)}): {sorted(powody)}")

    # Skan musi tez umiec powiedziec CZYSTO — inaczej zielone nic nie znaczy, bo zawsze cos zglasza.
    check("skan samodzielnosci nie zglasza nic na czystym tekscie",
          not skan.skanuj_tekst("Zwykly akapit o perimetrze i regulach ingress. Projekt 123456789012."))


def test_bramki_na_sciezce_apply() -> None:
    """Czy bramka stoi tam, gdzie NAPRAWDE zmienia sie granica — czy tylko obok.

    ZMIERZONY TRYB AWARII (DEC-16). `apply.yml` wyzwala sie na push do galezi domyslnej i wykonywal
    `plan` -> reguly `vpcsc.perimeter` na plan-JSON -> `apply`. Ani jednej bramki TRESCI: schematow,
    `vpcsc.onboarding` (w tym `control_plane_projects`), budzetu atrybutow, `control_plane_check.py`.
    Galaz domyslna repo perimetru bywa bez ochrony (funkcja platna na repo prywatnym), wiec commit
    wypchniety prosto na nia omijal CALY tor `pull_request`. `terraform plan` przepuszczal to na zielono,
    bo reguly `vpcsc.perimeter` nie wiedza nic o plaszczyznie sterowania.

    Ten test mierzy ZAWIERANIE ZBIOROW, a nie obecnosc slow w pliku: kazda bramka wolana przez tor pull
    requesta ma byc wolana takze przez mutatora. Zbiory licza sie z plikow, wiec dopisanie bramki tylko
    do `validate.yml` czerwieni ten test od razu — a to jest jedyny sposob, zeby „te same bramki"
    zostalo prawda po pierwszej zmianie.
    """
    print("\n== bramki na sciezce apply ==")

    def akcje(nazwa: str) -> set:
        wf = yaml.safe_load((ROOT / ".github/workflows" / nazwa).read_text())
        return {str(k.get("uses")) for job in (wf.get("jobs") or {}).values()
                for k in (job.get("steps") or [])
                if str(k.get("uses", "")).startswith("./.github/actions/")}

    tor_pr = akcje("validate.yml") | akcje("plan.yml")
    tor_apply = akcje("apply.yml")
    # PREMISA. Bez niej zawieranie pustego zbioru jest prawdziwe zawsze — czyli test bylby zielony takze
    # wtedy, gdyby bramki zniknely z obu torow naraz. Dokladnie ta klasa bledu, ktora ten plik tropi.
    check("premisa: tor pull requesta wola bramki ze wspolnej definicji", len(tor_pr) >= 2, str(tor_pr))
    check("KAZDA bramka z toru pull requesta jest tez na sciezce mutatora",
          tor_pr <= tor_apply, f"brakuje na apply: {sorted(tor_pr - tor_apply)}")

    apply_wf = yaml.safe_load((ROOT / ".github/workflows/apply.yml").read_text())
    joby = apply_wf["jobs"]
    job_bramek = next((n for n, j in joby.items()
                       if any(str(k.get("uses", "")).startswith("./.github/actions/")
                              for k in (j.get("steps") or []))), None)
    check("apply.yml ma job uruchamiajacy bramki", job_bramek is not None, str(list(joby)))

    job_applikujacy = next((n for n, j in joby.items()
                            if any("terraform" in str(k.get("run", "")) and " apply " in str(k.get("run", ""))
                                   for k in (j.get("steps") or []))), None)
    check("apply.yml ma job wykonujacy terraform apply", job_applikujacy is not None, str(list(joby)))

    if job_bramek and job_applikujacy:
        needs = joby[job_applikujacy].get("needs")
        needs = [needs] if isinstance(needs, str) else list(needs or [])
        # TWARDA zaleznosc, nie kolejnosc krokow: czerwone bramki maja SKASOWAC uruchomienie apply,
        # a nie zostawic je do przerwania w polowie.
        check("job applikujacy NIE STARTUJE bez zielonych bramek (needs)",
              job_bramek in needs, f"needs={needs}")
        # Job z `environment` nie wykona ani jednego kroku na galezi spoza polityki tego environment —
        # GitHub odrzuca CALY job. Bramki tresci w tamtym jobie byly by wiec nietestowalne inaczej niz na
        # zywej granicy; osobny job bez `environment` da sie uruchomic z galezi testowej i ZOBACZYC, ze
        # odrzuca. To jest jedyny powod, dla ktorego test anty-tautologiczny tej zmiany w ogole istnieje.
        check("job bramek tresci nie deklaruje environment (da sie go uruchomic z galezi testowej)",
              "environment" not in joby[job_bramek], str(joby[job_bramek].get("environment")))
        konta_bramek = [k.get("with", {}).get("service_account") for k in joby[job_bramek]["steps"]
                        if "google-github-actions/auth" in str(k.get("uses", ""))]
        # ZERO POSWIADCZEN w jobie bramek tresci: job, ktory sie nie uwierzytelnia, nie moze zmienic
        # niczego — takze wtedy, gdy ktos dopisze do niego krok. I dziala na kazdej galezi.
        check("job bramek tresci nie uwierzytelnia sie w chmurze", not konta_bramek, str(konta_bramek))

        # BRAMKI ZYWE TOZSAMOSCIA MUTATORA. Zapytane kontem `plan` opisywalyby swiat widziany przez KOGOS
        # INNEGO niz konto, ktore za chwile zmieni granice — a roznica wyszlaby dopiero jako czerwony apply.
        kroki_ap = joby[job_applikujacy]["steps"]
        zywe = [i for i, k in enumerate(kroki_ap) if str(k.get("uses", "")).endswith("/bramki-zywe")]
        auth = [i for i, k in enumerate(kroki_ap)
                if "google-github-actions/auth" in str(k.get("uses", ""))]
        konta_apply = [kroki_ap[i]["with"]["service_account"] for i in auth]
        check("bramki zywe stoja w jobie APPLIKUJACYM (ta sama tozsamosc, co mutacja)",
              len(zywe) == 1, str(zywe))
        check("job applikujacy uwierzytelnia sie kontem APPLY",
              konta_apply == ["${{ vars.APPLY_SERVICE_ACCOUNT }}"], str(konta_apply))
        stosowanie = [i for i, k in enumerate(kroki_ap)
                      if "terraform" in str(k.get("run", "")) and " apply " in str(k.get("run", ""))]
        check("bramki zywe wykonuja sie PRZED terraform apply",
              zywe and stosowanie and zywe[0] < stosowanie[0], f"zywe={zywe} apply={stosowanie}")

    # KONKRETNE bramki, nie sama liczba krokow: to sa te, ktorych brak zmierzono na sciezce apply.
    kroki_apply = [k for k, _ in kroki_workflow(apply_wf)]
    tresc = "\n".join(str(k.get("run", "")) for k in kroki_apply)
    for opis, wzorzec in (
        ("schematy JSON deklaracji", "check-jsonschema --schemafile schemas/policy.schema.json"),
        ("reguly vpcsc.onboarding (w tym control_plane_projects)", "--namespace vpcsc.onboarding"),
        ("testy jednostkowe regul (usunieta regula = czerwono)", "conftest verify --policy policy"),
        ("budzet atrybutow", "tools/attribute_budget.py"),
        ("control_plane_check.py offline", "python3 tools/control_plane_check.py\n"),
        ("control_plane_check.py --live", "tools/control_plane_check.py --live"),
        ("lista uslug wspieranych przez VPC-SC (zywa)", "tools/check_supported_services.py"),
        ("reguly vpcsc.perimeter na plan-JSON", "--namespace vpcsc.perimeter"),
        # Jedyna bramka WYLACZNIE mutatora — pyta o MOMENT skutku, nie o tresc zmiany (DEC-17). Stoi na tej
        # liscie z tego samego powodu, co reszta: zeby jej zniknieciu z apply.yml odpowiadal czerwony test,
        # a nie cisza.
        ("bramka promocji do enforced", "tools/promotion_hold.py"),
    ):
        check(f"sciezka apply uruchamia: {opis}", wzorzec in tresc, wzorzec)


def test_bramka_promocji() -> None:
    """Czy apply, ktory zaczyna EGZEKWOWAC granice wobec kogos nowego, naprawde staje — i czy da sie go
    puscic swiadomie (DEC-17).

    TEN TEST JEST ANTY-TAUTOLOGICZNY Z KONSTRUKCJI: nie pyta, czy w workflowie stoja wlasciwe slowa, tylko
    URUCHAMIA logike bramki na spreparowanych parach (deklaracja czlonkow, stan zywej granicy). Obie
    strony porownania sa wejsciem, wiec zaden wariant nie moze zdac przez przypadek — a para „bez promocji
    przechodzi" / „z promocja staje" jest tu jedna asercja obok drugiej. Bramka, ktora zatrzymuje wszystko,
    jest tak samo zepsuta jak ta, ktora nie zatrzymuje niczego: pierwsza cicho przestaje stosowac
    zmergowane zmiany.
    """
    print("\n== bramka promocji (swiadome uruchomienie przed enforced) ==")

    baza = ROOT / "fixture-bramka-promocji"
    (baza / "perimeter").mkdir(parents=True, exist_ok=True)
    wzor = yaml.safe_load((ROOT / "perimeter/projects.yaml").read_text())["members"][0]

    def zapisz(*wpisy) -> list:
        """Plik czlonkow z podanych par (stage, numer projektu). Zwraca ich klucze."""
        doc = {"schema_version": 1, "members": []}
        for i, (stage, numer) in enumerate(wpisy):
            w = json.loads(json.dumps(wzor))
            w.update(project_id=f"prj-example-czlonek-{i}", project_number=numer, stage=stage)
            doc["members"].append(w)
        (baza / "perimeter/projects.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
        return [f"{w['division']}-{w['project_id']}" for w in doc["members"]]

    def granica(*numery) -> pathlib.Path:
        """Odpowiedz API o zywym perimetrze — `status` to konfiguracja EGZEKWOWANA."""
        p = baza / "perimetr.json"
        p.write_text(json.dumps({"status": {"resources": [f"projects/{n}" for n in numery]}}))
        return p

    def bramka(perimetr, zatwierdzone="", zdarzenie="workflow_dispatch"):
        return sh([sys.executable, "tools/promotion_hold.py", "--root", str(baza),
                   "--policy", "perimeter/policy.yaml", "--perimetr-z-pliku", str(perimetr),
                   "--zatwierdzone", zatwierdzone, "--zdarzenie", zdarzenie, "--kto", "tester"], cwd=ROOT)

    # 1. PREMISA: zwykly apply MUSI przechodzic. Bez tej asercji „bramka dziala" bylo by prawdziwe takze
    #    dla bramki zatrzymujacej kazdy przebieg — czyli dla zepsutej jedynej drogi wdrozenia.
    zapisz(("dry-run", "000000000000"))
    p = bramka(granica())
    check("apply BEZ promocji przechodzi automatem", p.returncode == 0, p.stdout[-300:])

    # 2. Ta sama granica, jedna zmieniona wartosc `stage` — i przebieg ma stanac.
    klucze = zapisz(("enforced", "000000000000"))
    p = bramka(granica())
    check("apply Z promocja ZATRZYMUJE sie bez zatwierdzenia", p.returncode == 1, p.stdout[-300:])
    check("komunikat nazywa czlonka, ktory zostanie odciety", klucze[0] in p.stdout, p.stdout[-300:])

    # 3. Zwolnienie: dokladnie ten klucz, wpisany recznie.
    p = bramka(granica(), zatwierdzone=klucze[0])
    check("zatwierdzenie recznym uruchomieniem PRZEPUSZCZA promocje", p.returncode == 0, p.stdout[-300:])

    # 4. ZGODA „NA WSZYSTKO" NIE JEST WYRAZALNA. To jest sedno konstrukcji: pole nie przyjmuje potwierdzenia,
    #    tylko liste odcinanych. Gdyby przyjmowalo cokolwiek prawdziwego, bramka bylaby przyciskiem.
    for udawana in ("*", "true", "yes", "all"):
        p = bramka(granica(), zatwierdzone=udawana)
        check(f"zgoda-atrapa {udawana!r} NIE zwalnia bramki", p.returncode == 1, p.stdout[-200:])

    # 5. Zatwierdzenie nieaktualne (wskazuje kogos innego niz oczekujacy) tez zatrzymuje.
    p = bramka(granica(), zatwierdzone="example-division-prj-example-inny")
    check("zatwierdzenie wskazujace kogos INNEGO zatrzymuje", p.returncode == 1, p.stdout[-200:])

    # 6. Dwie promocje naraz: podzbior nie wystarcza, rownosc tak. Ta para pilnuje, zeby zgoda na jednego
    #    czlonka nie przepuszczala przy okazji drugiego, ktorego zatwierdzajacy nie widzial.
    klucze2 = zapisz(("enforced", "000000000000"), ("enforced", "111111111111"))
    p = bramka(granica(), zatwierdzone=klucze2[0])
    check("zatwierdzenie PODZBIORU oczekujacych zatrzymuje", p.returncode == 1, p.stdout[-300:])
    p = bramka(granica(), zatwierdzone=" ".join(klucze2))
    check("zatwierdzenie ROWNE oczekujacym przepuszcza", p.returncode == 0, p.stdout[-300:])

    # 7. Czlonek juz egzekwowany = brak promocji. Bez tego kazdy kolejny apply po pierwszej promocji
    #    prosilby o zgode na cos, co juz sie stalo — i bramka zostalaby wylaczona po tygodniu.
    zapisz(("enforced", "000000000000"))
    p = bramka(granica("000000000000"))
    check("ponowny apply nad JUZ egzekwowanym czlonkiem nie prosi o nic", p.returncode == 0, p.stdout[-300:])

    # 8. ASYMETRIA: zdjecie egzekwowania PRZYWRACA ruch, wiec nie jest bramkowane. Bramka w te strone
    #    wydluzalaby kazda awarie o czas szukania czlowieka.
    zapisz(("dry-run", "000000000000"))
    p = bramka(granica("000000000000"))
    check("ZDJECIE egzekwowania (rewert, break-glass) idzie automatem", p.returncode == 0, p.stdout[-300:])

    # 9. Zatwierdzenie ma JEDNO legalne zrodlo. Wpisane na stale w plik workflowa przyszloby ze zdarzeniem
    #    `push` — i wtedy jest zgoda, ktorej nikt nie wyraza w momencie skutku.
    klucze = zapisz(("enforced", "000000000000"))
    p = bramka(granica(), zatwierdzone=klucze[0], zdarzenie="push")
    check("zatwierdzenie przyniesione przez `push` NIE zwalnia (tylko workflow_dispatch)",
          p.returncode == 1, p.stdout[-300:])

    # 10. Perimetr, ktorego jeszcze nie ma (pierwszy apply na swiezej organizacji): pusta konfiguracja
    #     egzekwowana, nie awaria — inaczej bramka zatrzymywalaby wdrozenie idace dokumentowana sciezka.
    pusty = baza / "brak-perimetru.json"
    pusty.write_text("{}")
    zapisz(("dry-run", "000000000000"))
    p = bramka(pusty)
    check("brak perimetru = pusta konfiguracja egzekwowana (bootstrap przechodzi)",
          p.returncode == 0, p.stdout[-300:])
    zapisz(("enforced", "000000000000"))
    p = bramka(pusty)
    check("czlonek `enforced` od zera tez jest promocja (bootstrap staje)", p.returncode == 1, p.stdout[-300:])

    # --- osadzenie w workflowie ----------------------------------------------------------------------
    apply_wf = yaml.safe_load((ROOT / ".github/workflows/apply.yml").read_text())
    wejscia = ((apply_wf.get(True) or apply_wf.get("on"))["workflow_dispatch"] or {}).get("inputs", {})
    check("apply.yml ma pole `promocje` w recznym uruchomieniu", "promocje" in wejscia, str(list(wejscia)))

    kroki_ap = next(j["steps"] for j in apply_wf["jobs"].values()
                    if any("terraform" in str(k.get("run", "")) and " apply " in str(k.get("run", ""))
                           for k in j["steps"]))
    i_bramki = [i for i, k in enumerate(kroki_ap)
                if str(k.get("uses", "")).endswith("/bramka-promocji")]
    check("bramka promocji stoi w jobie APPLIKUJACYM", len(i_bramki) == 1, str(i_bramki))
    if i_bramki:
        # PRZED planem, wiec i przed wzieciem zamka stanu: przebieg wstrzymany nie blokuje niczyjego apply.
        i_plan = next(i for i, k in enumerate(kroki_ap) if "terraform -chdir=terraform plan" in str(k.get("run", "")))
        check("bramka promocji wykonuje sie PRZED planem (i przed zamkiem stanu)",
              i_bramki[0] < i_plan, f"bramka={i_bramki} plan={i_plan}")
        # ZATWIERDZENIE POCHODZI Z WEJSCIA URUCHOMIENIA, nie ze stalej w pliku. Wartosc wpisana na stale
        # bylaby bramka zdejmowana jednym commitem wygladajacym na konfiguracje (runtime lapie to osobno,
        # asercja 9 wyzej — tu pilnujemy, zeby nikt nie musial sie o tym dowiadywac z czerwonego apply).
        podane = str(kroki_ap[i_bramki[0]].get("with", {}).get("zatwierdzone_promocje", ""))
        check("zatwierdzenie idzie z pola uruchomienia, nie ze stalej",
              "inputs.promocje" in podane, podane)

    # ASYMETRIA WOBEC TORU PULL REQUESTA JEST DECYZJA, NIE PRZEOCZENIEM (DEC-17): promujacy pull request ma
    # byc zielony, przejrzany i scalony — zatrzymanie nalezy sie WYKONANIU. Bramka wpieta w `plan.yml`
    # czerwienilaby review promocji, czyli utrudniala dokladnie ten krok, ktory ma byc staranny.
    for tor in ("plan.yml", "validate.yml"):
        tekst = (ROOT / ".github/workflows" / tor).read_text()
        check(f"{tor} NIE wola bramki promocji (pyta o moment, nie o tresc)",
              "bramka-promocji" not in tekst, tor)


def test_boundary_probe() -> None:
    """Sonda blokady — jedyny workflow, ktorego wynik jest ZDANIEM O SWIECIE, a nie o konfiguracji.

    Dlatego jest testowana inaczej niz reszta: nie czytamy, czy w pliku stoja wlasciwe slowa, tylko
    URUCHAMIAMY jej logike werdyktu na spreparowanych wynikach sond. Badany tryb awarii jest jeden i jest
    kosztowny: chroniona usluga z WYLACZONYM API oraz brak roli IAM zwracaja ten SAM `PERMISSION_DENIED`
    co odmowa VPC-SC. Sonda, ktora liczy kod bledu, zamienia awarie srodowiska w dowod dzialania granicy.
    """
    print("\n== sonda blokady (boundary-probe) ==")
    wf = ROOT / ".github/workflows/boundary-probe.yml"
    check("boundary-probe istnieje po rozpakowaniu", wf.exists())
    if not wf.exists():
        return
    tresc = wf.read_text()

    # Sonda ma czytac WYLACZNIE. Prawo zapisu w tym workflow oznaczaloby narzedzie, ktore w trakcie
    # dowodzenia potrafi zmienic to, co dowodzi.
    check("boundary-probe woła tożsamością planu (read-only), nie apply",
          "PLAN_SERVICE_ACCOUNT" in tresc and "APPLY_SERVICE_ACCOUNT" not in tresc)

    # Sonda musi tez powiedziec, W JAKIEJ konfiguracji stoi projekt w chwili pomiaru — odczytany Z API,
    # nie z gita. Git opisuje stan ZAMIERZONY; gdyby apply nie doszedl albo promocja wciagnela wiecej
    # czlonkow niz mowil diff, sonda zmierzylaby prawde, ale nikt by nie wiedzial, o czym ona jest.
    check("boundary-probe czyta stan granicy z API (status i spec), nie z gita",
          "perimeters describe" in tresc and "status" in tresc and "spec" in tresc)

    # Wyciagamy kod werdyktu z pliku i uruchamiamy go na wejsciach, ktorych nigdy nie widzial.
    # `[-1]` — bierzemy OSTATNI heredok python3 tego pliku (werdykt), nie pierwszy (odczyt stanu granicy).
    kod = re.search(r"python3 - <<'PY'[^\n]*\n(.*?)\n\s*PY\n", tresc[tresc.index("- name: sondy"):], re.S)
    check("boundary-probe: da sie wyodrebnic kod werdyktu", kod is not None)
    if not kod:
        return
    kod_werdyktu = textwrap.dedent(kod.group(1))

    def przelot(oczekiwanie: str, sondy: dict) -> tuple[int, str]:
        kat = pathlib.Path(tempfile.mkdtemp(prefix="vpcsc-probe-"))
        (kat / "sondy").mkdir()
        for nazwa, (rc, out) in sondy.items():
            (kat / "sondy" / f"{nazwa}.rc").write_text(str(rc))
            (kat / "sondy" / f"{nazwa}.out").write_text(out)
        (kat / "werdykt.py").write_text(kod_werdyktu)
        p = sh([sys.executable, "werdykt.py"], cwd=kat,
               env={**os.environ, "OCZEKIWANIE": oczekiwanie, "PROJEKT": "prj-example-vertex-dev"})
        return p.returncode, p.stdout + p.stderr

    ODMOWA_VPCSC = ('ERROR: (gcloud.logging.buckets.list) PERMISSION_DENIED: Request is prohibited by '
                    "organization's policy. vpcServiceControlsUniqueIdentifier: AbCdEf123")
    API_WYLACZONE = ('ERROR: PERMISSION_DENIED: Cloud Monitoring API has not been used in project '
                     "000000000000 before or it is disabled.")
    BRAK_ROLI = ('ERROR: PERMISSION_DENIED: The caller does not have permission')

    # 1. Przelot PRZED promocja: wszystko przechodzi -> zielono.
    rc, out = przelot("open", {n: (0, "[]") for n in
                               ("chroniona-z-regula", "chroniona-bez-reguly",
                                "chroniona-inna-usluga", "spoza-granicy")})
    check("boundary-probe: `open` z czterema przelotami -> zgodne", rc == 0, out[-600:])

    # 2. Przelot PO promocji, uczciwy: chronione bez reguly odmowione PRZEZ VPC-SC, kontrole przechodza.
    rc, out = przelot("blocked", {
        "chroniona-z-regula": (0, "[]"),
        "chroniona-bez-reguly": (1, ODMOWA_VPCSC),
        "chroniona-inna-usluga": (1, ODMOWA_VPCSC),
        "spoza-granicy": (0, "[]"),
    })
    check("boundary-probe: `blocked` z odmowa VPC-SC -> zgodne", rc == 0, out[-600:])

    # 3. PULAPKA. Ten sam kod bledu, inna przyczyna: API wylaczone. Sonda MUSI to odrzucic — inaczej
    #    policzylaby awarie srodowiska jako dowod dzialania granicy (dokladnie ten blad zepsul juz raz
    #    eksperyment w tym materiale).
    rc, out = przelot("blocked", {
        "chroniona-z-regula": (0, "[]"),
        "chroniona-bez-reguly": (1, API_WYLACZONE),
        "chroniona-inna-usluga": (1, ODMOWA_VPCSC),
        "spoza-granicy": (0, "[]"),
    })
    check("boundary-probe: wylaczone API NIE jest liczone jako dowod blokady",
          rc != 0 and "API WYLACZONE" in out, out[-600:])

    # 4. Druga postac tej samej pulapki: brak roli IAM.
    rc, out = przelot("blocked", {
        "chroniona-z-regula": (0, "[]"),
        "chroniona-bez-reguly": (1, BRAK_ROLI),
        "chroniona-inna-usluga": (1, ODMOWA_VPCSC),
        "spoza-granicy": (0, "[]"),
    })
    check("boundary-probe: brak roli IAM NIE jest liczony jako dowod blokady",
          rc != 0 and "BRAK ROLI" in out, out[-600:])

    # 5. KONTROLA NEGATYWNA musi miec zeby: gdy po promocji odmawia takze usluga SPOZA granicy, to znaczy,
    #    ze zepsulismy projekt, a nie ze granica dziala. Sonda ma to zglosic, nie przemilczec.
    rc, out = przelot("blocked", {
        "chroniona-z-regula": (0, "[]"),
        "chroniona-bez-reguly": (1, ODMOWA_VPCSC),
        "chroniona-inna-usluga": (1, ODMOWA_VPCSC),
        "spoza-granicy": (1, ODMOWA_VPCSC),
    })
    check("boundary-probe: odmowa uslugi SPOZA granicy lamie przelot (projekt zepsuty, nie granica)",
          rc != 0, out[-600:])

    # 6. KONTROLA POZYTYWNA musi miec zeby: gdy odmowa dotyka takze ruchu DOZWOLONEGO regula ingress,
    #    to nie jest dzialajaca granica, tylko odciety projekt.
    rc, out = przelot("blocked", {
        "chroniona-z-regula": (1, ODMOWA_VPCSC),
        "chroniona-bez-reguly": (1, ODMOWA_VPCSC),
        "chroniona-inna-usluga": (1, ODMOWA_VPCSC),
        "spoza-granicy": (0, "[]"),
    })
    check("boundary-probe: odmowa ruchu DOZWOLONEGO regula lamie przelot",
          rc != 0, out[-600:])


def main() -> int:
    bootstrap()
    test_samodzielnosc()
    test_terraform()
    test_jeden_plik_projektow()
    test_iam_bootstrap()
    test_deny_check()
    test_contract()
    test_kontrakt_dwie_publikacje()
    test_przyklad_repo_dywizji()
    test_kanal_dywizji()
    test_kanal_ticketowy()
    test_monitoring()
    test_alerty()
    test_brownfield()
    test_external_egress_and_guard()
    test_acm_naming()
    test_access_levels_ksztalt()
    test_lint_and_pinning()
    test_rego()
    test_control_plane_lista()
    test_kompletnosc_decyzji()
    test_tools()
    test_preflight()
    test_eksperyment_wyscigu()
    test_workflows()
    test_workflowy_wykonywalne()
    test_bramki_na_sciezce_apply()
    test_bramka_promocji()
    test_boundary_probe()
    test_schemas()

    ok = sum(1 for _, c, _ in results if c)
    total = len(results)
    print(f"\n== wynik: {ok}/{total} ==")
    if ROOT:
        print(f"(katalog testowy: {ROOT})")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
