// FMA recording report (recorder.html, opened by recording.js on Stop).
// Shows the report in the compact layout as an editable page. Every block
// (a recorded FMA, or a blank FMA the user adds and types into) can be
// dragged anywhere; numbers follow the blocks' top-to-bottom order; Align
// vertical / Align staircase put them straight again. Recorded FMA snapshots
// are not editable. Save PNG draws exactly what is shown, without controls.
"use strict";

(function () {
  const TITLE_KEY = "statesim.recordTitle";
  const DEFAULT_TITLE = "FMA recording";
  const MANUAL_CAPTION = "Expected FMA";
  const GAP = 18;                       // vertical space between aligned blocks
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
  };

  // The report's own CSS (rc- prefix so it cannot clash with the panel's);
  // it is also embedded in the PNG.
  const SHEET_CSS = `
    .rc-sheet { display: inline-block; padding: 28px 44px 36px 32px; background: #fff; color: #1c2430;
                font-family: Inter, "Segoe UI", system-ui, sans-serif; }
    .rc-title { margin: 0 0 2px; font-size: 22px; font-weight: 700; color: #005c99; letter-spacing: .02em; }
    .rc-desc { font-size: 14px; color: #1c2430; margin: 2px 0 4px; white-space: pre-wrap; }
    .rc-desc:empty::before { content: attr(data-placeholder); color: #9aa3ae; }
    .rc-meta { font-size: 13px; color: #4a5565; margin-bottom: 22px; max-width: 760px; }
    .rc-rows { position: relative; }
    .rc-rec { position: absolute; }
    .rc-rec.rc-after::before { content: ""; position: absolute; left: -14px; top: -14px; width: 12px; height: 40px;
               border-left: 2px solid #c3cad4; border-bottom: 2px solid #c3cad4; border-bottom-left-radius: 8px; }
    .rc-cap { display: flex; align-items: baseline; gap: 10px; margin: 0 0 6px 2px; white-space: nowrap; }
    .rc-num { font-size: 11px; font-weight: 700; color: #fff; background: #005c99; border-radius: 10px; padding: 2px 7px; }
    .rc-label { font-size: 15px; font-weight: 700; white-space: pre-wrap; }
    .rc-time { font-family: "JetBrains Mono", Consolas, monospace; font-size: 12px; color: #4a5565; }
    .rc-notimes .rc-time { display: none; }
    .rc-others { font-size: 12px; color: #4a5565; margin: -2px 0 6px 2px; }
    .rc-note { font-size: 13px; color: #1c2430; margin: -2px 0 8px 2px; font-style: italic; white-space: pre-wrap; }
    .rc-note:empty::before { content: "Note"; color: #9aa3ae; }
    .rc-fma { display: inline-block; zoom: 0.5; }   /* the FMA at half its natural size */
    .rc-fma [data-slot] .fma-txt { white-space: pre; }
  `;
  // Preview only: edit controls, hidden blocks, empty positions (never in the PNG).
  const EDIT_CSS = `
    .rc-tools { position: absolute; left: 0; top: -24px; display: flex; gap: 3px; opacity: 0;
                transition: opacity .1s; white-space: nowrap; z-index: 3; }
    .rc-rec:hover .rc-tools, .rc-rec:focus-within .rc-tools { opacity: 1; }
    .rc-tools button { font: 600 11px Inter, "Segoe UI", system-ui, sans-serif; border: 1px solid #c3cad4; border-radius: 5px;
                       background: #fff; color: #1c2430; padding: 2px 6px; cursor: pointer; }
    .rc-rec { cursor: move; }
    .rc-rec.rc-moving { z-index: 4; opacity: .85; }
    .rc-sheet [contenteditable] { cursor: text; }
    .rc-sheet [contenteditable]:hover { background: #f0f6fb; border-radius: 3px; }
    .rc-rec.rc-hidden { opacity: .35; }
    .rc-rec.rc-hidden .rc-label::after { content: "  (hidden)"; font-weight: 400; color: #c62a3a; }
    .rc-sheet { margin-left: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.12); border-radius: 4px; }
    .rc-fma.rc-manual [data-slot] { outline: 1px dashed #4b5563; outline-offset: -1px; min-height: 1.1em; }
    .rc-fma.rc-manual [data-slot]:focus-within { outline: 2px solid #5ab4ff; }
    .rc-fma.rc-manual .fma-txt { display: inline-block; min-width: 1.6em; min-height: 1em; outline: none; }
    .rc-fma.rc-manual .arrow { cursor: pointer; }
    .rc-fma.rc-manual .fma-txt:hover { background: #1f2937; }
    .rc-swatches { position: absolute; z-index: 10; display: flex; gap: 4px; padding: 5px; background: #fff;
                   border: 1px solid #c3cad4; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,.2);
                   font: 600 11px Inter, "Segoe UI", system-ui, sans-serif; }
    .rc-swatches[hidden] { display: none; }
    .rc-swatches button { width: 22px; height: 22px; border: 2px solid #c3cad4; border-radius: 4px; cursor: pointer; }
    .rc-swatches button.on { border-color: #005c99; }
    .rc-swatches button.rc-default { width: auto; background: #fff; color: #1c2430; padding: 0 6px; }
  `;
  const SWATCH = { green: "#3cc843", white: "#ffffff", yellow: "#f2e34c", amber: "#f5a623", red: "#ff4a4a" };

  let data = null;          // the recording, as sent by the main page
  let panel = null;         // {css, body, slots: [{name, color, kind}], colors: [...]}
  let state = null;         // the editable report
  const undo = [];

  function cleanPanel(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    for (const s of doc.querySelectorAll("script, link, iframe, object, embed")) s.remove();
    for (const e of doc.querySelectorAll("*")) {
      for (const a of [...e.attributes]) {
        if (/^on/i.test(a.name) || /^\s*javascript:/i.test(a.value)) e.removeAttribute(a.name);
      }
    }
    const css = [...doc.querySelectorAll("style")].map((s) => s.textContent).join("\n");
    for (const s of doc.querySelectorAll("style")) s.remove();
    const slots = [...doc.querySelectorAll("[data-slot]")].map((e) => ({
      name: e.getAttribute("data-slot"), color: e.getAttribute("data-slot-color") || "white",
      kind: e.getAttribute("data-slot-kind") || "text",
    }));
    const root = doc.querySelector("[data-slot-colors]");
    const colors = root ? root.getAttribute("data-slot-colors").split(/\s+/).filter(Boolean) : Object.keys(SWATCH);
    return { css, body: doc.body.innerHTML, slots, colors };
  }

  // ---- state: blocks (recorded rows and manual FMAs) with positions
  function initialState() {
    return {
      title: store.get(TITLE_KEY) || DEFAULT_TITLE,
      desc: "",
      showTimes: true,
      step: 28,
      next: 1,
      align: "staircase",
      blocks: data.rows.map((r, i) => ({ key: "r" + i, kind: "rec", ri: i, label: r.label, note: null,
                                          hidden: false, x: null, y: null })),
    };
  }
  const snapshot = () => JSON.stringify(state);
  function push() {
    const s = snapshot();
    if (undo[undo.length - 1] !== s) undo.push(s);
    if (undo.length > 100) undo.shift();
    $("undo").disabled = false;
  }
  const byY = () => [...state.blocks].sort((a, b) => (a.y ?? 0) - (b.y ?? 0) || (a.x ?? 0) - (b.x ?? 0));

  const seconds = (ms) => (ms / 1000).toFixed(1) + " s";
  function meta() {
    const when = new Date(data.when);
    const pad = (n) => String(n).padStart(2, "0");
    const date = `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())} ${pad(when.getHours())}:${pad(when.getMinutes())}`;
    const changes = data.rows.filter((r) => r.kind === "change").length;
    const manual = state.blocks.filter((b) => b.kind === "man" && !b.hidden).length;
    const parts = [data.source, date, `recorded ${seconds(data.start)} to ${seconds(data.end)}`,
                   changes ? `${changes} FMA change${changes === 1 ? "" : "s"}` : "no FMA change during the recording",
                   manual ? `${manual} expected FMA${manual === 1 ? "" : "s"} added` : "",
                   `${data.layout} layout`];
    return parts.filter(Boolean).join(" · ");
  }

  function editable(node, get, set) {
    node.contentEditable = "plaintext-only";
    if (node.contentEditable !== "plaintext-only") node.contentEditable = "true";
    node.spellcheck = false;
    node.textContent = get();
    node.addEventListener("focus", push);
    node.addEventListener("input", () => set(node.textContent));
    node.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && node.dataset.single) { e.preventDefault(); node.blur(); }
    });
  }

  // A recorded FMA: the panel's markup with the recorded lights.
  function fmaNode(lit) {
    const box = el("div", "rc-fma");
    box.innerHTML = panel.body;
    const on = new Set(lit);
    for (const e of box.querySelectorAll("[data-lit-by]")) e.classList.toggle("lit", on.has(e.getAttribute("data-lit-by")));
    return box;
  }

  // A manual FMA: the panel's markup with every mode text off and each
  // [data-slot] position holding the user's text, in its colour.
  function manualFma(b) {
    const box = el("div", "rc-fma rc-manual");
    box.innerHTML = panel.body;
    for (const e of box.querySelectorAll("[data-lit-by]")) e.classList.remove("lit");
    const root = box.querySelector("[data-slot-colors]") || box.firstElementChild;
    if (root) root.classList.add("fma-edit");
    for (const pos of box.querySelectorAll("[data-slot]")) {
      const name = pos.getAttribute("data-slot");
      const def = pos.getAttribute("data-slot-color") || "white";
      if (pos.getAttribute("data-slot-kind") === "arrow") {           // the AP/AT arrow: none, left, right
        const mark = pos.querySelector(".m");
        const v = b.arrow || "";
        if (mark) mark.classList.toggle("lit", v !== "");
        pos.classList.toggle("right", v === "right");
        pos.title = "Click: no arrow, ←, →";
        pos.addEventListener("click", (e) => {
          e.stopPropagation();
          push();
          b.arrow = { "": "left", left: "right", right: "" }[b.arrow || ""];
          render();
        });
        continue;
      }
      for (const m of [...pos.children]) m.remove();                   // the recorded mode texts
      const slot = b.slots[name] || (b.slots[name] = { text: "", color: "" });
      const txt = el("span", "fma-txt fma-c-" + (slot.color || def));
      txt.dataset.slot = name;
      editable(txt, () => slot.text, (v) => { slot.text = v; });
      txt.dataset.single = "1";
      txt.addEventListener("focus", () => showSwatches(txt, slot, def));
      txt.addEventListener("blur", () => setTimeout(() => {
        if (!$("swatches").contains(document.activeElement)) $("swatches").hidden = true;
      }, 150));
      pos.append(txt);
    }
    return box;
  }

  // Colour menu of the focused position: the panel's palette plus "default".
  function showSwatches(txt, slot, def) {
    const menu = $("swatches");
    menu.replaceChildren();
    const pick = (c) => {
      push();
      slot.color = c;
      txt.className = "fma-txt fma-c-" + (c || def);
      for (const b of menu.querySelectorAll("button")) b.classList.toggle("on", b.dataset.c === (c || ""));
      txt.focus();
    };
    for (const c of panel.colors) {
      const b = el("button");
      b.type = "button"; b.title = c; b.dataset.c = c;
      b.style.background = SWATCH[c] || c;
      b.classList.toggle("on", (slot.color || "") === c);
      b.addEventListener("mousedown", (e) => { e.preventDefault(); pick(c); });
      menu.append(b);
    }
    const d = el("button", "rc-default", "default");
    d.type = "button"; d.dataset.c = ""; d.title = `default colour (${def})`;
    d.classList.toggle("on", !slot.color);
    d.addEventListener("mousedown", (e) => { e.preventDefault(); pick(""); });
    menu.append(d);
    const r = txt.getBoundingClientRect();
    menu.style.left = (r.left + window.scrollX) + "px";
    menu.style.top = (r.bottom + window.scrollY + 6) + "px";
    menu.hidden = false;
  }

  function newManual() {
    const slots = {};
    for (const s of panel.slots) if (s.kind !== "arrow") slots[s.name] = { text: "", color: "" };
    return { key: "m" + state.next++, kind: "man", label: MANUAL_CAPTION, time: "", note: null, hidden: false,
             x: 0, y: 0, slots, arrow: "" };
  }

  // ---- layout
  function measure() {
    const h = {};
    for (const n of document.querySelectorAll("#sheet .rc-rec")) h[n.dataset.key] = [n.offsetWidth, n.offsetHeight];
    return h;
  }
  // Realign: keep the top-to-bottom order; vertical = left edges aligned,
  // staircase = one indent step more per visible block.
  function align(mode) {
    const size = measure();
    let y = 24, k = 0;
    for (const b of byY()) {
      b.x = mode === "vertical" ? 0 : k * state.step;
      b.y = y;
      y += (size[b.key] ? size[b.key][1] : 120) + GAP;
      if (!b.hidden) k += 1;
    }
    state.align = mode;
  }

  // ---- render
  let dragging = null;
  function render() {
    const stage = $("stage");
    const sheet = el("div", "rc-sheet" + (state.showTimes ? "" : " rc-notimes"));
    sheet.id = "sheet";
    const h1 = el("h1", "rc-title");
    h1.dataset.single = "1";
    editable(h1, () => state.title, (v) => { state.title = v; store.set(TITLE_KEY, v.trim() || DEFAULT_TITLE); });
    const desc = el("div", "rc-desc");
    desc.dataset.placeholder = "Description (optional)";
    editable(desc, () => state.desc, (v) => { state.desc = v; });
    sheet.append(h1, desc, el("div", "rc-meta", meta()));

    const list = el("div", "rc-rows");
    let num = 0, first = true;
    for (const b of byY()) {
      const row = b.kind === "rec" ? data.rows[b.ri] : null;
      const rec = el("div", "rc-rec" + (b.hidden ? " rc-hidden" : "") + (!first && !b.hidden ? " rc-after" : ""));
      rec.dataset.key = b.key;
      rec.style.left = (b.x ?? 0) + "px";
      rec.style.top = (b.y ?? 0) + "px";

      const tools = el("div", "rc-tools rc-ui");
      const btn = (text, title, fn) => {
        const x = el("button", null, text);
        x.type = "button"; x.title = title;
        x.addEventListener("click", (e) => { e.stopPropagation(); fn(); });
        return x;
      };
      tools.append(
        btn(b.hidden ? "Show" : "Hide", b.hidden ? "Put this block back in the image" : "Leave this block out of the image",
            () => { push(); b.hidden = !b.hidden; render(); }),
        btn(b.note === null ? "+ Note" : "− Note", b.note === null ? "Add a note under the caption" : "Remove the note",
            () => { push(); b.note = b.note === null ? "" : null; render();
                    if (b.note === "") $("sheet").querySelector(`[data-key="${b.key}"] .rc-note`).focus(); }),
        btn("+ Blank FMA below", "Insert a blank FMA under this block", () => insertBelow(b)));
      if (b.kind === "man") tools.append(btn("Delete", "Remove this blank FMA", () => {
        push(); state.blocks = state.blocks.filter((x) => x !== b); render();
      }));

      const cap = el("div", "rc-cap");
      const startBadge = row && row.kind === "start" && first;
      const badge = el("span", "rc-num", startBadge ? "START" : (b.hidden ? "–" : String(++num)));
      const label = el("span", "rc-label");
      label.dataset.single = "1";
      editable(label, () => b.label, (v) => { b.label = v; });
      const time = el("span", "rc-time");
      if (row) time.textContent = seconds(row.t);
      else {
        time.dataset.single = "1";
        editable(time, () => b.time, (v) => { b.time = v; });
        if (!b.time) time.classList.add("rc-ui-empty");
      }
      cap.append(badge, label, time);
      rec.append(tools, cap);
      if (row && row.others && row.others.length) rec.append(el("div", "rc-others", "also: " + row.others.join(", ")));
      if (b.note !== null) {
        const note = el("div", "rc-note");
        editable(note, () => b.note, (v) => { b.note = v; });
        rec.append(note);
      }
      if (row) {
        if (!(row.kind === "start" && row.lit.length === 0)) rec.append(fmaNode(row.lit));   // no blank start FMA
      } else {
        rec.append(manualFma(b));
      }
      rec.addEventListener("pointerdown", (e) => startDrag(e, b, rec));
      list.append(rec);
      if (!b.hidden) first = false;
    }
    sheet.append(list);
    stage.replaceChildren(sheet);
    fitList();
    $("times").checked = state.showTimes;
    $("step").value = state.step;
  }

  // The block list is sized to hold the furthest block.
  function fitList() {
    const list = document.querySelector("#sheet .rc-rows");
    let w = 0, h = 0;
    for (const n of list.querySelectorAll(".rc-rec")) {
      w = Math.max(w, n.offsetLeft + n.offsetWidth);
      h = Math.max(h, n.offsetTop + n.offsetHeight);
    }
    list.style.width = w + "px";
    list.style.height = h + "px";
  }

  function insertBelow(b) {
    push();
    const size = measure();
    const m = newManual();
    const h = size[b.key] ? size[b.key][1] : 120;
    const sample = Object.entries(size).find(([k]) => /^r/.test(k) && size[k][1] > 80);
    const mh = sample ? sample[1][1] : 140;
    m.x = b.x ?? 0;
    m.y = (b.y ?? 0) + h + GAP;
    for (const o of state.blocks) if ((o.y ?? 0) > (b.y ?? 0)) o.y += mh + GAP;
    state.blocks.push(m);
    render();
    const first = $("sheet").querySelector(`[data-key="${m.key}"] .fma-txt`);
    if (first) first.focus();
  }

  function addBlank() {
    push();
    const size = measure();
    let bottom = 24, lastX = 0;
    for (const b of byY()) {
      const s = size[b.key];
      if (s && (b.y ?? 0) + s[1] + GAP > bottom) { bottom = (b.y ?? 0) + s[1] + GAP; lastX = b.x ?? 0; }
    }
    const m = newManual();
    m.x = state.align === "vertical" ? 0 : lastX + state.step;
    m.y = bottom;
    state.blocks.push(m);
    render();
    const first = $("sheet").querySelector(`[data-key="${m.key}"] .fma-txt`);
    if (first) first.focus();
  }

  // Drag a block anywhere (not from an editable text or a button).
  function startDrag(e, b, node) {
    if (e.button !== 0 || e.target.closest("[contenteditable], button, .arrow")) return;
    e.preventDefault();
    const x0 = e.clientX, y0 = e.clientY, bx = b.x ?? 0, by = b.y ?? 0;
    let moved = false;
    node.setPointerCapture(e.pointerId);
    node.classList.add("rc-moving");
    const move = (m) => {
      const dx = m.clientX - x0, dy = m.clientY - y0;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 3) return;
      if (!moved) { push(); moved = true; }
      b.x = Math.max(0, bx + dx);
      b.y = Math.max(0, by + dy);
      node.style.left = b.x + "px";
      node.style.top = b.y + "px";
    };
    const up = () => {
      node.removeEventListener("pointermove", move);
      node.removeEventListener("pointerup", up);
      node.removeEventListener("pointercancel", up);
      node.classList.remove("rc-moving");
      if (moved) render();                      // numbers follow the new order
    };
    node.addEventListener("pointermove", move);
    node.addEventListener("pointerup", up);
    node.addEventListener("pointercancel", up);
    dragging = b;
  }

  // ---- Save PNG: the sheet as shown, without edit controls or hidden blocks
  function fileName() {
    const d = new Date(data.when), pad = (n) => String(n).padStart(2, "0");
    const title = (state.title.trim() || DEFAULT_TITLE).replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim();
    return `${title} - ${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}${pad(d.getMinutes())}.png`;
  }
  const xmlText = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function exportNode() {
    const clone = $("sheet").cloneNode(true);
    for (const n of clone.querySelectorAll(".rc-ui, .rc-rec.rc-hidden")) n.remove();
    for (const n of clone.querySelectorAll("[contenteditable]")) n.removeAttribute("contenteditable");
    for (const n of clone.querySelectorAll(".rc-note")) if (!n.textContent.trim()) n.remove();
    for (const n of clone.querySelectorAll(".rc-manual")) n.classList.remove("rc-manual");   // no dashed outlines
    const desc = clone.querySelector(".rc-desc");
    if (desc && !desc.textContent.trim()) desc.remove();
    clone.style.marginLeft = "0"; clone.style.boxShadow = "none"; clone.style.borderRadius = "0";
    return clone;
  }

  async function savePng() {
    const node = exportNode();
    const probe = el("div");
    probe.style.cssText = "position:absolute;left:-100000px;top:0";
    probe.append(node);
    document.body.append(probe);
    // the list holds only the visible blocks now: size it to them
    const list = node.querySelector(".rc-rows");
    let lw = 0, lh = 0;
    for (const n of list.querySelectorAll(".rc-rec")) {
      lw = Math.max(lw, n.offsetLeft + n.offsetWidth);
      lh = Math.max(lh, n.offsetTop + n.offsetHeight);
    }
    list.style.width = lw + "px";
    list.style.height = lh + "px";
    const w = Math.ceil(node.scrollWidth), h = Math.ceil(node.scrollHeight);
    const xhtml = new XMLSerializer().serializeToString(node);
    probe.remove();
    const css = xmlText(panel.css + "\n" + SHEET_CSS);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><foreignObject x="0" y="0" width="${w}" height="${h}">` +
                `<div xmlns="http://www.w3.org/1999/xhtml"><style>${css}</style>${xhtml}</div></foreignObject></svg>`;
    const img = new Image();
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    await img.decode();
    const scale = 2;
    const canvas = document.createElement("canvas");
    canvas.width = w * scale; canvas.height = h * scale;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0);
    const blob = await new Promise((r) => canvas.toBlob(r, "image/png"));
    const a = el("a");
    a.href = URL.createObjectURL(blob);
    a.download = fileName();
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    $("status").textContent = `Saved ${a.download} (${canvas.width} × ${canvas.height} px)`;
    window.lastPng = { width: canvas.width, height: canvas.height, size: blob.size, name: a.download };  // for tests
    return window.lastPng;
  }

  function start(rec) {
    data = rec;
    panel = cleanPanel(rec.panel.html);
    const style = el("style");
    style.textContent = panel.css + "\n" + SHEET_CSS + "\n" + EDIT_CSS;
    document.head.append(style);
    const menu = el("div", "rc-swatches rc-ui");
    menu.id = "swatches";
    menu.hidden = true;
    document.body.append(menu);
    state = initialState();
    document.title = `${state.title} – StateSim`;
    $("bar").hidden = false;
    $("blank").hidden = panel.slots.length === 0;
    $("save").addEventListener("click", () => savePng().catch((e) => { $("status").textContent = "Could not save: " + e; }));
    $("undo").addEventListener("click", () => {
      const s = undo.pop();
      if (s) { state = JSON.parse(s); render(); }
      $("undo").disabled = undo.length === 0;
    });
    $("reset").addEventListener("click", () => { push(); state = initialState(); render(); align("staircase"); render(); });
    $("times").addEventListener("change", () => { push(); state.showTimes = $("times").checked; render(); });
    $("step").addEventListener("change", () => {
      push(); state.step = Math.max(0, Number($("step").value) || 0);
      if (state.align === "staircase") align("staircase");
      render();
    });
    $("blank").addEventListener("click", addBlank);
    $("align-v").addEventListener("click", () => { push(); align("vertical"); render(); });
    $("align-s").addEventListener("click", () => { push(); align("staircase"); render(); });
    render();
    align("staircase");                           // first layout: compact, from the measured blocks
    render();
  }

  window.addEventListener("message", (e) => {
    if (e.origin !== location.origin || !e.data || e.data.type !== "statesim-recording" || data) return;
    start(e.data);
  });
  window.StateSimReport = { start, savePng, align, get state() { return state; } };   // for tests and the console
  if (window.opener) window.opener.postMessage("statesim-recorder-ready", location.origin);
})();
