#!/usr/bin/env python3
"""Generator wpisow dnia pierwszego: wypelnia pola MECHANICZNE, ODMAWIA na niewywnioskowalnych.

CO TO ROZWIAZUJE. Dzien pierwszy to kilkaset istniejacych projektow wchodzacych do `dry-run` jednym
ciagiem, a cala reszta tego repozytorium jest zaprojektowana pod STRUMIEN (~50 wnioskow/mc). Recznie
napisany wpis kosztuje kilka minut i jest do przejrzenia; czterysta recznie napisanych wpisow nie jest
ani jednym, ani drugim. Ten plik zamienia tabele „pole -> skad -> co, gdy brakuje" z runbooka dnia
pierwszego (§2) w kod, ktory te tabele EGZEKWUJE.

DLACZEGO NIE ZACZYNAMY OD FORMATU PLIKU, TYLKO OD PYTANIA „SKAD WSAD". Pomiar na zywej organizacji
(runbook weryfikacji §9.47, powtorzony i rozszerzony w §9.70) mowi rzecz, ktora rozstrzyga ksztalt tego
narzedzia: **zaden kanal po stronie chmury nie produkuje `owner_group` ani `profiles`**. Etykiety
projektu nie niosa wlasciciela, `roles/owner` rozwiazuje sie do `user:` (zly typ), a folder-rodzic jest
proxy DYWIZJI, nie grupy. Inwentarz chmury oddaje wiec dokladnie POLOWE wpisu — te mechaniczna — i to
jest cala prawda o automatyzacji dnia pierwszego. Druga polowa mieszka w CMDB albo nigdzie.

Konsekwencja jest taka, ze narzedzie, ktore „jakos" wypelni brakujace pola, jest GORSZE od jego braku:

  * wpis bez wlasciciela jest martwy w dniu powstania — nie ma kogo zapytac przy promocji ani przy
    `review_by`, a sweeper otworzy za pol roku pull request offboardingowy, ktorego nikt nie zaadresuje;
  * wpis ze ZGADNIETYM profilem renderuje regule autoryzujaca ruch, o ktory nikt nie prosil — czyli
    dziure w granicy wygenerowana przez narzedzie majace ta granice budowac.

Dlatego jedyna dopuszczalna reakcja na brak danych to ODMOWA WYSTAWIENIA WPISU i przekazanie projektu
na liste „do przypisania". Nigdy placeholder, nigdy domysl, nigdy „uzupelnisz pozniej".

CZTERY TRYBY AWARII ZMIERZONE NA ZYWYM API, KTORE TEN PLIK MUSI PRZEZYC (§9.70)

  1. ODCZYT INWENTARZA ZAWODZI CICHO W STRONE „PUSTO". `gcloud asset search-all-resources` przy
     wylaczonym API pisze `[]` NA STDOUT i zwraca `rc=1`. Parser czytajacy sam stdout widzi wtedy
     „organizacja ma zero projektow" — czyli poprawnie sformatowana odpowiedz na pytanie, ktorego nikt
     nie zadal. Dlatego odczyt robi TO narzedzie i sam sprawdza kod wyjscia, a `--inwentarz-z-pliku`
     jest wylacznie hatchem testowym (ten sam uklad, co `--perimetry-z-pliku` w `preflight_gate.py`).
  2. ODCZYT INWENTARZA ZAWODZI CZESCIOWO. Zmierzone w tej samej serii: `rc=1` i **20 z 24** projektow
     na stdout, skladniowo poprawny JSON. To jest grozniejsze od punktu 1, bo wyglada jak sukces.
     Kontrola rozmiaru („zero projektow to awaria odczytu, nie wynik") lapie 1, ale NIE lapie 2 —
     jedyne, co lapie 2, to kod wyjscia. Dlatego jest sprawdzany bezwarunkowo i fail-closed.
  3. KOLEJNOSC ODPOWIEDZI JEST STABILNA, ALE NIE POSORTOWANA. Cztery udane przeloty z rzedu zwrocily
     IDENTYCZNA kolejnosc 24 projektow — i ta kolejnosc nie jest alfabetyczna. Stabilnosc bez kontraktu
     jest pulapka: generator dopisujacy w kolejnosci inwentarza produkuje przy nastepnym przelocie inny
     diff, gdy ktokolwiek utworzy projekt w organizacji. Sortujemy WLASNYM kluczem, jawnie.
  4. FOLDER-RODZIC NIE JEST JEDNA WARTOSCIA. `folders` to LANCUCH przodkow: zmierzone 8 z 24 projektow
     siedzi dwa poziomy gleboko, wiec „folder-rodzic" i „najwyzszy folder pod organizacja" daja INNA
     odpowiedz dla jednej trzeciej organizacji. 5 z 24 nie ma folderu w ogole. Tabela folder->dywizja
     jest wiec przeszukiwana wzdluz lancucha, a DWA trafienia w jednym lancuchu to niejednoznacznosc,
     ktora konczy sie odmowa — nie wyborem blizszego.

CO JEST JEDNOSTKA REVIEW — I DLACZEGO TO NIE JEST WIERSZ (DEC-51)

Partia 25 wpisow wygenerowanych mechanicznie z tego samego zlaczenia nie jest 25 decyzjami. Recenzent
czytajacy je wiersz po wierszu sprawdza, czy narzedzie poprawnie wykonalo `join` — czyli robi rzecz,
ktorej czlowiek nie robi dobrze, i nie robi rzeczy, ktorej maszyna nie zrobi za niego. Dlatego generator
wystawia PODSUMOWANIE PARTII i to ono jest przedmiotem review:

  * KLASY KSZTALTU — rozne (dywizja, zestaw profili, zestaw access-leveli). Jedna klasa to jedna
    decyzja autoryzacyjna, niezaleznie od tego, ilu czlonkow ja realizuje;
  * TOZSAMOSCI — zbior WSZYSTKICH principali w partii, odduplikowany, z liczba wpisow, w ktorych kazdy
    wystepuje. To jest to, co naprawde wpuszczamy do granicy, i tego nie wolno zwinac do klasy;
  * ODMOWY — projekty, ktore wpisu NIE dostaly, z powodem. Ta lista jest pierwszym produktem dnia
    pierwszego, a nie jego odpadem: to ona mowi, czego o wlasnej organizacji nie wiemy;
  * RACHUNEK — obiekty, atrybuty, przewidywany czas apply, zapas budzetu.

Wiersze zostaja w diffie i nikt ich nie ukrywa — zmienia sie to, CZEGO SIE OD RECENZENTA WYMAGA.

CZEGO TO NARZEDZIE NIE ROBI. Nie wola ACM, nie mutuje granicy, nie uruchamia pre-flightu i nie zna sie
na promocji. Czyta inwentarz, czyta eksport CMDB, dopisuje do `perimeter/projects.yaml` i wypisuje
podsumowanie. `stage` jest zawsze `dry-run` — wejscie proszace o `enforced` jest bledem wejscia, nie
wariantem, bo dzien pierwszy z definicji nikogo nie promuje (§9.47: `status` zostaje zerem).

DANE OSOBOWE. Eksport CMDB potrafi niesc adresy ludzi. Nie logujemy calych wierszy wejscia i nie
zapisujemy wejscia do repozytorium — do repo trafiaja wylacznie pola wpisu czlonkowskiego.
"""
import argparse
import csv
import io
import json
import pathlib
import subprocess
import sys
from collections import Counter, defaultdict

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("brakuje pyyaml: pip install pyyaml")

