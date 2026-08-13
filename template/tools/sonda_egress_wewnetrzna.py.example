#!/usr/bin/env python3
"""Sonda EGRESS uruchamiana WEWNATRZ perimetru — na maszynie w sieci VPC projektu czlonkowskiego.

PO CO OSOBNA SONDA, SKORO JEST `boundary-probe.yml`.
`boundary-probe.yml` wola z runnera CI, ktory jest spoza granicy z definicji — mierzy wiec wylacznie
INGRESS. Regula egress ocenia wywolanie, ktorego ZRODLO jest wewnatrz, a "wewnatrz" jest wlasnoscia SIECI,
nie tozsamosci. ZMIERZONE: konto serwisowe utworzone W projekcie czlonkowskim, impersonowane z zewnatrz
i wolajace chroniona usluge na TYM SAMYM projekcie, dostaje `ingressViolations` /
`NO_MATCHING_ACCESS_LEVEL`, `callerIp: "private"`, `callerNetwork: BRAK` — czyli jest liczone jako obce.
Nie istnieje wariant "pomiar egressu bez maszyny" i nie nalezy go szukac.

DRUGI WYNIK, WAZNY PRZY CZYTANIU `describe`: pusta lista regul egress (`status.egressPolicies: []`) znaczy
"ODMAWIAJ KAZDEGO WYJSCIA", a nie "egress nieegzekwowany". Regula egress jest WYJATKIEM od domyslnej
odmowy — dokument, ktory z `egress: 0` wnioskuje "nic nie chroni", mowi nieprawde o wlasnym systemie.

================================================================================================
TRZY STANY SWIATA, NIE DWA — I DLACZEGO POPRZEDNIA WERSJA TEGO PLIKU BYLA ATRAPA
================================================================================================
Poprzednia wersja wykonywala wywolania i DRUKOWALA ich wynik. Nie miala modelu oczekiwan, nie liczyla
niezgodnosci, nie zwracala werdyktu i nie miala niezerowego kodu wyjscia; petla byla nieskonczona, wiec
kodu wyjscia nie bylo GDZIE oddac. Skutek: przy nieistniejacym perimetrze, przy projekcie spoza granicy
albo w oknie swiezej sieci (patrz nizej) KAZDA sonda dostawala 200 i skrypt wypisywal `werdykt=PRZESZLO`
w kolko — output CO DO KSZTALTU nieodrozninalny od "regula egress, ktora wlasnie uzbroilem, przepuszcza
wywolanie". Instrument pomiarowy, ktory zawsze pokazuje wynik pozytywny, nie mierzy niczego.

Dlatego werdykt ma TRZY stany, nazwane osobno, i kazdy ma wlasny kod wyjscia:

  GRANICA-DZIALA     sonda jest wewnatrz, a wyjscia sa odmawiane zgodnie z modelem     -> 0 (gdy zgodne)
  GRANICA-NIE-DZIALA sonda jest POZA granica: nic nie jest odmawiane                   -> 1 (gdy niezgodne)
  NIE-ZMIERZONO      nie wiadomo — blad sieci, brak tokenu, wylaczone API, brak roli   -> 2 (zawsze)

`NIE-ZMIERZONO` NIGDY nie jest zielone. "Nie udalo sie zmierzyc" i "granica nie blokuje" to dwa rozne
zdania o swiecie i musza sie roznic TRESCIA, nie tylko kolorem.

WERDYKT Z TRESCI, NIE Z KODU. 403 zwraca odmowa VPC-SC, wylaczone API i brak roli IAM — trzy rozne stany
swiata, jeden kod. Klasyfikator nizej nazywa je osobno, tak samo jak `boundary-probe.yml`.

================================================================================================
CZWARTY STAN, KTORY JEST GORSZY OD "POZA GRANICA": OKNO SWIEZEJ SIECI
================================================================================================
Od utworzenia sieci VPC w projekcie bedacym czlonkiem konfiguracji EGZEKWOWANEJ uplywaja MINUTY, zanim
maszyna w tej sieci zaczyna byc traktowana jako "wewnatrz". W tym oknie wystepuje kombinacja, ktorej nie
ma w zadnym innym stanie: wywolanie na WLASNY projekt czlonkowski jest ODMAWIANE (bo dla granicy ta siec
jest obca), a wyjscia na zewnatrz PRZECHODZA. Czyli droga eksfiltracji jest przejezdna od konca do konca.
Sonda nazywa ten stan osobno (`OKNO-SWIEZEJ-SIECI`), zamiast raportowac go jako "poza granica" — bo to
NIE jest to samo i mylenie ich kosztuje najwiecej dokladnie wtedy, gdy boli najbardziej.

Konsekwencja operacyjna: po utworzeniu sieci ODCZEKAJ i POTWIERDZ przynaleznosc przelotem
`sonda-oczekiwanie=obserwacja`, zanim uznasz pomiar `wewnatrz-*` za wazny.

================================================================================================
MODEL OCZEKIWAN — `sonda-oczekiwanie`
================================================================================================
Macierz nizej jest cala teza tego pliku. Miedzy `wewnatrz-zamkniete` a `wewnatrz-otwarte` przelacza sie
DOKLADNIE JEDNA komorka; kazda inna zmiana znaczy, ze zmierzylismy cos innego niz regule. Kolumna
`poza-granica` jest KONTROLA ANTY-TAUTOLOGICZNA: to jest ten sam przelot na maszynie, ktora granicy nie
podlega, i musi dac INNY werdykt — inaczej "granica dziala" nie znaczy nic, bo nie widzielismy nigdy, zeby
nie dzialala.

  sonda               co izoluje                            wewnatrz-  wewnatrz-  poza-
                                                            zamkniete  otwarte    granica
  ------------------- ------------------------------------- ---------- ---------- ---------
  wewnatrz            PRZYNALEZNOSC: wnetrze -> wnetrze      PRZESZLO   PRZESZLO   PRZESZLO
  poza-uslugami       PRZYNALEZNOSC: usluga spoza
                      `vpcAccessibleServices.allowedServices`ODMOWA     ODMOWA     PRZESZLO
  egress-cel-metoda   metoda W regule, cel W regule          ODMOWA     PRZESZLO   PRZESZLO
  egress-cel-inna     metoda SPOZA reguly, ten sam cel       ODMOWA     ODMOWA     PRZESZLO
  izolacja-cel        metoda W regule, cel SPOZA reguly      ODMOWA     ODMOWA     PRZESZLO

`poza-uslugami` jest tu najwazniejsza i dlatego celuje we WLASNY projekt: nie zalezy od ZADNEJ reguly
ingress ani egress, wiec mierzy wylacznie to, czy wolajacy jest przypisany do sieci wewnatrz granicy.
Sonda celujaca w projekt CELU mieszalaby ten pomiar z pytaniem "czy cel jest na zewnatrz".

PULAPKA `poza-uslugami`. Dla ingressu "usluga spoza restricted_services ma nadal dzialac" jest poprawna
kontrola negatywna. DLA EGRESSU NIE JEST: przy `vpcAccessibleServices.enableRestriction: true` wywolanie
z wnetrza do uslugi spoza `allowedServices` dostaje `SERVICE_NOT_ALLOWED_FROM_VPC` — wpis, ktory NIE MA
ANI `ingressViolations`, ANI `egressViolations` (jest sam `violationReason`). Kazdy filtr pytajacy o ktoras
z tych tablic nie widzi tej klasy w ogole. Tutaj ta odmowa jest OCZEKIWANA, a nie awaria.

Czwarty tryb, `obserwacja`, nie ma oczekiwan i konczy sie zerem ZAWSZE — sluzy do mierzenia propagacji
(patrz nizej) i jego wypis mowi wprost, ze niczego nie dowodzi. Tryb bez oczekiwan, ktory udaje dowod,
byl dokladnie tym defektem, ktory ten plik naprawia.

================================================================================================
STAN GRANICY ODCZYTANY Z ACM — i dlaczego z wnetrza zwykle sie NIE UDA (to tez jest pomiar)
================================================================================================
`boundary-probe.yml` przypina swoj pomiar do rzeczywistosci, czytajac perimetr z API zanim cokolwiek
zasonduje. Ta sonda robi to samo, gdy poda sie `sonda-perimetr` — i wynik jest informacja w KAZDYM
z czterech przypadkow:

  200 + wlasny projekt w `status.resources`  granica istnieje i obejmuje mnie
  200 + wlasnego projektu NIE MA w `status`  granica istnieje, ale mnie nie obejmuje — odmow nie wolno
                                             przypisac granicy
  404                                        GRANICY NIE MA. To jest werdykt, a nie awaria kroku
  odmowa `SERVICE_NOT_ALLOWED_FROM_VPC`      ACM nie nalezy do `allowedServices`, wiec z wnetrza sie go
                                             NIE przeczyta — i wlasnie ta odmowa jest dowodem
                                             przynaleznosci; sonda mowi to wprost zamiast udawac awarie
  403 (IAM)                                  NIE WIADOMO — trzeci stan, nigdy "nie ma"

Odczyt ACM jest DODATKIEM, nie warunkiem: werdykt o granicy stawia RUCH (macierz wyzej), bo to ruch jest
rzecza, dla ktorej perimetr istnieje. Odczyt sluzy do tego, zeby powiedziec, CZEGO ten ruch dotyczyl.

PETLA, NIE JEDNORAZOWY PRZELOT. Rollback mierzy sie DWIEMA roznymi liczbami: czasem do zielonego apply
i czasem do zmiany zachowania RUCHU. Drugiej nie da sie dostac inaczej niz ciaglym wolaniem ze stemplem
czasu. Zmierzone na zywym ACM: uzbrojenie propaguje sie <= 8 s po apply, cofniecie 12-28 s — i propagacja
NIE JEST atomowa (zaobserwowane pojedyncze migotanie), wiec jeden przelot sondy nie jest dowodem. Petla
jest jednak SKONCZONA (`sonda-rundy`): nieskonczona nie ma gdzie oddac kodu wyjscia, wiec nie moze orzekac.

KONFIGURACJA — przez metadane instancji, zeby ten sam plik dzialal w kazdej organizacji:
  sonda-projekt-wewnatrz : projekt CZLONKOWSKI (ten, w ktorym stoi ta maszyna)
  sonda-projekt-cel      : projekt SPOZA perimetru wskazany w `egressTo.resources` mierzonej reguly
  sonda-kubelek-cel      : bucket w projekcie celu (metoda `objects.list` z reguly)
  sonda-kubelek-obcy     : bucket w projekcie, ktorego regula NIE wymienia (izolacja CELU)
  sonda-oczekiwanie      : wewnatrz-zamkniete | wewnatrz-otwarte | poza-granica | obserwacja
  sonda-rundy            : liczba rund (domyslnie 4; do pomiaru propagacji ustaw kilkaset)
  sonda-odstep           : odstep rund w sekundach (domyslnie 15)
  sonda-perimetr         : (opcjonalnie) `accessPolicies/<ID>/servicePerimeters/<NAZWA>` do odczytu z ACM
  sonda-baza-storage     : (opcjonalnie) baza API GCS — podmien na `https://restricted.googleapis.com`,
  sonda-baza-crm           zeby zmierzyc ten sam cel przez VIP `restricted` zamiast domyslnego
  sonda-baza-acm

DOWOD czytaj z portu szeregowego — `compute.googleapis.com` nie nalezy do `restricted_services`, wiec
serial czyta sie z zewnatrz nawet przy w pelni egzekwowanej granicy. Nie trzeba wiec ani reguly firewalla,
ani klucza SSH, ani wyjatku ingress dla operatora — czyli pomiar nie zmienia tego, co mierzy.
"""

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# `GCE_METADATA_HOST` jest konwencja bibliotek Google (google-auth respektuje ta sama zmienna), a nie
# furtka dopisana pod test. Dzieki niej selftest podstawia wlasny serwer i LICZY realne trafienia HTTP —
# czyli sprawdza, ze kod WOLAJACY istnieje i jest osiagalny, a nie ze plik sie parsuje. Dokladnie tego
# brakowalo wszystkim dotychczasowym bramkom, ktore ten plik przepuscily jako atrape.
HOST_METADANYCH = os.environ.get("GCE_METADATA_HOST", "metadata.google.internal")
METADATA = f"http://{HOST_METADANYCH}/computeMetadata/v1/instance/"

