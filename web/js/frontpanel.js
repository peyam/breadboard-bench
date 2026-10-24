// Front panel for PC-2: the real switches, buttons and LEDs, the 4-digit display, and a program loader
// that enters a program byte by byte through the PROGRAM switches. As on the real machine the run clock
// (the 555) always runs, at the speed chosen in the Clock menu (simctl's real-time clock): RUN/STEP at
// RUN lets it reach the computer until HALT; at STEP each press of the STEP button gives one cycle.
import { h, s, clear, toast, sleep } from "./util.js";
import { store } from "./store.js";
import { simctl } from "./simctl.js";
import { digitArt, positions, baseType } from "./parts.js";
import { PROGRAMS, programBytes, disasm, meaning, displayText, SEG, SEG_CHAR } from "./pc2asm.js";
import { LED_HEX } from "./signals.js";
import { speedSelect, pauseButton } from "./clockctl.js";
const CONTROLS = ["HLT", "MI", "RI", "RO", "IO", "II", "AI", "AO", "EO", "SU", "BI", "OI", "CE", "CO", "J", "FI", "XO", "SR"];

export class FrontPanel {
  constructor(root, app) {
    this.root = root; this.app = app;
    this.loading = false;
    this.listing = null;
    this.build();
    store.on("change", (e) => { if (e.kind === "load") { this.stop(); this.listing = null; this.render(); } });
    simctl.on("state", () => this.paint());
    simctl.on("synced", () => this.render());
    simctl.on("clock", () => this.paint());
  }
  get running() { const i = simctl.clockInfo(); return i.running && i.runMode && !i.halted; }
  build() {
    const tb = h("div", { class: "toolbar", role: "toolbar", "aria-label": "Front panel" });
    this.speedSel = speedSelect("How fast the 555 run clock goes (cycles per second); RUN/STEP decides whether the computer sees it");
    this.runBtn = h("button", { class: "btn go", title: "Set RUN/STEP to RUN: the clock reaches the computer, which runs until HALT", onclick: () => this.setRun(true) }, "▶ Run");
    this.stopBtn = h("button", { class: "btn", title: "Set RUN/STEP to STEP: the computer stops; STEP gives one cycle", onclick: () => this.setRun(false) }, "■ Stop");
    this.stepBtn = h("button", { class: "btn", title: "STEP mode, then one press of STEP: one clock cycle", onclick: () => this.stepOnce() }, "Step");
    this.resetBtn = h("button", { class: "btn", title: "Press RESET", onclick: () => this.reset() }, "Reset");
    this.pauseBtn = pauseButton();
    this.readout = h("span", { class: "cursor-readout", "aria-live": "polite" });
    tb.append(h("span", { class: "title" }, "Front panel"), this.runBtn, this.stopBtn, this.stepBtn, this.resetBtn, h("span", { class: "sep" }),
      h("label", { class: "field" }, "Clock", this.speedSel), this.pauseBtn, h("span", { class: "readout-slot" }, this.readout));
    this.main = h("div", { class: "panel-main" });
    this.side = h("div", { class: "panel-side" });
    this.root.append(tb, h("div", { class: "panel-wrap" }, this.main, this.side));
  }
  shown() { this.render(); }

  // ------------------------------------------------------------------ finding PC-2's controls
  controls() {
    const p = store.project;
    const byLabel = (re, type) => p.parts.find((x) => (!type || type.test(x.type)) && re.test((x.props && x.props.label) || ""));
    const dip = (re, fallback) => p.parts.find((x) => /^DIPSW/.test(x.type) && re.test(((x.props && x.props.labels) || [])[0] || (x.props && x.props.label) || "")) || p.parts.find((x) => x.id === fallback && /^DIPSW/.test(x.type));
    const c = {
      runstep: byLabel(/^RUN\s*\/\s*STEP$/i, /SPDT/), progrun: byLabel(/^PROG(RAM)?\s*\/\s*RUN$/i, /SPDT/),
      step: byLabel(/^STEP$/i, /BUTTON|BTN/), reset: byLabel(/^RESET$/i, /BUTTON|BTN/), write: byLabel(/^WRITE$/i, /BUTTON|BTN/),
      addr: dip(/address/i, "S1"), data: dip(/data/i, "S2"), ina: dip(/input A/i, "S3"), inb: dip(/input B/i, "S4"),
    };
    c.ok = !!(c.runstep && c.progrun && c.reset && c.write && c.addr && c.data && c.ina);
    c.digits = [0, 1, 2, 3].map((d) => p.parts.find((x) => /^7SEG/.test(baseType(x.type)) && new RegExp(`digit ${d}\\b`).test((x.props && x.props.label) || "")));
    return c;
  }
  throws(part) { return positions(part); }
  pos(part) { const th = this.throws(part); const c = simctl.ctl[part.id]; return th.find((x) => String(x).toUpperCase() === String(c).toUpperCase()) || th[0]; }

