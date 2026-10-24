"""The old pc2sim API, running on the Breadboard Bench engine, so the book's code keeps
working unchanged:

    from bbench.compat.pc2sim import Bench, Netlist, Sim, build, roms, CONTROL_LINES
    b = Bench(); b.load([0xC0, 0x70, 0x00]); b.set_bits("input A switch {}", 42)
    b.reset(); b.run(); print(b.display())               # '  42'

    N = Netlist(); m = N.module("bench")
    N.chip("U1", "74HC00", m, **{"1A": "A", "1B": "B", "1Y": "Y"}, ...)
    a = N.switch_to_vcc(m, "A", "input A"); s = Sim(N); a.closed = True; s.step(); s.v("Y")

Old names: Netlist (module, chip, part, led_source, led_sink, switch_bank, pulldown,
pullup, switch_to_vcc, nets, by_module), Part (.closed, .pos), PlacedChip (.model,
.pinnet), Sim (step, v, word, errors, contention, settle, edges), Bench (load,
set_bits, switch, spdt, press, reset, half, run, single_step, display, shown, rises,
u, N, sim), build (the PC-2 netlist), roms, CONTROL_LINES, RAILS, CHIP_TYPES.
The 555s are "manual" here, as in pc2sim: the bench sets their outputs.
"""
import re
from collections import defaultdict

from .. import chips as _chips
from ..core.netlist import Netlist as CoreNetlist
from ..core.engine import ZeroDelaySim

RAILS = {"VCC": 1, "GND": 0}
CHIP_TYPES = _chips.REGISTRY


# ============================================================== old netlist builder
class Part:
    """A passive or electromechanical part: R, C, LED, SW (switch section), BTN, SPDT, JP, Q, DISP."""

    def __init__(self, kind, ref, module, pins, value="", note="", board=None):
        self.kind, self.ref, self.module = kind, ref, module
        self.board = board or module
        self.pins = dict(pins)          # pin name -> net
        self.value, self.note = value, note
        self.closed = False             # for SW and BTN: test bench sets this
        self.pos = None                 # for SPDT/JP: name of the selected throw


class PlacedChip:
    def __init__(self, ref, cls, module, role="", image=None, board=None):
        self.ref, self.cls, self.module, self.role = ref, cls, module, role
        self.board = board or module
        self.image = image
        self.model = cls(ref, image) if image is not None else cls(ref)
        if hasattr(self.model, "mode"):
            self.model.mode = "manual"
        self.pinnet = {}                # pin number -> net

    def conn(self, **kw):
        return self.c(kw)

    def c(self, mapping):
        names = {name: n for n, (name, k) in self.cls.PINS.items()}
        for name, net in mapping.items():
            if name not in names:
                raise KeyError(f"{self.ref} ({self.cls.TYPE}) has no pin {name}")
            n = names[name]
            if n in self.pinnet and self.pinnet[n] != net:
                raise ValueError(f"{self.ref} pin {name} connected twice")
            self.pinnet[n] = net
        return self


