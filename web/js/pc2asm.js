// PC-2 instruction set, assembler and the book's starter programs.
// Instruction byte: high nibble = opcode, low nibble = operand (an address 0-15 or a value).
export const OPNAMES = ["HALT", "LOAD", "STORE", "ADD", "SUB", "JUMP", "JC", "OUT", "LDI", "ADI", "SBI", "JZ", "IN", "NOP", "USR1", "USR2"];
export const CODES = Object.fromEntries(OPNAMES.map((n, i) => [n, i]));
export const MEANING = {
  HALT: "stop the clock", LOAD: "A = memory[{a}]", STORE: "memory[{a}] = A", ADD: "A = A + memory[{a}]; set carry and zero",
  SUB: "A = A − memory[{a}]; set carry and zero", JUMP: "go to address {a}", JC: "if carry = 1, go to address {a}",
  OUT: "show A on the display (mode {a})", LDI: "A = {a}", ADI: "A = A + {a}; set carry and zero", SBI: "A = A − {a}; set carry and zero",
  JZ: "if zero = 1, go to address {a}", IN: "A = input switches {bank}", NOP: "do nothing", USR1: "your own instruction", USR2: "your own instruction",
};

export function asm(lines) {
  return lines.map((l) => {
    if (typeof l === "number") return l & 0xff;
    const [op, arg] = l.trim().split(/\s+/);
    if (!(op in CODES)) throw new Error(`unknown instruction ${op}`);
    const n = arg ? parseInt(arg, 10) : 0;
    if (!(n >= 0 && n <= 15)) throw new Error(`operand out of range in "${l}"`);
    return (CODES[op] << 4) | n;
  });
}
export function disasm(b) {
  const name = OPNAMES[b >> 4], a = b & 15;
  return ["HALT", "NOP", "USR1", "USR2"].includes(name) ? name : `${name} ${a}`;
}
export function meaning(b) {
  const name = OPNAMES[b >> 4], a = b & 15;
  return MEANING[name].replace("{a}", a).replace("{bank}", a % 2 ? "B" : "A");
}

// Starter programs (the same bytes the book proves for every input). `data` = {address: value}
// with named inputs the reader can set before loading; `inputs` = which input switch banks it reads.
export const PROGRAMS = [
  { id: "ECHO", title: "ECHO", what: "Shows the number on input switches A.", code: ["IN 0", "OUT 0", "HALT"], inputs: ["A"] },
  { id: "COUNTDOWN", title: "COUNTDOWN", what: "Counts down from input A to 0.", code: ["IN 0", "OUT 0", "SBI 1", "JC 1", "HALT"], inputs: ["A"] },
  { id: "ADD", title: "ADD", what: "Adds inputs A and B; the carry LED means the answer is too big.", code: ["IN 0", "STORE 15", "IN 1", "ADD 15", "JC 6", "OUT 0", "HALT"], inputs: ["A", "B"] },
  { id: "BIGGER", title: "BIGGER", what: "Shows the bigger of inputs A and B.", code: ["IN 1", "STORE 15", "IN 0", "STORE 14", "SUB 15", "JC 8", "LOAD 15", "JUMP 9", "LOAD 14", "OUT 0", "HALT"], inputs: ["A", "B"] },
  { id: "MULTIPLY", title: "MULTIPLY", what: "x × y by repeated adding. Set x and y below (answer up to 255).",
    code: ["LOAD 14", "SBI 1", "JC 6", "LOAD 13", "OUT 0", "HALT", "STORE 14", "LOAD 13", "ADD 15", "STORE 13", "JUMP 0"],
    params: [{ name: "x", addr: 15, value: 7 }, { name: "y", addr: 14, value: 6 }], data: { 13: 0 } },
  { id: "DIVIDE", title: "DIVIDE", what: "n ÷ d by repeated subtracting; the remainder is left in address 15.",
    code: ["LOAD 15", "SUB 14", "JC 6", "LOAD 13", "OUT 0", "HALT", "STORE 15", "LOAD 13", "ADI 1", "STORE 13", "JUMP 0"],
    params: [{ name: "n", addr: 15, value: 100 }, { name: "d", addr: 14, value: 7 }], data: { 13: 0 } },
  { id: "FIBONACCI", title: "FIBONACCI", what: "Shows 1 1 2 3 5 8 … 233, then halts when the next number is too big.",
    code: ["LOAD 14", "OUT 0", "ADD 15", "JC 10", "STORE 13", "LOAD 14", "STORE 15", "LOAD 13", "STORE 14", "JUMP 0", "HALT"], data: { 13: 0, 14: 1, 15: 0 } },
];

