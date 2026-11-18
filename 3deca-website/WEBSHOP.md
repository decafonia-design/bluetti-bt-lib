# Webshop voor 3deca.com: opties en advies

Nu bestellen klanten via het bestelformulier, dat een ingevulde e-mail maakt, of rechtstreeks per e-mail.
Dat werkt, maar de klant moet wachten op jouw bevestiging en betaalgegevens. Met een webshop betaalt de
klant meteen online.

De nieuwe site is daar al op voorbereid. Elke variant van een product heeft in `content.json` een veld
`checkout_url`. Vul je daar een betaallink in en voer je `python3 build.py` uit, dan verschijnt op die
productpagina automatisch een oranje knop **Buy now** naast "Add to order". Er is verder geen
programmeerwerk nodig.

## De opties

| Optie | Wat het is | Kosten (richtprijs, nakijken) | Winkelmandje | Werk |
|---|---|---|---|---|
| **A. Bestelformulier** (huidig) | Klant stelt bestelling samen, mail naar jou, jij stuurt een betaalverzoek | Gratis | Ja (via mail) | Geen |
| **B. Betaallinks** (Mollie of Stripe) | Per product/variant één link naar een betaalpagina | Geen abonnement, alleen kosten per betaling | Nee, één product per betaling | Klein |
| **C. Snipcart** | Winkelmandje en kassa bovenop deze site | ±2% per verkoop, met een minimum per maand bij lage omzet, plus de kosten van de betaalprovider | Ja | Middel |
| **D. Shopify** | Volledige webshop-dienst | Maandabonnement + transactiekosten | Ja | Middel (ontwerp opnieuw opbouwen) |
| **E. WooCommerce bij Combel** | WordPress-webshop op je eigen hosting | Hosting + plug-ins, gratis software | Ja | Groot (updates, beveiliging) |

Wat ik over de kosten vond (november 2026; controleer dit op de sites zelf):
- **Mollie** rekent per transactie, zonder abonnement. Betaallinks kosten volgens verschillende bronnen niets extra.
  Op Mollies prijspagina staat voor binnenlandse Belgische betalingen €0,39 per transactie. Een externe
  bron leest dat als het Bancontact-tarief, maar dat heb ik niet zelf bevestigd.
  ([Mollie pricing](https://www.mollie.com/pricing), [overzicht van externe bron](https://learnwithhasan.com/payment-gateways/mollie/))
- **Snipcart** rekent 2% per verkoop. Bij een lage omzet geldt volgens externe bronnen een vast
  minimum (genoemd: $20 per maand onder $1.000 omzet). Dat komt bovenop de kosten van de betaalprovider.
  ([Gappsy](https://gappsy.com/tools/snipcart/), [Toolradar](https://toolradar.com/tools/snipcart/pricing))
- **Shopify Starter** (alleen kassa en koopknoppen, geen eigen winkel) kost ±€5 per maand plus 5% + €0,25 per verkoop.
  Volgens één bron is het niet meer beschikbaar voor nieuwe winkels.
  ([Kanal](https://getkanal.com/fr/blog/shopify-starter-prix), [Style Factory](https://www.stylefactoryproductions.com/blog/shopify-starter-plan-review))

## Mijn advies

**Begin met optie B (Mollie-betaallinks) en houd het bestelformulier.**

- Je verkoopt een handvol producten in kleine aantallen, vaak aan professionals. Een abonnement of 2% extra loont dan niet.
- Mollie is een Europese betaalprovider en ondersteunt de betaalmethodes die je klanten gewend zijn:
  Bancontact, iDEAL, kaarten en meer.
- Standaardproducten (ZMT Mount, Battery Belt Clip, URX Sleeve, …) worden met één klik betaald.
- Maatwerk (andere bay-aantallen, Euronorm-inzet) blijft via het formulier lopen, want daar hoort een offerte bij.
- Groeit het en kopen klanten vaak meerdere producten tegelijk? Stap dan over naar **Snipcart** (optie C).
  Het ontwerp van de site blijft dan zoals het is, en het bestelformulier wordt een echt winkelmandje.

### Zo zet je optie B aan
1. Maak een Mollie-account (of Stripe) en maak per variant een betaallink aan, bijvoorbeeld
   "ZMT Mount, with magnet, €65".
2. Plak de link in `content.json` bij die variant:
   ```json
   { "label": "With magnet", "price": 65, "checkout_url": "https://..." }
   ```
   Voor producten zonder varianten (zoals de Sennheiser Belt Clip) vul je `checkout_url` in op productniveau.
3. Voer `python3 build.py` uit en upload `public/` opnieuw. De knop **Buy now** verschijnt en volgt de
   variant die de klant kiest.

## Wettelijke aandachtspunten (geen juridisch advies, laat dit nakijken)

- **Prijzen incl. btw voor consumenten.** De site toont nu prijzen ex btw, wat past bij verkoop aan
  bedrijven. Verkoop je via een webshop ook aan particulieren, dan moet de prijs die zij zien de btw
  bevatten ([Sufio over Belgische btw](https://sufio.com/articles/shopify/taxes/vat-eu-shopify/eu-taxes/belgian-taxes/)).
  Je kunt dan beide tonen: "€65 ex btw · €78,65 incl. 21% btw". Dat kan ik in de site inbouwen.
- **Btw bij verkoop in de EU.** Boven €10.000 per jaar aan particulieren in andere EU-landen geldt de btw
  van het land van de klant. Meestal regel je dat via het One-Stop-Shop-systeem (OSS).
- **Herroepingsrecht.** Particulieren mogen online aankopen binnen 14 dagen terugsturen. Producten die
  op maat volgens de specificaties van de klant gemaakt zijn, vallen daar meestal buiten. Sinds juli 2026
  moet een Belgische webshop ook een online herroepingsfunctie aanbieden
  ([CMS over de Belgische hervorming](https://cms.law/en/bel/legal-updates/belgian-consumer-law-reform-new-rules-on-online-sales-subscription-renewals-sustainability-claims-and-consumer-complaints)).
- **Algemene voorwaarden en privacyverklaring.** Voor een webshop heb je algemene voorwaarden nodig,
  met verzending, retour en garantie, en een privacyverklaring. Die pagina's kan ik toevoegen zodra je de inhoud kiest.

## Wat ik nodig heb om verder te gaan
- Je keuze: B (betaallinks), C (Snipcart) of nog even bij A blijven.
- Verkoop je ook aan particulieren? Dan voeg ik prijzen incl. btw toe.
- Voor B: de betaallinks per variant. Voor C: een Snipcart-account (publieke API-sleutel).