  // ------------------------------------------------------------------ drawing
  render() {
    clear(this.main);
    const c = this.controls();
    this.c = c;
    if (!c.ok) {
      this.main.append(h("div", { class: "empty" }, h("div", { class: "card" },
        h("h3", {}, "The front panel is for PC-2"),
        h("p", {}, "Open the whole computer to get its switches, buttons, LEDs and the 4-digit display."),
        h("button", { class: "btn primary", onclick: () => this.app.openPC2() }, "Open PC-2"))));
      clear(this.side);
      this.side.append(h("h4", {}, "Program loader"), h("p", { class: "note" }, "Available when PC-2 is open."));
      for (const b of [this.runBtn, this.stopBtn, this.stepBtn, this.resetBtn]) b.disabled = true;
      return;
    }
    for (const b of [this.runBtn, this.stopBtn, this.stepBtn, this.resetBtn]) b.disabled = false;
    const W = 1100, H = 720;
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "fp-svg", role: "group", "aria-label": "PC-2 front panel" });
    this.svg = svg;
    this.leds = [];
    svg.append(s("rect", { x: 1, y: 1, width: W - 2, height: H - 2, rx: 16, class: "fp-plate" }));
    const group = (x, y, w, hh, title, accent) => {
      svg.append(s("rect", { x, y, width: w, height: hh, rx: 12, class: "fp-group" }));
      svg.append(s("rect", { x, y: y + 10, width: 4, height: 18, rx: 2, fill: `var(--${accent || "teal"})` }));
      svg.append(s("text", { x: x + 14, y: y + 24, class: "fp-gtitle" }, title));
    };
    // display
    group(18, 18, 640, 190, "Display", "berry");
    const disp = s("g", { transform: "translate(40 46)" });
    disp.append(s("rect", { x: 0, y: 0, width: 300, height: 140, rx: 8, class: "fp-digit-bg" }));
    this.digitG = s("g");
    disp.append(this.digitG);
    svg.append(disp);
    this.dispText = s("text", { x: 190, y: 202, class: "fp-val", "text-anchor": "middle" }, "");
    svg.append(this.dispText);
    svg.append(s("text", { x: 362, y: 54, class: "fp-lab", "font-weight": 600 }, "Output register"));
    this.ledRow(svg, 374, 76, "OUT", null, 8, "red", "OUT");
    svg.append(this.valText(362, 122, "OUT"));
    svg.append(s("text", { x: 362, y: 150, class: "fp-lab", "font-weight": 600 }, "Display mode"));
    this.ledRow(svg, 374, 172, "MODE", null, 2, "red", "MODE");
    svg.append(this.valText(450, 176, "MODE"));
    // clock
    group(672, 18, 210, 190, "Clock", "sun");
    this.ledAt(svg, 712, 66, "CLK", "yellow", "clock");
    this.ledAt(svg, 772, 66, "HLT_n", "red", "halt", true);
    this.slide(svg, 690, 112, c.runstep, "RUN / STEP");
    this.key(svg, 842, 128, c.step, "STEP", () => this.pressStep());
    // program
    group(896, 18, 186, 190, "Program", "plum");
    this.slide(svg, 910, 50, c.progrun, "PROGRAM / RUN");
    this.ledAt(svg, 1048, 66, "PROG", "yellow", "program");
    this.key(svg, 946, 150, c.write, "WRITE", () => simctl.press(c.write.id, 120));
    this.key(svg, 1036, 150, c.reset, "RESET", () => this.reset());
    // registers
    group(18, 222, 540, 290, "Registers", "teal");
    const rows1 = [["BUS", "Bus", 8, "red"], ["A", "A register", 8, "red"], ["E", "ALU (Σ)", 8, "red"], ["B", "B register", 8, "red"]];
    rows1.forEach(([pre, lab, n, col], i) => { this.ledRow(svg, 160, 270 + i * 56, pre, lab, n, col, pre); svg.append(this.valText(424, 274 + i * 56, pre, n)); });
    this.ledAt(svg, 190, 494, "FC", "yellow", "carry");
    this.ledAt(svg, 260, 494, "FZ", "yellow", "zero");
    svg.append(s("text", { x: 36, y: 498, class: "fp-lab" }, "Flags"));
    group(574, 222, 508, 290, "Memory and instruction", "sky");
    const rows2 = [["PC", "Program counter", 4, "green"], ["RA", "RAM address", 4, "yellow"], ["RD", "RAM data", 8, "red"]];
    rows2.forEach(([pre, lab, n, col], i) => { this.ledRow(svg, 730, 270 + i * 56, pre, lab, n, col, pre); svg.append(this.valText(990, 274 + i * 56, pre, n)); });
    this.ledRow(svg, 730, 438, "OP", "Instruction", 4, "sky", "OP");
    this.ledRow(svg, 874, 438, "IRL", "", 4, "sky", "IRL");
    this.irText = s("text", { x: 1000, y: 442, class: "fp-val", "font-weight": 700 }, "");
    svg.append(this.irText);
    this.stepRow(svg, 730, 494);
    // control lines
    group(18, 526, 1064, 82, "Control lines (lit = active)", "sky");
    CONTROLS.forEach((nm, i) => this.ledAt(svg, 48 + i * 57, 576, `${nm}_n`, "green", nm, true, 7));
    // switches
    group(18, 622, 1064, 84, "", "copper");
    this.dipBank(svg, 36, 642, c.addr, "Address", 4);
    this.dipBank(svg, 232, 642, c.data, "Data", 8);
    this.dipBank(svg, 518, 642, c.ina, "Input A", 8);
    if (c.inb) this.dipBank(svg, 804, 642, c.inb, "Input B", 8);
    this.main.append(svg);
    this.renderSide();
    this.paint();
  }
  valText(x, y, pre) { const t = s("text", { x, y, class: "fp-val", "data-val": pre }, ""); return t; }
  ledAt(svg, x, y, net, col, label, activeLow = false, r = 8) {
    const g = s("g", { transform: `translate(${x} ${y})` });
    const led = { g, net, col: LED_HEX[col] || col, activeLow, r, label };
    this.leds.push(led);
    svg.append(g);
    if (label) svg.append(s("text", { x, y: y + r + 15, class: "fp-lab", "text-anchor": "middle" }, label));
    return led;
  }
  ledRow(svg, x, y, pre, label, n, col, valKey) {
    if (label) svg.append(s("text", { x: x - 124, y: y + 4, class: "fp-lab", "font-weight": 600 }, label));
    for (let k = n - 1; k >= 0; k--) {
      const xi = x + (n - 1 - k) * 34;
      this.ledAt(svg, xi, y, `${pre}${k}`, col, null);
      svg.append(s("text", { x: xi, y: y + 22, class: "fp-small", "text-anchor": "middle" }, String(k)));
    }
  }
  stepRow(svg, x, y) {
    svg.append(s("text", { x: x - 124, y: y + 4, class: "fp-lab", "font-weight": 600 }, "Step"));
    for (let k = 0; k < 8; k++) {
      this.ledAt(svg, x + k * 34, y, `STEPY${k}_n`, "green", null, true);
      svg.append(s("text", { x: x + k * 34, y: y + 22, class: "fp-small", "text-anchor": "middle" }, `T${k}`));
    }
  }
  slide(svg, x, y, part, label) {
    const th = this.throws(part);
    const g = s("g", { class: "fp-key", tabindex: "0", role: "switch", "data-ctl": part.id });
    const draw = () => {
      clear(g);
      const pos = this.pos(part);
      const left = pos === th[0];
      g.setAttribute("aria-label", `${label} switch, at ${pos}`);
      g.setAttribute("aria-checked", String(!left));
      g.append(s("rect", { x, y, width: 104, height: 34, rx: 17, fill: "var(--card)", stroke: "var(--ink)", "stroke-width": 1.4 }));
      g.append(s("rect", { x: left ? x + 3 : x + 53, y: y + 3, width: 48, height: 28, rx: 14, fill: "var(--ink)" }));
      g.append(s("text", { x: x + 27, y: y + 22, "text-anchor": "middle", class: "fp-val", "font-size": 11, "font-weight": 700, fill: left ? "var(--paper)" : "var(--ink2)", style: `fill:${left ? "var(--paper)" : "var(--ink3)"}` }, th[0]));
      g.append(s("text", { x: x + 77, y: y + 22, "text-anchor": "middle", class: "fp-val", "font-size": 11, "font-weight": 700, style: `fill:${!left ? "var(--paper)" : "var(--ink3)"}` }, th[1]));
      g.append(s("text", { x: x + 52, y: y + 52, "text-anchor": "middle", class: "fp-lab" }, label));
    };
    draw();
    g.__draw = draw;
    const act = () => {
      const next = this.pos(part) === th[0] ? th[1] : th[0];
      if (part === this.c.runstep) this.setRun(next === "RUN");
      else simctl.setThrow(part.id, next).then(draw);
    };
    g.addEventListener("click", act);
    g.addEventListener("keydown", (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); act(); } });
    svg.append(g);
  }
  key(svg, x, y, part, label, fn) {
    const g = s("g", { class: "fp-key", tabindex: "0", role: "button", "aria-label": `${label} button`, "data-key": label });
    g.append(s("rect", { x: x - 30, y: y - 22, width: 60, height: 44, rx: 10, fill: "var(--well)", stroke: "var(--line2)" }));
    g.append(s("circle", { cx: x, cy: y, r: 15, class: "cap" }));
    g.append(s("text", { x, y: y + 38, class: "fp-lab", "text-anchor": "middle", "font-weight": 600 }, label));
    const go = async () => { g.classList.add("down"); try { await fn(); } finally { setTimeout(() => g.classList.remove("down"), 140); } };
    g.addEventListener("click", go);
    g.addEventListener("keydown", (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); go(); } });
    svg.append(g);
  }
  dipBank(svg, x, y, part, label, n) {
    const g = s("g", { "data-dip": part.id });
    const ww = n * 22 + 16;
    g.append(s("text", { x, y: y + 2, class: "fp-lab", "font-weight": 600 }, `${label}`));
    const val = s("text", { x: x + ww, y: y + 2, class: "fp-val", "text-anchor": "end", "data-dipval": part.id }, "");
    g.append(val);
    g.append(s("rect", { x, y: y + 10, width: ww, height: 46, rx: 4, class: "dip-body" }));
    const msb = !!(part.props && part.props.msb_first);
    for (let k = n - 1; k >= 0; k--) {
      const sec = msb ? n - k : k + 1;                  // section 1 (leftmost) = bit 7 on PC-2; else section k+1 = bit k
      const xi = x + 8 + (n - 1 - k) * 22;
      const sw = s("g", { class: "dip-sw", tabindex: "0", role: "switch", "data-sec": String(sec), "data-bit": String(k), "aria-label": `${label} bit ${k}` });
      sw.append(s("rect", { x: xi, y: y + 16, width: 18, height: 34, rx: 3, class: "dip-slot" }));
      sw.append(s("rect", { x: xi + 2, y: y + 18, width: 14, height: 15, rx: 2, class: "dip-lever", "data-lever": "1" }));
      sw.append(s("text", { x: xi + 9, y: y + 70, class: "fp-small", "text-anchor": "middle" }, String(k)));
      const act = () => simctl.setSection(part.id, sec, !(simctl.ctl[part.id] || [])[sec - 1]);
      sw.addEventListener("click", act);
      sw.addEventListener("keydown", (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); act(); } });
      g.append(sw);
    }
    // type a number instead of flipping eight switches
    const fo = s("foreignObject", { x: x + ww + 6, y: y + 16, width: 66, height: 36 });
    const inp = h("input", { class: "input mono", type: "number", min: 0, max: (1 << n) - 1, "aria-label": `${label} value`, "data-dipinput": part.id, style: { width: "60px" } });
    inp.onchange = () => { const v = Math.max(0, Math.min((1 << n) - 1, parseInt(inp.value || "0", 10) || 0)); simctl.setBits(part.id, v, n); };
    fo.append(inp);
    g.append(fo);
    svg.append(g);
  }
  // ------------------------------------------------------------------ live state
  paint() {
    if (!this.svg || !this.c || !this.c.ok) return;
    const st = simctl.state || {};
    const nets = st.nets || {};
    for (const L of this.leds) {
      const v = nets[L.net];
      const on = L.activeLow ? v === 0 : v === 1;
      clear(L.g);
      if (on) {
        L.g.append(s("circle", { r: L.r + 5, fill: L.col, "fill-opacity": 0.22 }));
        for (let k = 0; k < 8; k++) { const a = (k * Math.PI) / 4; L.g.append(s("line", { x1: (L.r + 3) * Math.cos(a), y1: (L.r + 3) * Math.sin(a), x2: (L.r + 6) * Math.cos(a), y2: (L.r + 6) * Math.sin(a), stroke: L.col, "stroke-width": 1.3 })); }
        L.g.append(s("circle", { r: L.r, fill: L.col, stroke: "var(--ink)", "stroke-width": 1.1 }));
        L.g.append(s("circle", { cx: -L.r * 0.35, cy: -L.r * 0.35, r: L.r * 0.25, fill: "#fff" }));
      } else L.g.append(s("circle", { r: L.r, class: "led-off", "stroke-dasharray": v === "Z" || v === "X" ? "2 2" : null }));
      L.g.setAttribute("aria-label", `${L.label || L.net} ${on ? "on" : "off"}`);
    }
    const word = (pre, n) => { let x = 0; for (let k = 0; k < n; k++) { const b = nets[`${pre}${k}`]; if (b !== 0 && b !== 1) return null; x |= b << k; } return x; };
    for (const t of this.svg.querySelectorAll("[data-val]")) {
      const pre = t.dataset.val;
      const n = { PC: 4, RA: 4, MODE: 2 }[pre] || 8;
      const v = word(pre, n);
      t.textContent = v == null ? "—" : pre === "MODE" ? `mode ${v}` : `${v}  ·  ${v.toString(16).toUpperCase().padStart(n > 4 ? 2 : 1, "0")}h`;
    }
    const op = word("OP", 4), irl = word("IRL", 4);
    this.irText.textContent = op == null || irl == null ? "" : disasm((op << 4) | irl);
    // the display: from the engine's digit segments, or decoded from OUT and MODE
    const text = this.displayText(st, nets, word);
    clear(this.digitG);
    for (let d = 0; d < 4; d++) {
      const ch = text[d];
      const bits = SEG[ch] ?? 0;
      digitArt(this.digitG, 14 + d * 72, 20, bits, 1.25);
    }
    this.dispText.textContent = `display: “${text}”`;
    this.svg.setAttribute("data-display", text);
    // switches and inputs
    for (const dip of this.svg.querySelectorAll("[data-dip]")) {
      const id = dip.dataset.dip;
      const ctl = simctl.ctl[id] || [];
      let v = 0;
      for (const sw of dip.querySelectorAll("[data-sec]")) {
        const k = +sw.dataset.sec;
        const on = !!ctl[k - 1];
        if (on) v |= 1 << +sw.dataset.bit;
        const lever = sw.querySelector("[data-lever]");
        lever.setAttribute("y", on ? +lever.parentNode.firstChild.getAttribute("y") + 2 : +lever.parentNode.firstChild.getAttribute("y") + 17);
        sw.setAttribute("aria-checked", String(on));
      }
      dip.querySelector("[data-dipval]").textContent = `= ${v}`;
      const inp = dip.querySelector("[data-dipinput]");
      if (inp && document.activeElement !== inp) inp.value = String(v);
    }
    for (const g of this.svg.querySelectorAll("[data-ctl]")) g.__draw && g.__draw();
    const halted = st.halted || nets.HLT_n === 0;
    const info = simctl.clockInfo();
    const what = halted ? "halted" : !info.runMode ? (info.paused ? "STEP mode · clock paused" : "STEP mode") : info.running ? "running" : info.paused ? "RUN · clock paused" : "clock stopped";
    this.readout.textContent = `${what} · display “${text}”`;
    this.readout.title = st.cycles != null ? `${st.cycles} cycles of the 555 run clock` : "";
    this.paintListing(word("PC", 4), word("OP", 4));
  }
  displayText(st, nets, word) {
    const ids = this.c.digits;
    if (st.digits && ids.every((x) => x && st.digits[x.id] != null)) {
      return [3, 2, 1, 0].map((d) => SEG_CHAR[st.digits[ids[d].id] & 0x7f] ?? "?").join("");
    }
    const out = word("OUT", 8), mode = word("MODE", 2);
    return displayText(out ?? 0, mode ?? 0);
  }

  // ------------------------------------------------------------------ operating the clock
  // Run and Stop move the RUN/STEP slide switch, as on the real machine: the 555 clock keeps running
  // (simctl's real-time clock, at the chosen speed) and the switch decides whether CLK follows it.
  // They never change the simulator's pause (the "Pause clock" button, shared with the Schematic tab):
  // while it is paused the switch moves, the readout says so and nothing runs until it is resumed.
  async setRun(on) {
    const c = this.c || this.controls();
    if (!c.ok) return;
    const th = this.throws(c.runstep);
    const want = on ? (th.includes("RUN") ? "RUN" : th[0]) : (th.includes("STEP") ? "STEP" : th[1]);
    await simctl.setThrow(c.runstep.id, want);
    if (on && simctl.paused) toast("RUN/STEP is at RUN, but the clock is paused: press ▶ Resume clock to run.", 4000);
    simctl.kick();
    this.paint();
  }
  stop() { /* nothing runs here: the clock is simctl's */ }
  // the STEP button itself: the single-step 555 gives one clock pulse (only in STEP mode, as on the bench)
  async pressStep() {
    const c = this.c || this.controls();
    if (!c.step) return simctl.step(1);
    await simctl.press(c.step.id, 0);
  }
  // the toolbar's Step: STEP mode first, then one press
  async stepOnce() {
    const c = this.c || this.controls();
    if (this.pos(c.runstep) === "RUN") await this.setRun(false);
    const k = this.svg && this.svg.querySelector('[data-key="STEP"]');
    if (k) { k.classList.add("down"); setTimeout(() => k.classList.remove("down"), 140); }
    await this.pressStep();
  }
  async reset() { const c = this.c || this.controls(); await simctl.press(c.reset.id, 60); }

  // ------------------------------------------------------------------ program loader
  renderSide() {
    const el = this.side;
    clear(el);
    el.append(h("h4", {}, "Program loader"));
    el.append(h("p", { class: "note" }, "Pick a program: the loader enters it the way you would by hand — PROGRAM mode, set the address and data switches, press WRITE, for every byte — then sets RUN and presses RESET."));
    const sel = h("select", { class: "input", "aria-label": "Program", style: { flex: "1" } }, ...PROGRAMS.map((p) => h("option", { value: p.id }, p.title)));
    if (this.listing) sel.value = this.listing.prog.id;
    const params = h("div");
    const showParams = () => {
      clear(params);
      const prog = PROGRAMS.find((p) => p.id === sel.value);
      params.append(h("p", { class: "note" }, prog.what));
      for (const pr of prog.params || []) {
        const inp = h("input", { class: "input mono", type: "number", min: 0, max: 255, value: pr.value, "data-param": pr.name, style: { width: "80px" } });
        params.append(h("div", { class: "row" }, h("label", { class: "field" }, `${pr.name} (address ${pr.addr})`, inp)));
      }
      if (prog.inputs) params.append(h("p", { class: "note" }, `Then set input ${prog.inputs.join(" and ")} on the switches below the panel and press Run.`));
      this.showListing(prog, {});
    };
    sel.onchange = showParams;
    this.loadBtn = h("button", { class: "btn primary", onclick: async () => {
      const prog = PROGRAMS.find((p) => p.id === sel.value);
      const vals = {};
      for (const i of params.querySelectorAll("[data-param]")) vals[i.dataset.param] = +i.value;
      await this.loadProgram(prog, vals);
    } }, "Enter program");
    el.append(h("div", { class: "row" }, sel, this.loadBtn), params);
    this.progress = h("div", { class: "note", "aria-live": "polite" });
    this.listBox = h("div");
    el.append(this.progress, this.listBox);
    showParams();
  }
  showListing(prog, vals) {
    const { mem, writes } = programBytes(prog, vals);
    this.listing = { prog, mem, writes };
    clear(this.listBox);
    const t = h("table", { class: "listing" }, h("tr", {}, h("th", {}, "Addr"), h("th", {}, "Byte"), h("th", {}, "Binary"), h("th", {}, "Instruction"), h("th", {}, "Meaning")));
    for (const [a, b] of writes) {
      const isCode = a < prog.code.length;
      t.append(h("tr", { "data-addr": String(a) }, h("td", {}, a), h("td", {}, b.toString(16).toUpperCase().padStart(2, "0")),
        h("td", {}, `${(b >> 4).toString(2).padStart(4, "0")} ${(b & 15).toString(2).padStart(4, "0")}`),
        h("td", {}, isCode ? disasm(b) : `data ${b}`), h("td", { class: "m" }, isCode ? meaning(b) : "a value, not an instruction")));
    }
    this.listBox.append(t);
  }
  paintListing(pc) {
    if (!this.listBox) return;
    for (const tr of this.listBox.querySelectorAll("tr[data-addr]")) tr.classList.toggle("pc", +tr.dataset.addr === pc);
  }
  async loadProgram(prog, vals = {}) {
    const c = this.controls();
    if (!c.ok || this.loading) return;
    this.loading = true;
    this.loadBtn.disabled = true;
    await this.setRun(false);
    this.showListing(prog, vals);
    const { writes } = this.listing;
    const sp = simctl.speed === "real" ? 1000 : simctl.speed;
    const delay = sp === Infinity ? 0 : Math.max(0, Math.min(140, 600 / Math.max(1, +sp || 10)));
    const pt = this.throws(c.progrun);
    await simctl.setThrow(c.progrun.id, pt.includes("PROG") ? "PROG" : pt[0]);
    for (const [i, [a, b]] of writes.entries()) {
      this.progress.textContent = `Entering byte ${i + 1} of ${writes.length}: address ${a} = ${b.toString(16).toUpperCase().padStart(2, "0")}`;
      for (const tr of this.listBox.querySelectorAll("tr")) tr.classList.toggle("cur", tr.dataset.addr === String(a));
      await simctl.setBits(c.addr.id, a, 4);
      await simctl.setBits(c.data.id, b, 8);
      if (delay) await sleep(delay);
      await simctl.press(c.write.id, delay ? 60 : 0);
    }
    for (const tr of this.listBox.querySelectorAll("tr")) tr.classList.remove("cur");
    await simctl.setThrow(c.progrun.id, pt.includes("RUN") ? "RUN" : pt[1]);
    await simctl.press(c.reset.id, 0);
    this.progress.textContent = `${prog.title} is in memory (${writes.length} bytes). Set the inputs, then Run.`;
    this.loading = false;
    this.loadBtn.disabled = false;
    toast(`${prog.title} loaded`);
  }
}
