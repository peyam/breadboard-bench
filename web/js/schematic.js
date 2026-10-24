// Schematic workspace: place parts, move, rotate, delete; wire pin to pin with orthogonal routing;
// net labels; edit values; zoom/pan; live simulation colouring; operate switches and buttons.
import { h, s, clear, toast, clamp } from "./util.js";
import { store, pinNetIndex, pkey, connectPins, attachPin, deletePart, deleteWire, renameNet, newPartId, partById, netByName, detachPin, pruneNets } from "./store.js";
import { symbol, pinPositions, partBBox, getDef, prefixFor, rotPt, GRID, pinList, baseType, positions, pinNo } from "./parts.js";
import { netColour, netTint, vclass, vtext } from "./signals.js";
import { simctl } from "./simctl.js";
import { Viewport, zoomControls, gridPattern } from "./viewport.js";
import { askText } from "./ui.js";
import { clockControls } from "./clockctl.js";
import { normWhere, guessWhere } from "./where.js";

const snap = (v) => Math.round(v / GRID) * GRID;

export class Schematic {
  constructor(root, app) {
    this.root = root; this.app = app;
    this.sel = null;            // {kind: "part"|"wire"|"net"|"label", id/ref}
    this.tool = "select";
    this.armed = null;          // pin a wire starts from
    this.placing = null;        // type being placed
    this.sheet = "All";
    this.netEls = new Map();    // net -> elements to recolour
    this.partEls = new Map();
    this.build();
    store.on("change", (e) => { if (e.kind === "load") { this.sheet = this.defaultSheet(); this.autoLayout(); this.render(); this.fit(); } else this.render(); });
    simctl.on("state", () => this.paintState());
    simctl.on("problems", () => this.paintMarkers());
  }

  build() {
    const tb = h("div", { class: "toolbar", role: "toolbar", "aria-label": "Schematic tools" });
    this.sheetSel = h("select", { class: "input", "aria-label": "Sheet", title: "Show one module of the circuit" });
    this.sheetSel.onchange = () => { this.sheet = this.sheetSel.value; this.render(); this.fit(); };
    const tool = (id, label, key, title) => h("button", { "data-tool": id, "aria-pressed": "false", title: `${title} (${key})`, onclick: () => this.setTool(id) }, label);
    this.toolSeg = h("div", { class: "seg", role: "group", "aria-label": "Tool" },
      tool("select", "Select", "V", "Select, move and operate parts"), tool("wire", "Wire", "W", "Click a pin, then another pin"), tool("label", "Net label", "L", "Click a pin to give it a net name"));
    this.liveBtn = h("button", { class: "btn", "aria-pressed": "true", title: "Colour wires by their simulated value and let switches be operated", onclick: () => this.setLive(!simctl.live) }, "● Simulate");
    tb.append(h("span", { class: "title" }, "Schematic"), this.sheetSel, h("span", { class: "sep" }), this.toolSeg,
      h("button", { class: "btn", title: "Rotate the selected part (R)", onclick: () => this.rotateSel() }, "⟳ Rotate"),
      h("button", { class: "btn", title: "Delete the selection (Delete)", onclick: () => this.deleteSel() }, "Delete"),
      h("span", { class: "sep" }), this.liveBtn,
      h("button", { class: "btn", title: "Run the engine's checker", onclick: async () => { const pr = await simctl.check(); this.app.showProblems(pr.length > 0); } }, "Check"),
      h("span", { class: "sep" }), clockControls(),
      h("span", { class: "grow" }),
      this.legend());
    this.canvas = h("div", { class: "canvas", tabindex: "0", "aria-label": "Schematic sheet" });
    this.svg = s("svg", { class: "view", role: "application", "aria-roledescription": "schematic editor" });
    this.world = s("g");
    this.svg.append(gridPattern("sgrid"), this.world);
    this.vp = new Viewport(this.svg, this.world, { min: 0.15, max: 5 });
    this.help = h("div", { class: "overlay-help" });
    this.inspector = h("div", { class: "inspector", hidden: true });
    this.canvas.append(this.svg, this.help, this.inspector, zoomControls(this.vp, () => this.fit()));
    this.root.append(tb, this.canvas);
    this.svg.addEventListener("pointerdown", (e) => this.onDown(e));
    this.svg.addEventListener("pointermove", (e) => this.onMove(e));
    this.svg.addEventListener("dblclick", (e) => this.onDbl(e));
    this.canvas.addEventListener("keydown", (e) => this.onKey(e));
    this.canvas.addEventListener("dragover", (e) => e.preventDefault());
    this.canvas.addEventListener("drop", (e) => {
      e.preventDefault();
      const t = e.dataTransfer.getData("text/x-bbench-type");
      if (t) { const [x, y] = this.vp.toWorld(e.clientX, e.clientY); this.addPart(t, x, y); }
    });
    this.setTool("select");
  }
  legend() {
    const it = (cls, txt, extra = {}) => h("span", { class: "leg", title: txt }, h("i", { class: cls, ...extra }), txt);
    return h("span", { class: "legend", "aria-label": "Wire colours" }, it("lv1", "1"), it("lv0", "0"), it("lvz", "Z (floating)"), it("lvx", "X (unknown or fight)"));
  }
  setLive(on) {
    simctl.live = on;
    simctl.emit("clock", simctl.clockInfo());
    simctl.kick();
    this.liveBtn.setAttribute("aria-pressed", String(on));
    this.liveBtn.textContent = on ? "● Simulate" : "○ Simulate";
    this.paintState();
  }
  setTool(t) {
    this.tool = t;
    this.armed = null;
    this.placing = t === "place" ? this.placing : null;
    for (const b of this.toolSeg.children) b.setAttribute("aria-pressed", String(b.dataset.tool === t));
    this.svg.style.cursor = t === "wire" || t === "label" ? "crosshair" : t === "place" ? "copy" : "default";
    this.updateHelp();
    this.drawGhost(null);
    this.render();
  }
  updateHelp() {
    const msg = {
      select: "Drag parts to move them · click a switch to flip it · drag the sheet to pan · wheel to zoom · R rotates · Delete removes",
      wire: this.armed ? `Wiring from ${this.armed.id} pin ${this.armed.pin} — click another pin (Esc to stop)` : "Click a pin to start a wire",
      label: "Click a pin to give its net a name (BUS0, CLK, …)",
      place: `Click on the sheet to place ${this.placing} (Esc to stop)`,
    }[this.tool];
    this.help.textContent = msg;
  }
  defaultSheet() {
    const mods = this.modules();
    return mods.length ? mods[0] : "All";
  }
  modules() {
    const m = [];
    for (const p of store.project.parts) { const x = p.props && p.props.module; if (x && !m.includes(x)) m.push(x); }
    return m;
  }
  visibleParts() {
    const p = store.project;
    return this.sheet === "All" ? p.parts : p.parts.filter((x) => (x.props && x.props.module) === this.sheet);
  }

