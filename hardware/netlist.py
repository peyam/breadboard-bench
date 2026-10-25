"""Netlist structures for PC-2: chips placed on module boards, passives, and named nets.

The netlist is the single source of truth. The simulator, schematic drawings,
breadboard wire lists and the parts list are all generated from it.
"""
from collections import defaultdict
from chips import CHIP_TYPES

RAILS = {"VCC": 1, "GND": 0}


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
        self.model = cls(ref, image) if image is not None else cls(ref)
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
        # power pins are always wired the same way
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

    # convenience builders ------------------------------------------------
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

    # queries ---------------------------------------------------------------
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
