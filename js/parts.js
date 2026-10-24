// Part types (from the engine's library, plus the passives) and their schematic symbols.
// Symbols are drawn fresh in the book's style: white chip boxes with pin numbers and names,
// distinctive gate shapes, zig-zag resistors, LEDs with halo and rays when lit.
import { s } from "./util.js";
import { LED_HEX } from "./signals.js";

export const GRID = 10;
let LIB = new Map();

// Passives and I/O parts, used only when the engine's library() does not list them. Pins are
// numbered as in the engine (an LED is 1 = A, 2 = K) and the symbols find them by name.
const P = (spec) => spec.split(" ").map((x) => { const [n, nm, k] = x.split(":"); return [+n, nm, k || "pas"]; });
const dipPins = (n) => [...Array.from({ length: n }, (_, k) => [k + 1, `${k + 1}A`, "pas"]), ...Array.from({ length: n }, (_, k) => [n + k + 1, `${n - k}B`, "pas"])];
export const PASSIVES = [
  { type: "R", desc: "Resistor", category: "passive", defaults: { value: "10k" }, pins: P("1:1 2:2") },
  { type: "C", desc: "Capacitor", category: "passive", defaults: { value: "100nF" }, pins: P("1:1 2:2") },
  { type: "LED", desc: "Light-emitting diode", category: "indicator", defaults: { colour: "red" }, pins: P("1:A 2:K") },
  { type: "SW", desc: "On/off switch", category: "switch", defaults: { closed: false }, pins: P("1:1 2:2") },
  { type: "BUTTON", desc: "Push button (momentary)", category: "switch", defaults: {}, pins: P("1:1A 2:1B 3:2A 4:2B") },
  { type: "SPDT", desc: "Changeover slide switch (SPDT)", category: "switch", defaults: { positions: ["A", "B"], pos: 0 }, pins: P("1:A 2:COM 3:B") },
  { type: "DIPSW4", desc: "DIP switch, 4 positions", category: "switch", defaults: {}, pins: dipPins(4) },
  { type: "DIPSW8", desc: "DIP switch, 8 positions", category: "switch", defaults: {}, pins: dipPins(8) },
  { type: "RN8", desc: "Bussed resistor network, 8 resistors (SIP-9)", category: "passive", defaults: { value: "10k" }, pins: [[1, "COM", "pas"], ...Array.from({ length: 8 }, (_, k) => [k + 2, `R${k + 1}`, "pas"])] },
  { type: "7SEG-CA", desc: "7-segment digit, common anode", category: "indicator", defaults: {}, pins: P("1:e 2:d 3:CA 4:c 5:dp 6:b 7:a 8:CA2 9:f 10:g") },
  { type: "CLOCK", desc: "Clock source (square wave)", category: "active", defaults: { period_ns: 1000000 }, pins: P("1:OUT:out 2:GND:gnd") },
  { type: "PROBE", desc: "Logic probe", category: "indicator", defaults: {}, pins: P("1:TIP") },
].map((e) => ({ ...e, family: "part" }));
const PREFIX = { R: "R", C: "C", LED: "D", SW: "S", BUTTON: "BTN", SPDT: "SW", JUMPER3: "JP", POT: "VR", PNP: "Q", NPN: "Q", CLOCK: "CLK", PROBE: "P", POWER: "PWR" };
const ALIAS = { BTN: "BUTTON", "7SEG": "7SEG-CA", JP: "JUMPER3", JP3: "JUMPER3", VR: "POT", RES: "R", CAP: "C", SPST: "SW", "DIGIT-CA": "7SEG-CA", "DIGIT-CC": "7SEG-CC" };