import projects_file

# Koszt krancowy czlonka i staly narzut konfiguracji — ZMIERZONE rendererem (§9.47, tabela deklaracji
# o rozmiarze organizacji docelowej), nie oszacowane. `21` to konfiguracja z zerem czlonkow (baseline celuje
# w `*`, wiec ich koszt sie nie mnozy), `9.54` to (2884 - 41) / 298 dla mieszanki profili z §9.4.
# Te same liczby stoja w runbooku dnia pierwszego §1 — jesli sie rozjada, rozjedzie sie punkt zatrzymania.
NARZUT_KONFIGURACJI = 21
ATRYBUTOW_NA_CZLONKA = 9.54
LIMIT_ATRYBUTOW = 6000
PROG_WARNING = 4200  # 70 % limitu — powyzej tego dzien pierwszy wchodzi od razu na warning budzetu

# Tempo zapisu ZMIERZONE na zywym API przy rownoleglosci domyslnej (§9.47, przebieg A). Rownoleglosc
# podnosi je o 1,25x, nie 10x — zapisy szereguja sie na obiekcie perimetru — wiec ekstrapolacja czasu
# partii z tej jednej liczby jest uczciwa. Sluzy WYLACZNIE do podsumowania; nic jej nie egzekwuje.
ZAPISOW_NA_MINUTE = 33.2

# Rozmiar partii z runbooka dnia pierwszego §3E. Wynika z CZASU ODZYSKU po awarii apply, nie
# z czytelnosci diffa: ~67 obiektow to ~2,0 min apply, czyli tyle stoi strumien i tyle najwyzej trzeba
# powtorzyc. Zmiana tej liczby jest zmiana procedury, nie ustawieniem — dlatego jest tu stala z nazwa.
PARTIA_DOMYSLNA = 25

OKNO_REVIEW_DNI = 180  # `review_by` = `dry_run_since` + tyle (runbook §2)

POLA_Z_CMDB = ("owner_group", "profiles")


class BladWejscia(Exception):
    """Wejscie jest nie do przyjecia jako CALOSC. Zawsze fail-closed — nigdy „pomin i jedz dalej".

    Rozroznienie wzgledem odmowy pojedynczego projektu jest cala trescia tej klasy: brak `owner_group`
    dla jednego projektu to normalny wynik dnia pierwszego (projekt idzie na liste do przypisania),
    a duplikat `project_id` w eksporcie CMDB to stan, w ktorym NIE WIEMY, ktory wiersz jest prawdziwy —
    i wtedy nie wolno wybrac, tylko trzeba stanac.
    """


# --------------------------------------------------------------------- inwentarz chmury


def czytaj_inwentarz_z_api(organizacja: str, billing_project: str) -> list:
    """Inwentarz WSZYSTKICH projektow organizacji — jedno wywolanie, fail-closed na kodzie wyjscia.

    DLACZEGO CLOUD ASSET INVENTORY, A NIE `projects list`. Dwa powody, oba zmierzone:
      * `gcloud projects list` domyslnie pokazuje wylacznie `ACTIVE`, wiec projekt w `DELETE_REQUESTED`
        wyglada tam identycznie jak projekt, ktorego nigdy nie bylo — a to jest dokladnie ten stan,
        ktory dzien pierwszy musi ODRZUCIC swiadomie, a nie przeoczyc (§9.13, §9.52);
      * uprawnienie juz jest. Konto planu ma `cloudasset.viewer`; `resourcemanager.projects.get`
        na organizacji nie ma NIKT i jego nadanie byloby nowym uprawnieniem org-level dla konta
        wolanego z kazdego pull requesta (§9.52).

    DLACZEGO ODCZYT ROBI TO NARZEDZIE, A NIE CALLER. Bo kod wyjscia jest jedyna rzecza, ktora odroznia
    komplet od wyniku czesciowego — a zmierzony tryb awarii pisze poprawny JSON na stdout w OBU
    przypadkach (`[]` przy wylaczonym API, 20 z 24 przy API jeszcze propagujacym sie). Narzedzie, ktore
    przyjmuje plik, oddaje ten check komus, kto go nie zrobi.
    """
    p = subprocess.run(
        ["gcloud", "asset", "search-all-resources",
         f"--scope=organizations/{organizacja}",
         "--asset-types=cloudresourcemanager.googleapis.com/Project",
         f"--billing-project={billing_project}",
         "--format=json", "--quiet"],
        capture_output=True, text=True)
    if p.returncode != 0:
        raise BladWejscia(
            f"odczyt inwentarza organizacji {organizacja} NIE POWIODL SIE (rc={p.returncode}). "
            f"Nie zaczynam partii na niepelnej liscie projektow — zmierzone, ze to wywolanie przy "
            f"bledzie i tak pisze poprawny JSON na stdout (raz `[]`, raz 20 z 24 obiektow), wiec sama "
            f"tresc odpowiedzi NIE odroznia kompletu od wyniku czesciowego: {p.stderr.strip()[:400]}")
    return json.loads(p.stdout or "[]")


