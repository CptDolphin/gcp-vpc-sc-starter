#!/usr/bin/env python3
"""Promuje ISTNIEJACEGO czlonka `dry-run` -> `enforced` i zapisuje, KTO to podpisal i NA JAKIEJ PODSTAWIE.

LUSTRO `render_member.py`. Tamten DOPISUJE czlonka i zawsze ustawia `stage: dry-run`, bo etap nie moze
pochodzic od wnioskodawcy (DEC-4). Ten jest jedynym kanalem, ktory pisze `enforced` — i z tego samego
powodu jest tak samo waski: edytuje JEDEN wpis znaleziony po kluczu i zmienia w nim CZTERY POLA. Nie
tworzy wpisu, nie rusza dat, nie przepisuje profili.

DIFF, KTORY Z TEGO WYCHODZI:

    -  change_ref: snow:RITM0000123          <- wniosek ONBOARDINGOWY
    -  approved_by: net-approver@example.com
    +  change_ref: snow:RITM0000456          <- wniosek PROMOCYJNY
    +  approved_by: sec-approver@example.com
    -  stage: dry-run
    +  stage: enforced
    +  unmeasured_peers_ack: []

CZTERY POLA, A NIE DWA — I TO JEST CALA TRESC DEC-58. Pola `change_ref` i `approved_by` odpowiadaja na
pytanie „na jakiej podstawie ta konfiguracja istnieje DZIS i kogo pytac, gdy dowod trzeba odtworzyc"
(`schemas/member.schema.json`). Od chwili promocji podstawa jest wniosek promocyjny, a nie ten, ktorym
projekt wszedl do dry-run. Zostawienie tam wartosci onboardingowych zapisuje, ze pod JEDYNA zmiana w tym
repozytorium, ktorej skutkiem jest odmowa ruchu, podpisal sie ktos, kto podpisal wylacznie wejscie do
obserwacji — czyli decyzje bez autora. Referencja onboardingowa nie ginie: zostaje w historii pliku
i w pull requescie, ktory ja wpisal.

CZEGO TO NARZEDZIE NIE DOTYKA I DLACZEGO:

  `dry_run_since`  zegar okna obserwacji. Bramka promocji liczy dni wlasnie od tego pola, wiec narzedzie,
                   ktore je „odswieza", kasuje dowod, na ktory samo sie powoluje (runbook §A krok 4:
                   „to pole jest data wejscia do dry-run, nie parametrem do dostrojenia"). Przestawia je
                   WYLACZNIE break-glass i tylko on ma do tego prawo.
  `review_by`      data przegladu czlonkostwa, nie tej decyzji. Promocja nie jest przegladem.
  `profiles`,      zmiana profilu albo wlasciciela to inny wniosek i inne bramki. Kanal, ktory przy
  `owner_group`,   okazji promocji potrafi przepisac regule, jest kanalem zmiany regul.
  `division`,
  `project_*`

CZEGO TO NARZEDZIE NIE ROZSTRZYGA — i dlaczego to nie jest luka. Nie pyta, czy promocja jest DOZWOLONA:
dlugosc okna dry-run, istnienie raportu naruszen i zero naruszen w oknie sa regulami OPA
(`policy/onboarding.rego` §promocja do enforced), a moment SKUTKU trzyma `tools/promotion_hold.py` na
apply (DEC-17). To narzedzie produkuje material, ktory tamte bramki oceniaja. Odmowy nizej sa wylacznie
te, ktorych PO ZAPISIE nie widac juz jako bledu: pomylony klucz, wpis juz egzekwowany, plik zepsuty przed
wnioskiem, potwierdzenie wskazujace nikogo, referencja przepisana z onboardingu. Reszte niech mowia
bramki, tu nie dublujemy ich werdyktu.

Uzycie (klucz czlonka to `<dywizja>-<project_id>`):
    python3 tools/promote_member.py --member example-division-prj-example-vertex-dev \\
        --change-ref snow:RITM0000456 --approved-by sec-approver@example.com \\
        --peer example-division-prj-example-vertex-prod
    python3 tools/promote_member.py --member example-division-prj-example-vertex-dev \\
        --change-ref snow:RITM0000456 --approved-by sec-approver@example.com --bez-rowiesnikow
"""
import argparse
import pathlib
import sys

