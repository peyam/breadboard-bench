"""Chip base class, pin helpers and the chip registry of Breadboard Bench.

This interface is stable: every chip module in ``bbench.chips`` builds on it.

Writing a chip
--------------
::

    from .base import Chip, pins, bit, soft, register, Z

    @register
    class HC00(Chip):
        TYPE = "74HC00"                       # part number (registry key, unique)
        DESC = "Quad 2-input NAND"            # one line, plain words
        FAMILY = "HC"                         # "HC", "HCT", "LS", "CMOS", "memory", "timer", ...
        DATASHEET = "https://www.ti.com/lit/ds/symlink/sn74hc00.pdf"
        PINS = pins("1:1A:in 2:1B:in 3:1Y:out 7:GND:gnd 14:VCC:vcc ...")
        TPD = {("*", "*"): 20}                # ns, worst case at 4.5 V, 25 degC
        def eval(self, g):
            return {"1Y": 1 - (bit(g("1A")) & bit(g("1B"))), ...}

Class attributes
----------------
TYPE       part number, the registry key ("74HC173").
DESC       short description.
FAMILY     logic family or kind: "HC", "HCT", "LS", "CMOS", "memory", "timer", ...
PINS       {number: (name, kind)}; kind is one of KINDS:
           in, out, tri (tri-state output), io (bidirectional), clk (edge input),
           vcc, gnd, ana (analogue, read only through soft()), nc (no connection).
           Build it with pins("1:1A:in 2:1B:in ...").
EDGE       {clock pin name: "rise" | "fall"}.
TPD        {(from, to): ns}. ``from``/``to`` are pin names, "*" or fnmatch patterns
           ("A?", "*Q"). Lookup (Chip.tpd): exact/exact first, then exact/pattern,
           pattern/exact, pattern/pattern, each in dict order. Missing: DEFAULT_TPD.
           Use worst-case datasheet values at 4.5 V, 25 degC.
TDIS       optional {(from, to): ns}: the delay when an output turns off (goes to "Z"),
           the datasheet's disable time (tdis, tPHZ/tPLZ, tOHZ, tDF). Missing: TPD.
ADDR_HOLD  memories only: the output hold time tOH in ns. In the timed simulator the data
           outputs are unknown ("X") from ADDR_HOLD after an address change until the
           access time (the TPD of the address path). None: not modelled.
DRIVE      optional {"test_mA", "abs_max_mA", ...}: output current figures from the sheet.
SETUP      ns, or {pin name: ns}: data must be steady this long before the clock edge.
HOLD       ns, or {pin name: ns}: data must stay steady this long after the edge.
SAMPLED    {clock pin: [input pin names sampled at that edge]}. Default: every "in"
           pin (used only for setup/hold checks in the timed simulator).
DATASHEET  URL of the manufacturer's datasheet.
PACKAGE    "DIP14", "DIP28", ... (default "DIP<number of pins>").
WIDTH      row spacing in 0.1 in units: 3 (0.3 in) or 6 (0.6 in).
           Default: 6 for 24 pins or more, else 3.
VIH, VIL   input thresholds in volts (an input reads 1 at or above VIH, 0 at or below
           VIL); VOH, VOL the output levels it guarantees. Default: from FAMILY (LEVELS);
           None where the datasheet gives no logic level (a 555's analogue inputs).
TABLE      optional function table for the library card:
           {"inputs": [...], "outputs": [...], "rows": [[...], ...]} (strings/ints).

Methods (override as needed)
----------------------------
reset_state()        -> the power-up state (any value; copied into self.state).
eval(g)              -> {output pin name: 0 | 1 | "Z" | "X"}. Combinational view of the
                        outputs from the inputs and self.state. Must not change state.
edge(g, clkpin)      -> the NEXT state after an active edge on clkpin. Do not assign
                        self.state: the simulator commits all edges together.
asyncupd(g)          -> level-sensitive state change (async clear, RAM write); change
                        self.state in place and return True if it changed.
io_is_input(name, g) -> optional: is io pin ``name`` an input right now.
configure(ctx)       -> optional: called once by a simulator after the netlist is built.
                        ctx.pin_net(pin_name) gives the net on a pin (or None),
                        ctx.parts_on(net) gives [(part id, type, pin, props)], ctx.props
                        are this part's project props, ctx.resistance(net_a, net_b) gives
                        ohms (or None) and ctx.capacitance(net_a, net_b) farads through
                        the passives. Default does nothing.
wake_ns / wakeup(g)  -> optional timer hook (timed simulator only): set self.wake_ns to
                        a delay in ns inside asyncupd(); after that delay the simulator
                        calls wakeup(g), which changes self.state and returns True if
                        it changed (used by the 555 monostable).
Raise InCircuitWrite (a RuntimeError) from asyncupd() when a part that must not be
written in circuit (an EEPROM) is written; the simulators report it as an error.

``g(name)`` reads an input pin and returns 0 or 1; it raises FloatingInput when the
net is floating ("Z") or unknown ("X"). Use ``bit(v)`` to check a value, and
``soft(g, name)`` to read a pin whose value only passes through to an output (gives
"X" instead of raising), as a bus transceiver does.

Construction: ``Cls(ref, **props)``. A subclass with its own __init__ must accept
``ref`` first and call ``super().__init__(ref, **props)``.

Registry
--------
``@register`` adds a class to REGISTRY under its TYPE. If a TYPE is registered twice
the first class is kept and the clash is noted in DUPLICATES (tests check that it is
empty). ``get(type_name)`` returns the class, ``types()`` lists all TYPE strings.
"""
from fnmatch import fnmatchcase

