// Logic analyser: choose probes; record a timed run (real delays) that starts from the live machine's
// state, or show the live (zero-delay) simulation as it runs; waveforms with zoom and scroll, two
// cursors with Δt, buses grouped as hex, and VCD export.
import { h, clear, toast, download, fmtTime, fmtTimeRes, tickLabels, fmtFreq, parseTime, clamp } from "./util.js";
import { store } from "./store.js";
import { simctl } from "./simctl.js";
import { engine } from "../engine.js";
import { netKind } from "./signals.js";

const ROW = 30, BUSROW = 30, RULER = 30;
const KIND_VAR = { bus: "--bus", ctrl: "--sky", data: "--leaf", clock: "--berry", addr: "--grey", misc: "--copper", pwr: "--pwr", gnd: "--ink2" };

export class Analyser {
  constructor(root, app) {
    this.root = root; this.app = app;
    this.trace = null;            // {t_unit, signals}
    this.t0 = 0; this.t1 = 1000;  // visible window, ns
    this.tEnd = 0;
    this.cursors = [null, null];
    this.open = new Set();        // expanded bus groups
    this.mode = "auto";
    this.follow = true;           // live mode: keep showing the latest part of the run
    this.caption = "";
    this.isShown = false;
    this.build();
    store.on("change", (e) => { if (e.kind === "load") { this.trace = null; this.cursors = [null, null]; this.mode = "auto"; this.render(); } });
    // the live simulation moved on (its clocks run in real time): show it, a few times a second
    simctl.on("tick", () => { if (this.isShown && this.mode === "zero" && this.follow) this.liveLater(); });
    simctl.on("state", () => { if (this.isShown && this.mode === "zero" && this.follow && this.trace) this.liveLater(); });
  }
  liveLater() {
    if (this.liveT) return;
    this.liveT = setTimeout(async () => { this.liveT = null; if (this.isShown && this.mode === "zero" && !this.running) await this.showLive(); }, 400);
  }
  build() {
    const tb = h("div", { class: "toolbar", role: "toolbar", "aria-label": "Analyser" });
    this.probeBtn = h("button", { class: "btn", "aria-expanded": "false", onclick: () => this.toggleProbes() }, "Probes…");
    this.modeSel = h("select", { class: "input", "aria-label": "How to run", title: "Timed run: a run of its own with every chip's datasheet delay, starting from the live machine. Live: the simulation you operate, as it runs." },
      h("option", { value: "timed" }, "Timed run"), h("option", { value: "zero" }, "Live simulation"));
    this.modeSel.onchange = () => this.setMode(this.modeSel.value);
    this.fromSel = h("select", { class: "input", "aria-label": "Start the timed run from", title: "Where the timed run starts" },
      h("option", { value: "current" }, "from the live state"), h("option", { value: "power" }, "from power-up"));
    this.fromSel.title = "From the live state: registers, RAM (the loaded program), switches and clocks as they are now. From power-up: chips cleared, the switches as they are now.";
    this.amount = h("input", { class: "input mono", value: "10 ms", style: { width: "84px" }, "aria-label": "How long to run", title: "A time such as 10 ms, 50 us, 800 ns — or a number of cycles" });
    this.unitLab = h("span", { class: "hint" });
    this.runBtn = h("button", { class: "btn go", onclick: () => this.run() }, "▶ Run");
    this.followBtn = h("button", { class: "btn", "aria-pressed": "true", title: "Keep showing the live simulation as it runs", onclick: () => this.setFollow(!this.follow) }, "● Follow");
    this.readout = h("span", { class: "cursor-readout", "aria-live": "polite" }, "Click: cursor A · Shift-click: cursor B");
    tb.append(h("span", { class: "title" }, "Analyser"), this.probeBtn, this.modeSel, this.fromSel, this.amount, this.unitLab, this.runBtn, this.followBtn, h("span", { class: "sep" }),
      h("button", { class: "btn icon", title: "Zoom in", "aria-label": "Zoom in", onclick: () => this.zoom(0.5) }, "+"),
      h("button", { class: "btn icon", title: "Zoom out", "aria-label": "Zoom out", onclick: () => this.zoom(2) }, "−"),
      h("button", { class: "btn", title: "Show the whole run", onclick: () => { this.setFollow(false); this.fit(); } }, "Fit"),
      h("button", { class: "btn", title: "Export VCD: save the waveforms as a Value Change Dump file (PulseView, GTKWave)", "aria-label": "Export VCD", onclick: () => this.exportVcd() }, "⤓ VCD"),
      this.readoutSlot = h("span", { class: "readout-slot" }, this.readout));
    // the caption row: what is shown; the cursor readout moves here when the toolbar is too narrow
    this.captionText = h("span", { class: "txt", "aria-live": "polite" });
    this.captionSlot = h("span", { class: "readout-slot" });
    this.captionEl = h("div", { class: "wave-caption" }, this.captionText, this.captionSlot);
    new ResizeObserver(() => this.placeReadout()).observe(tb);
    this.names = h("div", { class: "wave-names" });
    this.canvasBox = h("div", { class: "wave-canvas" });
    this.canvas = h("canvas", { role: "img", "aria-label": "Waveforms" });
    this.canvasBox.append(this.canvas);
    this.wrap = h("div", { class: "wave-wrap" }, this.names, this.canvasBox);
    this.pop = h("div", { class: "probes-pop", hidden: true, role: "dialog", "aria-label": "Choose probes" });
    this.empty = h("div", { class: "empty" });
    this.body = h("div", { style: { position: "relative", flex: "1", minHeight: "0", display: "flex", flexDirection: "column" } }, this.wrap, this.empty, this.pop);
    this.root.append(tb, this.captionEl, this.body);
    new ResizeObserver(() => this.draw()).observe(this.canvasBox);
    this.bindCanvas();
  }
  setMode(mode) {
    this.mode = mode;
    this.modeSel.value = mode;
    const live = mode === "zero";
    this.amount.value = live ? "0" : this.defaultTime();
    this.amount.title = live ? "Clock cycles to add before showing (0: just show the run so far)" : "A time such as 10 ms, 50 us, 800 ns";
    this.unitLab.textContent = live ? "more cycles" : "";
    this.fromSel.hidden = live;
    this.followBtn.hidden = !live;
    this.runBtn.textContent = live ? "▶ Show" : "▶ Run";
    this.runBtn.title = live ? "Show the live simulation (after running the cycles typed, if any)" : "Record a timed run with real delays";
    if (live) { this.trace = null; this.showLive(true); } else { this.trace = null; this.setCaption(""); this.render(); }
  }
  setFollow(on) {
    this.follow = on;
    this.followBtn.setAttribute("aria-pressed", String(on));
    this.followBtn.textContent = on ? "● Follow" : "○ Follow";
    if (on && this.mode === "zero") this.showLive();
  }
  setCaption(text) { this.caption = text; this.captionText.textContent = text; this.captionEl.hidden = !text && this.readout.parentNode !== this.captionSlot; }
  // keep the toolbar on one line: the readout sits at its right end while it fits there, else it
  // moves to the caption row below (no wrapping, nothing cut off)
  placeReadout() {
    const r = this.readout;
    const need = r.scrollWidth;
    if (r.parentNode === this.readoutSlot) {
      if (need > this.readoutSlot.clientWidth + 1) { this.captionSlot.append(r); this.captionEl.hidden = false; }
    } else if (this.readoutSlot.clientWidth >= need + 4) {
      this.readoutSlot.append(r);
      this.captionEl.hidden = !this.caption;
    }
  }
  hidden() { this.isShown = false; }
  shown() {
    this.isShown = true;
    if (this.mode === "auto") this.setMode(this.isCpu() ? "zero" : "timed");
    else if (this.mode === "zero") this.showLive(!this.trace);
    else this.render();
  }
  isCpu() { return store.project.nets.some((n) => n.name === "HLT_n"); }
  defaultTime() {
    // a few periods of the slowest clock source in the project, if one is marked
    const per = (store.project.stimuli || []).map((s) => s.period_ns).filter(Boolean);
    const c = store.project.parts.filter((p) => p.type === "CLOCK").map((p) => +(p.props && p.props.period_ns)).filter(Boolean);
    const all = [...per, ...c];
    if (all.length) return fmtTime(6 * Math.max(...all)).replace(" ", " ");
    return store.project.parts.some((p) => /555/.test(p.type)) ? "10 ms" : "5 µs";
  }
  probes() { return store.project.probes || []; }

