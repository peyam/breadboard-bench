# Breadboard Bench

**Use it now:** https://peyam.github.io/breadboard-bench/ (works offline after the first visit).

Companion software for the book *The Breadboard Computer: build PC-2, the computer that runs itself*. The book's files (emulator, hardware model, EEPROM programmer, kit list) are in [`companion/`](companion/).

A free, open-source (MIT) digital-logic simulator for learning how computers work, from a single gate to the whole PC-2 of *The Breadboard Computer*. See DESIGN.md.

## Engine

The engine is the Python package `bbench/`: pure Python 3.11+, standard library only, so the
same code runs on the desktop and in the browser (Pyodide).

```python
import bbench
p = bbench.projects.pc2()               # or bbench.Project.load("my.bbproj")
p.check()                               # [] when the netlist and the 17 breadboards agree
sim = p.simulator("zero")               # or "timed": datasheet delays, setup/hold checks
sim.set("S3", 42); sim.press("RESET"); sim.step()
sim.state()                             # nets, LEDs, digits, switches, problems (JSON)
sim.trace(["CLK", "BUS0"]); sim.to_vcd(["CLK"])
bbench.library()                        # every chip and part with its pins
```

- `bbench/core/`: netlist, zero-delay and timed simulators, checks, waveforms (trace JSON, VCD).
- `bbench/chips/`: the chip library (`base.py` holds the chip base class and the registry).
- `bbench/parts/`: resistors, networks, LEDs, digits, switches, buttons, pots, transistors, clock, power, probe.
- `bbench/board/`: the breadboard model, the automatic layout and the checker.
- `bbench/project.py`: the `.bbproj` format; `bbench/projects/`: PC-2, its modules and examples.
- `bbench/compat/pc2sim.py`: the old `Bench`/`Netlist`/`Sim` API used by the book;
  `bbench/compat/pc2tools.py`: the book's pc2kit helpers. `book_modules/` holds the book's
  module names (`bench`, `pc2`, `pc2tools`), which the wheel installs at the top level so
  `from bench import Bench` and `import pc2, pc2tools` work in the app's Code tab.
- `web/LICENSES/`: the licence texts and notices of the app and of what it vendors (Pyodide,
  CPython, Emscripten, the fonts), shown by the app's About · Licences page.
- `python -m bbench`: command line (run, check, library, list, export).

Tests: `python -m pytest` (about a minute). Full PC-2 proof against the microcode emulator:
`python tools/prove_pc2.py` (483 runs). Wheel for the web app: `python tools/build_wheel.py`
(also refreshes the demo engine's data in `web/mock/`); then `python3 tools/build_sw.py` in
`web/`. Browser tests: `python3 -m pytest tests/e2e`. Screenshots in `docs/screenshots/` and
`docs/img/`: `python3 tools/screenshots.py`.
Full reference: [docs/engine.md](docs/engine.md).