MARKERY_VPCSC = ("vpcServiceControlsUniqueIdentifier", "VPC_SERVICE_CONTROLS",
                 "Request is prohibited by organization's policy")
MARKERY_API_WYLACZONE = ("has not been used in project", "it is disabled",
                         "SERVICE_DISABLED", "API has not been used")
MARKERY_BRAK_ROLI = ("does not have permission", "Permission denied on resource",
                     "IAM_PERMISSION_DENIED", "caller does not have permission",
                     "serviceusage.services.use")
# `violationReason` bywa w tresci odpowiedzi, a bywa wylacznie we wpisie audytowym — zaleznie od uslugi
# i wersji API. Wypisujemy go, GDY jest, i nigdy nie uzalezniamy od niego werdyktu: bramka wymagajaca
# pola, ktore czasem nie przychodzi, zamienia poprawna odmowe w "padlo z innego powodu".
POWODY_VPCSC = ("NETWORK_NOT_IN_SAME_SERVICE_PERIMETER", "NO_MATCHING_ACCESS_LEVEL",
                "SERVICE_NOT_ALLOWED_FROM_VPC", "RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER")

PRZESZLO = "PRZESZLO"
ODMOWA = "ODMOWA-VPCSC"
# Werdykty rundy.
WEWNATRZ = "GRANICA-DZIALA"
POZA = "GRANICA-NIE-DZIALA"
OKNO = "OKNO-SWIEZEJ-SIECI"
NIEZMIERZONE = "NIE-ZMIERZONO"

