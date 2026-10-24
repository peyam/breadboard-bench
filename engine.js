// The app's only door to the simulation engine (DESIGN §5). Every call is async and every value
// crosses as JSON. A Web Worker hosts Pyodide and the bbench package so the page never freezes.
// Until Python is ready (or when no bbench wheel is present) the demo engine in engine_mock.js
// answers instead, with the same interface; the app re-sends its project when the engine changes.
import { MockEngine } from "./engine_mock.js";
import { Emitter } from "./js/util.js";

const API = ["loadProject", "check", "newSim", "set", "step", "runUntil", "runNs", "clocks", "timedRun", "state", "trace", "library", "examples", "example"];

class Engine extends Emitter {
  constructor() {
    super();
    this.mock = new MockEngine();
    this.backend = "mock";                 // "mock" or "python"
    this.status = { phase: "loading", text: "Starting Python…" };
    this.worker = null;
    this.seq = 0;
    this.waiting = new Map();
    this.pyReady = false;
    this.info = {};
    for (const fn of API) this[fn] = (...args) => this.call(fn, ...args);
  }

  async start() {
    const want = new URLSearchParams(location.search).get("engine");     // ?engine=mock to skip Python
    if (want === "mock") { this.setStatus("mock", "Demo engine (Python switched off)"); return; }
    try {
      this.worker = new Worker(new URL("./engine_worker.js", import.meta.url), { type: "module" });
    } catch (e) {
      this.setStatus("mock", "Demo engine: this browser cannot start the Python worker"); return;
    }
    this.worker.onmessage = (e) => this.onMessage(e.data);
    this.worker.onerror = (e) => { console.error(e); this.setStatus("mock", "Demo engine: Python worker failed"); };
    const wheel = await findWheel();
    this.setStatus("loading", wheel ? "Loading Python and the bbench engine…" : "Loading Python…");
    try {
      const info = await this.raw("init", { wheel });
      this.pyReady = true;
      this.info = info;
      if (info.bbench) {
        this.backend = "python";
        this.setStatus("ok", `Python engine bbench ${info.version || ""}`.trim());
        this.emit("backend", "python");
      } else {
        this.setStatus("mock", info.error ? `Demo engine (bbench failed to load: ${info.error})` : "Demo engine · Python ready for the Code tab");
      }
    } catch (e) {
      console.error(e);
      this.setStatus("mock", "Demo engine (Python could not load)");
    }
  }
  setStatus(phase, text) { this.status = { phase, text }; this.emit("status", this.status); }

  raw(fn, ...args) {
    return new Promise((resolve, reject) => {
      const id = ++this.seq;
      this.waiting.set(id, { resolve, reject, fn });
      this.worker.postMessage({ id, fn, args });
    });
  }
  onMessage(m) {
    if (m.type === "stdout") { this.emit("stdout", m.text); return; }
    const w = this.waiting.get(m.id);
    if (!w) return;
    this.waiting.delete(m.id);
    if (m.ok) w.resolve(m.result);
    else w.reject(new EngineError(m.error, w.fn));
  }
  async call(fn, ...args) {
    if (this.backend === "python") return this.raw("api", fn, args);
    return this.mock[fn](...args);
  }
  // runs in the worker's Python (available as soon as Pyodide is up, even with the demo engine)
  async runPython(code) {
    if (!this.pyReady) return { ok: false, out: "", err: "Python is still loading… try again in a moment." };
    return this.raw("python", code);
  }
  async vcd(nets) { return this.backend === "python" ? this.raw("api", "toVcd", [nets]) : null; }
}

export class EngineError extends Error {
  constructor(msg, fn) { super(msg); this.fn = fn; }
}

// The wheel is web/py/bbench-*.whl. A static server cannot list a folder, so py/index.json names it;
// a local `python3 -m http.server` folder listing is the fallback.
async function findWheel() {
  const pick = (names) => names.filter((n) => /^bbench-.*\.whl$/.test(n)).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).pop() || null;
  try {
    const r = await fetch("py/", { cache: "no-cache" });
    if (r.ok && /text\/html/.test(r.headers.get("content-type") || "")) {
      const t = await r.text();
      const w = pick([...t.matchAll(/href="([^"]+?\.whl)"/g)].map((m) => decodeURIComponent(m[1]).split("/").pop()));
      if (w) return w;
    }
  } catch (e) { /* a static host without folder listings */ }
  try {
    const r = await fetch("py/index.json", { cache: "no-cache" });
    if (r.ok) { const j = await r.json(); if (j.wheel) return j.wheel; }
  } catch (e) { /* none */ }
  return null;
}

export const engine = new Engine();
