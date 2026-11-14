// FMA recording preview (recorder.html, opened by recording.js on Stop).
// Shows the report in the compact layout as an editable page: title,
// description, captions, notes, times, row order, hidden rows and indent.
// The FMA snapshots are the recorded ones and are not editable. Save PNG
// draws exactly what is shown, without the edit controls.
"use strict";

(function () {
  const TITLE_KEY = "statesim.recordTitle";
  const DEFAULT_TITLE = "FMA recording";
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
    .rc-meta { font-size: 13px; color: #4a5565; margin-bottom: 22px; }
    .rc-rec { position: relative; margin-bottom: 18px; }
    .rc-rec.rc-after::before { content: ""; position: absolute; left: -14px; top: -14px; width: 12px; height: 40px;
               border-left: 2px solid #c3cad4; border-bottom: 2px solid #c3cad4; border-bottom-left-radius: 8px; }
    .rc-cap { display: flex; align-items: baseline; gap: 10px; margin: 0 0 6px 2px; }
    .rc-num { font-size: 11px; font-weight: 700; color: #fff; background: #005c99; border-radius: 10px; padding: 2px 7px; }
    .rc-label { font-size: 15px; font-weight: 700; white-space: pre-wrap; }
    .rc-time { font-family: "JetBrains Mono", Consolas, monospace; font-size: 12px; color: #4a5565; }
    .rc-notimes .rc-time { display: none; }
    .rc-others { font-size: 12px; color: #4a5565; margin: -2px 0 6px 2px; }
    .rc-note { font-size: 13px; color: #1c2430; margin: -2px 0 8px 2px; font-style: italic; white-space: pre-wrap; }
    .rc-note:empty::before { content: "Note"; color: #9aa3ae; }
    .rc-fma { display: inline-block; zoom: 0.5; }   /* the FMA at half its natural size */
  `;
  // Preview only: edit controls and hidden rows (never in the PNG).
  const EDIT_CSS = `
    .rc-tools { position: absolute; right: 100%; top: -2px; margin-right: 20px; display: flex; gap: 3px; opacity: 0;
                transition: opacity .1s; white-space: nowrap; }
    .rc-rec:hover .rc-tools, .rc-rec:focus-within .rc-tools { opacity: 1; }
    .rc-tools button { font: 600 11px Inter, "Segoe UI", system-ui, sans-serif; border: 1px solid #c3cad4; border-radius: 5px;
                       background: #fff; color: #1c2430; padding: 2px 6px; cursor: pointer; }
    .rc-tools .rc-grip { cursor: grab; }
    .rc-sheet [contenteditable]:hover { background: #f0f6fb; border-radius: 3px; }
    .rc-rec.rc-hidden { opacity: .35; }
    .rc-rec.rc-hidden .rc-label::after { content: "  (hidden)"; font-weight: 400; color: #c62a3a; }
    .rc-rec.rc-dragging { opacity: .5; }
    .rc-rec.rc-drop-before { box-shadow: 0 -3px 0 #005c99; }
    .rc-rec.rc-drop-after { box-shadow: 0 3px 0 #005c99; }
    .rc-sheet { margin-left: 150px; box-shadow: 0 2px 10px rgba(0,0,0,.12); border-radius: 4px; }
  `;

  let data = null;          // the recording, as sent by the main page
  let panel = null;         // {css, body} of the FMA panel
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
    return { css, body: doc.body.innerHTML };
  }

  function initialState() {
    return {
      title: store.get(TITLE_KEY) || DEFAULT_TITLE,
      desc: "",
      showTimes: true,
      step: 28,
      order: data.rows.map((_, i) => i),
      rows: data.rows.map((r) => ({ label: r.label, note: null, hidden: false, nudge: 0 })),
    };
  }
  const snapshot = () => JSON.stringify(state);
  function push() {
    const s = snapshot();
    if (undo[undo.length - 1] !== s) undo.push(s);
    if (undo.length > 100) undo.shift();
    $("undo").disabled = false;
  }

  const seconds = (ms) => (ms / 1000).toFixed(1) + " s";
  function meta() {
    const when = new Date(data.when);
    const pad = (n) => String(n).padStart(2, "0");
    const date = `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())} ${pad(when.getHours())}:${pad(when.getMinutes())}`;
    const changes = data.rows.filter((r) => r.kind === "change").length;
    const parts = [data.source, date, `recorded ${seconds(data.start)} to ${seconds(data.end)}`,
                   changes ? `${changes} FMA change${changes === 1 ? "" : "s"}` : "no FMA change during the recording",
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
    node.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && node.dataset.single) { e.preventDefault(); node.blur(); } });
  }

  function fmaNode(lit) {
    const box = el("div", "rc-fma");
    box.innerHTML = panel.body;                     // the panel file's own markup (cleaned)
    const on = new Set(lit);
    for (const e of box.querySelectorAll("[data-lit-by]")) e.classList.toggle("lit", on.has(e.getAttribute("data-lit-by")));
    return box;
  }

  let dragFrom = null;
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
    let pos = 0, num = 0;
    state.order.forEach((i, at) => {
      const row = data.rows[i], s = state.rows[i];
      const rec = el("div", "rc-rec" + (s.hidden ? " rc-hidden" : "") + (pos > 0 ? " rc-after" : ""));
      rec.dataset.i = String(i);
      rec.style.marginLeft = Math.max(0, (pos + s.nudge) * state.step) + "px";

      const tools = el("div", "rc-tools rc-ui");
      const grip = el("button", "rc-grip", "⠇");
      grip.type = "button"; grip.title = "Drag to move this row"; grip.draggable = true;
      grip.addEventListener("dragstart", (e) => { dragFrom = at; rec.classList.add("rc-dragging"); e.dataTransfer.setData("text/plain", String(at)); });
      grip.addEventListener("dragend", () => { dragFrom = null; render(); });
      const btn = (text, title, fn) => { const b = el("button", null, text); b.type = "button"; b.title = title; b.addEventListener("click", fn); return b; };
      tools.append(grip,
        btn("◀", "Indent less", () => { push(); s.nudge -= 1; render(); }),
        btn("▶", "Indent more", () => { push(); s.nudge += 1; render(); }),
        btn(s.hidden ? "Show" : "Hide", s.hidden ? "Put this row back in the image" : "Leave this row out of the image",
            () => { push(); s.hidden = !s.hidden; render(); }),
        btn(s.note === null ? "+ Note" : "− Note", s.note === null ? "Add a note under the caption" : "Remove the note",
            () => { push(); s.note = s.note === null ? "" : null; render(); if (s.note === "") $("sheet").querySelector(`[data-i="${i}"] .rc-note`).focus(); }));

      rec.addEventListener("dragover", (e) => {
        if (dragFrom === null) return;
        e.preventDefault();
        const r = rec.getBoundingClientRect(), before = e.clientY < r.top + r.height / 2;
        rec.classList.toggle("rc-drop-before", before);
        rec.classList.toggle("rc-drop-after", !before);
      });
      rec.addEventListener("dragleave", () => rec.classList.remove("rc-drop-before", "rc-drop-after"));
      rec.addEventListener("drop", (e) => {
        if (dragFrom === null) return;
        e.preventDefault();
        const r = rec.getBoundingClientRect(), before = e.clientY < r.top + r.height / 2;
        push();
        moveRow(dragFrom, before ? at : at + 1);
        dragFrom = null;
        render();
      });

      const cap = el("div", "rc-cap");
      const isStart = row.kind === "start";
      const badge = el("span", "rc-num", isStart && at === 0 ? "START" : String(s.hidden ? "–" : ++num));
      const label = el("span", "rc-label");
      label.dataset.single = "1";
      editable(label, () => s.label, (v) => { s.label = v; });
      cap.append(badge, label, el("span", "rc-time", seconds(row.t)));
      rec.append(tools, cap);
      if (row.others && row.others.length) rec.append(el("div", "rc-others", "also: " + row.others.join(", ")));
      if (s.note !== null) {
        const note = el("div", "rc-note");
        editable(note, () => s.note, (v) => { s.note = v; });
        rec.append(note);
      }
      const blankStart = isStart && row.lit.length === 0;      // a blank start FMA is not drawn
      if (!blankStart) rec.append(fmaNode(row.lit));
      list.append(rec);
      if (!s.hidden) pos += 1;
    });
    sheet.append(list);
    stage.replaceChildren(sheet);
    $("times").checked = state.showTimes;
    $("step").value = state.step;
  }

  function moveRow(from, to) {
    const [i] = state.order.splice(from, 1);
    state.order.splice(to > from ? to - 1 : to, 0, i);
  }

  // ---- Save PNG: the sheet as shown, without edit controls or hidden rows
  function fileName() {
    const d = new Date(data.when), pad = (n) => String(n).padStart(2, "0");
    const title = (state.title.trim() || DEFAULT_TITLE).replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim();
    return `${title} - ${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}${pad(d.getMinutes())}.png`;
  }
  const xmlText = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function exportNode() {
    const live = $("sheet");
    const clone = live.cloneNode(true);
    for (const n of clone.querySelectorAll(".rc-ui, .rc-rec.rc-hidden")) n.remove();
    for (const n of clone.querySelectorAll("[contenteditable]")) n.removeAttribute("contenteditable");
    for (const n of clone.querySelectorAll(".rc-note")) if (!n.textContent.trim()) n.remove();
    const desc = clone.querySelector(".rc-desc");
    if (desc && !desc.textContent.trim()) desc.remove();
    // the first visible row has no connector; numbers follow the visible order
    const recs = [...clone.querySelectorAll(".rc-rec")];
    recs.forEach((r, k) => r.classList.toggle("rc-after", k > 0));
    clone.style.marginLeft = "0"; clone.style.boxShadow = "none"; clone.style.borderRadius = "0";
    return clone;
  }

  async function savePng() {
    const node = exportNode();
    // measure it off-screen, with the same CSS as the image
    const probe = el("div");
    probe.style.cssText = "position:absolute;left:-100000px;top:0";
    probe.append(node);
    document.body.append(probe);
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
    state = initialState();
    document.title = `${state.title} – StateSim`;
    $("bar").hidden = false;
    $("save").addEventListener("click", () => savePng().catch((e) => { $("status").textContent = "Could not save: " + e; }));
    $("undo").addEventListener("click", () => {
      const s = undo.pop();
      if (s) { state = JSON.parse(s); render(); }
      $("undo").disabled = undo.length === 0;
    });
    $("reset").addEventListener("click", () => { push(); state = initialState(); render(); });
    $("times").addEventListener("change", () => { push(); state.showTimes = $("times").checked; render(); });
    $("step").addEventListener("change", () => { push(); state.step = Math.max(0, Number($("step").value) || 0); render(); });
    render();
  }

  window.addEventListener("message", (e) => {
    if (e.origin !== location.origin || !e.data || e.data.type !== "statesim-recording" || data) return;
    start(e.data);
  });
  window.StateSimReport = { start, savePng, get state() { return state; } };   // for tests and the console
  if (window.opener) window.opener.postMessage("statesim-recorder-ready", location.origin);
})();
