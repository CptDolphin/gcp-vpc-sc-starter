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
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

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
        "contrib/action.yml", "contrib/validate-local.sh", "contrib/README.md",
        ".gitignore", ".pre-commit-config.yaml", ".tool-versions",
        "perimeter/policy.yaml", "perimeter/access-levels/corp.yaml", "perimeter/contributors.yaml",
        "perimeter/members/example-division-prj-example-vertex-dev.yaml",
        "perimeter/profiles/vertex-online-serving.yaml",
        "perimeter/profiles/vertex-batch-training.yaml",
        "perimeter/profiles/corp-user-console-access.yaml",
        "perimeter/profiles/bq-omni-external-read.yaml",
        "policy/onboarding.rego", "policy/onboarding_test.rego",
        "policy/perimeter.rego", "policy/perimeter_test.rego",
        "schemas/member.schema.json", "schemas/policy.schema.json", "schemas/profile.schema.json",
        "schemas/access-level.schema.json",
        "terraform/locals.tf", "terraform/members.tf", "terraform/outputs.tf",
        "terraform/perimeter.tf", "terraform/rules.tf", "terraform/versions.tf",
        "terraform/contract.tf", "terraform/tests/renderer.tftest.hcl", "terraform/monitoring.tf",
        "iam-bootstrap/README.md", "iam-bootstrap/main.tf", "iam-bootstrap/variables.tf",
        "iam-bootstrap/versions.tf", "iam-bootstrap/terraform.tfvars.sample",
        "tools/attribute_budget.py", "tools/collect_declarations.py", "tools/preflight_check.sh",
        "tools/render_member.py", "tools/snow_verify.py", "tools/violations_report.py",
        "tools/bootstrap_github.sh", "docs/access-request.md",
        "tools/check_supported_services.py",
        "tools/perimeter_to_policy.py", "tools/brownfield_import.sh",
        ".tflint.hcl", ".github/dependabot.yml", "tests/README.md",
        "tests/snow-approved.json", "tests/snow-not-approved.json", "tests/snow-self-approved.json",
        "tests/snow-wrong-project.json", "tests/dispatch-example.json",
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

    # Przykładowy członek jest w dry-run, więc konfiguracja EGZEKWOWANA musi być pusta. To pilnuje
    # najważniejszej własności startera: świeże repo nie blokuje nikomu ruchu.
    p = sh(["terraform", f"-chdir={tf}", "console"], input="length(local.ingress_rules_enforced)\n")
    check("swieze repo nie ma zadnej reguly egzekwowanej",
          p.returncode == 0 and p.stdout.strip().splitlines()[-1].strip() == "0", p.stdout + p.stderr[-300:])

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


# --------------------------------------------------------------------- monitoring
def test_monitoring() -> None:
    """Perimetr bez alertu to granica, o której dowiadujesz się od użytkownika."""
    print("\n== monitoring ==")
    body = (ROOT / "terraform/monitoring.tf").read_text()

    # Dwie metryki muszą być ROZŁĄCZNE: enforced page'uje, dry-run informuje. Wspólna metryka oznacza alert
    # odpalający przy normalnej pracy okna obserwacji — czyli alert, który po tygodniu jest ignorowany.
    check("metryka enforced filtruje dryRun=false", 'dryRun=\\"false\\"' in body)
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

    member = (ROOT / "perimeter/members/example-division-prj-example-vertex-dev.yaml").read_text()
    check("przykladowy czlonek uzywa profilu zewnetrznego (sciezka jest TESTOWANA)",
          "bq-omni-external-read" in member and "s3://" in member)

    rules = (ROOT / "terraform/rules.tf").read_text()
    check("external_resources renderowane w OBU konfiguracjach",
          rules.count("external_resources = each.value.external_resources") == 2,
          f"znaleziono {rules.count('external_resources = each.value.external_resources')}")

    # Wzorzec guardu wyciągamy z workflowa, żeby test i CI sprawdzały DOKŁADNIE to samo wyrażenie.
    wf = (ROOT / ".github/workflows/validate.yml").read_text()
    m = re.search(r"grep -rnE '([^']+)' tools \.github/workflows", wf)
    check("guard no-dry-run-commit istnieje w validate.yml", m is not None)
    if not m:
        return
    pattern = m.group(1)

    def guard_hits() -> str:
        found = sh(["grep", "-rnE", pattern, "tools", ".github/workflows"], cwd=ROOT).stdout
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
    uses = []
    for f in list((ROOT / ".github/workflows").glob("*.yml")) + [ROOT / "contrib/action.yml"]:
        # Zakotwiczone na początku linii: `uses:` pojawia się też WEWNĄTRZ wzorca grepa w guardzie CI,
        # a niezakotwiczony wzorzec wyciągał stamtąd fragmenty regexa i zgłaszał je jako nieprzypięte akcje.
        uses += re.findall(r"^\s*-?\s*uses:\s*(\S+)", f.read_text(), re.M)
    third_party = [u for u in uses if not u.startswith("./") and not u.startswith("ORG/")]
    unpinned = [u for u in third_party if not re.search(r"@[0-9a-f]{40}$", u)]
    check("wszystkie akcje third-party przypiete SHA-em", not unpinned, f"bez SHA: {unpinned}")
    check("guard na pinowanie jest w CI", "actions pinned to a SHA" in wf)
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
    for f in sorted((ROOT / "perimeter/members").glob("*.yaml")):
        for prof in yaml.safe_load(f.read_text()).get("profiles", []):
            used |= set(prof.get("params", {}).get("access_levels", []))
    for rule in policy.get("baseline_ingress", []):
        used |= set(rule.get("access_levels", []))
    check("poziomy uzywane w members/baseline istnieja w katalogu", used <= known, f"brakuje: {sorted(used - known)}")


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