export function setLibrary(list) {
  LIB = new Map();
  for (const e of list || []) LIB.set(e.type, { ...e, kind: kindOf(e), props: e.defaults || e.props || {} });
  for (const p of PASSIVES) if (!LIB.has(p.type)) LIB.set(p.type, { ...p, kind: "part", props: p.defaults });
  return LIB;
}
function kindOf(e) {
  if (e.category) return e.category === "chip" ? "chip" : "part";
  return ["part", "passive", "io", "parts"].includes(String(e.family || "").toLowerCase()) ? "part" : "chip";
}
export const library = () => [...LIB.values()];
export function getDef(type) {
  if (LIB.has(type)) return LIB.get(type);
  if (ALIAS[type] && LIB.has(ALIAS[type])) return LIB.get(ALIAS[type]);
  // tolerate 74HC/74HCT/74LS spellings of the same chip
  const m = String(type).match(/^74([A-Z]*)(\d+)$/);
  if (m) for (const fam of ["HCT", "HC", "LS", ""]) { const t = `74${fam}${m[2]}`; if (LIB.has(t)) return LIB.get(t); }
  if (/^DIPSW(\d+)$/.test(type)) { const n = +type.slice(5); return { type, desc: `DIP switch, ${n} positions`, family: "part", kind: "part", props: {}, pins: dipPins(n) }; }
  return null;
}
export const baseType = (type) => (getDef(type) || { type }).type;
// pin number (as a string) of a pin given by number or by name
export function pinNo(def, x) {
  if (!def) return String(x);
  const s2 = String(x);
  if (def.pins.some((p) => String(p[0]) === s2)) return s2;
  const q = def.pins.find((p) => String(p[1]) === s2);
  return q ? String(q[0]) : s2;
}
export function pinList(part) {
  const d = getDef(part.type);
  return d ? d.pins.map(([n, name, kind]) => ({ pin: String(n), name: String(name), kind })) : [];
}
export function prefixFor(type) {
  const d = getDef(type);
  const t = d ? d.type : type;
  if (PREFIX[t]) return PREFIX[t];
  if (/^DIPSW/.test(t)) return "S";
  if (/^RN/.test(t)) return "RN";
  if (/^7SEG/.test(t)) return "DS";
  return d && d.kind === "chip" ? "U" : "X";
}
export function positions(part) {
  const d = getDef(part.type);
  return (part.props && part.props.positions) || (d && d.props && d.props.positions) || ["A", "B"];
}

// ------------------------------------------------------------------------------- geometry
export function rotPt(x, y, rot) {
  switch (((rot % 360) + 360) % 360) {
    case 90: return [-y, x];
    case 180: return [-x, -y];
    case 270: return [y, -x];
    default: return [x, y];
  }
}

const symCache = new Map();
// Symbol for a part: {w, h, x0, y0, pins: [{pin, name, kind, x, y, sx, sy, side}], body(ctx) -> <g>}
export function symbol(part) {
  const key = part.type + "|" + positions(part).join(",");
  if (symCache.has(key)) return symCache.get(key);
  const def = getDef(part.type);
  let sym;
  const t = def ? def.type : part.type;
  if (!def) sym = boxSymbol(part, [{ pin: "?", name: "?", kind: "in" }]);
  else if (def.kind === "chip") {
    const g = gateKind(def);
    sym = g ? gateChipSymbol(def, g) : chipSymbol(def);
  } else if (t === "R") sym = resistorSymbol(def);
  else if (t === "C") sym = capSymbol(def);
  else if (t === "LED") sym = ledSymbol(def);
  else if (t === "SW") sym = switchSymbol(def, false);
  else if (t === "BUTTON") sym = buttonSymbol(def);
  else if (t === "SPDT" || t === "JUMPER3") sym = spdtSymbol(def, part);
  else if (/^DIPSW\d+$/.test(t)) sym = dipSymbol(def, +t.slice(5));
  else if (/^7SEG/.test(t)) sym = segSymbol(def);
  else if (t === "CLOCK") sym = clockSymbol(def);
  else if (t === "PROBE") sym = probeSymbol(def);
  else sym = boxSymbol(part, pinList(part).filter((p) => p.kind !== "gnd" || t !== "CLOCK"));
  symCache.set(key, sym);
  return sym;
}
export function clearSymbolCache() { symCache.clear(); }

// text that stays upright when the part is rotated (the view counter-rotates [data-rt] nodes)
export function txt(x, y, str, cls = "t-ink", size = 11, anchor = "start", weight) {
  return s("text", { x, y, class: cls, "font-size": size, "text-anchor": anchor, "font-weight": weight, "data-rt": "1" }, str);
}

function gateKind(def) {
  const names = new Set(def.pins.map((p) => String(p[1])));
  const d = String(def.desc || "");
  if (names.has("1A") && names.has("1Y") && !names.has("1B") && /invert/i.test(d)) return { k: "not", n: def.pins.filter((p) => /^\dA$/.test(p[1])).length };
  if (!(names.has("1A") && names.has("1B") && names.has("1Y")) || names.has("1C")) return null;
  const n = def.pins.filter((p) => /^\dY$/.test(p[1])).length;
  if (/XNOR/i.test(d)) return { k: "xnor", n };
  if (/XOR|exclusive/i.test(d)) return { k: "xor", n };
  if (/NAND/i.test(d)) return { k: "nand", n };
  if (/NOR/i.test(d)) return { k: "nor", n };
  if (/AND/i.test(d)) return { k: "and", n };
  if (/\bOR\b/i.test(d)) return { k: "or", n };
  return null;
}