  // ------------------------------------------------------------------ probe chooser
  toggleProbes(force) {
    const open = force ?? this.pop.hidden;
    this.pop.hidden = !open;
    this.probeBtn.setAttribute("aria-expanded", String(open));
    if (!open) return;
    clear(this.pop);
    const q = h("input", { class: "input", type: "search", placeholder: "Filter nets…", "aria-label": "Filter nets" });
    const list = h("div", { class: "list" });
    const fill = () => {
      clear(list);
      const want = q.value.trim().toLowerCase();
      const names = store.project.nets.map((n) => n.name).filter((n) => !/~/.test(n) && n !== "VCC" && n !== "GND").sort(natural);
      for (const n of names.filter((x) => !want || x.toLowerCase().includes(want))) {
        const cb = h("input", { type: "checkbox", checked: this.probes().includes(n) });
        cb.onchange = () => store.commit("probes", (p) => { p.probes = cb.checked ? [...new Set([...p.probes, n])] : p.probes.filter((x) => x !== n); }, "view");
        list.append(h("label", {}, cb, n));
      }
    };
    q.oninput = fill;
    fill();
    this.pop.append(h("div", { style: { display: "flex", gap: "6px" } }, q,
      h("button", { class: "btn", onclick: () => { store.commit("clear probes", (p) => { p.probes = []; }, "view"); fill(); this.render(); } }, "Clear"),
      h("button", { class: "btn primary", onclick: () => { this.toggleProbes(false); this.render(); } }, "Done")), list);
    q.focus();
  }

