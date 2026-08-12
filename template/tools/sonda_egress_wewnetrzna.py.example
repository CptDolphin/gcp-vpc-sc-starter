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

MACIERZ. Po uzbrojeniu mierzonej reguly ma sie przelaczyc DOKLADNIE JEDNA komorka. Kazda inna zmiana
znaczy, ze zmierzylismy cos innego niz regule:

  wewnatrz            wnetrze -> wnetrze                   PRZESZLO -> PRZESZLO  (kontrola pozytywna)
  egress-cel-metoda   metoda W regule, cel W regule        ODMOWA   -> PRZESZLO  (POMIAR)
  egress-cel-inna     metoda SPOZA reguly, ten sam cel     ODMOWA   -> ODMOWA    (izolacja METODY)
  izolacja-cel        metoda W regule, cel SPOZA reguly    ODMOWA   -> ODMOWA    (izolacja CELU)
  poza-restricted     usluga spoza restricted_services     zaleznie  (patrz nizej)

Trzy srodkowe wiersze to kontrola anty-tautologiczna: gdyby po uzbrojeniu przechodzilo WSZYSTKO, znaczyloby
to, ze egress przestal byc egzekwowany, a nie ze regula zadzialala.

PULAPKA `poza-restricted`. Dla ingressu "usluga spoza restricted_services ma nadal dzialac" jest poprawna
kontrola negatywna. DLA EGRESSU NIE JEST: przy `vpcAccessibleServices.enableRestriction: true` wywolanie
z wnetrza do uslugi spoza `allowedServices` dostaje `SERVICE_NOT_ALLOWED_FROM_VPC` — wpis, ktory NIE MA
ANI `ingressViolations`, ANI `egressViolations` (jest sam `violationReason`). Kazdy filtr pytajacy o ktoras
z tych tablic nie widzi tej klasy w ogole.

WERDYKT Z TRESCI, NIE Z KODU. 403 zwraca odmowa VPC-SC, wylaczone API i brak roli IAM — trzy rozne stany
swiata, jeden kod. Klasyfikator nizej nazywa je osobno, tak samo jak `boundary-probe.yml`.

PETLA, NIE JEDNORAZOWY PRZELOT. Rollback mierzy sie DWIEMA roznymi liczbami: czasem do zielonego apply
i czasem do zmiany zachowania RUCHU. Drugiej nie da sie dostac inaczej niz ciaglym wolaniem ze stemplem
czasu. Zmierzone na zywym ACM: uzbrojenie propaguje sie <= 8 s po apply, cofniecie 12-28 s — i propagacja
NIE JEST atomowa (zaobserwowane pojedyncze migotanie), wiec jeden przelot sondy nie jest dowodem.

KONFIGURACJA — przez metadane instancji, zeby ten sam plik dzialal w kazdej organizacji:
  sonda-projekt-wewnatrz : projekt CZLONKOWSKI (ten, w ktorym stoi ta maszyna)
  sonda-projekt-cel      : projekt SPOZA perimetru wskazany w `egressTo.resources` mierzonej reguly
  sonda-kubelek-cel      : bucket w projekcie celu (metoda `objects.list` z reguly)
  sonda-kubelek-obcy     : bucket w projekcie, ktorego regula NIE wymienia (izolacja CELU)
  sonda-odstep           : odstep rund w sekundach (domyslnie 15)

DOWOD czytaj z portu szeregowego — `compute.googleapis.com` nie nalezy do `restricted_services`, wiec
serial czyta sie z zewnatrz nawet przy w pelni egzekwowanej granicy. Nie trzeba wiec ani reguly firewalla,
ani klucza SSH, ani wyjatku ingress dla operatora — czyli pomiar nie zmienia tego, co mierzy.
"""

import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

METADATA = "http://metadata.google.internal/computeMetadata/v1/instance/"

MARKERY_VPCSC = ("vpcServiceControlsUniqueIdentifier", "VPC_SERVICE_CONTROLS",
                 "Request is prohibited by organization's policy")
MARKERY_API_WYLACZONE = ("has not been used in project", "it is disabled",
                         "SERVICE_DISABLED", "API has not been used")
MARKERY_BRAK_ROLI = ("does not have permission", "Permission denied on resource",
                     "IAM_PERMISSION_DENIED", "caller does not have permission",
                     "serviceusage.services.use")


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


def klasyfikuj(kod: int, tresc: str) -> str:
    if kod == 200:
        return "PRZESZLO"
    if any(m in tresc for m in MARKERY_VPCSC):
        return "ODMOWA-VPCSC"
    if any(m in tresc for m in MARKERY_API_WYLACZONE):
        return "API-WYLACZONE"          # NIE jest dowodem na granice
    if any(m in tresc for m in MARKERY_BRAK_ROLI):
        return "BRAK-ROLI"              # NIE jest dowodem na granice
    return "PADLO-INNY-POWOD"


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
    brak = [n for n, v in (("sonda-projekt-wewnatrz", wewnatrz), ("sonda-projekt-cel", cel),
                           ("sonda-kubelek-cel", kubelek_cel)) if not v]
    if brak:
        raise SystemExit(f"@@SONDA-BLAD brak metadanych: {', '.join(brak)}")
    sondy = {
        "wewnatrz": f"https://storage.googleapis.com/storage/v1/b?project={wewnatrz}",
        "egress-cel-metoda": f"https://storage.googleapis.com/storage/v1/b/{kubelek_cel}/o?maxResults=1",
        "egress-cel-inna": f"https://storage.googleapis.com/storage/v1/b?project={cel}",
        "poza-restricted": f"https://cloudresourcemanager.googleapis.com/v1/projects/{cel}",
    }
    if kubelek_obcy:
        sondy["izolacja-cel"] = f"https://storage.googleapis.com/storage/v1/b/{kubelek_obcy}/o?maxResults=1"
    return sondy


def runda(nr: int, tok: str, sondy: dict) -> None:
    ctx = ssl.create_default_context()
    for nazwa, url in sondy.items():
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        try:
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                kod, tresc = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            kod, tresc = e.code, e.read().decode("utf-8", "replace")
        except Exception as e:
            # Siec/DNS nazwane OSOBNO — blad transportu nie moze udawac odmowy granicy.
            kod, tresc = -1, f"BLAD-SIECI: {e!r}"
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"@@SONDA runda={nr} ts={ts} nazwa={nazwa} http={kod} "
              f"werdykt={klasyfikuj(kod, tresc)} vpcsc_id={identyfikator(tresc)}", flush=True)


def main() -> None:
    sondy = zbuduj_sondy()
    odstep = int(metadana("sonda-odstep", "15") or "15")
    print(f"@@SONDA-START {datetime.now(timezone.utc).isoformat()} sond={len(sondy)} odstep={odstep}s",
          flush=True)
    nr = 0
    while True:
        nr += 1
        try:
            tok = token()
        except Exception as e:
            print(f"@@SONDA runda={nr} BLAD-TOKENU {e!r}", flush=True)
            time.sleep(odstep)
            continue
        runda(nr, tok, sondy)
        time.sleep(odstep)


if __name__ == "__main__":
    main()
