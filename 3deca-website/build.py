#!/usr/bin/env python3
"""Build the static 3deca.com website.

Reads content.json and writes the HTML pages into public/.
Everything in public/ is the finished website: upload that folder as-is.

    python3 build.py                     # normal build: pretty URLs (/zmt-mount/)
    python3 build.py --preview           # links point at index.html files
    python3 build.py --preview --out DIR # write the HTML somewhere else

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
OUT = Path(sys.argv[sys.argv.index("--out") + 1]).resolve() if "--out" in sys.argv else PUBLIC

C = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
SITE = C["site"]
PRODUCTS = C["products"]
BY_SLUG = {p["slug"]: p for p in PRODUCTS}
YEAR = datetime.date.today().year


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def e(text):
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
    if root == "/":
        return "/"
    return root + "index.html" if PREVIEW else (root or "./")


def product_href(root, slug):
    return f"{root}{slug}/" + ("index.html" if PREVIEW else "")


_size_cache = {}


def img_size(rel):
    if rel not in _size_cache:
        with Image.open(PUBLIC / "img" / rel) as im:
            _size_cache[rel] = im.size
    return _size_cache[rel]


def srcset(root, key):
    small, large = f"{key}-720.webp", f"{key}-1600.webp"
    return f"{root}img/{small} {img_size(small)[0]}w, {root}img/{large} {img_size(large)[0]}w"


def picture(root, key, alt, sizes, cls="", eager=False):
    """Responsive <img> for an image key like 'zmt-mount/03' or 'zmt-mount/s1'."""
    lw, lh = img_size(f"{key}-1600.webp")
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    cls_attr = f' class="{cls}"' if cls else ""
    return (
        f'<img{cls_attr} src="{root}img/{key}-1600.webp" srcset="{srcset(root, key)}" '
        f'sizes="{sizes}" width="{lw}" height="{lh}" alt="{e(alt)}" {load} decoding="async">'
    )


def studio_keys(p):
    """The cover photo: a product-centred 4:3 crop of one original photo."""
    return [f"{p['slug']}/c"]


def photo_keys(p):
    return [f"{p['slug']}/{k + 1:02d}" for k in range(len(p["images"]))]


def checkout_links(p):
    """Payment links per priced choice (webshop mode). Empty when none are set."""
    links = {}
    for gi, g in enumerate(p["options"]):
        if g["priced"]:
            for ci, c in enumerate(g["choices"]):
                if c.get("checkout_url"):
                    links[f"{gi}:{ci}"] = c["checkout_url"]
    if p.get("checkout_url"):
        links["*"] = p["checkout_url"]
    return links


# --------------------------------------------------------------------------
# page chrome
# --------------------------------------------------------------------------

WORDMARK = (
    '<span class="wm" aria-hidden="true"><span class="wm-mark"></span>'
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
<meta name="theme-color" content="#0e0e0d">
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


def header(root):
    home = home_href(root)
    links = [("products", "Products"), ("in-use", "In use"), ("about", "About"), ("faq", "FAQ")]
    items = "".join(f'<li><a href="{home}#{a}">{t}</a></li>' for a, t in links)
    return f"""<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header" data-header>
  <div class="header-inner">
    <a class="brand" href="{home}" aria-label="3Deca, home">{WORDMARK}</a>
    <nav class="site-nav" id="site-nav" aria-label="Main">
      <ul>{items}</ul>
    </nav>
    <a class="btn btn-ink btn-sm header-cta" href="{home}#order">
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
        f'<li><a href="{product_href(root, p["slug"])}"><span class="f-code">{p["code"]}</span>{e(p["name"])}</a></li>'
        for p in PRODUCTS
    )
    return f"""<footer class="site-footer">
  <div class="container">
    <div class="footer-grid">
      <div class="footer-brand">
        <a class="footer-mark" href="{home}" aria-label="3Deca, home">{WORDMARK}</a>
        <p>Set gear for production sound.</p>
      </div>
      <div>
        <h2 class="footer-h">Products</h2>
        <ul class="footer-list">{gear}</ul>
      </div>
      <div>
        <h2 class="footer-h">Ordering</h2>
        <ul class="footer-list">
          <li>Prices ex VAT</li>
          <li>Free EU shipping above {euro(SITE['free_shipping_threshold'])}</li>
          <li>Commercial invoice on request</li>
          <li><a href="{home}#order">Order form</a></li>
        </ul>
      </div>
      <div>
        <h2 class="footer-h">Contact</h2>
        <ul class="footer-list">
          <li><a href="mailto:{SITE['email']}">{SITE['email']}</a></li>
          <li><a href="{SITE['imdb']}" rel="noopener">{SITE['owner_title']} on IMDb</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <p>© 2023–{YEAR} {SITE['owner']} · 3Deca</p>
    </div>
  </div>
</footer>
"""