def czytaj_inwentarz_z_pliku(sciezka) -> list:
    """Inwentarz z pliku — hatch dla testow i dla przelotu na zapisanej odpowiedzi.

    Kontrola rozmiaru jest tu, a nie w `czytaj_inwentarz_z_api`, bo dotyczy OBU drog: ktos predzej czy
    pozniej przekieruje stdout do pliku i poda go tutaj, gubiac po drodze kod wyjscia. Pusty inwentarz
    jako WYNIK nie istnieje — organizacja, ktora wchodzi pod granice, ma projekty z definicji.
    """
    dane = json.loads(pathlib.Path(sciezka).read_text())
    if not isinstance(dane, list):
        raise BladWejscia(f"{sciezka}: inwentarz ma byc lista zasobow, a jest {type(dane).__name__}")
    if not dane:
        raise BladWejscia(
            f"{sciezka}: inwentarz jest PUSTY. To nie jest wynik, to awaria odczytu — organizacja "
            f"wchodzaca pod granice ma projekty z definicji, a `gcloud asset search-all-resources` "
            f"przy wylaczonym API pisze dokladnie `[]` na stdout i zwraca rc=1 (zmierzone, §9.70).")
    return dane


def projekt_z_zasobu(zasob: dict) -> dict:
    """Jeden zasob z Asset Inventory -> pola, ktorych potrzebuje wpis czlonkowski.

    Ksztalt odczytany z API, nie z dokumentacji (§9.52): `additionalAttributes.projectId` niesie
    identyfikator, a `project` = `projects/<NUMER>` niesie numer — i to numerem operuje granica.
    `folders` jest LANCUCHEM przodkow od najblizszego do najdalszego (zmierzone: 8 z 24 projektow ma
    dwa elementy), a jego BRAK znaczy „wprost pod organizacja" (5 z 24) i jest legalnym stanem chmury,
    ktory dla nas konczy sie odmowa — bo nie ma z czego wyprowadzic dywizji.
    """
    return {
        "project_id": (zasob.get("additionalAttributes") or {}).get("projectId"),
        "project_number": str(zasob.get("project", "")).split("/")[-1],
        "state": zasob.get("state"),
        "foldery": [f.split("/")[-1] for f in (zasob.get("folders") or [])],
    }


# --------------------------------------------------------------------- eksport CMDB


def czytaj_cmdb(sciezka) -> dict:
    """Eksport CMDB jako mapa `project_id` -> wiersz. CSV albo JSON, rozpoznawane po rozszerzeniu.

    DUPLIKAT `project_id` JEST BLEDEM CALEGO WEJSCIA, NIE WIERSZA. Powod jest ten sam, dla ktorego
    `projects_file.py` odrzuca duplikat klucza mapy: przy dwoch wierszach o tym samym projekcie nie ma
    reguly poza „ostatni wygrywa", a ta regula znaczy tutaj „jedna z dwoch grup wlascicielskich zniknela
    bez sladu". `yamldecode` Terraforma i `yaml.safe_load` zachowuja sie tak samo i tak samo cicho
    (§9.9) — jedyna roznica jest taka, ze tu wybor zapada PRZED review, wiec nikt go juz nie zobaczy.
    """
    p = pathlib.Path(sciezka)
    tekst = p.read_text()
    if p.suffix.lower() == ".json":
        wiersze = json.loads(tekst)
        if not isinstance(wiersze, list):
            raise BladWejscia(f"{sciezka}: eksport CMDB w JSON ma byc LISTA wierszy")
    else:
        wiersze = list(csv.DictReader(io.StringIO(tekst)))

    mapa, widziane = {}, defaultdict(list)
    for i, w in enumerate(wiersze, 1):
        pid = (w.get("project_id") or "").strip()
        if not pid:
            raise BladWejscia(f"{sciezka}: wiersz #{i} nie ma `project_id` — bez niego nie ma czego zlaczyc")
        widziane[pid].append(i)
        mapa[pid] = w
    duble = {k: v for k, v in widziane.items() if len(v) > 1}
    if duble:
        opis = "; ".join(f"{k} w wierszach {v}" for k, v in sorted(duble.items()))
        raise BladWejscia(
            f"{sciezka}: eksport CMDB ma zdublowane `project_id` ({opis}). Nie wybieram za Ciebie: "
            f"'ostatni wygrywa' znaczy tu, ze jedna z dwoch grup wlascicielskich znika bez sladu, "
            f"a wybor zapada PRZED review i nikt go juz nie zobaczy. Popraw eksport i uruchom ponownie.")
    return mapa


