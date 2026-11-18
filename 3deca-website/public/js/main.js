/* 3Deca — site behaviour. No dependencies, no tracking. */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (sel, el) { return (el || document).querySelector(sel); };
  var $$ = function (sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); };

  /* ---------- storage (fails quietly in private mode) ---------- */
  var KEY = "3deca-order-v1";
  function loadOrder() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
  }
  function saveOrder(order) {
    try { localStorage.setItem(KEY, JSON.stringify(order)); } catch (e) { /* ignore */ }
  }
  function orderCount(order) {
    return Object.keys(order).reduce(function (n, k) { return n + (order[k].qty || 0); }, 0);
  }
  function updateBadge(order) {
    var n = orderCount(order);
    $$("[data-order-count]").forEach(function (el) {
      el.textContent = n;
      el.hidden = n === 0;
      el.setAttribute("aria-label", n + (n === 1 ? " item" : " items") + " in your order");
    });
  }
  updateBadge(loadOrder());

  /* ---------- header: solid once you scroll past the top ---------- */
  var header = $("[data-header]");
  if (header) {
    var onScroll = function () { header.classList.toggle("is-solid", window.scrollY > 40); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* ---------- mobile navigation ---------- */
  var toggle = $("[data-nav-toggle]");
  var nav = $("#site-nav");
  if (toggle && nav) {
    var setOpen = function (open) {
      toggle.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);
      if (header && open) header.classList.add("is-solid");
    };
    toggle.addEventListener("click", function () { setOpen(toggle.getAttribute("aria-expanded") !== "true"); });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) setOpen(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("is-open")) { setOpen(false); toggle.focus(); }
    });
  }

  /* ---------- time-of-day timecode, 25 fps ---------- */
  var tcEls = $$("[data-timecode]");
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function timecode() {
    var d = new Date();
    return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()) + ":" + pad(Math.floor(d.getMilliseconds() / 40));
  }

  /* ---------- level meters ---------- */
  var meters = $$("[data-meter]").map(function (el, i) {
    return { el: el, level: 0.4, target: 0.5, peakHold: 0, seed: i };
  });
  var energy = 0; // grows with scrolling / pointer movement, decays over time
  window.addEventListener("scroll", function () { energy = Math.min(1, energy + 0.06); }, { passive: true });
  window.addEventListener("pointermove", function () { energy = Math.min(1, energy + 0.015); }, { passive: true });

  function tickMeters() {
    energy *= 0.96;
    meters.forEach(function (m) {
      if (Math.random() < 0.18) {
        // speech-like bursts, louder when the visitor is "making noise"
        m.target = 0.25 + Math.random() * 0.45 + energy * 0.35;
        if (Math.random() < 0.05) m.target = 0.92 + Math.random() * 0.08;
      }
      var speed = m.target > m.level ? 0.45 : 0.12; // fast attack, slow release
      m.level += (m.target - m.level) * speed;
      m.el.style.setProperty("--lvl", Math.max(0.05, Math.min(1, m.level)).toFixed(3));
    });
  }

  if (tcEls.length || meters.length) {
    if (reduceMotion) {
      tcEls.forEach(function (el) { el.textContent = timecode(); });
      meters.forEach(function (m, i) { m.el.style.setProperty("--lvl", i % 2 ? "0.52" : "0.6"); });
    } else {
      var last = 0;
      var loop = function (t) {
        if (t - last >= 40) {
          last = t;
          var tc = timecode();
          tcEls.forEach(function (el) { el.textContent = tc; });
          tickMeters();
        }
        requestAnimationFrame(loop);
      };
      requestAnimationFrame(loop);
    }
  }

  /* ---------- reveal on scroll ---------- */
  var revealEls = $$("[data-reveal]");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add("is-visible"); io.unobserve(entry.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* ---------- product page: photo stage + lightbox ---------- */
  var galleryData = $("#gallery-data");
  if (galleryData) {
    var data = JSON.parse(galleryData.textContent);
    var stageBtn = $("[data-stage]");
    var stageImg = stageBtn && $("img", stageBtn);
    var thumbs = $$("[data-thumb]");

    thumbs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var i = +btn.getAttribute("data-thumb");
        var s = data.stage[i];
        thumbs.forEach(function (b) { b.removeAttribute("aria-current"); });
        btn.setAttribute("aria-current", "true");
        stageBtn.setAttribute("data-open", i);
        stageImg.classList.add("is-swapping");
        var swap = function () {
          stageImg.srcset = s.srcset;
          stageImg.src = s.src;
          stageImg.alt = s.alt;
          stageImg.width = s.w;
          stageImg.height = s.h;
          stageImg.classList.remove("is-swapping");
        };
        if (reduceMotion) swap(); else setTimeout(swap, 180);
      });
    });

    var lb = $("[data-lightbox]");
    if (lb && typeof lb.showModal === "function") {
      var lbImg = $("[data-lb-img]", lb);
      var lbCap = $("[data-lb-caption]", lb);
      var lbCount = $("[data-lb-count]", lb);
      var current = 0;
      var opener = null;
      var total = data.lightbox.length;
      var show = function (i) {
        current = (i + total) % total;
        var item = data.lightbox[current];
        lbImg.src = item.src;
        lbImg.alt = item.alt;
        lbCap.textContent = item.alt;
        lbCount.textContent = "Photo " + (current + 1) + " of " + total;
      };
      $$("[data-open]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          opener = btn;
          show(+btn.getAttribute("data-open"));
          lb.showModal();
        });
      });
      $("[data-lb-prev]", lb).addEventListener("click", function () { show(current - 1); });
      $("[data-lb-next]", lb).addEventListener("click", function () { show(current + 1); });
      $("[data-lb-close]", lb).addEventListener("click", function () { lb.close(); });
      lb.addEventListener("click", function (e) { if (e.target === lb) lb.close(); });
      lb.addEventListener("keydown", function (e) {
        if (e.key === "ArrowLeft") show(current - 1);
        if (e.key === "ArrowRight") show(current + 1);
      });
      lb.addEventListener("close", function () { if (opener) opener.focus(); });
      var touchX = null;
      lb.addEventListener("touchstart", function (e) { touchX = e.touches[0].clientX; }, { passive: true });
      lb.addEventListener("touchend", function (e) {
        if (touchX === null) return;
        var dx = e.changedTouches[0].clientX - touchX;
        if (Math.abs(dx) > 50) show(current + (dx < 0 ? 1 : -1));
        touchX = null;
      });
    }
  }

  /* ---------- order builder (home page) ---------- */
  var orderDataEl = $("#order-data");
  var form = $("[data-order-form]");
  if (!orderDataEl || !form) return;

  var OD = JSON.parse(orderDataEl.textContent);
  var order = loadOrder();
  var rows = $$(".order-row", form);
  var euro = function (n) { return "€" + (Math.round(n * 100) / 100).toString(); };

  // Accept "?add=slug&qty=1&o0=..." from a product page's "Add to order" form.
  var params = new URLSearchParams(window.location.search);
  var addSlug = params.get("add");
  if (addSlug && OD.products[addSlug]) {
    var p = OD.products[addSlug];
    var opts = p.options.map(function (g, gi) {
      var v = parseInt(params.get("o" + gi), 10);
      return v >= 0 && v < g.choices.length ? v : 0;
    });
    var addQty = Math.max(1, Math.min(50, parseInt(params.get("qty"), 10) || 1));
    var prev = order[addSlug];
    var sameOpts = prev && JSON.stringify(prev.opts) === JSON.stringify(opts);
    order[addSlug] = { qty: Math.min(50, (sameOpts ? prev.qty : 0) + addQty), opts: opts };
    saveOrder(order);
    if (window.history && history.replaceState) history.replaceState(null, "", window.location.pathname + "#order");
    window.addEventListener("load", function () {
      var target = $("#order");
      if (target) target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
    });
  }

  function lineFor(slug, state) {
    var p = OD.products[slug];
    var unit = p.price;
    var from = p.from;
    var quote = false;
    var details = [];
    p.options.forEach(function (g, gi) {
      var c = g.choices[state.opts && state.opts[gi] != null ? state.opts[gi] : 0] || g.choices[0];
      details.push(c.label);
      if (g.priced) {
        from = !!c.from;
        if (c.price == null) quote = true; else unit = c.price;
      }
    });
    return { name: p.name, qty: state.qty, unit: unit, total: unit * state.qty, from: from, quote: quote, details: details };
  }

  function currentLines() {
    return rows.map(function (row) {
      var slug = row.getAttribute("data-product");
      var st = order[slug] || { qty: 0, opts: [] };
      return st.qty > 0 ? lineFor(slug, st) : null;
    }).filter(Boolean);
  }

  var summaryEl = $("[data-summary]", form);
  var totalEl = $("[data-total]", form);
  var shipBox = $("[data-ship]", form);
  var shipMeter = $("[data-ship-meter]", form);
  var shipFill = $("[data-ship-fill]", form);
  var shipText = $("[data-ship-text]", form);

  function render() {
    rows.forEach(function (row) {
      var slug = row.getAttribute("data-product");
      var st = order[slug] || { qty: 0, opts: [] };
      var qtyInput = $("[data-qty]", row);
      if (document.activeElement !== qtyInput) qtyInput.value = st.qty;
      $$("select[data-opt]", row).forEach(function (sel) {
        var gi = +sel.getAttribute("data-opt");
        if (st.opts && st.opts[gi] != null) sel.value = String(st.opts[gi]);
      });
      row.classList.toggle("is-active", st.qty > 0);
      var priceEl = $("[data-line-price]", row);
      if (st.qty > 0) {
        var l = lineFor(slug, st);
        priceEl.textContent = l.quote ? "quote" : (l.from ? "from " : "") + euro(l.total);
      } else {
        var base = OD.products[slug];
        priceEl.textContent = (base.from ? "from " : "") + euro(base.price);
      }
    });

    var lines = currentLines();
    var total = 0, anyFrom = false, anyQuote = false;
    summaryEl.innerHTML = "";
    if (!lines.length) {
      var li = document.createElement("li");
      li.className = "summary-empty";
      li.textContent = "No gear selected yet.";
      summaryEl.appendChild(li);
    }
    lines.forEach(function (l) {
      if (!l.quote) total += l.total;
      anyFrom = anyFrom || l.from;
      anyQuote = anyQuote || l.quote;
      var li = document.createElement("li");
      var name = document.createElement("span");
      name.className = "s-name";
      name.textContent = l.qty + "× " + l.name;
      if (l.details.length) {
        var small = document.createElement("small");
        small.textContent = l.details.join(" · ");
        name.appendChild(small);
      }
      var price = document.createElement("span");
      price.className = "s-price";
      price.textContent = l.quote ? "quote" : (l.from ? "from " : "") + euro(l.total);
      li.appendChild(name);
      li.appendChild(price);
      summaryEl.appendChild(li);
    });
    totalEl.textContent = (anyFrom ? "from " : "") + euro(total) + (anyQuote ? " + quote" : "");

    var ratio = Math.min(1, total / OD.threshold);
    shipFill.style.setProperty("--ship", ratio.toFixed(3));
    shipMeter.setAttribute("aria-valuenow", String(Math.min(total, OD.threshold)));
    var free = total >= OD.threshold;
    shipBox.classList.toggle("is-free", free);
    shipText.textContent = free
      ? "Free EU shipping unlocked. Peak level reached."
      : total > 0
        ? euro(OD.threshold - total) + " more for free EU shipping."
        : "Free EU shipping above " + euro(OD.threshold) + ".";
    updateBadge(order);
  }

  function setQty(slug, qty) {
    qty = Math.max(0, Math.min(50, qty | 0));
    var st = order[slug] || { qty: 0, opts: [] };
    st.qty = qty;
    if (qty === 0) delete order[slug]; else order[slug] = st;
    saveOrder(order);
    render();
  }

  rows.forEach(function (row) {
    var slug = row.getAttribute("data-product");
    var qtyInput = $("[data-qty]", row);
    $$("[data-step]", row).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var cur = (order[slug] && order[slug].qty) || 0;
        setQty(slug, cur + +btn.getAttribute("data-step"));
      });
    });
    qtyInput.addEventListener("input", function () { setQty(slug, parseInt(qtyInput.value, 10) || 0); });
    $$("select[data-opt]", row).forEach(function (sel) {
      sel.addEventListener("change", function () {
        var st = order[slug] || { qty: 0, opts: [] };
        st.opts = st.opts || [];
        st.opts[+sel.getAttribute("data-opt")] = +sel.value;
        if (st.qty > 0) order[slug] = st;
        saveOrder(order);
        render();
      });
    });
  });

  function orderText() {
    var fd = new FormData(form);
    var lines = currentLines();
    var out = ["Hi Jan,", "", "I'd like to order:", ""];
    var total = 0, anyFrom = false, anyQuote = false;
    lines.forEach(function (l) {
      if (!l.quote) total += l.total;
      anyFrom = anyFrom || l.from;
      anyQuote = anyQuote || l.quote;
      out.push("- " + l.qty + "x " + l.name + (l.details.length ? " (" + l.details.join(", ") + ")" : "") +
        ": " + (l.quote ? "price on request" : (l.from ? "from " : "") + euro(l.total)));
    });
    out.push("");
    out.push("Subtotal ex VAT: " + (anyFrom ? "from " : "") + euro(total) + (anyQuote ? " + quote" : ""));
    var msg = (fd.get("message") || "").toString().trim();
    if (msg) { out.push("", msg); }
    out.push("", "Name: " + (fd.get("name") || ""), "Email: " + (fd.get("email") || ""));
    var country = (fd.get("country") || "").toString().trim();
    if (country) out.push("Shipping country: " + country);
    out.push("", "Thanks!");
    return out.join("\n");
  }

  var errorEl = null;
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (errorEl) { errorEl.remove(); errorEl = null; }
    if (!currentLines().length) {
      errorEl = document.createElement("p");
      errorEl.className = "order-error";
      errorEl.setAttribute("role", "alert");
      errorEl.textContent = "Add at least one item to your order first.";
      $(".order-summary .btn", form).insertAdjacentElement("afterend", errorEl);
      var firstStep = $('[data-step="1"]', form);
      if (firstStep) firstStep.focus();
      return;
    }
    if (!form.reportValidity()) return;
    var text = orderText();
    var fd = new FormData(form);
    var subject = "Order request 3Deca: " + (fd.get("name") || "");
    var fallback = $("[data-order-fallback]", form);
    $("[data-order-text]", form).value = "To: " + OD.email + "\nSubject: " + subject + "\n\n" + text;
    fallback.hidden = false;
    window.location.href = "mailto:" + OD.email + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(text);
  });

  var copyBtn = $("[data-copy-order]", form);
  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      var ta = $("[data-order-text]", form);
      var done = function () { copyBtn.textContent = "Copied"; setTimeout(function () { copyBtn.textContent = "Copy order"; }, 2000); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(ta.value).then(done, function () { ta.select(); });
      } else { ta.select(); try { document.execCommand("copy"); done(); } catch (err) { /* ignore */ } }
    });
  }

  render();
})();