  // Parts without a position (a netlist made by a script) get one: chips in columns, passives below.
  // Only a fallback: the engine's built-in projects (PC-2, its modules) come with positions sized
  // for these symbols (bbench/projects/sheet.py), so they are drawn as they are.
  autoLayout() {
    const p = store.project;
    let need = p.parts.filter((x) => x.x == null || x.y == null);
    // fallback: a netlist made by a script (no drawn wires) whose positions do not suit these symbols
    if (!need.length && !p.schematic.wires.length && this.crowded()) need = p.parts;
    if (!need.length) return;
    const groups = {};
    for (const x of need) (groups[(x.props && x.props.module) || "All"] ||= []).push(x);
    for (const list of Object.values(groups)) {
      const chips = list.filter((x) => (getDef(x.type) || {}).kind === "chip");
      const other = list.filter((x) => !chips.includes(x));
      const colX = [140, 540, 940];
      const colY = [40, 40, 40];
      for (const c of chips) {
        const k = colY.indexOf(Math.min(...colY));
        c.x = colX[k]; c.y = colY[k]; c.rot = 0;
        colY[k] += symbol(c).h + 40;
      }
      let y = Math.max(...colY) + 40, x = 60, rowH = 0;
      for (const o of other) {
        const sym = symbol(o);
        const [l, r] = this.tagRoom(o);
        const w = l + sym.w + r + 30;
        if (x + w > 1300) { x = 60; y += rowH + 40; rowH = 0; }
        o.x = snap(x + l); o.y = snap(y - sym.y0); o.rot = 0;
        x += w;
        rowH = Math.max(rowH, sym.h + 30);
      }
      for (const q of list) { q.x = snap(q.x); q.y = snap(q.y); }
    }
  }