def profile_z_wiersza(wiersz: dict) -> list:
    """Profile z wiersza CMDB. Akceptujemy strukture (JSON) albo tekst JSON w kolumnie CSV.

    NIE AKCEPTUJEMY listy samych NAZW profili. Profil bez `params` nie renderuje sie w nic sensownego —
    `caller_identities` jest tym, KOGO wpuszczamy, a profil z pusta lista tozsamosci to albo regula
    autoryzujaca nikogo (martwy atrybut w budzecie), albo — gorzej — profil, ktorego parametry ktos
    „uzupelni pozniej" bezposrednio na `projects.yaml`, czyli poza tym rachunkiem i poza podsumowaniem.
    """
    surowe = wiersz.get("profiles")
    if surowe in (None, "", []):
        return []
    if isinstance(surowe, str):
        try:
            surowe = json.loads(surowe)
        except json.JSONDecodeError as e:
            raise BladWejscia(
                f"projekt {wiersz.get('project_id')!r}: kolumna `profiles` nie jest poprawnym JSON-em "
                f"({e}). W CSV profile zapisuje sie jako JSON w jednej kolumnie.") from None
    if not isinstance(surowe, list):
        raise BladWejscia(f"projekt {wiersz.get('project_id')!r}: `profiles` ma byc lista, "
                          f"a jest {type(surowe).__name__}")
    for wpis in surowe:
        if not isinstance(wpis, dict) or not wpis.get("name"):
            raise BladWejscia(
                f"projekt {wiersz.get('project_id')!r}: kazdy profil to mapa z `name` i `params` — "
                f"sama nazwa nie wystarczy, bo `params` niesie tozsamosci, ktore wpuszczamy do granicy")
        if not wpis.get("params"):
            raise BladWejscia(
                f"projekt {wiersz.get('project_id')!r}: profil {wpis['name']!r} nie ma `params`. "
                f"Profil bez parametrow albo nie autoryzuje nikogo, albo zostanie uzupelniony recznie "
                f"POZA rachunkiem partii i poza podsumowaniem review.")
    return surowe


# --------------------------------------------------------------------- tabela folder -> dywizja


def czytaj_tabele_folderow(sciezka) -> dict:
    """Tabela folder->dywizja. UTRZYMUJE JA CZLOWIEK i to jest jej cala wartosc.

    Zmierzone (§9.47, potwierdzone na 24 projektach w §9.70): folder jest proxy dywizji, ale nazwa
    folderu nia nie jest — tlumaczenie jest decyzja organizacyjna, ktorej chmura nie przechowuje.
    Automatyczne wyprowadzenie dywizji z nazwy folderu bylo rozwazane i odrzucone: dawaloby dywizje
    zalezna od literowki w nazwie folderu, czyli identyfikator zasobu Terraforma (`<dywizja>-<projekt>`)
    zalezny od pola, ktore ktos moze zmienic w konsoli bez zadnego pull requesta.
    """
    dane = yaml.safe_load(pathlib.Path(sciezka).read_text())
    if not isinstance(dane, dict) or not isinstance(dane.get("folders"), dict):
        raise BladWejscia(f"{sciezka}: tabela ma byc mapa z kluczem `folders`: "
                          f"{{folders: {{'<numer-folderu>': '<dywizja>'}}}}")
    return {str(k): str(v) for k, v in dane["folders"].items()}


def dywizja_z_lancucha(foldery: list, tabela: dict):
    """(dywizja, powod-odmowy). Przeszukuje LANCUCH przodkow, a dwa trafienia = odmowa.

    DLACZEGO NIE „bierz najblizszy folder z tabeli". Bo to jest wybor, a nie odczyt. Zmierzone:
    8 z 24 projektow ma lancuch dwuelementowy, wiec „folder-rodzic" i „najwyzszy folder" daja rozna
    odpowiedz dla jednej trzeciej organizacji. Jesli oba poziomy sa w tabeli, to znaczy, ze tabela
    opisuje dwie rozne dywizje dla jednego projektu — i jest to blad TABELI, ktory milczaco rozstrzygniety
    daje czlonka przypisanego do dywizji, ktorej wlasciciel nigdy o nim nie slyszal. Adres zasobu
    w stanie Terraforma zaczyna sie od dywizji, wiec pozniejsza korekta to `destroy` + `create` reguly
    na zywej granicy, nie edycja pola.
    """
    if not foldery:
        return None, ("projekt lezy wprost pod organizacja — nie ma folderu, z ktorego wyprowadzamy "
                      "dywizje (zmierzone: dotyczy 5 z 24 projektow organizacji labu)")
    trafienia = [(f, tabela[f]) for f in foldery if f in tabela]
    if not trafienia:
        return None, (f"zaden folder z lancucha {foldery} nie ma tlumaczenia w tabeli folder->dywizja "
                      f"— tabele uzupelnia czlowiek, generator nie zgaduje dywizji z nazwy folderu")
    if len(trafienia) > 1:
        opis = ", ".join(f"{f}->{d}" for f, d in trafienia)
        return None, (f"lancuch folderow ma DWA tlumaczenia naraz ({opis}) — tabela opisuje dwie rozne "
                      f"dywizje dla jednego projektu; to blad tabeli, a nie sytuacja do rozstrzygniecia "
                      f"przez wybor blizszego folderu")
    return trafienia[0][1], None


# --------------------------------------------------------------------- budowanie wpisu


def zbuduj_wpis(projekt: dict, dywizja: str, wiersz_cmdb: dict, *, data: str,
                review_by: str, change_ref: str, approved_by: str) -> dict:
    """Wpis czlonkowski w kolejnosci pol zgodnej z `perimeter/projects.yaml.example`.

    `stage` jest ustawiany TUTAJ i tylko tutaj. Nie jest przepisywany z wejscia i nie da sie go z wejscia
    nadpisac — proba jest zatrzymywana wczesniej, w `sprawdz_brak_promocji`. Dzien pierwszy z definicji
    nikogo nie promuje: §9.47 mierzy, ze `status` zostaje zerem, dopoki nikt nie jest promowany, i to
    jest dowod, ze partia w `dry-run` nie dotyka konfiguracji egzekwowanej ANI JEDNYM atrybutem.
    """
    return {
        "schema_version": 1,
        "division": dywizja,
        "project_id": projekt["project_id"],
        "project_number": projekt["project_number"],
        "owner_group": wiersz_cmdb["owner_group"].strip(),
        "change_ref": change_ref,
        "approved_by": approved_by,
        "stage": "dry-run",
        "dry_run_since": data,
        "review_by": review_by,
        "profiles": profile_z_wiersza(wiersz_cmdb),
    }


