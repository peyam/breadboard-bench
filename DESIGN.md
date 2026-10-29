# Breadboard Bench — design document (v1)

**What it is:** a free, open-source digital-logic simulator for learning how computers work, from a single gate to a whole 8-bit computer. It is the companion software of the book *The Breadboard Computer* (PC-2) and its prequel *The Paperclip Computer* (PC-1), and shares their look. It aims to go beyond Logisim-Evolution where it matters for learners: real chip pin-outs, a breadboard view that is checked against the schematic, datasheet propagation delays and a logic analyser, contention and floating-input detection, and complete built-in computers.

**Licence:** MIT. All code is new (do not copy code, assets or file formats from Logisim, Logisim-Evolution, Digital, or any other simulator).
**Platforms:** runs in any modern browser, offline, from a folder of static files (no server, no build step needed to run), and is installable as a PWA. The engine is a pure-Python package that also runs on the desktop for scripts and the book's "Code it" boxes. In the browser the same engine runs in Pyodide.
**Audience:** ages 14+, teachers, hobbyists. Plain words in the UI, Australian English.

## 1. Repository layout (`/home/claude/bench`)
```
bbench/                 Python package (the engine) — pure Python 3.11+, no compiled deps
  __init__.py
  core/                 netlist, simulator (zero-delay and timed), waveforms, checks
  chips/                one module per family: gates.py, flipflops.py, counters.py, buffers.py,
                        decoders.py, mux.py, arith.py, shift.py, memory.py, timers.py, io.py
  parts/                passives and I/O: resistor, rnetwork, led, sevenseg, switch, button, spdt,
                        dipswitch, pot, capacitor, transistor, clock source, power, logic probe
  board/                breadboard model, placement, wire list, connectivity checker
  project.py            load/save the project format (§3)
  projects/             built-in projects: pc2.py (the whole PC-2 + each module), examples
  compat/pc2sim.py      the old book API (Bench, load, set_bits, press, run, single_step, display)
  cli.py                `python -m bbench run project.bbproj --until-halt --vcd out.vcd`
tests/                  pytest: every chip's function table; PC-2 runs every program; checks
web/                    the browser app (static): index.html, app.js (ES modules), css/, fonts/,
                        pyodide/ (vendored for offline use), sw.js (offline), manifest.json
docs/                   user guide (Markdown), chip reference (generated)
LICENSE, README.md
```

## 2. Engine
### 2.1 Chip model (keep compatible with the proven `pc2sim/chips.py`)
A chip class has: `TYPE` (part number, e.g. "74HCT173"), `DESC`, `FAMILY` ("HCT", "HC", "LS", "CMOS", "memory", "timer"), `PINS` {number: (name, kind)} with kind in in/out/tri/io/clk/vcc/gnd/ana/nc, `EDGE` {clock pin: "rise"/"fall"}, `TPD` {(from_pin_or_"*", to_pin_or_"*"): ns} worst case at 4.5 V 25 °C from the datasheet, `SETUP`/`HOLD` (ns, for clocked inputs), `DATASHEET` (URL), and methods `eval(get)`, `edge(get, clkpin)`, `asyncupd(get)`, `reset_state()`. Unknown inputs propagate as "X" where the real chip would pass them through (see `soft()` in pc2sim).

### 2.2 Netlist
Parts (chips + passives) with pins connected to named nets. Rails VCC/GND. Pull resistors and resistor networks are weak drivers; closed switches to a rail are strong drivers.

### 2.3 Simulators
- **Zero-delay** (`ZeroDelaySim`): the proven settle-then-edges algorithm of pc2sim/sim.py. Fast; used for stepping and the book. `run_ns(ns)` is its real-time view: every clock source and astable 555 toggles at its own period, so the app's live circuit ticks at a chosen speed (the app's clock, §4).
- Either simulator can **start from another's state** (`p.simulator("timed", start=sim)` or `start=sim.snapshot()`): registers, RAM/EEPROM contents, switches, clock levels and net values, so a timed run continues from the machine as it is (a program entered on the front panel included).
- **Timed** (`TimedSim`): discrete-event, picosecond integer time. When a chip input changes at t, the chip is re-evaluated and each output change is scheduled at t + TPD (inertial delay: a newer event on the same output cancels a pending one). Clock sources are stimuli with period/duty. Clocked chips sample their D inputs at the edge and record setup/hold violations (input changed within SETUP before or HOLD after the edge). Records every net change for the waveform view.
- Both detect and report: **contention** (two strong drivers on one net at once, with time and drivers), **floating inputs** (an input reading Z), **EEPROM written in circuit**, **oscillation**.
### 2.4 Waveforms
`sim.trace(nets)` returns `{"t_unit": "ns", "signals": [{"name", "changes": [[t, v], ...]}]}`; values 0/1/"Z"/"X". `to_vcd()` writes a standard VCD file (opens in PulseView/GTKWave).

### 2.5 Breadboard
The 830-point board model of the book (rows 1–63, holes a–j, inner rail GND, outer rail +5 V), placement of DIP chips (0.3 in and 0.6 in), two-leg parts across the gap or to a rail, SIP networks, buttons, digits; wires hole-to-hole. **Checker:** rebuild connectivity from holes and wires and compare it with the schematic netlist: report missing connections, shorts, unplaced pins, and holes used twice. (Port and generalise the proven `pc2sim/layout.py` check.)

