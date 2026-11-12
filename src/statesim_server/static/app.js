// StateSim front end. Builds the screen from the server's "model" message,
// then shows each "state" message. All model text goes in as textContent.
"use strict";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

let ws = null;
let controls = {};   // input name -> {kind, update(value)}
let machines = {};   // machine name -> {boxes, next, global, active, shown}
let litButtons = []; // [{el, var}]
let built = false;

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

// ------------------------------------------------------------ connection
function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => banner("");
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "model") build(msg);
    else if (msg.type === "state") show(msg);
    else if (msg.type === "error") { console.warn("StateSim:", msg.message); banner(msg.message, 3000); }
  };
  ws.onclose = () => {
    banner("Disconnected from the StateSim server. Reconnecting…");
    setTimeout(connect, 1000);
  };
}

let bannerTimer = null;
function banner(text, ms) {
  const b = $("banner");
  clearTimeout(bannerTimer);
  b.textContent = text;
  b.hidden = !text;
  if (text && ms) bannerTimer = setTimeout(() => { b.hidden = true; }, ms);
}

// ------------------------------------------------------------------ build
function build(model) {
  controls = {}; machines = {}; litButtons = [];
  const inputs = $("inputs");
  inputs.replaceChildren();
  for (const g of model.groups) {
    const card = el("div", "card" + (g.wide ? " wide" : ""));
    card.append(el("h2", null, g.name));
    for (const i of g.inputs) card.append(control(i));
    inputs.append(card);
  }
  const root = $("machines");
  root.replaceChildren();
  for (const m of model.machines) root.append(machineCard(m));
  built = true;
  requestAnimationFrame(fitStateText);
}

function control(i) {
  const id = "in-" + i.name;
  if (i.widget === "momentary" || i.widget === "lit") {
    const b = el("button", "pb " + i.widget, i.label);
    b.type = "button";
    let flash = null;
    b.addEventListener("click", () => {
      send({ type: "press", name: i.name });
      b.classList.add("pressed");                  // visible feedback, even for short pulses
      clearTimeout(flash);
      flash = setTimeout(() => b.classList.remove("pressed"), 300);
    });
    if (i.widget === "lit") {
      b.setAttribute("aria-pressed", "false");
      litButtons.push({ el: b, var: i.lit_by });
    }
    return b;
  }
  if (i.widget === "switch") {
    const lab = el("label", "switch");
    const box = el("input"); box.type = "checkbox"; box.id = id;
    box.addEventListener("change", () => send({ type: "set", name: i.name, value: box.checked }));
    lab.append(el("span", null, i.label), box, el("span", "track"));
    lab.lastChild.setAttribute("aria-hidden", "true");
    controls[i.name] = { update: (v) => { box.checked = !!v; } };
    return lab;
  }
  if (i.widget === "slider") {
    const wrap = el("div");
    const row = el("div", "row");
    const lab = el("label", null, i.label); lab.htmlFor = id;
    const val = el("span", "val");
    const r = el("input"); r.type = "range"; r.id = id;
    r.min = i.min; r.max = i.max;
    r.step = i.step ?? (i.type === "int" ? 1 : (i.max - i.min) / 100);
    let dragging = false, pending = false;
    r.addEventListener("pointerdown", () => { dragging = true; });
    r.addEventListener("pointerup", () => { dragging = false; });
    r.addEventListener("input", () => {
      val.textContent = r.value;
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => { pending = false; send({ type: "set", name: i.name, value: Number(r.value) }); });
    });
    row.append(lab, val);
    wrap.append(row, r);
    controls[i.name] = { update: (v) => { val.textContent = fmt(v); if (!dragging) r.value = v; } };
    return wrap;
  }
  const row = el("div", "row");
  const lab = el("label", null, i.label); lab.htmlFor = id;
  let field;
  if (i.widget === "dropdown") {
    field = el("select");
    for (const c of i.choices) field.append(el("option", null, c));
    field.addEventListener("change", () => send({ type: "set", name: i.name, value: field.value }));
  } else {
    field = el("input");
    field.type = i.widget === "number" ? "number" : "text";
    if (i.widget === "number") {
      if (i.min !== null) field.min = i.min;
      if (i.max !== null) field.max = i.max;
      field.step = i.step ?? (i.type === "int" ? 1 : "any");
    }
    field.addEventListener("change", () => send({
      type: "set", name: i.name, value: i.widget === "number" ? Number(field.value) : field.value,
    }));
  }
  field.id = id;
  row.append(lab, field);
  controls[i.name] = { update: (v) => { if (document.activeElement !== field) field.value = v; } };
  return row;
}

function fmt(v) {
  return typeof v === "number" && !Number.isInteger(v) ? v.toFixed(2) : String(v);
}

