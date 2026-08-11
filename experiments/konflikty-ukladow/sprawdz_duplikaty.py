#!/usr/bin/env python3
"""Bramka duplikatów dla JEDNOPLIKOWEJ listy projektów perimetru (`perimeter/projects.yaml`).

CZYM TO JEST: samodzielny odpowiednik bramki, żeby eksperyment dało się uruchomić bez reszty repozytorium.
CZYM NIE JEST: tą samą bramką, która jedzie w materiale. Tam duplikaty łapią reguły `policy/onboarding.rego`
(`m1.project_number == m2.project_number`, `m1.project_id == m2.project_id`) puszczane conftestem na
plan-JSON, a kształt wpisu pilnuje `schemas/member.schema.json`. Ten skrypt sprawdza TE SAME cztery
własności na pliku YAML, ale niczego o tamtych regułach nie dowodzi — jest tu po to, żeby wynik wariantu
B-edit („union scala i zostawia rozjechany wpis") dało się pokazać jako CZERWONĄ bramkę, a nie jako opinię.

    python3 sprawdz_duplikaty.py <plik.yaml>

Kod wyjścia: 0 = czysto, 1 = naruszenia (wypisane na stdout), 2 = błąd użycia albo brak pyyaml.

CZTERY REGUŁY, każda na inny tryb awarii jednoplikowej listy:

  1. DUPLIKAT KLUCZA MAPY na dowolnym poziomie. To jest reguła, bez której cały skrypt byłby ozdobą:
     `yaml.safe_load` na mapie z powtórzonym kluczem NIE zgłasza błędu — CICHO bierze ostatnie wystąpienie.
     Sterownik `merge=union` scalający dwie edycje tego samego wpisu produkuje dokładnie taki plik
     (powtórzone `stage:`/`owner_group:` wewnątrz jednego elementu listy), więc walidator zbudowany na
     `safe_load` przeczytałby go bez mrugnięcia, wybrał jedną z dwóch wartości i przepuścił do renderera.
     Stąd własna podklasa `SafeLoader` z nadpisanym `construct_mapping` — biblioteka nie ma na to opcji.
  2. Ten sam `project_id` w dwóch wpisach.
  3. Ten sam `project_number` w dwóch wpisach — ACM adresuje projekty NUMEREM, więc to jest właściwy
     identyfikator kolizji; dwa wpisy z tym samym numerem to dwóch właścicieli jednego zasobu ACM.
  4. Ten sam klucz `<division>-<project_id>` — to jest klucz `for_each` renderera. Dwa wpisy dające ten sam
     klucz nie są „duplikatem w dokumentacji": Terraform dostaje dwa razy ten sam adres zasobu.

ŚWIADOME OGRANICZENIE: klucze mapy porównujemy jako parę (tag YAML, tekst), więc `1:` (int) i `"1":` (str)
są traktowane jako RÓŻNE — zgodnie z YAML-em. Kluczy scalających (`<<`) ten format nie używa i skrypt ich
nie wyróżnia; gdyby się pojawiły, drugie `<<` w tej samej mapie zostanie zgłoszone jako duplikat.
"""

import pathlib
import sys

try:
    import yaml