  // ------------------------------------------------------------------ running
  async run() {
    const probes = this.probes();
    if (!probes.length) { this.toggleProbes(true); toast("Choose at least one probe first."); return; }
    this.runBtn.disabled = true;
    this.running = true;
    try {
      if (this.mode === "timed") {
        const ns = parseTime(this.amount.value);
        if (!(ns > 0)) { toast("Type a time such as 10 ms, 50 us or 800 ns."); return; }
        const fromCurrent = this.fromSel.value === "current";
        this.readout.textContent = "Running the timed simulation…";
        await simctl.whenReady();
        // a simulator of its own: the live one (and the program in its RAM) carries on untouched
        const r = await simctl.q(() => engine.timedRun(ns, probes, fromCurrent));
        this.trace = r.trace;
        this.trace.t_end = this.trace.t_end || ns;
        const notes = (r.errors || []).filter((e) => typeof e === "object").map((e) => ({ ...e, severity: e.kind === "contention" ? "warning" : e.severity || "warning", message: `Timed run: ${e.message}` }));
        if (notes.length) setTimeout(() => simctl.emit("problems", [...simctl.problems, ...notes]), 400);
        const from = r.from === "current" ? "the live state (registers, RAM with the program, switches, clocks)" : "power-up (chips cleared, switches as set)";
        this.setCaption(`Timed run of ${fmtTime(ns)} with datasheet delays, from ${from}. The live simulation is not changed.`);
        this.tEnd = this.trace.t_end;
        this.fit();
        this.render();
      } else {
        const n = parseInt(this.amount.value || "0", 10) || 0;
        await simctl.whenReady();
        if (n > 0) await simctl.step(n);
        await this.showLive(true);
        if (this.trace && this.trace.signals.every((s) => s.changes.length <= 1))
          toast(this.isCpu() ? "Nothing has changed yet: set RUN/STEP to RUN on the front panel (and load a program)." : "Nothing has changed yet: does the circuit have a clock source, and is the clock running?", 6000);
      }
    } catch (e) {
      console.error(e);
      toast(`The run failed: ${e.message}`, 6000);
    } finally { this.runBtn.disabled = false; this.running = false; }
  }
  // the live (zero-delay) simulation's record so far, without moving it on
  async showLive(fitAll = false) {
    const probes = this.probes();
    if (!probes.length) { this.render(); return; }
    if (!(await simctl.whenReady())) return;
    const tr = await simctl.q(() => (simctl.ready ? engine.trace(probes) : null));
    if (!tr) return;
    const st = simctl.state || {};
    const span = this.t1 - this.t0;
    const first = !this.trace;
    this.trace = tr;
    this.tEnd = Math.max(1, tr.t_end || 0, st.t_ns || 0, ...tr.signals.map((s) => (s.changes.length ? s.changes[s.changes.length - 1][0] : 0)));
    const t0 = Math.min(...tr.signals.filter((s) => s.changes.length).map((s) => s.changes[0][0]), this.tEnd);
    const info = simctl.clockInfo();
    const what = info.cpu ? (info.halted ? "halted" : !info.runMode ? "STEP mode" : info.running ? "running" : "clock paused") : info.running ? "running" : info.has ? "clock paused" : "no clock";
    this.setCaption(`Live simulation (${what}): what the circuit has done since it was loaded${st.cycles ? `, ${st.cycles} clock cycles` : ""}. Zero-delay: changes are shown at the clock edges.`);
    if (fitAll || first) { this.t0 = Math.max(0, t0 === this.tEnd ? 0 : t0); this.t1 = Math.max(this.tEnd, this.t0 + 1); }
    else if (this.follow) { this.t1 = this.tEnd; this.t0 = Math.max(0, this.t1 - span); }
    this.render();
  }

