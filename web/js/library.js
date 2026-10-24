// Library side panel: every chip and part, searchable, with its pin-out card and function table.
import { h, s, clear } from "./util.js";
import { library, getDef } from "./parts.js";
import { tableFor } from "./functables.js";

const FAMILY_NAMES = { HCT: "74HCT logic", HC: "74HC logic", LS: "74LS logic", CMOS: "CMOS logic", memory: "Memory", timer: "Timers", part: "Parts and switches" };

export class Library {
  constructor(root, app) {
    this.root = root; this.app = app; this.sel = null; this.q = "";
    const head = h("div", { class: "lib-head" });
    this.count = h("small");
    head.append(h("h3", {}, "Library", this.count));
    this.search = h("input", { class: "input", type: "search", placeholder: "Search: 74HCT08, counter, LED…", "aria-label": "Search the library" });
    this.search.oninput = () => { this.q = this.search.value.trim().toLowerCase(); this.renderList(); };
    head.append(this.search);
    this.list = h("div", { class: "lib-list", role: "listbox", "aria-label": "Chips and parts" });
    this.detail = h("div", { class: "lib-detail", "aria-live": "polite" });
    root.append(head, this.list, this.detail);
    this.list.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      const items = [...this.list.querySelectorAll(".lib-item")];
      const i = items.indexOf(document.activeElement);
      const n = items[Math.max(0, Math.min(items.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
      if (n) { e.preventDefault(); n.focus(); n.click(); }
    });
  }
  refresh() { this.renderList(); if (this.sel) this.show(this.sel); else { const f = library().find((d) => d.type === "74HCT00") || library().find((d) => d.kind === "chip"); if (f) this.show(f.type); } }
  renderList() {
    clear(this.list);
    const all = library();
    const match = (d) => !this.q || `${d.type} ${d.desc} ${d.family}`.toLowerCase().includes(this.q);
    const items = all.filter(match);
    this.count.textContent = `${items.length} of ${all.length}`;
    const groups = {};
    for (const d of items) (groups[d.kind === "part" ? "part" : d.family || "other"] ||= []).push(d);
    const rank = (g) => ["HCT", "HC", "LS", "CMOS", "memory", "timer"].indexOf(g) + 1 || (g === "part" ? 99 : 50);
    const order = Object.keys(groups).sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
    for (const g of order) {
      this.list.append(h("div", { class: "lib-group", role: "presentation" }, FAMILY_NAMES[g] || g));
      for (const d of groups[g].sort((a, b) => a.type.localeCompare(b.type, undefined, { numeric: true }))) {
        const add = h("span", { class: "add btn", title: `Place ${d.type} on the schematic`, role: "button", "aria-label": `Place ${d.type}` }, "+ Place");
        const it = h("button", { class: "lib-item", role: "option", "aria-selected": String(this.sel === d.type), draggable: "true", "data-type": d.type },
          h("span", { class: "badge" + (d.kind === "part" ? " part" : "") }, d.kind === "part" ? d.type.slice(0, 4) : String(d.pins.length)),
          h("span", { class: "t" }, d.type), add, h("span", { class: "d" }, d.desc || ""));
        it.onclick = (e) => { if (e.target === add) this.app.schematic.startPlace(d.type); else this.show(d.type); };
        it.ondblclick = () => this.app.schematic.startPlace(d.type);
        it.ondragstart = (e) => { e.dataTransfer.setData("text/x-bbench-type", d.type); e.dataTransfer.effectAllowed = "copy"; };
        this.list.append(it);
      }
    }
  }
  show(type, fromSelection = false) {
    const d = getDef(type);
    if (!d) return;
    this.sel = d.type;
    for (const it of this.list.querySelectorAll(".lib-item")) it.setAttribute("aria-selected", String(it.dataset.type === d.type));
    if (fromSelection) { const it = this.list.querySelector(`[data-type="${CSS.escape(d.type)}"]`); if (it) it.scrollIntoView({ block: "nearest" }); }
    clear(this.detail);
    this.detail.append(h("h4", {}, d.type), h("div", { class: "desc" }, d.desc || ""));
    const meta = h("div", { class: "meta" });
    if (d.family) meta.append(h("span", {}, `Family: ${d.family}`));
    meta.append(h("span", {}, `${d.pins.length} pins`));
    if (d.datasheet) meta.append(h("a", { href: d.datasheet, target: "_blank", rel: "noopener" }, "Datasheet ↗"));
    this.detail.append(meta, h("button", { class: "btn", style: { marginTop: "8px" }, onclick: () => this.app.schematic.startPlace(d.type) }, "+ Place on the schematic"));
    if (d.kind === "chip" && d.pins.length % 2 === 0) {
      this.detail.append(h("h5", {}, "Pin-out"), h("div", { class: "card" }, pinoutCard(d)));
    } else {
      this.detail.append(h("h5", {}, "Pins"));
      const tb = h("table", { class: "ft" }, h("tr", {}, h("th", {}, "Pin"), h("th", {}, "Name"), h("th", {}, "Kind")));
      for (const [n, name, kind] of d.pins) tb.append(h("tr", {}, h("td", {}, n), h("td", {}, name), h("td", { class: "n" }, kind)));
      this.detail.append(tb);
    }
    const t = tableFor(d);
    if (t) {
      this.detail.append(h("h5", {}, "Function table"));
      const sep = (i) => (t.split && i === t.split ? { style: { borderLeft: "2px solid var(--accent)" } } : {});
      const tb = h("table", { class: "ft" }, h("tr", {}, ...t.cols.map((c, i) => h("th", sep(i), c))));
      for (const r of t.rows) tb.append(h("tr", {}, ...r.map((c, i) => h("td", sep(i), c))));
      this.detail.append(tb);
      if (t.note) this.detail.append(h("p", { class: "desc", style: { fontSize: "12px" } }, t.note));
    }
    const tpd = Array.isArray(d.tpd) ? d.tpd : d.tpd ? Object.entries(d.tpd).map(([k, v]) => [...k.split(","), v]) : [];
    if (tpd.length) {
      this.detail.append(h("h5", {}, "Propagation delay"));
      const word = (x) => (x === "*" ? "any pin" : String(x).replace(/^\?/, ""));
      const tb = h("table", { class: "ft" }, h("tr", {}, h("th", {}, "From"), h("th", {}, "To"), h("th", {}, "ns, worst case")));
      for (const [a, b, ns] of tpd) tb.append(h("tr", {}, h("td", {}, word(a)), h("td", {}, word(b)), h("td", {}, ns)));
      for (const [a, b, ns] of d.tdis || []) tb.append(h("tr", {}, h("td", {}, word(a)), h("td", {}, `${word(b)} (turning off)`), h("td", {}, ns)));
      this.detail.append(tb);
      const small = (text) => h("p", { class: "desc", style: { fontSize: "12px" } }, text);
      const nsList = (v) => (v && typeof v === "object" ? [...new Set(Object.values(v))].join("/") : String(v || 0));
      const clocked = d.edge && Object.keys(d.edge).length;
      if (clocked && (d.setup || d.hold)) this.detail.append(small(`Set-up time before the clock edge: ${nsList(d.setup)} ns; hold time after it: ${nsList(d.hold)} ns.`));
      if (d.addr_hold != null) this.detail.append(small(`After an address change the old data stays for ${d.addr_hold} ns (tOH); the outputs are not valid again until the access time. The timed simulator shows them as unknown (X) in between.`));
      if (d.drive) this.detail.append(small(`Output drive: specified at ±${d.drive.test_mA} mA (a test condition); absolute maximum ±${d.drive.abs_max_mA} mA per output${d.drive.supply_abs_max_mA ? `, ±${d.drive.supply_abs_max_mA} mA through VCC or GND` : ""}.`));
      this.detail.append(small("Delays are datasheet maxima at VCC = 4.5 V, 25 °C (set-up and hold: minima)."));
    }
  }
}

// The book's DIP pin-out card: dark body, notch, pin numbers inside, names outside
export function pinoutCard(d) {
  const n = d.pins.length, half = n / 2, rowh = 20, W = 300, x = 110, w = 80;
  const H = half * rowh + 60;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${d.type} pin-out` });
  svg.append(s("title", {}, `${d.type} pin-out`));
  svg.append(s("rect", { x, y: 30, width: w, height: half * rowh + 10, rx: 4, fill: "var(--dip)", stroke: "#111" }));
  svg.append(s("path", { d: `M${x + w / 2 - 9} 30 A9 9 0 0 0 ${x + w / 2 + 9} 30`, fill: "#444", stroke: "#777", "stroke-width": 1.2 }));
  svg.append(s("text", { x: x + w / 2, y: 22, "text-anchor": "middle", "font-size": 13, "font-weight": 700, class: "t-ink" }, d.type));
  svg.append(s("circle", { cx: x + 12, cy: 40, r: 3, fill: "#BBB" }));
  const byNum = Object.fromEntries(d.pins.map((p) => [String(p[0]), p]));
  for (let p = 1; p <= n; p++) {
    const [, name, kind] = byNum[String(p)] || [p, "?", "nc"];
    const left = p <= half;
    const yy = 45 + (left ? p - 1 : n - p) * rowh;
    const px = left ? x - 10 : x + w;
    svg.append(s("rect", { x: px, y: yy - 5, width: 10, height: 10, rx: 1, fill: "#C9C9C9", stroke: "#777", "stroke-width": 0.6 }));
    svg.append(s("text", { x: left ? x + 6 : x + w - 6, y: yy + 4, "font-size": 10, fill: "#FFF", "text-anchor": left ? "start" : "end", class: "t-mono" }, String(p)));
    const col = kind === "vcc" ? "var(--pwr)" : kind === "gnd" ? "var(--ink2)" : kind === "clk" ? "var(--sig-clock)" : "var(--ink)";
    svg.append(s("text", { x: left ? x - 16 : x + w + 16, y: yy + 4, "font-size": 10.5, fill: col, "text-anchor": left ? "end" : "start", class: "t-mono", "font-weight": kind === "vcc" || kind === "gnd" ? 700 : 400 }, String(name)));
    svg.append(s("text", { x: left ? 6 : W - 6, y: yy + 4, "font-size": 8, class: "t-ink3", "text-anchor": left ? "start" : "end" }, kindWord(kind)));
  }
  return svg;
}
const kindWord = (k) => ({ in: "in", out: "out", tri: "out·Z", io: "in/out", clk: "clock", vcc: "+5 V", gnd: "GND", ana: "analogue", nc: "n.c." }[k] || k);
