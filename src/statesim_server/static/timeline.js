// Timeline pane: swimlanes of the state machines over time, a row of input
// changes, and a sequence chart of what a clicked event caused.
// Used by app.js (window.StateSimTimeline). All model text goes in as
// textContent. Times are milliseconds in the data and seconds on screen.
//
// Items (see src/statesim/timeline.py):
//   {k:"tr", id, t, tick, sm, tid, title, from, to, causes:[ids], writes:[[var, value], ...]}
//   {k:"in", id, t, tick, name, value}
//
// First state of a lane: the "from" of the machine's oldest transition in
// the data. Before its first transition: the state last reported by the
// server (the "states" of a state message), or else machine.states[0].
"use strict";

(function () {
  const NS = "http://www.w3.org/2000/svg";
  const LABEL_W = 140;        // label column
  const ROW_H = 30;           // one lane
  const AXIS_H = 20;
  const PAD_R = 16;
  const WINDOW_MS = 30000;    // visible time span
  const CAP = 20000;          // items kept
  const PALETTE = 8;
  const SEQ_MAX_ROWS = 200;
  const KEY_SHOWN = "statesim.timelineShown", KEY_H = "statesim.timelineHeight";
  const DEFAULT_H = 260, MIN_H = 120, MAX_FRACTION = 0.7, KEY_STEP = 20;

  const svg = (tag, cls, attrs) => {
    const e = document.createElementNS(NS, tag);
    if (cls) e.setAttribute("class", cls);
    if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  };
  const html = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const withTitle = (node, text) => {
    const t = svg("title");
    t.textContent = text;
    node.append(t);
    return node;
  };
  const seconds = (ms) => String(Math.round(ms) / 1000);
  const value = (v) => (typeof v === "number" && !Number.isInteger(v) ? String(Number(v.toFixed(3))) : String(v));
  const trTitle = (it) => `${it.tid}: ${it.title ? it.title + " " : ""}(${it.from} -> ${it.to})`;
  const inTitle = (it) => `${it.name} = ${value(it.value)}`;

  // Text widths, measured on a canvas and cached (state names repeat a lot).
  const measure = (() => {
    let ctx = null;
    const cache = new Map();
    return (text, font) => {
      const key = font + "|" + text;
      let w = cache.get(key);
      if (w === undefined) {
        if (!ctx) ctx = document.createElement("canvas").getContext("2d");
        ctx.font = font;
        w = ctx.measureText(text).width;
        if (cache.size > 5000) cache.clear();
        cache.set(key, w);
      }
      return w;
    };
  })();
  function ellipsis(text, font, max) {
    if (measure(text, font) <= max) return text;
    let n = text.length;
    while (n > 1 && measure(text.slice(0, n) + "…", font) > max) n--;
    return text.slice(0, n) + "…";
  }
  // First index whose item has t >= time (items are in time order).
  function lowerBound(list, time) {
    let lo = 0, hi = list.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (list[mid].t < time) lo = mid + 1; else hi = mid;
    }
    return lo;
  }

  // ------------------------------------------------------------------ pane
  // The pane, its splitter and its run-bar button are in index.html. They
  // work before a model arrives; an instance only draws inside the pane.
  const pane = { el: null, bar: null, btn: null, instance: null };

  const store = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, v) { try { localStorage.setItem(key, v); } catch { /* ignore */ } },
  };
  const maxH = () => Math.max(MIN_H, Math.floor(window.innerHeight * MAX_FRACTION));
  function setH(h) {
    h = Math.round(Math.min(maxH(), Math.max(MIN_H, h)));
    pane.el.style.height = h + "px";
    pane.bar.setAttribute("aria-valuenow", h);
    pane.bar.setAttribute("aria-valuemin", MIN_H);
    pane.bar.setAttribute("aria-valuemax", maxH());
    return h;
  }
  const paneH = () => parseFloat(pane.el.style.height) || DEFAULT_H;
  function setShown(on, save) {
    if (!pane.el) return;
    pane.el.hidden = !on;
    pane.bar.hidden = !on;
    if (pane.btn) pane.btn.setAttribute("aria-pressed", String(on));
    if (save) store.set(KEY_SHOWN, on ? "1" : "0");
    if (pane.instance) pane.instance.refresh();
  }
  function initPane() {
    pane.el = document.getElementById("timeline");
    pane.bar = document.getElementById("timeline-splitter");
    pane.btn = document.getElementById("timeline-toggle");
    if (!pane.el || !pane.bar) { pane.el = pane.bar = null; return; }
    const saved = Number(store.get(KEY_H));
    setH(saved > 0 ? saved : DEFAULT_H);
    setShown(store.get(KEY_SHOWN) === "1", false);
    if (pane.btn) pane.btn.addEventListener("click", () => setShown(pane.el.hidden, true));
    const bar = pane.bar;
    bar.addEventListener("pointerdown", (e) => {
      bar.setPointerCapture(e.pointerId);
      bar.classList.add("dragging"); document.body.classList.add("resizing-v");
      const startY = e.clientY, startH = paneH();
      const move = (ev) => setH(startH - (ev.clientY - startY));
      const up = () => {
        bar.removeEventListener("pointermove", move); bar.removeEventListener("pointerup", up);
        bar.removeEventListener("pointercancel", up);
        bar.classList.remove("dragging"); document.body.classList.remove("resizing-v");
        store.set(KEY_H, String(paneH()));
      };
      bar.addEventListener("pointermove", move); bar.addEventListener("pointerup", up);
      bar.addEventListener("pointercancel", up);
    });
    bar.addEventListener("keydown", (e) => {
      const d = e.key === "ArrowUp" ? KEY_STEP : e.key === "ArrowDown" ? -KEY_STEP : 0;
      if (!d) return;
      store.set(KEY_H, String(setH(paneH() + d)));
      e.preventDefault();
    });
    window.addEventListener("resize", () => setH(paneH()));
  }

  // -------------------------------------------------------------- instance
  function build(container, machines, opts) {
    opts = opts || {};
    const span = opts.windowMs > 0 ? opts.windowMs : WINDOW_MS;
    const cap = opts.cap > 0 ? opts.cap : CAP;

    // ---- data
    let gen = null;
    let items = [];              // every kept item, oldest first
    let byId = new Map();
    let inputs = [];
    let now = 0;
    let dropped = false;         // the oldest items are gone (cap)
    const lanes = new Map();     // machine name -> lane
    const laneList = [];
    machines.forEach((m, i) => {
      const colour = new Map();
      m.states.forEach((s, k) => colour.set(s, k % PALETTE));
      const lane = { name: m.name, label: m.label || m.name, row: i + 1, trs: [], colour,
                     last: undefined, hint: undefined, first: m.states[0] };
      lanes.set(m.name, lane);
      laneList.push(lane);
    });
    const rowsH = (laneList.length + 1) * ROW_H;

    // ---- view
    let follow = true;
    let viewStart = 0;
    let width = 0;
    let hover = null, selected = null;
    let closure = null;          // ids of the selected item and all it caused
    let chartDirty = false;
    let hits = [];
    let mouse = null;
    let frame = 0;
    let alive = true;

    // ---- DOM
    const fontFamily = getComputedStyle(document.body).fontFamily || "sans-serif";
    const F_BAR = `600 10px ${fontFamily}`, F_TID = `700 9px ${fontFamily}`, F_IN = `500 9px ${fontFamily}`;
    const F_LABEL = `600 12px ${fontFamily}`, F_SEQ = `600 11px ${fontFamily}`;

    const lanesBox = html("div", "tl-lanes");
    const root = svg("svg", "tl-svg", { height: rowsH + AXIS_H, role: "img", "aria-label": "State machines over time" });
    const clipId = "tl-clip-" + (++build.count);
    const defs = svg("defs");
    const clip = svg("clipPath", null, { id: clipId });
    const clipRect = svg("rect", null, { x: LABEL_W, y: 0, width: 0, height: rowsH + AXIS_H });
    clip.append(clipRect);
    defs.append(clip);
    const gStatic = svg("g");
    const gGrid = svg("g", null, { "clip-path": `url(#${clipId})` });
    const gBars = svg("g", null, { "clip-path": `url(#${clipId})` });
    const gMarks = svg("g", null, { "clip-path": `url(#${clipId})` });
    const gCauses = svg("g", "tl-causes", { "clip-path": `url(#${clipId})` });
    const gAxis = svg("g", "tl-axis");
    const cursor = svg("line", "tl-cursor", { y1: 0, y2: rowsH });
    root.append(defs, gStatic, gGrid, gBars, gMarks, gCauses, gAxis, cursor);

    const plotBg = svg("rect", "tl-plot", { x: LABEL_W, y: 0, width: 0, height: rowsH });
    gStatic.append(plotBg);
    const rowLines = [];
    for (let r = 0; r <= laneList.length + 1; r++) {
      const ln = svg("line", "tl-rowline", { x1: 0, y1: r * ROW_H + 0.5, y2: r * ROW_H + 0.5 });
      rowLines.push(ln);
      gStatic.append(ln);
    }
    gStatic.append(svg("line", "tl-rowline", { x1: LABEL_W + 0.5, x2: LABEL_W + 0.5, y1: 0, y2: rowsH }));
    const rowLabel = (text, row, cls) => {
      const t = svg("text", "tl-label" + (cls ? " " + cls : ""), { x: 12, y: row * ROW_H + ROW_H / 2 + 4 });
      t.textContent = ellipsis(text, F_LABEL, LABEL_W - 20);
      const g = withTitle(svg("g"), text);      // the full name on hover
      g.append(t);
      gStatic.append(g);
    };
    rowLabel("Inputs", 0, "tl-label-inputs");
    for (const lane of laneList) rowLabel(lane.label, lane.row);

    const live = html("button", "btn tl-live", "Live");
    live.type = "button";
    live.hidden = true;
    live.title = "Follow the run again";
    const tip = html("div", "tl-tip");
    tip.hidden = true;
    lanesBox.append(root, live, tip);

    const chart = html("div", "tl-chart");
    chart.hidden = true;
    const chartHead = html("div", "tl-chart-head");
    const chartTitle = html("span", "tl-chart-title");
    const close = html("button", "btn tl-close", "Close");
    close.type = "button";
    close.setAttribute("aria-label", "Close sequence chart");
    chartHead.append(chartTitle, close);
    const chartBody = html("div", "tl-chart-body");
    chart.append(chartHead, chartBody);
    container.replaceChildren(lanesBox, chart);

    // ---- data handling
    const laneStart = () => (dropped && items.length ? items[0].t : 0);
    const firstState = (lane) => (lane.trs.length ? lane.trs[0].from
      : lane.last !== undefined ? lane.last : lane.hint !== undefined ? lane.hint : lane.first);

    function clear() {
      items = []; byId = new Map(); inputs = []; now = 0; dropped = false;
      for (const lane of laneList) { lane.trs = []; lane.last = undefined; lane.hint = undefined; }
      follow = true; viewStart = 0;
      hover = null; selected = null; closure = null; hits = [];
      chart.hidden = true;
      chartBody.replaceChildren();
      tip.hidden = true;
    }

    function trim() {
      const cut = items.length - cap;
      const minId = items[cut].id;
      for (let i = 0; i < cut; i++) byId.delete(items[i].id);
      items = items.slice(cut);
      const keep = (list) => {
        let i = 0;
        while (i < list.length && list[i].id < minId) i++;
        return i ? list.slice(i) : list;
      };
      inputs = keep(inputs);
      for (const lane of laneList) lane.trs = keep(lane.trs);
      dropped = true;
    }

    function addItems(list) {
      for (const it of list) {
        if (!it || byId.has(it.id)) continue;
        if (!items.length && it.id > 1) dropped = true;     // the server's cap already dropped some
        items.push(it);
        byId.set(it.id, it);
        if (it.k === "in") inputs.push(it);
        else if (it.k === "tr") {
          const lane = lanes.get(it.sm);
          if (lane) { lane.trs.push(it); lane.last = it.to; }
          if (closure && it.causes && it.causes.some((c) => closure.has(c))) {
            closure.add(it.id);
            chartDirty = true;
          }
        }
        if (it.t > now) now = it.t;
      }
      if (items.length > cap * 1.1) trim();
    }

    function reset(newGen, list) {
      clear();
      gen = newGen === undefined ? null : newGen;
      addItems(list || []);
      refresh();
    }

    function add(list, t, states) {
      if (list && list.length) addItems(list);
      if (typeof t === "number" && isFinite(t)) now = t;
      if (states) for (const lane of laneList) if (lane.last === undefined) lane.hint = states[lane.name];
      refresh();
    }

    // One "state" message: tl/t/gen are optional (older servers send none).
    function state(st) {
      if (!st) return;
      if (st.gen !== undefined && st.gen !== gen) { clear(); gen = st.gen; refresh(); }
      if (st.tl === undefined && st.t === undefined) return;
      add(st.tl, st.t, st.states);
    }

    // ---- drawing
    function refresh() {
      if (!alive || frame) return;
      frame = requestAnimationFrame(() => { frame = 0; draw(); });
    }

    const plotW = () => Math.max(1, width - LABEL_W - PAD_R);
    const liveStart = () => Math.max(0, now - span);
    const xOf = (t) => LABEL_W + (t - viewStart) * plotW() / span;
    const rowY = (item) => (item.k === "in" ? 20 : (lanes.get(item.sm) ? lanes.get(item.sm).row * ROW_H + 19 : -1));

    function draw() {
      if (!alive) return;
      width = container.clientWidth;
      if (width <= LABEL_W + PAD_R + 20) return;
      root.setAttribute("width", width);
      clipRect.setAttribute("width", width - LABEL_W);
      plotBg.setAttribute("width", width - LABEL_W);
      for (const ln of rowLines) ln.setAttribute("x2", width);

      const ls = liveStart();
      if (follow) viewStart = ls;
      else {
        viewStart = Math.min(ls, Math.max(0, viewStart));
        if (viewStart >= ls - 0.5) follow = true;
      }
      live.hidden = follow;
      const t0 = viewStart, t1 = viewStart + span;
      const right = width;
      hits = [];

      const bars = document.createDocumentFragment();
      const marks = document.createDocumentFragment();
      drawInputs(marks, t0, t1);
      for (const lane of laneList) drawLane(lane, bars, marks, t0, t1);
      gBars.replaceChildren(bars);
      gMarks.replaceChildren(marks);
      drawAxis(t0, t1, right);
      drawCauses();

      const cx = xOf(now);
      if (now >= t0 && cx <= right) {
        cursor.setAttribute("x1", cx); cursor.setAttribute("x2", cx);
        cursor.removeAttribute("visibility");
      } else cursor.setAttribute("visibility", "hidden");

      if (chartDirty) renderChart();
      if (mouse && !mouse.drag) {            // the lanes moved under a resting pointer
        const h = hitAt(mouse.x, mouse.y);
        if (h !== hover) { setHover(h); }
      }
    }

    function markClass(base, it) {
      return base + (selected === it ? " sel" : "") + (hover === it ? " hover" : "");
    }

    function drawInputs(out, t0, t1) {
      let lastDot = -10, labelEnd = -10;
      for (let i = lowerBound(inputs, t0); i < inputs.length; i++) {
        const it = inputs[i];
        if (it.t > t1) break;
        const x = xOf(it.t);
        const special = it === selected || it === hover;
        if (x - lastDot < 2 && !special) continue;
        lastDot = x;
        const g = svg("g", markClass("tl-dot", it), { "data-id": it.id });
        withTitle(g, inTitle(it));
        g.append(svg("circle", null, { cx: x, cy: 20, r: 3.5 }));
        let x1 = x + 6;                        // the hit area covers the dot and its label
        if (x - 3 >= labelEnd + 5 || special) {
          const t = svg("text", "tl-in-label", { x: x - 3, y: 11 });
          t.textContent = it.name;
          g.append(t);
          labelEnd = x - 3 + measure(it.name, F_IN);
          x1 = Math.max(x1, labelEnd);
        }
        g.append(svg("rect", "tl-hit", { x: x - 6, y: 2, width: x1 - x + 6, height: 26 }));
        hits.push({ x0: x - 6, x1, y0: 2, y1: 28, ax: x, item: it });
        out.append(g);
      }
    }

    function drawLane(lane, bars, marks, t0, t1) {
      const trs = lane.trs;
      const y = lane.row * ROW_H;
      const end = Math.min(now, t1);
      let i = lowerBound(trs, t0);
      let st = i > 0 ? trs[i - 1].to : firstState(lane);
      let from = Math.max(t0, i > 0 ? trs[i - 1].t : laneStart());
      let denseA = null, denseB = 0, lastTick = -10, labelEnd = -10;
      const flush = () => {
        if (denseA === null) return;
        bars.append(svg("rect", "tl-bar tl-dense", { x: denseA, y: y + 11, width: Math.max(1, denseB - denseA), height: 16 }));
        denseA = null;
      };
      let thin = false;                          // the bar just drawn was merged
      const bar = (name, a, b) => {
        thin = false;
        if (b <= a) return;
        const xa = xOf(a), xb = xOf(b);
        if (xb - xa < 3) {                       // too thin to see: merge into one block
          if (denseA === null) denseA = xa;
          denseB = xb;
          thin = true;
          return;
        }
        flush();
        const k = lane.colour.get(name);
        const w = xb - xa - 1;
        const r = svg("rect", "tl-bar tl-s" + (k === undefined ? "x" : k),
                      { x: xa + 0.5, y: y + 11, width: w, height: 16, rx: 3 });
        withTitle(r, name);
        bars.append(r);
        if (measure(name, F_BAR) + 10 <= w) {
          const t = svg("text", "tl-bar-text", { x: xa + 5.5, y: y + 22.5 });
          t.textContent = name;
          bars.append(t);
        }
      };
      for (;; i++) {
        const more = i < trs.length && trs[i].t <= end;
        bar(st, from, more ? trs[i].t : end);
        if (!more) break;
        const it = trs[i];
        const x = xOf(it.t);
        const special = it === selected || it === hover;
        const next = i + 1 < trs.length && trs[i + 1].t <= end ? trs[i + 1].t : end;
        const inside = thin && xOf(next) - x < 3;          // between two merged bars: no tick
        if ((x - lastTick >= 2 && !inside) || special) {
          lastTick = x;
          const g = svg("g", markClass("tl-tick", it), { "data-id": it.id });
          withTitle(g, trTitle(it));
          g.append(svg("line", null, { x1: x, x2: x, y1: y + 2, y2: y + 28 }));
          let x1 = x + 4;                      // the hit area covers the tick and its label
          if (x + 3 >= labelEnd + 4 || special) {
            const t = svg("text", "tl-tid", { x: x + 3, y: y + 9 });
            t.textContent = it.tid;
            g.append(t);
            labelEnd = x + 3 + measure(it.tid, F_TID);
            x1 = Math.max(x1, labelEnd);
          }
          g.append(svg("rect", "tl-hit", { x: x - 4, y: y + 1, width: x1 - x + 4, height: ROW_H - 2 }));
          hits.push({ x0: x - 4, x1, y0: y, y1: y + ROW_H, ax: x, item: it });
          marks.append(g);
        }
        st = it.to;
        from = it.t;
      }
      flush();
    }

    function drawAxis(t0, t1, right) {
      const pxPerS = plotW() / span * 1000;
      let step = 1;
      for (const s of [1, 2, 5, 10, 30, 60, 120, 300, 600]) { step = s; if (s * pxPerS >= 48) break; }
      const axis = document.createDocumentFragment();
      const grid = document.createDocumentFragment();
      axis.append(svg("line", "tl-axis-line", { x1: LABEL_W, x2: right, y1: rowsH + 0.5, y2: rowsH + 0.5 }));
      const minor = pxPerS >= 6;
      for (let s = Math.ceil(t0 / 1000); s * 1000 <= t1 + (PAD_R * span / plotW()); s++) {
        const x = Math.round(xOf(s * 1000)) + 0.5;
        if (x < LABEL_W || x > right) continue;
        const major = s % step === 0;
        if (!major && !minor) continue;
        axis.append(svg("line", "tl-axis-tick", { x1: x, x2: x, y1: rowsH, y2: rowsH + (major ? 6 : 3) }));
        if (!major) continue;
        grid.append(svg("line", "tl-grid", { x1: x, x2: x, y1: 0, y2: rowsH }));
        const t = svg("text", "tl-axis-text", { x, y: rowsH + 16 });
        t.textContent = s + " s";
        axis.append(t);
      }
      gAxis.replaceChildren(axis);
      gGrid.replaceChildren(grid);
    }

    // Dashed lines from the hovered and the selected transition to their causes.
    function drawCauses() {
      const out = document.createDocumentFragment();
      const done = new Set();
      for (const it of [selected, hover]) {
        if (!it || it.k !== "tr" || done.has(it.id) || !it.causes) continue;
        done.add(it.id);
        const x2 = xOf(it.t), y2 = rowY(it);
        if (y2 < 0) continue;
        for (const cid of it.causes) {
          const c = byId.get(cid);
          if (!c) continue;
          const x1 = xOf(c.t), y1 = rowY(c);
          if (y1 < 0) continue;
          out.append(svg("line", "tl-cause", { x1, y1, x2, y2, "data-from": c.id, "data-to": it.id }));
          out.append(svg("circle", "tl-cause-end", { cx: x1, cy: y1, r: 2.5 }));
        }
      }
      gCauses.replaceChildren(out);
    }

    // ---- pointer: hover, click, pan
    function hitAt(x, y) {
      let best = null, d = Infinity;
      for (const h of hits) {
        if (x < h.x0 || x > h.x1 || y < h.y0 || y > h.y1) continue;
        const dx = Math.abs(x - h.ax);
        if (dx < d) { d = dx; best = h.item; }
      }
      return best;
    }
    function local(e) {
      const r = root.getBoundingClientRect();
      return { x: e.clientX - r.left, y: e.clientY - r.top };
    }
    function setHover(item) {
      hover = item;
      root.classList.toggle("tl-pointing", !!item);
      showTip();
      refresh();
    }
    function showTip() {
      if (!hover || !mouse) { tip.hidden = true; return; }
      const it = hover;
      tip.replaceChildren();
      if (it.k === "tr") {
        const lane = lanes.get(it.sm);
        tip.append(html("div", "tl-tip-head", it.title ? `${it.tid}: ${it.title}` : it.tid),
                   html("div", null, `${it.from} -> ${it.to}`),
                   html("div", "tl-tip-meta", `${lane ? lane.label : it.sm}, ${seconds(it.t)} s`));
      } else {
        tip.append(html("div", "tl-tip-head", inTitle(it)),
                   html("div", "tl-tip-meta", `${seconds(it.t)} s`));
      }
      tip.hidden = false;
      const w = tip.offsetWidth, h = tip.offsetHeight;
      let x = mouse.x + 12, y = mouse.y + 14;
      if (x + w > width - 4) x = Math.max(4, mouse.x - w - 8);
      if (y + h > rowsH + AXIS_H) y = Math.max(0, mouse.y - h - 8);
      tip.style.left = x + "px";
      tip.style.top = y + "px";
    }
    function pan(to) {
      const ls = liveStart();
      viewStart = Math.min(ls, Math.max(0, to));
      follow = viewStart >= ls - 0.5;
      refresh();
    }
    root.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      const p = local(e);
      mouse = { x: p.x, y: p.y, drag: { x: e.clientX, view: viewStart, moved: false } };
      try { root.setPointerCapture(e.pointerId); } catch { /* ignore */ }
    });
    root.addEventListener("pointermove", (e) => {
      const p = local(e);
      const drag = mouse && mouse.drag;
      mouse = { x: p.x, y: p.y, drag };
      if (drag) {
        const dx = e.clientX - drag.x;
        if (Math.abs(dx) > 3) drag.moved = true;
        if (drag.moved) {
          root.classList.add("tl-panning");
          if (hover) setHover(null);
          pan(drag.view - dx * span / plotW());
        }
        return;
      }
      const h = hitAt(p.x, p.y);
      if (h !== hover) setHover(h); else if (h) showTip();
    });
    const endDrag = (e, click) => {
      const drag = mouse && mouse.drag;
      if (!drag) return;
      mouse.drag = null;
      root.classList.remove("tl-panning");
      if (click && !drag.moved) {
        const p = local(e);
        const h = hitAt(p.x, p.y);
        if (h) select(h);
      }
    };
    root.addEventListener("pointerup", (e) => endDrag(e, true));
    root.addEventListener("pointercancel", (e) => endDrag(e, false));
    root.addEventListener("pointerleave", () => {
      if (mouse && mouse.drag) return;
      mouse = null;
      if (hover) setHover(null);
    });
    root.addEventListener("wheel", (e) => {
      if (liveStart() <= 0) return;                 // nothing to scroll back to yet
      const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      if (!d) return;
      e.preventDefault();
      pan(viewStart + (e.deltaMode === 1 ? d * 16 : d) * span / plotW());
    }, { passive: false });
    live.addEventListener("click", () => { follow = true; refresh(); });

    // ---- selection and sequence chart
    function select(item) {
      selected = item;
      closure = new Set([item.id]);
      const start = items.indexOf(item);
      for (let i = start + 1; i < items.length; i++) {
        const it = items[i];
        if (it.k === "tr" && it.causes && it.causes.some((c) => closure.has(c))) closure.add(it.id);
      }
      chart.hidden = false;
      renderChart();
      // bring the top of the chart into the pane
      const want = chart.offsetTop - Math.max(0, container.clientHeight - Math.min(chart.offsetHeight, 170));
      if (container.scrollTop < want) container.scrollTop = want;
      refresh();
    }
    function closeChart() {
      if (chart.hidden) return;
      selected = null; closure = null; chartDirty = false;
      chart.hidden = true;
      chartBody.replaceChildren();
      refresh();
    }
    close.addEventListener("click", closeChart);
    const onKey = (e) => { if (e.key === "Escape" && !chart.hidden) { closeChart(); e.preventDefault(); } };
    document.addEventListener("keydown", onKey);

    function renderChart() {
      chartDirty = false;
      if (!selected || !closure) return;
      const TIME_W = 70, HEAD_H = 30, SEQ_ROW = 26;
      const events = items.filter((it) => closure.has(it.id));
      if (!events.length) events.push(selected);         // dropped by the cap: keep showing it

      // rows, and the machines involved
      const rows = [];
      const used = new Set();
      let more = 0;
      for (const it of events) {
        if (rows.length >= SEQ_MAX_ROWS) { more++; continue; }
        if (it.k === "in") { rows.push({ kind: "in", it }); continue; }
        used.add(it.sm);
        const sources = [];
        for (const cid of it.causes || []) {
          const c = byId.get(cid);
          if (!c) continue;
          const life = c.k === "in" ? "" : c.sm;       // "" is the Inputs lifeline
          if (c.k === "tr") used.add(c.sm);
          if (!sources.includes(life)) sources.push(life);
        }
        rows.push({ kind: "tr", it, sources });
        for (const w of it.writes || []) rows.push({ kind: "write", it, w });
      }
      const lifes = [{ name: "", label: "Inputs" }];
      for (const lane of laneList) if (used.delete(lane.name)) lifes.push({ name: lane.name, label: lane.label });
      for (const name of used) lifes.push({ name, label: name });
      const avail = Math.max(0, chartBody.clientWidth - TIME_W - 8);
      const colW = Math.min(220, Math.max(120, avail / lifes.length));
      const col = new Map();
      lifes.forEach((l, i) => col.set(l.name, TIME_W + colW * (i + 0.5)));
      const w = TIME_W + colW * lifes.length + 8;
      const h = HEAD_H + rows.length * SEQ_ROW + (more ? SEQ_ROW : 0) + 10;

      const s = svg("svg", "tl-seq", { width: w, height: h, role: "img", "aria-label": "Sequence chart" });
      for (const l of lifes) {
        const x = col.get(l.name);
        s.append(svg("line", "tl-life", { x1: x, x2: x, y1: HEAD_H - 4, y2: h - 4 }));
        s.append(svg("rect", "tl-life-box", { x: x - colW / 2 + 6, y: 3, width: colW - 12, height: 22, rx: 5 }));
        const t = svg("text", "tl-life-text", { x, y: 18 });
        t.textContent = ellipsis(l.label, F_SEQ, colW - 24);
        const g = withTitle(svg("g"), l.label);
        g.append(t);
        s.append(g);
      }
      const arrow = (g, x1, x2, y, cls) => {
        const dir = x2 > x1 ? 1 : -1;
        g.append(svg("line", "tl-arrow" + (cls ? " " + cls : ""), { x1, x2: x2 - dir * 7, y1: y, y2: y }));
        g.append(svg("path", "tl-arrow-head" + (cls ? " " + cls : ""),
                     { d: `M${x2 - dir},${y}l${-dir * 8},-4v8z` }));
      };
      const label = (g, text, x, y, cls, anchor) => {
        const t = svg("text", "tl-seq-text " + cls, { x, y });
        if (anchor) t.setAttribute("text-anchor", anchor);
        t.textContent = text;
        g.append(t);
      };
      const x0 = col.get("");
      rows.forEach((row, i) => {
        const y = HEAD_H + i * SEQ_ROW + SEQ_ROW / 2 + 4;
        const it = row.it;
        const g = svg("g", "tl-seq-row tl-seq-" + row.kind + (it === selected && row.kind !== "write" ? " sel" : ""),
                      { "data-id": it.id });
        if (it === selected && row.kind !== "write") {
          g.append(svg("rect", "tl-seq-band", { x: 0, y: y - SEQ_ROW / 2, width: w, height: SEQ_ROW }));
        }
        if (row.kind !== "write") label(g, seconds(it.t) + " s", TIME_W - 10, y + 4, "tl-seq-time", "end");
        if (row.kind === "in") {
          withTitle(g, inTitle(it));
          g.append(svg("circle", "tl-seq-dot", { cx: x0, cy: y, r: 4 }));
          label(g, inTitle(it), x0 + 10, y + 4, "tl-seq-in");
        } else if (row.kind === "write") {
          const text = `${row.w[0]} = ${value(row.w[1])}`;
          withTitle(g, text);
          const xs = col.get(it.sm);
          arrow(g, xs, x0, y, "tl-write");
          label(g, text, (xs + x0) / 2, y - 5, "tl-seq-write", "middle");
        } else {
          withTitle(g, trTitle(it));
          const xt = col.get(it.sm);
          let nearest = null;
          for (const src of row.sources) {
            const xs = col.get(src);
            if (xs === xt) continue;
            arrow(g, xs, xt, y);
            g.append(svg("circle", "tl-arrow-start", { cx: xs, cy: y, r: 2.5 }));
            if (nearest === null || Math.abs(xs - xt) < Math.abs(nearest - xt)) nearest = xs;
          }
          if (row.sources.includes(it.sm)) {          // caused by its own machine: a loop
            g.append(svg("path", "tl-arrow tl-loop", { d: `M${xt},${y - 7}h22v11h-15` }));
            g.append(svg("path", "tl-arrow-head", { d: `M${xt + 1},${y + 4}l8,-4v8z` }));
            if (nearest === null) label(g, it.tid, xt + 28, y + 2, "tl-seq-tid");
          }
          if (nearest !== null) label(g, it.tid, (nearest + xt) / 2, y - 5, "tl-seq-tid", "middle");
          else if (!row.sources.includes(it.sm)) {    // no cause in the data (e.g. a timer)
            g.append(svg("rect", "tl-seq-mark", { x: xt - 4, y: y - 4, width: 8, height: 8, rx: 1 }));
            label(g, it.tid, xt + 10, y + 4, "tl-seq-tid");
          }
        }
        s.append(g);
      });
      if (more) {
        const t = svg("text", "tl-seq-text tl-seq-time", { x: TIME_W, y: HEAD_H + rows.length * SEQ_ROW + 18 });
        t.textContent = `… ${more} more`;
        s.append(t);
      }
      chartTitle.textContent = "Sequence from " +
        (selected.k === "tr" ? selected.tid : selected.name) + " at " + seconds(selected.t) + " s";
      chartBody.replaceChildren(s);
    }

    // ---- lifetime
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(() => {
      if (container.clientWidth !== width) { if (selected) chartDirty = true; refresh(); }
    }) : null;
    if (observer) observer.observe(container);

    const api = {
      reset, add, state, refresh,
      show(on) { setShown(!!on, true); refresh(); },
      destroy() {
        alive = false;
        if (frame) cancelAnimationFrame(frame);
        if (observer) observer.disconnect();
        document.removeEventListener("keydown", onKey);
        if (pane.instance === api) pane.instance = null;
        container.replaceChildren();
      },
      get gen() { return gen; },
      get count() { return items.length; },
      get following() { return follow; },
    };
    if (pane.instance) pane.instance.destroy();
    pane.instance = api;
    refresh();
    return api;
  }
  build.count = 0;

  initPane();
  window.StateSimTimeline = { build, show: (on) => setShown(!!on, true) };
})();