  // room the net tags need on each side of a part (they are drawn at pins without wires)
  tagRoom(part) {
    const idx = pinNetIndex(store.project);
    let l = 30, r = 30;
    for (const pp of symbol(part).pins) {
      const net = idx.get(pkey(part.id, pp.pin));
      if (!net) continue;
      const w = 30 + 6.4 * net.length * 9.5 / 10.5 + 8;
      if (pp.side === "L") l = Math.max(l, w); else if (pp.side === "R") r = Math.max(r, w);
    }
    return [l, r];
  }
  // do the given positions make parts (with their tags) overlap?
  crowded() {
    const parts = store.project.parts.filter((x) => x.x != null);
    if (parts.length < 4) return false;
    const boxes = parts.map((q) => { const b = partBBox(q); const [l, r] = this.tagRoom(q); return { x: b.x - l + 22, y: b.y, w: b.w + l + r - 44, h: b.h, m: (q.props && q.props.module) || "" }; });
    let hits = 0;
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], c = boxes[j];
      if (a.m !== c.m) continue;
      if (a.x < c.x + c.w - 4 && c.x < a.x + a.w - 4 && a.y < c.y + c.h - 4 && c.y < a.y + a.h - 4) { hits++; break; }
    }
    return hits > parts.length * 0.05;
  }

  // ------------------------------------------------------------------ rendering
  render() {
    const p = store.project;
    const mods = this.modules();
    clear(this.sheetSel);
    this.sheetSel.append(h("option", { value: "All" }, mods.length ? "All modules" : "Sheet 1"));
    for (const m of mods) this.sheetSel.append(h("option", { value: m }, m));
    if (this.sheet !== "All" && !mods.includes(this.sheet)) this.sheet = "All";
    this.sheetSel.value = this.sheet;
    this.sheetSel.hidden = !mods.length;

    clear(this.world);
    this.netEls = new Map();
    this.partEls = new Map();
    this.world.append(s("rect", { x: -20000, y: -20000, width: 40000, height: 40000, fill: "url(#sgrid)", class: "sheet-bg-grid" }));
    const idx = pinNetIndex(p);
    this.idx = idx;
    const parts = this.visibleParts();
    const visible = new Set(parts.map((x) => x.id));
    this.pinPos = new Map();
    for (const part of parts) for (const pp of pinPositions(part)) this.pinPos.set(pkey(part.id, pp.pin), pp);

    // wires
    const wired = new Set();
    const wl = s("g", { class: "wires" });
    const ends = new Map();
    for (const w of p.schematic.wires) {
      if (!w.a || !w.b || !visible.has(w.a[0]) || !visible.has(w.b[0])) continue;
      const pa = this.pinPos.get(pkey(...w.a)), pb = this.pinPos.get(pkey(...w.b));
      if (!pa || !pb) continue;
      w.points = route(pa, pb);
      wired.add(pkey(...w.a)); wired.add(pkey(...w.b));
      const d = "M" + w.points.map((q) => q.join(" ")).join(" L");
      const hit = s("path", { d, class: "wire-hit" });
      const path = s("path", { d, class: "wire" + (this.sel && this.sel.kind === "wire" && this.sel.w === w ? " selected" : ""), style: `stroke:${netColour(w.net)}`, "data-net": w.net });
      const g = s("g", { "data-wire": "1" }, hit, path, s("title", {}, `${w.net}`));
      g.__wire = w;
      wl.append(g);
      this.addNetEl(w.net, path);
      for (const q of [w.points[0], w.points[w.points.length - 1]]) { const k = q.join(","); ends.set(k, (ends.get(k) || 0) + 1); }
    }
    // junction dots where three or more wire ends meet
    for (const [k, n] of ends) if (n >= 2) {
      const [x, y] = k.split(",").map(Number);
      const net = [...this.pinPos.values()].find((q) => q.wx === x && q.wy === y);
      if (n >= 2 && net) { /* a pin with two wires: the pin itself is the junction */ }
      if (n >= 3) wl.append(s("circle", { cx: x, cy: y, r: 3.2, class: "junction", fill: "var(--ink)" }));
    }
    // labels placed freely on the sheet
    const ll = s("g", { class: "labels" });
    p.schematic.labels.forEach((l, i) => {
      if (l.pin && !visible.has(l.pin[0])) return;
      if (l.pin) { wired.add(pkey(...l.pin)); }
      if (this.sheet !== "All" && !l.pin) return;
      const at = l.pin ? this.pinPos.get(pkey(...l.pin)) : null;
      const x = at ? at.wx : l.x, y = at ? at.wy : l.y;
      if (at) { l.x = x; l.y = y; }
      const side = at ? sideOf(at) : "R";
      const t = tagEl(l.net, x, y, side, 10.5, true);
      t.__label = l;
      t.dataset.label = String(i);
      ll.append(t);
      this.addNetEl(l.net, t);
    });
    const pl = s("g", { class: "parts" });
    const tl = s("g", { class: "tags" });
    for (const part of parts) {
      const g = this.drawPart(part, idx, wired);
      pl.append(g);
      tl.append(g.__tags);
      this.partEls.set(part.id, g);
    }
    this.markerLayer = s("g", { class: "markers" });
    this.ghost = s("path", { class: "ghostwire", d: "" });
    this.world.append(wl, pl, tl, ll, this.markerLayer, this.ghost);
    this.paintState();
    this.paintMarkers();
    this.renderInspector();
  }
  addNetEl(net, el) { if (!this.netEls.has(net)) this.netEls.set(net, []); this.netEls.get(net).push(el); }

  drawPart(part, idx, wired) {
    const sym = symbol(part);
    const rot = part.rot || 0;
    const g = s("g", { class: "part" + (this.sel && this.sel.kind === "part" && this.sel.id === part.id ? " selected" : ""), "data-part": part.id,
                       transform: `translate(${part.x || 0} ${part.y || 0}) rotate(${rot})`, role: "group", "aria-label": `${part.id} ${part.type}` });
    const tg = s("g", { class: "ptags", transform: `translate(${part.x || 0} ${part.y || 0})` });
    g.__tags = tg;
    g.append(s("rect", { x: sym.x0 - 4, y: sym.y0 - 4, width: sym.w + 8, height: sym.h + 8, class: "selbox", rx: 6 }));
    g.append(s("rect", { x: sym.x0, y: sym.y0, width: sym.w, height: sym.h, class: "hit" }));
    const body = s("g", { class: "body" });
    body.append(sym.body(this.bodyCtx(part)));
    g.append(body);
    // pin stubs, numbers, tags and hot spots
    for (const pp of sym.pins) {
      const net = idx.get(pkey(part.id, pp.pin));
      if (pp.x !== pp.sx || pp.y !== pp.sy) {
        const stub = s("line", { x1: pp.sx, y1: pp.sy, x2: pp.x, y2: pp.y, class: "pinline", "data-net": net || "" });
        g.append(stub);
        if (net) this.addNetEl(net, stub);
        if (sym.chip) {
          const left = pp.side === "L";
          const t = s("text", { x: left ? pp.x + 17 : pp.x - 17, y: pp.y - 3, class: "t-ink2 t-mono", "font-size": 8.5, "text-anchor": left ? "end" : "start", "data-rt": "1" }, pp.pin);
          g.append(t);
        }
      }
      if (net && !wired.has(pkey(part.id, pp.pin))) {
        const [dx, dy] = rotPt(...({ L: [-1, 0], R: [1, 0], T: [0, -1], B: [0, 1] }[pp.side] || [pp.x - pp.sx, pp.y - pp.sy]), rot);
        const side = Math.abs(dx) >= Math.abs(dy) ? (dx < 0 ? "L" : "R") : dy < 0 ? "T" : "B";
        // tags live in an unrotated group that moves with the part, so their text stays upright
        const [wx, wy] = rotPt(pp.x, pp.y, rot);
        const t = tagEl(net, wx, wy, side, 9.5);
        tg.append(t);
        this.addNetEl(net, t);
      }
      const hot = s("circle", { cx: pp.x, cy: pp.y, r: 5.5, class: "pin-hot" + (this.armed && this.armed.id === part.id && this.armed.pin === pp.pin ? " armed" : ""),
                                "data-pin": pp.pin });
      hot.append(s("title", {}, `${part.id} pin ${pp.pin}${pp.name !== pp.pin ? " (" + pp.name + ")" : ""}${net ? " · " + net : " · not connected"}`));
      g.append(hot);
    }
    counterRotate(g, rot);
    return g;
  }
  bodyCtx(part) {
    const st = simctl.state || {};
    const ctx = { part, ctl: simctl.ctl[part.id] };
    const t = baseType(part.type);
    if (t === "LED") ctx.lit = simctl.live && !!(st.leds && st.leds[part.id]);
    if (/^7SEG/.test(t)) ctx.digit = simctl.live && st.digits ? st.digits[part.id] : null;
    if (t === "PROBE") {
      const net = this.idx && this.idx.get(pkey(part.id, pinNo(getDef(part.type), "TIP")));
      const pv = st.probes && part.id in st.probes ? st.probes[part.id] : net && st.nets ? st.nets[net] : "Z";
      ctx.probe = simctl.live ? vtext(pv) || "Z" : null;
    }
    return ctx;
  }
  // recolour by value without rebuilding the sheet
  paintState() {
    const st = simctl.state || {};
    const nets = (simctl.live && st.nets) || {};
    for (const [net, els] of this.netEls) {
      const v = simctl.live ? vclass(nets[net]) : "";
      for (const el of els) {
        const base = el.getAttribute("class").replace(/\s?v[01zx]\b/g, "");
        el.setAttribute("class", v ? `${base} ${v}` : base);
        if (el.classList.contains("tag")) {
          const b = el.querySelector(".valbadge");
          if (b) { b.textContent = simctl.live ? vtext(nets[net]) : ""; b.setAttribute("class", `valbadge ${v}`); }
        }
      }
    }
    // parts whose look depends on the simulation
    for (const part of this.visibleParts()) {
      if (!LIVE_TYPES.test(baseType(part.type))) continue;
      const g = this.partEls.get(part.id);
      if (!g) continue;
      const body = g.querySelector(":scope > .body");
      clear(body);
      body.append(symbol(part).body(this.bodyCtx(part)));
      counterRotate(body, part.rot || 0);
    }
  }
  paintMarkers() {
    if (!this.markerLayer) return;
    clear(this.markerLayer);
    const list = [...(simctl.problems || [])];
    for (const e of (simctl.state && simctl.state.errors) || []) list.push(typeof e === "object" ? e : { severity: "error", message: String(e), where: guessWhere(String(e)) });
    const seen = new Map();
    const said = new Set();
    for (const pr of list) {
      if (said.has(pr.message)) continue;
      said.add(pr.message);
      const w = normWhere(pr.where);
      if (w.part && !w.pin && w.pins && w.pins.length) { const pt = partById(store.project, w.part); w.pin = pt ? pinNo(getDef(pt.type), w.pins[0]) : null; }
      const ids = w.part ? [w.part] : w.parts || [];
      for (const pid of ids.slice(0, 8)) {
      let x, y;
      if (!this.partEls.has(pid)) continue;
      const part = partById(store.project, pid);
      const pp = w.pin && w.part && this.pinPos.get(pkey(pid, w.pin));
      if (pp) { x = pp.wx; y = pp.wy; }
      else { const b = partBBox(part); x = b.x + b.w - 8; y = b.y + 6; }
      const k = `${x},${y}`;
      const n = (seen.get(k) || 0);
      seen.set(k, n + 1);
      const g = s("g", { class: `marker ${pr.severity === "warning" ? "warning" : pr.severity === "info" ? "warning" : ""}`, transform: `translate(${x + n * 14} ${y - 12})` });
      g.append(s("circle", { r: 7.5 }), s("text", { y: 4, "text-anchor": "middle" }, "!"), s("title", {}, pr.message));
      this.markerLayer.append(g);
      }
    }
  }

  // ------------------------------------------------------------------ interaction
  hitInfo(e) {
    const t = e.target;
    const partG = t.closest("[data-part]");
    return {
      part: partG ? partG.dataset.part : null,
      pin: t.classList && t.classList.contains("pin-hot") ? t.dataset.pin : null,
      op: t.closest("[data-op]"),
      wire: t.closest("[data-wire]"),
      label: t.closest("[data-label]"),
      tag: t.closest(".tag"),
    };
  }
  onDown(e) {
    this.canvas.focus({ preventScroll: true });
    if (e.button === 1 || (e.button === 0 && e.shiftKey && this.tool === "select" && !e.target.closest("[data-part]"))) { this.vp.pan(e); return; }
    if (e.button !== 0) return;
    const hi = this.hitInfo(e);
    const [wx, wy] = this.vp.toWorld(e.clientX, e.clientY);
    if (this.tool === "place") { this.addPart(this.placing, wx, wy); if (!e.ctrlKey && !e.metaKey) this.setTool("select"); return; }
    if (hi.pin && hi.part) {
      if (this.tool === "label") { this.labelPin(hi.part, hi.pin); return; }
      // a pin always starts or finishes a wire, whatever the tool
      if (this.armed) { this.finishWire(hi.part, hi.pin); return; }
      this.armed = { id: hi.part, pin: hi.pin };
      this.dragWireFrom = { x: e.clientX, y: e.clientY };
      this.updateHelp();
      this.render();
      const up = (ev) => {
        window.removeEventListener("pointerup", up);
        const moved = Math.hypot(ev.clientX - this.dragWireFrom.x, ev.clientY - this.dragWireFrom.y) > 6;
        if (!moved) return;            // click-click wiring
        const el = document.elementFromPoint(ev.clientX, ev.clientY);
        const pg = el && el.closest && el.closest("[data-part]");
        if (el && el.classList.contains("pin-hot") && pg) this.finishWire(pg.dataset.part, el.dataset.pin);
        else { this.armed = null; this.drawGhost(null); this.updateHelp(); this.render(); }
      };
      window.addEventListener("pointerup", up);
      return;
    }
    if (this.armed) { this.armed = null; this.drawGhost(null); this.updateHelp(); this.render(); return; }
    if (hi.op && hi.part && simctl.live) { this.operate(hi.part, hi.op, e); return; }
    if (hi.part) { this.select({ kind: "part", id: hi.part }); this.dragPart(e, hi.part); return; }
    if (hi.wire) { this.select({ kind: "wire", w: hi.wire.__wire, net: hi.wire.__wire.net }); return; }
    if (hi.label) { const l = hi.label.__label; this.select({ kind: "net", net: l.net, label: l }); return; }
    if (hi.tag) { this.select({ kind: "net", net: hi.tag.dataset.net }); return; }
    this.select(null);
    this.vp.pan(e);
  }
  onMove(e) {
    if (this.armed) {
      const a = this.pinPos.get(pkey(this.armed.id, this.armed.pin));
      if (!a) return;
      const [x, y] = this.vp.toWorld(e.clientX, e.clientY);
      this.drawGhost(route(a, { wx: snap(x), wy: snap(y), wsx: snap(x), wsy: snap(y) }));
    }
  }
  drawGhost(pts) { if (this.ghost) this.ghost.setAttribute("d", pts ? "M" + pts.map((q) => q.join(" ")).join(" L") : ""); }
  onDbl(e) {
    const hi = this.hitInfo(e);
    if (hi.part && !hi.op) { this.select({ kind: "part", id: hi.part }); const f = this.inspector.querySelector("input"); if (f) f.focus(); }
  }
  onKey(e) {
    const op = e.target.closest && e.target.closest("[data-op]");
    if (op && (e.key === " " || e.key === "Enter")) {
      e.preventDefault();
      const pg = op.closest("[data-part]");
      if (pg && simctl.live) this.operate(pg.dataset.part, op.dataset.op === "press" ? null : op, null);
      return;
    }
    if (e.target !== this.canvas) return;
    const k = e.key;
    if (k === "Escape") { this.armed = null; this.setTool("select"); this.select(null); }
    else if (k === "Delete" || k === "Backspace") { e.preventDefault(); this.deleteSel(); }
    else if (k === "r" || k === "R") this.rotateSel(k === "R" ? -90 : 90);
    else if (k === "w" || k === "W") this.setTool("wire");
    else if (k === "l" || k === "L") this.setTool("label");
    else if (k === "v" || k === "V") this.setTool("select");
    else if (k === "f" || k === "F") this.fit();
    else if (k.startsWith("Arrow") && this.sel && this.sel.kind === "part") {
      e.preventDefault();
      const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[k];
      store.commit("move", (p) => { const q = partById(p, this.sel.id); q.x += d[0] * GRID; q.y += d[1] * GRID; }, "view");
    } else if ((k === " " || k === "Enter") && this.sel && this.sel.kind === "part") {
      const part = partById(store.project, this.sel.id);
      if (part && /^(SW|BUTTON|SPDT|JUMPER3)$/.test(baseType(part.type))) { e.preventDefault(); this.operate(part.id, null, null); }
    }
  }
  dragPart(e, id) {
    const part = partById(store.project, id);
    const x0 = part.x, y0 = part.y;
    const [sx, sy] = this.vp.toWorld(e.clientX, e.clientY);
    const g = this.partEls.get(id);
    let moved = false;
    const mv = (ev) => {
      const [x, y] = this.vp.toWorld(ev.clientX, ev.clientY);
      const nx = snap(x0 + x - sx), ny = snap(y0 + y - sy);
      if (nx !== part.x || ny !== part.y || moved) {
        moved = true;
        g.setAttribute("transform", `translate(${nx} ${ny}) rotate(${part.rot || 0})`);
        g.__tags.setAttribute("transform", `translate(${nx} ${ny})`);
        this._drag = [nx, ny];
      }
    };
    const up = () => {
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("pointerup", up);
      if (moved && this._drag) {
        const [nx, ny] = this._drag;
        this._drag = null;
        store.commit("move " + id, (p) => { const q = partById(p, id); q.x = nx; q.y = ny; }, "view");
      }
    };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
  }
  operate(id, opEl, e) {
    const part = partById(store.project, id);
    if (!part) return;
    const t = baseType(part.type);
    const op = opEl ? opEl.dataset.op : t === "BUTTON" ? "press" : t === "SPDT" || t === "JUMPER3" ? "throw" : "toggle";
    if (op === "toggle") simctl.toggle(id);
    else if (op === "throw") {
      const th = positions(part);
      simctl.setThrow(id, String(simctl.ctl[id]).toUpperCase() === String(th[0]).toUpperCase() ? th[1] : th[0]);
    } else if (op === "section") simctl.setSection(id, +opEl.dataset.sec, !(simctl.ctl[id] || [])[+opEl.dataset.sec - 1]);
    else if (op === "press") {
      if (!e) { simctl.press(id, 150); return; }
      simctl.setSwitch(id, true);
      const up = () => { window.removeEventListener("pointerup", up); simctl.setSwitch(id, false); };
      window.addEventListener("pointerup", up);
    }
  }
  finishWire(id, pin) {
    const a = this.armed;
    this.armed = null;
    this.drawGhost(null);
    if (!a || (a.id === id && a.pin === pin)) { this.render(); this.updateHelp(); return; }
    store.commit("wire", (p) => {
      const net = connectPins(p, [a.id, a.pin], [id, String(pin)]);
      p.schematic.wires.push({ net, points: [], a: [a.id, a.pin], b: [id, String(pin)] });
    });
    // keep going from the new pin when using the wire tool (Esc to stop)
    if (this.tool === "wire") this.updateHelp();
    else this.updateHelp();
  }
  async labelPin(id, pin) {
    const cur = pinNetIndex(store.project).get(pkey(id, pin));
    const name = await askText("Net name", cur && !/^N\d+$/.test(cur) ? cur : "", { hint: `The net at ${id} pin ${pin}. Pins with the same net name are connected.`, pattern: /^[A-Za-z_][\w~+-]*$/ });
    if (!name) return;
    store.commit("label", (p) => {
      if (cur) renameNet(p, cur, name);
      attachPin(p, id, pin, name);
      if (!p.schematic.labels.some((l) => l.pin && l.pin[0] === id && l.pin[1] === pin)) {
        const pp = this.pinPos.get(pkey(id, pin));
        p.schematic.labels.push({ net: name, x: pp ? pp.wx : 0, y: pp ? pp.wy : 0, pin: [id, String(pin)] });
      } else for (const l of p.schematic.labels) if (l.pin && l.pin[0] === id && l.pin[1] === pin) l.net = name;
    });
  }
  addPart(type, x, y) {
    const def = getDef(type);
    if (!def) { toast(`Unknown part ${type}`); return; }
    let id;
    store.commit("add " + type, (p) => {
      id = newPartId(p, prefixFor(type));
      const part = { id, type, x: 0, y: 0, rot: 0, props: { ...(def.props || {}) } };
      if (this.sheet !== "All") part.props.module = this.sheet;
      const sym = symbol(part);
      part.x = snap(x - sym.w / 2); part.y = snap(y - sym.y0 - sym.h / 2);
      p.parts.push(part);
      // chips: power pins go to the rails, as on the real board
      for (const [n, , kind] of def.pins) {
        if (kind === "vcc") attachPin(p, id, n, "VCC");
        if (kind === "gnd") attachPin(p, id, n, "GND");
      }
    });
    this.select({ kind: "part", id });
    return id;
  }
  startPlace(type) { this.placing = type; this.setTool("place"); this.app.showTab("schematic"); this.canvas.focus(); }
  rotateSel(d = 90) {
    if (!this.sel || this.sel.kind !== "part") return;
    store.commit("rotate", (p) => { const q = partById(p, this.sel.id); q.rot = (((q.rot || 0) + d) % 360 + 360) % 360; }, "view");
  }
  deleteSel() {
    const sl = this.sel;
    if (!sl) return;
    if (sl.kind === "part") store.commit("delete " + sl.id, (p) => deletePart(p, sl.id));
    else if (sl.kind === "wire") store.commit("delete wire", (p) => { const w = p.schematic.wires.find((x) => sameWire(x, sl.w)); if (w) deleteWire(p, w); });
    else if (sl.kind === "net" && sl.label) store.commit("delete label", (p) => {
      p.schematic.labels = p.schematic.labels.filter((l) => !(l.net === sl.label.net && l.x === sl.label.x && l.y === sl.label.y));
      if (sl.label.pin) detachPin(p, sl.label.pin[0], sl.label.pin[1]);
      pruneNets(p);
    });
    this.select(null);
  }
  select(sel) {
    this.sel = sel;
    for (const g of this.world.querySelectorAll(".part.selected")) g.classList.remove("selected");
    for (const w of this.world.querySelectorAll(".wire.selected")) w.classList.remove("selected");
    if (sel && sel.kind === "part") { const g = this.partEls.get(sel.id); if (g) g.classList.add("selected"); }
    if (sel && sel.kind === "wire") for (const g of this.world.querySelectorAll("[data-wire]")) if (g.__wire === sel.w) g.querySelector(".wire").classList.add("selected");
    if (sel && sel.kind === "part") this.app.library.show(partById(store.project, sel.id)?.type, true);
    this.renderInspector();
  }
  fit() {
    const parts = this.visibleParts();
    if (!parts.length) { this.vp.k = 1; this.vp.tx = 40; this.vp.ty = 40; this.vp.apply(); return; }
    let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
    for (const p of parts) { const b = partBBox(p); x1 = Math.min(x1, b.x - 90); y1 = Math.min(y1, b.y); x2 = Math.max(x2, b.x + b.w + 90); y2 = Math.max(y2, b.y + b.h); }
    this.vp.fit({ x: x1, y: y1, w: x2 - x1, h: y2 - y1 }, 30, 1.4);
  }
  focusPart(id) {
    const part = partById(store.project, id);
    if (!part) return;
    const mod = part.props && part.props.module;
    if (mod && this.sheet !== "All" && this.sheet !== mod) { this.sheet = mod; this.render(); }
    const b = partBBox(part);
    this.vp.centreOn(b.x + b.w / 2, b.y + b.h / 2);
    this.select({ kind: "part", id });
  }

  // ------------------------------------------------------------------ inspector
  renderInspector() {
    const el = this.inspector;
    clear(el);
    const sl = this.sel;
    if (!sl) { el.hidden = true; return; }
    el.hidden = false;
    const p = store.project;
    if (sl.kind === "part") {
      const part = partById(p, sl.id);
      if (!part) { el.hidden = true; return; }
      const def = getDef(part.type) || {};
      const idIn = h("input", { class: "input mono", value: part.id, "aria-label": "Part name" });
      idIn.onchange = () => {
        const nid = idIn.value.trim();
        if (!/^[A-Za-z_][\w.]*$/.test(nid) || partById(p, nid)) { idIn.value = part.id; toast("That name is taken or not allowed."); return; }
        store.commit("rename part", (q) => renamePart(q, part.id, nid));
        this.sel = { kind: "part", id: nid };
        this.renderInspector();
      };
      el.append(h("h4", {}, `${part.id}`), h("div", { class: "sub" }, `${part.type} · ${def.desc || ""}`), h("label", {}, "Name"), idIn);
      const prop = (key, label, opts) => {
        el.append(h("label", {}, label));
        let inp;
        if (opts) { inp = h("select", { class: "input" }, ...opts.map((o) => h("option", { value: o, selected: (part.props[key] || "") === o }, o))); }
        else inp = h("input", { class: "input mono", value: part.props[key] ?? "", "aria-label": label });
        inp.onchange = () => store.commit(`edit ${label}`, (q) => { const x = partById(q, part.id); x.props[key] = key === "period_ns" ? +inp.value : inp.value; });
        el.append(inp);
      };
      const bt = baseType(part.type);
      if (["R", "C", "POT"].includes(bt) || /^RN/.test(bt)) prop("value", "Value");
      if (bt === "LED") prop("colour", "Colour", ["red", "green", "yellow", "blue", "white"]);
      if (bt === "CLOCK") prop("period_ns", "Period (ns)");
      if (part.props.label !== undefined || def.kind === "chip") prop("label", "Note");
      const pins = h("div", { class: "pins", role: "list", "aria-label": "Pins and nets" });
      const idx = pinNetIndex(p);
      for (const pp of pinList(part)) {
        const net = idx.get(pkey(part.id, pp.pin));
        const row = h("div", { role: "listitem" }, h("span", {}, `${pp.pin} ${pp.name !== pp.pin ? pp.name : ""}`), h("span", { style: { color: net ? "var(--ink)" : "var(--ink3)" } }, net || "—"));
        if (net) { row.style.cursor = "pointer"; row.onclick = () => this.select({ kind: "net", net }); }
        pins.append(row);
      }
      el.append(h("label", {}, "Pins"), pins,
        h("div", { class: "row" },
          h("button", { class: "btn", onclick: () => this.rotateSel() }, "⟳ Rotate"),
          h("button", { class: "btn", onclick: () => this.deleteSel() }, "Delete"),
          def.datasheet ? h("a", { class: "btn ghost", href: def.datasheet, target: "_blank", rel: "noopener" }, "Datasheet ↗") : null));
    } else {
      const net = sl.net;
      const n = netByName(p, net);
      const v = simctl.state && simctl.state.nets ? vtext(simctl.state.nets[net]) : "";
      const nameIn = h("input", { class: "input mono", value: net, "aria-label": "Net name" });
      nameIn.onchange = () => {
        const nn = nameIn.value.trim();
        if (!/^[A-Za-z_][\w~+-]*$/.test(nn)) { nameIn.value = net; return; }
        store.commit("rename net", (q) => renameNet(q, net, nn));
        this.sel = { kind: sl.kind, net: nn, w: sl.w };
        this.renderInspector();
      };
      el.append(h("h4", {}, sl.kind === "wire" ? "Wire" : "Net"), h("div", { class: "sub" }, `${n ? n.pins.length : 0} pins${v ? " · value " + v : ""}`),
        h("label", {}, "Net name"), nameIn);
      const pins = h("div", { class: "pins" });
      for (const [a, b] of (n ? n.pins : [])) { const r = h("div", {}, h("span", {}, a), h("span", {}, `pin ${b}`)); r.style.cursor = "pointer"; r.onclick = () => this.focusPart(a); pins.append(r); }
      el.append(h("label", {}, "Pins on this net"), pins,
        h("div", { class: "row" },
          h("button", { class: "btn", title: "Show this net in the logic analyser", onclick: () => { store.commit("probe", (q) => { if (!q.probes.includes(net)) q.probes.push(net); }, "view"); toast(`${net} added to the analyser`); } }, "+ Probe"),
          sl.kind === "wire" || sl.label ? h("button", { class: "btn", onclick: () => this.deleteSel() }, "Delete") : null));
    }
  }
}