except ImportError:  # pyyaml jest jedyną zależnością spoza stdlib — powiedz to wprost, zamiast rzucać traceback
    print("brak pyyaml — zainstaluj: python3 -m pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)


class LoaderBezDuplikatow(yaml.SafeLoader):
    """SafeLoader, który na duplikacie klucza mapy PADA, zamiast po cichu brać ostatni.

    Nadpisujemy `construct_mapping`, bo woła go każdy węzeł mapy — także zagnieżdżony i w składni flow
    (`{a: 1, a: 2}`). Duplikaty liczymy na WĘZŁACH, przed zbudowaniem obiektów: budowanie klucza dwa razy
    (raz na potrzeby sprawdzenia, raz w `super()`) psułoby kotwice i referencje.
    """

    def construct_mapping(self, node, deep=False):
        widziane = set()
        for klucz_node, _ in node.value:
            if isinstance(klucz_node, yaml.ScalarNode):
                # Tag rozróżnia `1:` od `"1":` — bez niego bramka zgłaszałaby duplikat tam, gdzie YAML widzi
                # dwa różne klucze, czyli byłaby fałszywie czerwona na poprawnym pliku.
                odcisk = (klucz_node.tag, klucz_node.value)
            else:
                odcisk = ("!zlozony", repr(self.construct_object(klucz_node, deep=True)))
            if odcisk in widziane:
                raise yaml.constructor.ConstructorError(
                    "podczas budowania mapy",
                    node.start_mark,
                    f"duplikat klucza {klucz_node.value!r}",
                    klucz_node.start_mark,
                )
            widziane.add(odcisk)
        return super().construct_mapping(node, deep)


def wczytaj(sciezka):
    """Zwraca (lista_wpisow, naruszenia). Błąd parsowania JEST naruszeniem, nie wyjątkiem do góry."""
    try:
        tekst = pathlib.Path(sciezka).read_text(encoding="utf-8")
    except OSError as e:
        return [], [f"nie da się odczytać {sciezka}: {e}"]
    try:
        dokument = yaml.load(tekst, Loader=LoaderBezDuplikatow)
    except yaml.YAMLError as e:
        # Duplikat klucza wychodzi tędy. Komunikat pyyaml niesie numer linii — nie skracaj go.
        return [], [f"plik nie jest poprawnym YAML-em: {str(e).strip()}"]

    # Dwa akceptowane kształty: goła lista wpisów albo mapa z listą pod `members:`. Renderer czyta drugi,
    # ale eksperyment ma działać też na wycinku wklejonym do pliku bez nagłówka.
    if isinstance(dokument, list):
        return dokument, []
    if isinstance(dokument, dict) and isinstance(dokument.get("members"), list):
        return dokument["members"], []
    return [], [f"{sciezka}: nierozpoznany kształt — oczekiwano listy wpisów albo mapy z kluczem `members:`"]


def duplikaty_pola(wpisy, pole):
    """Zwraca listę komunikatów o wpisach dzielących wartość `pole`. Wpisy bez tego pola pomijamy —
    od braku wymaganych pól jest schemat, nie ta bramka (jedna bramka = jeden tryb awarii)."""
    po_wartosci = {}
    for idx, wpis in enumerate(wpisy):
        if not isinstance(wpis, dict) or pole not in wpis:
            continue
        po_wartosci.setdefault(str(wpis[pole]), []).append(idx)
    return [
        f"pole {pole}={wartosc!r} występuje w {len(idxs)} wpisach (indeksy: {', '.join(str(i) for i in idxs)})"
        for wartosc, idxs in sorted(po_wartosci.items())
        if len(idxs) > 1
    ]


def duplikaty_klucza_for_each(wpisy):
    """`<division>-<project_id>` to klucz `for_each` renderera — kolizja tutaj to dwa razy ten sam ADRES
    zasobu w stanie Terraform, czyli awaria twardsza niż niespójność w dokumencie."""
    po_kluczu = {}
    for idx, wpis in enumerate(wpisy):
        if not isinstance(wpis, dict):
            continue
        if "division" in wpis and "project_id" in wpis:
            po_kluczu.setdefault(f"{wpis['division']}-{wpis['project_id']}", []).append(idx)
    return [
        f"klucz for_each {klucz!r} powstaje z {len(idxs)} wpisów (indeksy: {', '.join(str(i) for i in idxs)})"
        for klucz, idxs in sorted(po_kluczu.items())
        if len(idxs) > 1
    ]


def sprawdz(sciezka):
    """Zwraca listę naruszeń (pustą = czysto)."""
    wpisy, naruszenia = wczytaj(sciezka)
    if naruszenia:
        return naruszenia
    naruszenia += duplikaty_pola(wpisy, "project_id")
    naruszenia += duplikaty_pola(wpisy, "project_number")
    naruszenia += duplikaty_klucza_for_each(wpisy)
    return naruszenia


def main(argv):
    if len(argv) != 2:
        print(f"uzycie: {argv[0]} <plik.yaml>")
        return 2
    naruszenia = sprawdz(argv[1])
    if not naruszenia:
        print(f"{argv[1]}: czysto — brak duplikatów")
        return 0
    print(f"{argv[1]}: {len(naruszenia)} naruszen")
    for n in naruszenia:
        print(f"  {n}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
