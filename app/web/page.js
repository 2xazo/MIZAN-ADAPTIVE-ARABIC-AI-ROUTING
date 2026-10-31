/* Interaction for the page iframes. Each block runs only when its section is in this iframe. */
(function () {
  "use strict";
  var D = window.MIZAN || {};
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* The iframe grows with its content, so the Streamlit document is the only scroller. */
  var page = $("#page");
  function fit() {
    try {
      var frame = window.frameElement;
      if (!frame) return;
      var h = Math.ceil(page.getBoundingClientRect().height) + "px";
      if (frame.style.height !== h) frame.style.height = h;
      // Streamlit fixes the wrapper at the first-paint height. Release it so later sections move with this one.
      var wrapper = frame.parentElement;
      if (wrapper && wrapper.style.flex !== "0 0 auto") { wrapper.style.height = "auto"; wrapper.style.flex = "0 0 auto"; }
    } catch (err) { /* cross-origin host: the height passed from Python stays */ }
  }
  if (window.ResizeObserver) new ResizeObserver(fit).observe(page);
  window.addEventListener("load", fit);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
  fit();

  /* Scrolling across the Streamlit document and the iframe. */
  var host = null;
  try { host = window.parent.document; } catch (err) { host = null; }
  function screenHeight() {
    var main = host && host.querySelector('[data-testid="stMain"]'), bar = host && host.querySelector(".mz-head");
    if (main && bar) document.documentElement.style.setProperty("--screen-h", (main.clientHeight - bar.getBoundingClientRect().height) + "px");
  }
  screenHeight();
  if (host) window.parent.addEventListener("resize", screenHeight);
  window.addEventListener("load", screenHeight);
  function locate(id) {
    if (!host) { var own = document.getElementById(id); return own ? { el: own, frame: null } : null; }
    var direct = id === "try" ? host.querySelector(".st-key-try") : host.getElementById(id);
    if (direct) return { el: direct, frame: null };
    var frames = $$("iframe", host);
    for (var i = 0; i < frames.length; i++) {
      try {
        var el = frames[i].contentDocument.getElementById(id);
        if (el) return { el: el, frame: frames[i] };
      } catch (err) { /* not ours */ }
    }
    return null;
  }
  function go(id) {
    var behavior = reduced ? "auto" : "smooth";
    var scroller = host ? host.querySelector('[data-testid="stMain"]') : null;
    if (id === "top") {
      if (scroller) scroller.scrollTo({ top: 0, behavior: behavior }); else window.scrollTo({ top: 0, behavior: behavior });
      return;
    }
    var target = locate(id);
    if (!target) return;
    if (target.el.tagName === "DETAILS") target.el.open = true;
    if (!scroller) { target.el.scrollIntoView({ behavior: behavior }); return; }
    var head = host.querySelector(".mz-head");
    var offset = head ? head.getBoundingClientRect().height : 0;
    var base = target.frame ? target.frame.getBoundingClientRect().top : 0;
    var y = base + target.el.getBoundingClientRect().top + scroller.scrollTop - offset;
    scroller.scrollTo({ top: Math.max(0, y), behavior: behavior });
  }
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest ? ev.target.closest("[data-go]") : null;
    if (a) { ev.preventDefault(); go(a.getAttribute("data-go")); }
  });
  if (host) {
    host.__mizanGo = go;
    if (!host.__mizanNav) {
      host.__mizanNav = true;
      host.addEventListener("click", function (ev) {
        var a = ev.target.closest ? ev.target.closest('.mz-head a[href^="#"]') : null;
        if (a) { ev.preventDefault(); host.__mizanGo(a.getAttribute("href").slice(1)); }
      });
    }
    /* A link that arrives with a section in the URL. */
    var arrival = window.parent.location.hash.slice(1);
    if (arrival && document.getElementById(arrival)) window.addEventListener("load", function () { setTimeout(function () { go(arrival); }, 300); });
  }

  /* Count-up. The final value is already in the markup. It only changes once a frame runs, and it always ends on the original text. */
  function countUp(el, delay) {
    if (reduced) return;
    var finalText = el.textContent;
    var parts = /^(\D*?)([+-]?)(\d+(?:\.\d+)?)(.*)$/.exec(finalText);
    if (!parts) return;
    var to = parseFloat(parts[3]), places = (parts[3].split(".")[1] || "").length, DURATION = 1100;
    setTimeout(function () {
      var started = null;
      var frame = function (now) {
        if (started === null) started = now;
        var t = Math.min(1, (now - started) / DURATION);
        if (t >= 1) { el.textContent = finalText; return; }
        var eased = 1 - Math.pow(1 - t, 3);
        el.textContent = parts[1] + parts[2] + (to * eased).toFixed(places) + parts[4];
        requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
      setTimeout(function () { el.textContent = finalText; }, DURATION + 900);
    }, delay || 0);
  }
  function onceInView(el, threshold, run) {
    if (!el || !window.IntersectionObserver) return;
    var watcher = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) { watcher.disconnect(); run(); }
    }, { threshold: threshold });
    watcher.observe(el);
  }
  $$('[data-count=""]').forEach(function (el) { countUp(el); });
  onceInView($(".metrics"), 0.3, function () {
    $$('[data-count="results"]').forEach(function (el, i) { countUp(el, i * 180); });
  });

  /* Demo: the meter fills, then the routing decision appears. Without this the panel simply shows its final state. */
  function playDemo(panel) {
    if (reduced || !panel) return;
    panel.classList.remove("play");
    panel.classList.add("armed");
    void panel.offsetWidth;
    setTimeout(function () { panel.classList.remove("armed"); panel.classList.add("play"); }, 40);
  }

  /* Metric cards and chips: click to expand in place, click again to collapse. */
  $$(".x-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var open = btn.getAttribute("aria-expanded") !== "true";
      var group = btn.closest("[data-group]");
      if (open && group && group.getAttribute("data-group") === "hero") {
        $$(".x-toggle", group).forEach(function (other) {
          other.setAttribute("aria-expanded", "false");
          document.getElementById(other.getAttribute("aria-controls")).classList.remove("open");
        });
      }
      btn.setAttribute("aria-expanded", String(open));
      document.getElementById(btn.getAttribute("aria-controls")).classList.toggle("open", open);
    });
  });

  /* Tabs: the demo selector and the technical evidence. */
  $$('[role="tablist"]').forEach(function (list) {
    var tabs = $$('[role="tab"]', list);
    function select(tab, focus) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
      });
      if (focus) tab.focus();
      var panel = document.getElementById(tab.getAttribute("aria-controls"));
      if (panel.classList.contains("demo-panel")) playDemo(panel);
    }
    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () { select(tab); });
      tab.addEventListener("keydown", function (ev) {
        if (ev.key === "ArrowRight") { ev.preventDefault(); select(tabs[(i + 1) % tabs.length], true); }
        if (ev.key === "ArrowLeft") { ev.preventDefault(); select(tabs[(i - 1 + tabs.length) % tabs.length], true); }
      });
    });
  });

  onceInView($("#panel-high"), 0.3, function () { playDemo($("#panel-high")); });

  /* Hero scale. */
  var stage = $("#stage");
  if (stage && D.scale) {
    var card = $("#scale-card");
    var beam = $(".beam", stage);
    var points = $$(".pt", stage);
    var tiltTimer = null;
    /* The card always shows the last point. Dimming happens only during an interaction, and the scale is otherwise at full colour. */
    var HOLD_AFTER_CLICK_MS = 2000;
    var held = { hover: 0, keyboard: 0, click: 0 };
    var clickTimer = null;
    var syncHighlight = function () {
      var n = held.hover || held.keyboard || held.click;
      if (n) stage.setAttribute("data-highlight", n); else stage.removeAttribute("data-highlight");
    };
    var activate = function (n) {
      stage.setAttribute("data-active", n);
      card.setAttribute("data-tone", n);
      $("strong", card).textContent = D.scale[n - 1].title;
      $("p", card).textContent = D.scale[n - 1].text;
      points.forEach(function (p) { p.classList.toggle("on", p.getAttribute("data-p") === String(n)); });
    };
    /* Only a click tilts the scale. It settles back level, so the resting state never depends on it. */
    var tilt = function (deg) {
      if (reduced) return;
      clearTimeout(tiltTimer);
      beam.style.setProperty("--tilt", deg + "deg");
      tiltTimer = setTimeout(function () { beam.style.setProperty("--tilt", "0deg"); }, 1300);
    };
    points.forEach(function (p) {
      var n = Number(p.getAttribute("data-p"));
      p.addEventListener("pointerenter", function (ev) {
        if (ev.pointerType !== "mouse") return;
        activate(n);
        held.hover = n;
        syncHighlight();
      });
      p.addEventListener("pointerleave", function (ev) {
        if (ev.pointerType !== "mouse") return;
        held.hover = 0;
        syncHighlight();
      });
      p.addEventListener("focus", function () {
        activate(n);
        if (p.matches(":focus-visible")) { held.keyboard = n; syncHighlight(); }
      });
      p.addEventListener("blur", function () {
        held.keyboard = 0;
        syncHighlight();
      });
      p.addEventListener("click", function () {
        activate(n);
        held.click = n;
        syncHighlight();
        clearTimeout(clickTimer);
        clickTimer = setTimeout(function () { held.click = 0; syncHighlight(); }, HOLD_AFTER_CLICK_MS);
        if (n === 2) tilt(-8);
        if (n === 4) tilt(8);
      });
    });
    activate(1);
  }

  /* Replay of the recorded per-item outcomes. */
  var play = $("#r-play");
  if (play && D.replay) {
    var R = D.replay;
    var total = R.ids.length;
    var BATCH = 10, STEP_MS = 160;  /* 50 steps, about 8 seconds */
    var timer = null;
    var pct = function (x, places) { return (x * 100).toFixed(places) + "%"; };
    var bar = $("#r-progress"), wrap = $("#r-progress-wrap");
    var show = function (v, upto) {
      $("#r-saving").textContent = v.saving;
      $("#r-accuracy").textContent = v.accuracy;
      $("#r-handled").textContent = v.handled;
      $("#r-count").textContent = String(upto);
      bar.style.width = (upto / total * 100) + "%";
      wrap.setAttribute("aria-valuenow", String(upto));
    };
    var showFinal = function () { show(R.final, total); };
    var at = function (upto) {
      var cost = 0, always = 0, ok = 0, esc = 0;
      for (var k = 0; k < upto; k++) { cost += R.cost[k]; always += R.always[k]; ok += R.ok[k]; esc += R.esc[k]; }
      show({ saving: pct(1 - cost / always, 0), accuracy: pct(ok / upto, 1), handled: pct((upto - esc) / upto, 1) }, upto);
    };
    var run = function () {
      clearInterval(timer);
      if (reduced) { showFinal(); return; }
      bar.style.transition = "none";
      bar.style.width = "0%";
      void bar.offsetWidth;
      bar.style.transition = "";
      $("#r-count").textContent = "0";
      var done = 0;
      timer = setInterval(function () {
        done = Math.min(total, done + BATCH);
        if (done >= total) { clearInterval(timer); showFinal(); return; }
        at(done);
      }, STEP_MS);
    };
    showFinal();
    play.addEventListener("click", run);
    onceInView($(".replay-main"), 0.5, run);
  }

  /* Cost and accuracy chart: MIZAN large and lime, the other four small and grey. */
  var chart = $("#chart");
  if (chart && D.chart && window.Plotly) {
    var C = D.chart;
    var GREY = "#A9C4C6", LIME = "#C6F23A";
    var narrow = function () { return window.innerWidth < 640; };
    var placement = {};
    placement.mizan = { xanchor: "center", yshift: 38 };
    placement.random = { xanchor: "left", xshift: 12, yshift: -22 };
    placement[C.small] = { xanchor: "left", xshift: 12, yshift: -22 };
    placement[C.mid] = { xanchor: "center", yshift: 32 };
    placement[C.large] = { xanchor: "right", xshift: -14, yshift: 26 };
    var traces = function () {
      return C.points.map(function (p) {
        var hero = p.key === "mizan";
        return {
          x: [p.x], y: [p.y], type: "scatter", mode: "markers", name: p.label,
          marker: { size: hero ? 24 : 10, color: hero ? LIME : GREY, line: hero ? { color: "#FFFFFF", width: 2 } : { width: 0 } },
          hovertext: [p.tip], hovertemplate: "%{hovertext}<extra></extra>", cliponaxis: false
        };
      });
    };
    var layout = function () {
      var compact = narrow();
      return {
        margin: { l: compact ? 48 : 64, r: compact ? 8 : 24, t: 16, b: compact ? 62 : 58 },
        paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", showlegend: false, hovermode: "closest", dragmode: false,
        font: { family: "Inter, 'Segoe UI', sans-serif", color: GREY, size: 13 },
        hoverlabel: { bgcolor: "#0B2E30", bordercolor: LIME, font: { family: "Inter, 'Segoe UI', sans-serif", color: "#FFFFFF", size: 13 }, align: "left" },
        xaxis: { title: { text: "Measured cost (always-large = 100)", standoff: 12 }, range: [0, 110], tickvals: [0, 20, 40, 60, 80, 100], showgrid: false, zeroline: false, linecolor: "#1C5A5F", fixedrange: true },
        yaxis: { title: { text: "Accuracy", standoff: 8 }, range: [0.71, 0.86], tickformat: ".0%", dtick: 0.05, gridcolor: "rgba(28,90,95,.45)", zeroline: false, fixedrange: true },
        annotations: C.points.map(function (p) {
          var hero = p.key === "mizan";
          var at = placement[p.key];
          var second = p.sub ? '<br><span style="font-size:' + (compact ? 10 : 11) + 'px;color:#7E9EA1">' + p.sub + "</span>" : "";
          return { x: p.x, y: p.y, xanchor: at.xanchor, xshift: at.xshift || 0, yshift: at.yshift, showarrow: false, align: at.xanchor,
                   text: (hero ? "<b>" + p.label + "</b>" : p.label) + second,
                   font: { size: hero ? 20 : (compact ? 11 : 13), color: hero ? LIME : GREY } };
        })
      };
    };
    var config = { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false };
    window.Plotly.newPlot(chart, traces(), layout(), config);
    var wasNarrow = narrow();
    window.addEventListener("resize", function () {
      if (narrow() !== wasNarrow) { wasNarrow = narrow(); window.Plotly.react(chart, traces(), layout(), config); }
    });
  }

  /* Accepted-error bars: hover, focus or tap shows the exact value and what it means. */
  var etip = $("#etip");
  if (etip) {
    $$(".ebar").forEach(function (b) {
      var on = function () { etip.textContent = b.getAttribute("data-tip"); etip.classList.add("on"); };
      b.addEventListener("mouseenter", on);
      b.addEventListener("focus", on);
      b.addEventListener("click", on);
    });
    etip.textContent = $(".ebar").getAttribute("data-tip");
  }

  /* Robustness toggle. */
  var stack = $("#optstack");
  if (stack && D.robust) {
    var Rb = D.robust;
    var ROW = 60;
    var letters = "ABCDE";
    var rows = $$(".optrow", stack);
    var place = function (shuffled) {
      rows.forEach(function (row, i) {
        var pos = shuffled ? Rb.shuffled_positions[i] : i;
        row.style.transform = "translateY(" + (pos * ROW) + "px)";
        $("bdi", row).textContent = letters[pos];
      });
    };
    var original = $("#rb-original"), shuffled = $("#rb-shuffled");
    var mode = function (isShuffled) {
      original.setAttribute("aria-pressed", String(!isShuffled));
      shuffled.setAttribute("aria-pressed", String(isShuffled));
      place(isShuffled);
    };
    original.addEventListener("click", function () { mode(false); });
    shuffled.addEventListener("click", function () { mode(true); });
    place(false);
  }

  /* Impact slider: the measured rates applied to the chosen task count. */
  var range = $("#impact-range");
  if (range && D.impact) {
    var fmt = function (n) { return n.toLocaleString("en-US"); };
    var nice = function (v) {
      var mag = Math.pow(10, Math.floor(Math.log10(v)) - 1);
      return Math.round(v / mag) * mag;
    };
    var update = function () {
      var tasks = nice(Math.pow(10, 4 + Number(range.value) / 100));
      var handled = Math.round(tasks * D.impact.handled);
      $("#impact-n").textContent = fmt(tasks);
      $("#impact-handled").textContent = fmt(handled);
      $("#impact-esc").textContent = fmt(tasks - handled);
      range.setAttribute("aria-valuetext", fmt(tasks) + " tasks");
    };
    range.addEventListener("input", update);
    update();
  }
})();
