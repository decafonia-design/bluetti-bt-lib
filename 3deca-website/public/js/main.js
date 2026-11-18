/* 3Deca — site behaviour. No dependencies, no tracking. */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (sel, el) { return (el || document).querySelector(sel); };
  var $$ = function (sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); };
  var euro = function (n) { return "€" + (Math.round(n * 100) / 100).toString(); };

  /* ---------- order storage (fails quietly in private mode) ---------- */
  var KEY = "3deca-order-v1";
  function loadOrder() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
  }
  function saveOrder(order) {
    try { localStorage.setItem(KEY, JSON.stringify(order)); } catch (e) { /* ignore */ }
  }
  function updateBadge(order) {
    var n = Object.keys(order).reduce(function (s, k) { return s + (order[k].qty || 0); }, 0);
    $$("[data-order-count]").forEach(function (el) {
      el.textContent = n;
      el.hidden = n === 0;
      el.setAttribute("aria-label", n + (n === 1 ? " item" : " items") + " in your order");
    });
  }
  updateBadge(loadOrder());

  /* ---------- mobile navigation ---------- */
  var toggle = $("[data-nav-toggle]");
  var nav = $("#site-nav");
  if (toggle && nav) {
    var setOpen = function (open) {
      toggle.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);
    };
    toggle.addEventListener("click", function () { setOpen(toggle.getAttribute("aria-expanded") !== "true"); });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) setOpen(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("is-open")) { setOpen(false); toggle.focus(); }
    });
  }

  /* ---------- video: load YouTube only after the visitor clicks play ---------- */
  $$("[data-video]").forEach(function (box) {
    var btn = $("[data-video-play]", box);
    if (!btn) return;
    btn.addEventListener("click", function () {
      var f = document.createElement("iframe");
      f.src = "https://www.youtube-nocookie.com/embed/" + box.getAttribute("data-video") + "?autoplay=1&rel=0";
      f.title = box.getAttribute("data-video-title") || "Video";
      f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
      f.setAttribute("allowfullscreen", "");
      box.replaceChild(f, btn);
      f.focus();
    });
  });

  /* ---------- shop filters ---------- */
  var chips = $$("[data-filter]");
  var cardList = $("[data-cards]");
  if (chips.length && cardList) {
    var status = $("[data-filter-status]");
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        var f = chip.getAttribute("data-filter");
        chips.forEach(function (c) { c.setAttribute("aria-pressed", String(c === chip)); });
        var shown = 0;
        $$(".card", cardList).forEach(function (card) {
          var sys = card.getAttribute("data-system");
          var show = f === "all" || sys === f || sys === "all";
          card.hidden = !show;
          if (show && sys !== "all") shown++;
        });
        if (status) status.textContent = shown + (shown === 1 ? " product" : " products") + (f === "all" ? "" : " for " + f);
      });
    });
  }

  /* ---------- product page: photo stage + lightbox ---------- */
  var galleryData = $("#gallery-data");
  if (galleryData) {
    var data = JSON.parse(galleryData.textContent).stage;
    var total = data.length;
    var stageBtn = $("[data-stage]");
    var stageImg = stageBtn && $("img", stageBtn);
    var stageCount = $("[data-stage-count]");
    var thumbs = $$("[data-thumb]");
    var two = function (n) { return (n < 10 ? "0" : "") + n; };

    var showStage = function (i) {
      var s = data[i];
      thumbs.forEach(function (b) { b.removeAttribute("aria-current"); });
      if (thumbs[i]) thumbs[i].setAttribute("aria-current", "true");
      stageBtn.setAttribute("data-open", i);
      if (stageCount) stageCount.textContent = two(i + 1) + " / " + two(total);
      var swap = function () {
        stageImg.srcset = s.srcset;
        stageImg.src = s.src;
        stageImg.alt = s.alt;
        stageImg.width = s.w;
        stageImg.height = s.h;
        stageImg.classList.remove("is-swapping");
      };
      if (reduceMotion) { swap(); } else { stageImg.classList.add("is-swapping"); setTimeout(swap, 150); }
    };
    thumbs.forEach(function (btn) {
      btn.addEventListener("click", function () { showStage(+btn.getAttribute("data-thumb")); });
    });

    var lb = $("[data-lightbox]");
    if (lb && typeof lb.showModal === "function") {
      var lbImg = $("[data-lb-img]", lb);
      var lbCap = $("[data-lb-caption]", lb);
      var lbCount = $("[data-lb-count]", lb);
      var current = 0;
      var opener = null;
      var show = function (i) {
        current = (i + total) % total;
        lbImg.src = data[current].src;
        lbImg.alt = data[current].alt;
        lbCap.textContent = data[current].alt;
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

  /* ---------- product page: options, quantity, add to order, buy now ---------- */
  var addForm = $("[data-add-form]");
  if (addForm) {
    var priceDisplay = $("[data-price-display]");
    var buyBtn = $("[data-buy]");
    var checkout = $("#checkout-data") ? JSON.parse($("#checkout-data").textContent) : {};
    var qtyInput = $('input[name="qty"]', addForm);

    var refresh = function () {
      var priced = $$('input[type="radio"][data-priced="1"]:checked', addForm)[0];
      if (priced && priceDisplay) {
        var p = priced.getAttribute("data-price");
        priceDisplay.textContent = p === "" ? "On request" : (priced.getAttribute("data-from") === "1" ? "from " : "") + "€" + p;
      }
      if (buyBtn) {
        var key = priced ? priced.name.slice(1) + ":" + priced.value : "*";
        var url = checkout[key] || checkout["*"];
        buyBtn.hidden = !url;
        if (url) buyBtn.href = url;
      }
    };
    $$('input[type="radio"]', addForm).forEach(function (r) { r.addEventListener("change", refresh); });
    refresh();

    $$("[data-qty-step]", addForm).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = (parseInt(qtyInput.value, 10) || 1) + +btn.getAttribute("data-qty-step");
        qtyInput.value = Math.max(1, Math.min(50, v));
      });
    });

    // Store the choice in this browser and go to the order form. Without JS
    // (or storage) the form falls back to a GET with ?add=... instead.
    addForm.addEventListener("submit", function (e) {
      var fd = new FormData(addForm);
      var slug = fd.get("add");
      var opts = [];
      for (var gi = 0; fd.has("o" + gi); gi++) opts.push(parseInt(fd.get("o" + gi), 10) || 0);
      var qty = Math.max(1, Math.min(50, parseInt(fd.get("qty"), 10) || 1));
      var order = loadOrder();
      var prev = order[slug];
      var same = prev && JSON.stringify(prev.opts) === JSON.stringify(opts);
      order[slug] = { qty: Math.min(50, (same ? prev.qty : 0) + qty), opts: opts };
      saveOrder(order);
      if (JSON.stringify(loadOrder()[slug]) !== JSON.stringify(order[slug])) return; // storage blocked
      e.preventDefault();
      window.location.href = addForm.getAttribute("action") + "#order";
    });
  }

  /* ---------- order builder (home page) ---------- */
  var orderDataEl = $("#order-data");
  var form = $("[data-order-form]");
  if (!orderDataEl || !form) return;

  var OD = JSON.parse(orderDataEl.textContent);
  var order = loadOrder();
  var rows = $$(".order-row", form);

  // Accept "?add=slug&qty=1&o0=..." from a product page without JS/storage.
  var params = new URLSearchParams(window.location.search);
  var addSlug = params.get("add");
  if (addSlug && OD.products[addSlug]) {
    var ap = OD.products[addSlug];
    var aopts = ap.options.map(function (g, gi) {
      var v = parseInt(params.get("o" + gi), 10);
      return v >= 0 && v < g.choices.length ? v : 0;
    });
    var addQty = Math.max(1, Math.min(50, parseInt(params.get("qty"), 10) || 1));
    var prevSt = order[addSlug];
    var sameOpts = prevSt && JSON.stringify(prevSt.opts) === JSON.stringify(aopts);
    order[addSlug] = { qty: Math.min(50, (sameOpts ? prevSt.qty : 0) + addQty), opts: aopts };
    saveOrder(order);
    if (window.history && history.replaceState) history.replaceState(null, "", window.location.pathname + "#order");
    window.addEventListener("load", function () {
      var target = $("#order");
      if (target) target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
    });
  }

  function lineFor(slug, state) {
    var p = OD.products[slug];
    var unit = p.price, from = p.from, quote = false, details = [];
    p.options.forEach(function (g, gi) {
      var c = g.choices[state.opts && state.opts[gi] != null ? state.opts[gi] : 0] || g.choices[0];
      details.push(c.label);
      if (g.priced) {
        from = !!c.from;
        if (c.price == null) quote = true; else unit = c.price;
      }
    });
    return { name: p.name, code: p.code, qty: state.qty, total: unit * state.qty, from: from, quote: quote, details: details };
  }
  function currentLines() {
    return rows.map(function (row) {
      var slug = row.getAttribute("data-product");
      var st = order[slug] || { qty: 0, opts: [] };
      return st.qty > 0 ? lineFor(slug, st) : null;
    }).filter(Boolean);
  }
  function priceText(l) { return l.quote ? "quote" : (l.from ? "from " : "") + euro(l.total); }

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
      var q = $("[data-qty]", row);
      if (document.activeElement !== q) q.value = st.qty;
      $$("select[data-opt]", row).forEach(function (sel) {
        var gi = +sel.getAttribute("data-opt");
        if (st.opts && st.opts[gi] != null) sel.value = String(st.opts[gi]);
      });
      row.classList.toggle("is-active", st.qty > 0);
      var base = OD.products[slug];
      $("[data-line-price]", row).textContent = st.qty > 0 ? priceText(lineFor(slug, st)) : (base.from ? "from " : "") + euro(base.price);
    });

    var lines = currentLines();
    var total = 0, anyFrom = false, anyQuote = false;
    summaryEl.innerHTML = "";
    if (!lines.length) {
      var empty = document.createElement("li");
      empty.className = "summary-empty";
      empty.textContent = "No gear selected yet.";
      summaryEl.appendChild(empty);
    }
    lines.forEach(function (l) {
      if (!l.quote) total += l.total;
      anyFrom = anyFrom || l.from;
      anyQuote = anyQuote || l.quote;
      var li = document.createElement("li");
      var name = document.createElement("span");
      name.textContent = l.qty + "× " + l.name;
      if (l.details.length) {
        var small = document.createElement("small");
        small.textContent = l.details.join(" · ");
        name.appendChild(small);
      }
      var price = document.createElement("span");
      price.className = "s-price";
      price.textContent = priceText(l);
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
      ? "Free EU shipping included."
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
    var q = $("[data-qty]", row);
    $$("[data-step]", row).forEach(function (btn) {
      btn.addEventListener("click", function () {
        setQty(slug, ((order[slug] && order[slug].qty) || 0) + +btn.getAttribute("data-step"));
      });
    });
    q.addEventListener("input", function () { setQty(slug, parseInt(q.value, 10) || 0); });
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
      out.push("- " + l.qty + "x " + l.code + " " + l.name + (l.details.length ? " (" + l.details.join(", ") + ")" : "") +
        ": " + (l.quote ? "price on request" : priceText(l)));
    });
    out.push("", "Subtotal ex VAT: " + (anyFrom ? "from " : "") + euro(total) + (anyQuote ? " + quote" : ""));
    var msg = String(fd.get("message") || "").trim();
    if (msg) out.push("", msg);
    out.push("", "Name: " + (fd.get("name") || ""), "Email: " + (fd.get("email") || ""));
    var country = String(fd.get("country") || "").trim();
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
      errorEl.textContent = "Add at least one product to your order first.";
      $(".order-summary .btn", form).insertAdjacentElement("afterend", errorEl);
      var firstStep = $('[data-step="1"]', form);
      if (firstStep) firstStep.focus();
      return;
    }
    if (!form.reportValidity()) return;
    var text = orderText();
    var subject = "Order request 3Deca: " + (new FormData(form).get("name") || "");
    $("[data-order-text]", form).value = "To: " + OD.email + "\nSubject: " + subject + "\n\n" + text;
    $("[data-order-fallback]", form).hidden = false;
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