Z = "Z"
X = "X"
KINDS = ("in", "out", "tri", "io", "clk", "vcc", "gnd", "ana", "nc")
DEFAULT_TPD = 10.0          # ns, used when a chip gives no figure for a path

REGISTRY = {}
DUPLICATES = []

# Logic levels by family, in volts, from the datasheets' DC tables at VCC = 4.5 V, 25 degC
# (VOH/VOL at |IO| = 4 mA): (VIH min, VIL max, VOH min, VOL max). HCT and LS have TTL input
# thresholds (VIH 2.0 V), so a TTL-level output (VOH 2.4 V: memories, the 555) drives
# them safely; HC needs VIH 3.15 V at 4.5 V and does not.
LEVELS = {
    "HC": (3.15, 1.35, 3.98, 0.26),
    "HCT": (2.0, 0.8, 3.98, 0.26),
    "LS": (2.0, 0.8, 2.7, 0.5),
    "CMOS": (3.15, 1.35, 3.98, 0.26),
}


class FloatingInput(Exception):
    """An input read a floating ("Z") or unknown ("X") net."""


class InCircuitWrite(RuntimeError):
    """A part that must not be written in circuit (an EEPROM) saw a write."""


def pins(spec):
    """'1:1A:in 2:1B:in ...' -> {1: ('1A', 'in'), 2: ('1B', 'in'), ...}"""
    out = {}
    for tok in spec.split():
        n, name, kind = tok.split(":")
        if kind not in KINDS:
            raise ValueError(f"pin {n} {name}: unknown kind {kind!r}")
        out[int(n)] = (name, kind)
    return out


def bit(v):
    """Return v if it is 0 or 1; raise FloatingInput for "Z" or "X"."""
    if v == Z or v == X:
        raise FloatingInput()
    return v


def soft(g, name):
    """Read an input that only passes through to an output: an unknown in gives an unknown out."""
    try:
        return g(name)
    except FloatingInput:
        return X


