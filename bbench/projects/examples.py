"""Small example projects, each laid out on one breadboard.

    from bbench.projects.examples import EXAMPLES
    p = EXAMPLES["xor-from-nand"]()
"""
from ..project import Project, FORMAT
from ..core.netlist import Netlist, lookup_type
from ..board.autolayout import layout


class _B:
    """A tiny builder: parts by type, connections by pin name or number."""

    def __init__(self, name, notes):
        self.name, self.notes = name, notes
        self.parts, self.nets, self.n = [], {}, {}
        self.probes = []

    def add(self, pid, type_name, x=0, y=0, **props):
        self.parts.append({"id": pid, "type": type_name, "x": x, "y": y, "rot": 0, "props": props})
        return pid

    def c(self, net, *pins):
        cls_of = {p["id"]: lookup_type(p["type"]) for p in self.parts}
        for pid, pin in pins:
            cls = cls_of[pid]
            n = pin if isinstance(pin, int) or str(pin).isdigit() else cls.pin_number(pin)
            self.nets.setdefault(net, []).append([pid, str(n)])

    def power(self, pid):
        cls = lookup_type(next(p["type"] for p in self.parts if p["id"] == pid))
        for n, (name, kind) in cls.PINS.items():
            if kind == "vcc":
                self.c("VCC", (pid, n))
            if kind == "gnd":
                self.c("GND", (pid, n))

    def switch(self, pid, net, x=0, y=0):
        """A switch to +5 V with a 10 k pull-down: closed = 1."""
        self.add(pid, "SW", x, y, label=net)
        self.add("R" + pid, "R", x, y + 40, value="10k", label=f"pull-down {net}")
        self.c("VCC", (pid, 1))
        self.c(net, (pid, 2), ("R" + pid, 1))
        self.c("GND", ("R" + pid, 2))

    def button(self, pid, net, x=0, y=0, to="VCC"):
        """A push button with a 10 k pull resistor: pressed = 1 (to VCC) or 0 (to GND)."""
        self.add(pid, "BUTTON", x, y, label=net)
        self.add("R" + pid, "R", x, y + 40, value="10k", label="pull-down" if to == "VCC" else "pull-up")
        self.c(to, (pid, 1), (pid, 2))
        self.c(net, (pid, 3), (pid, 4), ("R" + pid, 1))
        self.c("GND" if to == "VCC" else "VCC", ("R" + pid, 2))

    def led(self, pid, net, colour="red", x=0, y=0):
        self.add("R" + pid, "R", x, y, value="1k", label=f"LED resistor ({net})")
        self.add(pid, "LED", x, y + 40, colour=colour, label=net)
        self.c(net, ("R" + pid, 1))
        self.c(f"{net}~LED", ("R" + pid, 2), (pid, "A"))
        self.c("GND", (pid, "K"))
        self.probes.append(net)

    def decouple(self, chip):
        self.add("C" + chip, "C", 0, 0, value="100nF", label=f"decoupling {chip}")
        self.c("VCC", ("C" + chip, 1))
        self.c("GND", ("C" + chip, 2))

    def tie_unused(self, chip, pins):
        for p in pins:
            self.c("GND", (chip, p))

    def project(self, stimuli=None):
        for p in self.parts:
            p["props"].setdefault("board", "Main")
        data = {"format": FORMAT, "name": self.name, "notes": self.notes, "parts": self.parts,
                "nets": [{"name": k, "pins": v} for k, v in self.nets.items()],
                "schematic": {"wires": [], "labels": []}, "breadboards": [], "links": [],
                "stimuli": stimuli or [], "probes": self.probes}
        N = Netlist.from_project(data, strict=True)
        data["breadboards"], data["links"] = layout(data, N, ["Main"], ["Main"])
        return Project(data)