function powerText(def) {
  const pw = def.pins.filter((p) => p[2] === "vcc" || p[2] === "gnd").map((p) => `${p[1]} ${p[0]}`);
  return pw.length ? "power: " + pw.join(", ") : "";
}

// ---- generic chip box (book style: ref and part number on top, pins left and right)
function chipSymbol(def) {
  const left = [], right = [];
  for (const [n, name, kind] of def.pins) {
    const it = { pin: String(n), name: String(name), kind };
    if (kind === "vcc" || kind === "gnd") continue;
    if (def.type.endsWith("245") && kind === "io") (String(name)[0] === "A" ? left : right).push(it);
    else if (kind === "in" || kind === "clk" || kind === "ana") left.push(it);
    else right.push(it);
  }
  if (def.type.endsWith("555")) {           // DIS reads better on the right, next to OUT
    const i = left.findIndex((p) => p.name === "DIS");
    if (i >= 0) right.push(...left.splice(i, 1));
  }
  const W = 120, rows = Math.max(left.length, right.length, 1);
  const H = 50 + rows * 20 + 10;
  const pins = [];
  left.forEach((p, i) => pins.push({ ...p, x: -20, y: 50 + i * 20, sx: 0, sy: 50 + i * 20, side: "L" }));
  right.forEach((p, i) => pins.push({ ...p, x: W + 20, y: 50 + i * 20, sx: W, sy: 50 + i * 20, side: "R" }));
  const pw = powerText(def);
  return {
    w: W, h: H, x0: 0, y0: 0, pins, chip: true,
    body(ctx) {
      const g = s("g");
      g.append(s("rect", { x: 0, y: 0, width: W, height: H, rx: 3, class: "chipbox" }));
      g.append(txt(W / 2, 17, ctx.part.id, "t-ink", 12, "middle", 700));
      g.append(txt(W / 2, 31, def.type, "t-ink2", 10.5, "middle"));
      for (const p of pins) {
        const inside = p.side === "L" ? 5 : W - 5;
        g.append(txt(inside, p.y + 3.5, p.name, "t-ink t-mono", 9.5, p.side === "L" ? "start" : "end"));
        if (p.kind === "clk") g.append(s("path", { d: `M0 ${p.y - 4} L6 ${p.y} L0 ${p.y + 4}`, class: "pinline" }));
        if (/(_n|̅)$/.test(p.name) || /^(OE|CE|WE|G|E|CLR|LOAD|MR|RESET|G2A|G2B|\dG|\dCLR)$/.test(p.name)) {
          // active-low inputs get the book's small circle at the box edge
          if (p.side === "L") g.append(s("circle", { cx: -3, cy: p.y, r: 3, class: "symfill" }));
        }
      }
      if (pw) g.append(txt(W / 2, H - 6, pw, "t-ink3", 8.5, "middle"));
      return g;
    },
  };
}

