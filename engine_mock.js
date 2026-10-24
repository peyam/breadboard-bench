// Demo engine: a small stand-in for the Python engine (bbench) with the same interface and the same
// data shapes (DESIGN §2.6). The app uses it until Python has loaded, or when no bbench wheel is found.
// It simulates basic gates, switches, buttons, LEDs, pull resistors and clock sources, and runs PC-2
// at the microcode level. The real engine does all of this pin by pin with datasheet timing.
import { checkBreadboards } from "./js/bbgeom.js";
import { controlWord, active, SIGNALS, displayText, SEG } from "./js/pc2asm.js";
import { getDef, PASSIVES, pinNo, baseType, positions } from "./js/parts.js";
import { parseValue } from "./js/util.js";

const GATES = { "00": (a, b) => 1 - (a & b), "08": (a, b) => a & b, "32": (a, b) => a | b, "86": (a, b) => a ^ b, "02": (a, b) => 1 - (a | b) };
const TPD = { "00": 15, "08": 15, "32": 15, "86": 16, "02": 15, "04": 13 };
const RAIL = { VCC: 1, GND: 0 };
const num = (t) => (String(t).match(/^74[A-Z]*(\d+)$/) || [])[1];

export class MockEngine {
  constructor() { this.name = "demo engine"; this.p = null; this.sim = null; this._lib = null; }
  async library() {
    if (!this._lib) {
      const chips = await (await fetch(new URL("./mock/chips.json", import.meta.url))).json();
      this._lib = [...chips, ...PASSIVES.filter((p) => !chips.some((c) => c.type === p.type))];
    }
    return this._lib;
  }
  async examples() { return [{ id: "pc2", name: "PC-2: the whole computer", group: "PC-2" }]; }
  async example(id) {
    if (id === "pc2") return (await fetch(new URL("./mock/pc2.bbproj", import.meta.url))).json();
    throw new Error(`no example ${id}`);
  }
  async loadProject(json) {
    this.p = typeof json === "string" ? JSON.parse(json) : JSON.parse(JSON.stringify(json));
    this.sim = null;
    return { name: this.p.name, parts: this.p.parts.length, nets: this.p.nets.length };
  }
  isPC2() { return this.p && this.p.parts.some((x) => x.id === "U42") && this.p.parts.some((x) => x.id === "U24"); }
  async check() {
    if (!this.p) return [];
    const out = [];
    const idx = new Map();
    for (const n of this.p.nets) for (const [a, b] of n.pins) idx.set(`${a}.${b}`, n.name);
    for (const part of this.p.parts) {
      const d = getDef(part.type);
      if (!d || d.kind !== "chip") continue;
      for (const [n, name, kind] of d.pins) {
        if ((kind === "in" || kind === "clk") && !idx.has(`${part.id}.${n}`))
          out.push({ severity: "warning", message: `${part.id} pin ${n} (${name}) is not connected: an open input floats.`, where: `${part.id}.${n}` });
      }
    }
    for (const n of this.p.nets) if (n.pins.length === 1 && n.name !== "VCC" && n.name !== "GND")
      out.push({ severity: "info", message: `${n.name} goes to only one pin (${n.pins[0].join(" pin ")}).`, where: `net:${n.name}` });
    out.push(...checkBreadboards(this.p, getDef));
    return out;
  }
  async newSim(mode = "zero") {
    if (!this.p) throw new Error("no project loaded");
    this.sim = this.isPC2() ? new PC2Mock(this.p) : new GateMock(this.p, mode);
    return { mode, kind: this.sim.kind };
  }
  need() { if (!this.sim) throw new Error("no simulator: call newSim first"); return this.sim; }
  async set(id, value) { this.need().set(id, value); return null; }
  async step(n = 1) { this.need().step(n); return null; }
  async runUntil(cond = "halt", limit = 20000) { return this.need().runUntil(cond, limit); }
  async runNs(ns) { return this.need().runNs(ns); }
  async clocks() { return this.need().clockList(); }
  // the analyser's timed run, in a simulator of its own; the demo engine starts it from power-up
  // with the live switches (the Python engine starts from the live state, RAM included)
  async timedRun(ns, nets) {
    const live = this.need();
    const T = this.isPC2() ? new PC2Mock(this.p) : new GateMock(this.p, "timed");
    for (const [id, v] of Object.entries(live.state().switches || {})) {
      if (Array.isArray(v)) v.forEach((b, k) => { if (b) T.set(`${id}.${k + 1}`, true); });
      else if (v !== false) T.set(id, v);
    }
    T.runNs(ns);
    const tr = T.trace(nets);
    tr.t_end = ns;
    return { trace: tr, errors: [], from: "power-up" };
  }
  async state() { return this.need().state(); }
  async trace(nets) { return this.need().trace(nets); }
  async runPython() { return { ok: false, out: "", err: "Python is not available in the demo engine." }; }
}