import projects_file

# Ile kluczy wchodzi do komunikatu odmowy. Ta sama liczba i ten sam powod co `prog_probki_rowiesnikow`
# w `policy/onboarding.rego`: przy kilkuset czlonkach pelna lista jest sciana tekstu, przez ktora nie
# widac zdania, ktore ma cos zmienic.
PROG_PROBKI = 5


def probka(klucze) -> str:
    """Posortowana probka kluczy w postaci nadajacej sie do komunikatu dla czlowieka."""
    klucze = sorted(klucze)
    if len(klucze) <= PROG_PROBKI:
        return ", ".join(klucze) or "(brak)"
    return f"{', '.join(klucze[:PROG_PROBKI])} …i {len(klucze) - PROG_PROBKI} wiecej"


def skrot(tekst, limit: int = 80) -> str:
    """Wartosc pola do komunikatu. `change_ref` bywa AKAPITEM — wariant `manual:` wymaga uzasadnienia
    i miewa kilkaset znakow — a odmowa, ktorej nie da sie ogarnac jednym spojrzeniem, przestaje byc
    czytana. Pelna tresc jest w pliku, tutaj wystarczy tyle, zeby rozpoznac WPIS."""
    tekst = str(tekst)
    return tekst if len(tekst) <= limit else tekst[:limit - 1] + "…"


