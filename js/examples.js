// Built-in examples. Small circuits are drawn here; PC-2 and its modules come from the engine
// (bbench.projects), so the app always shows the same computer the book proves.
import { emptyProject, connectPins, attachPin } from "./store.js";
import { getDef, pinNo } from "./parts.js";

class Builder {
  constructor(name, notes = "") { this.p = emptyProject(name); this.p.notes = notes; }
  part(id, type, x, y, props = {}, rot = 0) {
    const def = getDef(type);
    this.p.parts.push({ id, type, x, y, rot, props: { ...((def && def.props) || {}), ...props } });
    if (def) for (const [n, , kind] of def.pins) { if (kind === "vcc") attachPin(this.p, id, n, "VCC"); if (kind === "gnd") attachPin(this.p, id, n, "GND"); }
    return this;
  }
  pin(x) {
    const [id, n] = x.split(".");
    const part = this.p.parts.find((q) => q.id === id);
    return [id, pinNo(part && getDef(part.type), n)];
  }
  wire(a, b) {
    const A = this.pin(a), B = this.pin(b);
    const net = connectPins(this.p, A, B);
    this.p.schematic.wires.push({ net, points: [], a: A, b: B });
    return this;
  }
  label(pin, net) {
    const [id, n] = this.pin(pin);
    attachPin(this.p, id, n, net);
    this.p.schematic.labels.push({ net, x: 0, y: 0, pin: [id, n] });
    return this;
  }
  name(pin, net) { const [id, n] = this.pin(pin); attachPin(this.p, id, n, net); return this; }
  done(probes = []) { this.p.probes = probes; return this.p; }
}

// a logic input: a switch to +5 V with a 10 kΩ pull-down, as the book wires every input
function input(b, sw, r, x, y, net) {
  b.part(sw, "SW", x, y).part(r, "R", x + 20, y + 50, { value: "10k" }, 90);
  b.label(`${sw}.1`, "VCC").name(`${sw}.2`, net).name(`${r}.1`, net).label(`${r}.2`, "GND");
  b.p.schematic.wires.push({ net, points: [], a: b.pin(`${sw}.2`), b: b.pin(`${r}.1`) });
}
// an LED that lights when a net is 1: net → 1 kΩ → LED → GND
function led(b, r, d, x, y, net, colour = "red") {
  b.part(r, "R", x, y, { value: "1k" }).part(d, "LED", x + 90, y, { colour });
  b.name(`${r}.1`, net).wire(`${r}.2`, `${d}.A`).label(`${d}.K`, "GND");
}

export function nandExample() {
  const b = new Builder("NAND gate", "Two switches drive one NAND gate of a 74HCT00. The LED is off only when both switches are on.");
  input(b, "S1", "R1", 100, 120, "A");
  input(b, "S2", "R2", 100, 320, "B");   // low enough that R1's GND tag does not cover the S2 label
  b.part("U1", "74HCT00", 300, 60);
  b.wire("S1.2", "U1.1").wire("S2.2", "U1.2");
  led(b, "R3", "D1", 520, 120, "Y");
  b.wire("U1.3", "R3.1");
  for (const pin of ["4", "5", "9", "10", "12", "13"]) b.name(`U1.${pin}`, "GND");
  return b.done(["A", "B", "Y"]);
}

export function gatesExample() {
  const b = new Builder("Six gates", "One input pair drives an AND, OR, XOR, NAND and NOR gate and an inverter. Flip the switches and compare the LEDs with the function tables.");
  input(b, "S1", "R1", 60, 140, "A");
  input(b, "S2", "R2", 60, 300, "B");
  const chips = [["U1", "74HCT08", "AND"], ["U2", "74HCT32", "OR"], ["U3", "74HCT86", "XOR"], ["U4", "74HCT00", "NAND"], ["U5", "74HCT02", "NOR"]];
  chips.forEach(([u, t, nm], i) => {
    const x = 280 + (i % 3) * 330, y = 40 + Math.floor(i / 3) * 360;
    b.part(u, t, x, y);
    const pins = t === "74HCT02" ? ["2", "3", "1"] : ["1", "2", "3"];
    b.name(`${u}.${pins[0]}`, "A").name(`${u}.${pins[1]}`, "B").name(`${u}.${pins[2]}`, nm);
    const unused = t === "74HCT02" ? ["5", "6", "8", "9", "11", "12"] : ["4", "5", "9", "10", "12", "13"];
    for (const pin of unused) b.name(`${u}.${pin}`, "GND");
  });
  b.part("U6", "74HCT04", 940, 400);
  b.name("U6.1", "A").name("U6.2", "NOT_A");
  for (const pin of ["3", "5", "9", "11", "13"]) b.name(`U6.${pin}`, "GND");
  ["AND", "OR", "XOR", "NAND", "NOR", "NOT_A"].forEach((nm, i) => led(b, `R${10 + i}`, `D${i + 1}`, 1300, 80 + i * 80, nm, ["red", "green", "yellow", "red", "green", "yellow"][i]));
  return b.done(["A", "B", "AND", "OR", "XOR", "NAND", "NOR", "NOT_A"]);
}

