// Breadboard workspace: the book's 830-point boards drawn 1:1, chips and parts on holes, wires hole to
// hole in real colours, several boards, and a Check button that highlights what the checker finds.
import { h, s, clear, toast } from "./util.js";
import { store, partById, pinNetIndex, pkey } from "./store.js";
import { getDef, baseType, positions } from "./parts.js";
import { simctl } from "./simctl.js";
import { Viewport, zoomControls } from "./viewport.js";
import { askText } from "./ui.js";
import { WIRE_SWATCHES, wireHex, LED_HEX } from "./signals.js";
import { PITCH, BOARD_W, BOARD_H, X0, Y0, RAILY, ROWS, COLS, holeXY, railXY, endXY, isRail, placementLegs, holeName, RAIL_WORDS, isDip, footprint } from "./bbgeom.js";
import { normWhere } from "./where.js";

const COLY = { a: 0, b: 1, c: 2, d: 3, e: 4, f: 7, g: 8, h: 9, i: 10, j: 11 };

export class Breadboard {
  constructor(root, app) {
    this.root = root; this.app = app;
    this.tool = "select";
    this.colour = WIRE_SWATCHES[2][0];
    this.sel = null;                // {kind: "placement"|"wire", board, index}
    this.armed = null;              // first end of a wire: {board, at}
    this.problems = [];
    this.focusBoard = null;
    this.build();
    store.on("change", (e) => { if (e.kind === "load") { this.problems = []; this.render(); this.fitAll(); } else this.render(); });
    simctl.on("state", () => this.paintLive());
  }
  build() {
    const tb = h("div", { class: "toolbar", role: "toolbar", "aria-label": "Breadboard tools" });
    const tool = (id, label, title) => h("button", { "data-tool": id, "aria-pressed": "false", title, onclick: () => this.setTool(id) }, label);
    this.toolSeg = h("div", { class: "seg", role: "group", "aria-label": "Tool" }, tool("select", "Select", "Select and move parts (V)"), tool("wire", "Wire", "Click a hole, then another hole or a rail (W)"));
    this.swatches = h("div", { class: "swatches", role: "radiogroup", "aria-label": "Wire colour" });
    for (const [c, name] of WIRE_SWATCHES) {
      const b = h("button", { class: "swatch", style: { background: c }, title: name, "aria-label": `wire colour ${name}`, role: "radio", "aria-pressed": String(c === this.colour) });
      b.onclick = () => { this.colour = c; for (const x of this.swatches.children) x.setAttribute("aria-pressed", String(x === b)); this.setTool("wire"); };
      this.swatches.append(b);
    }
    this.checkBtn = h("button", { class: "btn primary", title: "Compare the boards with the schematic's netlist", onclick: () => this.check() }, "✓ Check");
    this.summary = h("span", { class: "hint" });
    tb.append(h("span", { class: "title" }, "Breadboard"), this.toolSeg, this.swatches, h("span", { class: "sep" }),
      h("button", { class: "btn", title: "Delete the selection (Delete)", onclick: () => this.deleteSel() }, "Delete"),
      h("button", { class: "btn", title: "Add an empty 830-point board", onclick: () => this.addBoard() }, "+ Board"),
      h("span", { class: "sep" }), this.checkBtn, this.summary, h("span", { class: "grow" }));
    this.side = h("div", { class: "side", "aria-label": "Boards and parts" });
    this.canvas = h("div", { class: "canvas", tabindex: "0", "aria-label": "Breadboards" });
    this.canvas.style.background = "var(--paper)";
    this.svg = s("svg", { class: "view", role: "application", "aria-roledescription": "breadboard editor" });
    this.world = s("g");
    this.svg.append(this.world);
    this.vp = new Viewport(this.svg, this.world, { min: 0.12, max: 8 });
    this.help = h("div", { class: "overlay-help" });
    this.canvas.append(this.svg, this.help, zoomControls(this.vp, () => (this.focusBoard ? this.zoomBoard(this.focusBoard) : this.fitAll())));
    this.root.append(tb, h("div", { class: "split" }, this.side, this.canvas));
    this.svg.addEventListener("pointerdown", (e) => this.onDown(e));
    this.svg.addEventListener("pointermove", (e) => this.onMove(e));
    this.canvas.addEventListener("keydown", (e) => this.onKey(e));
    this.canvas.addEventListener("dragover", (e) => e.preventDefault());
    this.canvas.addEventListener("drop", (e) => {
      e.preventDefault();
      const id = e.dataTransfer.getData("text/x-bbench-part");
      if (id) this.dropPart(id, e.clientX, e.clientY);
    });
    this.setTool("select");
  }
  shown() { if (!this._fitted) { this.fitAll(); this._fitted = true; } }
  setTool(t) {
    this.tool = t;
    this.armed = null;
    for (const b of this.toolSeg.children) b.setAttribute("aria-pressed", String(b.dataset.tool === t));
    this.svg.style.cursor = t === "wire" ? "crosshair" : "default";
    this.help.textContent = t === "wire" ? "Click a hole, then another hole or a rail stripe. Esc stops." :
      "Drag parts from the list onto a board · drag a part to move it · click a hole of a part's leg to see its net · wheel to zoom";
    this.drawGhost(null);
  }

