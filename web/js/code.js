// Code tab: a Python console in the page. It runs in the engine's worker, so `import bbench` is the same
// engine as the rest of the app; `project` and `sim` are the project and simulator open in the app.
import { h, clear, esc, storageGet, storageSet } from "./util.js";
import { engine } from "../engine.js";
import { simctl } from "./simctl.js";

export const EXAMPLES = [
  { id: "nand", title: "A NAND gate's truth table", code: `# Code it: test one gate of a 74HCT00 (the kit's NAND chip) the way the book's bench does
from bbench.compat.pc2sim import Netlist, Sim

N = Netlist()
m = N.module("bench")
N.chip("U1", "74HCT00", m, **{"1A": "A", "1B": "B", "1Y": "Y",
        "2A": "GND", "2B": "GND", "3A": "GND", "3B": "GND", "4A": "GND", "4B": "GND"})
a = N.switch_to_vcc(m, "A", "input A")
b = N.switch_to_vcc(m, "B", "input B")
s = Sim(N)

print(" A  B | Y")
for va in (0, 1):
    for vb in (0, 1):
        a.closed, b.closed = bool(va), bool(vb)
        s.step()
        print(f" {va}  {vb} | {s.v('Y')}")
` },
  { id: "echo", title: "Run ECHO on PC-2", code: `# Code it: load ECHO through the PROGRAM switches, set input A, run, read the display
from bbench.compat.pc2sim import Bench

b = Bench()
b.load([0xC0, 0x70, 0x00])          # IN 0, OUT 0, HALT
b.set_bits("input A switch {}", 42)
b.reset()
b.run()
print("display shows", repr(b.display()), "after", b.rises, "clock cycles")
` },
  { id: "pc2kit", title: "The book's pc2kit boxes (pc2, pc2tools)", code: `# The book's boxes run here as printed: bench, pc2 and pc2tools come with the engine
import sys; sys.path.insert(0, "tools/pc2kit")   # (on the desktop: the companion folder)
from bench import Bench
from pc2 import PC2, asm
from pc2tools import trace, NAMES

code = asm(["IN 0", "OUT 0", "HALT"])          # ECHO
print([f"{b:02X}" for b in code], NAMES[code[0] >> 4])
for r in trace(code, in0=200)[:5]:
    print(r["cycle"], r["step"], " ".join(r["lines"]), "bus =", r["bus"])
` },
  { id: "project", title: "The project open in the app", code: `# 'project' is the project open in the app, 'sim' its simulator
print(project.name, "-", len(project.data["parts"]), "parts,", len(project.data["nets"]), "nets")
for p in project.check()[:12]:
    print(f'{p["severity"]:<8} {p["message"]}')
` },
  { id: "state", title: "Read the simulator's nets", code: `# The values of a few nets right now (0, 1, Z = floating, X = unknown)
st = sim.state()
for net in sorted(st["nets"])[:24]:
    print(f"{net:<10} {st['nets'][net]}")
print("LEDs lit:", [k for k, on in st["leds"].items() if on])
` },
  { id: "library", title: "Every 74HCT chip in the library", code: `import bbench
for chip in bbench.library():
    if chip["type"].startswith("74HCT"):
        print(f'{chip["type"]:<10} {len(chip["pins"]):>2} pins  {chip["desc"]}')
` },
  { id: "timed", title: "Measure a clock with the timed simulator", code: `# Run the open project for 5 ms with real delays and measure CLK's period
t = project.simulator("timed")
t.run_ns(5_000_000)
w = t.trace(["CLK"])
rises = [c[0] for i, c in enumerate(w["signals"][0]["changes"]) if c[1] == 1 and i > 0]
if len(rises) > 1:
    period = (rises[-1] - rises[0]) / (len(rises) - 1)
    print(f"period {period/1000:.1f} us, frequency {1e9/period:.0f} Hz")
else:
    print("CLK did not tick: open the 555 clock example first")
` },
];

const KW = new Set("False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield print range len sorted".split(" "));

