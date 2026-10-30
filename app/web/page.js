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

  /* Scrolling across the Streamlit document and both iframes. */
  var host = null;
  try { host = window.parent.document; } catch (err) { host = null; }
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
    }
    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () { select(tab); });
      tab.addEventListener("keydown", function (ev) {
        if (ev.key === "ArrowRight") { ev.preventDefault(); select(tabs[(i + 1) % tabs.length], true); }
        if (ev.key === "ArrowLeft") { ev.preventDefault(); select(tabs[(i - 1 + tabs.length) % tabs.length], true); }
      });
    });
  });

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
    var BATCH = 10, STEP_MS = 200;
    var timer = null;
    var pct = function (x, places) { return (x * 100).toFixed(places) + "%"; };
    var bar = $("#r-progress"), wrap = $("#r-progress-wrap"), feed = $("#r-feed");
    var drawFeed = function (upto) {
      var html = "";
      for (var k = upto - 1; k >= Math.max(0, upto - 5); k--) {
        html += R.esc[k]
          ? '<li class="x"><span>Request ' + (k + 1) + "</span><b>Escalated</b></li>"
          : '<li class="h"><span>Request ' + (k + 1) + "</span><b>Handled efficiently</b></li>";
      }
      feed.innerHTML = html;
    };
    var show = function (v, upto) {
      $("#r-saving").textContent = v.saving;
      $("#r-accuracy").textContent = v.accuracy;
      $("#r-handled").textContent = v.handled;
      $("#r-cost").textContent = v.cost;
      $("#r-count").textContent = String(upto);
      bar.style.width = (upto / total * 100) + "%";
      wrap.setAttribute("aria-valuenow", String(upto));
      drawFeed(upto);
    };
    var showFinal = function () { show(R.final, total); };
    var at = function (upto) {
      var cost = 0, always = 0, ok = 0, esc = 0;
      for (var k = 0; k < upto; k++) { cost += R.cost[k]; always += R.always[k]; ok += R.ok[k]; esc += R.esc[k]; }
      show({ saving: pct(1 - cost / always, 2), accuracy: pct(ok / upto, 1), handled: pct((upto - esc) / upto, 1), cost: pct(cost / always, 2) }, upto);
    };
    showFinal();
    play.addEventListener("click", function () {
      clearInterval(timer);
      if (reduced) { showFinal(); return; }
      play.disabled = true;
      play.textContent = "Replaying";
      bar.style.transition = "none";
      bar.style.width = "0%";
      void bar.offsetWidth;
      bar.style.transition = "";
      var done = 0;
      timer = setInterval(function () {
        done = Math.min(total, done + BATCH);
        if (done >= total) {
          clearInterval(timer);
          showFinal();
          play.disabled = false;
          play.textContent = "Replay";
          return;
        }
        at(done);
      }, STEP_MS);
    });
  }

  /* Cost and accuracy chart. */
  var chart = $("#chart");
  if (chart && D.chart && window.Plotly) {
    var C = D.chart;
    var byKey = {};
    C.points.forEach(function (p) { byKey[p.key] = p; });
    var mizan = byKey.mizan, top = byKey[C.large], small = byKey[C.small];
    var emphasized = false;
    var touch = window.matchMedia("(hover: none)").matches;
    var hintIdle = touch ? "Tap any point for details. Tap MIZAN to emphasize the callouts." : "Hover any point for details. Click MIZAN to emphasize the callouts.";
    var hintOn = (touch ? "Callouts emphasized. Tap" : "Callouts emphasized. Click") + " MIZAN again to reset.";
    $("#chart-hint").textContent = hintIdle;
    var COLORS = { mizan: "#C6F23A", other: "#A9C4C6" };
    var narrow = function () { return window.innerWidth < 640; };
    var traces = function () {
      var compact = narrow();
      return C.points.map(function (p) {
        var hero = p.key === "mizan";
        var positions = { mizan: "top left", random: "bottom right" };
        positions[C.small] = "bottom right";
        positions[C.large] = "top left";
        return {
          x: [p.x], y: [p.y], type: "scatter", mode: "markers+text", name: p.label,
          text: [p.key === C.large && !compact ? p.label : p.short], textposition: positions[p.key] || "top left",
          textfont: { family: "Inter, sans-serif", size: hero ? 16 : (compact ? 11 : 13), color: hero ? "#C6F23A" : "#A9C4C6" },
          marker: { size: hero ? 20 : 11, color: hero ? COLORS.mizan : COLORS.other, opacity: hero ? 1 : 0.75, line: hero ? { color: "#FFFFFF", width: 2 } : { width: 0 } },
          error_y: { type: "data", symmetric: false, array: [p.high - p.y], arrayminus: [p.y - p.low], color: hero ? "rgba(198,242,58,.55)" : "rgba(169,196,198,.35)", thickness: 1.5, width: 4 },
          hovertext: [p.tip], hovertemplate: "%{hovertext}<extra></extra>", cliponaxis: false
        };
      });
    };
    var layout = function () {
      var compact = narrow();
      var gapX = (small.x + mizan.x) / 2 + 5;
      var color = emphasized ? "#C6F23A" : "rgba(198,242,58,.6)";
      var cyan = emphasized ? "#2EC4D6" : "rgba(46,196,214,.6)";
      var w = emphasized ? 2.5 : 1.25;
      var line = function (x0, y0, x1, y1, c, dash) {
        return { type: "line", xref: "x", yref: "y", x0: x0, y0: y0, x1: x1, y1: y1, line: { color: c, width: w, dash: dash || "solid" }, layer: "below" };
      };
      var size = (compact ? 12 : 14) + (emphasized ? 2 : 0);
      return {
        margin: { l: compact ? 44 : 60, r: compact ? 8 : 20, t: 12, b: compact ? 62 : 58 },
        paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", showlegend: false, hovermode: "closest", dragmode: false,
        font: { family: "Inter, sans-serif", color: "#A9C4C6", size: 12 },
        hoverlabel: { bgcolor: "#0B2E30", bordercolor: "#C6F23A", font: { family: "Inter, sans-serif", color: "#FFFFFF", size: 13 }, align: "left" },
        xaxis: { title: { text: compact ? "Relative inference cost<br>(Always " + C.large + " = 100)" : "Relative inference cost (Always " + C.large + " = 100)", standoff: 12 }, range: [-3, 112], tickvals: [0, 20, 40, 60, 80, 100], showgrid: false, zeroline: false, linecolor: "#1C5A5F", fixedrange: true },
        yaxis: { title: { text: "Accuracy", standoff: 8 }, range: [0.67, 0.875], tickformat: ".0%", dtick: 0.05, gridcolor: "rgba(28,90,95,.45)", zeroline: false, fixedrange: true },
        shapes: [
          line(mizan.x, mizan.y, top.x, mizan.y, cyan),
          line(top.x, mizan.y, top.x, top.y, cyan, "dot"),
          line(small.x, small.y, gapX, small.y, color, "dot"),
          line(gapX, small.y, gapX, mizan.y, color),
          line(gapX, mizan.y, mizan.x, mizan.y, color, "dot")
        ],
        annotations: [
          { x: (mizan.x + top.x) / 2, y: mizan.y, yshift: 14, text: "<b>" + C.cost_callout + "</b>", showarrow: false, font: { size: size, color: "#2EC4D6" } },
          { x: gapX + 1, y: small.y - 0.016, xanchor: "left", text: "<b>" + C.acc_callout + "</b>", showarrow: false, font: { size: size, color: "#C6F23A" } }
        ]
      };
    };
    var config = { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false };
    var draw = function () { return window.Plotly.react(chart, traces(), layout(), config); };
    window.Plotly.newPlot(chart, traces(), layout(), config).then(function () {
      chart.on("plotly_click", function (ev) {
        if (ev.points && ev.points[0] && ev.points[0].data.name === "MIZAN") {
          emphasized = !emphasized;
          $("#chart-hint").textContent = emphasized ? hintOn : hintIdle;
          window.Plotly.relayout(chart, { shapes: layout().shapes, annotations: layout().annotations });
        }
      });
    });
    var wasNarrow = narrow();
    window.addEventListener("resize", function () {
      if (narrow() !== wasNarrow) { wasNarrow = narrow(); draw(); }
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
    stack.style.height = (Rb.options.length * ROW) + "px";
    var rows = Rb.options.map(function (text) {
      var row = document.createElement("div");
      row.className = "optrow";
      var bdi = document.createElement("bdi");
      bdi.className = "letter";
      var span = document.createElement("span");
      span.textContent = text;
      row.appendChild(bdi);
      row.appendChild(span);
      stack.appendChild(row);
      return row;
    });
    var auroc = $("#rb-auroc");
    var tween = null;
    var place = function (shuffled) {
      rows.forEach(function (row, i) {
        var pos = shuffled ? Rb.shuffled_positions[i] : i;
        row.style.transform = "translateY(" + (pos * ROW) + "px)";
        $("bdi", row).textContent = letters[pos];
      });
    };
    var setValue = function (target) {
      cancelAnimationFrame(tween);
      if (reduced) { auroc.textContent = target; return; }
      var from = parseFloat(auroc.textContent), to = parseFloat(target), started = performance.now();
      var frame = function (now) {
        var t = Math.min(1, (now - started) / 600);
        auroc.textContent = t === 1 ? target : (from + (to - from) * t).toFixed(3);
        if (t < 1) tween = requestAnimationFrame(frame);
      };
      tween = requestAnimationFrame(frame);
    };
    var original = $("#rb-original"), shuffled = $("#rb-shuffled");
    var mode = function (isShuffled) {
      original.setAttribute("aria-pressed", String(!isShuffled));
      shuffled.setAttribute("aria-pressed", String(isShuffled));
      place(isShuffled);
      setValue(isShuffled ? Rb.shuffled : Rb.original);
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
    var split = $$("#impact-split i");
    var grow = function () {
      if (reduced) return;
      split.forEach(function (bar) { bar.style.transition = "none"; bar.style.width = "0"; });
      void split[0].offsetWidth;
      split.forEach(function (bar) { bar.style.transition = ""; bar.style.width = bar.getAttribute("data-w") + "%"; });
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
    if (window.IntersectionObserver) {
      var seen = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting) { seen.disconnect(); grow(); }
      }, { threshold: 0.4 });
      seen.observe($("#impact-split"));
    }
  }
})();
