"""PC-2, the 8-bit breadboard computer of the book, as a Breadboard Bench project:
48 chips, every passive, the four ROM images, 17 breadboards and the board-to-board
wires; also each module as a small project of its own, and Panel, which works the
front panel through the public simulator API.

    from bbench.projects.pc2 import pc2, module_project, Panel, MODULES
    p = pc2()                       # the whole machine (a Project)
    panel = Panel()                 # zero-delay simulator of it, front panel helpers
    panel.load([0xC0, 0x70, 0x00]); panel.set_inputs(42); panel.reset(); panel.run()
    panel.display()                 # '  42'
"""
import copy

from ..project import Project, FORMAT
from ..core.romdata import encode
from ..core.netlist import Netlist
from ..compat.pc2sim import convert
from ..board.autolayout import layout
from . import pc2_netlist, pc2_roms
from .pc2_programs import PROGRAMS
from .sheet import place

# physical rack: (column, slot) of each board (pc2sim/layout.py)
RACK = {
    "Clock": (0, 0), "Program counter": (0, 1), "Memory address": (0, 2), "RAM": (0, 3),
    "Instruction register": (0, 4), "Control sequencer": (0, 5), "Control ROMs": (0, 6),
    "Bus": (1, 0),
    "A register": (2, 0), "ALU": (2, 1), "B register": (2, 2), "Flags": (2, 3),
    "Output": (2, 4), "Display driver": (2, 5), "Display": (2, 6), "Input": (2, 7),
    "Front panel": (1, 6),
}
BOARD_ORDER = sorted(RACK, key=lambda b: (RACK[b][0], RACK[b][1]))
# the rack on the Breadboard tab: one column of boards per rack column, slot 0 at the top.
# A board is drawn 640 x 236 (1:1, with its title); the pitch leaves a hand's width between
# boards, as on the book's rack (columns 18.5 cm apart, slots 6.4 cm).
RACK_PITCH_X, RACK_PITCH_Y = 720, 260
RACK_XY = {b: (c * RACK_PITCH_X, s * RACK_PITCH_Y) for b, (c, s) in RACK.items()}
# the order the book builds the boards in; board-to-board wires are chained in this order
BUILD_ORDER = ["Front panel", "Clock", "Bus", "A register", "B register", "ALU", "Flags",
               "Memory address", "RAM", "Program counter", "Instruction register", "Input", "Output",
               "Display driver", "Display", "Control sequencer", "Control ROMs"]
MODULES = ["Clock", "Bus", "A register", "B register", "ALU", "Flags", "Program counter",
           "Memory address", "RAM", "Instruction register", "Output", "Display", "Input", "Control"]

# the book's signal colours
BUS, CTRL, DATA, CLOCK, ADDR, COPPER = "#D9A21B", "#3D7FD0", "#4E9F3D", "#D64570", "#7B5EA7", "#E8743B"
CONTROL = {"HLT_n", "MI_n", "RI_n", "RO_n", "IO_n", "II_n", "AI_n", "AO_n", "EO_n", "SU_n", "BI_n", "OI_n",
           "CE_n", "CO_n", "J_n", "FI_n", "XO_n", "SR_n", "SU", "CE", "RI"}


def net_colour(net):
    if net.startswith("BUS"):
        return BUS
    if net in CONTROL:
        return CTRL
    if net in ("CLK", "CLK_n", "CLKRAW", "CK_RUN", "CK_STEP", "CK_SEL", "STEPPULSE", "SCANCLK"):
        return CLOCK
    if net == "VCC":
        return "#D7372B"
    if net == "GND":
        return "#222222"
    if net[:2] in ("RA", "PC") or net.startswith("MAR") or net.startswith("STEP") or net.startswith("LOP"):
        return ADDR
    if net in ("RST", "RST_n", "PROG", "RUNSEL", "RUNSEL_n"):
        return COPPER
    return DATA


TTL_SOURCES = ("AT28C256", "AS6C62256", "NE555")


