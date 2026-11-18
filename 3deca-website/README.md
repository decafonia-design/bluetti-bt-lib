# 3deca.com: nieuwe website

Een volledig nieuwe, statische versie van www.3deca.com. Er is geen sitebuilder, database of plug-in nodig.
De map `public/` **is** de website. Je zet die map online en klaar.

## Wat er nieuw is

- **Donker, minimalistisch ontwerp**: bijna zwarte achtergrond, lichte dunne letter (Archivo), strak raster,
  kleine titels en geen effecten. Oranje komt alleen terug in het kleine logovierkantje. Producten hebben
  een productcode (3D-01 … 3D-07), zoals in een catalogus.
- **Echte productfoto's**: je eigen foto's, niet uitgeknipt. Elk product heeft een uitsnede in 4:3 met het
  product in het midden, en alle foto's hebben dezelfde ingetogen kleurbehandeling, zodat ze één reeks vormen.
  Ga je met de muis over een product, dan zie je het in gebruik op de set.
- **Zakelijk**: geen uitleg bij de producten, alleen een korte specificatietabel (past op, bevestiging,
  materiaal, …) op basis van de informatie van de oude site.
- **Collectie met filters** per systeem (Zaxcom, Sennheiser, batterijen), een rustige tegel "Need a different fit?"
  voor maatwerk, een strook "In use" met foto's van de set, een korte "About", reviews en een FAQ.
- **Productpagina's**: grote fotoviewer (studio- en setfoto's), keuzeknoppen per variant die de prijs live
  aanpassen, een aantalkeuze, "Add to order", en "Related products".
- **Bestelmodule**: bezoekers stellen een bestelling samen (met productcodes). Ze zien het subtotaal ex btw
  en hoeveel ze nog nodig hebben voor gratis EU-verzending. Bij verzenden opent hun mailprogramma met
  alles ingevuld.
- **Klaar voor een webshop**: vul betaallinks in `content.json` in en er verschijnt een knop "Buy now". Zie `WEBSHOP.md`.
- **Toegankelijk**: getest met axe-core (WCAG 2.2 AA) zonder fouten, volledig met het toetsenbord te
  bedienen, alt-teksten bij elke foto, en de animaties staan uit als de bezoeker dat in zijn systeem heeft ingesteld.
- **Snel en privé**: alle foto's samen zijn ±5 MB (WebP, twee formaten per foto). Lettertypes staan op de
  eigen server. Geen cookies, geen trackers, dus ook geen cookiebanner nodig.
- **Vindbaar**: dezelfde URL's als nu (bv. `/zmt-mount/`), productgegevens voor Google (schema.org,
  inclusief productcode), `sitemap.xml`, en een deelafbeelding voor sociale media.

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
een alt-tekst toe aan de `images`-lijst van dat product in `content.json`. De hoofdfoto van een
product heet `c-720.webp` / `c-1600.webp` (een uitsnede in 4:3); de alt-tekst staat in de `studio`-lijst.

## Online zetten (gratis, via GitHub Pages)

De site wordt gratis gehost door GitHub Pages, met HTTPS. Je domeinnaam en je e-mail blijven bij Combell.
Elke wijziging in `3deca-website/public/` die op de branch `ha-deployment` komt, zet GitHub automatisch
online (workflow `.github/workflows/pages-3deca.yml`).

### Eenmalig in GitHub
1. Voeg de pull request samen in `ha-deployment`.
2. Ga in de repository naar **Settings → Pages**, en kies bij **Source** voor **GitHub Actions**.
3. Start de workflow eenmalig: **Actions → Publish 3deca.com → Run workflow**.
4. Vul in **Settings → Pages** bij **Custom domain** `www.3deca.com` in. Vink **Enforce HTTPS** aan
   zodra GitHub dat toelaat (dat kan een tot enkele uren duren na de DNS-wijziging).

### Eenmalig bij Combell (DNS-beheer van 3deca.com)
Pas **alleen** deze records aan. Verwijder de bestaande A- en CNAME-records voor `3deca.com` en `www`
die naar de Sitebuilder wijzen, en zet er dit voor in de plaats:

| Type | Naam | Waarde |
|---|---|---|
| CNAME | `www` | `decafonia-design.github.io` |
| A | `@` (3deca.com) | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |

**Raak de MX-records en andere mailrecords (SPF/TXT, autodiscover, …) niet aan.** Die zorgen ervoor
dat info@3deca.com blijft werken.

### Daarna
- Werkt de nieuwe site op www.3deca.com, dan kun je het Sitebuilder-abonnement bij Combell opzeggen.
  **Kijk eerst na of je mailbox los staat van het Sitebuilder-pakket.** Zit de mail in hetzelfde pakket,
  verhuis die dan eerst naar een los mailproduct, anders valt je e-mail weg.
- Oude links zoals `/en/` sturen door naar de homepage. De productpagina's behouden hun oude adressen.

### Alternatief: Combell-webhosting
Wil je liever alles bij Combell, neem dan een gewoon (Linux-)webhostingpakket en upload de inhoud van
`public/`, inclusief `.htaccess`, naar de webmap via FTP. Dat kost wel een maandelijks bedrag.

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
- Lees de specificaties per product even na.
- Webshop: zie `WEBSHOP.md` voor de opties, kosten en mijn advies.