// ------------------------------------------------------------------ small circuits
class GateMock {
  constructor(p, mode) {
    this.kind = "gates";
    this.mode = mode;
    this.p = p;
    this.t = 0;
    this.errors = [];
    this.ctl = {};                          // part id -> closed / throw / [sections]
    this.netOf = new Map();
    for (const n of p.nets) for (const [a, b] of n.pins) this.netOf.set(`${a}.${b}`, n.name);
    this.nets = [...new Set([...p.nets.map((n) => n.name), "VCC", "GND"])];
    this.parts = p.parts.map((x) => ({ ...x, type: baseType(x.type), def: getDef(x.type), props: { ...((getDef(x.type) || {}).props || {}), ...(x.props || {}) } }));
    this.out = new Map();                   // "U1.3" -> value driven by a chip output or clock
    this.clocks = [];
    for (const x of this.parts) {
      if (x.type === "CLOCK") this.clocks.push({ id: x.id, pin: pinNo(x.def, "OUT"), period: +(x.props.period_ns || 1000), duty: 0.5 });
      if (/555$/.test(x.type)) this.clocks.push(this.astable(x));
      if (x.type === "SPDT" || x.type === "JUMPER3") { const pos = positions(x); this.ctl[x.id] = typeof x.props.pos === "string" ? x.props.pos : pos[x.props.pos || 0]; }
      if (/^DIPSW/.test(x.type)) { const n = +x.type.slice(5), c = x.props.closed || 0; this.ctl[x.id] = Array.from({ length: n }, (_, k) => (Array.isArray(c) ? !!c[k] : !!((c >> k) & 1))); }
      if (x.type === "SW") this.ctl[x.id] = !!x.props.closed;
    }
    for (const st of p.stimuli || []) {
      const c = this.clocks.find((k) => k.id === st.part);
      if (c) { c.period = st.period_ns || c.period; c.duty = st.duty ?? c.duty; }
    }
    for (const c of this.clocks) this.out.set(`${c.id}.${c.pin}`, 0);
    this.v = {};
    this.hist = {};
    this.settle(true);
  }
  astable(x) {
    // f = 1.44 / ((R1 + 2 R2) C): find the resistors and capacitor around the 555
    const pinNet = (pn) => this.netOf.get(`${x.id}.${x.def.pins.find((q) => q[1] === pn)?.[0]}`);
    const dis = pinNet("DIS"), thr = pinNet("THR");
    const rs = this.parts.filter((q) => q.type === "R"), cs = this.parts.filter((q) => q.type === "C");
    const nets2 = (q) => [this.netOf.get(`${q.id}.1`), this.netOf.get(`${q.id}.2`)];
    const r1 = rs.find((q) => nets2(q).includes("VCC") && nets2(q).includes(dis));
    const r2 = rs.find((q) => nets2(q).includes(dis) && nets2(q).includes(thr));
    const c = cs.find((q) => nets2(q).includes(thr) && nets2(q).includes("GND"));
    const R1 = r1 ? parseValue(r1.props.value) : 1e3, R2 = r2 ? parseValue(r2.props.value) : 10e3, C = c ? parseValue(c.props.value) : 100e-9;
    const hi = 0.693 * (R1 + R2) * C, lo = 0.693 * R2 * C;
    return { id: x.id, pin: x.def.pins.find((q) => q[1] === "OUT")[0], period: (hi + lo) * 1e9, duty: hi / (hi + lo) };
  }
  set(id, value) {
    const [pid, sec] = String(id).split(".");
    const part = this.parts.find((x) => x.id === pid);
    if (!part) throw new Error(`no part ${pid}`);
    if (sec) { const a = this.ctl[pid] || []; a[+sec - 1] = !!value; this.ctl[pid] = a; }
    else if (/^DIPSW/.test(part.type) && typeof value === "number") this.ctl[pid] = this.ctl[pid].map((_, k) => !!((value >> k) & 1));
    else this.ctl[pid] = part.type === "SPDT" || part.type === "JUMPER3" ? String(value) : !!value;
    this.settle();
  }
  // which pairs of nets are joined by a closed contact, and which by a resistor
  links() {
    const strong = [], weak = [];
    for (const x of this.parts) {
      const n = (pin) => this.netOf.get(`${x.id}.${pinNo(x.def, pin)}`);
      const c = this.ctl[x.id];
      if (x.type === "SW" && c) strong.push([n("1"), n("2")]);
      if (x.type === "BUTTON") { strong.push([n("1A"), n("1B")], [n("2A"), n("2B")]); if (c) strong.push([n("1A"), n("2A")]); }
      if (x.type === "SPDT" || x.type === "JUMPER3") { const pos = positions(x); strong.push([n("COM"), n(String(c).toUpperCase() === String(pos[1]).toUpperCase() ? "B" : "A")]); }
      if (/^DIPSW/.test(x.type)) (c || []).forEach((on, k) => on && strong.push([n(`${k + 1}A`), n(`${k + 1}B`)]));
      if (x.type === "R") weak.push([n("1"), n("2")]);
      if (/^RN\d*$/.test(x.type)) for (const [, nm] of x.def.pins) if (nm !== "COM") weak.push([n("COM"), n(nm)]);
    }
    return { strong: strong.filter(([a, b]) => a && b), weak: weak.filter(([a, b]) => a && b) };
  }
  resolve() {
    const parent = {};
    const find = (a) => { while (parent[a] && parent[a] !== a) a = parent[a]; return a; };
    const { strong, weak } = this.links();
    for (const [a, b] of strong) { const ra = find(a), rb = find(b); if (ra !== rb) parent[ra] = rb; }
    const drv = {};
    const add = (net, v, who) => { const r = find(net); (drv[r] ||= []).push([v, who]); };
    for (const [k, v] of Object.entries(RAIL)) add(k, v, k);
    for (const [k, v] of this.out) { const net = this.netOf.get(k); if (net && v !== "Z") add(net, v, k); }
    const val = {};
    this.contention = [];
    for (const [r, list] of Object.entries(drv)) {
      const vs = new Set(list.map((x) => x[0]));
      val[r] = vs.size === 1 ? [...vs][0] : "X";
      if (vs.size > 1) this.contention.push(list.map((x) => x[1]).join(" and "));
    }
    // weak pulls through resistors, from driven groups to undriven ones
    for (let it = 0; it < 8; it++) {
      let ch = false;
      for (const [a, b] of weak) {
        const ra = find(a), rb = find(b);
        if (val[ra] === undefined && val[rb] !== undefined && drv[rb]) { val[ra] = val[rb]; ch = true; }
        else if (val[rb] === undefined && val[ra] !== undefined && drv[ra]) { val[rb] = val[ra]; ch = true; }
      }
      if (!ch) break;
    }
    const v = {};
    for (const net of this.nets) v[net] = val[find(net)] ?? "Z";
    return v;
  }
  evalChips(v) {
    const next = new Map();
    const floating = [];
    for (const x of this.parts) {
      const nn = num(x.type);
      if (!x.def || x.def.kind !== "chip" || (!GATES[nn] && nn !== "04")) continue;
      const pinOf = Object.fromEntries(x.def.pins.map((q) => [q[1], q[0]]));
      const get = (name) => { const net = this.netOf.get(`${x.id}.${pinOf[name]}`); const r = net ? v[net] : "Z"; if (r === "Z") floating.push(`${x.id} ${name}`); return r; };
      const groups = nn === "04" ? 6 : 4;
      for (let g = 1; g <= groups; g++) {
        let r;
        if (!this.netOf.has(`${x.id}.${pinOf[g + "Y"]}`)) continue;
        if (nn === "04") { const a = get(g + "A"); r = a === 0 || a === 1 ? 1 - a : "X"; }
        else { const a = get(g + "A"), b = get(g + "B"); r = (a === 0 || a === 1) && (b === 0 || b === 1) ? GATES[nn](a, b) : "X"; }
        const tp = (x.def.tpd || []).find((q) => q[0] === "*");
        next.set(`${x.id}.${pinOf[g + "Y"]}`, { v: r, tpd: (tp && tp[2]) || TPD[nn] || 15 });
      }
    }
    return { next, floating };
  }
  settle(first = false) {
    let v;
    for (let it = 0; it < 60; it++) {
      v = this.resolve();
      const { next, floating } = this.evalChips(v);
      this.floating = floating;
      let ch = false;
      for (const [k, o] of next) if (this.out.get(k) !== o.v) { this.out.set(k, o.v); ch = true; }
      if (!ch) break;
      if (it === 59) this.errors.push("oscillation: the circuit never settles");
    }
    this.record(v, first);
    return v;
  }
  record(v, first) {
    for (const [k, x] of Object.entries(v)) {
      const h = (this.hist[k] ||= []);
      if (first || !h.length || h[h.length - 1][1] !== x) h.push([this.t, x]);
    }
    this.v = v;
  }
  clockPeriod() { return this.clocks.length ? this.clocks[0].period : 1000; }
  clockList() { return this.clocks.map((c) => ({ part: c.id, period_ns: c.period, duty: c.duty, role: "clock" })); }
  step(n = 1) {
    const P = this.clockPeriod();
    this.cycles = (this.cycles || 0) + n;
    for (let i = 0; i < n; i++) {
      for (const c of this.clocks) this.out.set(`${c.id}.${c.pin}`, 1);
      this.settle();
      this.t += P / 2;
      for (const c of this.clocks) this.out.set(`${c.id}.${c.pin}`, 0);
      this.settle();
      this.t += P / 2;
    }
  }
  runUntil(cond, limit) { this.step(Math.min(limit, 1000)); return { cycles: Math.min(limit, 1000), halted: false }; }
  // timed: discrete events with each gate's propagation delay (inertial)
  runNs(ns) {
    const end = this.t + ns;
    const q = [];
    const pending = new Map();
    let edges = 0;
    for (const c of this.clocks) {
      const cur = this.out.get(`${c.id}.${c.pin}`) || 0;
      // each clock keeps its phase from one call to the next (short real-time slices add up)
      let t = c.next != null && c.next >= this.t && c.lvl === cur ? c.next : this.t + (cur ? c.period * c.duty : c.period * (1 - c.duty));
      let lvl = 1 - cur;
      while (t <= end) {
        q.push({ t, k: `${c.id}.${c.pin}`, v: lvl });
        edges++;
        if (lvl && c === this.clocks[0]) this.cycles = (this.cycles || 0) + 1;
        t += lvl ? c.period * c.duty : c.period * (1 - c.duty); lvl = 1 - lvl;
      }
      c.next = t; c.lvl = 1 - lvl;
    }
    q.sort((a, b) => a.t - b.t);
    let guard = 0;
    while (q.length && guard++ < 200000) {
      const e = q.shift();
      if (e.t > end) break;
      if (e.gen !== undefined && pending.get(e.k) !== e.gen) continue;
      this.t = e.t;
      if (this.out.get(e.k) === e.v) continue;
      this.out.set(e.k, e.v);
      const v = this.resolve();
      this.record(v);
      const { next } = this.evalChips(v);
      for (const [k, o] of next) {
        const gen = (pending.get(k) || 0) + 1;
        pending.set(k, gen);
        const ev = { t: this.t + o.tpd, k, v: o.v, gen };
        let i = q.findIndex((x) => x.t > ev.t);
        if (i < 0) i = q.length;
        q.splice(i, 0, ev);
      }
    }
    this.t = end;
    return { t_ns: this.t, edges, done: true };
  }
  state() {
    const leds = {};
    for (const x of this.parts) {
      if (x.type !== "LED") continue;
      const a = this.netOf.get(`${x.id}.${pinNo(x.def, "A")}`), k = this.netOf.get(`${x.id}.${pinNo(x.def, "K")}`);
      // an LED lights when its anode side is pulled high through its resistor and its cathode is low
      const av = a ? this.v[a] : "Z", kv = k ? this.v[k] : "Z";
      leds[x.id] = av === 1 && kv === 0;
    }
    const errs = [...this.errors];
    for (const f of this.floating || []) errs.push(`floating input: ${f}`);
    for (const c of this.contention || []) errs.push(`contention: ${c}`);
    const probes = {};
    for (const x of this.parts) if (x.type === "PROBE") { const net = this.netOf.get(`${x.id}.${pinNo(x.def, "TIP")}`); probes[x.id] = net ? this.v[net] : "Z"; }
    return { mode: this.mode, nets: { ...this.v }, leds, digits: {}, probes, switches: { ...this.ctl }, errors: errs, t_ns: this.t, cycles: this.cycles || 0 };
  }
  trace(nets) {
    return { t_unit: "ns", t_end: this.t, signals: nets.map((n) => ({ name: n, changes: (this.hist[n] || []).map(([t, v]) => [t, v]) })) };
  }
}