// ---- quad/hex gate chip: the box with the gates drawn inside, wired to their pins
function gateChipSymbol(def, gk) {
  const W = 130;
  const byName = Object.fromEntries(def.pins.map(([n, name, kind]) => [String(name), { pin: String(n), name: String(name), kind }]));
  const pins = [];
  const blocks = [];
  if (gk.k === "not") {
    for (let i = 1; i <= gk.n; i++) {
      const y = 50 + (i - 1) * 30;
      pins.push({ ...byName[`${i}A`], x: -20, y, sx: 0, sy: y, side: "L" });
      pins.push({ ...byName[`${i}Y`], x: W + 20, y, sx: W, sy: y, side: "R" });
      blocks.push({ y, ins: [y] });
    }
  } else {
    for (let i = 1; i <= gk.n; i++) {
      const top = 40 + (i - 1) * 60;
      pins.push({ ...byName[`${i}A`], x: -20, y: top + 10, sx: 0, sy: top + 10, side: "L" });
      pins.push({ ...byName[`${i}B`], x: -20, y: top + 30, sx: 0, sy: top + 30, side: "L" });
      pins.push({ ...byName[`${i}Y`], x: W + 20, y: top + 20, sx: W, sy: top + 20, side: "R" });
      blocks.push({ y: top + 20, ins: [top + 10, top + 30] });
    }
  }
  const H = (gk.k === "not" ? 50 + gk.n * 30 - 10 : 40 + gk.n * 60) + 20;
  const pw = powerText(def);
  return {
    w: W, h: H, x0: 0, y0: 0, pins, chip: true,
    body(ctx) {
      const g = s("g");
      g.append(s("rect", { x: 0, y: 0, width: W, height: H, rx: 3, class: "chipbox" }));
      g.append(txt(W / 2, 17, ctx.part.id, "t-ink", 12, "middle", 700));
      g.append(txt(W / 2, 31, def.type, "t-ink2", 10.5, "middle"));
      const sc = gk.k === "not" ? 0.55 : 0.8;
      for (const b of blocks) {
        const tip = W / 2 + 28;
        g.append(gateShape(gk.k, tip, b.y, sc));
        const ins = gateInputs(gk.k, tip, b.y, sc, b.ins.length);
        b.ins.forEach((yy, k) => {
          const [ix, iy] = ins[k];
          g.append(s("path", { d: `M0 ${yy} H${ix - 10} V${iy} H${ix}`, class: "pinline" }));
        });
        g.append(s("path", { d: `M${tip} ${b.y} H${W}`, class: "pinline" }));
      }
      for (const p of pins) {
        const inside = p.side === "L" ? 4 : W - 4;
        g.append(txt(inside, p.y - 3, p.name, "t-ink3 t-mono", 8, p.side === "L" ? "start" : "end"));
      }
      if (pw) g.append(txt(W / 2, H - 6, pw, "t-ink3", 8.5, "middle"));
      return g;
    },
  };
}

// Gate outline with its output tip at (x, y) — same proportions as the book's drawing kit.
export function gateShape(kind, x, y, sc = 1, cls = "symfill") {
  const k = kind.toLowerCase();
  const W = 50 * sc, H = 40 * sc;
  const bub = ["nand", "nor", "not", "xnor"].includes(k);
  const x0 = x - W - (bub ? 8 * sc : 0), y0 = y - H / 2;
  const g = s("g");
  if (k === "and" || k === "nand") g.append(s("path", { d: `M${x0} ${y0} H${x0 + W / 2} A${H / 2} ${H / 2} 0 0 1 ${x0 + W / 2} ${y0 + H} H${x0} Z`, class: cls }));
  else if (["or", "nor", "xor", "xnor"].includes(k)) {
    g.append(s("path", { d: `M${x0} ${y0} Q${x0 + W * 0.55} ${y0} ${x0 + W} ${y} Q${x0 + W * 0.55} ${y0 + H} ${x0} ${y0 + H} Q${x0 + W * 0.28} ${y} ${x0} ${y0} Z`, class: cls }));
    if (k === "xor" || k === "xnor") g.append(s("path", { d: `M${x0 - 7 * sc} ${y0} Q${x0 + W * 0.28 - 7 * sc} ${y} ${x0 - 7 * sc} ${y0 + H}`, class: "symline" }));
  } else if (k === "not" || k === "buf") g.append(s("path", { d: `M${x0 + 6 * sc} ${y0 + 2 * sc} L${x0 + W - 4 * sc} ${y} L${x0 + 6 * sc} ${y0 + H - 2 * sc} Z`, class: cls }));
  if (bub) g.append(s("circle", { cx: x - 4 * sc, cy: y, r: 4 * sc, class: cls }));
  return g;
}
export function gateInputs(kind, x, y, sc = 1, n = 2) {
  const k = kind.toLowerCase();
  const W = 50 * sc, H = 40 * sc;
  const x0 = x - W - (["nand", "nor", "not", "xnor"].includes(k) ? 8 * sc : 0);
  if (k === "not" || k === "buf") return [[x0 + 6 * sc, y]];
  const inset = ({ or: 7, nor: 7, xor: 6, xnor: 6 }[k] || 0) * sc;
  return Array.from({ length: n }, (_, i) => [x0 + inset, y - H / 2 + (H * (i + 1)) / (n + 1)]);
}

// ---- passives
function two(def, len, a = "1", b = "2") {
  return [{ pin: pinNo(def, a), name: a, kind: "pas", x: 0, y: 0, sx: 0, sy: 0, side: "L" }, { pin: pinNo(def, b), name: b, kind: "pas", x: len, y: 0, sx: len, sy: 0, side: "R" }];
}
function idText(g, part, x, y, anchor = "middle") { g.append(txt(x, y, part.id, "t-ink2", 10, anchor, 600)); }