# nazwa sondy -> werdykt oczekiwany w kazdym z trzech trybow (macierz z naglowka)
OCZEKIWANIA = {
    "wewnatrz-zamkniete": {"wewnatrz": PRZESZLO, "poza-uslugami": ODMOWA, "egress-cel-metoda": ODMOWA,
                           "egress-cel-inna": ODMOWA, "izolacja-cel": ODMOWA},
    "wewnatrz-otwarte":   {"wewnatrz": PRZESZLO, "poza-uslugami": ODMOWA, "egress-cel-metoda": PRZESZLO,
                           "egress-cel-inna": ODMOWA, "izolacja-cel": ODMOWA},
    "poza-granica":       {"wewnatrz": PRZESZLO, "poza-uslugami": PRZESZLO, "egress-cel-metoda": PRZESZLO,
                           "egress-cel-inna": PRZESZLO, "izolacja-cel": PRZESZLO},
}
TRYBY = tuple(OCZEKIWANIA) + ("obserwacja",)


def metadana(nazwa: str, domyslna: str = "") -> str:
    req = urllib.request.Request(METADATA + "attributes/" + nazwa,
                                 headers={"Metadata-Flavor": "Google"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode().strip()
    except Exception:
        return domyslna


def token() -> str:
    req = urllib.request.Request(METADATA + "service-accounts/default/token",
                                 headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["access_token"]


def wywolaj(url: str, tok: str) -> tuple[int, str]:
    """JEDYNE miejsce, w ktorym ta sonda dotyka sieci.

    Wydzielone celowo: dopoki transport byl wpleciony w petle wypisujaca, "czy sonda cokolwiek wola"
    dalo sie sprawdzic tylko czytaniem kodu — i nikt tego nie sprawdzil. Z jedna funkcja test podstawia
    ja i LICZY wywolania, wiec runda, ktora tylko drukuje, przestaje przechodzic testy.
    """
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        # Siec/DNS nazwane OSOBNO — blad transportu nie moze udawac odmowy granicy.
        return -1, f"BLAD-SIECI: {e!r}"


def klasyfikuj(kod: int, tresc: str) -> str:
    if kod == 200:
        return PRZESZLO
    if any(m in tresc for m in MARKERY_VPCSC) or any(p in tresc for p in POWODY_VPCSC):
        return ODMOWA
    if any(m in tresc for m in MARKERY_API_WYLACZONE):
        return "API-WYLACZONE"          # NIE jest dowodem na granice
    if any(m in tresc for m in MARKERY_BRAK_ROLI):
        return "BRAK-ROLI"              # NIE jest dowodem na granice
    if tresc.startswith("BLAD-SIECI"):
        return "BLAD-SIECI"             # NIE jest dowodem na granice
    return "PADLO-INNY-POWOD"


def powod(tresc: str) -> str:
    for p in POWODY_VPCSC:
        if p in tresc:
            return p
    return "-"


def identyfikator(tresc: str) -> str:
    """`vpcServiceControlsUniqueIdentifier` z odpowiedzi API = `vpcServiceControlsUniqueId` we wpisie
    audytowym. Tylko ta wartosc wiaze dwa zrodla dowodu z TYM SAMYM wywolaniem, a nie z "jakimis odmowami
    w oknie".

    CALE CIALO, NIE PIERWSZE N BAJTOW. Wersja czytajaca `read(4000)` ucinala identyfikator w polowie przy
    dluzszej odpowiedzi: sonda raportowala ODMOWE z id, ktorego w audit-logu nie bylo (66 znakow zamiast
    80, zero trafien w korelacji). Krok korelacyjny wygladalby wtedy na znalezisko "odmowa bez wpisu
    audytowego" — czyli bramka klamalaby o systemie zamiast o sobie.
    """
    if "vpcServiceControlsUniqueIdentifier" not in tresc:
        return "-"
    ogon = tresc.split("vpcServiceControlsUniqueIdentifier")[1].lstrip('":, ')
    return ogon.split('"')[0].split()[0].rstrip(".,") if ogon else "-"


def zbuduj_sondy() -> dict:
    wewnatrz = metadana("sonda-projekt-wewnatrz")
    cel = metadana("sonda-projekt-cel")
    kubelek_cel = metadana("sonda-kubelek-cel")
    kubelek_obcy = metadana("sonda-kubelek-obcy")
    gcs = metadana("sonda-baza-storage", "https://storage.googleapis.com").rstrip("/")
    crm = metadana("sonda-baza-crm", "https://cloudresourcemanager.googleapis.com").rstrip("/")
    brak = [n for n, v in (("sonda-projekt-wewnatrz", wewnatrz), ("sonda-projekt-cel", cel),
                           ("sonda-kubelek-cel", kubelek_cel)) if not v]
    if brak:
        raise SystemExit(f"@@SONDA-BLAD brak metadanych: {', '.join(brak)}")
    sondy = {
        "wewnatrz": f"{gcs}/storage/v1/b?project={wewnatrz}",
        # CEL = WLASNY projekt. Ta sonda ma mierzyc PRZYNALEZNOSC wolajacego do sieci wewnatrz granicy,
        # a nie polozenie celu; wskazanie projektu spoza granicy mieszaloby dwa pytania w jedna odpowiedz.
        "poza-uslugami": f"{crm}/v1/projects/{wewnatrz}",
        "egress-cel-metoda": f"{gcs}/storage/v1/b/{kubelek_cel}/o?maxResults=1",
        "egress-cel-inna": f"{gcs}/storage/v1/b?project={cel}",
    }
    if kubelek_obcy:
        sondy["izolacja-cel"] = f"{gcs}/storage/v1/b/{kubelek_obcy}/o?maxResults=1"
    return sondy


def stan_granicy(tok: str) -> str:
    """Odczyt perimetru z ACM — cztery rozne odpowiedzi, cztery rozne zdania (patrz naglowek).

    Zwraca linie do wypisania. NIE wywraca sondy: brak granicy jest WERDYKTEM, a nie awaria kroku, i to
    jest dokladnie ta roznica, ktorej brakowalo tez w `boundary-probe.yml`.
    """
    sciezka = metadana("sonda-perimetr")
    if not sciezka:
        return "@@SONDA-GRANICA stan=NIE-PYTANO (brak metadanej `sonda-perimetr`)"
    acm = metadana("sonda-baza-acm", "https://accesscontextmanager.googleapis.com").rstrip("/")
    wewnatrz = metadana("sonda-projekt-wewnatrz")
    kod, tresc = wywolaj(f"{acm}/v1/{sciezka}", tok)
    if kod == 404:
        return f"@@SONDA-GRANICA stan=BRAK http=404 perimetr={sciezka} (GRANICY NIE MA — to werdykt)"
    if kod == 200:
        try:
            zasoby = (json.loads(tresc).get("status") or {}).get("resources") or []
        except json.JSONDecodeError:
            return "@@SONDA-GRANICA stan=NIE-WIADOMO http=200 (odpowiedz nie jest JSON-em)"
        moj = any(str(wewnatrz) in z for z in zasoby)
        return (f"@@SONDA-GRANICA stan=ISTNIEJE czlonkow={len(zasoby)} moj_projekt_w_status={moj} "
                f"perimetr={sciezka}")
    kl = klasyfikuj(kod, tresc)
    if kl == ODMOWA:
        # To NIE jest awaria: ACM nie nalezy do `vpcAccessibleServices.allowedServices`, wiec z wnetrza
        # granicy nie da sie go przeczytac. Sama ta odmowa jest dowodem przynaleznosci do sieci wewnatrz.
        return (f"@@SONDA-GRANICA stan=NIEODCZYTYWALNY-Z-WNETRZA http={kod} powod={powod(tresc)} "
                f"(odmowa ACM = dowod przynaleznosci, nie awaria)")
    return f"@@SONDA-GRANICA stan=NIE-WIADOMO http={kod} klasyfikacja={kl}"


def runda(nr: int, tok: str, sondy: dict, tryb: str) -> tuple[str, list]:
    """Jedna runda: wola KAZDA sonde, klasyfikuje po TRESCI, orzeka o stanie swiata.

    Zwraca (werdykt_rundy, lista_niezgodnosci). Poprzednia wersja zwracala `None` i tylko drukowala —
    dlatego przy nieistniejacej granicy produkowala nieskonczona serie zielonych linii.
    """
    wyniki = {}
    for nazwa, url in sondy.items():
        kod, tresc = wywolaj(url, tok)
        wyniki[nazwa] = klasyfikuj(kod, tresc)
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"@@SONDA runda={nr} ts={ts} nazwa={nazwa} http={kod} "
              f"werdykt={wyniki[nazwa]} powod={powod(tresc)} vpcsc_id={identyfikator(tresc)}", flush=True)

    # --- 1. Czy w ogole DA SIE orzekac. Kazda klasa spoza {PRZESZLO, ODMOWA} znaczy, ze o granicy nie
    # dowiedzielismy sie nic — a to jest osobny stan, nie "granica nie blokuje".
    nieznane = {n: w for n, w in wyniki.items() if w not in (PRZESZLO, ODMOWA)}
    if nieznane:
        return NIEZMIERZONE, [f"{n}: {w} — to NIE jest zdanie o granicy" for n, w in nieznane.items()]

    # --- 2. Stan swiata czytany z PRZYNALEZNOSCI, niezaleznie od oczekiwan. `poza-uslugami` nie zalezy od
    # zadnej reguly, wiec rozstrzyga sam; `wewnatrz` dokłada rozroznienie okna swiezej sieci.
    przynaleznosc = wyniki["poza-uslugami"]
    wyjscia = [n for n in wyniki if n.startswith(("egress-", "izolacja-"))]
    if wyniki["wewnatrz"] == ODMOWA and przynaleznosc == PRZESZLO:
        stan = OKNO
    elif przynaleznosc == ODMOWA:
        stan = WEWNATRZ
    elif all(wyniki[n] == PRZESZLO for n in wyjscia):
        stan = POZA
    else:
        # Sprzecznosc: nie jestesmy przypisani do sieci wewnatrz, a mimo to cos jest odmawiane. Uśrednianie
        # takiej rundy byloby zgadywaniem — nazywamy ja niezmierzona.
        return NIEZMIERZONE, [f"wskazniki przynaleznosci sprzeczne: {wyniki}"]

    if tryb == "obserwacja":
        return stan, []

    oczekiwane = OCZEKIWANIA[tryb]
    bledy = [f"{n}: mialo byc {oczekiwane[n]}, jest {w}"
             for n, w in wyniki.items() if oczekiwane.get(n) and w != oczekiwane[n]]
    return stan, bledy


def main() -> None:
    tryb = metadana("sonda-oczekiwanie", "obserwacja") or "obserwacja"
    if tryb not in TRYBY:
        raise SystemExit(f"@@SONDA-BLAD nieznane `sonda-oczekiwanie`: {tryb} (dozwolone: {', '.join(TRYBY)})")
    sondy = zbuduj_sondy()
    odstep = int(metadana("sonda-odstep", "15") or "15")
    rundy = int(metadana("sonda-rundy", "4") or "4")
    print(f"@@SONDA-START {datetime.now(timezone.utc).isoformat()} sond={len(sondy)} tryb={tryb} "
          f"rund={rundy} odstep={odstep}s", flush=True)

    try:
        print(stan_granicy(token()), flush=True)
    except Exception as e:
        print(f"@@SONDA-GRANICA stan=NIE-WIADOMO blad-tokenu={e!r}", flush=True)

    # DWIE OSOBNE LISTY, BO TO DWA OSOBNE ZDANIA. `niezgodne` zbiera rozjazdy z rund, ktore UDALO SIE
    # zmierzyc; `niepewne` — powody, dla ktorych rundy zmierzyc sie nie dalo. Zwiniecie ich w jedna liste
    # daloby werdykt "granica zachowuje sie inaczej, niz oczekiwano" przy zerwanej sieci, czyli zdanie
    # o granicy postawione na danych, ktorych nie ma.
    stany, niezgodne, niepewne, bez_tokenu = [], [], [], 0
    for nr in range(1, rundy + 1):
        try:
            tok = token()
        except Exception as e:
            # Brak tokenu to "nie wiadomo", nie "przeszlo" — i musi zostac policzony, a nie tylko wypisany.
            print(f"@@SONDA runda={nr} werdykt={NIEZMIERZONE} BLAD-TOKENU {e!r}", flush=True)
            bez_tokenu += 1
            stany.append(NIEZMIERZONE)
            niepewne.append((nr, NIEZMIERZONE, [f"BLAD-TOKENU {e!r}"]))
            if nr < rundy:
                time.sleep(odstep)
            continue
        stan, uwagi = runda(nr, tok, sondy, tryb)
        stany.append(stan)
        if uwagi:
            (niepewne if stan == NIEZMIERZONE else niezgodne).append((nr, stan, uwagi))
        print(f"@@SONDA-RUNDA nr={nr} stan={stan} uwag={len(uwagi)}", flush=True)
        if nr < rundy:
            time.sleep(odstep)

    # WERDYKT KONCOWY. Migotanie stanu miedzy rundami jest ZMIERZONYM zachowaniem propagacji, a nie
    # szumem do usredniania — raportujemy je jawnie, bo jedna runda "PRZESZLO" nie jest dowodem.
    unikalne = sorted(set(stany))
    dominujacy = max(unikalne, key=stany.count) if stany else NIEZMIERZONE
    niezmierzone = stany.count(NIEZMIERZONE)
    for nr, stan, uwagi in niezgodne:
        for u in uwagi:
            print(f"@@SONDA-NIEZGODNOSC runda={nr} stan={stan} {u}", flush=True)
    for nr, stan, uwagi in niepewne:
        for u in uwagi:
            print(f"@@SONDA-NIEPEWNOSC runda={nr} stan={stan} {u}", flush=True)

    if tryb == "obserwacja":
        kod = 0
        slowo = "OBSERWACJA (bez oczekiwania — ten przelot NICZEGO nie dowodzi)"
    elif niezgodne:
        kod = 1
        slowo = f"NIEZGODNE Z OCZEKIWANIEM `{tryb}`"
    elif niezmierzone:
        kod = 2
        slowo = "NIE-ZMIERZONO (nie wiadomo, czy granica dziala)"
    else:
        kod = 0
        slowo = f"ZGODNE Z OCZEKIWANIEM `{tryb}`"

    print(f"@@SONDA-WERDYKT tryb={tryb} stan={dominujacy} stany={','.join(unikalne)} "
          f"rund={len(stany)} niezgodnych={len(niezgodne)} niezmierzonych={niezmierzone} "
          f"bez_tokenu={bez_tokenu} exit={kod} :: {slowo}", flush=True)
    sys.exit(kod)


if __name__ == "__main__":
    main()
