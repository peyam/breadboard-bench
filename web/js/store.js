// The open project, its undo history, and the netlist operations every view uses.
// The netlist ("nets") is the source of truth; the schematic and the breadboards are views of it.
import { Emitter, deep } from "./util.js";

export const FORMAT = "breadboard-bench/1";

export function emptyProject(name = "Untitled") {
  return { format: FORMAT, name, notes: "", parts: [], nets: [], schematic: { wires: [], labels: [] },
           breadboards: [], links: [], stimuli: [], probes: [] };
}

export function normalise(p) {
  p = deep(p) || emptyProject();
  p.format ||= FORMAT;
  p.name ||= "Untitled";
  p.parts ||= []; p.nets ||= []; p.links ||= []; p.stimuli ||= []; p.probes ||= []; p.breadboards ||= [];
  p.schematic ||= {}; p.schematic.wires ||= []; p.schematic.labels ||= [];
  for (const pt of p.parts) { pt.props ||= {}; pt.rot ||= 0; }
  for (const n of p.nets) n.pins = (n.pins || []).map(([a, b]) => [String(a), String(b)]);
  arrangeBoards(p);
  return p;
}

// Fallback: boards that share a place (no positions given) go into a rack, columns of up to six
// boards. PC-2's boards come from the engine already in the book's rack.
export function arrangeBoards(p) {
  const bs = p.breadboards;
  if (bs.length < 2) return;
  const key = (b) => `${Math.round((b.x || 0) / 100)},${Math.round((b.y || 0) / 100)}`;
  if (new Set(bs.map(key)).size === bs.length) return;
  const per = Math.max(3, Math.ceil(bs.length / 3));
  bs.forEach((b, i) => { b.x = Math.floor(i / per) * 700; b.y = (i % per) * 270; });
}

class Store extends Emitter {
  constructor() {
    super();
    this.project = emptyProject();
    this.undoStack = [];
    this.redoStack = [];
    this.dirty = false;
    this.rev = 0;
  }
  load(p, { keepHistory = false } = {}) {
    this.project = normalise(p);
    if (!keepHistory) { this.undoStack = []; this.redoStack = []; }
    this.dirty = false;
    this.rev++;
    this.emit("load", this.project);
    this.emit("change", { kind: "load" });
  }
  // Run a change with an undo snapshot. kind: "netlist" (engine must reload) or "view" (positions only)
  commit(label, fn, kind = "netlist") {
    const before = JSON.stringify(this.project);
    const r = fn(this.project);
    const after = JSON.stringify(this.project);
    if (before === after) return r;
    this.undoStack.push({ label, json: before, kind });
    if (this.undoStack.length > 150) this.undoStack.shift();
    this.redoStack = [];
    this.dirty = true;
    this.rev++;
    this.emit("change", { kind, label });
    return r;
  }
  undo() {
    const u = this.undoStack.pop();
    if (!u) return false;
    this.redoStack.push({ label: u.label, json: JSON.stringify(this.project), kind: u.kind });
    this.project = JSON.parse(u.json);
    this.rev++;
    this.dirty = true;
    this.emit("change", { kind: u.kind === "view" ? "view" : "netlist", label: "undo " + u.label, undo: true });
    return u.label;
  }
  redo() {
    const r = this.redoStack.pop();
    if (!r) return false;
    this.undoStack.push({ label: r.label, json: JSON.stringify(this.project), kind: r.kind });
    this.project = JSON.parse(r.json);
    this.rev++;
    this.dirty = true;
    this.emit("change", { kind: r.kind === "view" ? "view" : "netlist", label: "redo " + r.label, undo: true });
    return r.label;
  }
}
export const store = new Store();

// ------------------------------------------------------------------------------ netlist helpers
export const pkey = (id, pin) => `${id}.${pin}`;

export function pinNetIndex(p) {
  const m = new Map();
  for (const n of p.nets) for (const [id, pin] of n.pins) m.set(pkey(id, pin), n.name);
  return m;
}
export function netByName(p, name) { return p.nets.find((n) => n.name === name); }
export function partById(p, id) { return p.parts.find((x) => x.id === id); }

export function autoNetName(p, base = "N") {
  const used = new Set(p.nets.map((n) => n.name));
  for (let i = 1; ; i++) if (!used.has(base + i)) return base + i;
}
export const isAutoName = (n) => /^N\d+$/.test(n);

export function newPartId(p, prefix) {
  const used = new Set(p.parts.map((x) => x.id));
  for (let i = 1; ; i++) if (!used.has(prefix + i)) return prefix + i;
}

