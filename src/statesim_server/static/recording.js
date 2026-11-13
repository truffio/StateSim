// FMA recording: Start/Stop buttons in the run bar mark a window; Stop turns
// the FMA changes in it into rows (one per input that changed the settled
// FMA) and opens the editable preview (recorder.html). Logging (trace,
// timeline) is not affected: this module only reads the state messages and
// timeline items the page already receives. Used by app.js.
"use strict";

(function () {
  const START_LABEL = "Start of the manoeuvre";

  // ---- rows (pure; also used by the tests through window.StateSimRecorder)
  function isPress(meta) { return meta && (meta.widget === "momentary" || meta.widget === "lit"); }

  // Plain-English cause: "Approach button pressed", "Radio altitude set to 2500 ft".
  function describe(item, inputs) {
    const m = inputs[item.name] || {};
    const what = m.description || m.label || item.name;
    if (isPress(m)) return `${what} pressed`;
    if (m.type === "bool" || typeof item.value === "boolean") return `${what} ${item.value ? "on" : "off"}`;
    return `${what} set to ${item.value}${m.unit ? " " + m.unit : ""}`;
  }

  // start: {t, lit: [vars lit at Start]}; items: timeline items in the window
  // (any order); vars: the FMA's lit variables; inputs: model.inputs.
  // Returns rows [{kind: "start"|"change", t, lit: [...], label, others: [...]}]:
  // the start row, then one row per input whose changes left a different
  // settled FMA. All FMA changes between one input and the next are merged.
  function buildRows(start, items, vars, inputs) {
    const watched = new Set(vars);
    const list = [...items].sort((a, b) => a.id - b.id);
    const byId = new Map(list.map((it) => [it.id, it]));
    const cur = new Set(start.lit.filter((v) => watched.has(v)));
    const key = () => [...cur].sort().join(" ");
    const rows = [{ kind: "start", t: start.t, lit: [...cur].sort(), label: START_LABEL, others: [] }];
    let shown = key();
    let group = null;

    const roots = (dps) => {          // the inputs (in the window) that led to these changes
      const found = new Map(), seen = new Set();
      const walk = (id) => {
        if (seen.has(id)) return;
        seen.add(id);
        const it = byId.get(id);
        if (!it) return;                // before the window, or dropped by the cap
        if (it.k === "in") { if (!(isPress(inputs[it.name]) && it.value === false)) found.set(it.id, it); return; }
        for (const c of it.causes || []) walk(c);
      };
      for (const d of dps) for (const c of d.causes || []) walk(c);
      return [...found.values()].sort((a, b) => a.id - b.id);
    };
    const close = () => {
      if (!group) return;
      const k = key();
      if (group.dps.length && k !== shown) {
        const causes = roots(group.dps);
        const main = causes.length ? causes[causes.length - 1] : group.input;
        rows.push({
          kind: "change",
          t: main ? main.t : group.dps[0].t,
          lit: [...cur].sort(),
          label: main ? describe(main, inputs) : "FMA change",
          others: causes.slice(0, -1).map((c) => describe(c, inputs)),
        });
        shown = k;
      }
      group = null;
    };
    for (const it of list) {
      if (it.k === "in") {
        if (isPress(inputs[it.name]) && it.value === false) continue;    // the end of a press
        close();
        group = { input: it, dps: [] };
      } else if (it.k === "dp" && watched.has(it.name)) {
        if (!group) group = { input: null, dps: [] };
        if (it.value) cur.add(it.name); else cur.delete(it.name);
        group.dps.push(it);
      }
    }
    close();
    return rows;
  }

  // ---- page part
  function build(model, opts) {
    const rec = model.recorder;
    const startBtn = document.getElementById("rec-start");
    const stopBtn = document.getElementById("rec-stop");
    const clock = document.getElementById("rec-clock");
    if (!startBtn || !stopBtn) return null;
    startBtn.hidden = stopBtn.hidden = true;
    if (clock) clock.hidden = true;
    if (!rec) return null;                                   // no FMA panel: no recording

    let last = null;          // latest state message
    let maxId = 0;            // newest timeline item seen
    let gen = null;
    let rec0 = null;          // {t, lit, gen, startId, items: Map}
    let resetting = false;    // Reset clicked: the next new gen is expected
    const say = opts && opts.banner ? opts.banner : () => {};

    const ingest = (items) => {
      for (const it of items || []) {
        if (it.id > maxId) maxId = it.id;
        if (rec0 && it.id > rec0.startId) rec0.items.set(it.id, it);
      }
    };
    const showButtons = () => {
      startBtn.hidden = !!rec0;
      stopBtn.hidden = !rec0;
      if (clock) clock.hidden = !rec0;
    };
    const tick = () => {
      if (clock && rec0 && last) clock.textContent = `REC ${((last.t - rec0.t) / 1000).toFixed(1)} s`;
    };

    const fresh = (st) => ({
      t: st.t || 0, gen,
      lit: rec.vars.filter((v) => st.lit && st.lit[v]),
      startId: maxId, items: new Map(),
    });
    function start() {
      if (!last) return;
      rec0 = fresh(last);
      showButtons();
      tick();
    }
    // A new gen (Reset): item ids start again at 1. A recording started after
    // the Reset click restarts on the new run; one from before ends.
    function newGen(g, st) {
      gen = g;
      maxId = 0;
      if (rec0) {
        if (resetting && st) rec0 = fresh(st);
        else stop(false);
      }
      resetting = false;
    }

    // Stop: build the rows and open the preview. Called from the click (so the
    // window is allowed to open) or, with open = false, when a reset ended it.
    function stop(open = true) {
      if (!rec0) return null;
      const r = rec0;
      rec0 = null;
      showButtons();
      const rows = buildRows({ t: r.t, lit: r.lit }, [...r.items.values()], rec.vars, model.inputs || {});
      const data = {
        type: "statesim-recording",
        layout: "compact",
        source: model.source || "",
        when: new Date().toISOString(),
        start: r.t, end: last ? last.t : r.t,
        panel: { label: rec.label, html: rec.html },
        rows,
      };
      if (!open) { say("Recording ended by the reset."); return data; }
      const w = window.open("recorder.html", "_blank");
      if (!w) { say("The browser blocked the recording window: allow pop-ups for this page and press Stop again."); return data; }
      const onMsg = (e) => {
        if (e.source !== w || e.data !== "statesim-recorder-ready") return;
        window.removeEventListener("message", onMsg);
        w.postMessage(data, location.origin);
      };
      window.addEventListener("message", onMsg);
      return data;
    }

    startBtn.addEventListener("click", start);
    stopBtn.addEventListener("click", () => stop(true));
    showButtons();

    return {
      state(st) {
        if (st.gen !== undefined && gen !== null && st.gen !== gen) newGen(st.gen, st);
        else if (st.gen !== undefined) gen = st.gen;
        last = st;
        ingest(st.tl);
        tick();
      },
      timeline(msg) {
        if (gen !== null && msg.gen !== gen) newGen(msg.gen, null);
        else gen = msg.gen;
        ingest(msg.items);
      },
      beforeReset() {                                   // Reset clicked while recording: same as Stop
        if (rec0) stop(true);
        resetting = true;
      },
      get recording() { return !!rec0; },
      start, stop,
    };
  }

  window.StateSimRecorder = { build, buildRows, describe };
})();
