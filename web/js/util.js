// Small helpers shared by every view.
export const SVGNS = "http://www.w3.org/2000/svg";

export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  setAttrs(el, attrs);
  for (const k of kids.flat()) if (k != null && k !== false) el.append(k instanceof Node ? k : String(k));
  return el;
}

export function s(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  setAttrs(el, attrs);
  for (const k of kids.flat()) if (k != null && k !== false) el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return el;
}

function setAttrs(el, attrs) {
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.setAttribute("class", v);
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "text") el.textContent = v;
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
}

export function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
export const deep = (o) => (o == null ? o : JSON.parse(JSON.stringify(o)));
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function debounce(fn, ms) {
  let t = null;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export function download(name, text, type = "application/json") {
  const blob = new Blob([text], { type });
  const a = h("a", { href: URL.createObjectURL(blob), download: name });
  document.body.append(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

let toastT = null;
export function toast(msg, ms = 2600) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastT);
  toastT = setTimeout(() => (t.hidden = true), ms);
}

// Simple event hub
export class Emitter {
  constructor() { this.l = {}; }
  on(ev, fn) { (this.l[ev] ||= new Set()).add(fn); return () => this.l[ev].delete(fn); }
  emit(ev, ...a) { for (const fn of this.l[ev] || []) { try { fn(...a); } catch (e) { console.error(e); } } }
}

// Engineering formatting of times given in ns
export function fmtTime(ns, digits = 3) {
  const a = Math.abs(ns);
  if (a === 0) return "0 s";
  if (a < 1) return `${+(ns * 1000).toPrecision(digits)} ps`;
  if (a < 1e3) return `${+ns.toPrecision(digits)} ns`;
  if (a < 1e6) return `${+(ns / 1e3).toPrecision(digits)} µs`;
  if (a < 1e9) return `${+(ns / 1e6).toPrecision(digits)} ms`;
  return `${+(ns / 1e9).toPrecision(digits)} s`;
}
// A time shown to a resolution: enough digits that two times res apart read differently
export function fmtTimeRes(ns, res) {
  const a = Math.abs(ns);
  if (a === 0) return "0 s";
  const [div, unit] = a < 1 ? [1e-3, "ps"] : a < 1e3 ? [1, "ns"] : a < 1e6 ? [1e3, "µs"] : a < 1e9 ? [1e6, "ms"] : [1e9, "s"];
  const dec = Math.max(0, Math.min(9, Math.ceil(-Math.log10(Math.max(res, 1e-6) / div) - 1e-9)));
  return `${(ns / div).toFixed(dec)} ${unit}`;
}
// Labels for ruler ticks every `step` ns: distinct and readable at any zoom. Absolute times get as
// many digits as the step needs; when that makes them long (zoomed far in, late in a run) the ticks
// read as offsets from a base time shown once: {base: "208.1235 µs", labels: ["+0", "+20 ns", ...]}.
export function tickLabels(ticks, step, maxLen = 10) {
  if (!ticks.length) return { base: null, labels: [] };
  const abs = ticks.map((t) => fmtTimeRes(t, step));
  if (Math.max(...abs.map((x) => x.length)) <= maxLen) return { base: null, labels: abs };
  const t0 = ticks[0];
  return { base: fmtTimeRes(t0, step), labels: ticks.map((t) => (t === t0 ? "+0" : `+${fmtTime(t - t0, 6)}`)) };
}
export function fmtFreq(hz) {
  if (!isFinite(hz) || hz <= 0) return "—";
  if (hz < 1e3) return `${+hz.toPrecision(3)} Hz`;
  if (hz < 1e6) return `${+(hz / 1e3).toPrecision(3)} kHz`;
  return `${+(hz / 1e6).toPrecision(3)} MHz`;
}
export function parseTime(str) {
  // "10 us", "2ms", "500ns", "1.5 s", plain number = ns
  const m = String(str).trim().match(/^([\d.]+)\s*(ps|ns|us|µs|ms|s)?$/i);
  if (!m) return NaN;
  const k = { ps: 1e-3, ns: 1, us: 1e3, "µs": 1e3, ms: 1e6, s: 1e9 }[(m[2] || "ns").toLowerCase()];
  return parseFloat(m[1]) * k;
}

// Resistance/capacitance values like "4.7k", "1M", "100nF", "10uF"
export function parseValue(v) {
  const m = String(v || "").trim().match(/^([\d.]+)\s*([pnuµmkKM]?)/);
  if (!m) return NaN;
  const k = { p: 1e-12, n: 1e-9, u: 1e-6, "µ": 1e-6, m: 1e-3, k: 1e3, K: 1e3, M: 1e6, "": 1 }[m[2]];
  return parseFloat(m[1]) * k;
}

export function storageGet(k, d = null) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
export function storageSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } }
