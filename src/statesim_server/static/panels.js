// Aircraft panels: HTML files from the model, shown in the top pane.
// Each panel lives in its own shadow root, so its CSS cannot affect the page
// and the page's CSS cannot affect it. Scripts and on* attributes are removed;
// StateSim wires the elements by their data-input, data-show and data-lit-by
// attributes. Used by app.js (window.StateSimPanels).
"use strict";

(function () {
  const BASE_CSS = `
    :host { display: block; }
    .ss-panel { display: inline-block; transform-origin: top left; }
    [data-input] { touch-action: none; }
    [data-input]:focus-visible { outline: 2px solid #5ab4ff; outline-offset: 2px; }
    .ss-knob { position: relative; user-select: none; }
    .ss-knob::after { content: ""; position: absolute; left: 50%; top: 8%; width: 4px; height: 30%;
                      margin-left: -2px; border-radius: 2px; background: #f2f2f2; pointer-events: none; }
    .ss-knob.ss-dragging { cursor: grabbing; }
  `;
  const KNOB_ANGLE = 135;        // degrees each side of 12 o'clock
  const PX_PER_STEP = 3;         // vertical drag distance per step
  const FLASH_MS = 300;

  // printf-like formatting: %d %5d %05d %+05d %.2f %s %%
  function format(value, fmt) {
    if (!fmt) return String(value);
    return fmt.replace(/%([+0-]*)(\d*)(?:\.(\d+))?([dfs%])/g, (all, flags, width, prec, conv) => {
      if (conv === "%") return "%";
      let body, sign = "";
      if (conv === "s") body = String(value);
      else {
        const n = Number(value);
        if (!Number.isFinite(n)) return String(value);
        const abs = Math.abs(n);
        body = conv === "d" ? String(Math.round(abs)) : abs.toFixed(prec === undefined ? 6 : Number(prec));
        if (n < 0 && Number(body) !== 0) sign = "-";
        else if (flags.includes("+")) sign = "+";
      }
      const w = Number(width || 0);
      if (flags.includes("0") && !flags.includes("-") && conv !== "s") {
        return sign + body.padStart(Math.max(w - sign.length, 0), "0");
      }
      const s = sign + body;
      return flags.includes("-") ? s.padEnd(w) : s.padStart(w);
    });
  }

  function clean(doc) {
    for (const s of doc.querySelectorAll("script, link, iframe, object, embed")) s.remove();
    for (const e of doc.querySelectorAll("*")) {
      for (const a of [...e.attributes]) {
        if (/^on/i.test(a.name) || /^\s*javascript:/i.test(a.value)) e.removeAttribute(a.name);
      }
    }
  }

  // Build every panel into `top`; returns an object with update(state) and fit().
  function build(top, panels, send) {
    top.replaceChildren();
    top.hidden = panels.length === 0;
    const binds = { show: [], lit: [], knobs: [], toggles: [] };
    const hosts = [];

    for (const p of panels) {
      const host = document.createElement("div");
      host.className = "panel-host";
      host.setAttribute("role", "region");
      host.setAttribute("aria-label", p.name);
      const root = host.attachShadow({ mode: "open" });
      const doc = new DOMParser().parseFromString(p.html, "text/html");
      clean(doc);
      const base = document.createElement("style");
      base.textContent = BASE_CSS;
      const styles = [...doc.querySelectorAll("style")];
      const wrap = document.createElement("div");
      wrap.className = "ss-panel";
      wrap.append(...[...doc.body.childNodes].filter((n) => !(n.nodeName === "STYLE")));
      root.append(base, ...styles, wrap);
      top.append(host);
      hosts.push({ host, wrap });

      for (const e of root.querySelectorAll("[data-input]")) {
        const name = e.getAttribute("data-input");
        const meta = p.inputs[name];
        if (!meta) continue;
        if (meta.widget === "knob") binds.knobs.push(knob(e, name, meta, send));
        else button(e, name, meta.widget, send, binds);
      }
      for (const e of root.querySelectorAll("[data-show]")) {
        binds.show.push({ el: e, name: e.getAttribute("data-show"), fmt: e.getAttribute("data-format") });
      }
      for (const e of root.querySelectorAll("[data-lit-by]")) {
        binds.lit.push({ el: e, name: e.getAttribute("data-lit-by") });
      }
    }

    function fit() {
      const avail = top.clientWidth - 2 * 12;
      for (const { host, wrap } of hosts) {
        wrap.style.transform = "none";
        const w = wrap.offsetWidth, h = wrap.offsetHeight;
        const s = w > 0 ? Math.min(1, avail / w) : 1;   // never enlarged
        wrap.style.transform = s < 1 ? `scale(${s})` : "none";
        host.style.width = Math.floor(w * s) + "px";
        host.style.height = Math.ceil(h * s) + "px";
      }
    }

    function update(st) {
      for (const b of binds.show) {
        const v = b.name in st.values ? st.values[b.name] : st.inputs[b.name];
        if (v !== undefined) b.el.textContent = format(v, b.fmt);
      }
      for (const b of binds.lit) b.el.classList.toggle("lit", !!st.lit[b.name]);
      for (const k of binds.knobs) k.update(st.inputs[k.name]);
      for (const t of binds.toggles) t.el.setAttribute("aria-pressed", String(!!st.inputs[t.name]));
    }

    requestAnimationFrame(fit);
    return { update, fit };
  }

  function button(e, name, widget, send, binds) {
    if (!e.hasAttribute("tabindex") && e.tagName !== "BUTTON") e.tabIndex = 0;
    if (e.tagName !== "BUTTON") e.setAttribute("role", "button");
    let flash = null;
    const press = () => {
      send(widget === "toggle" ? { type: "toggle", name } : { type: "press", name });
      e.classList.add("pressed");
      clearTimeout(flash);
      flash = setTimeout(() => e.classList.remove("pressed"), FLASH_MS);
    };
    e.addEventListener("click", press);
    if (e.tagName !== "BUTTON") {
      e.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); press(); }
      });
    }
    if (widget === "toggle") binds.toggles.push({ el: e, name });
  }

  function knob(e, name, meta, send) {
    const min = meta.min, max = meta.max, step = meta.step || 1;
    let value = min, dragging = false, pending = false;
    e.classList.add("ss-knob");
    e.tabIndex = 0;
    e.setAttribute("role", "slider");
    if (!e.hasAttribute("aria-label")) e.setAttribute("aria-label", meta.label || name);
    e.setAttribute("aria-valuemin", min);
    e.setAttribute("aria-valuemax", max);

    const draw = () => {
      const frac = max > min ? (value - min) / (max - min) : 0;
      e.style.transform = `rotate(${(-KNOB_ANGLE + 2 * KNOB_ANGLE * frac).toFixed(1)}deg)`;
      e.setAttribute("aria-valuenow", value);
    };
    const set = (v) => {                       // stops at min and max (no wrap)
      v = Math.min(max, Math.max(min, Math.round((v - min) / step) * step + min));
      if (v === value) return;
      value = v;
      draw();
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => { pending = false; send({ type: "set", name, value }); });
    };

    e.addEventListener("pointerdown", (ev) => {
      e.setPointerCapture(ev.pointerId);
      dragging = true;
      e.classList.add("ss-dragging");
      const y0 = ev.clientY, v0 = value;
      const move = (m) => set(v0 + Math.round((y0 - m.clientY) / PX_PER_STEP) * step);
      const up = () => {
        dragging = false;
        e.classList.remove("ss-dragging");
        e.removeEventListener("pointermove", move);
        e.removeEventListener("pointerup", up);
        e.removeEventListener("pointercancel", up);
      };
      e.addEventListener("pointermove", move);
      e.addEventListener("pointerup", up);
      e.addEventListener("pointercancel", up);
    });
    e.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      set(value + (ev.deltaY < 0 ? 1 : -1) * step * (ev.shiftKey ? 10 : 1));
    }, { passive: false });
    e.addEventListener("keydown", (ev) => {
      const k = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1, PageUp: 10, PageDown: -10 }[ev.key];
      if (k) { ev.preventDefault(); set(value + k * step); }
      else if (ev.key === "Home") { ev.preventDefault(); set(min); }
      else if (ev.key === "End") { ev.preventDefault(); set(max); }
    });
    draw();
    return {
      name,
      update: (v) => { if (!dragging && v !== undefined && v !== value) { value = v; draw(); } },
    };
  }

  window.StateSimPanels = { build, format };
})();