# --------------------------------------------------------------------- narzedzia
def test_tools() -> None:
    print("\n== narzedzia ==")
    decl = (ROOT / "declarations.json").read_text()

    p = sh([sys.executable, "tools/attribute_budget.py", "--input", "declarations.json", "--format", "json"], cwd=ROOT)
    check("attribute_budget.py liczy budzet", p.returncode == 0, p.stderr[-400:])
    if p.returncode == 0:
        doc = json.loads(p.stdout)
        check("budzet: swieze repo daleko od limitu", doc["worst_pct"] < 5, json.dumps(doc)[:300])

    # NEGATYW: sztucznie zawyżone zużycie musi przekroczyć próg i zwrócić kod błędu.
    over = json.loads(decl)
    over["policy"]["attribute_budget"]["limit_per_config"] = 10
    (ROOT / "over-budget.json").write_text(json.dumps(over))
    p = sh([sys.executable, "tools/attribute_budget.py", "--input", "over-budget.json"], cwd=ROOT)
    check("attribute_budget.py PADA po przekroczeniu progu", p.returncode == 1, p.stdout[-300:])

    # render_member.py MUSI wymuszać dry-run niezależnie od tego, co przyszło w payloadzie.
    p = sh([sys.executable, "tools/render_member.py", "--division", "x", "--project-id", "prj-x-test",
            "--project-number", "123456789012", "--owner-group", "g@example.com",
            "--change-ref", "snow:RITM0000009", "--approved-by", "n@example.com",
            "--profiles-json", '[{"name":"vertex-online-serving","params":{}}]',
            "--today", "2026-07-28", "--out", "rendered.yaml"], cwd=ROOT)
    rendered = (ROOT / "rendered.yaml").read_text() if (ROOT / "rendered.yaml").exists() else ""
    check("render_member.py wymusza stage: dry-run", p.returncode == 0 and "stage: dry-run" in rendered,
          p.stderr[-300:] + rendered[:200])
    check("render_member.py ustawia date przegladu", "review_by: '2027-01-24'" in rendered or "review_by: 2027-01-24" in rendered,
          rendered[:300])

    # NEGATYW: powtorne zgloszenie tego samego projektu NIE MOZE nadpisac istniejacego wpisu. Gdyby moglo,
    # czlonek `enforced` wracalby do `dry-run` (render zawsze ustawia dry-run) — projekt tracilby ochrone
    # PR-em wygladajacym na onboarding. Regula OPA tego nie zlapie: porownuje dwa PLIKI, a tu plik jest ten sam.
    (ROOT / "istniejacy.yaml").write_text("division: x\nproject_id: prj-x-test\nstage: enforced\n")
    p = sh([sys.executable, "tools/render_member.py", "--division", "x", "--project-id", "prj-x-test",
            "--project-number", "123456789012", "--owner-group", "g@example.com",
            "--change-ref", "snow:RITM0000009", "--approved-by", "n@example.com",
            "--profiles-json", '[{"name":"vertex-online-serving","params":{}}]',
            "--today", "2026-07-28", "--out", "istniejacy.yaml"], cwd=ROOT)
    zachowany = (ROOT / "istniejacy.yaml").read_text()
    check("render_member.py ODRZUCA nadpisanie istniejacego czlonka", p.returncode != 0,
          p.stdout + p.stderr)
    check("render_member.py NIE degraduje enforced do dry-run", "stage: enforced" in zachowany, zachowany[:200])

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
# Atrapa `gcloud`: udaje ZDROWY projekt (istnieje, numer sie zgadza, PGA i DNS w porzadku), zeby jedyna
# zmienna w tescie byla odpowiedz o TOZSAMOSC. Lista kont istniejacych przychodzi zmienna srodowiskowa.
GCLOUD_ATRAPA = """#!/usr/bin/env bash
case "$*" in
  "projects describe "*) echo "123456789012" ;;
  *"service-accounts describe "*)
    for arg in "$@"; do case " $STUB_SA_OK " in *" $arg "*) exit 0 ;; esac; done
    exit 1 ;;
  *"perimeters list"*) echo "[]" ;;
  *"managed-zones list"*) printf 'googleapis.com.\\nnotebooks.googleusercontent.com.\\n' ;;
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


# --------------------------------------------------------------------- workflows
def test_workflows() -> None:
    print("\n== workflows ==")
    wf = sorted((ROOT / ".github/workflows").glob("*.yml"))
    check("dziesiec workflow po rozpakowaniu", len(wf) == 10, str([f.name for f in wf]))

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

    ext = (ROOT / ".github/workflows/external-intake.yml").read_text()
    # Kanał zewnętrzny ma dwa niezbywalne zabezpieczenia: change_ref musi wskazywać repozytorium, które
    # NAPRAWDĘ wysłało dispatch, a stage jest nadpisywany na dry-run niezależnie od treści payloadu.
    check("external-intake: change_ref sprawdzany wobec repozytorium zgłaszającego",
          'ref.startswith(f"pr:{source}#")' in ext)
    check("external-intake: stage wymuszany na dry-run", 'member["stage"] = "dry-run"' in ext)
    # Trzecie zabezpieczenie: istniejący wpis nie może zostać nadpisany. Sprawdzamy też KOLEJNOŚĆ — wymuszenie
    # dry-run po sprawdzeniu istnienia jest bezpieczne, przed nim byłoby cichą degradacją członka `enforced`.
    check("external-intake: nie nadpisuje istniejacego czlonka",
          "if out.exists():" in ext and ext.index("if out.exists():") < ext.index('member["stage"] = "dry-run"'))

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
        if "id-token: write" in body:
            # Warunek jest o TOŻSAMOŚCI, nie o wersji akcji: sprawdzamy, że workflow uwierzytelnia się przez
            # `auth` z `workload_identity_provider`. Wersja jest przypięta SHA-em i będzie się zmieniać
            # (Dependabot), więc wpisanie tu `@v2` robiło z tego testu detektor aktualizacji, nie bramkę.
            uses_auth = re.search(r"uses:\s*google-github-actions/auth@", body) is not None
            check(f"{f.name}: uzywa WIF (bez kluczy SA)",
                  uses_auth and "workload_identity_provider:" in body)
    joined = "\n".join(f.read_text() for f in wf)
    check("zaden workflow nie zawiera klucza SA ani hasla",
          "private_key" not in joined and "credentials_json" not in joined)


# --------------------------------------------------------------------- schematy (opcjonalnie)
def test_schemas() -> None:
    print("\n== json schema (opcjonalnie) ==")
    if not have("check-jsonschema"):
        print("  SKIP  check-jsonschema niedostepny lokalnie (CI instaluje go w validate.yml)")
        return
    pairs = [("schemas/policy.schema.json", ["perimeter/policy.yaml"]),
             ("schemas/profile.schema.json", sorted(str(p.relative_to(ROOT)) for p in (ROOT / "perimeter/profiles").glob("*.yaml"))),
             ("schemas/member.schema.json", sorted(str(p.relative_to(ROOT)) for p in (ROOT / "perimeter/members").glob("*.yaml"))),
             ("schemas/access-level.schema.json", sorted(str(p.relative_to(ROOT)) for p in (ROOT / "perimeter/access-levels").glob("*.yaml")))]
    for schema, files in pairs:
        p = sh(["check-jsonschema", "--schemafile", schema, *files], cwd=ROOT)
        check(f"schema {pathlib.Path(schema).stem} akceptuje przyklady", p.returncode == 0, p.stdout[-500:])

    # Furtka `control_plane_exception` musi przejść PRZEZ SCHEMĘ, bo validate.yml sprawdza schematy ZANIM
    # uruchomi reguły OPA (`additionalProperties: false` odrzuciłoby ją wcześniej). Gdyby jej tam brakło,
    # jedyną drogą przy realnej potrzebie byłoby usunięcie projektu z control_plane_projects — czyli
    # rozbrojenie bramki dla wszystkich członków naraz.
    czlonek = yaml.safe_load((ROOT / "perimeter/members/example-division-prj-example-vertex-dev.yaml").read_text())
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


def main() -> int:
    bootstrap()
    test_samodzielnosc()
    test_terraform()
    test_iam_bootstrap()
    test_contract()
    test_kontrakt_dwie_publikacje()
    test_przyklad_repo_dywizji()
    test_monitoring()
    test_brownfield()
    test_external_egress_and_guard()
    test_acm_naming()
    test_lint_and_pinning()
    test_rego()
    test_tools()
    test_preflight()
    test_eksperyment_wyscigu()
    test_workflows()
    test_schemas()

    ok = sum(1 for _, c, _ in results if c)
    total = len(results)
    print(f"\n== wynik: {ok}/{total} ==")
    if ROOT:
        print(f"(katalog testowy: {ROOT})")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