def json_ld(data):
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n'


def product_card(root, p):
    s1 = studio_keys(p)[0]
    hover = f"{p['slug']}/{p['hover']}"
    sizes = "(min-width: 1100px) 25vw, (min-width: 560px) 50vw, 100vw"
    return f"""<li class="card" data-system="{e(p['system'])}">
        <a class="card-link" href="{product_href(root, p['slug'])}">
          <span class="card-media">
            {picture(root, s1, p['studio'][0], sizes, 'card-img')}
            {picture(root, hover, '', sizes, 'card-img card-img-alt')}
          </span>
          <span class="card-meta"><span class="code">{p['code']}</span><span>{e(p['brand'])}</span></span>
          <span class="card-title">{e(p['name'])}</span>
          <span class="card-price">{price_label(p)}</span>
        </a>
      </li>"""


# --------------------------------------------------------------------------
# home
# --------------------------------------------------------------------------


def order_row(p):
    opts = ""
    for gi, g in enumerate(p["options"]):
        choices = "".join(
            f'<option value="{ci}">{e(c["label"])}'
            + (f" · {choice_price(c)}" if g["priced"] and c.get("price") is not None else "")
            + "</option>"
            for ci, c in enumerate(g["choices"])
        )
        opts += f"""<label class="field field-inline">
              <span class="field-label">{e(g['label'])}</span>
              <select name="{p['slug']}-o{gi}" data-opt="{gi}">{choices}</select>
            </label>"""
    return f"""<li class="order-row" data-product="{p['slug']}">
          <div class="order-row-main">
            <span class="order-thumb" aria-hidden="true"><img src="img/{studio_keys(p)[0]}-720.webp" alt="" width="72" height="54" loading="lazy"></span>
            <div class="order-row-text">
              <span class="order-name" id="on-{p['slug']}">{e(p['name'])}</span>
              <span class="order-fits"><span class="code">{p['code']}</span> {e(p['fits'])}</span>
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
    hero_p = BY_SLUG[intro["hero_product"]]
    threshold = SITE["free_shipping_threshold"]

    facts = "".join(
        f'<li class="fact"><span class="fact-title">{e(f["title"])}</span><span class="fact-text">{e(f["text"])}</span></li>'
        for f in C["facts"]
    )
    filters = '<button type="button" class="chip" aria-pressed="true" data-filter="all">All</button>' + "".join(
        f'<button type="button" class="chip" aria-pressed="false" data-filter="{e(s)}">{e(s)}</button>'
        for s in C["systems"]
    )
    cards = "".join(product_card(root, p) for p in PRODUCTS)
    cards += f"""<li class="card card-custom" data-system="all">
        <a class="card-link" href="mailto:{SITE['email']}?subject=Custom%20build%20request">
          <span class="custom-title">{e(C['custom']['title'])}</span>
          <span class="custom-text">{e(C['custom']['text'])}</span>
          <span class="custom-cta">Ask for a custom build <span aria-hidden="true">→</span></span>
        </a>
      </li>"""

    in_use = "".join(
        f"""<li class="use">
          <a class="use-media" href="{product_href(root, u['product'])}">{picture(root, u['image'], BY_SLUG[u['product']]['images'][int(u['image'].split('/')[1]) - 1], '(min-width: 900px) 25vw, 50vw')}</a>
        </li>"""
        for u in C["in_use"]
    )

    reviews = "".join(
        f"""<li><figure class="review">
            <blockquote><p>{e(r['quote'])}</p></blockquote>
            <figcaption>{e(r['name'])}, {e(r['city'])}</figcaption>
          </figure></li>"""
        for r in C["reviews"]
    )
    faq = "".join(
        f"""<details class="faq-item"><summary>{e(f['q'])}</summary><p>{e(f['a'])}</p></details>"""
        for f in C["faq"]
    )
    points = "".join(f"<li>{e(t)}</li>" for t in C["ordering"]["points"])
    rows = "".join(order_row(p) for p in PRODUCTS)

    order_data = {
        "email": SITE["email"],
        "threshold": threshold,
        "products": {
            p["slug"]: {"name": p["name"], "code": p["code"], "price": p["price"], "from": p.get("price_from", False), "options": p["options"]}
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

    out = head(root, "3Deca · Set gear for production sound mixers", SITE["description"], SITE["url"] + "/", json_ld(ld))
    out += '<body class="page-home">\n' + header(root)
    out += f"""<main id="main">
  <section class="hero" aria-labelledby="hero-title">
    <div class="container hero-grid">
      <div class="hero-text">
        <h1 id="hero-title" class="hero-title">{e(intro['title'])}</h1>
        <div class="hero-actions">
          <a class="btn btn-ink" href="#products">Products</a>
          <a class="text-link" href="#order">Order form</a>
        </div>
        <ul class="facts" role="list">{facts}</ul>
      </div>
      <figure class="hero-media">
        <a class="hero-shot" href="{product_href(root, hero_p['slug'])}">
          {picture(root, intro['hero_image'], intro['hero_alt'], '(min-width: 1000px) 55vw, 100vw', 'hero-img', eager=True)}
        </a>
        <figcaption class="hero-caption">
          <span><span class="code">{hero_p['code']}</span> {e(hero_p['name'])}</span>
          <a href="{product_href(root, hero_p['slug'])}">{price_label(hero_p)}<span class="sr-only"> · view {e(hero_p['name'])}</span></a>
        </figcaption>
      </figure>
    </div>
  </section>

  <section class="section shop" id="products" aria-labelledby="shop-title">
    <div class="container">
      <div class="section-bar">
        <h2 id="shop-title" class="sr-only">Products</h2>
        <div class="filters" role="group" aria-label="Filter by system">{filters}</div>
      </div>
      <p class="sr-only" aria-live="polite" data-filter-status></p>
      <ul class="cards" role="list" data-cards>
        {cards}
      </ul>
    </div>
  </section>

  <section class="section in-use" id="in-use" aria-labelledby="use-title">
    <div class="container">
      <div class="section-bar">
        <h2 id="use-title" class="section-title">In use</h2>
      </div>
      <ul class="uses" role="list">{in_use}</ul>
    </div>
  </section>

  <section class="section about" id="about" aria-labelledby="about-title">
    <div class="container split">
      <h2 id="about-title" class="section-title">About</h2>
      <div class="about-copy">
        <p>{e(C['about']['text'])}</p>
        <p><a class="text-link" href="mailto:{SITE['email']}">{SITE['email']}</a></p>
        <p><a class="imdb" href="{SITE['imdb']}" rel="noopener"><img src="img/imdb.png" width="56" height="28" alt="{e(SITE['owner_title'])} on IMDb"></a></p>
      </div>
    </div>
  </section>

  <section class="section reviews" id="reviews" aria-labelledby="reviews-title">
    <div class="container split">
      <h2 id="reviews-title" class="section-title">Reviews</h2>
      <ul class="reviews-grid" role="list">{reviews}</ul>
    </div>
  </section>

  <section class="section faq" id="faq" aria-labelledby="faq-title">
    <div class="container split">
      <h2 id="faq-title" class="section-title">FAQ</h2>
      <div class="faq-list">{faq}</div>
    </div>
  </section>

  <section class="section order" id="order" aria-labelledby="order-title">
    <div class="container">
      <div class="section-bar">
        <h2 id="order-title" class="section-title">Order</h2>
        <ul class="order-points" role="list">{points}</ul>
      </div>

      <form class="order-form" id="order-form" action="mailto:{SITE['email']}" method="post" enctype="text/plain" data-order-form>
        <fieldset class="order-items">
          <legend class="order-legend">1 · Choose your gear</legend>
          <ul class="order-list" role="list">{rows}</ul>
        </fieldset>

        <div class="order-side">
          <fieldset class="order-you">
            <legend class="order-legend">2 · Your details</legend>
            <label class="field"><span class="field-label">Name</span><input id="f-name" name="name" autocomplete="name" required></label>
            <label class="field"><span class="field-label">Email</span><input id="f-email" name="email" type="email" autocomplete="email" required></label>
            <label class="field"><span class="field-label">Shipping country</span><input id="f-country" name="country" autocomplete="country-name"></label>
            <label class="field"><span class="field-label">Message <span class="optional">(custom requests, invoice details)</span></span><textarea id="f-message" name="message" rows="3"></textarea></label>
          </fieldset>

          <div class="order-summary">
            <h3 class="order-legend">3 · Summary</h3>
            <ul class="summary-lines" data-summary role="list"><li class="summary-empty">No gear selected yet.</li></ul>
            <div class="summary-total"><span>Subtotal ex VAT</span><output data-total aria-live="polite">€0</output></div>
            <div class="ship" data-ship>
              <div class="ship-meter" role="meter" aria-valuemin="0" aria-valuemax="{threshold}" aria-valuenow="0" aria-label="Progress to free EU shipping" data-ship-meter>
                <span class="ship-fill" data-ship-fill></span>
              </div>
              <p class="ship-text" data-ship-text aria-live="polite">Free EU shipping above {euro(threshold)}.</p>
            </div>
            <button class="btn btn-ink btn-block" type="submit">Send order request <span aria-hidden="true">→</span></button>
            <p class="order-fine">This opens your email app with the order filled in. Nothing is charged until I've confirmed it.</p>
            <div class="order-fallback" data-order-fallback hidden>
              <p>Email app didn't open? Copy your order and send it to <a href="mailto:{SITE['email']}">{SITE['email']}</a>.</p>
              <textarea readonly rows="8" data-order-text aria-label="Your order as text"></textarea>
              <button class="btn btn-line btn-sm" type="button" data-copy-order>Copy order</button>
            </div>
          </div>
        </div>
      </form>
    </div>
  </section>