function resistorSymbol(def) {
  return {
    w: 60, h: 20, x0: 0, y0: -10, pins: two(def, 60),
    body({ part }) {
      const g = s("g");
      const pts = ["M0 0 H15"];
      for (let i = 0; i < 6; i++) pts.push(`L${15 + 30 * (i + 0.5) / 6} ${i % 2 ? 6 : -6}`);
      pts.push("L45 0 H60");
      g.append(s("path", { d: pts.join(" "), class: "symline" }));
      g.append(txt(30, -11, (part.props && part.props.value) || "", "t-ink2", 10, "middle"));
      idText(g, part, 30, 20);
      return g;
    },
  };
}
function capSymbol(def) {
  return {
    w: 40, h: 20, x0: 0, y0: -12, pins: two(def, 40),
    body({ part }) {
      const g = s("g");
      g.append(s("path", { d: "M0 0 H17 M23 0 H40 M17 -10 V10 M23 -10 V10", class: "symline" }));
      g.append(txt(20, -14, (part.props && part.props.value) || "", "t-ink2", 10, "middle"));
      idText(g, part, 20, 23);
      return g;
    },
  };
}
function ledSymbol(def) {
  return {
    w: 60, h: 30, x0: 0, y0: -16, pins: two(def, 60, "A", "K"),
    body({ part, lit }) {
      const g = s("g");
      const col = LED_HEX[(part.props && part.props.colour) || "red"] || "#E8473B";
      if (lit) {
        g.append(s("circle", { cx: 29, cy: 0, r: 17, fill: col, "fill-opacity": 0.18 }));
        for (let k = 0; k < 8; k++) {
          const a = (k * Math.PI) / 4;
          g.append(s("line", { x1: 29 + 13 * Math.cos(a), y1: 13 * Math.sin(a), x2: 29 + 17 * Math.cos(a), y2: 17 * Math.sin(a), stroke: col, class: "led-ray" }));
        }
      }
      g.append(s("path", { d: "M0 0 H20 M38 0 H60", class: "symline" }));
      g.append(s("path", { d: "M20 -9 L37 0 L20 9 Z", fill: lit ? col : "var(--chip)", stroke: "var(--chip-line)", "stroke-width": 1.6, "stroke-linejoin": "round" }));
      g.append(s("path", { d: "M38 -9 V9", class: "symline" }));
      g.append(s("path", { d: "M30 -11 l6 -7 m-4 0 h4 v4 M36 -9 l6 -7 m-4 0 h4 v4", class: "symline", "stroke-width": 1.1 }));
      g.append(txt(30, 24, `${part.id}${lit ? " · on" : ""}`, lit ? "t-ink" : "t-ink2", 10, "middle", 600));
      return g;
    },
  };
}
function contacts(g, on, button) {
  g.append(s("circle", { cx: 13, cy: 0, r: 2.6, class: "symfill" }));
  g.append(s("circle", { cx: 37, cy: 0, r: 2.6, class: "symfill" }));
  if (button) {
    const y = on ? -4 : -10;
    g.append(s("path", { d: `M10 ${y} H40 M25 ${y} V${y - 9} M18 ${y - 9} H32`, class: "symline knob", "stroke-width": 2 }));
  } else g.append(s("path", { d: on ? "M13 0 L37 -3" : "M13 0 L34 -14", class: "symline lever", "stroke-width": 2.2 }));
}
function switchSymbol(def) {
  return {
    w: 50, h: 30, x0: 0, y0: -22, pins: two(def, 50), operable: true,
    body({ part, ctl }) {
      const on = !!ctl;
      const g = s("g", { class: "operable", "data-op": "toggle", role: "switch", "aria-checked": String(on), "aria-label": `${part.id} switch, ${on ? "on" : "off"}`, tabindex: "0" });
      g.append(s("rect", { x: 2, y: -24, width: 46, height: 34, fill: "transparent" }));
      g.append(s("path", { d: "M0 0 H12 M38 0 H50", class: "symline" }));
      contacts(g, on, false);
      g.append(txt(25, -20, `${part.id}${part.props && part.props.label ? " " + part.props.label : ""}`, "t-ink2", 10, "middle", 600));
      g.append(txt(25, 16, on ? "on" : "off", on ? "t-ink" : "t-ink3", 9, "middle"));
      return g;
    },
  };
}
// a tactile button: legs 1A and 1B are one side, 2A and 2B the other (joined inside the part)
function buttonSymbol(def) {
  const pins = [
    { pin: pinNo(def, "1A"), name: "1A", kind: "pas", x: 0, y: 0, sx: 0, sy: 0, side: "L" },
    { pin: pinNo(def, "2A"), name: "2A", kind: "pas", x: 50, y: 0, sx: 50, sy: 0, side: "R" },
    { pin: pinNo(def, "1B"), name: "1B", kind: "pas", x: 0, y: 30, sx: 0, sy: 30, side: "L" },
    { pin: pinNo(def, "2B"), name: "2B", kind: "pas", x: 50, y: 30, sx: 50, sy: 30, side: "R" },
  ];
  return {
    w: 50, h: 56, x0: 0, y0: -22, pins, operable: true,
    body({ part, ctl }) {
      const on = !!ctl;
      const g = s("g", { class: "operable", "data-op": "press", role: "button", "aria-pressed": String(on), "aria-label": `${part.id} push button${part.props && part.props.label ? " " + part.props.label : ""}`, tabindex: "0" });
      g.append(s("rect", { x: 2, y: -24, width: 46, height: 60, fill: "transparent" }));
      g.append(s("path", { d: "M0 0 H12 M38 0 H50 M0 30 H6 V0 M50 30 H44 V0", class: "symline", "stroke-width": 1.2 }));
      contacts(g, on, true);
      g.append(txt(25, 44, `${part.id}${part.props && part.props.label ? " " + part.props.label : ""}`, "t-ink2", 10, "middle", 600));
      if (on) g.append(txt(25, 13, "pressed", "t-ink", 8.5, "middle"));
      return g;
    },
  };
}
function spdtSymbol(def, part) {
  const th = positions(part);
  const pins = [{ pin: pinNo(def, "COM"), name: "COM", kind: "pas", x: 0, y: 0, sx: 0, sy: 0, side: "L" },
    { pin: pinNo(def, "A"), name: th[0], kind: "pas", x: 60, y: -10, sx: 60, sy: -10, side: "R" },
    { pin: pinNo(def, "B"), name: th[1], kind: "pas", x: 60, y: 10, sx: 60, sy: 10, side: "R" }];
  return {
    w: 60, h: 40, x0: 0, y0: -22, pins, operable: true,
    body({ part: pt, ctl }) {
      const pos = ctl || th[0];
      const g = s("g", { class: "operable", "data-op": "throw", role: "switch", "aria-label": `${pt.id} slide switch, at ${pos}`, tabindex: "0" });
      g.append(s("rect", { x: 0, y: -22, width: 60, height: 44, fill: "transparent" }));
      g.append(s("path", { d: "M0 0 H14 M44 -10 H60 M44 10 H60", class: "symline" }));
      g.append(s("circle", { cx: 15, cy: 0, r: 2.6, class: "symfill" }));
      g.append(s("circle", { cx: 44, cy: -10, r: 2.6, class: "symfill" }));
      g.append(s("circle", { cx: 44, cy: 10, r: 2.6, class: "symfill" }));
      g.append(s("path", { d: String(pos).toUpperCase() === String(th[1]).toUpperCase() ? "M15 0 L42 9" : "M15 0 L42 -9", class: "symline lever", "stroke-width": 2.2 }));
      g.append(txt(30, -15, `${th[0]}`, "t-ink3 t-mono", 8, "middle"));
      g.append(txt(30, 21, `${th[1]}`, "t-ink3 t-mono", 8, "middle"));
      g.append(txt(30, 33, `${pt.id}: ${pos}`, "t-ink2", 10, "middle", 600));
      return g;
    },
  };
}
function dipSymbol(def, n) {
  const pins = [];
  for (let k = 1; k <= n; k++) {
    const y = 20 + (k - 1) * 20;
    pins.push({ pin: pinNo(def, `${k}A`), name: `${k}A`, kind: "pas", x: -20, y, sx: 0, sy: y, side: "L" });
    pins.push({ pin: pinNo(def, `${k}B`), name: `${k}B`, kind: "pas", x: 80, y, sx: 60, sy: y, side: "R" });
  }
  const H = n * 20 + 20;
  return {
    w: 60, h: H, x0: 0, y0: 0, pins, operable: true,
    body({ part, ctl }) {
      const g = s("g");
      g.append(s("rect", { x: 0, y: 0, width: 60, height: H, rx: 3, class: "dip-body" }));
      g.append(txt(30, -6, part.id, "t-ink2", 10, "middle", 700));
      const labels = (part.props && part.props.labels) || [];
      for (let k = 1; k <= n; k++) {
        const on = !!(ctl && ctl[k - 1]);
        const y = 20 + (k - 1) * 20;
        const sw = s("g", { class: "dip-sw operable", "data-op": "section", "data-sec": String(k), role: "switch", tabindex: "0",
                            "aria-checked": String(on), "aria-label": `${part.id} section ${k}${labels[k - 1] ? " (" + labels[k - 1] + ")" : ""}, ${on ? "on" : "off"}` });
        sw.append(s("rect", { x: 14, y: y - 6, width: 32, height: 12, rx: 2, class: "dip-slot" }));
        sw.append(s("rect", { x: on ? 32 : 15, y: y - 5, width: 13, height: 10, rx: 1.5, class: "dip-lever" }));
        const num = txt(8, y + 3, String(k), "t-mono", 8, "middle");
        num.setAttribute("fill", "#fff");
        sw.append(num);
        g.append(sw);
      }
      g.append(txt(30, H + 12, "ON →", "t-ink3", 8.5, "middle"));
      return g;
    },
  };
}
const SEGS = { a: [[8, 4], [36, 4]], b: [[38, 6], [36, 36]], c: [[36, 40], [34, 70]], d: [[6, 72], [32, 72]], e: [[4, 40], [6, 70]], f: [[6, 6], [4, 36]], g: [[6, 38], [34, 38]] };
export function digitArt(g, x, y, bits, sc = 1, cls = ["seg-on", "seg-off"]) {
  const names = ["a", "b", "c", "d", "e", "f", "g"];
  names.forEach((nm, k) => {
    const [[x1, y1], [x2, y2]] = SEGS[nm];
    const on = bits != null && (bits >> k) & 1;
    g.append(s("line", { x1: x + x1 * sc + 4 * sc, y1: y + y1 * sc, x2: x + x2 * sc + 4 * sc, y2: y + y2 * sc, "stroke-width": 5.5 * sc, "stroke-linecap": "round",
                         class: on ? cls[0] : cls[1], stroke: on ? "#FF3B2F" : "#3A1A18" }));
  });
  const dp = bits != null && (bits >> 7) & 1;
  g.append(s("circle", { cx: x + 45 * sc, cy: y + 72 * sc, r: 3 * sc, fill: dp ? "#FF3B2F" : "#3A1A18" }));
}
function segSymbol(def) {
  const names = ["a", "b", "c", "d", "e", "f", "g", "dp"];
  const pins = names.map((nm, i) => ({ pin: pinNo(def, nm), name: nm, kind: "pas", x: -20, y: 20 + i * 20, sx: 0, sy: 20 + i * 20, side: "L" }));
  const com = def.pins.filter((p) => /^C[AC]2?$/.test(p[1]));
  com.forEach((p, i) => pins.push({ pin: String(p[0]), name: p[1], kind: "pas", x: 90, y: 20 + i * 20, sx: 70, sy: 20 + i * 20, side: "R" }));
  return {
    w: 70, h: 180, x0: 0, y0: 0, pins,
    body({ part, digit }) {
      const g = s("g");
      g.append(s("rect", { x: 0, y: 0, width: 70, height: 180, rx: 4, class: "chipbox" }));
      g.append(s("rect", { x: 14, y: 50, width: 50, height: 90, rx: 4, fill: "#151515" }));
      digitArt(g, 18, 58, digit, 0.95);
      names.forEach((nm, i) => g.append(txt(4, 20 + i * 20 + 3, nm, "t-ink t-mono", 8.5)));
      com.forEach((p, i) => g.append(txt(66, 23 + i * 20, p[1], "t-ink t-mono", 8.5, "end")));
      g.append(txt(35, 172, part.id, "t-ink2", 10, "middle", 700));
      return g;
    },
  };
}
function clockSymbol(def) {
  return {
    w: 60, h: 40, x0: 0, y0: -20, pins: [{ pin: pinNo(def, "OUT"), name: "OUT", kind: "out", x: 60, y: 0, sx: 40, sy: 0, side: "R" }],
    body({ part }) {
      const g = s("g");
      g.append(s("rect", { x: 0, y: -20, width: 40, height: 40, rx: 6, class: "chipbox" }));
      g.append(s("path", { d: "M7 6 H13 V-6 H20 V6 H27 V-6 H33", class: "symline", stroke: "var(--sig-clock)", "stroke-width": 2 }));
      const per = +(part.props && part.props.period_ns) || 0;
      g.append(txt(20, 33, `${part.id}${per ? " · " + fmtPer(per) : ""}`, "t-ink2", 10, "middle", 600));
      return g;
    },
  };
}
function fmtPer(ns) { const f = 1e9 / ns; return f >= 1e6 ? `${+(f / 1e6).toPrecision(3)} MHz` : f >= 1e3 ? `${+(f / 1e3).toPrecision(3)} kHz` : `${+f.toPrecision(3)} Hz`; }
function probeSymbol(def) {
  return {
    w: 50, h: 30, x0: 0, y0: -15, pins: [{ pin: pinNo(def, "TIP"), name: "TIP", kind: "in", x: 0, y: 0, sx: 0, sy: 0, side: "L" }],
    body({ part, probe }) {
      const g = s("g");
      const v = probe == null ? "?" : String(probe);
      const cls = v === "1" ? "v1" : v === "0" ? "v0" : v === "Z" ? "vz" : v === "X" ? "vx" : "";
      g.append(s("path", { d: "M0 0 H12", class: "symline" }));
      g.append(s("rect", { x: 12, y: -12, width: 30, height: 24, rx: 12, class: "chipbox" }));
      g.append(txt(27, 5, v, `valbadge ${cls}`, 13, "middle", 700));
      g.append(txt(27, 26, part.id, "t-ink2", 10, "middle", 600));
      return g;
    },
  };
}
function boxSymbol(part, pins) {
  const half = Math.ceil(pins.length / 2);
  const left = pins.slice(0, half), right = pins.slice(half);
  const W = 80, H = 30 + Math.max(left.length, right.length) * 20;
  const geo = [];
  left.forEach((p, i) => geo.push({ ...p, x: -20, y: 30 + i * 20, sx: 0, sy: 30 + i * 20, side: "L" }));
  right.forEach((p, i) => geo.push({ ...p, x: W + 20, y: 30 + i * 20, sx: W, sy: 30 + i * 20, side: "R" }));
  return {
    w: W, h: H, x0: 0, y0: 0, pins: geo,
    body({ part: pt }) {
      const g = s("g");
      g.append(s("rect", { x: 0, y: 0, width: W, height: H, rx: 6, class: "chipbox" }));
      g.append(txt(W / 2, 16, pt.id, "t-ink", 11, "middle", 700));
      for (const p of geo) g.append(txt(p.side === "L" ? 5 : W - 5, p.y + 3.5, p.name, "t-ink t-mono", 9, p.side === "L" ? "start" : "end"));
      const v = pt.props && (pt.props.value || pt.props.label);
      if (v) g.append(txt(W / 2, H + 12, String(v).slice(0, 26), "t-ink3", 9, "middle"));
      return g;
    },
  };
}

