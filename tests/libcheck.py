"""Test helpers for the extended chip library (tests/test_lib_*.py).

A tiny one-chip test bench: inputs are held in a dict, outputs are read from the
model's eval(), clocked chips get their edge() result committed as the simulators do.
"""
import itertools

from bbench.chips import get, FloatingInput, Z, X


def getter(values):
    def g(name):
        v = values[name]
        if v == Z or v == X:
            raise FloatingInput(name)
        return v
    return g


def check_pins(type_name, n, vcc, gnd):
    """Pin count, numbering 1..n, unique names, supply pins in the right place."""
    cls = get(type_name)
    assert sorted(cls.PINS) == list(range(1, n + 1)), f"{type_name}: pins are not 1..{n}"
    names = [nm for nm, k in cls.PINS.values()]
    assert len(set(names)) == n, f"{type_name}: duplicate pin names"
    assert cls.PINS[vcc][1] == "vcc" and cls.PINS[gnd][1] == "gnd"
    kinds = [k for nm, k in cls.PINS.values()]
    assert kinds.count("vcc") == 1 and kinds.count("gnd") == 1
    assert cls.DATASHEET.startswith("https://")
    assert cls.FAMILY and cls.DESC
    assert cls.TPD, f"{type_name}: no TPD"


def expand(row):
    """Yield every 0/1 assignment of a row whose values may be 'X' (don't care)."""
    keys = [k for k, v in row.items() if v == "X"]
    for combo in itertools.product((0, 1), repeat=len(keys)):
        r = dict(row)
        r.update(zip(keys, combo))
        yield r


class Bench:
    def __init__(self, type_name, levels=None, **init):
        """levels: starting input levels (others start at 0); init: chip props."""
        self.cls = get(type_name)
        self.chip = self.cls("U1", **init)
        self.v = {nm: 0 for nm, k in self.cls.PINS.values() if k in ("in", "clk", "io")}
        self.v.update(levels or {})
        self.out = {}
        self.settle()

    def set(self, **vals):
        for k, val in vals.items():
            assert k in self.v, f"{self.cls.TYPE} has no input {k}"
            self.v[k] = val
        return self.settle()

    def setp(self, mapping):
        return self.set(**mapping)

    def settle(self):
        g = getter(self.v)
        for _ in range(4):
            if not self.chip.asyncupd(g):
                break
        self.out = self.chip.eval(g)
        return self

    def __getitem__(self, name):
        return self.out[name]

    def edge(self, pin):
        """Drive an active edge on pin (and leave the pin at its new level)."""
        kind = self.cls.EDGE[pin]
        before, after = (0, 1) if kind == "rise" else (1, 0)
        self.set(**{pin: before})
        self.v[pin] = after                 # as in the simulators: the net has its new level
        new = self.chip.edge(getter(self.v), pin)
        self.chip.state = new
        return self.settle()

    def pulse(self, pin, n=1):
        """n full clock pulses: active edge, then back to the idle level."""
        kind = self.cls.EDGE[pin]
        idle = 0 if kind == "rise" else 1
        for _ in range(n):
            self.edge(pin)
            self.set(**{pin: idle})
        return self

    def outs(self, names):
        return [self.out[n] for n in names]
