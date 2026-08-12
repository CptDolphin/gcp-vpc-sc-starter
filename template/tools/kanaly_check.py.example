#!/usr/bin/env python3
"""Czy alert `CRITICAL` ma jak dojść do odbiorcy — pytanie zadane tak, żeby dało się na nie odpowiedzieć.

DLACZEGO TO ISTNIEJE. Poprzednia procedura kazała operatorowi sprawdzić kolumnę `verificationStatus`:

    gcloud alpha monitoring channels list --project=<PROJEKT> \\
      --format='table(displayName,type,verificationStatus)'

Kolumna wraca PUSTA — i to nie jest usterka formatowania. Zmierzone na żywym API (trzy kanały, dwa typy):

  * `GET /v3/projects/<p>/notificationChannels/<id>` nie niesie klucza `verificationStatus` W OGÓLE;
  * jawna maska `?fields=name,type,verificationStatus` też go nie zwraca (czyli nie jest przycięty);
  * pozostałe pola tego samego odczytu (`type`, `displayName`, `enabled`) przychodzą poprawnie —
    kontrola pozytywna metody: odczyt DZIAŁA, brakuje wyłącznie tego jednego pola.

`verificationStatus` jest enumem proto3, więc wartość domyślna `VERIFICATION_STATUS_UNSPECIFIED`
nie serializuje się do JSON-a. Google opisuje tę wartość jako „stan nieznany, pominięty **albo
nieadekwatny** (kanały, które weryfikacji ani nie wspierają, ani nie wymagają)" — czyli PUSTE POLE
NIE ZNACZY „NIEZWERYFIKOWANY". Znaczy „nie wiesz".

Kontrola, która to rozstrzygnęła (i którą trzeba powtórzyć, zanim ktokolwiek wróci do tamtej komendy):
kanał e-mail założony jednorazowo przez API, a potem `:sendVerificationCode`. Gdyby kanał wymagał
weryfikacji, po zainicjowaniu procesu MUSIAŁBY stać w stanie `UNVERIFIED` — to wartość NIEDOMYŚLNA,
która serializuje się zawsze. Zmierzone: po `sendVerificationCode` (HTTP 200) pole **nadal nie istnieje**.
Nie ma więc wersji API ani formatu, w którym tamta komenda zaczyna odpowiadać na swoje pytanie.

CO ROBI TEN SKRYPT ZAMIAST TEGO. Zamienia pytanie „jaki jest status kanału" (na które API nie odpowiada)
na pytanie „czy da się UDOWODNIĆ, że powiadomienie tędy przechodzi" — per kanał i per polityka:

  DOWODLIWY        kanał, którego doręczenie potwierdza maszyna:
                   * `pubsub` — temat istnieje i agent powiadomień Monitoringu ma na nim `pubsub.publisher`;
                     odebraną wiadomość widać potem w subskrypcji, więc alert zostawia ślad do sprawdzenia;
                   * kanał w stanie `VERIFIED` — Google definiuje ten stan jako „udowodniono, że
                     powiadomienia mogą być na tym kanale odbierane".
  NIEROZSTRZYGNIETY kanał, o którego doręczalności API NIE MÓWI NIC (typowo `email`). To NIE jest „zepsuty"
                   i NIE jest „sprawny" — jedynym dowodem jest człowiek, który potwierdzi, że dostał
                   wiadomość. Procedura: `docs/7-alerty.md`, sekcja „Test negatywny".
  BŁĄD             kanał wpięty w politykę, którego NIE MA, albo odczyt się nie udał. Stanu „nie udało się
                   sprawdzić" nie zamiatamy pod OK — kontrola, która milczy o tym, czego nie odczytała,
                   jest gorsza od jej braku.

WERDYKT CAŁOŚCI dotyczy polityk `CRITICAL`: każda musi mieć **co najmniej jeden kanał DOWODLIWY**.
Powód jest ten sam, dla którego dead-man's-switch idzie niezależnym torem: alert, którego doręczenia
nikt nie umie sprawdzić, jest nieodróżnialny od alertu, którego nie ma — a wygląda na uzbrojony, bo
incydent widać w konsoli. `WARNING` nie podlega temu wymogowi świadomie: przy sygnale, który się czyta
w godzinach pracy, koszt kanału maszynowego przewyższa szkodę z jego braku.

CZTERY ODPOWIEDZI `:getVerificationCode`, KTÓRE TRZEBA UMIEĆ ROZRÓŻNIĆ (zmierzone; skrypt rozróżnia je
po TREŚCI, nie po samym kodzie HTTP, bo dwie różne sytuacje dają to samo `404`):

  200 + `code`                                     → kanał jest `VERIFIED`
  400 `Cannot generate a verification code from an unverified channel.`   → kanał NIE jest `VERIFIED`;
      NIE wynika z tego, że jest zablokowany — patrz akapit o `UNSPECIFIED` wyżej
  400 `Cannot generate verification codes for a channel of this type.`    → typ kanału weryfikacji nie zna
  404 JSON `Channel does not exist.`               → kanału NIE MA
  404 HTML (strona błędu Google, nie JSON)         → METODY nie ma pod tym adresem (zmiana API/literówka).
      To jest ta sama pułapka co nieistniejąca komenda `gcloud` z wygaszonym stderr: wygodne „zero wyników",
      które wygląda jak zdanie o świecie, a jest zdaniem o narzędziu.

Użycie:
    python3 tools/kanaly_check.py --project <PROJEKT_MONITORINGU>

Kody wyjścia (rozłączne, do użycia w bramce):
    0 = każda polityka CRITICAL ma kanał dowodliwy
    1 = któraś polityka CRITICAL go NIE MA (albo kanał wpięty w politykę nie istnieje)
    2 = nie udało się odczytać (brak poświadczeń, brak uprawnienia, API odpowiedziało inaczej niż umiemy)
    3 = błąd wywołania

Uprawnienia: `monitoring.notificationChannels.list`/`.get`, `monitoring.alertPolicies.list`
(`roles/monitoring.viewer`) oraz — dla sprawdzenia kanału `pubsub` — `pubsub.topics.getIamPolicy`.
Brak tego ostatniego degraduje pojedynczy kanał do BŁĘDU z podanym powodem, nigdy do cichego OK.
"""
import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://monitoring.googleapis.com/v3"