class Netlist:
    def __init__(self):
        self.chips = {}
        self.parts = {}
        self.modules = []
        self._n = defaultdict(int)

    def module(self, name):
        if name not in self.modules:
            self.modules.append(name)
        return name

    def chip(self, ref, type_name, module, role="", image=None, board=None, **pins):
        cls = CHIP_TYPES[type_name]
        pc = PlacedChip(ref, cls, module, role, image, board)
        self.chips[ref] = pc
        pw = {name: name for n, (name, k) in cls.PINS.items() if k in ("vcc", "gnd")}
        pc.c(pw)
        if pins:
            pc.c(pins)
        return pc

    def part(self, kind, module, pins, value="", note="", ref=None, board=None):
        if ref is None:
            self._n[kind] += 1
            ref = f"{kind}{self._n[kind]}"
        p = Part(kind, ref, module, pins, value, note, board)
        self.parts[ref] = p
        return p

    def led_source(self, module, net, ohms, colour, label, board=None):
        """Logic net -> resistor -> LED -> GND: lights when net is high."""
        mid = f"{net}~LED"
        r = self.part("R", module, {"1": net, "2": mid}, ohms, note=f"LED resistor ({label})", board=board)
        led = self.part("LED", module, {"A": mid, "K": "GND"}, colour, note=label, board=board)
        led.pair, led.style = r.ref, "source"
        return led

    def led_sink(self, module, net, ohms, colour, label, board=None):
        """VCC -> resistor -> LED -> logic net: lights when net is low."""
        mid = f"{net}~LED"
        r = self.part("R", module, {"1": "VCC", "2": mid}, ohms, note=f"LED resistor ({label})", board=board)
        led = self.part("LED", module, {"A": mid, "K": net}, colour, note=label, board=board)
        led.pair, led.style = r.ref, "sink"
        return led

    def switch_bank(self, module, nets, labels, ref, board="Front panel", msb_first=False):
        """A DIP switch package (one section per net, closed = net tied to VCC) and a bussed
        10 kOhm resistor network holding every line low when its switch is open.
        nets and labels are given in bit order (bit 0 first). msb_first=True wires the
        package so that switch 1 (the leftmost, at the lowest row) is the highest bit, so the
        bank reads like a written binary number and like every LED row."""
        order = list(range(len(nets)))
        if msb_first:
            order.reverse()
        rn = self.part("RN", module, {"C": "GND", **{str(pos + 1): nets[k] for pos, k in enumerate(order)}},
                       f"{len(nets)} x 10k bussed", note=f"pull-downs for {ref}", ref=f"RN{int(ref[1:]) + 1}", board=board)
        rn.msb_first = msb_first
        secs = []
        for pos, k in enumerate(order):
            sw = self.part("SW", module, {"1": "VCC", "2": nets[k]}, note=labels[k], ref=f"{ref}.{pos + 1}", board=board)
            sw.pkg, sw.pos, sw.bit, sw.msb_first = ref, pos, k, msb_first
            secs.append(sw)
        return rn, secs


    def pulldown(self, module, net, ohms="10k"):
        return self.part("R", module, {"1": net, "2": "GND"}, ohms, note="pull-down")

    def pullup(self, module, net, ohms="10k"):
        return self.part("R", module, {"1": "VCC", "2": net}, ohms, note="pull-up")

    def switch_to_vcc(self, module, net, label):
        """DIP switch section: closed = net tied to VCC; a 10k pull-down holds it low when open."""
        self.pulldown(module, net)
        return self.part("SW", module, {"1": "VCC", "2": net}, note=label)

    def nets(self):
        s = set()
        for pc in self.chips.values():
            s.update(pc.pinnet.values())
        for p in self.parts.values():
            s.update(p.pins.values())
        return s

    def by_module(self, module):
        return ([c for c in self.chips.values() if c.module == module],
                [p for p in self.parts.values() if p.module == module])


# ============================================================== old parts -> new parts
SEG_PIN = {"e": 1, "d": 2, "c": 4, "dp": 5, "b": 6, "a": 7, "f": 9, "g": 10}