def family(N):
    """Where 74HCT is *needed*: an input driven by a memory or 555 output (pc2sim/bomgen.py's
    rule). The kit and to_project() use 74HCT for every logic chip; this is kept for scripts
    that want to know which sockets would not take a 74HC part."""
    src = {}
    for ref, pc in N.chips.items():
        if pc.cls.TYPE in TTL_SOURCES:
            for n, net in pc.pinnet.items():
                if pc.cls.PINS[n][1] in ("out", "tri", "io"):
                    src[net] = ref
    fam = {}
    for ref, pc in N.chips.items():
        if not pc.cls.TYPE.startswith("74"):
            continue
        need = False
        for n, net in pc.pinnet.items():
            name, kind = pc.cls.PINS[n]
            if net not in src:
                continue
            if kind in ("in", "clk"):
                need = True
            if kind == "io":
                dir_net = pc.pinnet[1]
                side_in = "A" if dir_net == "VCC" else ("B" if dir_net == "GND" else "AB")
                if name[0] in side_in:
                    need = True
        fam[ref] = "HCT" if need else "HC"
    return fam


DEFAULT_POS = {"RUN / STEP": "STEP", "PROGRAM / RUN": "RUN", "speed range jumper": "FAST"}


def to_project(N, name="PC-2", notes="", hct=True, boards=True):
    """An old-style netlist (pc2_netlist.build) -> project dict, with breadboards.
    hct=True makes every 74HC logic chip the 74HCT part, as in the kit."""
    specs = convert(N)
    parts = []
    for s in specs:
        t = s["type"]
        if hct and t.startswith("74HC") and not t.startswith("74HCT"):
            t = "74HCT" + t[4:]
        props = dict(s["props"])
        if s["chip"] is not None and s["chip"].image is not None:
            props["image"] = encode(s["chip"].image)
        if t in ("SPDT", "JUMPER3"):
            props["pos"] = DEFAULT_POS.get(props.get("label"), props.get("pos"))
        parts.append({"id": s["id"], "type": t, "x": 0, "y": 0, "rot": 0, "props": props})
    nets = {}
    for s in specs:
        for n, net in sorted(s["pins"].items()):
            nets.setdefault(net, []).append([s["id"], str(n)])
    data = {"format": FORMAT, "name": name, "notes": notes, "parts": parts,
            "nets": [{"name": k, "pins": v} for k, v in nets.items()],
            "schematic": {"wires": [], "labels": []}, "breadboards": [], "links": [],
            "stimuli": [], "probes": []}
    if boards:
        core = Netlist.from_project(data, strict=True)
        data["breadboards"], data["links"] = layout(data, core, BOARD_ORDER, BUILD_ORDER, net_colour,
                                                    positions=RACK_XY)
    place(data, MODULES)
    return data


_CACHE = {}


def _whole():
    if "pc2" not in _CACHE:
        N = pc2_netlist.build()
        notes = ("PC-2, the 8-bit breadboard computer of The Breadboard Computer: every chip pin, "
                 "the four ROM images and the 17 breadboards of the build. Programs: "
                 + ", ".join(PROGRAMS) + ".")
        d = to_project(N, "PC-2", notes)
        d["stimuli"] = [{"part": "U1", "role": "main"}, {"part": "U36", "role": "scan"}]
        d["probes"] = ["CLK", "HLT_n", "STEP0", "STEP1", "STEP2"] + [f"BUS{k}" for k in range(8)] + \
                      ["MI_n", "RO_n", "II_n", "AI_n", "AO_n", "EO_n", "OI_n", "CE_n", "CO_n", "SR_n"]
        d["programs"] = {k: {"mem": v["mem"], "notes": v["notes"]} for k, v in PROGRAMS.items()}
        _CACHE["pc2"] = d
    return _CACHE["pc2"]


def pc2():
    """The whole PC-2 as a Project."""
    return Project(copy.deepcopy(_whole()))