export function detachPin(p, id, pin) {
  for (const n of p.nets) n.pins = n.pins.filter(([a, b]) => !(a === id && b === String(pin)));
  pruneNets(p);
}

export function attachPin(p, id, pin, netName) {
  pin = String(pin);
  const cur = pinNetIndex(p).get(pkey(id, pin));
  if (cur === netName) return;
  if (cur) mergeNets(p, netName, cur);
  else {
    let n = netByName(p, netName);
    if (!n) { n = { name: netName, pins: [] }; p.nets.push(n); }
    n.pins.push([id, pin]);
  }
}

// Join two nets: keep the "better" name (a named net wins over an automatic one, rails win over all)
export function mergeNets(p, a, b) {
  if (a === b) return a;
  const rank = (x) => (x === "VCC" || x === "GND" ? 3 : isAutoName(x) ? 1 : 2);
  let keep = a, drop = b;
  if (rank(b) > rank(a)) { keep = b; drop = a; }
  const nk = netByName(p, keep), nd = netByName(p, drop);
  if (!nd) return keep;
  if (!nk) { nd.name = keep; return keep; }
  for (const pin of nd.pins) if (!nk.pins.some(([x, y]) => x === pin[0] && y === pin[1])) nk.pins.push(pin);
  p.nets = p.nets.filter((n) => n !== nd);
  renameRefs(p, drop, keep);
  return keep;
}

export function connectPins(p, a, b) {
  const idx = pinNetIndex(p);
  const na = idx.get(pkey(...a)), nb = idx.get(pkey(...b));
  if (na && nb) return mergeNets(p, na, nb);
  const name = na || nb || autoNetName(p);
  attachPin(p, a[0], a[1], name);
  attachPin(p, b[0], b[1], name);
  return name;
}

function renameRefs(p, from, to) {
  for (const w of p.schematic.wires) if (w.net === from) w.net = to;
  for (const l of p.schematic.labels) if (l.net === from) l.net = to;
  p.probes = [...new Set(p.probes.map((x) => (x === from ? to : x)))];
  for (const bb of p.breadboards) for (const w of bb.wires || []) if (w.net === from) w.net = to;
}

export function renameNet(p, from, to) {
  to = to.trim();
  if (!to || from === to) return false;
  if (netByName(p, to)) { mergeNets(p, to, from); return true; }
  const n = netByName(p, from);
  if (n) n.name = to;
  renameRefs(p, from, to);
  return true;
}

export function pruneNets(p) {
  const labelled = new Set(p.schematic.labels.map((l) => l.net));
  p.nets = p.nets.filter((n) => n.pins.length > 1 || labelled.has(n.name) || n.name === "VCC" || n.name === "GND" ||
                                (n.pins.length === 1 && !isAutoName(n.name)));
  // remove empty rails unless used
  p.nets = p.nets.filter((n) => n.pins.length > 0 || labelled.has(n.name));
}

export function deletePart(p, id) {
  p.parts = p.parts.filter((x) => x.id !== id);
  for (const n of p.nets) n.pins = n.pins.filter(([a]) => a !== id);
  p.schematic.wires = p.schematic.wires.filter((w) => !(w.a && w.a[0] === id) && !(w.b && w.b[0] === id));
  for (const bb of p.breadboards) bb.placements = (bb.placements || []).filter((pl) => pl.part !== id);
  p.stimuli = p.stimuli.filter((s) => s.part !== id);
  pruneNets(p);
}

// A wire is removed: the pins it joined may come apart.
export function deleteWire(p, w) {
  p.schematic.wires = p.schematic.wires.filter((x) => x !== w);
  if (!w.a || !w.b) return;
  const net = netByName(p, w.net);
  if (!net) return;
  const wires = p.schematic.wires.filter((x) => x.net === w.net && x.a && x.b);
  const touches = (pin) => wires.some((x) => (x.a[0] === pin[0] && x.a[1] === pin[1]) || (x.b[0] === pin[0] && x.b[1] === pin[1]));
  const hasLabel = (pin) => (pin && p.schematic.labels.some((l) => l.net === w.net && l.pin && l.pin[0] === pin[0] && l.pin[1] === pin[1]));
  // the end left with no other wire and no label of its own leaves the net
  for (const end of [w.b, w.a]) {
    if (!touches(end) && !hasLabel(end)) {
      net.pins = net.pins.filter(([a, b]) => !(a === end[0] && b === String(end[1])));
      break;
    }
  }
  pruneNets(p);
}