### 2.6 Public Python API (used by the web app through Pyodide and by the book)
```python
import bbench
p = bbench.Project.load(json_text_or_dict)      # or bbench.projects.pc2()
problems = p.check()                            # list of {severity, message, where}
sim = p.simulator(mode="zero")                  # or "timed"
sim.set("S3.4", True)                           # switch/button/slide by part id (section ids allowed)
sim.step()                                      # one clock cycle (zero mode) / sim.run_ns(1000) (timed)
sim.run(until="halt", limit=20000)              # PC-2 helper
sim.run_ns(1e6)                                 # zero mode: clocks tick in real time
t = p.simulator("timed", start=sim)             # a timed run from sim's state (RAM included)
st = sim.state()   # {"nets": {name: v}, "leds": {id: bool}, "digits": {id: segment_bits}, "errors": [...]}
wf = sim.trace(["CLK", "BUS0"])                 # waveform JSON (§2.4)
bbench.library()                                # [{type, desc, family, pins: [[n, name, kind]], datasheet, levels}]
```
All return values are plain JSON-compatible Python objects (dicts, lists, ints, strings).

## 3. Project format (`.bbproj`, JSON, UTF-8)
```json
{ "format": "breadboard-bench/1", "name": "A register", "notes": "…",
  "parts": [ {"id": "U7", "type": "74HCT173", "x": 120, "y": 80, "rot": 0, "props": {}},
             {"id": "R1", "type": "R", "props": {"value": "1k"}},
             {"id": "D1", "type": "LED", "props": {"colour": "red"}},
             {"id": "S3", "type": "DIPSW8"} ],
  "nets": [ {"name": "BUS0", "pins": [["U7", "14"], ["U9", "18"]]} ],
  "schematic": { "wires": [ {"net": "A0", "points": [[x, y], ...]} ], "labels": [ {"net": "BUS0", "x": 0, "y": 0} ] },
  "breadboards": [ {"id": "BB1", "name": "A register", "x": 0, "y": 0,
                    "placements": [ {"part": "U7", "row": 2, "hole": "e"} ],
                    "wires": [ {"a": [14, "j"], "b": [30, "g"], "colour": "#D9A21B"},
                               {"a": [5, "a"], "b": "B-"} ] } ],
  "links": [ {"a": ["BB1", [14, "i"]], "b": ["BB2", [3, "h"]]} ],
  "stimuli": [ {"part": "CLK1", "period_ns": 1000000, "duty": 0.5} ],
  "probes": ["CLK", "BUS0", "AI_n"] }
```
Pins are referred to by number as strings. The netlist ("nets") is the source of truth; the schematic and breadboard are views of it and are checked against it.

## 4. Web app
- One page, five workspaces as tabs: **Schematic** (place parts from the library, wire, net labels, edit values; live simulation colours wires by value: 1 = signal colour, 0 = dark, Z = dashed grey, X = red), **Breadboard** (the book's 1:1 board look; drag chips onto the board, draw wires hole to hole; a Check button runs the checker and highlights problems), **Analyser** (logic analyser: pick probes; a timed run with real delays that starts from the live machine, or the live simulation shown as it runs; zoom/scroll the waveforms in ns/µs, cursors and time measurements, export VCD), **Front panel** (for PC-2 projects: the real switches, buttons, LEDs and 4-digit display, RUN/STEP, speed), **Code** (a Python console running the same engine, with the book's examples).
- **The clock** of the live simulation runs in real time on every tab, as on the bench: clock sources and astable 555s tick at a chosen speed (1 Hz to 1 kHz of the main clock, real time, or fastest) with pause and one-cycle controls. For PC-2 this is the 555 run clock: RUN/STEP at RUN lets it reach the machine until HALT; at STEP each press of STEP gives one cycle.
- **Library panel**: every chip with its pin-out card and function table, searchable.
- **Projects**: open/save `.bbproj` to the user's computer; built-in examples: gates, latches, the 555 clock, every PC-2 module, the whole PC-2 (with ECHO, COUNTDOWN, ADD, BIGGER, MULTIPLY, DIVIDE, FIBONACCI ready to load), PC-1 programs.
- **Look:** the book's design tokens (ink #1B2A41, paper #FFFBF3, copper/teal/sun/berry/sky/leaf/plum, grey #7E848D for address wires; Fredoka headings, Lexend UI text, JetBrains Mono for values), the same signal colours (bus yellow, control blue, data green, clock pink-red, address and step grey), light and dark themes.
- **Accessibility:** keyboard operable, colour never the only cue (values also shown as text/patterns), screen-reader labels.
- **Offline:** all assets vendored (Pyodide included); a service worker caches the app.
- **Tests:** Playwright end-to-end tests (load PC-2, enter ECHO on the front panel, run, read the display).

## 5. Interface between the app and the engine
The app loads Pyodide, installs the `bbench` package from `web/py/bbench-*.whl` (or the source folder), and calls the §2.6 API through a small JS wrapper `engine.js` exposing async functions: `loadProject(json)`, `check()`, `newSim(mode)`, `set(id, value)`, `step(n)`, `runUntil(cond, limit)`, `runNs(ns, maxEdges)`, `clocks()`, `timedRun(ns, nets, fromCurrent)` (a timed run in a simulator of its own, from the live state; the live simulation is left as it was), `state()`, `trace(nets)`, `library()`. Everything crosses the boundary as JSON. A Web Worker hosts Pyodide so the UI never freezes.
