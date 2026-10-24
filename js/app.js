// Breadboard Bench — the app shell: header, tabs, library, status bar, problems, examples, files.
import { h, clear, toast, download, storageGet, storageSet } from "./util.js";
import { engine } from "../engine.js";
import { store, emptyProject, normalise } from "./store.js";
import { setLibrary, clearSymbolCache } from "./parts.js";
import { simctl } from "./simctl.js";
import { Library } from "./library.js";
import { Schematic } from "./schematic.js";
import { Breadboard } from "./breadboard.js";
import { Analyser } from "./analyser.js";
import { FrontPanel } from "./frontpanel.js";
import { CodeTab } from "./code.js";
import { LOCAL, ENGINE_GROUP, moduleOf } from "./examples.js";
import { normWhere, whereText } from "./where.js";

const $ = (id) => document.getElementById(id);

class App {
  constructor() {
    this.tab = "schematic";
    window.bbench = this;              // handy for the console and for tests
    this.store = store; this.simctl = simctl; this.engine = engine;
  }
  async start() {
    this.initTheme();
    engine.on("status", (st) => this.showEngine(st));
    this.showEngine(engine.status);
    const lib = await engine.library();
    setLibrary(lib);
    this.library = new Library($("library"), this);
    this.schematic = new Schematic($("ws-schematic"), this);
    this.breadboard = new Breadboard($("ws-breadboard"), this);
    this.analyser = new Analyser($("ws-analyser"), this);
    this.panel = new FrontPanel($("ws-panel"), this);
    this.code = new CodeTab($("ws-code"), this);
    this.library.refresh();
    this.bindHeader();
    this.bindKeys();
    simctl.on("problems", (pr) => this.renderProblems(pr));
    simctl.on("state", (st) => this.showSimStatus(st));
    simctl.on("clock", () => this.showSimStatus(simctl.state || {}));
    store.on("change", () => this.showProject());
    engine.on("backend", async () => {
      setLibrary(await engine.library());
      clearSymbolCache();
      this.library.refresh();
      this.schematic.render();
      this.loadExampleMenu();
      toast("The Python engine is ready.");
    });
    // first project: the last one worked on, or the NAND example
    const saved = storageGet("bb-autosave");
    const tab = storageGet("bb-tab", "schematic");
    if (saved && saved.parts && saved.parts.length && !new URLSearchParams(location.search).has("fresh")) store.load(saved);
    else store.load(LOCAL[0].make());
    this.showTab(tab);
    this.loadExampleMenu();
    store.on("change", () => { this.autosaveSoon(); });
    engine.start();
    if ("serviceWorker" in navigator && location.protocol !== "file:" && !new URLSearchParams(location.search).has("nosw")) {
      navigator.serviceWorker.register("sw.js").catch((e) => console.warn("service worker:", e));
    }
    document.body.dataset.ready = "1";
  }