# Agent powiadomień Monitoringu — konto, które REALNIE publikuje na temat Pub/Sub. Sprawdzamy grant dla
# NIEGO, a nie dla tożsamości apply: temat może istnieć, polityka może go wskazywać, a powiadomienie i tak
# nie wyjdzie, jeśli tego jednego wiązania nie ma. Nazwa jest kontraktem Google i zależy od NUMERU projektu.
AGENT_POWIADOMIEN = "service-{numer}@gcp-sa-monitoring-notification.iam.gserviceaccount.com"

DOWODLIWY = "DOWODLIWY"
NIEROZSTRZYGNIETY = "NIEROZSTRZYGNIETY"
BLAD = "BŁĄD"


def gcloud(*args: str) -> str:
    p = subprocess.run(["gcloud", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"gcloud {' '.join(args)}: {p.stderr.strip()[:300]}")
    return p.stdout.strip()


def zadanie(url: str, token: str, projekt: str, metoda: str = "GET") -> tuple[int, str]:
    """Zwraca (kod HTTP, treść). Treść oddajemy SUROWĄ — rozróżnienie „nie ma metody" (HTML) od
    „nie ma zasobu" (JSON) niesie właśnie ona, a nie kod."""
    req = urllib.request.Request(url, method=metoda, data=b"{}" if metoda == "POST" else None)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("x-goog-user-project", projekt)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except OSError as e:  # sieć, DNS, timeout — NIE jest to odpowiedź „nie ma"
        return 0, f"<brak odpowiedzi: {e}>"


def komunikat(tresc: str) -> str:
    try:
        return json.loads(tresc).get("error", {}).get("message", "")
    except (json.JSONDecodeError, AttributeError):
        return ""


def sprawdz_email(nazwa: str, token: str, projekt: str) -> tuple[str, str]:
    kod, tresc = zadanie(f"{API}/{nazwa}:getVerificationCode", token, projekt, "POST")
    msg = komunikat(tresc)
    if kod == 200:
        return DOWODLIWY, "stan VERIFIED — Google potwierdza, że powiadomienia są tu odbierane"
    if kod == 400 and "unverified channel" in msg:
        return (NIEROZSTRZYGNIETY,
                "nie jest VERIFIED; API NIE MÓWI, czy dostarcza (pole verificationStatus nieobecne "
                "= stan nieznany LUB nieadekwatny). Dowodem jest wyłącznie człowiek — patrz test negatywny")
    if kod == 400 and "channel of this type" in msg:
        return NIEROZSTRZYGNIETY, "typ kanału nie zna weryfikacji; doręczalności API nie potwierdza"
    if kod == 404 and msg:
        return BLAD, f"kanał wpięty w politykę NIE ISTNIEJE ({msg})"
    if kod == 404:
        return BLAD, "metody :getVerificationCode NIE MA pod tym adresem — API się zmieniło, popraw skrypt"
    return BLAD, f"nierozpoznana odpowiedź HTTP {kod}: {(msg or tresc)[:120]}"


def sprawdz_pubsub(temat: str, numer: str) -> tuple[str, str]:
    if not temat:
        return BLAD, "kanał pubsub bez etykiety `topic`"
    agent = AGENT_POWIADOMIEN.format(numer=numer)
    try:
        surowe = gcloud("pubsub", "topics", "get-iam-policy", temat, "--format=json")
    except RuntimeError as e:
        return BLAD, f"nie udało się odczytać IAM tematu (to NIE znaczy „brak grantu”): {e}"
    polityka = json.loads(surowe or "{}")
    for wiazanie in polityka.get("bindings", []):
        if wiazanie.get("role") == "roles/pubsub.publisher" and \
           f"serviceAccount:{agent}" in wiazanie.get("members", []):
            return DOWODLIWY, "temat istnieje, agent powiadomień ma publisher; odbiór widać w subskrypcji"
    return BLAD, (f"temat istnieje, ale {agent} NIE MA roles/pubsub.publisher — "
                  "polityka wygląda na uzbrojoną, a powiadomienie nie wyjdzie")


def main() -> int:
    ap = argparse.ArgumentParser(description="Czy alert CRITICAL ma jak dojść do odbiorcy.")
    ap.add_argument("--project", required=True, help="projekt, w którym stoją metryki i alerty perimetru")
    args = ap.parse_args()
    projekt = args.project

    try:
        token = gcloud("auth", "print-access-token")
        numer = gcloud("projects", "describe", projekt, "--format=value(projectNumber)")
    except RuntimeError as e:
        print(f"NIE UDAŁO SIĘ ODCZYTAĆ: {e}", file=sys.stderr)
        return 2

    kod, tresc = zadanie(f"{API}/projects/{projekt}/notificationChannels?pageSize=200", token, projekt)
    if kod != 200:
        print(f"NIE UDAŁO SIĘ ODCZYTAĆ kanałów (HTTP {kod}): {komunikat(tresc) or tresc[:200]}", file=sys.stderr)
        return 2
    kanaly = json.loads(tresc).get("notificationChannels", [])

    kod, tresc = zadanie(f"{API}/projects/{projekt}/alertPolicies?pageSize=200", token, projekt)
    if kod != 200:
        print(f"NIE UDAŁO SIĘ ODCZYTAĆ polityk (HTTP {kod}): {komunikat(tresc) or tresc[:200]}", file=sys.stderr)
        return 2
    polityki = json.loads(tresc).get("alertPolicies", [])

    print("== kanały ==")
    werdykty: dict[str, tuple[str, str]] = {}
    for k in kanaly:
        nazwa, typ = k["name"], k.get("type", "?")
        if typ == "pubsub":
            werdykt = sprawdz_pubsub(k.get("labels", {}).get("topic", ""), numer)
        elif typ == "email":
            werdykt = sprawdz_email(nazwa, token, projekt)
        else:
            werdykt = (NIEROZSTRZYGNIETY, f"typu `{typ}` ten skrypt nie umie potwierdzić — dopisz obsługę")
        werdykty[nazwa] = werdykt
        # `enabled` to DRUGIE pole i DRUGI tryb awarii: kanał wyłączony nie dostarcza nic niezależnie
        # od tego, czy jest dowodliwy. Wypisujemy je zawsze, żeby nikt nie mylił obu pytań.
        wylaczony = "" if k.get("enabled", True) else "  [WYŁĄCZONY — nie dostarczy nic]"
        print(f"  {werdykt[0]:17} {typ:8} {k.get('displayName', '')[:44]:46}{wylaczony}")
        print(f"  {'':17} └─ {werdykt[1]}")

    print("\n== polityki ==")
    braki = 0
    for p in polityki:
        waga = p.get("severity", "<bez severity>")
        kanaly_p = p.get("notificationChannels", [])
        stany = [werdykty.get(c, (BLAD, "kanał spoza tego projektu — nieodczytany"))[0] for c in kanaly_p]
        ma_dowod = DOWODLIWY in stany
        if waga == "CRITICAL" and not ma_dowod:
            braki += 1
            znacznik = "BRAK DOWODU"
        elif BLAD in stany:
            braki += 1 if waga == "CRITICAL" else 0
            znacznik = "KANAŁ ZEPSUTY"
        else:
            znacznik = "ok" if ma_dowod else "—"
        print(f"  {znacznik:13} {waga:9} {p.get('displayName', '')[:52]:54} kanały: {len(kanaly_p)}")

    krytyczne = sum(1 for p in polityki if p.get("severity") == "CRITICAL")
    print(f"\npolityk: {len(polityki)} (CRITICAL: {krytyczne}), kanałów: {len(kanaly)}")
    if braki:
        print(f"WERDYKT: {braki} polityk(i) CRITICAL bez kanału, którego doręczenie da się udowodnić.")
        print("Alert, którego doręczenia nikt nie umie sprawdzić, jest nieodróżnialny od alertu, "
              "którego nie ma — a wygląda na uzbrojony, bo incydent widać w konsoli.")
        return 1
    print("WERDYKT: każda polityka CRITICAL ma co najmniej jeden kanał dowodliwy.")
    print("UWAGA: to NIE jest zdanie o skrzynkach e-mail. Ich doręczalności nie potwierdza żadne API —")
    print("potwierdza ją wyłącznie człowiek po teście negatywnym (`docs/7-alerty.md`).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(3)
