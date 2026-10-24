// Pan and zoom for an SVG view: drag the empty sheet (or middle button) to pan, wheel or pinch to zoom.
import { s, clamp } from "./util.js";

export class Viewport {
  constructor(svg, world, { min = 0.1, max = 6, onChange } = {}) {
    this.svg = svg; this.world = world; this.k = 1; this.tx = 0; this.ty = 0; this.min = min; this.max = max;
    this.onChange = onChange || (() => {});
    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const r = svg.getBoundingClientRect();
      const f = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0018));
      this.zoomAt(e.clientX - r.left, e.clientY - r.top, f);
    }, { passive: false });
    this.apply();
  }
  apply() {
    this.world.setAttribute("transform", `translate(${this.tx.toFixed(2)} ${this.ty.toFixed(2)}) scale(${this.k.toFixed(4)})`);
    this.onChange(this);
  }
  zoomAt(sx, sy, f) {
    const k2 = clamp(this.k * f, this.min, this.max);
    f = k2 / this.k;
    this.tx = sx - (sx - this.tx) * f;
    this.ty = sy - (sy - this.ty) * f;
    this.k = k2;
    this.apply();
  }
  zoomCentre(f) { const r = this.svg.getBoundingClientRect(); this.zoomAt(r.width / 2, r.height / 2, f); }
  toWorld(cx, cy) {
    const r = this.svg.getBoundingClientRect();
    return [(cx - r.left - this.tx) / this.k, (cy - r.top - this.ty) / this.k];
  }
  fit(b, pad = 40, maxK = 1.6) {
    const r = this.svg.getBoundingClientRect();
    if (!b || !r.width || !isFinite(b.w)) return;
    const k = clamp(Math.min((r.width - 2 * pad) / Math.max(b.w, 1), (r.height - 2 * pad) / Math.max(b.h, 1)), this.min, maxK);
    this.k = k;
    this.tx = (r.width - b.w * k) / 2 - b.x * k;
    this.ty = (r.height - b.h * k) / 2 - b.y * k;
    this.apply();
  }
  centreOn(x, y) {
    const r = this.svg.getBoundingClientRect();
    this.tx = r.width / 2 - x * this.k;
    this.ty = r.height / 2 - y * this.k;
    this.apply();
  }
  // start a pan drag from a pointer event
  pan(e) {
    const x0 = e.clientX, y0 = e.clientY, tx = this.tx, ty = this.ty;
    const host = this.svg.parentElement;
    host.classList.add("dragging");
    const mv = (ev) => { this.tx = tx + ev.clientX - x0; this.ty = ty + ev.clientY - y0; this.apply(); };
    const up = () => { host.classList.remove("dragging"); window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
  }
}

export function zoomControls(vp, fit) {
  const lab = document.createElement("span");
  const el = document.createElement("div");
  el.className = "zoomctl";
  const b = (t, title, fn) => { const x = document.createElement("button"); x.textContent = t; x.title = title; x.setAttribute("aria-label", title); x.onclick = fn; return x; };
  el.append(b("−", "Zoom out", () => vp.zoomCentre(1 / 1.25)), lab, b("+", "Zoom in", () => vp.zoomCentre(1.25)), b("⤢", "Fit to window", fit));
  const prev = vp.onChange;
  vp.onChange = (v) => { prev(v); lab.textContent = `${Math.round(v.k * 100)}%`; };
  lab.textContent = `${Math.round(vp.k * 100)}%`;
  return el;
}

export function gridPattern(id, step = 10, major = 50) {
  const defs = s("defs");
  const p = s("pattern", { id, width: major, height: major, patternUnits: "userSpaceOnUse" });
  for (let i = 0; i < major; i += step) {
    p.append(s("circle", { cx: i, cy: 0, r: i === 0 ? 1.1 : 0.6, class: "gridline", fill: "var(--grid)", stroke: "none" }));
    for (let j = step; j < major; j += step) if (i === 0) p.append(s("circle", { cx: 0, cy: j, r: 0.6, fill: "var(--grid)" }));
  }
  for (let i = step; i < major; i += step) for (let j = step; j < major; j += step) p.append(s("circle", { cx: i, cy: j, r: 0.6, fill: "var(--grid)" }));
  defs.append(p);
  return defs;
}