export function latchExample() {
  const b = new Builder("SR latch", "Two cross-coupled NAND gates remember one bit. Press SET and the LED stays on; press RESET to clear it. Both buttons pull their line low (active low).");
  b.part("BTN1", "BUTTON", 80, 120, { label: "SET" }).part("BTN2", "BUTTON", 80, 300, { label: "RESET" });
  b.part("R1", "R", 200, 60, { value: "10k" }, 90).part("R2", "R", 200, 240, { value: "10k" }, 90);
  b.label("BTN1.1A", "GND").name("BTN1.2A", "S_n").label("BTN2.1A", "GND").name("BTN2.2A", "R_n");
  b.label("R1.1", "VCC").label("R2.1", "VCC");
  b.wire("BTN1.2A", "R1.2").wire("BTN2.2A", "R2.2");
  b.part("U1", "74HCT00", 340, 60);
  b.wire("R1.2", "U1.1");
  b.name("U1.3", "Q").name("U1.5", "Q").name("U1.2", "Q_n").name("U1.6", "Q_n").name("U1.4", "R_n");
  b.p.schematic.wires.push({ net: "R_n", points: [], a: ["R2", "2"], b: ["U1", "4"] });
  b.name("BTN1.1B", "GND").name("BTN1.2B", "S_n").name("BTN2.1B", "GND").name("BTN2.2B", "R_n");
  for (const pin of ["9", "10", "12", "13"]) b.name(`U1.${pin}`, "GND");
  led(b, "R3", "D1", 560, 100, "Q", "red");
  led(b, "R4", "D2", 560, 220, "Q_n", "green");
  return b.done(["S_n", "R_n", "Q", "Q_n"]);
}

export function clockExample() {
  const b = new Builder("555 clock", "A 555 timer wired astable: R1 = 1 kΩ, R2 = 10 kΩ, C = 100 nF give about 690 Hz. An inverter makes CLK_n. Open the Analyser to see both clocks.");
  b.part("U1", "NE555", 260, 60);
  b.part("R1", "R", 60, 60, { value: "1k" }, 90).part("R2", "R", 60, 160, { value: "10k" }, 90).part("C1", "C", 60, 270, { value: "100nF" }, 90).part("C2", "C", 160, 330, { value: "10nF" }, 90);
  b.label("R1.1", "VCC").name("R1.2", "DIS").name("R2.1", "DIS").name("R2.2", "THR").name("C1.1", "THR").label("C1.2", "GND");
  b.wire("R1.2", "R2.1").wire("R2.2", "C1.1");
  const pin = (nm) => getDef("NE555").pins.find((q) => q[1] === nm)[0];
  b.name(`U1.${pin("DIS")}`, "DIS").name(`U1.${pin("THR")}`, "THR").name(`U1.${pin("TRIG")}`, "THR").name(`U1.${pin("RESET")}`, "VCC").name(`U1.${pin("CTRL")}`, "CV").name(`U1.${pin("OUT")}`, "CLK");
  b.name("C2.1", "CV").label("C2.2", "GND");
  b.part("U2", "74HCT04", 520, 60);
  b.name("U2.1", "CLK").name("U2.2", "CLK_n");
  for (const p of ["3", "5", "9", "11", "13"]) b.name(`U2.${p}`, "GND");
  led(b, "R3", "D1", 780, 80, "CLK", "yellow");
  b.p.stimuli = [];
  return b.done(["CLK", "CLK_n", "THR"]);
}

export const LOCAL = [
  { id: "nand", group: "Gates", name: "NAND gate", desc: "Two switches, one gate, one LED", make: nandExample },
  { id: "gates", group: "Gates", name: "Six gates", desc: "AND, OR, XOR, NAND, NOR and NOT side by side", make: gatesExample },
  { id: "latch", group: "Memory", name: "SR latch", desc: "Two NAND gates that remember a bit", make: latchExample },
  { id: "clock555", group: "Clocks", name: "555 clock", desc: "An astable 555 and its inverted clock", make: clockExample },
  // drawn by the engine (bbench.projects.examples); listed here so the menu always has it: Examples ▸ Counters ▸ 4-bit counter
  { id: "4-bit-counter", group: "Counters", name: "4-bit counter", desc: "A 555 (about 2 Hz) clocks a 74HCT161; four LEDs count in binary", engine: true },
];

// the engine's examples go into the same topic groups as the ones drawn here
export const ENGINE_GROUP = { "nand-gate": "Gates", "nor-from-nand": "Gates", "xor-from-nand": "Gates",
  "sr-latch": "Memory", "d-flip-flop": "Memory", "555-clock": "Clocks", "4-bit-counter": "Counters" };

// One module of PC-2 as a project of its own: its parts and the nets between them
export function moduleOf(pc2, module) {
  const ids = new Set(pc2.parts.filter((x) => x.props && x.props.module === module).map((x) => x.id));
  const p = emptyProject(`PC-2 · ${module}`);
  p.notes = `The ${module} module of PC-2, cut out of the whole computer. Signals from other modules end at named nets.`;
  p.parts = pc2.parts.filter((x) => ids.has(x.id)).map((x) => ({ ...x, x: undefined, y: undefined }));
  p.nets = pc2.nets.map((n) => ({ name: n.name, pins: n.pins.filter(([id]) => ids.has(id)) })).filter((n) => n.pins.length);
  const boards = new Set(p.parts.map((x) => x.props.board));
  p.breadboards = (pc2.breadboards || []).filter((b) => boards.has(b.name)).map((b) => ({ ...b, placements: b.placements.filter((pl) => ids.has(pl.part)) }));
  p.probes = (pc2.probes || []).filter((n) => p.nets.some((x) => x.name === n));
  return p;
}