class Chip:
    TYPE = "?"
    DESC = ""
    FAMILY = ""
    PINS = {}
    EDGE = {}
    TPD = {}
    TDIS = None
    ADDR_HOLD = None
    DRIVE = None
    SETUP = 0
    HOLD = 0
    SAMPLED = {}
    DATASHEET = ""
    PACKAGE = None
    WIDTH = None
    TABLE = None
    VIH = VIL = VOH = VOL = None          # None: take them from LEVELS[FAMILY]

    def __init__(self, ref="U?", **props):
        self.ref = ref
        self.props = props
        self.state = self.reset_state()
        self.names = {name: n for n, (name, k) in self.PINS.items()}

    # ---------------------------------------------------------------- behaviour
    def reset_state(self):
        return None

    def reset(self):
        self.state = self.reset_state()

    def eval(self, g):
        return {}

    def asyncupd(self, g):
        """Level-sensitive state changes (async clear, RAM write). Return True if state changed."""
        return False

    def edge(self, g, clkpin):
        return self.state

    def configure(self, ctx):
        return None

    # ---------------------------------------------------------------- metadata
    @classmethod
    def pin_number(cls, name):
        for n, (nm, k) in cls.PINS.items():
            if nm == name:
                return n
        raise KeyError(f"{cls.TYPE} has no pin {name}")

    @classmethod
    def pin_name(cls, n):
        return cls.PINS[int(n)][0]

    @classmethod
    def package(cls):
        return cls.PACKAGE or f"DIP{len(cls.PINS)}"

    @classmethod
    def width(cls):
        if cls.WIDTH:
            return cls.WIDTH
        return 6 if len(cls.PINS) >= 24 else 3

    @classmethod
    def tpd(cls, frm, to):
        """Propagation delay in ns from input pin ``frm`` to output pin ``to``."""
        cache = cls.__dict__.get("_tpd_cache")
        if cache is None:
            cache = {}
            cls._tpd_cache = cache
        key = (frm, to)
        v = cache.get(key)
        if v is None:
            v = cls._tpd_lookup(frm, to)
            cache[key] = v
        return v

    @classmethod
    def tdis(cls, frm, to):
        """Disable delay in ns (an output going to "Z"): from TDIS, else the TPD figure."""
        if not cls.TDIS:
            return cls.tpd(frm, to)
        cache = cls.__dict__.get("_tdis_cache")
        if cache is None:
            cache = {}
            cls._tdis_cache = cache
        key = (frm, to)
        v = cache.get(key)
        if v is None:
            v = cls._tpd_lookup(frm, to, cls.TDIS)
            if v is None:
                v = cls.tpd(frm, to)
            cache[key] = v
        return v

    @classmethod
    def _tpd_lookup(cls, frm, to, table=None):
        tab = cls.TPD if table is None else table
        if (frm, to) in tab:
            return float(tab[(frm, to)])

        def m(pat, s):
            return pat == "*" or pat == s or (any(c in pat for c in "*?[") and fnmatchcase(s, pat))
        for exact_from, exact_to in ((True, False), (False, True), (False, False)):
            for (a, b), ns in tab.items():
                if exact_from and a != frm:
                    continue
                if exact_to and b != to:
                    continue
                if m(a, frm) and m(b, to):
                    return float(ns)
        return DEFAULT_TPD if table is None else None

    @classmethod
    def setup_ns(cls, pin):
        s = cls.SETUP
        return float(s.get(pin, s.get("*", 0))) if isinstance(s, dict) else float(s)

    @classmethod
    def hold_ns(cls, pin):
        h = cls.HOLD
        return float(h.get(pin, h.get("*", 0))) if isinstance(h, dict) else float(h)

    @classmethod
    def sampled(cls, clkpin):
        if clkpin in cls.SAMPLED:
            return list(cls.SAMPLED[clkpin])
        return [nm for n, (nm, k) in sorted(cls.PINS.items()) if k == "in"]

    @classmethod
    def levels(cls):
        """{"VIH", "VIL", "VOH", "VOL"} in volts (None where not given)."""
        fam = LEVELS.get(cls.FAMILY, (None, None, None, None))
        own = (cls.VIH, cls.VIL, cls.VOH, cls.VOL)
        return {k: (o if o is not None else f) for k, o, f in zip(("VIH", "VIL", "VOH", "VOL"), own, fam)}

    @classmethod
    def info(cls):
        """Library card as plain JSON-compatible data."""
        d = {"type": cls.TYPE, "desc": cls.DESC, "family": cls.FAMILY,
             "category": "chip", "package": cls.package(), "width": cls.width(),
             "pins": [[n, nm, k] for n, (nm, k) in sorted(cls.PINS.items())],
             "edge": dict(cls.EDGE),
             "tpd": [[a, b, ns] for (a, b), ns in cls.TPD.items()],
             "tdis": [[a, b, ns] for (a, b), ns in (cls.TDIS or {}).items()],
             "setup": cls.SETUP if not isinstance(cls.SETUP, dict) else dict(cls.SETUP),
             "hold": cls.HOLD if not isinstance(cls.HOLD, dict) else dict(cls.HOLD),
             "datasheet": cls.DATASHEET, "levels": cls.levels()}
        if cls.ADDR_HOLD is not None:
            d["addr_hold"] = cls.ADDR_HOLD
        if cls.DRIVE:
            d["drive"] = dict(cls.DRIVE)
        if cls.TABLE:
            d["table"] = cls.TABLE
        return d


def register(cls):
    """Class decorator: add a chip class to REGISTRY under cls.TYPE."""
    t = cls.TYPE
    if not isinstance(t, str) or t in ("", "?"):
        raise ValueError(f"{cls.__name__}: TYPE must be a part number")
    names = [nm for nm, k in cls.PINS.values()]
    for pin in cls.EDGE:
        if pin not in names:
            raise ValueError(f"{t}: EDGE pin {pin} is not in PINS")
    if t in REGISTRY and REGISTRY[t] is not cls:
        DUPLICATES.append((t, REGISTRY[t].__module__, cls.__module__))
        return cls
    REGISTRY[t] = cls
    return cls


def variant(base, type_name, family, tpd=None, setup=None, hold=None, datasheet=None, desc=None,
            tdis=None):
    """Register a same-logic variant of a chip (e.g. 74HCT173 from 74HC173)."""
    attrs = {"TYPE": type_name, "FAMILY": family, "__module__": base.__module__}
    if tpd is not None:
        attrs["TPD"] = tpd
    if tdis is not None:
        attrs["TDIS"] = tdis
    if setup is not None:
        attrs["SETUP"] = setup
    if hold is not None:
        attrs["HOLD"] = hold
    if datasheet is not None:
        attrs["DATASHEET"] = datasheet
    if desc is not None:
        attrs["DESC"] = desc
    cls = type(base.__name__ + "_" + type_name.replace("-", "_"), (base,), attrs)
    return register(cls)


def get(type_name):
    try:
        return REGISTRY[type_name]
    except KeyError:
        raise KeyError(f"unknown chip type {type_name!r}") from None


def types():
    return sorted(REGISTRY)