  // ------------------------------------------------------------------ header
  bindHeader() {
    $("btn-new").onclick = () => { if (this.confirmDiscard()) store.load(emptyProject()); };
    $("btn-open").onclick = () => $("file-input").click();
    $("file-input").onchange = async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      try {
        const p = JSON.parse(await f.text());
        if (!p.parts || !p.nets) throw new Error("this is not a Breadboard Bench project");
        store.load(p);
        toast(`Opened ${f.name}`);
      } catch (err) { toast(`Could not open ${f.name}: ${err.message}`, 5000); }
      e.target.value = "";
    };
    $("btn-save").onclick = () => this.save();
    $("btn-undo").onclick = () => this.undo();
    $("btn-redo").onclick = () => this.redo();
    $("btn-theme").onclick = () => this.toggleTheme();
    $("btn-lib").onclick = () => {
      const lib = $("library");
      lib.classList.toggle("collapsed");
      $("btn-lib").setAttribute("aria-pressed", String(!lib.classList.contains("collapsed")));
      storageSet("bb-lib", !lib.classList.contains("collapsed"));
    };
    if (storageGet("bb-lib", true) === false) { $("library").classList.add("collapsed"); $("btn-lib").setAttribute("aria-pressed", "false"); }
    const nm = $("proj-name");
    nm.onchange = () => store.commit("rename project", (p) => { p.name = nm.value.trim() || "Untitled"; }, "view");
    for (const t of document.querySelectorAll(".tab")) {
      t.onclick = () => this.showTab(t.dataset.tab);
      t.onkeydown = (e) => {
        const tabs = [...document.querySelectorAll(".tab")];
        const i = tabs.indexOf(t);
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") { const n = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length]; n.focus(); this.showTab(n.dataset.tab); }
      };
    }
    const exb = $("btn-examples"), menu = $("examples-menu");
    exb.onclick = (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; exb.setAttribute("aria-expanded", String(!menu.hidden)); if (!menu.hidden) menu.querySelector("button")?.focus(); };
    document.addEventListener("click", (e) => { if (!menu.contains(e.target)) { menu.hidden = true; exb.setAttribute("aria-expanded", "false"); } });
    menu.addEventListener("keydown", (e) => {
      const items = [...menu.querySelectorAll("button")];
      const i = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); items[Math.min(items.length - 1, i + 1)].focus(); }
      if (e.key === "ArrowUp") { e.preventDefault(); items[Math.max(0, i - 1)].focus(); }
      if (e.key === "Escape") { menu.hidden = true; exb.focus(); }
    });
    $("problems-btn").onclick = () => this.showProblems($("problems").hidden);
  }
  async loadExampleMenu() {
    const menu = $("examples-menu");
    clear(menu);
    const groups = { Gates: [], Memory: [], Clocks: [], Counters: [], "PC-2": [], "PC-2 modules": [] };   // menu order
    let eng = [];
    try { eng = await engine.examples(); } catch (e) { eng = []; }
    for (const ex of LOCAL) {
      if (ex.engine && eng.some((e) => e.id === ex.id)) continue;     // the engine's own entry follows
      const run = ex.engine
        ? async () => {
          if (engine.backend !== "python") throw new Error("it is drawn by the Python engine, which is still starting: try again when the status bar says it is ready");
          store.load(await engine.example(ex.id));
        }
        : () => store.load(ex.make());
      (groups[ex.group] ||= []).push({ ...ex, run });
    }
    for (const ex of eng) {
      if (ex.id === "pc2") {
        (groups["PC-2"] ||= []).unshift({ name: "PC-2: the whole computer", desc: "48 chips on 17 boards, with ECHO, BIGGER, MULTIPLY… ready to load", run: () => this.openPC2() });
      } else {
        const g = ENGINE_GROUP[ex.id] || (ex.group === "From the engine" ? "Examples from the book" : ex.group || "Examples from the book");
        const local = LOCAL.find((l) => l.id === ex.id);
        (groups[g] ||= []).push({ name: local ? local.name : (ex.name || ex.id).replace(/^PC-2 /, ""), desc: (local && local.desc) || ex.desc || "", run: async () => store.load(await engine.example(ex.id)) });
      }
    }
    if (eng.some((e) => e.id === "pc2") && !eng.some((e) => e.kind === "module")) {
      const mods = ["Clock", "Bus", "A register", "B register", "ALU", "Flags", "Program counter", "Memory address", "RAM", "Instruction register", "Output", "Display", "Input", "Control"];
      for (const m of mods) (groups["PC-2 modules"] ||= []).push({ name: m, desc: "", run: async () => store.load(moduleOf(await this.pc2Json(), m)) });
    }
    for (const [g, list] of Object.entries(groups)) {
      if (!list.length) continue;
      menu.append(h("h6", {}, g));
      for (const ex of list) {
        const b = h("button", { role: "menuitem" }, ex.name, ex.desc ? h("small", {}, ex.desc) : null);
        b.onclick = async () => {
          menu.hidden = true;
          if (!this.confirmDiscard()) return;
          try { await ex.run(); toast(`Opened ${ex.name}`); } catch (e) { toast(`Could not open ${ex.name}: ${e.message}`, 5000); }
        };
        menu.append(b);
      }
    }
  }
  async pc2Json() {
    if (!this._pc2 || this._pc2backend !== engine.backend) { this._pc2 = await engine.example("pc2"); this._pc2backend = engine.backend; }
    return this._pc2;
  }
  async openPC2() {
    store.load(await this.pc2Json());
    this.showTab("panel");
  }
  confirmDiscard() { return !store.dirty || store.project.parts.length < 1 || window.__bbNoConfirm || confirm("Open another project? Unsaved changes to this one will be lost (it is kept as the autosave until then)."); }
  save() {
    const p = normalise(store.project);
    const name = (p.name || "project").replace(/[^\w.-]+/g, "_") + ".bbproj";
    download(name, JSON.stringify(p, null, 1));
    store.dirty = false;
    this.showProject();
    toast(`Saved ${name}`);
  }
  undo() { const l = store.undo(); if (l) toast(`Undo: ${l}`, 1200); }
  redo() { const l = store.redo(); if (l) toast(`Redo: ${l}`, 1200); }
  autosaveSoon() {
    clearTimeout(this._as);
    this._as = setTimeout(() => { const p = store.project; if (p.parts.length < 400) storageSet("bb-autosave", p); }, 800);
  }
  bindKeys() {
    document.addEventListener("keydown", (e) => {
      const mod = e.ctrlKey || e.metaKey;
      const inField = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
      if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); this.save(); }
      else if (mod && e.key.toLowerCase() === "o") { e.preventDefault(); $("file-input").click(); }
      else if (!inField && mod && e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); this.undo(); }
      else if (!inField && mod && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) { e.preventDefault(); this.redo(); }
      else if (!inField && e.altKey && /^[1-5]$/.test(e.key)) { e.preventDefault(); this.showTab(["schematic", "breadboard", "analyser", "panel", "code"][+e.key - 1]); }
    });
  }
  showTab(tab) {
    this.tab = tab;
    storageSet("bb-tab", tab);
    for (const t of document.querySelectorAll(".tab")) {
      const on = t.dataset.tab === tab;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      if (on) {
        const acc = t.dataset.accent;
        document.documentElement.style.setProperty("--accent", `var(--${acc})`);
        document.documentElement.style.setProperty("--accent-t", `var(--${acc}-t)`);
      }
    }
    for (const ws of document.querySelectorAll(".ws")) ws.hidden = ws.id !== `ws-${tab}`;
    $("library").classList.toggle("offtab", !["schematic", "breadboard"].includes(tab));
    const views = { schematic: this.schematic, breadboard: this.breadboard, analyser: this.analyser, panel: this.panel, code: this.code };
    for (const [k, v] of Object.entries(views)) if (k !== tab && v && v.hidden) v.hidden();
    const view = views[tab];
    if (view && view.shown) view.shown();
  }

  // ------------------------------------------------------------------ status, problems
  showProject() {
    const nm = $("proj-name");
    if (document.activeElement !== nm) nm.value = store.project.name || "Untitled";
    $("dirty").textContent = store.dirty ? "· edited" : "";
    $("btn-undo").disabled = !store.undoStack.length;
    $("btn-redo").disabled = !store.redoStack.length;
    document.title = `${store.project.name || "Untitled"} · Breadboard Bench`;
  }
  showEngine(st) {
    const el = $("engine-status");
    el.className = `pill ${st.phase === "ok" ? "ok" : st.phase === "mock" ? "mock" : st.phase === "error" ? "err" : ""}`;
    el.querySelector("span").textContent = st.text;
    el.title = st.phase === "mock" ? "The demo engine simulates gates, switches, LEDs, clocks and PC-2 (at the microcode level). The Python engine simulates every chip pin by pin." : st.text;
    document.body.dataset.engine = engine.backend;
  }
  showSimStatus(st) {
    const el = $("sim-status");
    const bits = [];
    if (st.cycles != null) bits.push(`${st.cycles} cycles`);
    if (st.t_ns != null && st.cycles == null) bits.push(`t = ${Math.round(st.t_ns)} ns`);
    if (st.halted) bits.push("halted");
    const info = simctl.clockInfo();
    if (info.has && info.paused) bits.push("⏸ clock paused");
    document.body.classList.toggle("clock-paused", !!(info.has && info.paused));
    if (st.errors && st.errors.length) bits.push(`${st.errors.length} sim error${st.errors.length > 1 ? "s" : ""}`);
    el.textContent = bits.join(" · ");
    el.hidden = !bits.length;
  }
  renderProblems(list) {
    const btn = $("problems-btn"), box = $("problems");
    const n = list.filter((p) => p.severity !== "info").length;
    btn.classList.toggle("has-problems", n > 0);
    $("problems-count").textContent = n ? `${n} problem${n > 1 ? "s" : ""}` : list.length ? `${list.length} note${list.length > 1 ? "s" : ""}` : "No problems";
    clear(box);
    box.append(h("h4", {}, "Problems found by the checker", h("button", { class: "btn ghost", onclick: () => this.showProblems(false), "aria-label": "Close" }, "✕")));
    if (!list.length) box.append(h("p", { class: "hint" }, "Nothing to report: every net is connected as the netlist says."));
    for (const pr of list) {
      const sev = pr.severity || "error";
      const row = h("div", { class: "problem", tabindex: "0", role: "button" },
        h("span", { class: `sev ${sev}`, "aria-label": sev }, sev === "error" ? "!" : sev === "warning" ? "!" : "i"),
        h("div", {}, h("div", {}, pr.message), whereText(pr.where) ? h("div", { class: "where" }, whereText(pr.where)) : null));
      row.onclick = () => this.goTo(pr.where);
      row.onkeydown = (e) => { if (e.key === "Enter") this.goTo(pr.where); };
      box.append(row);
    }
  }
  showProblems(open) {
    $("problems").hidden = !open;
    $("problems-btn").setAttribute("aria-expanded", String(open));
  }
  goTo(where) {
    const w = normWhere(where);
    if (w.board || (this.tab === "breadboard" && (w.part || w.net))) { this.showTab("breadboard"); this.breadboard.focusWhere(where); return; }
    const pid = w.part || (w.parts && w.parts[0]);
    if (pid && store.project.parts.some((p) => p.id === pid)) { this.showTab("schematic"); this.schematic.focusPart(pid); }
    else if (w.net) { this.showTab("schematic"); this.schematic.select({ kind: "net", net: w.net }); }
  }
  // ------------------------------------------------------------------ theme
  initTheme() {
    const t = storageGet("bb-theme-choice");
    if (t) document.documentElement.dataset.theme = t;
  }
  toggleTheme() {
    const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    storageSet("bb-theme-choice", next);
    try { localStorage.setItem("bb-theme", next); } catch (e) { /* private mode */ }
    if (this.analyser) this.analyser.draw();
  }
}

const app = new App();
app.start().catch((e) => { console.error(e); toast(`Breadboard Bench could not start: ${e.message}`, 10000); });
