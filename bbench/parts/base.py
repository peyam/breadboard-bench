"""Base class and registry for passives and I/O parts (resistors, LEDs, switches ...).

A part has numbered pins like a chip: PINS = {1: ("A", "pas"), 2: ("K", "pas")}.
It takes no part in logic evaluation; instead it tells the simulator
- which pins it currently joins (``links()``): closed switches are strong links,
  resistors are weak links (a pull-up, a pull-down, or a series resistor that a net
  follows when nothing else drives it);
- what it shows (``show(value)``), for indicators: LEDs, 7-segment digits, probes.

Active parts that do drive outputs (transistors, clock source) are Chip subclasses
and live in this package too (CATEGORY "active").

FOOTPRINT says how the part sits on a breadboard (see bbench.board.model):
  {"kind": "leads"}                   free legs, placed leg by leg
  {"kind": "dip", "width": 3 | 6}     dual in-line (pin 1 at the anchor hole)
  {"kind": "sip", "pitch": 1}         single in-line, pins in consecutive rows
  {"kind": "button"}                  4-leg tactile switch across the centre gap
  {"kind": "virtual"}                 not placed on a board (an instrument)
INTERNAL lists pin pairs joined inside the part (a button's legs, a digit's two
common pins).
"""
from ..core.analog import parse_value

PARTS = {}


def part(cls):
    """Class decorator: add a part class to PARTS under cls.TYPE (and its ALIASES)."""
    if cls.TYPE in PARTS and PARTS[cls.TYPE] is not cls:
        raise ValueError(f"part type {cls.TYPE} registered twice")
    PARTS[cls.TYPE] = cls
    for a in getattr(cls, "ALIASES", ()):
        PARTS.setdefault(a, cls)
    return cls


class Part:
    TYPE = "?"
    DESC = ""
    FAMILY = "part"
    CATEGORY = "passive"          # passive, switch, indicator, source, active
    PINS = {}
    FOOTPRINT = {"kind": "leads"}
    INTERNAL = ()
    DEFAULTS = {}

    def __init__(self, ref="X?", **props):
        self.ref = ref
        p = dict(self.DEFAULTS)
        p.update(props)
        self.props = p
        self.state = None
        self.names = {name: n for n, (name, k) in self.PINS.items()}

    # simulation ------------------------------------------------------------
    def links(self):
        """[(pin_a, pin_b, "strong" | "weak", ohms_or_None, who)] currently conducting."""
        return []

    def show(self, value):
        """Indicator view; value(pin_number) gives the net value on a pin."""
        return None

    def set(self, value, section=None):
        raise TypeError(f"{self.ref} ({self.TYPE}) cannot be set")

    def get(self):
        return self.state

    def sections(self):
        return []

    # metadata --------------------------------------------------------------
    @classmethod
    def pin_number(cls, name):
        for n, (nm, k) in cls.PINS.items():
            if nm == name:
                return n
        raise KeyError(f"{cls.TYPE} has no pin {name}")

    @classmethod
    def info(cls):
        return {"type": cls.TYPE, "desc": cls.DESC, "family": cls.FAMILY, "category": cls.CATEGORY,
                "pins": [[n, nm, k] for n, (nm, k) in sorted(cls.PINS.items())],
                "footprint": dict(cls.FOOTPRINT), "internal": [list(p) for p in cls.INTERNAL],
                "defaults": dict(cls.DEFAULTS), "datasheet": ""}

    def ohms(self):
        return parse_value(self.props.get("value"))


def two(a="1", b="2"):
    return {1: (a, "pas"), 2: (b, "pas")}