def nand_gate():
    b = _B("A NAND gate", "One gate of a 74HC00. Close the switches: the LED goes out only when both inputs are 1.")
    b.add("U1", "74HC00", 200, 100)
    b.power("U1")
    b.switch("SA", "A", 0, 60)
    b.switch("SB", "B", 0, 160)
    b.c("A", ("U1", "1A"))
    b.c("B", ("U1", "1B"))
    b.c("Y", ("U1", "1Y"))
    b.tie_unused("U1", ["2A", "2B", "3A", "3B", "4A", "4B"])
    b.led("D1", "Y", "red", 420, 100)
    b.decouple("U1")
    b.probes[:0] = ["A", "B"]
    return b.project()


def nor_from_nand():
    b = _B("NOR from NAND gates", "NOT A and NOT B (NAND gates with joined inputs), a NAND of those is A OR B, "
                                  "and one more NAND as an inverter gives A NOR B. All four gates of one 74HC00.")
    b.add("U1", "74HC00", 200, 100)
    b.power("U1")
    b.switch("SA", "A", 0, 60)
    b.switch("SB", "B", 0, 160)
    b.c("A", ("U1", "1A"), ("U1", "1B"))
    b.c("NA", ("U1", "1Y"), ("U1", "3A"))
    b.c("B", ("U1", "2A"), ("U1", "2B"))
    b.c("NB", ("U1", "2Y"), ("U1", "3B"))
    b.c("OR", ("U1", "3Y"), ("U1", "4A"), ("U1", "4B"))
    b.c("NOR", ("U1", "4Y"))
    b.led("D1", "NOR", "red", 420, 100)
    b.decouple("U1")
    b.probes[:0] = ["A", "B", "OR"]
    return b.project()


def xor_from_nand():
    b = _B("XOR from four NAND gates", "M = A NAND B; then (A NAND M) NAND (B NAND M) is A XOR B.")
    b.add("U1", "74HC00", 200, 100)
    b.power("U1")
    b.switch("SA", "A", 0, 60)
    b.switch("SB", "B", 0, 160)
    b.c("A", ("U1", "1A"), ("U1", "2A"))
    b.c("B", ("U1", "1B"), ("U1", "3B"))
    b.c("M", ("U1", "1Y"), ("U1", "2B"), ("U1", "3A"))
    b.c("P", ("U1", "2Y"), ("U1", "4A"))
    b.c("Q", ("U1", "3Y"), ("U1", "4B"))
    b.c("XOR", ("U1", "4Y"))
    b.led("D1", "XOR", "red", 420, 100)
    b.decouple("U1")
    b.probes[:0] = ["A", "B", "M"]
    return b.project()


def sr_latch():
    b = _B("SR latch", "Two cross-coupled NAND gates remember one bit. Press SET (S goes low): Q = 1. "
                       "Press RESET (R goes low): Q = 0. Let go and the latch keeps its value.")
    b.add("U1", "74HC00", 200, 100)
    b.power("U1")
    b.button("BS", "S_n", 0, 60, to="GND")
    b.button("BR", "R_n", 0, 180, to="GND")
    b.parts[-4]["props"]["label"] = "SET"
    b.parts[-2]["props"]["label"] = "RESET"
    b.c("S_n", ("U1", "1A"))
    b.c("Q", ("U1", "1Y"), ("U1", "2A"))
    b.c("R_n", ("U1", "2B"))
    b.c("Q_n", ("U1", "2Y"), ("U1", "1B"))
    b.tie_unused("U1", ["3A", "3B", "4A", "4B"])
    b.led("D1", "Q", "red", 420, 80)
    b.led("D2", "Q_n", "yellow", 420, 180)
    b.decouple("U1")
    b.probes[:0] = ["S_n", "R_n"]
    return b.project()


def d_flip_flop():
    b = _B("D flip-flop", "A 74HC174 D flip-flop: on each press of CLOCK, Q takes the value of the D switch.")
    b.add("U1", "74HC174", 200, 100)
    b.power("U1")
    b.switch("SD", "D", 0, 60)
    b.button("BC", "CLK", 0, 180)
    b.parts[-2]["props"]["label"] = "CLOCK"
    b.c("D", ("U1", "1D"))
    b.c("CLK", ("U1", "CLK"))
    b.c("VCC", ("U1", "CLR"))
    b.c("Q", ("U1", "1Q"))
    b.tie_unused("U1", ["2D", "3D", "4D", "5D", "6D"])
    b.led("D1", "Q", "red", 420, 100)
    b.decouple("U1")
    b.probes[:0] = ["D", "CLK"]
    return b.project()


