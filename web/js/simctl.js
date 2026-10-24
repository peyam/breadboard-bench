// Keeps the engine in step with the open project: reloads it after netlist edits, remembers how the
// reader has set every switch and button, and hands the latest simulator state to the views.
// It also runs the live simulation's clocks in real time: every clock source and astable 555 keeps
// ticking at the chosen speed, on every tab, as on the real bench (PC-2's 555 clock always runs;
// its RUN/STEP switch decides whether the machine sees it).
import { engine } from "../engine.js";
import { store } from "./store.js";
import { Emitter, debounce, toast, storageGet, storageSet } from "./util.js";
import { getDef, baseType, positions } from "./parts.js";

class SimCtl extends Emitter {
  constructor() {
    super();
    this.ctl = {};               // part id -> true/false (SW, BTN), throw name (SPDT, JP), [bools] (DIPSW)
    this.msb = {};               // DIPSW part id -> true when section 1 is the highest bit
    this.state = { nets: {}, leds: {}, digits: {}, errors: [] };
    this.problems = [];
    this.live = true;
    this.ready = false;
    this.busy = Promise.resolve();
    this.syncing = null;
    this.rev = -1;
    this.mode = "zero";
    this.lastError = null;
    // real-time clock
    this.clocks = [];            // the live simulation's clock sources, main clock first
    this.speed = null;           // main-clock cycles per second, "real" (real time) or Infinity (fastest)
    this.paused = false;         // the reader paused the clocks
    this.ticking = false;
    this.lastPaint = 0;
    this.batch = 20;
    const later = debounce(() => this.sync(), 250);
    store.on("change", (e) => { if (e.kind !== "view") { if (e.kind === "load") { this.ctl = {}; this.speed = null; this.paused = false; this.sync(); } else later(); } });
    engine.on("backend", () => this.sync());
  }
  // serialise engine calls so a sync never interleaves with a step
  q(fn) {
    const r = this.busy.then(fn, fn);
    this.busy = r.catch(() => {});
    return r;
  }
  defaults() {
    for (const p of store.project.parts) {
      if (p.id in this.ctl) continue;
      const t = baseType(p.type);
      const pr = { ...((getDef(p.type) || {}).props || {}), ...(p.props || {}) };
      if (t === "SW") this.ctl[p.id] = !!pr.closed;
      else if (t === "BUTTON") this.ctl[p.id] = false;
      else if (t === "SPDT" || t === "JUMPER3") { const pos = positions(p); this.ctl[p.id] = typeof pr.pos === "string" ? pr.pos : pos[pr.pos || 0]; }
      else if (/^DIPSW\d+$/.test(t)) { const n = +t.slice(5), c = pr.closed || 0; this.msb[p.id] = !!pr.msb_first; this.ctl[p.id] = Array.from({ length: n }, (_, k) => (Array.isArray(c) ? !!c[k] : !!((c >> this.bitOf(p.id, k + 1, n)) & 1))); }
    }
  }
  // the engine reports where every switch is: that is the truth the views draw
  takeSwitches(sw) {
    if (!sw) return;
    for (const [id, v] of Object.entries(sw)) {
      if (Array.isArray(v)) this.ctl[id] = v.map((x) => !!x);
      else if (typeof v === "string") this.ctl[id] = v;
      else if (typeof v === "boolean" || typeof v === "number") this.ctl[id] = !!v;
    }
  }
  sync() {
    const rev = store.rev;
    this.syncing = this.q(async () => {
      if (!store.project.parts.length) { this.ready = false; this.state = { nets: {}, leds: {}, digits: {}, errors: [] }; this.emit("state", this.state); this.problems = []; this.emit("problems", []); return; }
      try {
        await engine.loadProject(store.project);
        this.defaults();
        await engine.newSim(this.mode);
        for (const [id, v] of Object.entries(this.ctl)) {
          if (!store.project.parts.some((p) => p.id === id)) { delete this.ctl[id]; continue; }
          if (Array.isArray(v)) { for (let k = 0; k < v.length; k++) if (v[k]) await engine.set(`${id}.${k + 1}`, true); }
          else if (v !== false) await engine.set(id, v === true ? true : v);
        }
        this.ready = true;
        this.rev = rev;
        this.lastError = null;
        try { this.clocks = (await engine.clocks()) || []; } catch (e) { this.clocks = []; }
        if (this.speed == null) this.speed = this.defaultSpeed();
        this.emit("clock", this.clockInfo());
        await this._refresh();
        this.problems = await engine.check();
        this.emit("problems", this.problems);
      } catch (e) {
        console.warn("sync failed", e);
        this.ready = false;
        this.lastError = e.message;
        this.state = { nets: {}, leds: {}, digits: {}, errors: [String(e.message)] };
        this.emit("state", this.state);
        this.problems = [{ severity: "error", message: `The engine could not load this project: ${e.message}`, where: "" }];
        this.emit("problems", this.problems);
      }
      this.emit("synced");
      this.kick();
    });
    return this.syncing;
  }
  // ---- the real-time clock
  isCpu() { return store.project.nets.some((n) => n.name === "HLT_n"); }
  mainPeriod() { const c = this.clocks[0]; return c && c.period_ns > 0 ? c.period_ns : null; }
  realHz() { const p = this.mainPeriod(); return p ? 1e9 / p : null; }
  defaultSpeed() {
    const saved = storageGet(`bb-speed:${store.project.name}`, null);
    if (saved != null) return saved === "Infinity" ? Infinity : saved;
    if (this.isCpu()) return 10;
    const hz = this.realHz();
    return hz && hz <= 20 ? "real" : 5;
  }
  setSpeed(v) {
    this.speed = v === "Infinity" || v === Infinity ? Infinity : v === "real" ? "real" : +v;
    storageSet(`bb-speed:${store.project.name}`, this.speed === Infinity ? "Infinity" : this.speed);
    this.emit("clock", this.clockInfo());
    this.kick();
  }
  setPaused(on) { this.paused = !!on; this.emit("clock", this.clockInfo()); this.kick(); }
  clockInfo() {
    const st = this.state || {};
    const nets = st.nets || {};
    const halted = !!(st.halted || nets.HLT_n === 0);
    return { has: this.clocks.length > 0, speed: this.speed, paused: this.paused, realHz: this.realHz(), cpu: this.isCpu(),
      halted, runMode: nets.RUNSEL == null ? true : nets.RUNSEL === 1,
      running: this.clocks.length > 0 && this.live && !this.paused && this.ready };
  }
  // is the machine doing anything when its clock ticks? PC-2 halted, or with RUN/STEP at STEP: no.
  // The 555 still runs on the bench, but its pulses do not get past the clock gate, so the
  // simulation waits instead of filling the analyser with idle time.
  idle() {
    const st = this.state || {};
    const nets = st.nets || {};
    return this.isCpu() && (st.halted || nets.HLT_n === 0 || nets.RUNSEL === 0);
  }
  kick() {
    if (this.ticking) return;
    this.ticking = true;
    this.lastTick = performance.now();
    const frame = () => new Promise((r) => (typeof document !== "undefined" && document.hidden ? setTimeout(r, 200) : requestAnimationFrame(() => r())));
    (async () => {
      while (true) {
        const go = this.ready && this.live && !this.paused && this.clocks.length > 0 && this.speed != null;
        if (!go) break;
        await frame();
        const now = performance.now();
        const dt = Math.min(0.25, (now - this.lastTick) / 1000);
        this.lastTick = now;
        if (this.idle()) { await new Promise((r) => setTimeout(r, 120)); continue; }
        try { await this.tick(dt, now); } catch (e) { console.warn("clock", e); await new Promise((r) => setTimeout(r, 500)); }
      }
      this.ticking = false;
    })();
  }
  async tick(dt, now) {
    const st = this.state || {};
    const nets = st.nets || {};
    let moved = 0;
    if (this.speed === Infinity && this.isCpu()) {
      // as fast as the engine goes: whole cycles in batches sized to redraw about every 50 ms
      const t0 = performance.now();
      const r = await this.q(async () => (this.ready ? engine.runUntil("halt", this.batch) : null));
      const took = performance.now() - t0;
      this.batch = Math.max(5, Math.min(5000, Math.round(this.batch * (50 / Math.max(took, 5)))));
      moved = r ? 1 : 0;
    } else {
      const per = this.mainPeriod() || 1e6;
      const rate = this.speed === "real" ? 1e9 : this.speed === Infinity ? 1e12 : this.speed * per;   // simulated ns per second
      const ns = dt * rate;
      if (!(ns > 0)) return;
      const r = await this.q(async () => (this.ready ? engine.runNs(ns, 4000) : null));
      moved = r ? (r.edges ?? 1) : 0;
    }
    // redraw the views when something moved, at most about 20 times a second
    if (moved && now - this.lastPaint > 45) {
      this.lastPaint = now;
      await this.refresh();
      this.emit("tick", this.clockInfo());
    }
  }