</main>
<script type="application/json" id="order-data">{json.dumps(order_data, ensure_ascii=False)}</script>
"""
    out += footer(root) + "</body>\n</html>\n"
    (OUT / "index.html").write_text(out, encoding="utf-8")


# --------------------------------------------------------------------------
# product pages
# --------------------------------------------------------------------------


def related(p, n=3):
    same = [q for q in PRODUCTS if q["system"] == p["system"] and q is not p]
    rest = [q for q in PRODUCTS if q["system"] != p["system"]]
    return (same + rest)[:n]


def build_product(i, p):
    root = "../"
    slug = p["slug"]
    skeys, pkeys = studio_keys(p), photo_keys(p)
    keys = skeys + pkeys
    alts = p["studio"] + p["images"]
    n = len(keys)
    url = f"{SITE['url']}/{slug}/"

    thumbs = "".join(
        f"""<li><button type="button" class="thumb" data-thumb="{k}" aria-label="Show photo {k + 1} of {n}"{' aria-current="true"' if k == 0 else ''}>
            <img src="{root}img/{keys[k]}-720.webp" alt="" width="96" height="72" loading="lazy" decoding="async">
          </button></li>"""
        for k in range(n)
    )
    specs = f'<tr><th scope="row">Product code</th><td>{p["code"]}</td></tr>' + "".join(
        f'<tr><th scope="row">{e(a)}</th><td>{e(b)}</td></tr>' for a, b in p["specs"]
    )

    option_groups = ""
    for gi, g in enumerate(p["options"]):
        radios = "".join(
            f"""<label class="seg"><input type="radio" name="o{gi}" value="{ci}"{' checked' if ci == 0 else ''} data-priced="{1 if g['priced'] else 0}" data-price="{'' if c.get('price') is None else c['price']}" data-from="{1 if c.get('from') else 0}">
              <span>{e(c['label'])}{f'<small>{choice_price(c)}</small>' if g['priced'] else ''}</span></label>"""
            for ci, c in enumerate(g["choices"])
        )
        option_groups += f'<fieldset class="opt-group"><legend class="field-label">{e(g["label"])}</legend><div class="segs">{radios}</div></fieldset>'

    links = checkout_links(p)
    buy = (
        f'<a class="btn btn-ink" href="#" data-buy hidden>Buy now <span aria-hidden="true">→</span></a>'
        f'<script type="application/json" id="checkout-data">{json.dumps(links)}</script>'
        if links
        else ""
    )

    # Photos from the field, laid out on a 3-column grid without gaps
    spans, col = [], 0
    for k in range(len(pkeys)):
        w = 2 if k % 5 == 0 else 1
        if col + w > 3:
            col = 0
        spans.append(w)
        col = (col + w) % 3
    if col and spans:
        spans[-1] += 3 - col
    shot_cls = [{1: "", 2: " shot-wide", 3: " shot-full"}[w] for w in spans]
    field = "".join(
        f"""<li class="shot{shot_cls[k]}">
          <button type="button" class="shot-btn" data-open="{len(skeys) + k}" aria-label="Enlarge: {e(p['images'][k])}">
            {picture(root, pkeys[k], p['images'][k], '(min-width: 900px) 33vw, 100vw')}
          </button>
        </li>"""
        for k in range(len(pkeys))
    )

    rel = "".join(product_card(root, q) for q in related(p))

    gallery_data = {
        "stage": [
            {
                "src": f"{root}img/{k}-1600.webp",
                "srcset": srcset(root, k),
                "w": img_size(k + "-1600.webp")[0],
                "h": img_size(k + "-1600.webp")[1],
                "alt": alts[j],
            }
            for j, k in enumerate(keys)
        ]
    }

    offers = [c["price"] for g in p["options"] if g["priced"] for c in g["choices"] if c.get("price") is not None] or [p["price"]]
    ld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": p["card_name"],
        "sku": p["code"],
        "description": p["summary"],
        "image": [f"{SITE['url']}/img/{k}-1600.webp" for k in keys[:3]],
        "brand": {"@type": "Brand", "name": "3Deca"},
        "url": url,
        "offers": {"@type": "AggregateOffer", "priceCurrency": "EUR", "lowPrice": min(offers), "highPrice": max(offers), "availability": "https://schema.org/InStock"},
    }

    title = f"{p['card_name']} · 3Deca"
    desc = f"{p['summary']} {price_label(p).capitalize()} ex VAT. Designed by a production sound mixer."
    out = head(root, title, desc, url, json_ld(ld))
    out += '<body class="page-product">\n' + header(root)
    out += f"""<main id="main">
  <div class="container">
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <ol>
        <li><a href="{home_href(root)}">Home</a></li>
        <li><a href="{home_href(root)}#products">Products</a></li>
        <li><span aria-current="page">{e(p['name'])}</span></li>
      </ol>
    </nav>

    <section class="product" aria-labelledby="product-title">
      <div class="product-gallery">
        <div class="stage">
          <button type="button" class="stage-btn" data-open="0" data-stage aria-label="Enlarge photo">
            {picture(root, keys[0], alts[0], '(min-width: 1000px) 58vw, 100vw', 'stage-img', eager=True)}
          </button>
          <span class="stage-count" aria-hidden="true" data-stage-count>01 / {n:02d}</span>
        </div>
        <ul class="thumbs" role="list" aria-label="Photos">{thumbs}</ul>
      </div>

      <div class="product-info">
        <p class="product-meta"><span class="code">{p['code']}</span><span>{e(p['brand'])}</span></p>
        <h1 id="product-title" class="product-title">{e(p['name'])}</h1>
        <p class="product-price"><span class="price-big" data-price-display>{price_label(p)}</span><span class="price-note">ex VAT</span></p>
        <table class="spec-table"><caption class="sr-only">Specifications</caption><tbody>{specs}</tbody></table>

        <form class="buy-box" action="{home_href(root)}" method="get" data-add-form>
          <input type="hidden" name="add" value="{slug}">
          {option_groups}
          <div class="buy-row">
            <div class="stepper" role="group" aria-label="Quantity">
              <button type="button" class="step" data-qty-step="-1" aria-label="One less">−</button>
              <input type="number" name="qty" min="1" max="50" value="1" inputmode="numeric" aria-label="Quantity">
              <button type="button" class="step" data-qty-step="1" aria-label="One more">+</button>
            </div>
            <button class="btn btn-ink btn-grow" type="submit">Add to order <span aria-hidden="true">→</span></button>
          </div>
          {buy}
          {f'<p class="product-note">{e(p["note"])}</p>' if p.get('note') else ''}
          <a class="text-link" href="mailto:{SITE['email']}?subject={e('Custom request: ' + p['name'])}">Ask about a custom build</a>
        </form>

        <ul class="assurances" role="list">
          <li>Free EU shipping above {euro(SITE['free_shipping_threshold'])}</li>
        </ul>
      </div>
    </section>
  </div>

  <section class="section field" aria-labelledby="field-title">
    <div class="container">
      <div class="section-bar">
        <h2 id="field-title" class="section-title">Photos <span class="count">{len(pkeys)}</span></h2>
      </div>
      <ul class="shots" role="list">{field}</ul>
    </div>
  </section>

  <section class="section related" aria-labelledby="related-title">
    <div class="container">
      <div class="section-bar">
        <h2 id="related-title" class="section-title">Related products</h2>
        <a class="text-link" href="{home_href(root)}#products">All products</a>
      </div>
      <ul class="cards cards-3" role="list">{rel}</ul>
    </div>
  </section>
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
<script type="application/json" id="gallery-data">{json.dumps(gallery_data, ensure_ascii=False)}</script>
"""
    out += footer(root) + "</body>\n</html>\n"
    d = OUT / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(out, encoding="utf-8")


def build_404():
    root = "/"
    out = head(root, "Page not found · 3Deca", "This page doesn't exist.", SITE["url"] + "/404.html")
    out = out.replace('<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"')
    out += '<body class="page-404">\n' + header(root)
    out += """<main id="main" class="notfound container">
  <h1 class="section-title">Page not found</h1>
  <p class="section-lead">This page may have moved when the site was renewed.</p>
  <a class="btn btn-ink" href="/#products">Products</a>
</main>
"""
    out += footer(root) + "</body>\n</html>\n"
    (OUT / "404.html").write_text(out, encoding="utf-8")


def build_sitemap():
    today = datetime.date.today().isoformat()
    urls = [SITE["url"] + "/"] + [f"{SITE['url']}/{p['slug']}/" for p in PRODUCTS]
    body = "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n',
        encoding="utf-8",
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    build_home()
    for i, p in enumerate(PRODUCTS):
        build_product(i, p)
    if not PREVIEW:
        build_404()
        build_sitemap()
    print(f"Built {1 + len(PRODUCTS)} pages into {OUT}" + (" (preview links)" if PREVIEW else ""))


if __name__ == "__main__":
    main()