export class CodeTab {
  constructor(root, app) {
    this.root = root; this.app = app;
    this.n = 0;
    this.history = [];
    this.build();
    engine.on("stdout", (t) => this.write(t, "out"));
    engine.on("status", () => this.shown());
  }
  build() {
    const tb = h("div", { class: "toolbar", role: "toolbar", "aria-label": "Code" });
    this.exSel = h("select", { class: "input", "aria-label": "Examples" }, h("option", { value: "" }, "Book examples…"), ...EXAMPLES.map((e) => h("option", { value: e.id }, e.title)));
    this.exSel.onchange = () => { const e = EXAMPLES.find((x) => x.id === this.exSel.value); if (e) { this.setCode(e.code); } this.exSel.value = ""; };
    this.runBtn = h("button", { class: "btn go", title: "Run (Ctrl+Enter)", onclick: () => this.run() }, "▶ Run");
    this.note = h("span", { class: "hint" });
    tb.append(h("span", { class: "title" }, "Code"), this.exSel, this.runBtn,
      h("button", { class: "btn", onclick: () => clear(this.out) && this.write("", "out") }, "Clear output"), h("span", { class: "grow" }), this.note);
    const editor = h("div", { class: "editor" });
    this.gutter = h("div", { class: "gutter", "aria-hidden": "true" });
    this.hl = h("pre", { class: "hl", "aria-hidden": "true" });
    this.ta = h("textarea", { spellcheck: "false", "aria-label": "Python code", autocapitalize: "off", autocomplete: "off" });
    editor.append(this.gutter, h("div", { class: "stack" }, this.hl, this.ta));
    this.ta.addEventListener("input", () => { this.paint(); storageSet("bb-code", this.ta.value); });
    this.ta.addEventListener("scroll", () => { this.hl.scrollTop = this.ta.scrollTop; this.hl.scrollLeft = this.ta.scrollLeft; this.gutter.scrollTop = this.ta.scrollTop; });
    this.ta.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); this.run(); }
      else if (e.key === "Tab" && !e.shiftKey) { e.preventDefault(); document.execCommand("insertText", false, "    "); }
    });
    this.out = h("div", { class: "console", role: "log", "aria-label": "Output", "aria-live": "polite" });
    this.prompt = h("input", { "aria-label": "Python prompt", placeholder: "type a line of Python and press Enter", spellcheck: "false" });
    this.prompt.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && this.prompt.value.trim()) { const c = this.prompt.value; this.history.push(c); this.hpos = this.history.length; this.prompt.value = ""; this.exec(c, true); }
      else if (e.key === "ArrowUp" && this.history.length) { this.hpos = Math.max(0, (this.hpos ?? this.history.length) - 1); this.prompt.value = this.history[this.hpos]; e.preventDefault(); }
      else if (e.key === "ArrowDown" && this.history.length) { this.hpos = Math.min(this.history.length, (this.hpos ?? 0) + 1); this.prompt.value = this.history[this.hpos] || ""; e.preventDefault(); }
    });
    const consoleBox = h("div", { style: { display: "flex", flexDirection: "column", minHeight: "0", background: "#1E2A3A" } }, this.out,
      h("div", { class: "console prompt", style: { overflow: "visible", flex: "0 0 auto", borderTop: "1px solid #33445C" } }, h("span", { class: "in" }, ">>>"), this.prompt));
    this.out.style.flex = "1";
    this.root.append(tb, h("div", { class: "code-wrap" }, editor, consoleBox));
    this.setCode(storageGet("bb-code") || EXAMPLES[0].code);
    this.write("Python console. The engine is the same one the app uses: try a book example from the menu, or type below.\n", "lbl");
  }
  shown() {
    this.note.textContent = engine.backend === "python" ? "bbench is loaded · project and sim are the app's" : engine.pyReady ? "Python is ready; the bbench engine is not installed (demo engine)" : "Python is loading…";
  }
  setCode(c) { this.ta.value = c; this.paint(); storageSet("bb-code", c); }
  paint() {
    const src = this.ta.value;
    this.hl.innerHTML = highlight(src) + "\n";
    const n = src.split("\n").length;
    this.gutter.textContent = Array.from({ length: n }, (_, i) => i + 1).join("\n");
  }
  write(text, cls = "out") {
    const el = h("pre", { class: cls }, text);
    this.out.append(el);
    this.out.scrollTop = this.out.scrollHeight;
  }
  async run() { await this.exec(this.ta.value, false); }
  async exec(code, echo) {
    this.runBtn.disabled = true;
    this.n++;
    this.write(echo ? `>>> ${code}` : `In [${this.n}]: running ${code.split("\n").length} lines…`, "in");
    await simctl.whenReady();
    const t0 = performance.now();
    const r = await simctl.q(() => engine.runPython(code));
    if (r.out) this.write(r.out.replace(/\n$/, ""), r.ok ? "out" : "err");
    if (!r.ok && r.err) this.write(r.err, "err");
    if (!echo) this.write(r.ok ? `✓ done in ${Math.round(performance.now() - t0)} ms` : "✗ stopped with an error", r.ok ? "ok" : "err");
    this.runBtn.disabled = false;
    // the code may have changed the simulator the app shows
    simctl.refresh();
  }
}

export function highlight(src) {
  let out = "";
  const re = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|[rbfu]{0,2}"(?:\\.|[^"\\\n])*"|[rbfu]{0,2}'(?:\\.|[^'\\\n])*')|\b(\d+(?:\.\d+)?|0x[0-9a-fA-F]+)\b|\b([A-Za-z_]\w*)\b(\s*\()?/g;
  let last = 0, m;
  while ((m = re.exec(src))) {
    out += esc(src.slice(last, m.index));
    if (m[1]) out += `<span class="com">${esc(m[1])}</span>`;
    else if (m[2]) out += `<span class="str">${esc(m[2])}</span>`;
    else if (m[3]) out += `<span class="num">${esc(m[3])}</span>`;
    else if (m[4]) out += KW.has(m[4]) ? `<span class="kw">${m[4]}</span>${esc(m[5] || "")}` : m[5] ? `<span class="fn">${m[4]}</span>${esc(m[5])}` : esc(m[4]);
    last = re.lastIndex;
  }
  return out + esc(src.slice(last));
}