// ---------------------------------------------------------------------- helpers
const LIVE_TYPES = /^(LED|7SEG.*|PROBE|SW|BUTTON|SPDT|JUMPER3|DIPSW\d+)$/;
function sameWire(a, b) { return a && b && a.net === b.net && JSON.stringify(a.a) === JSON.stringify(b.a) && JSON.stringify(a.b) === JSON.stringify(b.b); }

export function renamePart(p, from, to) {
  for (const x of p.parts) if (x.id === from) x.id = to;
  for (const n of p.nets) for (const pin of n.pins) if (pin[0] === from) pin[0] = to;
  for (const w of p.schematic.wires) { if (w.a && w.a[0] === from) w.a[0] = to; if (w.b && w.b[0] === from) w.b[0] = to; }
  for (const l of p.schematic.labels) if (l.pin && l.pin[0] === from) l.pin[0] = to;
  for (const bb of p.breadboards) for (const pl of bb.placements || []) if (pl.part === from) pl.part = to;
  for (const st of p.stimuli) if (st.part === from) st.part = to;
  if (from in simctl.ctl) { simctl.ctl[to] = simctl.ctl[from]; delete simctl.ctl[from]; }
}

function sideOf(pp) {
  const dx = pp.dx || pp.wx - pp.wsx, dy = pp.dy || pp.wy - pp.wsy;
  return Math.abs(dx) >= Math.abs(dy) ? (dx < 0 ? "L" : "R") : dy < 0 ? "T" : "B";
}