def sprawdz_change_ref(wartosc: str, katalog_schematow) -> None:
    """`change_ref` MUSI przejsc ten sam wzorzec, ktory sprawdzi schemat — sprawdzony PRZED zapisem.

    ZMIERZONE, ZE BRAK TEGO CHECKU BOLI DOPIERO NA KONCU. Przelot z `--change-ref x` zapisal **438
    poprawnych wpisow** i dopiero `check-jsonschema` na pull requescie odrzucil je wszystkie naraz,
    po jednym bledzie na wpis. Wartosc jest dla calej partii JEDNA, wiec jej wada jest wada calej
    partii — a kosztem spoznionego wykrycia jest wygenerowanie jej od nowa.

    WZORZEC CZYTAMY ZE SCHEMATU, NIE PRZEPISUJEMY. Druga kopia regexu rozjechalaby sie z pierwsza przy
    pierwszej zmianie konwencji identyfikatorow zmian, a rozjazd objawilby sie jako narzedzie
    odrzucajace wartosci, ktore schemat przyjmuje — czyli bramka ostrzejsza od kontraktu i niemozliwa
    do obejscia inaczej niz jej wylaczeniem.
    """
    import re
    p = pathlib.Path(katalog_schematow) / "member.schema.json"
    if not p.exists():
        raise BladWejscia(f"nie ma {p} — bez schematu nie mam czym sprawdzic `change_ref`, "
                          f"a wartosc niezgodna ze schematem odrzuci dopiero bramka, po zapisaniu partii")
    wzorzec = (json.loads(p.read_text()).get("properties", {}).get("change_ref", {}) or {}).get("pattern")
    if wzorzec and not re.match(wzorzec, wartosc):
        raise BladWejscia(
            f"`--change-ref {wartosc!r}` nie pasuje do wzorca ze schematu ({wzorzec}). Ta wartosc jest "
            f"wspolna dla CALEJ partii, wiec jej wada jest wada calej partii — zatrzymuje przed zapisem, "
            f"a nie po nim.")


def sprawdz_brak_promocji(cmdb: dict) -> None:
    """Wejscie proszace o `enforced` zatrzymuje CALY przelot — nie jest po cichu nadpisywane.

    Roznica jest zasadnicza. Nadpisanie `enforced` na `dry-run` daje przelot zielony i wpis poprawny,
    a intencja — czyjas, byc moze bledna — znika bez sladu; nastepnym razem ta sama intencja przyjdzie
    ta sama droga i tak samo zniknie. Zatrzymanie robi z tego rozmowe przed partia. Promocja ma wlasny
    tor z wlasnymi bramkami (okno obserwacji, czyste okno, bramka manualna) i dzien pierwszy nie jest
    zadnym z jego etapow.
    """
    proby = sorted(pid for pid, w in cmdb.items() if str(w.get("stage", "")).strip() == "enforced")
    if proby:
        raise BladWejscia(
            f"eksport CMDB prosi o `stage: enforced` dla: {', '.join(proby)}. Dzien pierwszy wprowadza "
            f"WYLACZNIE do `dry-run` i nie promuje nikogo — promocja ma wlasny tor z okna obserwacji "
            f"i bramka manualna. Nie nadpisuje tego po cichu: cicha korekta zostawilaby intencje "
            f"niewidoczna dla review, a nastepnym razem przyszlaby ta sama droga.")


# --------------------------------------------------------------------- rachunek partii


def rachunek(czlonkow_razem: int) -> dict:
    """Rachunek budzetu i czasu dla CALEJ konfiguracji po wejsciu partii — nie dla samej partii.

    Liczymy sume, a nie przyrost, bo limit 6000 atrybutow jest limitem KONFIGURACJI. Partia, ktora sama
    w sobie jest mala, potrafi przekroczyc prog, jesli wchodzi jako dziesiata.
    """
    atrybuty = NARZUT_KONFIGURACJI + ATRYBUTOW_NA_CZLONKA * czlonkow_razem
    return {
        "czlonkow": czlonkow_razem,
        "atrybuty_spec": round(atrybuty),
        "procent_limitu": round(100 * atrybuty / LIMIT_ATRYBUTOW, 1),
        "zapas_czlonkow": int((LIMIT_ATRYBUTOW - atrybuty) / ATRYBUTOW_NA_CZLONKA),
        "przekroczony_warning": atrybuty > PROG_WARNING,
    }


def czas_apply(obiektow: int) -> float:
    """Minuty apply dla podanej liczby obiektow. EKSTRAPOLACJA ze zmierzonego tempa, i tak jest opisana."""
    return round(obiektow / ZAPISOW_NA_MINUTE, 1)


def regul_w_profilach(katalog) -> dict:
    """Nazwa profilu -> ile REGUL renderuje. Czytane z katalogu profili, nie zakladane.

    ZMIERZONE, ZE ZALOZENIE „jeden profil = jedna regula" ZANIZA. Katalog ma dzis profil renderujacy
    ingress ORAZ egress (`vertex-batch-training`), wiec formula `1 + len(profiles)` policzyla dla partii
    300 czlonkow **767** obiektow zamiast **808** zmierzonych rendererem (§9.47) — 5 % w dol, i to
    w kierunku, w ktorym operacyjna liczba mylic sie nie powinna: „apply potrwa krocej, niz potrwa".
    Katalog lezy w tym samym repozytorium, wiec odczyt jest tansi niz stala do pilnowania.
    """
    mapa = {}
    for p in sorted(pathlib.Path(katalog).glob("*.yaml")):
        d = yaml.safe_load(p.read_text()) or {}
        if d.get("name"):
            mapa[d["name"]] = len(d.get("ingress") or []) + len(d.get("egress") or [])
    return mapa


