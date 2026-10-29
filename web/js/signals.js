// Signal colours, the same rules as the book's drawings (bus yellow, control blue, data green,
// clock pink-red, address and step grey, +5 V red, GND ink). Colour is never the only cue: every wire
// and tag also carries its name and its value as text.
const CONTROL = new Set(["HLT_n", "MI_n", "RI_n", "RO_n", "IO_n", "II_n", "AI_n", "AO_n", "EO_n", "SU_n", "BI_n", "OI_n",
  "CE_n", "CO_n", "J_n", "FI_n", "XO_n", "SR_n", "SU", "CE", "RI"]);
const CLOCKS = new Set(["CLK", "CLK_n", "CLKRAW", "CK_RUN", "CK_STEP", "CK_SEL", "STEPPULSE", "SCANCLK", "CLOCK"]);
const MISC = new Set(["RST", "RST_n", "PROG", "RUNSEL", "RUNSEL_n"]);

export function netKind(net) {
  if (!net) return "data";
  if (net === "VCC" || net === "+5V") return "pwr";
  if (net === "GND") return "gnd";
  if (/^BUS\d*$/.test(net)) return "bus";
  if (CONTROL.has(net)) return "ctrl";
  if (CLOCKS.has(net) || /^CLK/.test(net)) return "clock";
  if (MISC.has(net)) return "misc";
  if (/^(RA|PC|MAR|ADDR|ADR)\d/.test(net) || /^STEP\d/.test(net) || /^LOP/.test(net)) return "addr";
  if (/_n$/.test(net) && !/^(DSEL|STEPY|XSEL)/.test(net)) return "ctrl";
  return "data";
}

const VAR = { bus: "--sig-bus", ctrl: "--sig-ctrl", data: "--sig-data", clock: "--sig-clock", addr: "--sig-addr", misc: "--sig-misc", pwr: "--pwr", gnd: "--gndc" };
const TINTV = { bus: "--sun-t", ctrl: "--sky-t", data: "--leaf-t", clock: "--berry-t", addr: "--grey-t", misc: "--copper-t", pwr: "--copper-t", gnd: "--well" };
export const netColour = (net) => `var(${VAR[netKind(net)]})`;
export const netTint = (net) => `var(${TINTV[netKind(net)]})`;

// Real wire colours for the breadboard (a physical board looks the same in either theme)
export const WIRE_HEX = { pwr: "#D7372B", gnd: "#222222", bus: "#D9A21B", ctrl: "#3D7FD0", data: "#4E9F3D", clock: "#D64570", addr: "#7E848D", misc: "#E8743B" };
export const wireHex = (net) => WIRE_HEX[netKind(net)];
export const WIRE_SWATCHES = [
  ["#D7372B", "red (+5 V)"], ["#222222", "black (GND)"], ["#D9A21B", "yellow (bus)"], ["#3D7FD0", "blue (control)"],
  ["#4E9F3D", "green (data)"], ["#D64570", "pink (clock)"], ["#7E848D", "grey (address)"], ["#E8743B", "orange"], ["#F2F2F2", "white"],
];

export function vclass(v) {
  if (v === 1 || v === true || v === "1") return "v1";
  if (v === 0 || v === false || v === "0") return "v0";
  if (v === "Z" || v === "z") return "vz";
  if (v === "X" || v === "x") return "vx";
  return "";
}
export function vtext(v) {
  const c = vclass(v);
  return c === "v1" ? "1" : c === "v0" ? "0" : c === "vz" ? "Z" : c === "vx" ? "X" : "";
}

export const LED_HEX = { red: "#E8473B", green: "#4E9F3D", yellow: "#F4B942", sky: "#3D7FD0", blue: "#3D7FD0", white: "#F4F4F4", orange: "#E8743B" };