  async whenReady() { await this.syncing; await this.busy; return this.ready; }
  async _refresh() {
    this.state = await engine.state();
    this.takeSwitches(this.state.switches);
    this.emit("state", this.state);
    return this.state;
  }
  refresh() { return this.q(() => this.ready && this._refresh()); }

  // ---- operating parts
  toggle(id) { const v = !this.ctl[id]; this.ctl[id] = v; return this.setEngine(id, v); }
  setSwitch(id, v) { this.ctl[id] = !!v; return this.setEngine(id, !!v); }
  setThrow(id, pos) { this.ctl[id] = pos; return this.setEngine(id, pos); }
  setSection(id, k, v) {
    const a = this.ctl[id] || [];
    a[k - 1] = !!v;
    this.ctl[id] = a;
    return this.setEngine(`${id}.${k}`, !!v);
  }
  // set several DIP sections at once (one refresh at the end)
  // which bit of the bank's value section k (1 = leftmost) is: k-1, or n-k for a bank wired
  // most significant bit first (props msb_first, as on PC-2's front panel)
  bitOf(id, k, n) { return this.msb && this.msb[id] ? n - k : k - 1; }
  setBits(id, value, n) {
    const a = this.ctl[id] || [];
    const changes = [];
    for (let k = 1; k <= n; k++) { const b = !!((value >> this.bitOf(id, k, n)) & 1); if (!!a[k - 1] !== b) changes.push([k, b]); a[k - 1] = b; }
    this.ctl[id] = a;
    return this.q(async () => {
      if (!this.ready) return;
      for (const [k, b] of changes) await engine.set(`${id}.${k}`, b);
      await this._refresh();
    });
  }
  async press(id, holdMs = 0) {
    this.ctl[id] = true;
    await this.setEngine(id, true);
    if (holdMs) await new Promise((r) => setTimeout(r, holdMs));
    this.ctl[id] = false;
    return this.setEngine(id, false);
  }
  setEngine(id, v) {
    return this.q(async () => {
      if (!this.ready) return;
      try { await engine.set(id, v); } catch (e) { toast(`Engine: ${e.message}`); }
      await this._refresh();
    });
  }
  step(n = 1) { return this.q(async () => { if (!this.ready) return; await engine.step(n); return this._refresh(); }); }
  runUntil(cond = "halt", limit = 20000) {
    return this.q(async () => { if (!this.ready) return null; const r = await engine.runUntil(cond, limit); await this._refresh(); return r; });
  }
  async check() {
    await this.whenReady();
    return this.q(async () => {
      try { this.problems = await engine.check(); } catch (e) { this.problems = [{ severity: "error", message: e.message, where: "" }]; }
      this.emit("problems", this.problems);
      return this.problems;
    });
  }
}
export const simctl = new SimCtl();
