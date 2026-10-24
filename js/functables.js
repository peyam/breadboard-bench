// Function tables in the datasheets' own terms (H = high, L = low, X = either, ↑ = rising edge,
// Z = off/high impedance). Used when the engine's library entry carries no table of its own.
const T = (cols, rows, note) => ({ cols, rows, note });
const gate2 = (f) => T(["A", "B", "Y"], [["L", "L", f(0, 0)], ["L", "H", f(0, 1)], ["H", "L", f(1, 0)], ["H", "H", f(1, 1)]].map(([a, b, y]) => [a, b, y ? "H" : "L"]),
  "Each of the four gates on the chip works the same way.");
export const TABLES = {
  "00": gate2((a, b) => !(a && b)),
  "08": gate2((a, b) => a && b),
  "32": gate2((a, b) => a || b),
  "02": gate2((a, b) => !(a || b)),
  "86": gate2((a, b) => a !== b),
  "04": T(["A", "Y"], [["L", "H"], ["H", "L"]], "Six inverters."),
  "138": T(["G1", "G2A", "G2B", "C B A", "Output low"], [["L", "X", "X", "X X X", "none"], ["X", "H", "X", "X X X", "none"], ["X", "X", "H", "X X X", "none"],
    ["H", "L", "L", "L L L", "Y0"], ["H", "L", "L", "L L H", "Y1"], ["H", "L", "L", "…", "…"], ["H", "L", "L", "H H H", "Y7"]], "Exactly one output is low when enabled."),
  "139": T(["G", "B A", "Output low"], [["H", "X X", "none"], ["L", "L L", "Y0"], ["L", "L H", "Y1"], ["L", "H L", "Y2"], ["L", "H H", "Y3"]], "Two separate decoders."),
  "157": T(["G", "S", "Y"], [["H", "X", "L"], ["L", "L", "A"], ["L", "H", "B"]], "Four 2-to-1 switches sharing S and G."),
  "245": T(["OE", "DIR", "Data flows"], [["L", "L", "B → A"], ["L", "H", "A → B"], ["H", "X", "off (Z)"]], "Eight two-way buffers."),
  "283": T(["Inputs", "Outputs"], [["A1-A4, B1-B4, C0", "S1-S4 = A + B + C0, C4 = carry out"]], "Chain C4 to the next chip's C0 for 8 bits."),
  "173": T(["CLR", "G1", "G2", "CLK", "D", "Q next"], [["H", "X", "X", "X", "X", "L"], ["L", "H", "X", "↑", "X", "Q (hold)"], ["L", "X", "H", "↑", "X", "Q (hold)"],
    ["L", "L", "L", "↑", "L", "L"], ["L", "L", "L", "↑", "H", "H"]], "Outputs are off (Z) while M or N is high."),
  "161": T(["CLR", "LOAD", "ENP", "ENT", "CLK", "Q next"], [["L", "X", "X", "X", "X", "0 (at once)"], ["H", "L", "X", "X", "↑", "D C B A"], ["H", "H", "H", "H", "↑", "count + 1"],
    ["H", "H", "L", "X", "↑", "hold"], ["H", "H", "X", "L", "↑", "hold"]], "RCO is high at 15 while ENT is high."),
  "174": T(["CLR", "CLK", "D", "Q next"], [["L", "X", "X", "L"], ["H", "↑", "H", "H"], ["H", "↑", "L", "L"], ["H", "L", "X", "Q (hold)"]], "Six D flip-flops."),
  "377": T(["E", "CLK", "D", "Q next"], [["H", "X", "X", "Q (hold)"], ["L", "↑", "H", "H"], ["L", "↑", "L", "L"]], "Eight D flip-flops with one enable."),
  "107": T(["CLR", "CLK", "J", "K", "Q next"], [["L", "X", "X", "X", "L"], ["H", "↓", "L", "L", "Q"], ["H", "↓", "H", "L", "H"], ["H", "↓", "L", "H", "L"], ["H", "↓", "H", "H", "toggle"]], "Clocked on the falling edge."),
  "595": T(["Pin", "Does"], [["SER", "the next bit in"], ["SRCLK ↑", "shift one place"], ["RCLK ↑", "copy to the outputs"], ["OE = H", "outputs off (Z)"], ["SRCLR = L", "clear the shift register"]]),
  "555": T(["Wiring", "Does"], [["astable (R1, R2, C)", "square wave, f = 1.44 / ((R1 + 2·R2)·C)"], ["monostable (R, C)", "one pulse of 1.1·R·C after TRIG goes low"], ["bistable", "TRIG low sets OUT high, RESET low clears it"]]),
  "62256": T(["CE", "OE", "WE", "Does"], [["H", "X", "X", "off (Z)"], ["L", "L", "H", "read: IO = memory[A]"], ["L", "X", "L", "write: memory[A] = IO"], ["L", "H", "H", "outputs off"]]),
  "28C256": T(["CE", "OE", "WE", "Does"], [["H", "X", "X", "off (Z)"], ["L", "L", "H", "read: IO = memory[A]"], ["L", "H", "L", "write (needs a programmer in PC-2)"]]),
};
export function tableFor(def) {
  if (def.table) {
    const t = def.table;
    if (Array.isArray(t)) return { cols: t[0], rows: t.slice(1) };
    if (t.inputs && t.outputs) return { cols: [...t.inputs, ...t.outputs], rows: t.rows.map((r) => r.map(String)), note: t.note || "From the engine's model of the chip (1 = high, 0 = low)." , split: t.inputs.length };
    if (t.cols || t.columns) return { cols: t.cols || t.columns, rows: t.rows, note: t.note };
  }
  const m = String(def.type).match(/(\d+)$/);
  const t = String(def.type);
  if (/62256/.test(t)) return TABLES["62256"];
  if (/28C256/.test(t)) return TABLES["28C256"];
  if (/555/.test(t)) return TABLES["555"];
  return m ? TABLES[String(+m[1])] || TABLES[m[1]] : null;
}