// Orthogonal route between two pins: out of each pin along its own direction, then an L or Z bend.
export function route(a, b) {
  const da = dirOf(a), db = dirOf(b);
  const A = [a.wx, a.wy], B = [b.wx, b.wy];
  const A1 = [A[0] + da[0] * 10, A[1] + da[1] * 10];
  const B1 = [B[0] + db[0] * 10, B[1] + db[1] * 10];
  let mid;
  if (da[0] !== 0 && db[0] !== 0) {
    const mx = snap((A1[0] + B1[0]) / 2);
    if ((da[0] > 0 && mx < A1[0]) || (da[0] < 0 && mx > A1[0]) || (db[0] > 0 && mx < B1[0]) || (db[0] < 0 && mx > B1[0])) {
      const my = snap((A1[1] + B1[1]) / 2);
      mid = [[A1[0], my], [B1[0], my]];
    } else mid = [[mx, A1[1]], [mx, B1[1]]];
  } else if (da[1] !== 0 && db[1] !== 0) {
    const my = snap((A1[1] + B1[1]) / 2);
    mid = [[A1[0], my], [B1[0], my]];
  } else if (da[0] !== 0) mid = [[B1[0], A1[1]]];
  else mid = [[A1[0], B1[1]]];
  return simplify([A, A1, ...mid, B1, B]);
}
function dirOf(p) {
  if (p.dx != null && (p.dx || p.dy)) return [p.dx, p.dy];
  const dx = p.wx - (p.wsx ?? p.wx), dy = p.wy - (p.wsy ?? p.wy);
  if (!dx && !dy) return [0, 0];
  return Math.abs(dx) >= Math.abs(dy) ? [Math.sign(dx), 0] : [0, Math.sign(dy)];
}
function simplify(pts) {
  const out = [];
  for (const q of pts) {
    const last = out[out.length - 1];
    if (last && last[0] === q[0] && last[1] === q[1]) continue;
    out.push(q);
    while (out.length >= 3) {
      const [p1, p2, p3] = out.slice(-3);
      if ((p1[0] === p2[0] && p2[0] === p3[0]) || (p1[1] === p2[1] && p2[1] === p3[1])) out.splice(out.length - 2, 1);
      else break;
    }
  }
  return out;
}