def convert(N):
    """Old netlist -> list of new part specs, in netlist order (chips first, then parts):
    [{"id", "type", "props", "pins": {new pin number: net}, "old": [old part refs],
      "chip": PlacedChip or None, "sync": function(model) copying old switch state}]"""
    specs = []
    for ref, pc in N.chips.items():
        props = {"module": pc.module, "board": pc.board}
        if pc.role:
            props["label"] = pc.role
        specs.append({"id": ref, "type": pc.cls.TYPE, "props": props, "pins": dict(pc.pinnet),
                      "chip": pc, "old": [ref]})
    banks = {}
    for p in N.parts.values():
        base = {"module": p.module, "board": p.board}
        if p.kind == "SW" and getattr(p, "pkg", None):
            b = banks.get(p.pkg)
            if b is None:
                b = banks[p.pkg] = {"id": p.pkg, "secs": [], "props": dict(base)}
                specs.append(b)
            b["secs"].append(p)
            continue
        k = p.kind
        pins = {}
        props = dict(base)
        if p.note:
            props["label"] = p.note
        if k == "R":
            t = "R"
            pins = {1: p.pins["1"], 2: p.pins["2"]}
            props["value"] = p.value
        elif k == "RN":
            n = len(p.pins) - 1
            t = f"RN{n}"
            pins = {1: p.pins["C"], **{int(s) + 1: net for s, net in p.pins.items() if s != "C"}}
            m = re.match(r"\s*\d+\s*x\s*(\S+)", str(p.value))
            props["value"] = m.group(1) if m else p.value
            if p.note.startswith("pull-downs for "):
                props["bank"] = p.note.split()[-1]
        elif k == "C":
            t = "C"
            if getattr(p, "rail_row", None):
                props["rail_row"] = p.rail_row
            if "+" in p.pins:
                pins = {1: p.pins["+"], 2: p.pins["-"]}
                props["polarised"] = True
            else:
                pins = {1: p.pins["1"], 2: p.pins["2"]}
            props["value"] = p.value
        elif k == "LED":
            t = "LED"
            pins = {1: p.pins["A"], 2: p.pins["K"]}
            props["colour"] = p.value
        elif k == "SW":
            t = "SW"
            pins = {1: p.pins["1"], 2: p.pins["2"]}
        elif k == "BTN":
            t = "BUTTON"
            pins = {1: p.pins["1"], 2: p.pins["1"], 3: p.pins["2"], 4: p.pins["2"]}
        elif k in ("SPDT", "JP"):
            t = "SPDT" if k == "SPDT" else "JUMPER3"
            throws = [x for x in p.pins if x != "COM"]
            pins = {1: p.pins[throws[0]], 2: p.pins["COM"], 3: p.pins[throws[1]]}
            props["positions"] = throws
            props["pos"] = p.pos
        elif k == "VR":
            t = "POT"
            pins = {1: p.pins["1"], 2: p.pins["W"], 3: p.pins["3"]}
            props["value"] = p.value
            props["position"] = 0.0
        elif k == "Q":
            t = "PNP" if "3906" in str(p.value) or "PNP" in str(p.value).upper() else "NPN"
            pins = {1: p.pins["E"], 2: p.pins["B"], 3: p.pins["C"]}
            props["value"] = p.value
        elif k == "DISP":
            t = "7SEG-CC" if "cathode" in str(p.value) else "7SEG-CA"
            com = p.pins.get("CA", p.pins.get("CC"))
            pins = {3: com, 8: com, **{SEG_PIN[s]: net for s, net in p.pins.items() if s in SEG_PIN}}
            props["value"] = p.value
        else:
            raise ValueError(f"{p.ref}: unknown old part kind {k}")
        spec = {"id": p.ref, "type": t, "props": props, "pins": pins, "old": [p.ref], "chip": None, "part": p}
        if hasattr(p, "pair"):
            props["resistor"] = p.pair
        specs.append(spec)
    for b in banks.values():
        secs = sorted(b["secs"], key=lambda q: q.pos)
        n = len(secs)
        b["type"] = f"DIPSW{n}"
        b["props"]["labels"] = [q.note for q in secs]
        if any(getattr(q, "msb_first", False) for q in secs):
            b["props"]["msb_first"] = True        # switch 1 (leftmost) is the highest bit
        pins = {}
        for k, q in enumerate(secs):
            pins[k + 1] = q.pins["1"]
            pins[2 * n - k] = q.pins["2"]
        b["pins"] = pins
        b["old"] = [q.ref for q in secs]
        b["chip"] = None
        b["sections"] = secs
    return specs


def to_core(N):
    """Old netlist -> (core Netlist sharing the chip models, list of (new model, sync))."""
    C = CoreNetlist()
    syncs = []
    for s in convert(N):
        if s["chip"] is not None:
            C.add(s["id"], s["type"], s["props"], model=s["chip"].model)
        else:
            props = {k: v for k, v in s["props"].items() if k != "pos"}
            m = C.add(s["id"], s["type"], props)
            if "sections" in s:
                secs = s["sections"]
                syncs.append((m, "bank", secs))
            elif s["type"] in ("SW", "BUTTON"):
                syncs.append((m, "closed", s["part"]))
            elif s["type"] in ("SPDT", "JUMPER3"):
                syncs.append((m, "pos", s["part"]))
        for n, net in s["pins"].items():
            C.connect(net, s["id"], n)
    return C, syncs


# ============================================================== Sim
class Sim:
    """pc2sim's Sim on the new zero-delay engine. Switch states are read from the old
    Part objects (.closed, .pos) at every step(), as before."""

    def __init__(self, N):
        self.N = N
        core_n, self._syncs = to_core(N)
        self.core = ZeroDelaySim(core_n, record=False, settle=False)
        self.nets = self.core.nets
        self.readers = self.core.readers
        self.drv = self.core.drv

    @property
    def errors(self):
        return self.core.log

    @property
    def contention(self):
        return self.core.contention

    def refresh_switches(self):
        for m, how, src in self._syncs:
            if how == "bank":
                m.state = [bool(q.closed) for q in src]
            elif how == "closed":
                m.state = bool(src.closed)
            else:
                m.set(src.pos)
        self.core.refresh_switches()

    def step(self):
        """Settle, then fire any clock edges, then settle again."""
        self.refresh_switches()
        self.core.full_resolve()
        self.core.settle()
        self.core.edges()
        return self

    def settle(self, todo=None, limit=20000):
        self.core.settle(todo, limit)
        return self

    def edges(self):
        self.core.edges()

    def full_resolve(self):
        self.core.full_resolve()

    def resolve(self, net):
        return self.core.resolve(net)

    def getter(self, ref):
        return self.core.getter(ref)

    def v(self, net):
        return self.core.nets[net]

    def word(self, prefix, n):
        return self.core.word(prefix, n)