  // ------------------------------------------------------------------ rendering
  render() {
    const p = store.project;
    this.idx = pinNetIndex(p);
    this.renderSide();
    clear(this.world);
    this.boardEls = new Map();
    for (const bb of p.breadboards) this.world.append(this.drawBoard(bb));
    this.linkLayer = s("g");
    this.world.append(this.linkLayer);
    this.drawLinks();
    this.problemLayer = s("g");
    this.world.append(this.problemLayer);
    this.ghost = s("path", { class: "ghostwire", d: "" });
    this.world.append(this.ghost);
    if (!p.breadboards.length) {
      const g = s("g", { transform: "translate(40 40)" });
      g.append(s("text", { x: 0, y: 20, class: "t-ink2", "font-size": 16 }, "No breadboard yet. Press “+ Board” to add one, then drag parts onto it."));
      this.world.append(g);
    }
    this.paintProblems();
    this.paintLive();
  }
  renderSide() {
    const p = store.project;
    const el = this.side;
    clear(el);
    el.append(h("h5", {}, `Boards (${p.breadboards.length})`));
    for (const bb of p.breadboards) {
      const n = this.problems.filter((x) => this.problemBoard(x) === bb.id).length;
      const b = h("button", { class: "item" + (n ? " bad" : ""), "aria-current": String(this.focusBoard === bb.id) },
        h("span", {}, bb.name || bb.id), h("span", { class: "n" }, n ? `${n} ✗` : `${(bb.placements || []).length}`));
      b.title = `${bb.id}: ${(bb.placements || []).length} parts, ${(bb.wires || []).length} wires`;
      b.onclick = () => this.zoomBoard(bb.id);
      b.ondblclick = () => this.renameBoard(bb.id);
      el.append(b);
    }
    if (p.breadboards.length > 1) el.append(h("button", { class: "item", onclick: () => { this.focusBoard = null; this.fitAll(); this.renderSide(); } }, h("span", {}, "Show all boards"), h("span", { class: "n" }, "⤢")));
    const placed = new Set(p.breadboards.flatMap((b) => (b.placements || []).map((x) => x.part)));
    const unplaced = p.parts.filter((x) => !placed.has(x.id));
    el.append(h("h5", {}, `Not on a board (${unplaced.length})`));
    if (!unplaced.length) el.append(h("p", { class: "hint", style: { margin: "0 6px" } }, "Every part has a place."));
    for (const x of unplaced.slice(0, 200)) {
      const it = h("button", { class: "item", draggable: "true", title: "Drag onto a board" }, h("span", {}, x.id), h("span", { class: "n" }, x.type));
      it.ondragstart = (e) => { e.dataTransfer.setData("text/x-bbench-part", x.id); };
      it.onclick = () => this.placeAtFirstFree(x.id);
      el.append(it);
    }
    el.append(h("h5", {}, "How to"), h("p", { class: "hint", style: { margin: "0 6px", fontSize: "12px" } },
      "Chips sit across the centre gap with pin 1 at the left. Click a part in this list to drop it on the first free rows. Choose a colour, click a hole, then click another hole or a rail to add a wire. Check compares every board with the schematic."));
  }
  drawBoard(bb) {
    const g = s("g", { class: "bb", transform: `translate(${bb.x || 0} ${bb.y || 0})`, "data-board": bb.id });
    this.boardEls.set(bb.id, g);
    g.append(s("text", { x: 8, y: Y0 - 15.4 * PITCH - 6, class: "bb-title", "font-size": 13 }, `${bb.name || bb.id}`));
    g.append(s("text", { x: BOARD_W - 4, y: Y0 - 15.4 * PITCH - 6, class: "t-ink3", "font-size": 10, "text-anchor": "end" }, `${bb.id} · ${(bb.wires || []).length} wires`));
    const top = Y0 - 15.4 * PITCH;
    g.append(s("rect", { x: 6, y: top, width: 636, height: 19.2 * PITCH, rx: 6, class: "bb-board", "data-board-bg": bb.id }));
    // the centre gap
    g.append(s("rect", { x: 6, y: Y0 - 6.3 * PITCH, width: 636, height: 1.6 * PITCH, fill: "rgba(0,0,0,.05)" }));
    let holes = "";
    for (const [rail, col] of [["B-", "n"], ["B+", "p"], ["T-", "n"], ["T+", "p"]]) {
      const yy = Y0 - RAILY[rail] * PITCH;
      const ly = rail[1] === "+" ? (rail[0] === "B" ? yy + 4.8 : yy - 4.8) : (rail[0] === "B" ? yy - 4.8 : yy + 4.8);
      g.append(s("line", { x1: X0 - 6, y1: ly, x2: X0 + 62 * PITCH + 6, y2: ly, class: col === "p" ? "bb-railline-p" : "bb-railline-n" }));
      g.append(s("text", { x: X0 - 10, y: yy + 3.5, "font-size": 10, "text-anchor": "end", fill: col === "p" ? "#D7372B" : "#2F6DB5", "font-weight": 700 }, col === "p" ? "+" : "−"));
      for (let r = 1; r <= ROWS; r++) if ((r - 1) % 6 !== 5) holes += `M${(X0 + (r - 1) * PITCH - 1.6).toFixed(1)} ${(yy - 1.6).toFixed(1)}h3.2v3.2h-3.2z`;
    }
    for (let r = 1; r <= ROWS; r++) for (const c of COLS) { const [x, y] = holeXY(r, c); holes += `M${(x - 1.6).toFixed(1)} ${(y - 1.6).toFixed(1)}h3.2v3.2h-3.2z`; }
    g.append(s("path", { d: holes, class: "bb-hole" }));
    for (let r = 1; r <= ROWS; r++) if (r % 5 === 0 || r === 1) {
      g.append(s("text", { x: X0 + (r - 1) * PITCH, y: Y0 + 4.2 * PITCH + 2, "font-size": 6.5, "text-anchor": "middle", class: "bb-label" }, String(r)));
      g.append(s("text", { x: X0 + (r - 1) * PITCH, y: Y0 - 11.6 * PITCH - 5, "font-size": 6.5, "text-anchor": "middle", class: "bb-label" }, String(r)));
    }
    for (const c of COLS) { const [, y] = holeXY(1, c); g.append(s("text", { x: X0 - 9, y: y + 2.5, "font-size": 6.5, "text-anchor": "end", class: "bb-label" }, c)); }
    // wires under the parts
    const wl = s("g", { class: "bb-wires" });
    (bb.wires || []).forEach((w, i) => {
      const [ax, ay] = endXY(w.a, Array.isArray(w.b) ? +w.b[0] : 1);
      const [bx, by] = endXY(w.b, Array.isArray(w.a) && !isRail(w.a[0]) ? +w.a[0] : 1);
      const col = w.colour || (w.net ? wireHex(w.net) : "#4E9F3D");
      let d;
      if (isRail(w.b) || isRail(w.a) || (Array.isArray(w.b) && isRail(w.b[0]))) d = `M${ax} ${ay} L${bx} ${by}`;
      else {
        const span = Math.abs(bx - ax) + Math.abs(by - ay);
        const bow = Math.min(26, 4 + span * 0.16) * (i % 2 ? 1 : -1);
        d = `M${ax.toFixed(1)} ${ay.toFixed(1)} Q${((ax + bx) / 2).toFixed(1)} ${((ay + by) / 2 - bow).toFixed(1)} ${bx.toFixed(1)} ${by.toFixed(1)}`;
      }
      const sel = this.sel && this.sel.kind === "wire" && this.sel.board === bb.id && this.sel.index === i;
      const wg = s("g", { "data-wire": String(i) });
      wg.append(s("path", { d, class: "wire-hit" }));
      wg.append(s("path", { d, class: "bb-wire" + (sel ? " selected" : ""), stroke: col, style: col === "#F2F2F2" ? "stroke:#F2F2F2;filter:drop-shadow(0 0 .6px #555)" : "" }));
      for (const [px, py] of [[ax, ay], [bx, by]]) wg.append(s("circle", { cx: px, cy: py, r: 2.1, fill: col }));
      wg.append(s("title", {}, `Wire ${i + 1}${w.net ? " · " + w.net : ""}: ${holeName(w.a)} to ${isRail(w.b) ? RAIL_WORDS[w.b] : holeName(w.b)}`));
      wl.append(wg);
    });
    g.append(wl);
    const pl = s("g", { class: "bb-parts" });
    (bb.placements || []).forEach((pl0, i) => { const el = this.drawPlacement(bb, pl0, i); if (el) pl.append(el); });
    g.append(pl);
    if (this.focusBoard === bb.id) g.append(s("rect", { x: 2, y: top - 4, width: 644, height: 19.2 * PITCH + 8, rx: 9, class: "bb-frame focus" }));
    return g;
  }
  drawPlacement(bb, pl, i) {
    const part = partById(store.project, pl.part);
    if (!part) return null;
    const def = getDef(part.type);
    const legs = placementLegs(pl, def);
    if (!legs.length) return null;
    const sel = this.sel && this.sel.kind === "placement" && this.sel.board === bb.id && this.sel.index === i;
    const g = s("g", { class: "bb-part" + (sel ? " selected" : ""), "data-placement": String(i), "data-part": part.id, role: "img", "aria-label": `${part.id} ${part.type}` });
    const pts = legs.map((l) => endXY(l.at));
    const xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]);
    const xa = Math.min(...xs) - 4.5, xb = Math.max(...xs) + 4.5, ya = Math.max(...ys), yb = Math.min(...ys);
    const t = baseType(part.type);
    const title = s("title", {}, `${part.id} ${part.type}${part.props && part.props.label ? " — " + part.props.label : ""}`);
    if (/^7SEG/.test(t)) {
      g.append(s("rect", { x: xa, y: yb + 2, width: xb - xa, height: ya - yb - 4, rx: 2, class: "body", fill: "#1E1E1E", stroke: "#000" }));
      const dg = s("g", { "data-digit": part.id });
      g.append(dg);
      this.drawDigit(dg, part.id, (xa + xb) / 2 - 11, yb + (ya - yb) / 2 - 18);
    } else if (isDip(def) && !pl.legs) {
      if (/^DIPSW/.test(t)) {
        g.append(s("rect", { x: xa, y: yb + 2, width: xb - xa, height: ya - yb - 4, rx: 2, class: "body", fill: "#C8392F", stroke: "#7A1E18", "stroke-width": 1 }));
        const n = def.pins.length / 2;
        const ctl = simctl.ctl[part.id] || [];
        for (let k = 0; k < n; k++) {
          const xx = X0 + (+pl.row + k - 1) * PITCH;
          const on = !!ctl[k];
          const sw = s("g", { class: "dip-sw", "data-op": "section", "data-sec": String(k + 1) });
          sw.append(s("rect", { x: xx - 2.8, y: yb + 4, width: 5.6, height: ya - yb - 8, rx: 1, fill: "#8E241C" }));
          sw.append(s("rect", { x: xx - 2.5, y: on ? yb + 4.5 : (ya + yb) / 2 + 0.5, width: 5, height: (ya - yb - 9) / 2, rx: 1, fill: "#FFF" }));
          sw.append(s("title", {}, `${part.id} section ${k + 1}: ${on ? "on" : "off"}`));
          g.append(sw);
        }
        g.append(s("text", { x: (xa + xb) / 2, y: yb - 3, "font-size": 7.5, "text-anchor": "middle", "font-weight": 700, fill: "#1B2A41" }, part.id));
      } else {
        const wide = footprint(def).width >= 6;
        const yA = ya + 2, yB = yb - 2;
        const ytop = Math.min(yA, yB) + (wide ? 4 : 2), ybot = Math.max(yA, yB) - (wide ? 4 : 2);
        g.append(s("rect", { x: xa, y: ytop, width: xb - xa, height: ybot - ytop, rx: 2, class: "body", fill: "#2A2A2E", stroke: "#111", "stroke-width": 1 }));
        const my = (ytop + ybot) / 2;
        g.append(s("path", { d: `M${xa} ${my - 4} A4 4 0 0 1 ${xa} ${my + 4}`, fill: "#444", stroke: "#888", "stroke-width": 1 }));
        g.append(s("circle", { cx: xa + 4, cy: ybot - 4, r: 1.6, fill: "#BBB" }));
        g.append(s("text", { x: (xa + xb) / 2, y: my - 1, "font-size": 8.5, "text-anchor": "middle", fill: "#FFF", "font-weight": 700 }, part.id));
        g.append(s("text", { x: (xa + xb) / 2, y: my + 9, "font-size": 6.8, "text-anchor": "middle", fill: "#DDD" }, part.type));
      }
    } else if (legs.length === 2 && ["R", "C", "LED"].includes(t)) {
      const [[x1, y1], [x2, y2]] = pts;
      const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
      g.append(s("line", { x1, y1, x2, y2, stroke: "#9A9A9A", "stroke-width": 1.2 }));
      const ang = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
      if (t === "LED") {
        const col = LED_HEX[part.props.colour] || "#E8473B";
        g.append(s("circle", { cx: mx, cy: my, r: 5, class: "body led-body", fill: "#EEE", stroke: "#666", "stroke-width": 0.9, "data-led": part.id, "data-col": col }));
      } else if (t === "R") {
        const b = s("g", { transform: `rotate(${ang} ${mx} ${my})` });
        b.append(s("rect", { x: mx - 7, y: my - 2.6, width: 14, height: 5.2, rx: 2, class: "body", fill: "#D9C08C", stroke: "#8C7A33", "stroke-width": 0.6 }));
        for (const [k, c] of bandColours(part.props.value).entries()) b.append(s("rect", { x: mx - 4.5 + k * 3, y: my - 2.6, width: 1.4, height: 5.2, fill: c }));
        g.append(b);
      } else {
        const b = s("g", { transform: `rotate(${ang} ${mx} ${my})` });
        b.append(s("rect", { x: mx - 5, y: my - 3.5, width: 10, height: 7, rx: 3, class: "body", fill: /u|µ/.test(part.props.value || "") ? "#2F6DB5" : "#E6A23C", stroke: "#7A5B1A", "stroke-width": 0.6 }));
        g.append(b);
      }
    } else if (/^RN/.test(t)) {
      g.append(s("rect", { x: xa, y: yb - 7, width: xb - xa, height: 9, rx: 2, class: "body", fill: "#E9D48A", stroke: "#8C7A33", "stroke-width": 0.8 }));
      g.append(s("circle", { cx: xa + 4.5, cy: yb - 2.5, r: 1.5, fill: "#333" }));
      g.append(s("text", { x: xa + 2, y: yb - 9, "font-size": 6.5, class: "bb-label" }, part.id));
    } else if (t === "BUTTON") {
      g.append(s("rect", { x: xa, y: yb - 2, width: xb - xa, height: ya - yb + 4, rx: 2, class: "body", fill: "#333", stroke: "#000" }));
      const k = s("g", { class: "operable", "data-op": "press" });
      k.append(s("circle", { cx: (xa + xb) / 2, cy: (ya + yb) / 2, r: 6, fill: simctl.ctl[part.id] ? "#AAA" : "#777", stroke: "#000" }));
      g.append(k);
      g.append(s("text", { x: (xa + xb) / 2, y: yb - 5, "font-size": 7.5, "text-anchor": "middle", "font-weight": 700, fill: "#1B2A41" }, part.props.label || part.id));
    } else {
      const fill = { SPDT: "#3B6EA5", JUMPER3: "#222", PNP: "#222", NPN: "#222", POT: "#2F6DB5" }[t] || "#555";
      const hh = Math.max(10, ya - yb + 8);
      g.append(s("rect", { x: xa, y: (ya + yb) / 2 - hh / 2, width: xb - xa, height: hh, rx: t === "PNP" ? 5 : 2, class: "body", fill, stroke: "#000", "stroke-width": 0.8 }));
      if (t === "SPDT") {
        const th = positions(part);
        const pos = simctl.ctl[part.id] || th[0];
        const knobLeft = String(pos).toUpperCase() === String(th[0]).toUpperCase();
        const k = s("g", { class: "operable", "data-op": "throw" });
        k.append(s("rect", { x: knobLeft ? xa + 2 : (xa + xb) / 2, y: (ya + yb) / 2 - 3, width: (xb - xa) / 2 - 2, height: 6, rx: 1.5, fill: "#EEE" }));
        g.append(k);
      }
      g.append(s("text", { x: (xa + xb) / 2, y: (ya + yb) / 2 - hh / 2 - 3, "font-size": 6.8, "text-anchor": "middle", "font-weight": 700, fill: "#1B2A41" }, part.props.label || part.id));
    }
    // leg dots (handles when selected)
    for (const [k, l] of legs.entries()) {
      const [x, y] = pts[k];
      if (sel && pl.legs) g.append(s("circle", { cx: x, cy: y, r: 3.2, fill: "var(--select)", class: "leg-handle", "data-leg": l.key, style: "cursor:move" }));
    }
    g.append(title);
    return g;
  }
  drawDigit(g, id, x, y) {
    clear(g);
    const bits = simctl.live && simctl.state.digits ? simctl.state.digits[id] : null;
    const seg = [[2, 0, 18, 0], [20, 2, 20, 16], [20, 20, 20, 34], [2, 36, 18, 36], [0, 20, 0, 34], [0, 2, 0, 16], [2, 18, 18, 18]];
    seg.forEach(([x1, y1, x2, y2], k) => g.append(s("line", { x1: x + x1, y1: y + y1, x2: x + x2, y2: y + y2, "stroke-width": 3, "stroke-linecap": "round", stroke: bits != null && (bits >> k) & 1 ? "#FF3B2F" : "#4A1E1E" })));
    g.append(s("circle", { cx: x + 24, cy: y + 37, r: 1.6, fill: bits != null && (bits >> 7) & 1 ? "#FF3B2F" : "#4A1E1E" }));
  }
  drawLinks() {
    const p = store.project;
    const pos = Object.fromEntries(p.breadboards.map((b) => [b.id, b]));
    const names = Object.fromEntries(p.breadboards.map((b) => [b.id, b.name || b.id]));
    for (const l of p.links || []) {
      for (const [end, other] of [["a", "b"], ["b", "a"]]) {
        const [bid, at] = l[end];
        const bb = pos[bid];
        if (!bb) continue;
        const [hx, hy] = endXY(at);
        const up = Array.isArray(at) && "fghij".includes(at[1]);
        const ey = up ? hy - 7 : hy + 7;
        const col = l.colour || (l.net ? wireHex(l.net) : "#7B5EA7");
        const g = s("g", { transform: `translate(${bb.x || 0} ${bb.y || 0})` });
        g.append(s("line", { x1: hx, y1: hy, x2: hx, y2: ey, stroke: col, "stroke-width": 1.8 }));
        g.append(s("circle", { cx: hx, cy: ey, r: 1.8, fill: col }));
        g.append(s("title", {}, `${l.net || "link"}: ${holeName(at)} to ${names[l[other][0]] || l[other][0]} ${holeName(l[other][1])}`));
        this.linkLayer.append(g);
      }
    }
  }
  paintLive() {
    if (!this.boardEls) return;
    const st = simctl.state || {};
    for (const el of this.world.querySelectorAll("[data-led]")) {
      const on = simctl.live && st.leds && st.leds[el.dataset.led];
      el.setAttribute("fill", on ? el.dataset.col : "#EEE");
      el.style.filter = on ? `drop-shadow(0 0 4px ${el.dataset.col})` : "";
    }
    for (const el of this.world.querySelectorAll("[data-digit]")) {
      const bb = el.getBBox ? null : null;
      const first = el.querySelector("line");
      if (first) this.drawDigit(el, el.dataset.digit, +first.getAttribute("x1") - 2, +first.getAttribute("y1"));
    }
  }

  // ------------------------------------------------------------------ problems
  async check() {
    this.checkBtn.disabled = true;
    this.summary.textContent = "Checking…";
    const pr = await simctl.check();
    this.checkBtn.disabled = false;
    this.problems = pr;
    const bad = pr.filter((x) => x.severity !== "info").length;
    this.summary.textContent = bad ? `${bad} problem${bad > 1 ? "s" : ""} — highlighted in red` : "All boards match the schematic ✓";
    this.summary.style.color = bad ? "var(--danger)" : "var(--ok)";
    this.renderSide();
    this.paintProblems();
    if (bad) this.app.showProblems(true);
    return pr;
  }
  problemBoard(pr) {
    const w = normWhere(pr.where);
    if (w.board) return w.board;
    if (w.part) for (const bb of store.project.breadboards) if ((bb.placements || []).some((x) => x.part === w.part)) return bb.id;
    return null;
  }
  // where: "BB1:14j", "BB1 14j", "U3", "U3.7", "net:BUS0"
  locate(where) {
    const p = store.project;
    const w = normWhere(where);
    const out = [];
    if (w.board && w.hole) { const [x, y] = holeXY(+w.hole[0], w.hole[1]); out.push({ board: w.board, x, y, r: 5 }); return out; }
    const netName = !w.part && (w.net || (w.nets && w.nets[0]));
    const pins = netName ? (p.nets.find((n) => n.name === netName) || { pins: [] }).pins.map(([a, b]) => `${a}.${b}`) : null;
    const pm = !pins && w.part ? [null, w.part, w.pin] : null;
    for (const bb of p.breadboards) for (const pl of bb.placements || []) {
      const part = partById(p, pl.part);
      if (!part) continue;
      const legs = placementLegs(pl, getDef(part.type));
      for (const l of legs) {
        const key = `${part.id}.${l.pin}`;
        if ((pins && pins.includes(key)) || (pm && pm[1] === part.id && (!pm[2] || pm[2] === l.pin))) {
          const [x, y] = endXY(l.at);
          out.push({ board: bb.id, x, y, r: pm && !pm[2] ? 3.6 : 5 });
        }
      }
    }
    return out;
  }
  paintProblems() {
    if (!this.problemLayer) return;
    clear(this.problemLayer);
    const pos = Object.fromEntries(store.project.breadboards.map((b) => [b.id, b]));
    for (const pr of this.problems) {
      if (pr.severity === "info") continue;
      for (const L of this.locate(pr.where)) {
        const bb = pos[L.board];
        if (!bb) continue;
        const c = s("circle", { cx: (bb.x || 0) + L.x, cy: (bb.y || 0) + L.y, r: L.r, class: "bb-problem-fill" });
        c.append(s("title", {}, pr.message));
        this.problemLayer.append(c);
      }
    }
  }
  focusWhere(where) {
    const L = this.locate(where)[0];
    if (!L) { const w = normWhere(where); if (w.board) this.zoomBoard(w.board); return; }
    const bb = store.project.breadboards.find((b) => b.id === L.board);
    this.focusBoard = L.board;
    this.vp.k = 2.6;
    this.vp.centreOn((bb.x || 0) + L.x, (bb.y || 0) + L.y);
    this.render();
  }

  // ------------------------------------------------------------------ navigation
  boardsBBox(ids) {
    const bs = store.project.breadboards.filter((b) => !ids || ids.includes(b.id));
    if (!bs.length) return { x: 0, y: 0, w: 700, h: 300 };
    const x1 = Math.min(...bs.map((b) => b.x || 0)), y1 = Math.min(...bs.map((b) => (b.y || 0) - 30));
    const x2 = Math.max(...bs.map((b) => (b.x || 0) + BOARD_W + 10)), y2 = Math.max(...bs.map((b) => (b.y || 0) + BOARD_H));
    return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
  }
  fitAll() { this.vp.fit(this.boardsBBox(), 24, 2.2); }
  zoomBoard(id) { this.focusBoard = id; this.vp.fit(this.boardsBBox([id]), 24, 3); this.render(); }

  // ------------------------------------------------------------------ interaction
  pointAt(e) {
    const [wx, wy] = this.vp.toWorld(e.clientX, e.clientY);
    for (const bb of store.project.breadboards) {
      const lx = wx - (bb.x || 0), ly = wy - (bb.y || 0);
      if (lx < 0 || lx > BOARD_W || ly < Y0 - 16 * PITCH || ly > Y0 + 4 * PITCH) continue;
      const row = Math.round((lx - X0) / PITCH) + 1;
      if (row < 1 || row > ROWS) return { board: bb.id, lx, ly };
      const yi = (Y0 - ly) / PITCH;
      for (const [rail, ry] of Object.entries(RAILY)) if (Math.abs(yi - ry) < 0.45) return { board: bb.id, at: [rail, row], lx, ly };
      for (const [c, ci] of Object.entries(COLY)) if (Math.abs(yi - ci) < 0.5) return { board: bb.id, at: [row, c], lx, ly };
      return { board: bb.id, lx, ly };
    }
    return null;
  }
  onDown(e) {
    this.canvas.focus({ preventScroll: true });
    if (e.button === 1) { this.vp.pan(e); return; }
    if (e.button !== 0) return;
    const pt = this.pointAt(e);
    if (this.tool === "wire") {
      if (pt && pt.at) {
        if (!this.armed) { this.armed = { board: pt.board, at: pt.at }; this.help.textContent = `Wire from ${holeName(pt.at)} — click the other end (Esc stops)`; return; }
        if (this.armed.board !== pt.board) { toast("Both ends of a wire must be on the same board."); return; }
        const a = this.armed.at, b = pt.at;
        this.armed = null;
        this.drawGhost(null);
        if (JSON.stringify(a) === JSON.stringify(b)) return;
        store.commit("breadboard wire", (p) => {
          const bb = p.breadboards.find((x) => x.id === pt.board);
          (bb.wires ||= []).push({ a, b, colour: this.colour });
        });
        this.setTool("wire");
        return;
      }
      this.armed = null; this.drawGhost(null); this.vp.pan(e); return;
    }
    const op = e.target.closest("[data-op]");
    const pg = e.target.closest("[data-placement]");
    if (op && pg && simctl.live) { this.operate(pg.dataset.part, op); return; }
    const leg = e.target.closest("[data-leg]");
    if (leg && pg) { this.dragLeg(e, pg.closest("[data-board]").dataset.board, +pg.dataset.placement, leg.dataset.leg); return; }
    if (pg) {
      const bid = pg.closest("[data-board]").dataset.board;
      this.select({ kind: "placement", board: bid, index: +pg.dataset.placement });
      this.dragPlacement(e, bid, +pg.dataset.placement);
      return;
    }
    const wg = e.target.closest("[data-wire]");
    if (wg && wg.closest("[data-board]")) { this.select({ kind: "wire", board: wg.closest("[data-board]").dataset.board, index: +wg.dataset.wire }); return; }
    if (pt && pt.at && Array.isArray(pt.at) && !isRail(pt.at[0])) this.showHole(pt);
    this.select(null);
    this.vp.pan(e);
  }
  showHole(pt) {
    // name the half-row's net (from any leg on that node), so a builder can trace a connection
    const bb = store.project.breadboards.find((b) => b.id === pt.board);
    const [row, col] = pt.at;
    const half = "abcde".includes(col) ? "abcde" : "fghij";
    let net = null;
    for (const pl of bb.placements || []) {
      const part = partById(store.project, pl.part);
      if (!part) continue;
      for (const l of placementLegs(pl, getDef(part.type))) if (Array.isArray(l.at) && +l.at[0] === row && half.includes(l.at[1])) net = this.idx.get(pkey(part.id, l.pin)) || net;
    }
    this.help.textContent = `Hole ${row}${col} on ${bb.name || bb.id}${net ? ` · net ${net}` : ""} — holes ${row}${half[0]} to ${row}${half[4]} are joined underneath.`;
  }
  onMove(e) {
    if (this.tool === "wire" && this.armed) {
      const bb = store.project.breadboards.find((b) => b.id === this.armed.board);
      const [ax, ay] = endXY(this.armed.at);
      const [wx, wy] = this.vp.toWorld(e.clientX, e.clientY);
      this.drawGhost(`M${(bb.x || 0) + ax} ${(bb.y || 0) + ay} L${wx} ${wy}`);
    }
  }
  drawGhost(d) { if (this.ghost) this.ghost.setAttribute("d", d || ""); }
  onKey(e) {
    if (e.target !== this.canvas) return;
    if (e.key === "Escape") { this.setTool("select"); this.select(null); }
    else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); this.deleteSel(); }
    else if (e.key === "w" || e.key === "W") this.setTool("wire");
    else if (e.key === "v" || e.key === "V") this.setTool("select");
  }
  operate(id, op) {
    const part = partById(store.project, id);
    if (op.dataset.op === "section") { const k = +op.dataset.sec; simctl.setSection(id, k, !(simctl.ctl[id] || [])[k - 1]).then(() => this.render()); }
    else if (op.dataset.op === "throw") { const th = positions(part); simctl.setThrow(id, String(simctl.ctl[id]).toUpperCase() === String(th[0]).toUpperCase() ? th[1] : th[0]).then(() => this.render()); }
    else if (op.dataset.op === "press") { simctl.setSwitch(id, true); const up = () => { window.removeEventListener("pointerup", up); simctl.setSwitch(id, false).then(() => this.render()); }; window.addEventListener("pointerup", up); this.render(); }
  }
  select(sel) {
    this.sel = sel;
    for (const el of this.world.querySelectorAll(".bb-part.selected")) el.classList.remove("selected");
    for (const el of this.world.querySelectorAll(".bb-wire.selected")) el.classList.remove("selected");
    if (!sel) return;
    const bg = this.boardEls.get(sel.board);
    if (!bg) return;
    if (sel.kind === "placement") {
      const el = bg.querySelector(`[data-placement="${sel.index}"]`);
      if (el) { el.classList.add("selected"); const pid = el.dataset.part; const part = partById(store.project, pid); if (part) this.app.library.show(part.type, true); this.help.textContent = `${pid} selected · drag to move · Delete takes it off the board`; }
      if (el && store.project.breadboards.find((b) => b.id === sel.board).placements[sel.index].legs) this.render();
    } else {
      const el = bg.querySelector(`[data-wire="${sel.index}"] .bb-wire`);
      if (el) el.classList.add("selected");
    }
  }
  dragPlacement(e, bid, index) {
    const bb = store.project.breadboards.find((b) => b.id === bid);
    const pl = bb.placements[index];
    const [sx, sy] = this.vp.toWorld(e.clientX, e.clientY);
    const el = this.boardEls.get(bid).querySelector(`[data-placement="${index}"]`);
    let dr = 0, dc = 0;
    const mv = (ev) => {
      const [x, y] = this.vp.toWorld(ev.clientX, ev.clientY);
      dr = Math.round((x - sx) / PITCH);
      dc = pl.legs ? Math.round((sy - y) / PITCH) : 0;
      el.setAttribute("transform", `translate(${dr * PITCH} ${-dc * PITCH})`);
    };
    const up = () => {
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("pointerup", up);
      if (!dr && !dc) return;
      store.commit("move on board", (p) => {
        const q = p.breadboards.find((b) => b.id === bid).placements[index];
        if (q.legs) for (const [k, v] of Object.entries(q.legs)) q.legs[k] = shiftAt(v, dr, dc);
        else q.row = Math.max(1, Math.min(ROWS, +q.row + dr));
      }, "netlist");
    };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
  }
  dragLeg(e, bid, index, key) {
    const up = (ev) => {
      window.removeEventListener("pointerup", up);
      const pt = this.pointAt(ev);
      if (!pt || !pt.at || pt.board !== bid) return;
      store.commit("move leg", (p) => { p.breadboards.find((b) => b.id === bid).placements[index].legs[key] = pt.at; });
    };
    window.addEventListener("pointerup", up);
  }
  deleteSel() {
    const sl = this.sel;
    if (!sl) return;
    store.commit(sl.kind === "wire" ? "delete wire" : "take part off the board", (p) => {
      const bb = p.breadboards.find((b) => b.id === sl.board);
      if (sl.kind === "wire") bb.wires.splice(sl.index, 1);
      else bb.placements.splice(sl.index, 1);
    });
    this.sel = null;
  }
  async addBoard() {
    const name = await askText("New breadboard", `Board ${store.project.breadboards.length + 1}`, { hint: "An 830-point board: rows 1 to 63, holes a to j, two power rails along each edge." });
    if (!name) return;
    let id;
    store.commit("add board", (p) => {
      const used = new Set(p.breadboards.map((b) => b.id));
      let i = 1; while (used.has(`BB${i}`)) i++;
      id = `BB${i}`;
      const y = p.breadboards.length ? Math.max(...p.breadboards.map((b) => (b.y || 0))) + 270 : 0;
      p.breadboards.push({ id, name, x: 0, y, placements: [], wires: [] });
    });
    this.zoomBoard(id);
  }
  async renameBoard(id) {
    const bb = store.project.breadboards.find((b) => b.id === id);
    const name = await askText("Board name", bb.name || id);
    if (name) store.commit("rename board", (p) => { p.breadboards.find((b) => b.id === id).name = name; }, "view");
  }
  dropPart(id, cx, cy) {
    const pt = this.pointAt({ clientX: cx, clientY: cy });
    if (!pt || !pt.at || isRail(pt.at[0])) { toast("Drop the part onto a board's holes."); return; }
    this.place(id, pt.board, +pt.at[0], pt.at[1]);
  }
  placeAtFirstFree(id) {
    const p = store.project;
    if (!p.breadboards.length) { toast("Add a board first (+ Board)."); return; }
    const bid = this.focusBoard || p.breadboards[0].id;
    const bb = p.breadboards.find((b) => b.id === bid);
    let next = 1;
    for (const pl of bb.placements || []) {
      const part = partById(p, pl.part);
      const legs = placementLegs(pl, part && getDef(part.type));
      for (const l of legs) if (Array.isArray(l.at) && !isRail(l.at[0])) next = Math.max(next, +l.at[0] + 2);
    }
    if (next > ROWS) { toast("That board is full. Add another board."); return; }
    this.place(id, bid, next, "e");
  }
  place(id, bid, row, col) {
    const part = partById(store.project, id);
    const def = getDef(part.type);
    if (!def) return;
    if (footprint(def).kind === "virtual") { toast(`${id} is an instrument, not a part on the board.`); return; }
    store.commit(`place ${id}`, (p) => {
      const bb = p.breadboards.find((b) => b.id === bid);
      for (const b of p.breadboards) b.placements = (b.placements || []).filter((x) => x.part !== id);
      let pl;
      const fp = footprint(def);
      const bottom = "abcde".includes(col);
      if (fp.kind === "virtual") return;
      if (fp.kind === "dip") pl = { part: id, row: Math.min(row, ROWS - def.pins.length / 2 + 1), hole: fp.width >= 6 ? "c" : "e" };
      else if (fp.kind === "button") pl = { part: id, row: Math.min(row, ROWS - 2), hole: "e" };
      else if (fp.kind === "sip") pl = { part: id, row: Math.min(row, ROWS - (def.pins.length - 1) * (fp.pitch || 1)), hole: bottom ? "c" : "h" };
      else {
        const legs = {};
        if (def.pins.length === 2) { legs[String(def.pins[0][0])] = [row, "d"]; legs[String(def.pins[1][0])] = [row, "f"]; }
        else def.pins.forEach(([n], k) => { legs[String(n)] = [row + k, bottom ? "c" : "h"]; });
        pl = { part: id, legs };
      }
      bb.placements.push(pl);
    });
    this.zoomBoard(bid);
  }
}