def _always_drives(model, n, pinnet):
    """Does chip pin n drive its net whenever the circuit runs? An output; a tri-state or
    bidirectional pin whose output enables (OE; a 74x173's M and N) are tied to a rail, and
    for a transceiver with DIR tied to a rail only the side it drives (a ROM with OE on GND
    always drives its data pins; a 74x245 enabled by a control line does not)."""
    name, kind = model.PINS[n]
    if kind == "out":
        return True
    if kind not in ("tri", "io"):
        return False
    net = {model.PINS[k][0]: v for k, v in pinnet.items()}
    for en in ("OE", "M", "N"):
        if en in model.names and net.get(en) not in ("VCC", "GND"):
            return False
    if kind == "io" and "DIR" in model.names:
        side = {"VCC": "B", "GND": "A"}.get(net.get("DIR"))
        return bool(side) and name.startswith(side)
    return True


def module_project(module):
    """One PC-2 module as a small standalone project: its own parts, plus a switch
    (with a 10 k pull-down) for every signal that comes from another module, and a
    button for its clock."""
    if module not in MODULES:
        raise KeyError(f"no PC-2 module {module!r} (have {MODULES})")
    whole = _whole()
    keep = [p for p in whole["parts"] if p["props"].get("module") == module]
    ids = {p["id"] for p in keep}
    N = Netlist.from_project(whole)
    mine = {}
    for net, pins in N.nets.items():
        own = [(pid, n) for pid, n in pins if pid in ids]
        if own:
            mine[net] = own
    # nets this module reads but does not drive by itself
    inputs = []
    for net, own in mine.items():
        if net in ("VCC", "GND"):
            continue
        others = [pid for pid, n in N.nets[net] if pid not in ids]
        if not others:
            continue
        reads = drives_out = False
        for pid, n in own:
            m = N.parts[pid]
            if hasattr(m, "eval"):
                kind = m.PINS[n][1]
                if _always_drives(m, n, N.pinnet[pid]):
                    drives_out = True
                elif kind in ("in", "clk", "io", "ana"):
                    reads = True
        if reads and not drives_out:
            inputs.append(net)
    parts = copy.deepcopy(keep)
    nets = {net: [[pid, str(n)] for pid, n in own] for net, own in mine.items()}
    k = 0
    for net in inputs:
        k += 1
        clocky = net in ("CLK", "CLK_n", "SCANCLK", "CLKRAW")
        sid, rid = f"IN{k}", f"RIN{k}"
        parts.append({"id": sid, "type": "BUTTON" if clocky else "SW", "x": 0, "y": 0, "rot": 0,
                      "props": {"label": net, "module": module, "role": "input"}})
        parts.append({"id": rid, "type": "R", "x": 0, "y": 0, "rot": 0,
                      "props": {"value": "10k", "label": "pull-down", "module": module, "role": "input"}})
        if clocky:
            nets.setdefault("VCC", []).extend([[sid, "1"], [sid, "2"]])
            nets[net].extend([[sid, "3"], [sid, "4"]])
        else:
            nets.setdefault("VCC", []).append([sid, "1"])
            nets[net].append([sid, "2"])
        nets[net].append([rid, "1"])
        nets.setdefault("GND", []).append([rid, "2"])
    data = {"format": FORMAT, "name": f"PC-2 {module}",
            "notes": f"The {module} module of PC-2 on its own. The switches IN1, IN2, ... stand in for "
                     f"the signals that come from other modules: {', '.join(inputs) or 'none'}.",
            "parts": parts, "nets": [{"name": n, "pins": v} for n, v in nets.items()],
            "schematic": {"wires": [], "labels": []}, "breadboards": [], "links": [],
            "stimuli": [], "probes": [n for n in mine if n not in ("VCC", "GND") and "~" not in n][:24]}
    for p in data["parts"]:
        if p["type"] == "NE555":
            p["props"]["mode"] = "manual" if module != "Clock" else p["props"].get("mode", "auto")
    place(data)
    return Project(data)