// ------------------------------------------------------------------ PC-2 at the microcode level
class PC2Mock {
  constructor(p) {
    this.kind = "pc2";
    this.p = p;
    this.byLabel = {};
    for (const x of p.parts) if (x.props && x.props.label) this.byLabel[x.props.label] = x.id;
    this.ids = {};
    for (const x of p.parts) if (/^DIPSW/.test(x.type)) {
      const lab = (x.props.labels || [])[0] || "";
      const which = /address/.test(lab) ? "asw" : /data/.test(lab) ? "dsw" : /input A/.test(lab) ? "ina" : /input B/.test(lab) ? "inb" : null;
      if (which) this.ids[x.id] = which;
    }
    this.sw = { asw: 0, dsw: 0, ina: 0, inb: 0 };
    this.runstep = "STEP"; this.progrun = "RUN";
    this.mem = Array(16).fill(0);
    this.reset();
    this.out = 0; this.mode = 0; this.cycles = 0; this.t = 0; this.hist = {}; this.halted = false;
    this.record(true);
  }
  reset() { this.a = this.b = this.ir = this.mar = this.pc = 0; this.c = this.z = 0; this.stepn = 0; this.halted = false; }
  set(id, value) {
    const [pid, sec] = String(id).split(".");
    if (this.ids[pid] && sec) {
      const bit = +sec - 1, key = this.ids[pid];
      this.sw[key] = value ? this.sw[key] | (1 << bit) : this.sw[key] & ~(1 << bit);
    } else {
      const part = this.p.parts.find((x) => x.id === pid);
      const lab = part && part.props.label;
      if (lab === "RUN / STEP") this.runstep = String(value);
      else if (lab === "PROGRAM / RUN") this.progrun = String(value);
      else if (lab === "RESET" && value) { this.reset(); this.clk = 0; }
      else if (lab === "WRITE" && value && this.progrun === "PROG") this.mem[this.sw.asw & 15] = this.sw.dsw & 255;
      else if (lab === "STEP" && value && this.runstep === "STEP") this.cycle();
    }
    this.record();
  }
  word() { return controlWord(this.ir >> 4, this.stepn, this.c, this.z); }
  alu(su) { const b = su ? this.b ^ 0xff : this.b; const s = this.a + b + (su ? 1 : 0); return [s & 255, s > 255 ? 1 : 0, (s & 255) === 0 ? 1 : 0]; }
  bus() {
    const on = new Set(active(this.word()));
    const [e] = this.alu(on.has("SU"));
    if (on.has("RO")) return this.mem[this.mar];
    if (on.has("IO")) return this.ir & 15;
    if (on.has("AO")) return this.a;
    if (on.has("EO")) return e;
    if (on.has("CO")) return this.pc;
    if (on.has("XO")) return this.ir & 1 ? this.sw.inb : this.sw.ina;
    return 0;
  }
  cycle() {
    if (this.halted || this.progrun === "PROG") return;
    const on = new Set(active(this.word()));
    const [, ec, ez] = this.alu(on.has("SU"));
    const bus = this.bus();
    this.t += 500; this.clk = 1; this.record(); this.clk = 0;
    if (on.has("HLT")) this.halted = true;
    if (on.has("MI")) this.mar = bus & 15;
    if (on.has("RI")) this.mem[this.mar] = bus;
    if (on.has("II")) this.ir = bus;
    if (on.has("AI")) this.a = bus;
    if (on.has("BI")) this.b = bus;
    if (on.has("OI")) { this.out = bus; this.mode = this.ir & 3; }
    if (on.has("FI")) { this.c = ec; this.z = ez; }
    if (on.has("J")) this.pc = bus & 15;
    if (on.has("CE")) this.pc = (this.pc + 1) & 15;
    this.stepn = on.has("SR") ? 0 : this.stepn + 1;
    this.cycles++;
    this.t += 500;
    this.record();
  }
  // the run clock only reaches the machine with RUN/STEP at RUN (STEP mode: the STEP button)
  step(n = 1) { for (let i = 0; i < n && !this.halted && this.runstep === "RUN"; i++) this.cycle(); }
  clockList() { return [{ part: "U1", period_ns: 1000, duty: 0.5, role: "main" }]; }
  runUntil(cond, limit) {
    let k = 0;
    while (!this.halted && this.runstep === "RUN" && k < limit) { this.cycle(); k++; }
    return { cycles: k, halted: this.halted, done: this.halted };
  }
  runNs(ns) {
    this.acc = (this.acc || 0) + ns / 1000;
    const n = Math.floor(this.acc);
    this.acc -= n;
    const before = this.cycles;
    this.step(n);
    return { t_ns: this.t, edges: 2 * (this.cycles - before), cycles: this.cycles, done: true };
  }
  nets() {
    const n = {};
    const bits = (name, v, w) => { for (let k = 0; k < w; k++) n[`${name}${k}`] = (v >> k) & 1; };
    const word = this.word();
    const on = new Set(active(word));
    const [e] = this.alu(on.has("SU"));
    const prog = this.progrun === "PROG";
    bits("BUS", prog ? 0 : this.bus(), 8); bits("A", this.a, 8); bits("B", this.b, 8); bits("E", e, 8);
    bits("PC", this.pc, 4); bits("MAR", this.mar, 4);
    const ra = prog ? this.sw.asw & 15 : this.mar;
    bits("RA", ra, 4); bits("RD", this.mem[ra], 8);
    bits("IRL", this.ir & 15, 4); bits("OP", this.ir >> 4, 4); bits("OUT", this.out, 8);
    bits("MODE", this.mode, 2); bits("STEP", this.stepn, 3);
    for (let k = 0; k < 8; k++) n[`STEPY${k}_n`] = this.stepn === k ? 0 : 1;
    for (const s of SIGNALS) n[`${s}_n`] = on.has(s) && !prog ? 0 : 1;
    n.SU = on.has("SU") ? 1 : 0; n.CE = on.has("CE") ? 1 : 0;
    n.FC = this.c; n.FZ = this.z; n.CLK = this.clk || 0; n.PROG = prog ? 1 : 0; n.RUNSEL = this.runstep === "RUN" ? 1 : 0;
    n.HLT_n = this.halted ? 0 : 1;
    bits("INA", this.sw.ina, 8); bits("INB", this.sw.inb, 8); bits("ASW", this.sw.asw, 4); bits("DSW", this.sw.dsw, 8);
    return n;
  }
  record(first) {
    const v = this.nets();
    for (const [k, x] of Object.entries(v)) {
      const h = (this.hist[k] ||= []);
      if (first || !h.length || h[h.length - 1][1] !== x) h.push([this.t, x]);
    }
    this.v = v;
  }
  state() {
    const nets = this.nets();
    const leds = {}, digits = {};
    const netOf = new Map();
    for (const n of this.p.nets) for (const [a, b] of n.pins) netOf.set(`${a}.${b}`, n.name);
    for (const x of this.p.parts) {
      if (x.type === "LED") {
        const a = netOf.get(`${x.id}.1`) || "", k = netOf.get(`${x.id}.2`) || "";
        const base = a.replace(/~LED$/, "");
        leds[x.id] = k === "GND" ? nets[base] === 1 : nets[k] === 0;
      }
      if (/^7SEG/.test(x.type)) {
        const m = /digit (\d)/.exec(x.props.label || "");
        if (m) { const t = displayText(this.out, this.mode); digits[x.id] = SEG[t[3 - +m[1]]] ?? 0; }
      }
    }
    const switches = {};
    for (const x of this.p.parts) {
      const lab = x.props && x.props.label;
      if (lab === "RUN / STEP") switches[x.id] = this.runstep;
      if (lab === "PROGRAM / RUN") switches[x.id] = this.progrun;
      if (this.ids[x.id]) { const v = this.sw[this.ids[x.id]], n = +x.type.slice(5); switches[x.id] = Array.from({ length: n }, (_, k) => (v >> k) & 1); }
    }
    return { mode: "zero", nets, leds, digits, switches, errors: [], cycles: this.cycles, halted: this.halted, t_ns: this.t };
  }
  trace(nets) {
    return { t_unit: "ns", t_end: this.t, signals: nets.map((n) => ({ name: n, changes: (this.hist[n] || []).map(([t, v]) => [t, v]) })) };
  }
}