# ============================================================== Bench
def build(control_images=None, display_image=None):
    """The whole PC-2 netlist (pc2_netlist.build)."""
    from ..projects.pc2_netlist import build as _build
    return _build(control_images, display_image)


class Bench:
    """Operate the simulated PC-2 the way a reader operates the real one."""

    def __init__(self, N=None):
        self.N = N or build()
        self.sim = Sim(self.N)
        self.note = {}
        for p in self.N.parts.values():
            if p.note:
                self.note.setdefault(p.note, p)
        self.u = self.N.chips
        self.spdt("RUN / STEP", "STEP")
        self.spdt("PROGRAM / RUN", "RUN")
        self.u["U3"].model.state = 0
        self.u["U1"].model.state = 0
        self.u["U2"].model.state = 0
        self.u["U36"].model.state = 0
        self.N.parts[self.note["speed range jumper"].ref].pos = "FAST"
        self.sim.step()
        self.rises = 0
        self.shown = []

    def spdt(self, label, pos):
        self.note[label].pos = pos

    def switch(self, label, closed):
        self.note[label].closed = bool(closed)

    def press(self, label):
        self.switch(label, True)
        self.sim.step()
        self.switch(label, False)
        self.sim.step()

    def set_bits(self, fmt, value, n=8):
        for k in range(n):
            self.switch(fmt.format(k), (value >> k) & 1)

    def reset(self):
        self.press("RESET")

    def load(self, mem):
        self.spdt("PROGRAM / RUN", "PROG")
        self.sim.step()
        for addr, val in enumerate(mem):
            self.set_bits("address switch {}", addr, 4)
            self.set_bits("data switch {}", val, 8)
            self.sim.step()
            self.press("WRITE")
        back = []
        for addr in range(len(mem)):
            self.set_bits("address switch {}", addr, 4)
            self.sim.step()
            back.append(self.sim.word("RD", 8))
        self.spdt("PROGRAM / RUN", "RUN")
        self.sim.step()
        return back

    def half(self, raw):
        self.u["U1"].model.state = raw
        before = self.sim.v("CLK")
        oi = self.sim.v("OI_n")
        self.sim.step()
        if before == 0 and self.sim.v("CLK") == 1:
            self.rises += 1
            if oi == 0:
                self.shown.append(self.sim.word("OUT", 8))

    def run(self, limit=20000):
        self.u["U3"].model.state = 1
        self.sim.step()
        while self.sim.v("HLT_n") == 1:
            if self.rises >= limit:
                return False
            self.half(1)
            self.half(0)
        return True

    def single_step(self):
        self.u["U3"].model.state = 0
        self.u["U2"].model.state = 1
        before = self.sim.v("CLK")
        oi = self.sim.v("OI_n")
        self.sim.step()
        if before == 0 and self.sim.v("CLK") == 1:
            self.rises += 1
            if oi == 0:
                self.shown.append(self.sim.word("OUT", 8))
        self.u["U2"].model.state = 0
        self.sim.step()

    SEGS = {0x3F: "0", 0x06: "1", 0x5B: "2", 0x4F: "3", 0x66: "4", 0x6D: "5", 0x7D: "6", 0x07: "7",
            0x7F: "8", 0x6F: "9", 0x77: "A", 0x7C: "B", 0x39: "C", 0x5E: "D", 0x79: "E", 0x71: "F",
            0x40: "-", 0x00: " "}

    def display(self):
        """Scan the four digits and read the lit segments, as the eye would."""
        chars = {}
        for _ in range(8):
            s = self.u["U36"].model
            s.state ^= 1
            self.sim.step()
            on = [d for d in range(4) if self.sim.v(f"DSEL{d}_n") == 0]
            assert len(on) == 1, on
            pattern = sum((1 - self.sim.v(f"SEG{k}")) << k for k in range(8))
            chars[on[0]] = self.SEGS.get(pattern, "?")
        return "".join(chars[d] for d in (3, 2, 1, 0))


class _Roms:
    """`roms` as the book imports it: control_images(), display_image(), display_text(), SEG."""

    def __getattr__(self, name):
        from ..projects import pc2_roms
        return getattr(pc2_roms, name)


roms = _Roms()
CONTROL_LINES = ["HLT", "MI", "RI", "RO", "IO", "II", "AI", "AO", "EO", "SU", "BI", "OI",
                 "CE", "CO", "J", "FI", "XO", "SR"]
B = [f"BUS{i}" for i in range(8)]
