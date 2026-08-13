#!/usr/bin/env python3
"""Dopisuje wpis czlonka do `perimeter/projects.yaml` z zatwierdzonego ticketu. Uzywany przez kanaly wejscia.

DLACZEGO osobny skrypt, a nie heredoc w workflow: `stage: dry-run` i data przegladu musza byc USTAWIANE
PRZEZ KOD, nie przepisywane z payloadu. Gdyby wnioskodawca mogl podac `stage`, ominalby cala dwustopniowosc
onboardingu jednym polem w formularzu.

Uzycie (patrz .github/workflows/intake.yml):
    python3 tools/render_member.py --division risk --project-id prj-x --project-number 1 \\
        --owner-group grp@example.com --change-ref snow:RITM0000001 --approved-by net@example.com \\
        --profiles-json '[{"name":"vertex-online-serving","params":{...}}]'
"""
import argparse
import datetime
import json
import os
import pathlib
import sys

import projects_file

REVIEW_AFTER_DAYS = 180  # pol roku — wpis bez potwierdzenia wygasa (expiry-sweep otwiera PR offboardingowy)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--division", required=True)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--project-number", required=True)
    ap.add_argument("--owner-group", required=True)
    ap.add_argument("--change-ref", required=True, help="snow:RITM… | pr:ORG/repo#123 | manual:<uzasadnienie>")
    ap.add_argument("--approved-by", required=True)
    ap.add_argument("--profiles-json", required=True)
    ap.add_argument("--today", default=datetime.date.today().isoformat())
    ap.add_argument("--root", default=".", help="korzen repozytorium perimetru (domyslnie biezacy katalog)")
    args = ap.parse_args()

    # WYWOLANIE ZAPISANE, ZEBY DALO SIE JE POWTORZYC NA INNEJ BAZIE. Kanaly wejsciowe przenosza wniosek
    # na galaz domyslna odczytana tuz przed pushem (`tools/swieza_baza.py`) — a gdy w tym oknie zmienil
    # sie takze plik czlonkow, przeniesienie GOTOWEJ kopii skasowaloby cudzy wpis. Wniosek trzeba wtedy
    # wyrenderowac JESZCZE RAZ, na swiezym pliku.
    #
    # ARGUMENTY BIERZEMY Z `args`, NIE Z `sys.argv`, i to nie jest kosmetyka: `--today` ma wartosc
    # DOMYSLNA liczona z zegara, wiec powtorzenie po polnocy dalo by inne `dry_run_since` i `review_by`
    # niz wywolanie, ktore przeszlo bramki. Zapis znormalizowany utrwala to, co realnie zostalo uzyte.
    #
    # Zapis jest sterowany zmienna srodowiskowa, bo poza kanalem wejscia (ręczne wywolanie, testy) nie ma
    # go po co robic — a skrypt, ktory zawsze pisze do pliku obok, jest skryptem z efektem ubocznym.
    zapis_argv = os.environ.get("RENDER_ARGV_ZAPIS")
    if zapis_argv:
        pathlib.Path(zapis_argv).write_text(json.dumps([
            "--division", args.division,
            "--project-id", args.project_id,
            "--project-number", str(args.project_number),
            "--owner-group", args.owner_group,
            "--change-ref", args.change_ref,
            "--approved-by", args.approved_by,
            "--profiles-json", args.profiles_json,
            "--today", args.today,
            "--root", args.root,
        ]), encoding="utf-8")

    today = datetime.date.fromisoformat(args.today)
    member = {
        "schema_version": 1,
        "division": args.division,
        "project_id": args.project_id,
        # str(): numery projektow przekraczaja bezpieczny zakres integerow w czesci parserow YAML.
        "project_number": str(args.project_number),
        "owner_group": args.owner_group,
        "change_ref": args.change_ref,
        "approved_by": args.approved_by,
        # NIE z payloadu — zawsze dry-run. Promocja to osobny PR z czlowiekiem (DEC-4).
        "stage": "dry-run",
        "dry_run_since": today.isoformat(),
        "review_by": (today + datetime.timedelta(days=REVIEW_AFTER_DAYS)).isoformat(),
        "profiles": json.loads(args.profiles_json),
        # `exceptions: []` STALO TU DO DEC-23 i zniknelo razem z polem. Renderer wypisywal je w kazdym
        # wpisie, wiec pole wygladalo na czesc normalnego formatu — a `grep -rn "exceptions" terraform/`
        # dawal zero, czyli nie renderowalo ani jednej reguly. Teraz `additionalProperties: false`
        # w member.schema.json odrzuca wpis, ktory je niesie; regula spoza katalogu wchodzi jako nowy
        # profil, pod CODEOWNERS Security.
    }

    doc = projects_file.wczytaj(args.root)
    wpisy = doc["members"]

    # WPIS O TYM PROJEKCIE JUZ ISTNIEJE = ten projekt jest w perimetrze. Dopisanie drugiego wygladaloby jak
    # onboarding, a byloby przepisaniem cudzego wpisu — w tym CICHYM cofnieciem `stage: enforced` do
    # `dry-run`, bo slownik wyzej zawsze ustawia dry-run. Projekt stracilby realna ochrone pull requestem
    # zatytulowanym „onboard”, przechodzacym bramki (nowy stan `dry-run` nie lamie zadnej reguly promocji)
    # i kwalifikujacym sie do auto-merge'a jako „dodanie do dry-run”.
    #
    # TO JEST TEN SAM NIEZMIENNIK, KTORY PRZY PLIKU-NA-PROJEKT REALIZOWAL `out.exists()` — i to jedyny
    # powod, dla ktorego tamten warunek istnial. Przy jednym wspolnym pliku „plik istnieje” jest prawda
    # ZAWSZE, wiec warunek trzeba bylo przepisac na pytanie o WPIS, a nie o plik. Regula OPA porownujaca
    # dwa wpisy tego nie zastapi: ona odrzuca duplikat, ktory juz powstal, a tutaj odmawiamy jego
    # UTWORZENIA — czyli kanal nie produkuje pull requesta, ktory wyglada na onboarding.
    #
    # PYTAMY O `project_id` I O `project_number` OSOBNO. Literowka w dywizji daje inny klucz wpisu, ale ten
    # sam projekt; pytanie tylko o klucz przepuscilo by taki wniosek. Zmiana profili i promocja ida pull
    # requestem na istniejacym wpisie (docs/3-runbook-promocja-i-break-glass.md).
    istniejacy = projects_file.znajdz(
        wpisy, project_id=args.project_id, project_number=str(args.project_number)
    )
    if istniejacy is not None:
        raise SystemExit(
            f"{projects_file.SCIEZKA}: wpis {projects_file.klucz(istniejacy)} juz opisuje ten projekt "
            f"(project_id: {istniejacy.get('project_id')}, project_number: {istniejacy.get('project_number')}, "
            f"stage: {istniejacy.get('stage', '?')}, change_ref: {istniejacy.get('change_ref', '?')}). "
            "To nie jest onboarding: zmiane profili albo promocje zglos pull requestem na istniejacym wpisie."
        )

    # Duplikaty W PLIKU, ktory zastalismy — sprawdzane PRZED dopisaniem czegokolwiek. Kanal wejsciowy nie
    # ma prawa dokladac wpisu do pliku, ktory juz jest zepsuty: jego pull request wygladalby wtedy na
    # przyczyne czerwonych bramek, a bylby tylko ich swiadkiem.
    problemy = projects_file.duplikaty(wpisy)
    if problemy:
        raise SystemExit(
            f"{projects_file.SCIEZKA} zawiera duplikaty JESZCZE PRZED tym wnioskiem — napraw je najpierw:\n  "
            + "\n  ".join(problemy)
        )

    p = projects_file.dopisz(args.root, member)
    print(f"dopisano {projects_file.klucz(member)} do {p}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except projects_file.BladPliku as e:
        # Blad ksztaltu pliku wspolnego nie jest bledem wniosku — komunikat ma to mowic wprost, inaczej
        # wnioskodawca poprawia swoj formularz w kolko, a zepsuty jest plik po drugiej stronie granicy.
        print(f"BLAD PLIKU CZLONKOW: {e}", file=sys.stderr)
        raise SystemExit(1) from e