// World position of every pin of a placed part
export function pinPositions(part) {
  const sym = symbol(part);
  const rot = part.rot || 0;
  return sym.pins.map((p) => {
    const [x, y] = rotPt(p.x, p.y, rot);
    const [sx, sy] = rotPt(p.sx, p.sy, rot);
    const [dx, dy] = rotPt(...({ L: [-1, 0], R: [1, 0], T: [0, -1], B: [0, 1] }[p.side] || [0, 0]), rot);
    return { ...p, dx, dy, wx: (part.x || 0) + x, wy: (part.y || 0) + y, wsx: (part.x || 0) + sx, wsy: (part.y || 0) + sy };
  });
}
export function partBBox(part) {
  const sym = symbol(part);
  const pts = [[sym.x0 - 22, sym.y0 - 14], [sym.x0 + sym.w + 22, sym.y0 + sym.h + 16]];
  const rot = part.rot || 0;
  const xs = [], ys = [];
  for (const [x, y] of [[pts[0][0], pts[0][1]], [pts[1][0], pts[0][1]], [pts[0][0], pts[1][1]], [pts[1][0], pts[1][1]]]) {
    const [a, b] = rotPt(x, y, rot);
    xs.push(a + (part.x || 0)); ys.push(b + (part.y || 0));
  }
  return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
}
