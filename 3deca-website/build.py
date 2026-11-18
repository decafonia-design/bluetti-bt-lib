#!/usr/bin/env python3
"""Build the static 3deca.com website.

Reads content.json and writes the HTML pages into public/.
Everything in public/ is the finished website: upload that folder as-is.

    python3 build.py            # normal build: pretty URLs (/zmt-mount/)
    python3 build.py --preview  # links point at index.html files, for
                                # opening the site straight from disk

Needs Python 3.8+ and Pillow (only to read image sizes).
"""

import datetime
import html
import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
PREVIEW = "--preview" in sys.argv
# --out DIR writes the HTML somewhere else (used for previews); assets stay in public/.
OUT = Path(sys.argv[sys.argv.index("--out") + 1]).resolve() if "--out" in sys.argv else PUBLIC

C = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
SITE = C["site"]
PRODUCTS = C["products"]
YEAR = datetime.date.today().year


def e(text):
    """Escape text for HTML."""
    return html.escape(str(text), quote=True)


def euro(amount):
    return f"€{amount:g}"


def choice_price(c):
    if c.get("price") is None:
        return "on request"
    return ("from " if c.get("from") else "") + euro(c["price"])


def price_label(p):
    return ("from " if p.get("price_from") else "") + euro(p["price"])


def home_href(root):
    return root + ("index.html" if PREVIEW else "") if root else ("index.html" if PREVIEW else "./")


def product_href(root, slug):
    return f"{root}{slug}/" + ("index.html" if PREVIEW else "")


_size_cache = {}


def img_size(rel):
    if rel not in _size_cache:
        with Image.open(PUBLIC / "img" / rel) as im:
            _size_cache[rel] = im.size
    return _size_cache[rel]


def picture(root, key, alt, sizes, cls="", eager=False):
    """Responsive <img> for an image key like 'zmt-mount/03'."""
    small, large = f"{key}-720.webp", f"{key}-1600.webp"
    sw, _ = img_size(small)
    lw, lh = img_size(large)
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    cls_attr = f' class="{cls}"' if cls else ""
    return (
        f'<img{cls_attr} src="{root}img/{large}" '
        f'srcset="{root}img/{small} {sw}w, {root}img/{large} {lw}w" '
        f'sizes="{sizes}" width="{lw}" height="{lh}" alt="{e(alt)}" '
        f'{load} decoding="async">'
    )


# --------------------------------------------------------------------------
# Shared page chrome
# --------------------------------------------------------------------------

WORDMARK = (
    '<span class="wm" aria-hidden="true"><span class="wm-dot"></span>'
    '<span class="wm-3d">3D</span><span class="wm-eca">eca</span></span>'
)