def obiektow_z_wpisow(wpisy: list, regul: dict) -> int:
    """Obiekty w `spec`: jeden zasob czlonkowski + reguly kazdego profilu.

    Sluzy WYLACZNIE ekstrapolacji czasu apply w podsumowaniu. Zrodlem prawdy o ATRYBUTACH jest
    `tools/attribute_budget.py` liczacy z wyrenderowanych deklaracji — gdyby ta funkcja byla drugim
    licznikiem budzetu, rozjechalaby sie z nim tak samo, jak rozjechaly sie trzy kopie liczenia budzetu
    przed powstaniem tamtego narzedzia. Profil nieznany katalogowi liczymy jako JEDNA regule i to jest
    swiadome zanizenie zamiast wyjatku: nieznany profil zatrzyma i tak bramka tresci, a podsumowanie ma
    dzialac takze na wejsciu, ktore jeszcze nie przeszlo bramek.
    """
    return sum(1 + sum(regul.get(p.get("name"), 1) for p in (w.get("profiles") or [])) for w in wpisy)


# --------------------------------------------------------------------- podsumowanie = jednostka review


def klasa_ksztaltu(wpis: dict) -> tuple:
    """(dywizja, nazwy profili, access-levele) — jedna decyzja autoryzacyjna. Bez tozsamosci.

    Tozsamosci sa SWIADOMIE poza klasa i sa raportowane osobno, jako zbior. Gdyby wchodzily do klasy,
    kazdy czlonek mialby wlasna klase (konta serwisowe sa per projekt) i podsumowanie zdegenerowaloby sie
    z powrotem do listy wierszy — czyli do rzeczy, ktora ten podzial ma usunac. Gdyby ich nie bylo nigdzie,
    review przepuszczaloby dowolna tozsamosc pod znana etykieta profilu, co jest gorsze niz brak
    podsumowania: dawaloby poczucie, ze partia zostala przejrzana.
    """
    profile = tuple(sorted(p.get("name", "?") for p in (wpis.get("profiles") or [])))
    poziomy = tuple(sorted({lvl for p in (wpis.get("profiles") or [])
                            for lvl in ((p.get("params") or {}).get("access_levels") or [])}))
    return (wpis.get("division"), profile, poziomy)


def tozsamosci_wpisu(wpis: dict) -> set:
    """Wszystkie principale wpisu, niezaleznie od tego, przez ktory parametr profilu weszly.

    Zbieramy po KSZTALCIE wartosci (`typ:adres`), a nie po nazwie parametru, bo nazwy parametrow naleza
    do katalogu profili i rosna razem z nim — lista nazw wpisana tutaj bylaby czwarta kopia katalogu
    i cicho przestalaby widziec tozsamosci nowego profilu.
    """
    znalezione = set()
    for profil in wpis.get("profiles") or []:
        for wartosc in (profil.get("params") or {}).values():
            for v in (wartosc if isinstance(wartosc, list) else [wartosc]):
                if isinstance(v, str) and ":" in v and v.split(":", 1)[0] in (
                        "user", "group", "serviceAccount", "principal", "principalSet"):
                    znalezione.add(v)
    return znalezione


def podsumowanie(wpisy: list, odmowy: list, pominiete: list, czlonkow_razem: int,
                 regul: dict) -> list:
    """Podsumowanie partii — to jest przedmiot review, nie wiersze (DEC-51)."""
    linie = []
    klasy = Counter(klasa_ksztaltu(w) for w in wpisy)
    tozsamosci = Counter(t for w in wpisy for t in tozsamosci_wpisu(w))
    r = rachunek(czlonkow_razem)
    obiektow = obiektow_z_wpisow(wpisy, regul)

    linie.append(f"WPISOW W PARTII: {len(wpisy)}   ODMOW: {len(odmowy)}   "
                 f"POMINIETYCH (juz w pliku): {len(pominiete)}")
    linie.append("")
    linie.append(f"KLASY KSZTALTU — {len(klasy)} decyzji autoryzacyjnych na {len(wpisy)} wpisow:")
    for (dyw, profile, poziomy), ile in sorted(klasy.items(), key=lambda x: (-x[1], str(x[0]))):
        przyklad = next(w["project_id"] for w in wpisy if klasa_ksztaltu(w) == (dyw, profile, poziomy))
        linie.append(f"  [{ile:>3}x] {dyw} :: {' + '.join(profile) or '(bez profili)'} "
                     f":: poziomy={', '.join(poziomy) or '(brak)'}   np. {przyklad}")
    linie.append("")
    linie.append(f"TOZSAMOSCI — {len(tozsamosci)} roznych principali wpuszczanych ta partia:")
    for t, ile in sorted(tozsamosci.items(), key=lambda x: (-x[1], x[0])):
        linie.append(f"  [{ile:>3}x] {t}")
    linie.append("")
    linie.append(f"RACHUNEK PO PARTII: czlonkow {r['czlonkow']}, atrybuty spec ~{r['atrybuty_spec']} "
                 f"({r['procent_limitu']} % limitu {LIMIT_ATRYBUTOW}), zapas ~{r['zapas_czlonkow']} czlonkow")
    linie.append(f"                    obiektow w partii ~{obiektow}, apply ~{czas_apply(obiektow)} min "
                 f"(ekstrapolacja z {ZAPISOW_NA_MINUTE} zapisu/min — zmierzone, nie oszacowane)")
    if odmowy:
        linie.append("")
        linie.append("ODMOWY — projekty BEZ wpisu (to jest pierwszy produkt dnia pierwszego, nie odpad):")
        for pid, powod in sorted(odmowy):
            linie.append(f"  {pid}: {powod}")
    if pominiete:
        linie.append("")
        linie.append(f"POMINIETE — maja juz wpis w {projects_file.SCIEZKA}, wiec partia ich nie dubluje:")
        linie.append("  " + ", ".join(sorted(pominiete)))
    return linie