export function programBytes(prog, params = {}) {
  const mem = asm(prog.code);
  while (mem.length < 16) mem.push(0);
  for (const [a, v] of Object.entries(prog.data || {})) mem[+a] = v & 0xff;
  for (const p of prog.params || []) mem[p.addr] = (params[p.name] ?? p.value) & 0xff;
  // the bytes to enter by hand: the code, then each data byte the program reads
  const addrs = new Set(prog.code.map((_, i) => i));
  for (const a of Object.keys(prog.data || {})) addrs.add(+a);
  for (const p of prog.params || []) addrs.add(p.addr);
  return { mem, writes: [...addrs].sort((a, b) => a - b).map((a) => [a, mem[a]]) };
}

// ---- microcode, exactly as the book builds it (used by the demo engine)
export const SIGNALS = ["HLT", "MI", "RI", "RO", "IO", "II", "AI", "AO", "EO", "SU", "BI", "OI", "CE", "CO", "J", "FI", "XO", "SR"];
const BIT = Object.fromEntries(SIGNALS.map((s, i) => [s, 1 << i]));
const cw = (...n) => n.reduce((v, s) => v | BIT[s], 0);
const FETCH = [cw("CO", "MI"), cw("RO", "II", "CE")];
const OPS = {
  0: [cw("HLT")], 1: [cw("IO", "MI"), cw("RO", "AI", "SR")], 2: [cw("IO", "MI"), cw("AO", "RI", "SR")],
  3: [cw("IO", "MI"), cw("RO", "BI"), cw("EO", "AI", "FI", "SR")], 4: [cw("IO", "MI"), cw("RO", "BI"), cw("EO", "AI", "SU", "FI", "SR")],
  5: [cw("IO", "J", "SR")], 6: null, 7: [cw("AO", "OI", "SR")], 8: [cw("IO", "AI", "SR")], 9: [cw("IO", "BI"), cw("EO", "AI", "FI", "SR")],
  10: [cw("IO", "BI"), cw("EO", "AI", "SU", "FI", "SR")], 11: null, 12: [cw("XO", "AI", "SR")], 13: [cw("SR")], 14: [cw("SR")], 15: [cw("SR")],
};
export function controlWord(op, step, c, z) {
  let steps = OPS[op];
  if (op === 6) steps = c ? [cw("IO", "J", "SR")] : [cw("SR")];
  if (op === 11) steps = z ? [cw("IO", "J", "SR")] : [cw("SR")];
  const full = [...FETCH, ...steps];
  return step < full.length ? full[step] : cw("SR");
}
export const active = (word) => SIGNALS.filter((s) => word & BIT[s]);

export const SEG = { "0": 0x3f, "1": 0x06, "2": 0x5b, "3": 0x4f, "4": 0x66, "5": 0x6d, "6": 0x7d, "7": 0x07, "8": 0x7f, "9": 0x6f,
  A: 0x77, B: 0x7c, C: 0x39, D: 0x5e, E: 0x79, F: 0x71, "-": 0x40, " ": 0x00 };
export const SEG_CHAR = Object.fromEntries(Object.entries(SEG).map(([k, v]) => [v, k]));
export function displayText(value, mode) {
  let t = "";
  if (mode === 0) t = String(value);
  else if (mode === 1) t = String(value > 127 ? value - 256 : value);
  else if (mode === 2) t = value.toString(16).toUpperCase().padStart(2, "0");
  return t.padStart(4, " ");
}