def head(root, title, description, canonical, extra=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">
<meta name="theme-color" content="#0a0a0b">
<meta name="color-scheme" content="dark">
<meta property="og:type" content="website">
<meta property="og:site_name" content="3Deca">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{e(SITE['url'])}/img/og-image.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<link rel="preload" href="{root}fonts/archivo-var.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{root}css/style.css">
<script>document.documentElement.classList.add("js")</script>
<script src="{root}js/main.js" defer></script>
{extra}</head>
"""


def header(root, current=""):
    home = home_href(root)
    links = [("gear", "Gear"), ("about", "About"), ("reviews", "Reviews"), ("ordering", "Ordering")]
    items = "".join(
        f'<li><a href="{home}#{a}"{" aria-current=\"page\"" if current == a else ""}>{t}</a></li>'
        for a, t in links
    )
    return f"""<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header" data-header>
  <div class="header-inner">
    <a class="brand" href="{home}" aria-label="3Deca, home">{WORDMARK}</a>
    <nav class="site-nav" id="site-nav" aria-label="Main">
      <ul>{items}</ul>
    </nav>
    <a class="btn btn-accent btn-sm header-cta" href="{home}#order">
      Order<span class="order-count" data-order-count hidden></span>
    </a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav" data-nav-toggle>
      <span class="sr-only">Menu</span><span class="nav-toggle-bars" aria-hidden="true"></span>
    </button>
  </div>
</header>
"""


def footer(root):
    home = home_href(root)
    gear = "".join(
        f'<li><a href="{product_href(root, p["slug"])}">{e(p["name"])}</a></li>' for p in PRODUCTS
    )
    return f"""<footer class="site-footer">
  <div class="container">
    <div class="footer-top">
      <a class="footer-mark" href="{home}" aria-label="3Deca, home">{WORDMARK}</a>
      <p class="footer-claim">Set gear by a sound mixer, for sound mixers.</p>
    </div>
    <div class="footer-grid">
      <div>
        <h2 class="footer-h">Contact</h2>
        <p><a class="footer-mail" href="mailto:{SITE['email']}">{SITE['email']}</a></p>
        <p>Questions, suggestions or a custom build? Mail me.</p>
      </div>
      <div>
        <h2 class="footer-h">Gear</h2>
        <ul class="footer-list">{gear}</ul>
      </div>
      <div>
        <h2 class="footer-h">Good to know</h2>
        <ul class="footer-list">
          <li>Prices ex VAT</li>
          <li>Free EU shipping above {euro(SITE['free_shipping_threshold'])}</li>
          <li>Commercial invoice on request</li>
          <li><a href="{SITE['imdb']}" rel="noopener">{SITE['owner']} on IMDb</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <p>© 2023–{YEAR} {SITE['owner']} · 3Deca</p>
      <p>No cookies. No trackers. Just gear.</p>
    </div>
  </div>
</footer>
"""


def json_ld(data):
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n'


def hud(label_left="SC 3D · TK 01"):
    """The camera-monitor overlay (decorative)."""
    meter = '<span class="meter" data-meter><span class="meter-fill"></span></span>'
    return f"""<div class="hud" aria-hidden="true">
      <span class="hud-corner tl"></span><span class="hud-corner tr"></span>
      <span class="hud-corner bl"></span><span class="hud-corner br"></span>
      <span class="hud-tl"><span class="rec-dot"></span>REC</span>
      <span class="hud-tr">TC <span data-timecode>00:00:00:00</span> · 25P</span>
      <span class="hud-bl">{label_left}</span>
      <span class="hud-br"><span class="meters"><span class="meter-label">L</span>{meter}<span class="meter-label">R</span>{meter}</span></span>
      <span class="hud-cross"></span>
    </div>"""


# --------------------------------------------------------------------------
# Home page
# --------------------------------------------------------------------------


def product_card(root, p, i, large=False):
    key = f'{p["slug"]}/01'
    sizes = "(min-width: 1000px) 50vw, 100vw" if large else "(min-width: 1000px) 25vw, (min-width: 640px) 50vw, 100vw"
    return f"""<li class="card{' card-lg' if large else ''}" data-reveal>
        <a class="card-link" href="{product_href(root, p['slug'])}">
          <span class="card-media">{picture(root, key, p['images'][0], sizes)}</span>
          <span class="card-body">
            <span class="card-meta"><span class="card-idx">{i:02d}</span><span class="card-brand">{e(p['brand'])}</span></span>
            <span class="card-title">{e(p['name'])}</span>
            <span class="card-tagline">{e(p['tagline'])}</span>
            <span class="card-foot"><span class="price">{price_label(p)}</span><span class="card-arrow" aria-hidden="true">→</span></span>
          </span>
        </a>
      </li>"""


def order_row(p, i):
    opts = ""
    for gi, g in enumerate(p["options"]):
        choices = "".join(
            f'<option value="{ci}">{e(c["label"])}'
            + (f' · {choice_price(c)}' if g["priced"] and c.get("price") is not None else "")
            + "</option>"
            for ci, c in enumerate(g["choices"])
        )
        opts += f"""<label class="field field-inline">
              <span class="field-label">{e(g['label'])}</span>
              <select name="{p['slug']}-o{gi}" data-opt="{gi}">{choices}</select>
            </label>"""
    return f"""<li class="order-row" data-product="{p['slug']}">
          <div class="order-row-main">
            <span class="order-idx" aria-hidden="true">{i:02d}</span>
            <div class="order-row-text">
              <span class="order-name" id="on-{p['slug']}">{e(p['name'])}</span>
              <span class="order-fits">{e(p['fits'])}</span>
            </div>
            <div class="stepper" role="group" aria-labelledby="on-{p['slug']}">
              <button type="button" class="step" data-step="-1" aria-label="One less {e(p['name'])}">−</button>
              <input type="number" name="{p['slug']}-qty" min="0" max="50" value="0" inputmode="numeric" aria-label="Quantity, {e(p['name'])}" data-qty>
              <button type="button" class="step" data-step="1" aria-label="One more {e(p['name'])}">+</button>
            </div>
            <span class="order-line-price" data-line-price aria-hidden="true">{price_label(p)}</span>
          </div>
          {f'<div class="order-row-opts">{opts}</div>' if opts else ''}
        </li>"""


def build_home():
    root = ""
    intro = C["intro"]
    hero_key = intro["hero_image"]
    facts = "".join(f"<li>{e(f)}</li>" for f in C["facts"])
    facts_track = "".join(f'<span class="marquee-item">{e(f)}</span>' for f in C["facts"])
    cards = "".join(product_card(root, p, i + 1, large=(i in (0, 3))) for i, p in enumerate(PRODUCTS))
    values = "".join(
        f"""<li class="value" data-reveal>
          <span class="value-num" aria-hidden="true">{i + 1:02d}</span>
          <h3 class="value-title">{e(v['title'])}</h3>
          <p>{e(v['text'])}</p>
        </li>"""
        for i, v in enumerate(C["values"])
    )
    reviews = "".join(
        f"""<li class="review{' review-featured' if r.get('featured') else ''}" data-reveal>
          <figure>
            <blockquote><p>{e(r['quote'])}</p></blockquote>
            <figcaption><span class="review-name">{e(r['name'])}</span><span class="review-city">{e(r['city'])}</span></figcaption>
          </figure>
        </li>"""
        for r in C["reviews"]
    )
    ordering = "".join(f"<li>{e(t)}</li>" for t in C["ordering"]["points"])
    rows = "".join(order_row(p, i + 1) for i, p in enumerate(PRODUCTS))
    threshold = SITE["free_shipping_threshold"]

    order_data = {
        "email": SITE["email"],
        "threshold": threshold,
        "products": {
            p["slug"]: {
                "name": p["name"],
                "price": p["price"],
                "from": p.get("price_from", False),
                "options": p["options"],
            }
            for p in PRODUCTS
        },
    }

    ld = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "3Deca",
        "url": SITE["url"],
        "email": SITE["email"],
        "founder": {"@type": "Person", "name": SITE["owner"], "sameAs": SITE["imdb"]},
        "description": SITE["description"],
    }

    title = "3Deca · Set gear for production sound mixers"
    out = head(root, title, SITE["description"], SITE["url"] + "/", json_ld(ld))
    out += '<body class="page-home">\n'
    out += header(root)
    out += f"""<main id="main">
  <section class="hero" aria-labelledby="hero-title">
    <div class="hero-frame">
      {picture(root, hero_key, intro['hero_alt'], '100vw', 'hero-img', eager=True)}
      <div class="hero-scrim" aria-hidden="true"></div>
      {hud()}
    </div>
    <div class="hero-copy container">
      <p class="eyebrow"><span class="eyebrow-line" aria-hidden="true"></span>{e(intro['eyebrow'])}</p>
      <h1 id="hero-title" class="hero-title">
        <span class="hero-line"><span>Built on set.</span></span>
        <span class="hero-line hero-line-accent"><span>For the set.</span></span>
      </h1>
      <p class="hero-lead">{e(intro['lead'])}</p>
      <div class="hero-actions">
        <a class="btn btn-accent" href="#gear">See the gear <span aria-hidden="true">↓</span></a>
        <a class="btn btn-ghost" href="#order">Build an order</a>
      </div>
    </div>
  </section>

  <section class="facts" aria-label="Key facts">
    <ul class="sr-only">{facts}</ul>
    <div class="marquee" aria-hidden="true">
      <div class="marquee-track">{facts_track}{facts_track}</div>
      <div class="marquee-track">{facts_track}{facts_track}</div>
    </div>
  </section>

  <section class="section gear" id="gear" aria-labelledby="gear-title">
    <div class="container">
      <div class="section-head" data-reveal>
        <p class="kicker">The kit · {len(PRODUCTS):02d} items</p>
        <h2 id="gear-title" class="section-title">Gear that earns its place on your belt.</h2>
        <p class="section-lead">Mounts, belt clips and storage for Zaxcom, Sennheiser and Wisycom. Printed in sturdy carbon/nylon and tested every shooting day.</p>
      </div>
      <ul class="cards" role="list">
        {cards}
      </ul>
    </div>
  </section>

  <section class="section values" aria-labelledby="values-title">
    <div class="container">
      <h2 id="values-title" class="sr-only">Why 3Deca</h2>
      <ul class="values-grid" role="list">{values}</ul>
    </div>
  </section>

  <section class="section about" id="about" aria-labelledby="about-title">
    <div class="container about-grid">
      <div class="about-media" data-reveal>
        <div class="about-frame">
          {picture(root, 'zmt-mount/02', PRODUCTS[0]['images'][1], '(min-width: 900px) 45vw, 100vw')}
          {hud('EXT. BEACH · DAY')}
        </div>
      </div>
      <div class="about-copy" data-reveal>
        <p class="kicker">From the sound cart</p>
        <h2 id="about-title" class="section-title">Made by someone who needed it.</h2>
        <p class="about-lead">I'm a production sound mixer based in Europe. Every product here started on set, as a fix for something that slowed us down. I use them daily, and so do my colleagues.</p>
        <p>Got a piece of kit that needs a better home? Contact me with any questions or suggestions you might have. Custom bay counts and fits for your case are part of the job.</p>
        <div class="about-actions">
          <a class="btn btn-ghost" href="{SITE['imdb']}" rel="noopener">My credits on IMDb <span aria-hidden="true">↗</span></a>
          <a class="text-link" href="mailto:{SITE['email']}">{SITE['email']}</a>
        </div>
      </div>
    </div>
  </section>

  <section class="section reviews" id="reviews" aria-labelledby="reviews-title">
    <div class="container">
      <div class="section-head" data-reveal>
        <p class="kicker">Heard on set</p>
        <h2 id="reviews-title" class="section-title">“No flimsy stuff.”</h2>
      </div>
      <ul class="reviews-grid" role="list">{reviews}</ul>
    </div>
  </section>

  <section class="section order" id="order" aria-labelledby="order-title">
    <div class="container">
      <div class="section-head" id="ordering" data-reveal>
        <p class="kicker">Order</p>
        <h2 id="order-title" class="section-title">Build your order.</h2>
        <p class="section-lead">Pick your gear, and I'll get back to you with a confirmation and payment details.</p>
        <ul class="ordering-points" role="list">{ordering}</ul>
      </div>

      <form class="order-form" id="order-form" action="mailto:{SITE['email']}" method="post" enctype="text/plain" data-order-form>
        <fieldset class="order-items">
          <legend class="order-legend">1 · Gear</legend>
          <ul class="order-list" role="list">{rows}</ul>
        </fieldset>

        <div class="order-side">
          <fieldset class="order-you">
            <legend class="order-legend">2 · You</legend>
            <label class="field"><span class="field-label">Your name</span><input name="name" autocomplete="name" required></label>
            <label class="field"><span class="field-label">Your email</span><input name="email" type="email" autocomplete="email" required></label>
            <label class="field"><span class="field-label">Shipping country</span><input name="country" autocomplete="country-name"></label>
            <label class="field"><span class="field-label">Your message <span class="optional">(custom requests, invoice details)</span></span><textarea name="message" rows="4"></textarea></label>
          </fieldset>

          <div class="order-summary" aria-labelledby="summary-title">
            <h3 id="summary-title" class="order-legend">3 · Summary</h3>
            <ul class="summary-lines" data-summary role="list"><li class="summary-empty">No gear selected yet.</li></ul>
            <div class="summary-total"><span>Subtotal ex VAT</span><output data-total aria-live="polite">€0</output></div>
            <div class="ship" data-ship>
              <div class="ship-meter" role="meter" aria-valuemin="0" aria-valuemax="{threshold}" aria-valuenow="0" aria-label="Progress to free EU shipping" data-ship-meter>
                <span class="ship-fill" data-ship-fill></span>
                <span class="ship-mark" aria-hidden="true">0 dB</span>
              </div>
              <p class="ship-text" data-ship-text aria-live="polite">Free EU shipping above {euro(threshold)}.</p>
            </div>
            <button class="btn btn-accent btn-block" type="submit">Send order request <span aria-hidden="true">→</span></button>
            <p class="order-fine">This opens your email app with the order filled in. Nothing is charged until we've confirmed it together.</p>
            <div class="order-fallback" data-order-fallback hidden>
              <p>Email app didn't open? Copy your order and send it to <a href="mailto:{SITE['email']}">{SITE['email']}</a>.</p>
              <textarea readonly rows="8" data-order-text aria-label="Your order as text"></textarea>
              <button class="btn btn-ghost btn-sm" type="button" data-copy-order>Copy order</button>
            </div>
          </div>
        </div>
      </form>
    </div>
  </section>
</main>
<script type="application/json" id="order-data">{json.dumps(order_data, ensure_ascii=False)}</script>
"""
    out += footer(root)
    out += "</body>\n</html>\n"
    (OUT / "index.html").write_text(out, encoding="utf-8")


# --------------------------------------------------------------------------
# Product pages
# --------------------------------------------------------------------------


def build_product(i, p):
    root = "../"
    slug = p["slug"]
    n = len(p["images"])
    keys = [f"{slug}/{k + 1:02d}" for k in range(n)]
    url = f"{SITE['url']}/{slug}/"

    thumbs = "".join(
        f"""<li><button type="button" class="thumb" data-thumb="{k}" aria-label="Show photo {k + 1} of {n}"{' aria-current="true"' if k == 0 else ''}>
            {picture(root, keys[k], '', '96px')}
          </button></li>"""
        for k in range(n)
    )
    features = "".join(f"<li>{e(f)}</li>" for f in p["features"])

    option_rows = ""
    for g in p["options"]:
        if g["priced"]:
            for c in g["choices"]:
                price = choice_price(c).capitalize() if c.get("price") is None else choice_price(c)
                option_rows += f"<tr><th scope=\"row\">{e(c['label'])}</th><td>{price}</td></tr>"
    if not option_rows:
        option_rows = f"<tr><th scope=\"row\">{e(p['name'])}</th><td>{euro(p['price'])}</td></tr>"

    selects = ""
    for gi, g in enumerate(p["options"]):
        choices = "".join(
            f'<option value="{ci}">{e(c["label"])}'
            + (f' · {choice_price(c)}' if g["priced"] and c.get("price") is not None else "")
            + "</option>"
            for ci, c in enumerate(g["choices"])
        )
        selects += f'<label class="field"><span class="field-label">{e(g["label"])}</span><select name="o{gi}">{choices}</select></label>'

    # Lay photos out on a 3-column grid; a photo left alone on the last row spans it.
    spans, col = [], 0
    for k in range(n):
        w = 2 if k % 5 == 0 else 1
        if col + w > 3:
            col = 0
        spans.append(w)
        col = (col + w) % 3
    if col:  # stretch the last photo so the final row has no gap
        spans[-1] += 3 - col
    shot_cls = [{1: "", 2: " shot-wide", 3: " shot-full"}[w] for w in spans]
    gallery = "".join(
        f"""<li class="shot{shot_cls[k]}" data-reveal>
          <button type="button" class="shot-btn" data-open="{k}">
            {picture(root, keys[k], p['images'][k], '(min-width: 900px) 33vw, 100vw')}
            <span class="shot-idx" aria-hidden="true">{k + 1:02d}/{n:02d}</span>
          </button>
        </li>"""
        for k in range(n)
    )

    prev_p = PRODUCTS[(i - 1) % len(PRODUCTS)]
    next_p = PRODUCTS[(i + 1) % len(PRODUCTS)]

    lightbox_data = [
        {
            "src": f"{root}img/{k}-1600.webp",
            "alt": p["images"][j],
        }
        for j, k in enumerate(keys)
    ]
    main_srcs = [
        {
            "src": f"{root}img/{k}-1600.webp",
            "srcset": f"{root}img/{k}-720.webp {img_size(k + '-720.webp')[0]}w, {root}img/{k}-1600.webp {img_size(k + '-1600.webp')[0]}w",
            "w": img_size(k + "-1600.webp")[0],
            "h": img_size(k + "-1600.webp")[1],
            "alt": p["images"][j],
        }
        for j, k in enumerate(keys)
    ]

    offers = []
    for g in p["options"]:
        if g["priced"]:
            for c in g["choices"]:
                if c.get("price") is not None:
                    offers.append(c["price"])
    if not offers:
        offers = [p["price"]]
    ld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": p["card_name"],
        "description": p["summary"],
        "image": [f"{SITE['url']}/img/{k}-1600.webp" for k in keys[:3]],
        "brand": {"@type": "Brand", "name": "3Deca"},
        "url": url,
        "offers": {
            "@type": "AggregateOffer",
            "priceCurrency": "EUR",
            "lowPrice": min(offers),
            "highPrice": max(offers),
            "availability": "https://schema.org/InStock",
        },
    }

    title = f"{p['card_name']} · 3Deca"
    desc = f"{p['summary']} {price_label(p).capitalize()} ex VAT. Designed by a production sound mixer."
    out = head(root, title, desc, url, json_ld(ld))
    out += '<body class="page-product">\n'
    out += header(root)
    out += f"""<main id="main">
  <div class="container">
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <ol>
        <li><a href="{home_href(root)}">Home</a></li>
        <li><a href="{home_href(root)}#gear">Gear</a></li>
        <li><span aria-current="page">{e(p['name'])}</span></li>
      </ol>
    </nav>

    <section class="product" aria-labelledby="product-title">
      <div class="product-gallery">
        <div class="product-stage">
          <button type="button" class="stage-btn" data-open="0" data-stage aria-label="Enlarge photo">
            {picture(root, keys[0], p['images'][0], '(min-width: 1000px) 55vw, 100vw', 'stage-img', eager=True)}
          </button>
          {hud(f'ITEM {i + 1:02d} · {slug.upper()}')}
        </div>
        <ul class="thumbs" role="list" aria-label="Photos">{thumbs}</ul>
      </div>

      <div class="product-info">
        <p class="kicker">{i + 1:02d} / {len(PRODUCTS):02d} · {e(p['brand'])}</p>
        <h1 id="product-title" class="product-title">{e(p['name'])}</h1>
        <p class="product-tagline">{e(p['tagline'])}</p>
        <p class="product-price"><span class="price-big">{price_label(p)}</span><span class="price-note">ex VAT · free EU shipping above {euro(SITE['free_shipping_threshold'])}</span></p>
        <p class="product-summary">{e(p['summary'])}</p>
        <p class="product-fits"><span class="fits-label">Fits</span> {e(p['fits'])}</p>
        <ul class="feature-list" role="list">{features}</ul>
        {f'<p class="product-note">{e(p["note"])}</p>' if p.get('note') else ''}

        <table class="price-table">
          <caption class="sr-only">Options and prices, ex VAT</caption>
          <tbody>{option_rows}</tbody>
        </table>

        <form class="add-form" action="{home_href(root)}" method="get" data-add-form>
          <input type="hidden" name="add" value="{slug}">
          {f'<div class="add-opts">{selects}</div>' if selects else ''}
          <div class="add-row">
            <label class="field field-qty"><span class="field-label">Qty</span><input type="number" name="qty" min="1" max="50" value="1" inputmode="numeric"></label>
            <button class="btn btn-accent" type="submit">Add to order <span aria-hidden="true">→</span></button>
          </div>
          <a class="text-link" href="mailto:{SITE['email']}?subject={e('Custom request: ' + p['name'])}">Ask about a custom build</a>
        </form>
      </div>
    </section>
  </div>

  <section class="section field-shots" aria-labelledby="shots-title">
    <div class="container">
      <div class="section-head" data-reveal>
        <p class="kicker">All photos · {n:02d}</p>
        <h2 id="shots-title" class="section-title">Seen on set.</h2>
      </div>
      <ul class="shots" role="list">{gallery}</ul>
    </div>
  </section>

  <nav class="section more" aria-label="More gear">
    <div class="container more-grid">
      <a class="more-link" href="{product_href(root, prev_p['slug'])}">
        <span class="kicker">← Previous</span><span class="more-name">{e(prev_p['name'])}</span><span class="price">{price_label(prev_p)}</span>
      </a>
      <a class="more-link more-next" href="{product_href(root, next_p['slug'])}">
        <span class="kicker">Next →</span><span class="more-name">{e(next_p['name'])}</span><span class="price">{price_label(next_p)}</span>
      </a>
    </div>
  </nav>
</main>

<dialog class="lightbox" data-lightbox aria-label="Photo viewer">
  <figure class="lb-figure">
    <img data-lb-img src="" alt="">
    <figcaption data-lb-caption></figcaption>
  </figure>
  <button type="button" class="lb-btn lb-close" data-lb-close aria-label="Close">✕</button>
  <button type="button" class="lb-btn lb-prev" data-lb-prev aria-label="Previous photo">←</button>
  <button type="button" class="lb-btn lb-next" data-lb-next aria-label="Next photo">→</button>
  <p class="lb-count" data-lb-count aria-live="polite"></p>
</dialog>
<script type="application/json" id="gallery-data">{json.dumps({'lightbox': lightbox_data, 'stage': main_srcs}, ensure_ascii=False)}</script>
"""
    out += footer(root)
    out += "</body>\n</html>\n"
    d = OUT / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(out, encoding="utf-8")


def build_404():
    root = "/"
    out = head(root, "Page not found · 3Deca", "This page doesn't exist.", SITE["url"] + "/404.html")
    out = out.replace('<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"')
    out += '<body class="page-404">\n' + header(root)
    out += f"""<main id="main" class="notfound container">
  <p class="kicker">Error 404 · No signal</p>
  <h1 class="section-title">Lost the feed.</h1>
  <p class="section-lead">This page doesn't exist (anymore). The gear is still here.</p>
  <a class="btn btn-accent" href="/#gear">Back to the gear</a>
</main>
"""
    out += footer(root) + "</body>\n</html>\n"
    (PUBLIC / "404.html").write_text(out, encoding="utf-8")


def build_sitemap():
    today = datetime.date.today().isoformat()
    urls = [SITE["url"] + "/"] + [f"{SITE['url']}/{p['slug']}/" for p in PRODUCTS]
    body = "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    (PUBLIC / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n',
        encoding="utf-8",
    )


def main():
    build_home()
    for i, p in enumerate(PRODUCTS):
        build_product(i, p)
    if not PREVIEW:
        build_404()
        build_sitemap()
    print(f"Built {1 + len(PRODUCTS)} pages into {OUT}" + (" (preview links)" if PREVIEW else ""))


if __name__ == "__main__":
    main()