function shiftAt(at, dr, dc) {
  if (Array.isArray(at) && /^[TB][+-]$/.test(at[0])) return [at[0], Math.max(1, Math.min(ROWS, +at[1] + dr))];
  const order = "abcde  fghij";
  const i = order.indexOf(at[1]);
  let j = Math.max(0, Math.min(order.length - 1, i + dc));
  if (order[j] === " ") j = dc > 0 ? 7 : 4;
  return [Math.max(1, Math.min(ROWS, +at[0] + dr)), order[j]];
}

// resistor colour bands for a value such as "10k" (first digit, second digit, multiplier)
const BAND = ["#000", "#7B3F00", "#D7372B", "#F28C28", "#F4D03F", "#2E8B57", "#3D7FD0", "#7B5EA7", "#888", "#FFF"];
function bandColours(v) {
  const m = String(v || "").match(/^([\d.]+)\s*([kKM]?)/);
  if (!m) return [];
  let ohms = parseFloat(m[1]) * ({ k: 1e3, K: 1e3, M: 1e6 }[m[2]] || 1);
  if (!(ohms >= 10)) return [];
  const e = Math.floor(Math.log10(ohms)) - 1;
  const d = Math.round(ohms / 10 ** e);
  return [BAND[Math.floor(d / 10) % 10], BAND[d % 10], BAND[Math.max(0, Math.min(9, e))]];
}
export { pkey };
