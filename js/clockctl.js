// Controls for the live simulation's real-time clock (simctl): the speed menu, shared by the
// Schematic and Front panel tabs, and a pause / one-cycle pair for the schematic.
import { h } from "./util.js";
import { simctl } from "./simctl.js";

export const SPEEDS = [["1 Hz", 1], ["2 Hz", 2], ["5 Hz", 5], ["10 Hz", 10], ["50 Hz", 50], ["200 Hz", 200], ["1 kHz", 1000],
  ["Real time", "real"], ["Fastest", "Infinity"]];

const hz = (f) => (f >= 1000 ? `${+(f / 1000).toPrecision(3)} kHz` : f >= 1 ? `${+f.toPrecision(3)} Hz` : `${+(1 / f).toPrecision(3)} s period`);

export function speedSelect(title = "How fast the clocks run: cycles of the main clock per second") {
  const sel = h("select", { class: "input", "aria-label": "Clock speed", title, "data-speed": "1" });
  const fill = () => {
    const info = simctl.clockInfo();
    const cur = info.speed === Infinity ? "Infinity" : String(info.speed);
    sel.replaceChildren(...SPEEDS.map(([t, v]) => h("option", { value: String(v) },
      v === "real" && info.realHz ? `Real time (${hz(info.realHz)})` : t)));
    sel.value = cur;
  };
  sel.onchange = () => simctl.setSpeed(sel.value);
  simctl.on("clock", fill);
  fill();
  return sel;
}

// The one pause switch of the simulator's clocks. It is the same state on every tab (simctl.paused):
// the Schematic and Front panel toolbars both show it, and only this button (or Step on the
// schematic, which pauses first) changes it. RUN/STEP on the front panel is a switch of the
// machine and does not touch it.
export function pauseButton() {
  const b = h("button", { class: "btn", "aria-pressed": "false", "data-clock": "pause",
    title: "Pause or resume the simulator's clocks (clock sources and 555 timers) on every tab" }, "⏸ Pause clock");
  b.onclick = () => simctl.setPaused(!simctl.paused);
  const show = () => {
    const info = simctl.clockInfo();
    b.textContent = info.paused ? "▶ Resume clock" : "⏸ Pause clock";
    b.setAttribute("aria-pressed", String(info.paused));
    b.classList.toggle("go", info.paused);
    b.classList.toggle("paused", info.paused);
  };
  simctl.on("clock", show);
  show();
  return b;
}

// Pause / resume, one cycle and the speed menu (hidden when the circuit has no clock source)
export function clockControls() {
  const pauseBtn = pauseButton();
  const stepBtn = h("button", { class: "btn", "data-clock": "step", title: "Pause the clock, then one cycle of the main clock" }, "Step");
  const sel = speedSelect();
  const wrap = h("span", { class: "clockctl", role: "group", "aria-label": "Clock" }, h("span", { class: "hint" }, "Clock"), pauseBtn, stepBtn, sel);
  stepBtn.onclick = async () => { simctl.setPaused(true); await simctl.step(1); };
  const show = () => { wrap.hidden = !simctl.clockInfo().has; };
  simctl.on("clock", show);
  show();
  return wrap;
}