  // ------------------------------------------------------------------ rows (buses grouped)
  rows() {
    const sigs = new Map(((this.trace && this.trace.signals) || []).map((s) => [s.name, s]));
    const groups = new Map();
    for (const n of this.probes()) {
      const m = n.match(/^(.*?[A-Za-z_])(\d+)$/);
      const key = m ? m[1] : null;
      if (key) { if (!groups.has(key)) groups.set(key, []); groups.get(key).push([+m[2], n]); }
    }
    const done = new Set(), out = [];
    for (const n of this.probes()) {
      if (done.has(n)) continue;
      const m = n.match(/^(.*?[A-Za-z_])(\d+)$/);
      const g = m && groups.get(m[1]);
      if (g && g.length >= 2) {
        const bits = g.sort((a, b) => a[0] - b[0]);
        for (const [, x] of bits) done.add(x);
        const name = `${m[1]}[${bits[bits.length - 1][0]}:${bits[0][0]}]`;
        out.push({ bus: true, name, key: m[1], bits: bits.map(([k, x]) => ({ k, name: x, sig: sigs.get(x) })) });
        if (this.open.has(m[1])) for (const b of [...bits].reverse()) out.push({ name: b[1], sig: sigs.get(b[1]), child: true });
      } else { done.add(n); out.push({ name: n, sig: sigs.get(n) }); }
    }
    return out;
  }
  render() {
    const has = this.trace && this.probes().length;
    this.wrap.hidden = !has;
    this.empty.hidden = !!has;
    clear(this.empty);
    if (!has) {
      const p = this.probes();
      this.empty.append(h("div", { class: "card" },
        h("h3", {}, "Logic analyser"),
        h("p", {}, p.length ? `Probes: ${p.slice(0, 12).join(", ")}${p.length > 12 ? "…" : ""}. Press Run to record them.` : "Choose the nets to watch, then press Run."),
        h("p", { class: "hint" }, "Timed run: a run of its own with each chip's datasheet delay, starting from the live machine as it is now (registers, RAM with the loaded program, switches) or from power-up. Live simulation: what the circuit you operate on the schematic or front panel is doing, shown as it runs."),
        h("div", { style: { display: "flex", gap: "8px", justifyContent: "center" } },
          h("button", { class: "btn", onclick: () => this.toggleProbes(true) }, "Choose probes"),
          p.length ? h("button", { class: "btn go", onclick: () => this.run() }, "▶ Run") : null)));
      return;
    }
    this.draw();
  }
  fit() { this.t0 = 0; this.t1 = Math.max(this.tEnd, 1); this.draw(); }
  zoom(f, at) {
    const span = this.t1 - this.t0;
    const c = at ?? (this.t0 + this.t1) / 2;
    const ns = clamp(span * f, 0.5, Math.max(this.tEnd * 1.2, 10));
    this.t0 = c - (c - this.t0) * (ns / span);
    this.t1 = this.t0 + ns;
    if (this.t0 < 0) { this.t1 -= this.t0; this.t0 = 0; }
    this.draw();
  }

