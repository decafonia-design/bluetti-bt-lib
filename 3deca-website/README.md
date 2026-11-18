# 3deca.com: nieuwe website

Een volledig nieuwe, statische versie van www.3deca.com. Er is geen sitebuilder, database of plug-in nodig.
De map `public/` **is** de website. Je zet die map online en klaar.

## Wat er nieuw is

- **Donker, filmisch design** rond één idee: de site ziet eruit als een cameramonitor op de set.
  REC-lampje, lopende *time-of-day* tijdcode (25 fps) en audiometers die meebewegen als je scrolt.
- **Bestelmodule**: bezoekers kiezen producten, varianten en aantallen. Het subtotaal (ex btw) en een
  "verzendmeter" tot €130 (gratis EU-verzending) lopen live mee. Bij verzenden opent hun mailprogramma
  met de volledige bestelling ingevuld naar info@3deca.com, en er is een kopieerknop als dat niet lukt.
  Er is geen server of betaalsysteem nodig. Dat past bij "orders via contactform or email only".
- **Productpagina's** met grote foto, fotostrip, fotoviewer (pijltjestoetsen of vegen op telefoon), prijzen per
  optie en een knop "Add to order".
- **Toegankelijk**: getest met axe-core (WCAG 2.2 AA) zonder fouten, volledig met het toetsenbord te
  bedienen, een "skip to content"-link, alt-teksten bij elke foto, en de animaties staan uit als de
  bezoeker dat in zijn systeem heeft ingesteld.
- **Snel en privé**: foto's van 23 MB teruggebracht naar ±4,5 MB (WebP, twee formaten per foto). Lettertypes
  staan op de eigen server, dus geen Google Fonts. Geen cookies, geen trackers, dus ook geen cookiebanner nodig.
- **Vindbaar**: nette URL's (dezelfde als nu, bv. `/zmt-mount/`), meta-beschrijvingen, deelafbeelding voor
  sociale media, productgegevens voor Google (schema.org), `sitemap.xml` en `robots.txt`.

## Mappen

```
3deca-website/
├── content.json   ← alle teksten, prijzen, opties, reviews en alt-teksten
├── build.py       ← maakt de HTML-pagina's uit content.json
└── public/        ← de website (deze map zet je online)
    ├── index.html, 404.html, <product>/index.html
    ├── css/style.css, js/main.js
    ├── img/<product>/01-720.webp, 01-1600.webp, …
    ├── fonts/ (Archivo + JetBrains Mono, SIL Open Font License)
    └── .htaccess, robots.txt, sitemap.xml, favicon.svg
```

## Tekst of prijs aanpassen

1. Pas `content.json` aan (bijvoorbeeld `"price": 65`).
2. Voer `python3 build.py` uit. Dat heeft Python 3 en Pillow nodig (`pip install pillow`).
3. Zet de gewijzigde bestanden uit `public/` opnieuw online.

Wil je een foto toevoegen? Zet `NN-720.webp` en `NN-1600.webp` in `public/img/<product>/` en voeg
een alt-tekst toe aan de `images`-lijst van dat product in `content.json`.

## Online zetten

**Let op:** de huidige site draait op de *Combel Sitebuilder*. Daarin kun je geen eigen HTML-bestanden
uploaden. Je hebt dus één van deze twee opties:

### A. Combel webhosting (domein en hosting blijven bij Combel)
1. Neem bij Combel een gewoon webhostingpakket (Linux) in plaats van de Sitebuilder, of laat het omzetten.
2. Upload de **inhoud** van `public/`, inclusief het verborgen bestand `.htaccess`, naar de webmap
   (meestal `www` of `public_html`). Dat kan met FileZilla (FTP/SFTP) of met de bestandsbeheerder in je Combel-controlepaneel.
3. Klaar. Oude links zoals `/en/` sturen automatisch door naar de nieuwe homepage.

### B. Gratis statische hosting (domein blijft bij Combel)
1. Sleep de map `public/` naar bijvoorbeeld Netlify Drop of Cloudflare Pages.
2. Laat bij Combel de DNS van www.3deca.com naar die dienst wijzen (zij geven je de exacte records).

## Lokaal bekijken

```
cd public && python3 -m http.server 8000
```
Open daarna http://localhost:8000.

## Om na te kijken

- Op de oude site staat bij de NP-50-box zowel "Wisycom **LBP61**" als "Wisycom **MTP61** battery's".
  Op de nieuwe site staat overal LBP61. Klopt dat?
- De ZMT-mount krijgt de vermelding "rubber-coated magnet". Dat komt uit een review van een klant.
- De bestelmodule groet in de e-mail met "Hi Jan". Dat kun je aanpassen in `public/js/main.js`.