# ====================================================================== front panel
class Panel:
    """Work PC-2's front panel through the public simulator API, as a reader would:
    real switches, buttons, the bistable RUN/STEP debouncer and the STEP monostable."""

    SEGS = {0x3F: "0", 0x06: "1", 0x5B: "2", 0x4F: "3", 0x66: "4", 0x6D: "5", 0x7D: "6", 0x07: "7",
            0x7F: "8", 0x6F: "9", 0x77: "A", 0x7C: "B", 0x39: "C", 0x5E: "D", 0x79: "E", 0x71: "F",
            0x40: "-", 0x00: " "}

    def __init__(self, sim=None, mode="zero"):
        self.sim = sim or pc2().simulator(mode, record=False)
        s = self.sim
        self.digit = {}
        for pid, pr in s.N.props.items():
            lab = pr.get("label", "")
            if s.N.types[pid].startswith("7SEG") and lab.startswith("digit "):
                self.digit[int(lab.split()[1])] = pid
        self.rises = 0
        self.shown = []

    def power_cycle(self):
        self.sim.drive("RUN / STEP", "STEP")
        self.sim.drive("PROGRAM / RUN", "RUN")
        self.sim.power_cycle()
        self.rises = 0
        self.shown = []

    def load(self, mem):
        """PROGRAM mode, set the switches and press WRITE for each byte; read every byte
        back from the RAM data LEDs."""
        s = self.sim
        s.set("PROGRAM / RUN", "PROG")
        self._wait()
        for addr, val in enumerate(mem):
            s.drive("S1", addr)
            s.drive("S2", val)
            s.update()
            self._wait()
            self._press("WRITE")
        back = []
        for addr in range(len(mem)):
            s.set("S1", addr)
            self._wait()
            back.append(s.word("RD", 8))
        s.set("PROGRAM / RUN", "RUN")
        self._wait()
        return back

    def _wait(self):
        """In the timed simulator, give the logic a moment (2 us) after each action."""
        if self.sim.mode == "timed":
            self.sim.run_ns(2000)

    def _press(self, pid):
        if self.sim.mode == "timed":
            self.sim.press(pid, hold_ns=5000)
            self._wait()
        else:
            self.sim.press(pid)

    def set_inputs(self, a=0, b=0):
        self.sim.drive("S3", a)
        self.sim.drive("S4", b)
        self.sim.update()
        self._wait()

    def reset(self):
        self._press("RESET")

    def _watch(self, fn):
        s = self.sim
        before, oi = s.v("CLK"), s.v("OI_n")
        fn()
        if before == 0 and s.v("CLK") == 1:
            self.rises += 1
            if oi == 0:
                self.shown.append(s.word("OUT", 8))

    def half(self, level):
        self._watch(lambda: self.sim.half(level, "U1"))

    def run(self, limit=20000):
        """RUN mode, clock until HLT stops it. False if it did not halt within limit cycles."""
        s = self.sim
        s.set("RUN / STEP", "RUN")
        if s.mode == "timed":                      # the 555 clock runs by itself
            r = s.run("halt", limit=limit)
            self.rises += r["cycles"]
            return r["done"]
        while s.v("HLT_n") == 1:
            if self.rises >= limit:
                return False
            self.half(1)
            self.half(0)
        return True

    def single_step(self):
        """STEP mode, one press of STEP."""
        s = self.sim
        ref, _ = s._target("RUN / STEP")
        if s.N.parts[ref].get() != "STEP":
            s.set("RUN / STEP", "STEP")
        s.drive("STEP", True)
        self._watch(s.update)
        s.drive("STEP", False)
        self._watch(s.update)

    def display(self):
        """The four digits as the eye sees them."""
        dg = self.sim.state()["digits"]
        return "".join(self.SEGS.get(dg.get(self.digit[d], 0), "?") for d in (3, 2, 1, 0))

    def leds(self):
        return self.sim.state(persist=False)["leds"]