  // ------------------------------------------------------------------ drawing
  colours() {
    const cs = getComputedStyle(document.documentElement);
    const v = (n) => cs.getPropertyValue(n).trim();
    return { bg: v("--wave-bg"), grid: v("--wave-grid"), ink: v("--ink"), ink2: v("--ink2"), ink3: v("--ink3"), z: v("--vz"), x: v("--vx"), sky: v("--sky"), berry: v("--berry"),
      line: v("--line"), card: v("--card"), kind: (net) => v(KIND_VAR[netKind(net)] || "--leaf") };
  }
  draw() {
    if (!this.trace || this.wrap.hidden) return;
    const rows = this.rows();
    this.rowsCache = rows;
    const box = this.canvasBox.getBoundingClientRect();
    const W = Math.max(50, box.width), Hh = Math.max(RULER + rows.length * ROW + 10, box.height);
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = W * dpr; this.canvas.height = box.height * dpr;
    const g = this.canvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const C = this.colours();
    g.fillStyle = C.bg; g.fillRect(0, 0, W, Hh);
    const X = (t) => ((t - this.t0) / (this.t1 - this.t0)) * W;
    this.X = X;
    // ruler and grid
    const step = niceStep((this.t1 - this.t0) / Math.max(2, W / 110));
    g.font = "11px JBM, monospace"; g.textBaseline = "middle";
    g.fillStyle = C.card; g.fillRect(0, 0, W, RULER);
    g.strokeStyle = C.line; g.beginPath(); g.moveTo(0, RULER + 0.5); g.lineTo(W, RULER + 0.5); g.stroke();
    const ticks = [];
    for (let k = Math.ceil(this.t0 / step); k * step <= this.t1 && ticks.length < 400; k++) ticks.push(k * step);
    const { base, labels } = tickLabels(ticks, step);
    this.tickText = labels;
    ticks.forEach((t, i) => {
      const x = Math.round(X(t)) + 0.5;
      g.strokeStyle = C.grid; g.beginPath(); g.moveTo(x, RULER); g.lineTo(x, Hh); g.stroke();
      g.strokeStyle = C.ink3; g.beginPath(); g.moveTo(x, RULER - 6); g.lineTo(x, RULER); g.stroke();
      if (base && i === 0) return;                      // the base time is shown in its own box
      g.fillStyle = C.ink2; g.fillText(labels[i], x + 3, RULER / 2);
    });
    if (base && ticks.length) {
      // zoomed far in: ticks are offsets from the first tick, whose time is shown here
      const x = Math.max(2, Math.round(X(ticks[0])) + 3), txt = `t = ${base}`, w = g.measureText(txt).width + 10;
      g.fillStyle = C.bg; g.fillRect(x - 3, 4, w, RULER - 8);
      g.strokeStyle = C.ink3; g.strokeRect(x - 2.5, 4.5, w - 1, RULER - 9);
      g.fillStyle = C.ink; g.fillText(txt, x + 2, RULER / 2);
    }
    this.tickBase = base;
    // end of recorded data
    if (this.tEnd < this.t1) { g.fillStyle = "rgba(128,128,128,0.08)"; g.fillRect(X(this.tEnd), RULER, W - X(this.tEnd), Hh); }
    // signals
    rows.forEach((r, i) => {
      const y0 = RULER + i * ROW;
      g.strokeStyle = C.grid; g.beginPath(); g.moveTo(0, y0 + ROW + 0.5); g.lineTo(W, y0 + ROW + 0.5); g.stroke();
      if (r.bus) this.drawBus(g, r, y0, X, W, C);
      else this.drawBit(g, r, y0, X, W, C);
    });
    // cursors
    const lab = ["A", "B"];
    this.cursors.forEach((t, k) => {
      if (t == null) return;
      const x = Math.round(X(t)) + 0.5;
      const col = k ? C.berry : C.sky;
      g.strokeStyle = col; g.lineWidth = 1.5; g.setLineDash(k ? [5, 3] : []);
      g.beginPath(); g.moveTo(x, 0); g.lineTo(x, Hh); g.stroke();
      g.setLineDash([]); g.lineWidth = 1;
      g.fillStyle = col; g.fillRect(x - 9, 2, 18, 16);
      g.fillStyle = "#fff"; g.font = "bold 11px Lexend, sans-serif"; g.textAlign = "center"; g.fillText(lab[k], x, 10); g.textAlign = "start";
    });
    this.drawNames(rows);
    this.updateReadout();
  }
  drawBit(g, r, y0, X, W, C) {
    const ch = (r.sig && r.sig.changes) || [];
    const hi = y0 + 7, lo = y0 + ROW - 7, mid = (hi + lo) / 2;
    const col = C.kind(r.name);
    let prevV = null, prevX = null;
    const seg = (v, xa, xb) => {
      if (xb < 0 || xa > W) return;
      xa = Math.max(xa, -2); xb = Math.min(xb, W + 2);
      if (v === 1 || v === 0) {
        g.strokeStyle = v === 1 ? col : col; g.lineWidth = v === 1 ? 2 : 1.6;
        g.beginPath(); g.moveTo(xa, v === 1 ? hi : lo); g.lineTo(xb, v === 1 ? hi : lo); g.stroke();
        if (v === 1) { g.fillStyle = col; g.globalAlpha = 0.12; g.fillRect(xa, hi, xb - xa, lo - hi); g.globalAlpha = 1; }
      } else if (v === "Z") {
        g.strokeStyle = C.z; g.lineWidth = 1.4; g.setLineDash([4, 3]);
        g.beginPath(); g.moveTo(xa, mid); g.lineTo(xb, mid); g.stroke(); g.setLineDash([]);
      } else {
        g.fillStyle = C.x; g.globalAlpha = 0.2; g.fillRect(xa, hi, xb - xa, lo - hi); g.globalAlpha = 1;
        g.strokeStyle = C.x; g.lineWidth = 1; g.strokeRect(xa, hi, xb - xa, lo - hi);
      }
      g.lineWidth = 1;
    };
    for (let k = 0; k < ch.length; k++) {
      const [t, v] = ch[k];
      const tn = k + 1 < ch.length ? ch[k + 1][0] : this.tEnd;
      const xa = X(t), xb = X(tn);
      if (prevV != null && prevV !== v && xa >= -2 && xa <= W + 2 && (prevV === 0 || prevV === 1) && (v === 0 || v === 1)) {
        g.strokeStyle = col; g.lineWidth = 1.6; g.beginPath(); g.moveTo(xa, hi); g.lineTo(xa, lo); g.stroke(); g.lineWidth = 1;
      }
      seg(v, xa, xb);
      prevV = v; prevX = xb;
    }
  }
  busChanges(r) {
    // merge the bits' change times into one list of [t, value | "X" | "Z"]
    const times = new Set();
    for (const b of r.bits) for (const [t] of (b.sig && b.sig.changes) || []) times.add(t);
    const ts = [...times].sort((a, b) => a - b);
    const idx = r.bits.map(() => 0);
    const out = [];
    for (const t of ts) {
      let v = 0, bad = null;
      r.bits.forEach((b, i) => {
        const ch = (b.sig && b.sig.changes) || [];
        while (idx[i] + 1 < ch.length && ch[idx[i] + 1][0] <= t) idx[i]++;
        const bv = ch.length && ch[idx[i]][0] <= t ? ch[idx[i]][1] : null;
        if (bv === 1) v |= 1 << b.k;
        else if (bv !== 0) bad = bad || (bv === "Z" ? "Z" : "X");
      });
      const val = bad && bad === "Z" && r.bits.every((b) => { const ch = (b.sig && b.sig.changes) || []; const c = ch[idx[r.bits.indexOf(b)]]; return c && c[1] === "Z"; }) ? "Z" : bad ? "X" : v;
      if (!out.length || out[out.length - 1][1] !== val) out.push([t, val]);
    }
    return out;
  }
  drawBus(g, r, y0, X, W, C) {
    const ch = this.busChanges(r);
    r.changes = ch;
    const hi = y0 + 7, lo = y0 + ROW - 7, mid = (hi + lo) / 2;
    const col = C.kind(r.key + "0");
    const width = Math.ceil(r.bits.length / 4);
    g.font = "11px JBM, monospace"; g.textBaseline = "middle";
    for (let k = 0; k < ch.length; k++) {
      const [t, v] = ch[k];
      const tn = k + 1 < ch.length ? ch[k + 1][0] : this.tEnd;
      let xa = X(t), xb = X(tn);
      if (xb < 0 || xa > W) continue;
      const e = Math.min(4, (xb - xa) / 2);
      if (v === "Z") { g.strokeStyle = C.z; g.setLineDash([4, 3]); g.beginPath(); g.moveTo(xa, mid); g.lineTo(xb, mid); g.stroke(); g.setLineDash([]); continue; }
      g.beginPath();
      g.moveTo(xa, mid); g.lineTo(xa + e, hi); g.lineTo(xb - e, hi); g.lineTo(xb, mid); g.lineTo(xb - e, lo); g.lineTo(xa + e, lo); g.closePath();
      g.fillStyle = v === "X" ? C.x : col; g.globalAlpha = 0.16; g.fill(); g.globalAlpha = 1;
      g.strokeStyle = v === "X" ? C.x : col; g.lineWidth = 1.4; g.stroke(); g.lineWidth = 1;
      const label = v === "X" ? "X" : v.toString(16).toUpperCase().padStart(width, "0");
      const tw = g.measureText(label).width;
      const a = Math.max(xa, 0) + 6, b = Math.min(xb, W) - 6;
      if (b - a > tw) { g.fillStyle = C.ink; g.fillText(label, (a + b) / 2 - tw / 2, mid + 0.5); }
    }
  }
  drawNames(rows) {
    clear(this.names);
    this.names.append(h("div", { class: "wave-ruler", style: { height: `${RULER}px`, borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", padding: "0 10px", fontSize: "11px", color: "var(--ink3)" } }, "Signal", h("span", { style: { marginLeft: "auto" } }, "at A")));
    rows.forEach((r, i) => {
      const v = this.valueAt(r, this.cursors[0]);
      const col = `var(${KIND_VAR[netKind(r.bus ? r.key + "0" : r.name)] || "--leaf"})`;
      const el = h("div", { class: "wave-name", style: { top: `${RULER + i * ROW}px`, height: `${ROW}px`, paddingLeft: r.child ? "26px" : "10px" } },
        h("span", { class: "sw", style: { background: col } }),
        r.bus ? h("span", { class: "tw", role: "button", tabindex: "0", "aria-label": this.open.has(r.key) ? "Collapse bus" : "Expand bus", onclick: () => { this.open.has(r.key) ? this.open.delete(r.key) : this.open.add(r.key); this.draw(); } }, this.open.has(r.key) ? "▾" : "▸") : null,
        h("span", {}, r.name),
        h("span", { class: "val" }, v),
        r.child ? null : h("button", { title: `Remove ${r.name}`, "aria-label": `Remove ${r.name}`, onclick: () => this.removeRow(r) }, "✕"));
      this.names.append(el);
    });
  }
  removeRow(r) {
    const drop = new Set(r.bus ? r.bits.map((b) => b.name) : [r.name]);
    store.commit("probes", (p) => { p.probes = p.probes.filter((x) => !drop.has(x)); }, "view");
    this.draw();
  }
  valueAt(r, t) {
    if (t == null) return "";
    const ch = r.bus ? r.changes || this.busChanges(r) : (r.sig && r.sig.changes) || [];
    let v = null;
    for (const [tt, vv] of ch) { if (tt <= t) v = vv; else break; }
    if (v == null) return "";
    if (r.bus) return typeof v === "number" ? `${v.toString(16).toUpperCase().padStart(Math.ceil(r.bits.length / 4), "0")}h ${v}` : v;
    return String(v);
  }
  updateReadout() {
    const [a, b] = this.cursors;
    const parts = [];
    const res = Math.max((this.t1 - this.t0) / Math.max(100, this.canvasBox.clientWidth || 800), 1e-3);
    if (a != null) parts.push(h("span", { class: "ca" }, h("b", {}, "A "), fmtTimeRes(a, res)));
    if (b != null) parts.push(h("span", { class: "cb" }, h("b", {}, "B "), fmtTimeRes(b, res)));
    if (a != null && b != null) { const d = Math.abs(b - a); parts.push(h("span", {}, h("b", {}, "Δt "), fmtTime(d, 4)), h("span", {}, h("b", {}, "1/Δt "), fmtFreq(1e9 / d))); }
    clear(this.readout);
    if (!parts.length) {
      this.readout.append(`${fmtTimeRes(this.t0, res * 10)} – ${fmtTimeRes(this.t1, res * 10)}`);
      this.readout.title = "Click: cursor A · Shift-click or right-click: cursor B · wheel: zoom · drag: scroll";
    } else { this.readout.append(...parts); this.readout.title = this.readout.textContent; }
    this.placeReadout();
  }

  // ------------------------------------------------------------------ mouse
  bindCanvas() {
    const cv = this.canvas;
    const tAt = (e) => { const r = cv.getBoundingClientRect(); return this.t0 + ((e.clientX - r.left) / r.width) * (this.t1 - this.t0); };
    cv.addEventListener("wheel", (e) => {
      e.preventDefault();
      if (this.mode === "zero" && this.follow) this.setFollow(false);
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        const d = (e.deltaX || e.deltaY) / cv.getBoundingClientRect().width * (this.t1 - this.t0);
        this.t0 = Math.max(0, this.t0 + d); this.t1 = this.t0 + (this.t1 - this.t0 + 0) ; this.t1 = this.t0 + (this.t1 - this.t0);
        const span = this.t1 - this.t0; this.t1 = this.t0 + span;
        this.draw(); return;
      }
      this.zoom(Math.exp(e.deltaY * 0.002), tAt(e));
    }, { passive: false });
    cv.addEventListener("pointerdown", (e) => {
      const x0 = e.clientX, t0 = this.t0, t1 = this.t1;
      const near = this.cursors.findIndex((t) => t != null && Math.abs(this.X(t) - (e.clientX - cv.getBoundingClientRect().left)) < 6);
      let moved = false;
      const mv = (ev) => {
        if (Math.abs(ev.clientX - x0) > 3) moved = true;
        if (!moved) return;
        if (near >= 0) { this.cursors[near] = Math.max(0, tAt(ev)); this.draw(); return; }
        if (this.mode === "zero" && this.follow) this.setFollow(false);
        const dt = ((ev.clientX - x0) / cv.getBoundingClientRect().width) * (t1 - t0);
        this.t0 = Math.max(0, t0 - dt); this.t1 = this.t0 + (t1 - t0); this.draw();
      };
      const up = (ev) => {
        window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up);
        if (!moved) { this.cursors[ev.shiftKey || ev.button === 2 ? 1 : 0] = Math.max(0, tAt(ev)); this.draw(); }
      };
      window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
    });
    cv.addEventListener("contextmenu", (e) => { e.preventDefault(); this.cursors[1] = Math.max(0, tAt(e)); this.draw(); });
  }

  // ------------------------------------------------------------------ VCD
  exportVcd() {
    if (!this.trace) { toast("Run first, then export."); return; }
    download(`${(store.project.name || "trace").replace(/[^\w.-]+/g, "_")}.vcd`, toVcd(this.trace, store.project.name), "text/plain");
  }
}

// A standard Value Change Dump (IEEE 1364): one 1-bit wire per net, time in picoseconds.
export function toVcd(trace, name = "bench") {
  const sigs = trace.signals || [];
  const id = (i) => { let s = ""; i += 0; do { s += String.fromCharCode(33 + (i % 94)); i = Math.floor(i / 94); } while (i > 0); return s; };
  const out = [`$date ${new Date().toISOString()} $end`, "$version Breadboard Bench $end", "$timescale 1ps $end", `$scope module ${String(name).replace(/\W+/g, "_") || "top"} $end`];
  sigs.forEach((s, i) => out.push(`$var wire 1 ${id(i)} ${s.name.replace(/\s+/g, "_")} $end`));
  out.push("$upscope $end", "$enddefinitions $end");
  const ev = new Map();
  sigs.forEach((s, i) => { for (const [t, v] of s.changes) { const ps = Math.round(t * 1000); if (!ev.has(ps)) ev.set(ps, []); ev.get(ps).push(`${v === 1 ? "1" : v === 0 ? "0" : v === "Z" ? "z" : "x"}${id(i)}`); } });
  const times = [...ev.keys()].sort((a, b) => a - b);
  let first = true;
  for (const t of times) { out.push(`#${t}`); if (first) { out.push("$dumpvars"); } out.push(...ev.get(t)); if (first) { out.push("$end"); first = false; } }
  if (trace.t_end) out.push(`#${Math.round(trace.t_end * 1000)}`);
  return out.join("\n") + "\n";
}
function niceStep(x) {
  const p = 10 ** Math.floor(Math.log10(x));
  for (const m of [1, 2, 5, 10]) if (m * p >= x) return m * p;
  return 10 * p;
}
const natural = (a, b) => a.localeCompare(b, undefined, { numeric: true });
