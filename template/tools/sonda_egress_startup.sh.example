#!/bin/bash
# Startup-script maszyny sondujacej egress (patrz tools/sonda_egress_wewnetrzna.py).
#
# WYNIK IDZIE NA PORT SZEREGOWY, NIE PRZEZ SSH — i to nie jest wygoda, tylko warunek poprawnosci pomiaru.
# Odczyt serialu to wywolanie `compute.googleapis.com`, ktore NIE nalezy do `restricted_services`, wiec
# dziala z zewnatrz nawet przy w pelni egzekwowanej granicy. Dzieki temu pomiar nie potrzebuje reguly
# firewalla, klucza SSH ani wyjatku ingress dla operatora — czyli NIE ZMIENIA tego, co mierzy. Kazdy
# z tych trzech dodatkow byłby zmiana konfiguracji granicy wprowadzona po to, zeby granice zmierzyc.
#
# Maszyna stoi BEZ ADRESU ZEWNETRZNEGO, na podsieci z Private Google Access. Adres zewnetrzny nie jest
# potrzebny do wolania Google API i tylko poszerzalby powierzchnie tego, co maszyna moze zrobic.
#
# ODCZYT DOWODU:
#   gcloud compute instances get-serial-port-output <NAZWA> --project=<CZLONEK> --zone=<STREFA> \
#     | grep '@@SONDA'
#
# UWAGA PRZY POWTARZANIU PRZELOTU. `gcloud compute instances reset` uruchamia startup-script od nowa, ale
# DYSK ZOSTAJE — wszystko, co skrypt dopisal do systemu plikow w poprzednim rozruchu, nadal tam jest.
# Zmierzone: pierwszy przelot A/B byl niewazny, bo wpisy w `/etc/hosts` z poprzedniego rozruchu przezyly
# reset i maszyna dalej chodzila w trybie, ktory mial byc wylaczony. Stan ustawiany przez ten skrypt
# kasuj bezwarunkowo i dokladaj warunkowo, nigdy odwrotnie.
set -u
exec > >(tee /dev/console) 2>&1
echo "@@BOOT $(date -u +%FT%TZ)"

curl -sf -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/sonda-py > /opt/sonda.py
echo "@@SONDA-POBRANA $(wc -c < /opt/sonda.py) bajtow"
python3 /opt/sonda.py