def promowany(wpis: dict, potwierdzenie: list, change_ref: str, approved_by: str) -> dict:
    """Kopia wpisu po promocji: podmienione pola decyzji, `stage`, i `unmeasured_peers_ack` TUZ ZA
    `dry_run_since` — tam, gdzie stawia je schemat.

    DLACZEGO POZYCJA POLA W OGOLE MA ZNACZENIE. `yaml.safe_dump(sort_keys=False)` zapisuje klucze
    w kolejnosci wstawienia, wiec pole dopisane do slownika „na koncu" wyladowaloby ZA blokiem `profiles`,
    czyli w drugim hunku diffa, kilkanascie linii od zmienionego `stage`. Recenzent promocji ma zobaczyc
    JEDNA zmiane w jednym miejscu — dwie zmiany, ktore trzeba ze soba skojarzyc, to juz jest praca, ktorej
    sie nie wykonuje. Kolejnosc `dry_run_since` -> `unmeasured_peers_ack` -> `review_by` jest przy okazji
    dokladnie ta, ktora deklaruje `schemas/member.schema.json`.

    Podmiana pol decyzji NIE zmienia ich pozycji: `change_ref` i `approved_by` stoja we wpisie PRZED
    `stage`, wiec caly wynik nadal miesci sie w jednym hunku diffa razem ze zmienionym etapem.
    """
    # Co ta promocja ZAPISUJE — jeden slownik, z ktorego korzysta i podmiana, i fallback nizej. Dwie
    # listy tych samych pol rozjechalyby sie przy pierwszym dolozonym polu, a rozjazd znaczylby „pole
    # ustawione przy wpisie kompletnym, zgubione przy niekompletnym" — czyli roznice widoczna wylacznie
    # w tym jednym przypadku, ktorego nikt nie testuje.
    decyzja = {"change_ref": change_ref, "approved_by": approved_by, "stage": "enforced"}

    nowy = {}
    for k, v in wpis.items():
        if k == "unmeasured_peers_ack":
            continue  # pole juz bylo — o pozycji decyduje petla, o wartosci argument
        nowy[k] = decyzja.get(k, v)
        if k == "dry_run_since":
            nowy["unmeasured_peers_ack"] = potwierdzenie
    # Wpis bez `dry_run_since` nie przejdzie schematu (`required`), ale odmawiac tutaj nie ma po co:
    # pole musi gdzies wyladowac, a o brakujacej dacie schemat powie czytelniej niz to narzedzie.
    nowy.setdefault("unmeasured_peers_ack", potwierdzenie)
    # Tak samo dla pol decyzji: wpis, ktory ich nie ma, jest niezgodny ze schematem — ale promocja ma je
    # USTAWIC, a nie zgubic dlatego, ze poprzednik ich nie mial. Cichy brak `approved_by` przy
    # `stage: enforced` to dokladnie ten stan, ktorego zakazuje DEC-58.
    for k, v in decyzja.items():
        nowy.setdefault(k, v)
    return nowy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--member", required=True, metavar="KLUCZ",
                    help="klucz czlonka `<dywizja>-<project_id>` — ten sam, ktorym posluguje sie bramka "
                         "promocji i pole `unmeasured_peers_ack`")

    # PODSTAWA I PODPIS TEJ DECYZJI, nie tamtej. Oba pola sa WYMAGANE i celowo nie maja wartosci
    # domyslnej „zostaw, co bylo": domysl przepisywalby autoryzacje onboardingu na zmiane, ktora odcina
    # ruch, i robilby to po cichu — czyli dokladnie to, przed czym stoi DEC-58. Nazwy flag sa te same,
    # co w `render_member.py`, zeby oba kanaly wolalo sie tak samo.
    ap.add_argument("--change-ref", required=True,
                    help="wniosek PROMOCYJNY: snow:RITM… | pr:ORG/repo#123 | manual:<uzasadnienie>. "
                         "NIE ten sam, ktorym projekt wszedl do dry-run")
    ap.add_argument("--approved-by", required=True,
                    help="kto zatwierdzil PROMOCJE — podpis pod oswiadczeniem `unmeasured_peers_ack`")

    # POTWIERDZENIE MA BYC WYPOWIEDZIANE, NIE WYWNIOSKOWANE Z MILCZENIA. `--peer` z domyslna pusta lista
    # znaczyloby, ze pominiecie flagi produkuje OSWIADCZENIE „z zadnym z nich nie wymieniamy ruchu" — a to
    # jest jedyne zdanie w tym pliku, ktore ktos podpisuje wlasnym `approved_by` (runbook §A krok 3).
    # Regula OPA rozroznia te dwa stany wprost (pusta lista legalna, BRAK POLA odrzuca) i narzedzie nie ma
    # prawa tej roznicy zasypac: puste pole formularza to nie jest zgoda, to jest puste pole formularza.
    deklaracja = ap.add_mutually_exclusive_group(required=True)
    deklaracja.add_argument("--peer", action="append", default=[], metavar="KLUCZ",
                            help="klucz czlonka zostajacego w dry-run, z ktorym TEN czlonek wymienia ruch; "
                                 "powtarzalne")
    deklaracja.add_argument("--bez-rowiesnikow", action="store_true",
                            help="OSWIADCZENIE, ze ten czlonek nie wymienia ruchu z zadnym z czlonkow "
                                 "zostajacych w dry-run (zapisuje `unmeasured_peers_ack: []`)")

    ap.add_argument("--root", default=".", help="korzen repozytorium perimetru (domyslnie biezacy katalog)")
    args = ap.parse_args()

    doc = projects_file.wczytaj(args.root)
    wpisy = doc["members"]

    # Czy plik BYL kanoniczny, sprawdzone PRZED zmiana — bo `zapisz` nizej przepisuje go w calosci.
    # To jest NOTATKA, nie odmowa: werdykt o postaci kanonicznej nalezy do guardu w `bramki-tresci`
    # (i tak jest juz czerwony na galezi domyslnej, jesli plik nie jest kanoniczny), a zatrzymywanie
    # legalnej promocji cudzym bledem formatowania byloby bramka nie na tej tresci. Milczec tez nie
    # wolno: obietnica „diff w jednym hunku" jest wtedy nieprawdziwa i promocja tonie w 200 przepisanych
    # liniach — dokladnie ten tryb awarii opisuje `projects_file.zapisz`.
    sciezka = pathlib.Path(args.root) / projects_file.SCIEZKA
    kanoniczny_przed = sciezka.read_text() == projects_file.zrzut(doc)

    # ODMOWA 3 (KOLEJNOSC JEST INNA NIZ W RENDERERZE — SWIADOMIE). Renderer pyta o duplikaty PO pytaniu
    # o tozsamosc projektu, bo adresuje wniosek po TRESCI: `projects_file.znajdz` skanuje liste i widzi
    # oba blizniaki. To narzedzie adresuje czlonka po KLUCZU, czyli przez `projects_file.mapa` — a jej
    # wlasna docstringa mowi „NIE UZYWAJ jej do wykrywania duplikatow, ona je gubi z definicji". Na pliku
    # ze zdublowanym kluczem mapa zostawia JEDEN wpis, wiec kazde pytanie zadane pozniej (istnieje? jest
    # juz enforced?) dostaje odpowiedz o przypadkowym blizniaku. Duplikaty musza wiec isc pierwsze.
    #
    # Reszta powodu jest ta sama, co u renderera: kanal zmieniajacy plik nie ma prawa dokladac zmiany do
    # pliku juz zepsutego — jego pull request wygladalby na przyczyne czerwonych bramek, a bylby ich
    # swiadkiem.
    problemy = projects_file.duplikaty(wpisy)
    if problemy:
        raise SystemExit(
            f"{projects_file.SCIEZKA} zawiera duplikaty JESZCZE PRZED tym wnioskiem — napraw je najpierw:\n  "
            + "\n  ".join(problemy)
        )

    czlonkowie = projects_file.mapa(wpisy)

    # ODMOWA 1 — nie ma czego promowac, bo nie ma wpisu. To jest lustro `out.exists()` z renderera odbite
    # w druga strone: tamten odmawia, gdy wpis JEST, ten odmawia, gdy wpisu NIE MA. Cichy fallback „to
    # dopiszmy nowy" bylby onboardingiem od razu do konfiguracji egzekwowanej — czyli dokladnie tym, czego
    # zakazuje DEC-4, przemyconym przez kanal, ktory nazywa sie „promocja".
    #
    # Literowka w DYWIZJI trafia wlasnie tutaj i to jest zamierzone: klucz sklada sie z dywizji i projektu,
    # wiec `risc-prj-x` zamiast `risk-prj-x` nie wskazuje niczego. Odmowa z probka istniejacych kluczy
    # mowi to od razu, zamiast kazac szukac roznicy w pliku.
    wpis = czlonkowie.get(args.member)
    if wpis is None:
        raise SystemExit(
            f"{projects_file.SCIEZKA}: nie ma wpisu o kluczu {args.member!r} — promocja EDYTUJE istniejacy "
            f"wpis, a nie tworzy nowego. Jesli tego projektu nie ma jeszcze w perimetrze, to nie jest "
            f"promocja, tylko ONBOARDING: idzie kanalem wejscia (intake.yml / external-intake.yml, "
            f"docs/5-servicenow-intake.md), ktory zawsze zapisuje `stage: dry-run`. Klucz ma postac "
            f"`<dywizja>-<project_id>` — sprawdz tez dywizje, literowka w niej daje klucz, ktorego nie ma. "
            f"W pliku sa: {probka(czlonkowie)}"
        )

    # ODMOWA 2 — wpis juz jest egzekwowany. ODMOWA, NIE CICHY NO-OP, i to jest cala roznica: „zrobione"
    # wypisane nad plikiem, ktorego nikt nie zmienil, potwierdza pomylke zamiast ja pokazac. Ten sam blad
    # popelnia sie na dwa sposoby i oba konczy sie tu: pomylony klucz (promujesz kogos, kto od dawna jest
    # enforced, a Twoj czlonek zostaje w dry-run) albo praca na nieaktualnym obrazie repo (ktos scalil te
    # promocje wczesniej). `promotion_hold.py` odrzuca z tego samego powodu zatwierdzenie, ktoremu nie
    # odpowiada zadna oczekujaca promocja.
    #
    # GDY GRANICA REALNIE NIE EGZEKWUJE, A PLIK MOWI `enforced` (po democji recznej, break-glassie,
    # odtworzeniu perimetru — runbook §D.4): deklaracja jest juz poprawna i edycja pliku niczego nie
    # zmieni. Wlaczeniem zajmuje sie apply, ktory porownuje deklaracje z ZYWYM perimetrem:
    # `gh workflow run apply.yml -f promocje="<klucz>"`.
    etap = wpis.get("stage")
    if etap == "enforced":
        raise SystemExit(
            f"{projects_file.SCIEZKA}: wpis {args.member} jest juz `stage: enforced` — nie ma czego "
            f"promowac (dry_run_since: {wpis.get('dry_run_since', '?')}, change_ref: "
            f"{skrot(wpis.get('change_ref', '?'))}). Jesli zywa granica go NIE egzekwuje (democja, break-glass, "
            f"odtworzenie perimetru), plik jest poprawny, a wlacza apply: "
            f"gh workflow run apply.yml -f promocje=\"{args.member}\" (runbook §D.4). Jesli chodzi o zmiane "
            f"`unmeasured_peers_ack`, to osobny pull request na tym wpisie — po promocji pole jest ZAPISEM "
            f"podjetej decyzji, nie potwierdzeniem do odswiezania."
        )

    # Kazdy inny etap niz `dry-run` tez zatrzymuje, bo `stage` jest jedynym polem tego pliku, ktorego
    # skutkiem jest odmowa ruchu — nadpisywanie wartosci, ktorej nie rozumiemy, jest tu najdrozsza
    # z mozliwych pomylek. Schemat dopuszcza dokladnie dwie wartosci, wiec trzecia znaczy „plik jest juz
    # niezgodny ze schematem" i naprawa nalezy do wpisu, nie do promocji.
    if etap != "dry-run":
        raise SystemExit(
            f"{projects_file.SCIEZKA}: wpis {args.member} ma `stage: {etap!r}`, a promocja prowadzi "
            f"WYLACZNIE z `dry-run`. Schemat dopuszcza `dry-run` albo `enforced` — popraw wpis, zanim "
            f"ktokolwiek bedzie go promowal."
        )

    # ODMOWA 5 — referencja PRZEPISANA Z ONBOARDINGU. Odmowa nalezy do tego samego zbioru, co cztery
    # pozostale: po zapisie nie widac jej juz jako bledu. Wpis wyglada wtedy na kompletny — pole
    # `change_ref` jest wypelnione, format zgadza sie ze schematem, bramki sa zielone — a mowi, ze
    # podstawa odciecia ruchu jest wniosek, ktory prosil wylacznie o obserwacje. Zadna pozniejsza
    # kontrola tego nie odrozni, bo obie wartosci sa poprawnymi referencjami.
    #
    # Wariant „to naprawde ta sama sprawa" nie istnieje: ponowna promocja po break-glassie ma swieze
    # okno, swiezy raport i swoj wlasny wniosek (runbook §B „Po incydencie"), a wniosek promocyjny
    # w kanale ticketowym jest z definicji osobna pozycja katalogu.
    if str(args.change_ref) == str(wpis.get("change_ref")):
        raise SystemExit(
            f"{projects_file.SCIEZKA}: --change-ref {skrot(args.change_ref)} jest DOKLADNIE ta wartoscia, "
            f"ktora wpis {args.member} niesie od onboardingu. To pole ma powiedziec, na jakiej podstawie "
            f"granica zaczyna tego czlonka EGZEKWOWAC — a wniosek o wejscie do dry-run tej podstawy nie "
            f"niesie (DEC-58). Podaj referencje wniosku PROMOCYJNEGO; onboardingowa zostaje w historii "
            f"pliku i w pull requescie, ktory ja wpisal."
        )

    # ODMOWA 4 — potwierdzenie wskazujace kogos, kogo nie ma. TA SAMA regula stoi w `policy/onboarding.rego`
    # (deny „…a to nie jest INNY czlonek perimetru"); tutaj odmawiamy WCZESNIEJ, zeby literowka nie
    # dojechala do pull requesta jako lista, ktora w diffie wyglada na przemyslana, a nie potwierdza ani
    # jednej pary. Wskazanie SAMEGO SIEBIE jest tym samym bledem i z tego samego powodu: para „czlonek
    # z samym soba" nie istnieje, wiec taki wpis podbija dlugosc listy, nie jej tresc.
    #
    # `sorted(set(...))`: schemat wymaga `uniqueItems`, a kolejnosc nie znaczy nic — deterministyczny
    # zapis oszczedza recenzentowi porownywania kolejnosci przy kazdym kolejnym wniosku.
    #
    # `args.bez_rowiesnikow` nie jest tu odczytywane i nie jest to niedopatrzenie: ta flaga nie niesie
    # danych, tylko WYMUSZA wypowiedzenie pustej listy (grupa `required=True` wyzej). Wartoscia jest
    # zawsze `args.peer`, ktore bez zadnego `--peer` jest puste.
    potwierdzenie = sorted(set(args.peer))
    obcy = [k for k in potwierdzenie if k == args.member or k not in czlonkowie]
    if obcy:
        raise SystemExit(
            f"{projects_file.SCIEZKA}: unmeasured_peers_ack wskazuje {obcy} — to nie sa INNI czlonkowie "
            f"perimetru. Potwierdzenie wymienia klucze z {projects_file.SCIEZKA} w postaci "
            f"`<dywizja>-<project_id>`; wlasny klucz ({args.member}) tez sie nie liczy. Czlonkowie "
            f"w pliku: {probka(set(czlonkowie) - {args.member})}"
        )

    # Co ta promocja realnie oswiadcza — wypisane PRZED zapisem, tymi samymi kluczami, ktorych uzywa
    # raport naruszen i regula OPA. Nie jest to bramka (pusta lista jest legalna), tylko zdanie, ktore
    # autor pull requesta ma przeczytac zanim je podpisze `approved_by`.
    zostaja = sorted(k for k, m in czlonkowie.items() if k != args.member and m.get("stage") != "enforced")
    print(f"po tej promocji w dry-run zostaje {len(zostaja)} czlonkow: {probka(zostaja)}")
    print(f"potwierdzone jako wymieniajace ruch z {args.member}: {probka(potwierdzenie)}"
          + ("  [OSWIADCZENIE: z zadnym]" if not potwierdzenie else ""))
    print(f"podstawa i podpis tej promocji: {skrot(args.change_ref)} / {args.approved_by} "
          f"(bylo: {skrot(wpis.get('change_ref', '?'))} / {wpis.get('approved_by', '?')})")

    # Podmiana po TOZSAMOSCI obiektu, nie po kluczu: `mapa` zwrocila referencje do tego samego slownika,
    # ktory siedzi na liscie, a duplikatow — jedynego przypadku, w ktorym ta tozsamosc bylaby dwuznaczna —
    # nie ma, bo odmowa 3 wyzej ich nie przepuscila.
    doc["members"] = [promowany(w, potwierdzenie, args.change_ref, args.approved_by) if w is wpis else w
                      for w in wpisy]

    if not kanoniczny_przed:
        print(f"UWAGA: {sciezka} NIE byl w postaci kanonicznej przed ta zmiana, a zapis przepisuje caly "
              f"plik — diff bedzie zawieral takze przeformatowanie i promocja utonie w szumie. Guard "
              f"„plik czlonkow w postaci kanonicznej” (.github/actions/bramki-tresci) jest juz z tego "
              f"powodu czerwony; napraw postac osobnym commitem PRZED promocja.", file=sys.stderr)

    p = projects_file.zapisz(args.root, doc)
    print(f"{args.member}: stage dry-run -> enforced w {p}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except projects_file.BladPliku as e:
        # Blad ksztaltu pliku wspolnego nie jest bledem wniosku — komunikat ma to mowic wprost, inaczej
        # promujacy poprawia swoje argumenty w kolko, a zepsuty jest plik po drugiej stronie granicy.
        print(f"BLAD PLIKU CZLONKOW: {e}", file=sys.stderr)
        raise SystemExit(1) from e
