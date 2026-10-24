# Breadboard Bench engine: API reference

The engine is the pure-Python package `bbench` (Python 3.11 or later, standard library only).
It runs on the desktop and, unchanged, in the browser under Pyodide. Every function in the
public API returns plain JSON-compatible data: dicts, lists, ints, floats and strings.

Every example on this page was run, and the output shown is what it printed
(`python tools/doc_examples.py` runs them all again).

## Contents

1. [Projects](#1-projects)
2. [Simulators](#2-simulators)
3. [State, traces and VCD](#3-state-traces-and-vcd)
4. [Problems the engine reports](#4-problems-the-engine-reports)
5. [Breadboards](#5-breadboards)
6. [The chip library](#6-the-chip-library)
7. [Built-in projects and PC-2](#7-built-in-projects-and-pc-2)
8. [The old pc2sim API](#8-the-old-pc2sim-api)
9. [Command line](#9-command-line)
10. [In the browser](#10-in-the-browser)
11. [Performance](#11-performance)

## 1. Projects

A project is the `.bbproj` JSON format of DESIGN §3. The netlist (`"nets"`) is the source of
truth; the schematic and the breadboards are views of it, and are checked against it.

```python
import bbench
p = bbench.Project.load(text_or_dict_or_path)   # or bbench.projects.pc2()
p.save("my.bbproj")                             # returns the JSON text too
p.to_dict()                                     # a copy of the data
problems = p.check()                            # [{severity, kind, message, where}]
sim = p.simulator(mode="zero")                  # or "timed"
t = p.simulator("timed", start=sim)             # a timed run from where sim is now
```

`save()` gives back exactly what `load()` read, including keys the engine does not use, so
the app can keep its own settings in the file. Pins are numbers written as strings
(`["U7", "14"]`); a pin name (`["U7", "1D"]`) is also accepted when loading.

Part `props` used by the engine:

| Prop | Parts | Meaning |
|---|---|---|
| `value` | R, RNn, C, POT | `"10k"`, `"4k7"`, `"100nF"`, `"1uF"` |
| `label` | any | the name shown to the user; `sim.set()` accepts it as the part's id |
| `labels` | DIPSWn | one label per section |
| `positions`, `pos` | SPDT, JUMPER3 | position names (default `["A", "B"]`) and the starting one |
| `position` | POT | wiper, 0 to 1 |
| `closed` | SW, DIPSWn | starting state (bool, or an int for a DIP switch) |
| `colour` | LED | `"red"`, `"yellow"`, ... |
| `image` | AT28C256, AS6C62256 | `{"size": 32768, "fill": 255, "base64": "..."}` (trailing fill bytes left out) |
| `mode` | NE555 | `auto` (default), `astable`, `monostable`, `bistable`, `manual` |
| `period_ns`, `duty` | CLOCK | the square wave |
| `bank` | RNn | the DIP switch it pulls down (keeps them together in the auto layout) |
| `module`, `board` | any | which module and which breadboard (used by the auto layout) |

`"stimuli"` entries are `{"part", "period_ns", "duty", "delay_ns", "role"}`. `part` is a
CLOCK, a 555 or a switch. Leave out `period_ns` and the engine works it out: from a CLOCK's
props, or from the resistors and capacitor around an astable 555. `role` is `"main"` (the
clock `step()` uses), `"scan"` (a display multiplexing clock, see `state()`), or `"clock"`.
CLOCK parts and astable 555s that are not listed become clocks of their own.

## 2. Simulators

Both simulators take the same calls:

| Call | Zero-delay (`"zero"`) | Timed (`"timed"`) |
|---|---|---|
| `set(id, value)` | sets a switch, button, slide, pot or clock output and settles | the same, at the current time |
| `press(id)` | down, settle, up, settle | down, hold 1 ms (`hold_ns=`), up |
| `drive(id, value)` | sets without settling (then call `update()`) | the same |
| `update()` | settles and fires clock edges | applies `drive()` changes now |
| `step(n=1)` | n cycles of the main clock | runs n periods of the main clock |
| `half(level, clock=None)` | moves one clock to a level | the same |
| `run(until="halt", limit=20000)` | steps until the condition, `{"done", "cycles"}` | the same, plus `"t_ns"` |
| `run_ns(ns, max_edges=100000)` | real-time view: moves the time on by ns and toggles every clock source at its own period and duty, settling after each edge; `{"t_ns", "edges", "cycles", "done"}` | advances time |
| `clocks()` | the clock sources the app's speed control is about (not a `"scan"` clock) | – |
| `scan_clocks()` | display scan clocks (role `"scan"`); `run_ns` moves these too | – |
| `snapshot()` | every part's state now (registers, memories, switches, clock levels) and the nets | the same |
| `v(net)`, `word(prefix, n)` | value of a net; `word("BUS", 8)` reads BUS0..BUS7 (None if any bit is not 0/1) | the same |
| `state()`, `trace(nets)`, `to_vcd(nets)` | see §3 | the same |
| `errors` | problem dicts (§4) | the same, plus `violations` |

`id` is a part id (`"S3"`), a DIP switch section (`"S3.4"`), or a part's label
(`"RESET"`, `"RUN / STEP"`). A DIP switch also takes a whole number: `set("S3", 42)` sets
section k to bit k-1. A slide takes a position name or 0/1.

`until` is `"halt"` (net `HLT_n` low, or net `HLT` high), `{"net": "Q3", "value": 1}`, or a
function of the simulator.

**Zero-delay** settles every chip, fires the clock edges, then settles again: the proven
algorithm of pc2sim. Registers sample the values settled before the edge. Time is nominal:
each `update()` moves on by half a main-clock period, so traces look like ideal timing
diagrams. After the first update only what changed is worked on; if you change a chip's
`state` yourself, call `update(full=True)`.

`run_ns` is what the app's Schematic and Front panel tabs use to keep the live circuit
ticking: clock parts and astable 555s run at their own periods (the main clock's `cycles`
count its rising edges), so a 555 blinks an LED and a counter counts without any `step()`.
A display scan clock (stimulus role `"scan"`, PC-2's U36) runs too, so the digit counter and
the digit selects change as on the bench; `state()` still shows all four digits lit.

**Starting from another simulator.** `p.simulator(mode, start=other)` (or
`start=other.snapshot()`) builds a simulator of the same project that starts where `other`
is: chip registers, RAM and EEPROM contents, 555 levels, switches, buttons, pots, and the
net values and drivers, so that nothing passes through power-up values on the way (which
could write the RAM). The source simulator is not changed. The app's analyser uses this for
a timed run of a program entered on the front panel.

**Timed** is event driven in integer picoseconds. A changed input re-evaluates its chip, and
each changed output is scheduled after the datasheet delay `TPD` for that input to that
output (inertial: a pulse shorter than the delay is swallowed). Clocked chips sample their
inputs as they were just before the edge and record setup and hold violations. The 555
models run at the period their resistors and capacitors give: t_high = 0.693 (R1 + R2) C,
t_low = 0.693 R2 C, and a monostable pulse of 1.1 R C. Short overlaps are normal in real
logic, so contention counts only when two drivers fight for more than 10 ns
(`contention_grace_ns`), and a floating input only after 1 µs (`float_grace_ns`).
An output that turns off uses the chip's disable time (`TDIS`: the 74HCT245's tdis, a
memory's tOHZ or tDF) where the datasheet gives one.

**Unknown outputs while a memory settles.** After a change on an address pin a memory keeps
its old data for its output hold time tOH (`ADDR_HOLD`: 0 ns for the AT28C256, 10 ns for the
AS6C62256), then its outputs are unknown (`"X"`) until the access time (150 ns, 55 ns): the
datasheets promise nothing in between, and a real AT28C256 can glitch. Unknown values pass
through the logic: a chip with unknown inputs is evaluated with each 0/1 value of them and an
output that depends on them is unknown, so a control line from a microcode ROM can briefly
enable any bus driver. A fight where at most one driver is known is reported as a possible
brief overlap (kind `"overlap"`, a warning); a fight between known drivers is contention (an
error). Every interval is also listed in `sim.overlaps` as
`{"kind", "net", "drivers", "from_ns", "to_ns", "ns"}`.

Example (an XOR made of four NAND gates):

```python
import bbench
p = bbench.projects.example("xor-from-nand")
print(p.name, "-", len(p.data["parts"]), "parts,", len(p.data["nets"]), "nets")
print(p.check())
sim = p.simulator(mode="zero")
for a in (0, 1):
    for b in (0, 1):
        sim.drive("SA", a)
        sim.drive("SB", b)
        sim.update()
        print(a, b, "->", sim.v("XOR"), "LED lit:", sim.state()["leds"]["D1"])
```
```
XOR from four NAND gates - 8 parts, 9 nets
[]
0 0 -> 0 LED lit: False
0 1 -> 1 LED lit: True
1 0 -> 1 LED lit: True
1 1 -> 0 LED lit: False
```

A timed run, six inverters in a chain (each 74HC04 gate takes 20 ns):

```python
from bbench.core.netlist import Netlist
N = Netlist()
N.add("U1", "74HC04")
N.add("S1", "SW")
N.add("R1", "R", {"value": "10k"})
N.connect("VCC", "U1", 14); N.connect("GND", "U1", 7)
N.connect("VCC", "S1", 1); N.connect("N0", "S1", 2)
N.connect("N0", "R1", 1); N.connect("GND", "R1", 2)
for k in range(1, 7):
    N.connect(f"N{k - 1}", "U1", f"{k}A")
    N.connect(f"N{k}", "U1", f"{k}Y")
t = bbench.TimedSim(N)
t.run_ns(100)
t.set("S1", True)
t.run_ns(500)
print(t.trace(["N0", "N1", "N6"]))
```
```
{'t_unit': 'ns', 'signals': [{'name': 'N0', 'changes': [[0, 0], [100, 1]]}, {'name': 'N1', 'changes': [[0, 1], [120, 0]]}, {'name': 'N6', 'changes': [[0, 0], [220, 1]]}]}
```

How a net gets its value, strongest first: a rail (VCC, GND, or a POWER part's pin); strong
drivers (chip outputs that are not `"Z"`, and closed switches to a rail; nets joined by a
closed switch act as one net); a weak pull (a resistor to a rail); a follower (a net joined by
a resistor to a net with a value, such as an LED's resistor or a transistor's base
resistor); otherwise `"Z"`. Two strong drivers at once give `"X"` if they disagree, and are
reported as contention either way, as pc2sim did.

## 3. State, traces and VCD

`sim.state()` returns:

```
{"mode": "zero", "t_ns": 1234.0,
 "nets": {"BUS0": 0, "CLK": 1, "RD3": "Z", ...},
 "leds": {"LED17": true, ...},          # by part id
 "digits": {"DISP3": 102, ...},         # segment bits: bit k = a, b, c, d, e, f, g, dp
 "probes": {"P1": 1},                   # PROBE parts
 "switches": {"S3": [0, 1, 0, 0, 0, 0, 0, 0], "SPDT1": "RUN", "BTN1": false, "VR1": 0.0},
 "errors": [...]}
```

In the zero-delay simulator, if the project has a stimulus with role `"scan"` (PC-2's U36),
`state()` runs that clock through a whole scan and keeps every lit segment, so `digits` shows
the display as the eye sees it. `state(persist=False)` skips this.

`sim.trace(nets)` returns `{"t_unit": "ns", "signals": [{"name", "changes": [[t, v], ...]}]}`
with values 0, 1, `"Z"` or `"X"`. Recording starts when the simulator is made;
`sim.record(nets=None)` starts again from now (all nets, or only the ones given).
`sim.to_vcd(nets)` gives standard VCD text (timescale 1 ps) that opens in PulseView and
GTKWave; `sim.write_vcd(path, nets)` writes it. `bbench.core.waveforms.parse_vcd(text)` reads
one back.

```
$comment Breadboard Bench $end
$version Breadboard Bench engine $end
$timescale 1ps $end
$scope module bench $end
$var wire 1 ! N0 $end
$var wire 1 " N6 $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
0"
$end
#100000
1!
#220000
1"
```

## 4. Problems the engine reports

Every problem is `{"severity": "error" | "warning", "kind", "message", "where", "count"}`
(simulators add `"t_ns"`, the time it was first seen). A problem appears once, and `count`
says how often it happened.

| kind | Found by | Meaning |
|---|---|---|
| `contention` | simulators | two strong drivers on one net; `where`: net, drivers (timed: `from_ns`, `to_ns`) |
| `overlap` | timed | warning: a driver whose output is unknown (a ROM settling) fights another; `where` as contention |
| `floating` | simulators | a chip input reads `"Z"` or `"X"` |
| `unconnected` | check, simulators | a chip input pin is on no net |
| `no-driver` | check, simulators | a net is read but nothing can ever drive it |
| `eeprom-write` | simulators | an EEPROM's WE went low in circuit |
| `oscillation` | simulators | the logic did not settle, or a net toggles more than 1000 times in 1 µs |
| `setup`, `hold` | timed | a clocked input changed too close to its edge; full list in `sim.violations` |
| `short` | simulators, breadboard | a switch joins two rails; two nets touch on the breadboard |
| `missing` | breadboard | a net is in more than one piece; `where.pieces` lists the pins of each piece |
| `hole`, `unplaced` | breadboard | a hole used twice or under a chip body; a part or pin not on a board |
| `part`, `net`, `power` | check | unknown type or pin, a pin on two nets, a chip's power pin not on its rail |
| `levels` | check, simulators | warning: a chip output's high level (VOH) is below the input threshold (VIH) of a chip that reads it, such as a 555 or a memory driving a 74HC input; `where`: part (the reader), driver, nets |

A latch made of two cross-coupled gates of one chip is symmetric: in a zero-delay
simulator it would flip both outputs together for ever. When settling takes too long the
engine changes one output at a time, which settles a latch the way a real one does (on one
side). A true oscillator, such as a ring of three inverters, is still reported.

## 5. Breadboards

The board is the book's 830-point board: rows 1 to 63, holes a to e and f to j, a GND rail
(`B-`, `T-`) and a +5 V rail (`B+`, `T+`) along each long edge. A 0.3 in chip has its pins in e
and f, a 0.6 in chip (or 0.56 in digit) in c and g (holes are 0.1 in apart and the gap is 0.3 in, so the rows are 6 pitches apart), with pin 1 at the given hole.

```json
"breadboards": [{"id": "BB1", "name": "Main", "x": 0, "y": 0,
  "placements": [{"part": "U1", "row": 1, "hole": "e"},
                 {"part": "R1", "legs": {"1": [12, "d"], "2": ["B-", 12]}}],
  "wires": [{"a": [3, "a"], "b": [9, "b"], "colour": "#4E9F3D"}, {"a": [7, "a"], "b": "B-"}]}],
"links": [{"a": ["BB1", [14, "i"]], "b": ["BB2", [3, "h"]]}]
```

Footprints: `dip` (chips, DIP switches, 7-segment digits), `sip` (resistor networks,
slides, jumpers and transistors in three rows, a pot with its legs two rows apart),
`button` (four legs across the gap), `leads` (placed leg by leg), `virtual` (CLOCK, POWER,
PROBE are instruments, not placed). A board's `"rails"` can map rails to other nets.

The checker rebuilds the circuit from the holes, legs and wires and compares it with the
netlist:

```python
import copy
from bbench.board.checker import check_boards
d = copy.deepcopy(bbench.projects.example("nand-gate").data)
d["breadboards"][0]["wires"].pop(0)
for prob in check_boards(d):
    print(prob["severity"], prob["kind"], prob["message"])
```
```
error missing missing connection: Y is in 2 separate pieces
```

`bbench.board.layout(data, netlist, board_order, chain_order)` lays a project out
automatically (the generalised pc2sim layout); for PC-2 it gives the book's 17 boards hole
for hole (`tools/compare_seed_layout.py` checks this).

## 6. The chip library

`bbench.library()` lists every chip and part:
`[{"type", "desc", "family", "category", "package", "width", "pins": [[n, name, kind]], "edge", "tpd", "setup", "hold", "datasheet", "levels", ...}]`.
`levels` is `{"VIH", "VIL", "VOH", "VOL"}` in volts (`None` where the datasheet gives no
logic level, such as a 555's analogue inputs).
Parts also have `"footprint"`, `"internal"` and `"defaults"`.

A chip is a class registered with `@register` (see the docstring of `bbench/chips/base.py`):
`TYPE`, `DESC`, `FAMILY`, `PINS` (`{n: (name, kind)}`, kinds in, out, tri, io, clk, vcc,
gnd, ana, nc), `EDGE`, `TPD` (`{(from, to): ns}`, worst case at 4.5 V and 25 °C; pin names,
`"*"` or patterns such as `"?CLR"`), `SETUP`, `HOLD`, `SAMPLED`, `DATASHEET`, and the methods
`eval(g)`, `edge(g, clkpin)`, `asyncupd(g)`, `reset_state()`. Every module in
`bbench/chips/` is imported automatically. HCT versions of the PC-2 chips are registered
(`74HCT173`, ...) with the same logic (a `variant()` of the HC class), their own datasheet
delays and TI CD74HCT/SN74HCT datasheets.

Logic levels (`VIH`, `VIL`, `VOH`, `VOL`; `Chip.levels()`) come from the family, at
VCC = 4.5 V: HC inputs need 3.15 V for a 1, HCT and LS inputs 2.0 V (TTL levels). Memories
(AS6C62256, AT28C256) and the NE555 give TTL-level outputs (VOH 2.4 V and 2.75 V at
least), so they can drive HCT but not HC inputs; `check()` warns where they do (kind
`levels`). This is why PC-2 is built with 74HCT parts throughout.

Parts in `bbench/parts/`: `R`, `RN2`..`RN10` (bussed SIP network, pin 1 common), `C`, `POT`,
`LED`, `7SEG-CA`, `7SEG-CC` (10-pin digit, pins 3 and 8 common), `SW`, `DIPSW1`..`DIPSW12`
(section k joins pins k and 2n+1-k), `BUTTON` (pins 1-2 and 3-4 joined inside), `SPDT`,
`JUMPER3`, `PNP`, `NPN` (pins 1 E, 2 B, 3 C; switch models), `CLOCK`, `POWER`, `PROBE`.

## 7. Built-in projects and PC-2

```python
bbench.projects.catalogue()      # [{"id", "name", "kind"}]
bbench.projects.get("pc2")       # the whole PC-2; "pc2:ALU" a module; "sr-latch" an example
bbench.projects.pc2()            # same as get("pc2")
bbench.projects.module("RAM")    # one PC-2 module, with switches for its inputs
bbench.projects.example("4-bit-counter")
```

Examples: `nand-gate`, `nor-from-nand`, `xor-from-nand`, `sr-latch`, `d-flip-flop`,
`555-clock`, `4-bit-counter`; each laid out on one breadboard.

The PC-2 project is built from the proven netlist (`bbench/projects/pc2_netlist.py`, a port
of pc2sim's): 48 chips as in the kit's bill of materials (every logic chip a 74HCT part, four
NE555 timers, the AS6C62256 RAM and four AT28C256 EEPROMs), every passive, the four ROM
images, the 17 breadboards and 210 board-to-board wires. The boards sit in the book's rack
(`bbench.projects.pc2.RACK`: three columns, the Bus at the top of the middle one and the
Front panel at its foot; `RACK_XY` gives each board's place on the Breadboard tab), and
every part has a schematic position, one block per module, spaced for the app's symbols and
net tags (`bbench/projects/sheet.py`), so the app draws them as they are. Its 555s are real models: U1
astable (4.8 kHz on the FAST jumper), U2 the STEP monostable (110 ms), U3 the RUN/STEP
debouncer, U36 the display scan (686 Hz). `data["programs"]` holds the book's programs.

```python
p = bbench.projects.pc2()
print(len(p.data["parts"]), "parts,", len(p.data["breadboards"]), "breadboards,", len(p.data["links"]), "links")
print(p.check())
sim = p.simulator("zero")
sim.set("PROGRAM / RUN", "PROG")
for addr, byte in enumerate([0xC0, 0x70, 0x00]):      # ECHO: IN 0, OUT 0, HALT
    sim.set("S1", addr)                                # address switches
    sim.set("S2", byte)                                # data switches
    sim.press("WRITE")
sim.set("PROGRAM / RUN", "RUN")
sim.set("S3", 42)                                      # input bank A
sim.press("RESET")
sim.set("RUN / STEP", "RUN")
print(sim.run(until="halt", limit=1000))
st = sim.state()
print("OUT =", sim.word("OUT", 8), " digits:", st["digits"])
print("errors:", st["errors"])
```
```
338 parts, 17 breadboards, 210 links
[]
{'done': True, 'cycles': 8}
OUT = 42  digits: {'DISP1': 0, 'DISP2': 0, 'DISP3': 102, 'DISP4': 91}
errors: []
```

(`DISP4` is the ones digit: the digits are made in the order 3, 2, 1, 0, and 91 is the
pattern of "2", 102 of "4".)

`bbench.projects.pc2.Panel` works the front panel for you: `load(mem)` (returns the bytes
read back from the RAM LEDs), `set_inputs(a, b)`, `reset()`, `run(limit)`, `single_step()`,
`display()` (the four characters), `shown` (every value OUT wrote), `rises`. With
`Panel(mode="timed")` it waits between actions as a person would.

```python
from bbench.projects.pc2 import Panel
panel = Panel()
panel.load(bbench.projects.pc2_programs.PROGRAMS["FIBONACCI"]["mem"])
panel.reset()
panel.run()
print(panel.shown, repr(panel.display()))
```
```
[1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233] ' 233'
```

**Timing findings.** Delays are the datasheet maxima at 4.5 V, 25 °C (set-up and hold
minima) of the kit's parts (see the comments in `bbench/chips/*.py`). Running the seven book
programs (ECHO … FIBONACCI) the timed simulator finds no setup or hold violation, and:

- **Possible overlaps while the microcode ROMs settle (warnings).** Each falling edge of
  CLK moves the step counter (U45) and the control-address latch (U46), so the three
  AT28C256 change address about 60 ns later. Their outputs are then unknown until tACC
  (150 ns), so any output-enable line (AO, EO, CO, IO, RO, XO) may glitch active. On every
  step change BUS0-BUS7 can be driven by U9, U16, U21, U25, U31 and U39 or U40 from about
  91 ns to 240-274 ns after the falling edge (149-183 ns), and RD0-RD7 by U24 and U25 for
  125-164 ns (91-255 ns after the edge). This is in the low half of the clock, long before
  the next rising edge loads any register.
- **Hand-overs between known drivers (contention, inside those windows).** Shown on their
  own when the ROM is modelled as a clean 150 ns delay (`AT28C256.ADDR_HOLD = None`):
  32 ns on BUS0-BUS7 when an `IN` step (XO: U39 or U40) is followed by a fetch (CO: U21),
  because XO passes through the U41 decoder (34 ns) before reaching the 245's OE (30 ns
  disable) while CO enables U21 in 32 ns; 13 ns on RD0-RD7 at the end of every RAM read
  (RO), when U25 turns round (32 ns) before the RAM lets go (U28 25 ns + tOHZ 20 ns).
- **PROGRAM to RUN.** Sliding PROGRAM/RUN to RUN gives 17 ns of contention on RD0-RD7
  (U25 enabled in 32 ns; the RAM released after U28's select path, 29 ns, + tOHZ 20 ns).

The machine gives every right answer. Overlaps this short are harmless for the chips (the
damage limit is about heating), but each is a supply current spike.

## 8. The old pc2sim API

`bbench.compat.pc2sim` keeps the book's code working unchanged: `Bench` (`load`,
`set_bits`, `switch`, `spdt`, `press`, `reset`, `half`, `run`, `single_step`, `display`,
`shown`, `rises`, `u`, `N`, `sim`), `Netlist` (`module`, `chip`, `part`, `led_source`,
`led_sink`, `switch_bank`, `pulldown`, `pullup`, `switch_to_vcc`, `nets`, `by_module`),
`Sim` (`step`, `v`, `word`, `errors`, `contention`), `build`, `roms`, `CONTROL_LINES`. Its
555s are "manual", as before: the bench sets their outputs (`b.u["U3"].model.state = 1`).
Messages keep their old wording.

```python
from bbench.compat.pc2sim import Bench
b = Bench()
b.load([0xC0, 0x70, 0x00])
b.set_bits("input A switch {}", 200)
b.reset()
b.run()
print("display:", repr(b.display()))
```
```
display: ' 200'
```

`python tools/prove_pc2.py` runs all 483 cases of pc2sim's `test_hw.py` (add `--api` to go
through the new API and the real 555 models instead).

## 9. Command line

```
python -m bbench run PROJECT [--mode zero|timed] [--until-halt] [--cycles N] [--ns T]
                     [--limit N] [--set ID=VALUE ...] [--press ID ...] [--program NAME]
                     [--vcd FILE] [--probes A,B]
python -m bbench check PROJECT          # JSON; exit status 1 if there is an error
python -m bbench library
python -m bbench list
python -m bbench export pc2 pc2.bbproj
```

PROJECT is a `.bbproj` file or a built-in id. For example
`python -m bbench run pc2 --program ECHO --set S3=42 --press RESET --until-halt --vcd out.vcd`
prints a JSON summary with `"shown": [42]` and `"display": "  42"`.

## 10. In the browser

`python tools/build_wheel.py` builds `web/py/bbench-1.0.0-py3-none-any.whl` with the standard
library only, and writes its name into `web/py/index.json`. The app's worker fetches it and
unzips it into Pyodide's site-packages, then calls the API above through `engine_glue.py`.
Besides the calls of DESIGN §5, the glue has `runNs(ns, maxEdges)` (the live clock),
`clocks()`, and `timedRun(ns, nets, fromCurrent)`: a timed run in a simulator of its own,
started from the live simulation's state (`fromCurrent`) or from power-up with the live
switches, which returns the trace and leaves the live simulation as it was. The build also
refreshes `web/mock/` (the library and PC-2 for the demo engine).
Nothing in the engine needs a compiled module, numpy or the network.

## 11. Performance

On the development machine (CPU time, PC-2 running MULTIPLY 7 × 6, 206 clock cycles):
zero-delay about 1400 cycles per second, timed about 1000 cycles per second
(`python tools/bench_speed.py`). The test suite (`python -m pytest`) takes about a minute.
