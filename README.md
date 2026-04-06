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
