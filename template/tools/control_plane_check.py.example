#!/usr/bin/env python3
"""Czy `control_plane_projects` opisuje miejsce, w którym maszyneria perimetru NAPRAWDĘ leży.

DLACZEGO TO ISTNIEJE. Bramka OPA w `policy/onboarding.rego` odrzuca członka wskazującego projekt Z TEJ
LISTY. Lista jest deklaracją — pisze ją człowiek i do dziś nikt jej z niczym nie konfrontował. Projekt
płaszczyzny sterowania, którego na niej NIE MA, przechodzi przez tamtą bramkę jak każdy inny wniosek:
drugi bucket stanu, osobny projekt monitoringu, backend przeniesiony jedną linijką w `versions.tf`.
Bramka wygląda wtedy na uzbrojoną i chroni pusty zbiór, a wraca przez nią jedyny tryb awarii tego
repozytorium, którego `git revert` NIE COFA (konto apply odcięte od własnego stanu — patrz nagłówek
sekcji `control_plane_projects` w `perimeter/policy.yaml`).

To jest ta sama klasa błędu, co bramka OPA na planie, która przez cały czas czytała nieistniejący plik:
zielono, bo nie miała czego odrzucić. Deklaracja bez konfrontacji z rzeczywistością nie jest kontrolą.

DWA TRYBY, BO POŚWIADCZENIA SĄ W JEDNYM MIEJSCU PIPELINE'U:

  offline (domyślny, `validate.yml`) — spójność deklaracji MIĘDZY PLIKAMI repozytorium. Zero chmury,
      więc szybki feedback na pull requeście zostaje szybki.
  --live (`plan.yml`)                — konfrontacja z API: do jakiego PROJEKTU należy bucket, w którym
      naprawdę leży stan Terraform. To jest jedyne sprawdzenie, które czyta rzeczywistość, a nie kolejny
      plik napisany przez tego samego człowieka co lista.

CZEGO ŚWIADOMIE NIE POKRYWAMY (żeby zielony wynik nie znaczył więcej, niż znaczy):

  * PROJEKT BUCKETA KONTRAKTÓW. Tożsamość `plan` ma na nim wyłącznie `objectViewer` zawężony prefiksem —
    `storage.buckets.get` do niego NIE NALEŻY. Sprawdzenie wymagałoby poszerzenia praw konta CI na
    buckecie, którego utrata jest odwracalna zwykłym `git revert` + apply. Bramka nie jest warta
    poszerzania tożsamości, którą sama ma chronić.
  * `state_prefix`. Rozjazd prefiksu ogłasza się sam: pierwszy `plan` pada na 403 przy odczycie stanu.
    Tryby awarii, które krzyczą, nie potrzebują bramki — potrzebują ich te, które milczą.

Użycie (patrz `.github/workflows/validate.yml` i `plan.yml`):
    python3 tools/control_plane_check.py
    python3 tools/control_plane_check.py --live
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

import yaml

# Placeholder w rozpakowanym starterze (`<MONITORING_PROJECT>`) znaczy „jeszcze nie skonfigurowane", a nie
# „skonfigurowane błędnie". Offline puszczamy go dalej z adnotacją; w trybie `--live` jest BŁĘDEM — tam
# istnieją poświadczenia, czyli repozytorium jest wdrożone i placeholder oznacza konfigurację niedokończoną.
PLACEHOLDER = re.compile(r"^<[A-Z0-9_]+>$")


def backend_bucket(sciezka: pathlib.Path) -> str | None:
    """Nazwa bucketa z bloku `backend "gcs"`. `None`, gdy bloku albo pola nie ma.

    Czytamy TEKST, a nie stan czy konfigurację Terraforma, bo konfiguracja backendu jest jedyną częścią
    HCL, której sam Terraform nie udostępnia z poziomu wyrażeń — `contract.tf` ma z tego powodu wpisaną
    nazwę bucketa stanu drugi raz, w `policy.yaml`. Ta funkcja istnieje po to, żeby te dwa miejsca nie
    mogły się rozjechać w ciszy.
    """
    if not sciezka.exists():
        return None
    tekst = sciezka.read_text()
    m = re.search(r'backend\s+"gcs"\s*\{(.*?)\}', tekst, re.DOTALL)
    if not m:
        return None
    b = re.search(r'^\s*bucket\s*=\s*"([^"]+)"', m.group(1), re.MULTILINE)
    return b.group(1) if b else None


def tfvars(sciezka: pathlib.Path) -> dict:
    """Wartości `klucz = "wartosc"` z pliku tfvars. Linie zakomentowane pomijamy — to są DOMYŚLNE
    wartości opisane w komentarzu, a nie deklaracje tego wdrożenia."""
    if not sciezka.exists():
        return {}
    out = {}
    for linia in sciezka.read_text().splitlines():
        if linia.lstrip().startswith("#"):
            continue
        m = re.match(r'\s*([a-z_]+)\s*=\s*"([^"]*)"', linia)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def numer_projektu_bucketa(bucket: str) -> str:
    """Numer projektu, do którego należy bucket — z ŻYWEGO API.

    `--raw` jest tu konieczne, nie kosmetyczne: bez niego `gcloud storage buckets describe` zwraca własny,
    znormalizowany kształt zasobu, w którym pola `projectNumber` NIE MA W OGÓLE. Bramka czytałaby wtedy
    `None` i albo padała zawsze, albo (gorzej) pomijała sprawdzenie jako „nieustalone".
    """
    p = subprocess.run(
        ["gcloud", "storage", "buckets", "describe", f"gs://{bucket}", "--raw", "--format=json"],
        capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"gcloud storage buckets describe gs://{bucket} zwrocilo {p.returncode}: "
                 f"{p.stderr.strip()[:300]}")
    numer = (json.loads(p.stdout or "{}") or {}).get("projectNumber")
    if not numer:
        sys.exit(f"API nie podalo projectNumber dla gs://{bucket} — bez tego nie da sie stwierdzic, "
                 f"czy projekt stanu jest na liscie control_plane_projects")
    return str(numer)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="perimeter/policy.yaml")
    ap.add_argument("--versions", default="terraform/versions.tf", help="plik z blokiem backend")
    ap.add_argument("--tfvars", default="iam-bootstrap/terraform.tfvars",
                    help="wartosci stacku tozsamosci — sprawdzane, gdy plik istnieje")
    ap.add_argument("--live", action="store_true",
                    help="dodatkowo zapytaj API, do jakiego projektu nalezy bucket stanu")
    args = ap.parse_args()

    polityka = yaml.safe_load(pathlib.Path(args.policy).read_text())
    lista = list(polityka.get("control_plane_projects") or [])
    kontrakt = polityka.get("contract") or {}
    problemy: list[str] = []
    zrobione: list[str] = []
    pominiete: list[str] = []

    def na_liscie(wartosc: str) -> bool:
        return any(str(wpis) == str(wartosc) for wpis in lista)

    # --- 1. bucket stanu: HCL kontra policy.yaml --------------------------------------------------
    # Sprawdzenie ŻYWE niżej pyta o bucket wzięty z `contract.state_bucket`, bo tylko ta nazwa jest
    # maszynowo czytelna. Gdyby rozjechała się z backendem, bramka pytałaby o projekt CUDZEGO bucketa
    # i meldowała zielono o stanie, którego nawet nie dotknęła.
    z_backendu = backend_bucket(pathlib.Path(args.versions))
    zadeklarowany = kontrakt.get("state_bucket")
    if z_backendu is None:
        problemy.append(
            f"{args.versions}: nie znalazlem `bucket` w bloku backend \"gcs\" — bez tego nie da sie "
            f"potwierdzic, ze sprawdzamy bucket, w ktorym naprawde lezy stan")
    elif not zadeklarowany:
        problemy.append(
            f"{args.policy}: brak `contract.state_bucket`, a backend wskazuje {z_backendu!r} — "
            f"wpisz te sama nazwe, inaczej ani guard kontraktu, ani ta bramka nie wiedza, co jest stanem")
    elif z_backendu != zadeklarowany:
        problemy.append(
            f"bucket stanu rozjechany: backend w {args.versions} to {z_backendu!r}, a "
            f"{args.policy} `contract.state_bucket` to {zadeklarowany!r} — jedna z tych wartosci opisuje "
            f"cudzy bucket; zrownaj je, zanim ktokolwiek zaufa bramce plaszczyzny sterowania")
    else:
        zrobione.append(f"bucket stanu zgodny w {args.versions} i {args.policy}: {z_backendu}")

    # --- 2. monitoring: projekt zadeklarowany W TEJ POLITYCE musi byc na liscie -------------------
    # Sekcja `monitoring` sama nazywa projekt plaszczyzny sterowania. Jesli go na liscie nie ma, to
    # `policy.yaml` przeczy sam sobie w dwoch sekcjach oddalonych o 150 linii — a bramka OPA przepusci
    # wniosek o wciagniecie wlasnego monitoringu perimetru.
    monitoring = (polityka.get("monitoring") or {}).get("project_id")
    if not monitoring:
        pominiete.append("monitoring.project_id — sekcja `monitoring` wylaczona")
    elif PLACEHOLDER.match(str(monitoring)):
        if args.live:
            problemy.append(
                f"{args.policy}: monitoring.project_id to nadal placeholder {monitoring!r}, a bramka "
                f"jedzie z poswiadczeniami — repozytorium jest wdrozone z niedokonczona konfiguracja")
        else:
            pominiete.append(f"monitoring.project_id — placeholder {monitoring!r} (nierozpakowany starter)")
    elif not na_liscie(monitoring):
        problemy.append(
            f"{args.policy}: monitoring.project_id = {monitoring!r} NIE JEST na liscie "
            f"control_plane_projects — to projekt plaszczyzny sterowania nazwany w tym samym pliku, "
            f"a bramka onboardingu go nie chroni; dopisz go do listy")
    else:
        zrobione.append(f"monitoring.project_id na liscie: {monitoring}")

    # --- 3. stack tozsamosci: bucket i projekty, ktore stack realnie obsluguje --------------------
    # `iam-bootstrap/terraform.tfvars` jest PIERWSZYM miejscem, w ktorym pojawia sie drugi projekt
    # plaszczyzny sterowania (osobny monitoring, przeniesiona tozsamosc). Gdy plik nie istnieje (swiezy
    # starter), mowimy o tym wprost zamiast milczec — pominiecie policzone jako pominiecie, nie jako OK.
    p_tfvars = pathlib.Path(args.tfvars)
    if not p_tfvars.exists():
        pominiete.append(f"{args.tfvars} — pliku nie ma (stack tozsamosci jeszcze nie wypelniony)")
    else:
        v = tfvars(p_tfvars)
        for pole in ("identity_project_id", "monitoring_project_id"):
            wartosc = v.get(pole)
            if not wartosc:
                continue
            if na_liscie(wartosc):
                zrobione.append(f"{args.tfvars} {pole} na liscie: {wartosc}")
            else:
                problemy.append(
                    f"{args.tfvars}: {pole} = {wartosc!r} NIE JEST na liscie control_plane_projects — "
                    f"w tym projekcie stoi maszyneria perimetru (konta, pula WIF albo metryki), wiec "
                    f"jego wciagniecie do konfiguracji egzekwowanej odcina pipeline od siebie samego")
        for pole, oczekiwane, skad in (("state_bucket", kontrakt.get("state_bucket"), "contract.state_bucket"),
                                       ("contracts_bucket", kontrakt.get("bucket"), "contract.bucket")):
            wartosc = v.get(pole)
            if wartosc and oczekiwane and wartosc != oczekiwane:
                problemy.append(
                    f"{args.tfvars}: {pole} = {wartosc!r}, a {args.policy} {skad} = {oczekiwane!r} — "
                    f"uprawnienia nadaje sie na jednym buckecie, a uzywa drugiego")

    # --- 4. ZYWE: do jakiego projektu nalezy bucket stanu -----------------------------------------
    if not args.live:
        pominiete.append("projekt bucketa stanu z API — tryb offline (to sprawdza `--live` w plan.yml)")
    elif not zadeklarowany or z_backendu != zadeklarowany:
        problemy.append(
            "nie pytam API o projekt bucketa stanu, bo nazwa bucketa jest niepewna (patrz blad wyzej) — "
            "odpowiedz dotyczylaby cudzego zasobu")
    elif PLACEHOLDER.match(str(zadeklarowany)):
        problemy.append(
            f"nazwa bucketa stanu to nadal placeholder {zadeklarowany!r}, a bramka jedzie "
            f"z poswiadczeniami — repozytorium jest wdrozone z niedokonczona konfiguracja")
    else:
        numer = numer_projektu_bucketa(zadeklarowany)
        if na_liscie(numer):
            zrobione.append(f"projekt bucketa stanu gs://{zadeklarowany} (numer {numer}) jest na liscie")
        else:
            problemy.append(
                f"bucket stanu gs://{zadeklarowany} nalezy do projektu o numerze {numer}, ktorego NIE MA "
                f"na liscie control_plane_projects — dopisz \"{numer}\" (w cudzyslowach, bo YAML bez nich "
                f"da liczbe, a porownanie z project_number nigdy nie trafi). Bramka porownuje NUMER, bo "
                f"tyle o wlascicielu bucketa mowi API; identyfikator projektu zostaw obok, dla czytelnika")

    for z in zrobione:
        print(f"  OK        {z}")
    for z in pominiete:
        print(f"  POMINIETE {z}")
    for z in problemy:
        print(f"  BLAD      {z}")
    if problemy:
        # Bez tego stderr wyprzedza stdout i podsumowanie ląduje NAD lista bledow, ktora podsumowuje —
        # w logu CI wyglada to jak komunikat o czyms innym.
        sys.stdout.flush()
        print(f"\nNIEZALICZONE ({len(problemy)}): lista control_plane_projects nie opisuje tego, gdzie lezy "
              f"maszyneria perimetru. Bramka onboardingu chroni wtedy zbior, ktory tylko wyglada na pelny.",
              file=sys.stderr)
        return 1
    print(f"\nOK: {len(zrobione)} sprawdzen zgodnych, {len(pominiete)} pominietych "
          f"({'tryb zywy' if args.live else 'tryb offline'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
