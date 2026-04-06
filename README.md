# Marek Tammets veebirakendus

Marek Tammetsa koduleht koos Resend-põhise päringuvormiga.

## Käivitamine

1. Kopeeri näidisfail:

```bash
cp .env.example .env
```

2. Lisa `.env` faili oma Resendi API võti.

3. Käivita server:

```bash
python3 app.py
```

4. Ava brauseris `http://127.0.0.1:8000`.

## Vajalikud muutujad

```bash
RESEND_API_KEY=...
RESEND_FROM_EMAIL=broneering@send.tammets.ee
RESEND_FROM_NAME=Tammets.ee
BOOKING_TO_EMAIL=marek@tammets.ee
BOOKING_REPLY_TO_EMAIL=marek@tammets.ee
```

`RESEND_FROM_EMAIL` peab kasutama täpselt seda domeeni või alamdomeeni, mille sa Resendis ära verifitseerid.

## Soovitatud Resendi seadistus

1. Lisa Resendi Domains vaates uus saatmise domeen.
2. Soovituslik variant on `send.tammets.ee`, mitte juurdomeen.
3. Lisa Resendi antud DNS kirjed oma domeeni haldusesse.
4. Oota kuni domeen muutub olekusse `verified`.
5. Loo API key, millel on `sending access`.
6. Pane API key `.env` faili väljale `RESEND_API_KEY`.

## Mis juhtub päringu saatmisel

- vorm saadab päringu Resendi API kaudu
- kiri jõuab aadressile `marek@tammets.ee`
- reply-to seatakse vormi täitja e-postile, nii et saad otse vastata

## Ülespanek `tammets.ee` alla Veebimajutuses

1. Ava serverisse SSH ühendus.
2. Liigu domeeni juurkausta:

```bash
cd /www/apache/domains/www.tammets.ee
```

3. Klooni repo serverisse:

```bash
git clone git@github.com:mtammets/tammets.git
```

4. Tee virtualenv ja paigalda FastCGI tugi:

```bash
python3.9 -m venv ~/.virtualenvs/website
source ~/.virtualenvs/website/bin/activate
pip install -r /www/apache/domains/www.tammets.ee/tammets/deployment/veebimajutus/requirements.txt
```

5. Lisa serveris faili `/www/apache/domains/www.tammets.ee/tammets/.env` oma päris väärtused.

6. Kopeeri FastCGI fail õigesse kohta:

```bash
mkdir -p ~/htdocs/cgi-bin
cp /www/apache/domains/www.tammets.ee/tammets/deployment/veebimajutus/dispatch.fcgi ~/htdocs/cgi-bin/dispatch.fcgi
chmod +x ~/htdocs/cgi-bin/dispatch.fcgi
```

7. Kopeeri rewrite reeglid:

```bash
cp /www/apache/domains/www.tammets.ee/tammets/deployment/veebimajutus/.htaccess ~/htdocs/.htaccess
```

8. Ava `https://tammets.ee`.

Kui muudatused kohe ei rakendu, taaskäivita FastCGI protsess:

```bash
pkill -f dispatch.fcgi
```