function machineCard(m) {
  const card = el("div", "sm");
  card.append(el("h3", null, m.label));
  const grid = el("div", "states");
  const boxes = {};
  const info = { boxes, next: m.next, global: m.global, active: null, shown: false };
  for (const s of m.states) {
    const b = el("div", "st");
    breakable(b, s);
    const enter = () => { if (info.active === s && !info.shown) highlight(info, true); };
    b.addEventListener("mouseenter", enter);
    b.addEventListener("mousemove", enter);
    b.addEventListener("focus", enter);
    b.addEventListener("mouseleave", () => highlight(info, false));
    b.addEventListener("blur", () => highlight(info, false));
    boxes[s] = b;
    grid.append(b);
  }
  card.append(grid);
  machines[m.name] = info;
  return card;
}

// Text with optional line breaks after "_" (state names like No_Vertical_State).
function breakable(node, text) {
  text.split(/(?<=_)/).forEach((part, k) => {
    if (k) node.append(document.createElement("wbr"));
    node.append(part);
  });
}

function highlight(info, on) {
  info.shown = on;
  const targets = on ? (info.next[info.active] || []) : [];
  const globals = on ? info.global : [];
  for (const [s, b] of Object.entries(info.boxes)) {
    b.classList.toggle("next", s !== info.active && (targets.includes(s) || globals.includes(s)));
    b.classList.toggle("next-global", s !== info.active && globals.includes(s) && !targets.includes(s));
  }
}

function fitStateText() {
  for (const b of document.querySelectorAll(".st")) {
    b.classList.remove("small");
    if (b.scrollHeight > 52) b.classList.add("small");   // more than 3 lines: smaller font
  }
}

// ------------------------------------------------------------------- show
function show(st) {
  if (!built) return;
  for (const [name, info] of Object.entries(machines)) {
    const now = st.states[name];
    if (now === info.active) continue;
    if (info.shown) highlight(info, false);
    if (info.active !== null) {
      const old = info.boxes[info.active];
      old.classList.remove("active");
      old.removeAttribute("tabindex");
      if (document.activeElement === old) old.blur();
    }
    info.active = now;
    const b = info.boxes[now];
    if (b) { b.classList.add("active"); b.tabIndex = 0; }
  }
  for (const [name, c] of Object.entries(controls)) {
    if (name in st.inputs) c.update(st.inputs[name]);
  }
  for (const l of litButtons) {
    const on = !!st.lit[l.var];
    l.el.classList.toggle("on", on);
    l.el.setAttribute("aria-pressed", String(on));
  }
  for (const b of document.querySelectorAll(".seg button")) {
    b.setAttribute("aria-pressed", String(b.dataset.mode === st.mode));
  }
  $("pause").textContent = st.paused ? "Resume" : "Pause";
  $("step").disabled = !st.paused;
}

// --------------------------------------------------------------- controls
for (const b of document.querySelectorAll(".seg button")) {
  b.addEventListener("click", () => send({ type: "mode", mode: b.dataset.mode }));
}
$("pause").addEventListener("click", () => send({ type: $("pause").textContent === "Resume" ? "resume" : "pause" }));
$("step").addEventListener("click", () => send({ type: "step" }));
$("reset").addEventListener("click", () => send({ type: "reset" }));

// --------------------------------------------------------------- splitter
const left = $("left"), bar = $("splitter");
const MIN = 280, DEFAULT_W = 440, KEY = "statesim.leftPaneWidth";
// The divider position is remembered in this browser (a convenience only:
// storage may be unavailable, then the default is used).
function savedW() {
  try { const v = Number(localStorage.getItem(KEY)); return v > 0 ? v : DEFAULT_W; } catch { return DEFAULT_W; }
}
function saveW() {
  try { localStorage.setItem(KEY, String(Math.round(left.getBoundingClientRect().width))); } catch { /* ignore */ }
}
const maxW = () => Math.max(MIN, window.innerWidth - 240);
function setW(w) {
  w = Math.round(Math.min(maxW(), Math.max(MIN, w)));
  left.style.width = w + "px";
  bar.setAttribute("aria-valuenow", w);
  bar.setAttribute("aria-valuemax", maxW());
}
bar.addEventListener("pointerdown", (e) => {
  bar.setPointerCapture(e.pointerId);
  bar.classList.add("dragging"); document.body.classList.add("resizing");
  const startX = e.clientX, startW = left.getBoundingClientRect().width;
  const move = (ev) => setW(startW + ev.clientX - startX);
  const up = () => {
    bar.removeEventListener("pointermove", move); bar.removeEventListener("pointerup", up);
    bar.classList.remove("dragging"); document.body.classList.remove("resizing");
    saveW();
    fitStateText();
  };
  bar.addEventListener("pointermove", move); bar.addEventListener("pointerup", up);
});
bar.addEventListener("keydown", (e) => {
  const w = left.getBoundingClientRect().width;
  if (e.key === "ArrowLeft") { setW(w - 20); saveW(); e.preventDefault(); }
  if (e.key === "ArrowRight") { setW(w + 20); saveW(); e.preventDefault(); }
});
window.addEventListener("resize", () => setW(left.getBoundingClientRect().width));
setW(savedW());

connect();