# --------------------------------------------------------------------- przelot


def generuj(*, inwentarz: list, cmdb: dict, tabela: dict, istniejacy: list, data: str,
            review_by: str, change_ref: str, approved_by: str, partia: int):
    """(wpisy do dopisania, odmowy, pominiete). Czysta funkcja — zero wejscia i wyjscia.

    IDEMPOTENCJA. Projekt majacy juz wpis w `projects.yaml` jest POMIJANY i raportowany, nigdy dopisywany
    drugi raz. Klucz porownania to `project_id` ORAZ `project_number` — literowka w dywizji zmienia klucz
    czlonka (`<dywizja>-<projekt>`), wiec porownanie po samym kluczu czlonka przepuscilo by ten sam projekt
    jako nowego. To jest wprost powod, dla ktorego `projects_file.znajdz` pyta o oba pola.

    Dzieki temu ponowienie po smierci `apply` w polowie nie dubluje niczego i nie gubi reszty: wpisy juz
    zapisane w pliku sa pomijane, brakujace powstaja. Rozjazd miedzy plikiem a ZYWA GRANICA to inna sprawa
    i inne narzedzie (`perimeter_watch.py`, procedura sieroty w runbooku dnia pierwszego §5) — generator
    swiadomie nie pyta ACM, bo wtedy jego wynik zalezalby od stanu, ktorego review nie widzi.

    DETERMINIZM. Sortujemy po `(dywizja, project_id)` — kolejnosc odpowiedzi Asset Inventory jest
    stabilna, ale NIE posortowana (zmierzone: cztery przeloty, identyczna kolejnosc, nie alfabetyczna).
    Poleganie na niej daloby inny diff przy nastepnym przelocie, gdy ktokolwiek utworzy projekt.
    """
    wpisy, odmowy, pominiete = [], [], []
    for zasob in inwentarz:
        p = projekt_z_zasobu(zasob)
        pid = p["project_id"]
        if not pid:
            odmowy.append(("(zasob bez projectId)", f"odpowiedz inwentarza bez `additionalAttributes.projectId`"))
            continue

        # `state` PRZED wszystkim innym: numer projektu skasowanego jest rozwiazywalny przez 30 dni,
        # wiec ACM przyjmie go jako czlonka bez slowa skargi (§9.13). Odrzucamy po STANIE, nigdy po tym,
        # czy numer „dziala" — bo dziala.
        if p["state"] != "ACTIVE":
            odmowy.append((pid, f"stan projektu to {p['state']}, nie ACTIVE — soft-delete zostawia numer "
                                f"rozwiazywalny przez 30 dni, wiec granica przyjelaby go jako martwego czlonka"))
            continue

        if projects_file.znajdz(istniejacy, project_id=pid, project_number=p["project_number"]):
            pominiete.append(pid)
            continue

        dywizja, powod = dywizja_z_lancucha(p["foldery"], tabela)
        if dywizja is None:
            odmowy.append((pid, powod))
            continue

        wiersz = cmdb.get(pid)
        if wiersz is None:
            odmowy.append((pid, "brak wiersza w eksporcie CMDB — projekt nie ma znanego wlasciciela; "
                                "to jest lista, ktora ktos musi przypisac, zanim projekt wejdzie pod granice"))
            continue

        # Dywizja z tabeli jest ZRODLEM PRAWDY, bo wyprowadza sie z zywego drzewa zasobow. Jesli CMDB
        # tez ja niesie i mowi co innego, to nie jest sytuacja do rozstrzygniecia priorytetem — to znaczy,
        # ze jedno z dwoch zrodel opisuje nieaktualny swiat, a wybor milczacy zostawilby czlonka
        # w dywizji, ktorej wlasciciel o nim nie wie.
        z_cmdb = (wiersz.get("division") or "").strip()
        if z_cmdb and z_cmdb != dywizja:
            odmowy.append((pid, f"dywizja z tabeli folderow ({dywizja}) rozni sie od dywizji z CMDB "
                                f"({z_cmdb}) — jedno ze zrodel opisuje nieaktualny stan"))
            continue

        brakujace = [pole for pole in POLA_Z_CMDB if not wiersz.get(pole)]
        if brakujace:
            odmowy.append((pid, f"eksport CMDB nie niesie: {', '.join(brakujace)} — zaden kanal po stronie "
                                f"chmury tego nie produkuje (§9.47), wiec wpis NIE powstaje"))
            continue

        wpisy.append(zbuduj_wpis(p, dywizja, wiersz, data=data, review_by=review_by,
                                 change_ref=change_ref, approved_by=approved_by))

    wpisy.sort(key=lambda w: (w["division"], w["project_id"]))
    return wpisy[:partia], odmowy, pominiete