// A net tag (the book's rounded flag holding a signal name) with a value badge for the simulation.
export function tagEl(net, x, y, side, size = 10, free = false) {
  const w = Math.max(18, 8 + 6.4 * net.length * size / 10.5);
  const g = s("g", { class: "tag", "data-net": net, role: "img", "aria-label": `net ${net}` });
  let x0, y0 = y - 8;
  if (side === "L") x0 = x - 2 - w;
  else if (side === "R") x0 = x + 2;
  else { x0 = x - w / 2; y0 = side === "T" ? y - 20 : y + 4; }
  if (free) { x0 = side === "L" ? x - w - 2 : x + 2; }
  g.append(s("rect", { x: x0, y: y0, width: w, height: 16, rx: 8, style: `fill:${netTint(net)};stroke:${netColour(net)}` }));
  g.append(s("text", { x: x0 + w / 2, y: y0 + 11.5, "font-size": size, "text-anchor": "middle" }, net));
  const bx = side === "L" ? x0 - 8 : x0 + w + 8;
  g.append(s("text", { x: bx, y: y0 + 11.5, class: "valbadge", "text-anchor": "middle" }, ""));
  return g;
}

function counterRotate(g, rot) {
  if (!rot) return;
  for (const t of g.querySelectorAll("[data-rt]")) {
    const x = +t.getAttribute("x"), y = +t.getAttribute("y");
    t.setAttribute("transform", `rotate(${-rot} ${x} ${y - 3})`);
  }
}
export { clamp };
