#!/usr/bin/env python3
"""Przenosi zgloszenie kanalu wejsciowego na galaz domyslna odczytana TERAZ — tuz przed pushem galezi.

CO TO NAPRAWIA (zmierzone). Kanal wejsciowy robi checkout galezi domyslnej, buduje z niej galaz
zgloszenia i wypycha ja kilkadziesiat sekund pozniej. Gdy w tym oknie na galaz domyslna wejdzie merge
dotykajacy `.github/workflows/**`, push zostaje ODRZUCONY:

    ! [remote rejected] external/<dywizja>-<projekt> -> external/<dywizja>-<projekt>
      (refusing to allow a GitHub App to create or update workflow
       `.github/workflows/<plik>.yml` without `workflows` permission)

MECHANIZM NIE JEST TAKI, JAK SUGERUJE TEN KOMUNIKAT — i to jest jedyny powod, dla ktorego ten plik ma
nagłowek zamiast jednej linijki `git fetch`. Zgloszenie nie zmienia ZADNEGO workflowa: jego commit
dotyka wylacznie pliku czlonkow (`add-paths` w `create-pull-request`). GitHub porownuje jednak
wypychana galaz z galezia DOMYSLNA, a nie z jej wlasna baza — a galaz zbudowana ze STARSZEGO `main`
niesie STARSZA wersje pliku workflow niz `main`, wiec jej utworzenie wyglada dla tej kontroli na
MODYFIKACJE workflowa. Stad dwa wnioski, ktore latwo przeoczyc:

  * `add-paths` tego NIE zamyka (i nie zamknelo, mimo ze wyglada na dokladnie te obrone): ogranicza
    zawartosc COMMITA, a kontrola patrzy na DRZEWO galezi wobec galezi domyslnej;
  * ponowienie zgloszenia zwykle pomaga, bo druga proba startuje z bazy, ktora juz zawiera tamten
    merge — czyli objaw jest niedeterministyczny i na spokojnym repozytorium nie wystapi nigdy.

DLACZEGO NIE `workflows: write`. Brak tego uprawnienia jest KONTROLA, nie usterka: kanal wejsciowy nie
ma prawa dotykac plikow workflow perimetru i nie ma go dostac. Odmowa GitHuba jest tu POPRAWNA.
Naprawiamy to, ze kanal WYGLADA, jakby chcial.

CO ROBI TEN SKRYPT. Odczytuje galaz domyslna z `origin` i przestawia na nia drzewo robocze, zachowujac
wniosek. Rozroznia przy tym dwa przypadki, bo maja rozne konsekwencje:

  * plik czlonkow NIE ruszyl sie miedzy stara baza a swiezym `main` — wyrenderowany plik jest wtedy
    funkcja tego samego wejscia, wiec jego PRZENIESIENIE daje bajt w bajt to samo, co ponowny render.
    Przenosimy, i nic wiecej nie trzeba.
  * plik czlonkow RUSZYL SIE — czyli w oknie wszedl CUDZY onboarding. Przeniesienie gotowego pliku
    SKASOWALOBY tamten wpis (nasza kopia powstala, zanim tamten istnial), i to bez sladu w diffie
    zgloszenia, bo diff liczy sie wobec nowej bazy. Renderujemy wiec wniosek JESZCZE RAZ, na swiezym
    pliku, TYMI SAMYMI argumentami — a wolajacy MUSI po tym powtorzyc bramki tresci, bo drzewo, ktore
    pojedzie do pull requesta, nie jest juz drzewem, ktore te bramki widzialy. Sygnalem jest output
    `przerenderowano`.

DLACZEGO PONOWNY RENDER JEST BEZPIECZNY. `render_member.py` odmawia dopisania wpisu, ktory juz opisuje
ten projekt (po `project_id` ORAZ po `project_number`). Jesli w oknie wszedl onboarding TEGO SAMEGO
projektu, ponowienie konczy sie odmowa — i to jest wlasciwy wynik: wniosek przestal byc onboardingiem
w trakcie wlasnego przebiegu. Ten skrypt melduje wtedy ODRZUCENIE TRESCI, a nie awarie transportu.

CZEGO TEN SKRYPT NIE ROBI. Nie zamyka okna do zera i nie da sie go zamknac — miedzy odczytem `main`
a pushem zawsze zostaje ulamek sekundy, a kontrola po stronie GitHuba dzieje sie dopiero przy pushu.
Zwezenie jest z kilkudziesieciu sekund do okolo jednej, nie do zera. Dlatego kanal ma DRUGA warstwe:
krok, ktory po nieudanym pushu mowi WPROST, ze to byl wyscig transportu, a nie odrzucenie wniosku —
kolor obu jest identyczny, a wnioskodawca siedzi po drugiej stronie granicy organizacji i widzi
wylacznie ten kolor.

Uzycie (patrz `.github/workflows/intake.yml` i `external-intake.yml`):
    python3 tools/swieza_baza.py --galaz main --baza "$GITHUB_SHA" --argv-render "$RUNNER_TEMP/render-argv.json"

Kody wyjscia (rozlaczne, bo wolajacy ma z nich zbudowac werdykt, a nie sam kolor):
    0 = drzewo stoi na swiezej bazie (przeniesione albo przerenderowane albo baza sie nie ruszyla)
    1 = TRANSPORT: nie udalo sie odczytac albo przestawic bazy — to NIE jest odrzucenie wniosku
    2 = TRESC: ponowny render odrzucil wniosek na swiezym pliku (np. ten projekt wlasnie wszedl inna droga)
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

import projects_file

# Adnotacje GitHuba: przecinek w TYTULE rozdziela wlasciwosci polecenia (`title=…,file=…`), wiec tytul
# z przecinkiem dojezdza do API uciety. Stad tytuly bez przecinkow — to nie jest styl, to skladnia.
TYTUL_TRANSPORT = "PRZENIESIENIE NA SWIEZA BAZE NIE POWIODLO SIE"
TYTUL_TRESC = "WNIOSEK ODRZUCONY PRZEZ BRAMKE TRESCI"


class BladGita(RuntimeError):
    pass


# Korzen repozytorium — ustawiany w `main()` z `--root`. Kazde wywolanie gita idzie przez `-C`, zeby
# skrypt nie zalezal od tego, z ktorego katalogu go zawolano (workflow wola z korzenia, testy nie).
KORZEN = "."


def git(*args, dozwolone=(0,)):
    """Wolanie gita, w ktorym KAZDY kod wyjscia poza wymienionymi jest bledem.

    `git diff --quiet` uzywa kodu 1 jako ODPOWIEDZI („rozni sie"), a kodu 128 jako BLEDU („nie ma
    takiego obiektu") — sklejenie ich w `returncode != 0` czytaloby brak commitu jako „plik sie
    zmienil" i kazaloby renderowac na drzewie, ktorego nikt nie odczytal. Stad jawna lista.
    """
    p = subprocess.run(["git", "-C", KORZEN, *args], text=True, capture_output=True)
    if p.returncode not in dozwolone:
        raise BladGita(f"git {' '.join(args)} -> {p.returncode}\n{p.stdout}{p.stderr}")
    return p


def podsumowanie(*linie: str) -> None:
    """Dopisuje do podsumowania przebiegu. To jest KANAL WERDYKTU dla kogos spoza tego repozytorium."""
    plik = os.environ.get("GITHUB_STEP_SUMMARY")
    if not plik:
        return
    with open(plik, "a", encoding="utf-8") as fh:
        fh.write("\n".join(linie) + "\n")


def output(**pary) -> None:
    plik = os.environ.get("GITHUB_OUTPUT")
    if not plik:
        return
    with open(plik, "a", encoding="utf-8") as fh:
        for k, v in pary.items():
            fh.write(f"{k}={v}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--galaz", required=True, help="galaz domyslna perimetru (czytana z kontekstu przebiegu)")
    ap.add_argument("--baza", required=True, help="commit, na ktorym przebieg zrobil checkout (GITHUB_SHA)")
    ap.add_argument("--argv-render", required=True,
                    help="plik z argumentami `render_member.py` zapisany przez krok renderujacy")
    ap.add_argument("--root", default=".", help="korzen repozytorium perimetru")
    args = ap.parse_args()

    global KORZEN
    KORZEN = args.root

    zdalna = f"refs/remotes/origin/{args.galaz}"
    try:
        # `--depth=1`: checkout kanalu jest plytki, wiec pobieramy sam wierzcholek. Do porownania DRZEW
        # (`git diff A B -- sciezka`) historia nie jest potrzebna — potrzebne sa dwa obiekty commitu.
        # Refspec podany JAWNIE, bo od tego zalezy `refs/remotes/origin/<galaz>`, a to wlasnie ten ref
        # czyta pozniej `create-pull-request` (`git reset --hard origin/<galaz>`).
        git("fetch", "--no-tags", "--depth=1", "origin", f"+refs/heads/{args.galaz}:{zdalna}")
        swiezy = git("rev-parse", zdalna).stdout.strip()
    except BladGita as e:
        print(f"::error title={TYTUL_TRANSPORT}::Nie udalo sie odczytac galezi domyslnej z origin. "
              "To NIE jest odrzucenie wniosku - bramki tresci przeszly.")
        print(e, file=sys.stderr)
        podsumowanie("## ❌ WERDYKT: NIEROZSTRZYGNIETY — nie odczytano galezi domyslnej",
                     "Bramki tresci przeszly. Zawiodl odczyt stanu repozytorium, nie wniosek.")
        return 1

    if swiezy == args.baza:
        # Nic sie nie zmienilo — najczestszy przypadek. Melduje sie mimo to, bo „krok, ktory milczy przy
        # sukcesie" jest nieodrozninalny od kroku, ktory sie nie wykonal.
        print(f"::notice::baza zgloszenia jest aktualna ({swiezy[:12]}) - nic do przeniesienia")
        podsumowanie(f"Baza zgloszenia aktualna: `{swiezy[:12]}` (galaz domyslna nie ruszyla sie "
                     "miedzy startem przebiegu a pushem).")
        output(baza=swiezy, przesunieta="false", przerenderowano="false")
        return 0

    sciezka = pathlib.Path(args.root) / projects_file.SCIEZKA
    try:
        ruszyl_plik_czlonkow = git("diff", "--quiet", args.baza, swiezy, "--", projects_file.SCIEZKA,
                                   dozwolone=(0, 1)).returncode == 1
    except BladGita as e:
        print(f"::error title={TYTUL_TRANSPORT}::Nie udalo sie porownac pliku czlonkow miedzy stara "
              "a swieza baza. To NIE jest odrzucenie wniosku - bramki tresci przeszly.")
        print(e, file=sys.stderr)
        podsumowanie("## ❌ WERDYKT: NIEROZSTRZYGNIETY — nie porownano pliku czlonkow")
        return 1
    wyrenderowany = sciezka.read_text(encoding="utf-8")

    try:
        # `reset --hard` NIE rusza plikow nieśledzonych (pobrany kontrakt, `declarations.json`) — one maja
        # przezyc, bo powtorzenie bramek tresci ich potrzebuje.
        git("reset", "--hard", zdalna)
    except BladGita as e:
        print(f"::error title={TYTUL_TRANSPORT}::Nie udalo sie przestawic drzewa na swieza baze. "
              "To NIE jest odrzucenie wniosku - bramki tresci przeszly.")
        print(e, file=sys.stderr)
        podsumowanie("## ❌ WERDYKT: NIEROZSTRZYGNIETY — nie przestawiono bazy zgloszenia")
        return 1

    if not ruszyl_plik_czlonkow:
        sciezka.write_text(wyrenderowany, encoding="utf-8")
        print(f"::notice::baza przesunieta {args.baza[:12]} -> {swiezy[:12]}; "
              "plik czlonkow bez zmian - wniosek przeniesiony")
        podsumowanie(f"Baza zgloszenia przesunieta z `{args.baza[:12]}` na `{swiezy[:12]}`. "
                     f"`{projects_file.SCIEZKA}` w tym oknie sie nie zmienil, wiec wyrenderowany wniosek "
                     "zostal PRZENIESIONY bez zmian (bajt w bajt to samo, co ponowny render).")
        output(baza=swiezy, przesunieta="true", przerenderowano="false")
        return 0

    # PLIK CZLONKOW SIE RUSZYL — przeniesienie skasowaloby cudzy wpis. Renderujemy od nowa, tymi samymi
    # argumentami (lacznie z `--today`: data wyliczona domyslnie rozjechalaby sie na przelomie doby).
    try:
        argv = json.loads(pathlib.Path(args.argv_render).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"::error title={TYTUL_TRANSPORT}::Brak zapisanych argumentow renderu - nie mam czym "
              "powtorzyc wniosku na swiezym pliku czlonkow.")
        print(e, file=sys.stderr)
        podsumowanie("## ❌ WERDYKT: NIEROZSTRZYGNIETY — brak argumentow renderu")
        return 1

    wynik = subprocess.run([sys.executable, "tools/render_member.py", *argv], text=True,
                           capture_output=True, cwd=args.root)
    print(wynik.stdout, end="")
    print(wynik.stderr, end="", file=sys.stderr)
    if wynik.returncode != 0:
        print(f"::error title={TYTUL_TRESC}::Bramki wykonaly sie i odrzucily TRESC tego zgloszenia na "
              "aktualnym pliku czlonkow. Powtorzenie niczego nie zmieni - poprawka jest po stronie wniosku.")
        podsumowanie("## ❌ WERDYKT: ODRZUCONY — treść zgłoszenia nie przeszła bramki",
                     "",
                     "W czasie tego przebiegu na gałąź domyślną wszedł wpis, z którym ten wniosek jest "
                     "sprzeczny (najczęściej: ten sam projekt wszedł do perimetru inną drogą).")
        return 2

    print(f"::notice::baza przesunieta {args.baza[:12]} -> {swiezy[:12]}; "
          "plik czlonkow ZMIENIONY - wniosek wyrenderowany ponownie")
    podsumowanie(f"Baza zgłoszenia przesunięta z `{args.baza[:12]}` na `{swiezy[:12]}`, a "
                 f"`{projects_file.SCIEZKA}` zmienił się w tym oknie (wszedł czyjś wpis). Wniosek został "
                 "**wyrenderowany ponownie** na świeżym pliku — przeniesienie gotowej kopii skasowałoby "
                 "tamten wpis. Bramki treści lecą jeszcze raz, bo to jest inne drzewo niż to, które je "
                 "przeszło.")
    output(baza=swiezy, przesunieta="true", przerenderowano="true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