def main() -> int:
    ap = argparse.ArgumentParser(description="Generator wpisow dnia pierwszego (tylko `dry-run`).")
    ap.add_argument("--cmdb", required=True, help="eksport CMDB (CSV albo JSON)")
    ap.add_argument("--foldery", required=True, help="tabela folder->dywizja (YAML), utrzymuje czlowiek")
    ap.add_argument("--change-ref", required=True, help="identyfikator zmiany, w ktorej partia jest zatwierdzona")
    ap.add_argument("--approved-by", required=True, help="czlowiek zatwierdzajacy partie")
    ap.add_argument("--data", required=True, help="data partii (`dry_run_since`), YYYY-MM-DD")
    ap.add_argument("--root", default=".", help="korzen repozytorium (dla perimeter/projects.yaml)")
    ap.add_argument("--policy", default="perimeter/policy.yaml")
    ap.add_argument("--organizacja", help="numer organizacji do odczytu inwentarza z API")
    ap.add_argument("--billing-project", help="projekt rozliczajacy kwote odczytu Asset Inventory")
    ap.add_argument("--inwentarz-z-pliku", help="zapisana odpowiedz Asset Inventory zamiast wywolania (testy)")
    ap.add_argument("--partia", type=int, default=PARTIA_DOMYSLNA,
                    help=f"maksymalny rozmiar partii (domyslnie {PARTIA_DOMYSLNA}, runbook dnia pierwszego §3E)")
    ap.add_argument("--tylko-podsumowanie", action="store_true",
                    help="policz i wypisz, NIE zapisuj nic do perimeter/projects.yaml")
    args = ap.parse_args()

    try:
        if args.inwentarz_z_pliku:
            inwentarz = czytaj_inwentarz_z_pliku(args.inwentarz_z_pliku)
        else:
            if not (args.organizacja and args.billing_project):
                raise BladWejscia("bez `--inwentarz-z-pliku` potrzebuje `--organizacja` i `--billing-project`")
            inwentarz = czytaj_inwentarz_z_api(args.organizacja, args.billing_project)

        sprawdz_change_ref(args.change_ref, pathlib.Path(args.root) / "schemas")
        cmdb = czytaj_cmdb(args.cmdb)
        sprawdz_brak_promocji(cmdb)
        tabela = czytaj_tabele_folderow(args.foldery)
        istniejacy = projects_file.wczytaj(args.root)["members"]

        # `review_by` = `dry_run_since` + 180 dni. Liczone z daty partii, nigdy „dzis" — data partii jest
        # polem procedury i musi dac ten sam wynik przy ponowieniu przelotu nastepnego dnia. Inaczej
        # wznowienie po awarii przesunelo by okno review czesci czlonkow o roznice dat, po cichu.
        import datetime
        d = datetime.date.fromisoformat(args.data)
        review_by = (d + datetime.timedelta(days=OKNO_REVIEW_DNI)).isoformat()

        wpisy, odmowy, pominiete = generuj(
            inwentarz=inwentarz, cmdb=cmdb, tabela=tabela, istniejacy=istniejacy,
            data=args.data, review_by=review_by, change_ref=args.change_ref,
            approved_by=args.approved_by, partia=args.partia)
    except (BladWejscia, projects_file.BladPliku) as e:
        print(f"::error::dzien pierwszy PRZERWANY: {e}", file=sys.stderr)
        return 2

    razem = len(istniejacy) + len(wpisy)
    r = rachunek(razem)
    regul = regul_w_profilach(pathlib.Path(args.root) / "perimeter" / "profiles")
    for linia in podsumowanie(wpisy, odmowy, pominiete, razem, regul):
        print(linia)

    # PUNKT ZATRZYMANIA. Prog jest sprawdzany PRZED zapisem, bo decyzja o dzwigniach budzetowych zapada
    # przed partia, a nie po niej: partia, ktora juz wjechala, kosztuje tyle samo atrybutow niezaleznie
    # od tego, czy ktos ja przejrzal. Zwracamy blad zamiast ostrzezenia — ostrzezenie w logu przebiegu,
    # ktory i tak konczy sie zielono, jest ostrzezeniem dla nikogo.
    if r["przekroczony_warning"]:
        print(f"\n::error::PUNKT ZATRZYMANIA: po tej partii konfiguracja mialaby ~{r['atrybuty_spec']} "
              f"atrybutow ({r['procent_limitu']} % limitu), czyli powyzej progu {PROG_WARNING}. "
              f"Dzien pierwszy wszedlby od razu na warning budzetu, a zapas starczylby na kwartal. "
              f"Nie zaczynaj partii — najpierw zejdz z kosztu atrybutowego czlonka (kolejnosc dzwigni: "
              f"usuniecie regul nieuzywanych, kolaps regul profilowych do poziomu dywizji, konsolidacja "
              f"profili, baseline). Nie zapisalem nic.", file=sys.stderr)
        return 1

    # PARTIA PUSTA A PONOWIENIE — to sa DWA ROZNE stany i musza miec rozne kody wyjscia.
    #
    # Zero wpisow przy zerze pominietych znaczy, ze z calego inwentarza nie dalo sie wystawic ANI JEDNEGO
    # czlonka — zwykle dlatego, ze eksport CMDB nie niesie `owner_group` albo tabela folderow jest pusta.
    # To nie jest „partia bez zmian", to jest przelot, ktory nie wykonal swojej pracy, i musi byc
    # odrozniany kodem wyjscia: zielony przebieg z zerem wpisow zostalby przeczytany jako „gotowe".
    #
    # Zero wpisow przy niezerowej liczbie pominietych to co innego — wszyscy kandydaci sa juz w pliku,
    # czyli PONOWIENIE po awarii zrobilo dokladnie to, co mialo zrobic. Ten stan jest sukcesem i musi
    # nim byc, inaczej wznowienie po smierci `apply` konczyloby sie czerwonym przebiegiem za poprawne
    # zachowanie — a to uczy operatora ignorowac kod wyjscia tego narzedzia.
    if not wpisy and not pominiete:
        print(f"\n::error::PARTIA PUSTA: z {len(inwentarz)} projektow inwentarza nie powstal ani jeden "
              f"wpis, a zaden nie byl juz w pliku. Wszystkie {len(odmowy)} projektow odmowiono — "
              f"lista powodow wyzej. Najczestsza przyczyna: eksport CMDB bez `owner_group`/`profiles` "
              f"(zaden kanal po stronie chmury ich nie produkuje) albo pusta tabela folder->dywizja.",
              file=sys.stderr)
        return 1

    if args.tylko_podsumowanie:
        print("\n(--tylko-podsumowanie: nie zapisalem nic)")
        return 0

    for wpis in wpisy:
        projects_file.dopisz(args.root, wpis)
    print(f"\ndopisano {len(wpisy)} wpisow do {projects_file.SCIEZKA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