def _astable(b, ref, out, r1, r2, c, x=0, y=0):
    b.add(ref, "NE555", x, y)
    b.power(ref)
    b.add("R1" + ref, "R", x - 120, y, value=r1, label="astable R1")
    b.add("R2" + ref, "R", x - 120, y + 50, value=r2, label="astable R2")
    b.add("C1" + ref, "C", x - 120, y + 100, value=c, label="timing capacitor", polarised=True)
    b.add("C2" + ref, "C", x - 120, y + 150, value="10nF", label="control-voltage decoupling")
    b.c("VCC", (ref, "RESET"), ("R1" + ref, 1))
    b.c(f"DIS_{ref}", (ref, "DIS"), ("R1" + ref, 2), ("R2" + ref, 1))
    b.c(f"CT_{ref}", (ref, "THR"), (ref, "TRIG"), ("R2" + ref, 2), ("C1" + ref, 1))
    b.c("GND", ("C1" + ref, 2))
    b.c(f"CV_{ref}", (ref, "CTRL"), ("C2" + ref, 1))
    b.c("GND", ("C2" + ref, 2))
    b.c(out, (ref, "OUT"))


def clock_555():
    b = _B("555 astable clock", "A 555 timer as a clock: t_high = 0.693 (R1 + R2) C, t_low = 0.693 R2 C. "
                                "With 1 k, 68 k and 10 uF it blinks about once a second.")
    _astable(b, "U1", "CLK", "1k", "68k", "10uF", 200, 100)
    b.led("D1", "CLK", "yellow", 420, 100)
    b.decouple("U1")
    return b.project()


def counter_4bit():
    b = _B("4-bit counter", "A 74HCT161 counts the 555 clock (about 2 Hz) in binary on four LEDs; "
                            "RESET clears it. The chips are 74HCT because a 555's high output "
                            "(2.75 V at least) is too low for a 74HC input (3.15 V).")
    _astable(b, "U1", "CLK", "1k", "330k", "1uF", 0, 100)
    b.add("U2", "74HCT161", 300, 100)
    b.power("U2")
    b.button("BR", "RST", 0, 300)
    b.parts[-2]["props"]["label"] = "RESET"
    b.add("U3", "74HCT04", 300, 300)
    b.power("U3")
    b.c("RST", ("U3", "1A"))
    b.c("CLR_n", ("U3", "1Y"), ("U2", "CLR"))
    b.tie_unused("U3", ["2A", "3A", "4A", "5A", "6A"])
    b.c("CLK", ("U2", "CLK"))
    b.c("VCC", ("U2", "ENP"), ("U2", "ENT"), ("U2", "LOAD"))
    b.tie_unused("U2", ["A", "B", "C", "D"])
    for k, q in enumerate(["QA", "QB", "QC", "QD"]):
        b.c(f"Q{k}", ("U2", q))
    for k in (3, 2, 1, 0):
        b.led(f"D{k + 1}", f"Q{k}", "green", 520, 60 * (3 - k))
    b.decouple("U1")
    b.decouple("U2")
    b.decouple("U3")
    b.probes[:0] = ["CLK", "CLR_n"]
    return b.project()


EXAMPLES = {"nand-gate": nand_gate, "nor-from-nand": nor_from_nand, "xor-from-nand": xor_from_nand,
            "sr-latch": sr_latch, "d-flip-flop": d_flip_flop, "555-clock": clock_555,
            "4-bit-counter": counter_4bit}
TITLES = {"nand-gate": "A NAND gate", "nor-from-nand": "NOR from NAND gates",
          "xor-from-nand": "XOR from four NAND gates", "sr-latch": "SR latch", "d-flip-flop": "D flip-flop",
          "555-clock": "555 astable clock", "4-bit-counter": "4-bit counter"}
