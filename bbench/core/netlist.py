"""The netlist: parts (chips and passives) with numbered pins on named nets.

Nets named VCC and GND are the rails (1 and 0), as are nets on a POWER part's pins.
The netlist is the source of truth; simulators and the breadboard checker read it.
"""
from .. import chips as _chips
from .. import parts as _parts
from ..chips.base import Chip

RAILS = {"VCC": 1, "GND": 0}


def lookup_type(type_name):
    """The class for a part type: a chip from the chip registry or a passive/I/O part."""
    if type_name in _chips.REGISTRY:
        return _chips.REGISTRY[type_name]
    if type_name in _parts.PARTS:
        return _parts.PARTS[type_name]
    raise KeyError(f"unknown part type {type_name!r}")


def is_active(model):
    return isinstance(model, Chip)


class NetlistError(ValueError):
    pass


class Netlist:
    def __init__(self):
        self.parts = {}          # id -> model (Chip or Part instance)
        self.types = {}          # id -> type name
        self.props = {}          # id -> project props
        self.nets = {}           # net -> [(id, pin number)]
        self.pinnet = {}         # id -> {pin number: net}
        self.problems = []       # static problems found while building

    # building ---------------------------------------------------------------
    def add(self, pid, type_name, props=None, model=None):
        if pid in self.parts:
            raise NetlistError(f"part id {pid} used twice")
        props = dict(props or {})
        if model is None:
            cls = lookup_type(type_name)
            model = cls(pid, **props)
        self.parts[pid] = model
        self.types[pid] = type_name
        self.props[pid] = props
        self.pinnet[pid] = {}
        return model

    def pin_number(self, pid, pin):
        model = self.parts[pid]
        if isinstance(pin, int):
            n = pin
        elif isinstance(pin, str) and pin.isdigit():
            n = int(pin)
        else:
            try:
                n = model.pin_number(pin)
            except KeyError:
                raise NetlistError(f"{pid} ({self.types[pid]}) has no pin {pin}") from None
        if n not in model.PINS:
            raise NetlistError(f"{pid} ({self.types[pid]}) has no pin {pin}")
        return n

    def connect(self, net, pid, pin):
        if pid not in self.parts:
            raise NetlistError(f"net {net}: unknown part {pid}")
        n = self.pin_number(pid, pin)
        old = self.pinnet[pid].get(n)
        if old is not None and old != net:
            raise NetlistError(f"{pid} pin {n} is on two nets: {old} and {net}")
        if old == net:
            return
        self.pinnet[pid][n] = net
        self.nets.setdefault(net, []).append((pid, n))

    @classmethod
    def from_project(cls, data, strict=False):
        """Build from a project dict (DESIGN section 3). Problems that make a part or a
        connection impossible are kept in .problems (or raised when strict)."""
        N = cls()
        for p in data.get("parts", []):
            try:
                N.add(p["id"], p["type"], p.get("props"))
            except (KeyError, NetlistError, ValueError, TypeError) as e:
                if strict:
                    raise
                N.problems.append({"severity": "error", "kind": "part", "message": str(e).strip("'\""),
                                   "where": {"part": p.get("id")}})
        for net in data.get("nets", []):
            name = net["name"]
            N.nets.setdefault(name, [])
            for pid, pin in net.get("pins", []):
                try:
                    N.connect(name, pid, pin)
                except NetlistError as e:
                    if strict:
                        raise
                    N.problems.append({"severity": "error", "kind": "net", "message": str(e),
                                       "where": {"net": name, "part": pid, "pin": str(pin)}})
        return N

    # queries ---------------------------------------------------------------
    def rails(self):
        r = dict(RAILS)
        for pid, model in self.parts.items():
            rail = getattr(model, "RAIL", None)
            if rail:
                for n, v in rail.items():
                    net = self.pinnet[pid].get(n)
                    if net is not None:
                        r[net] = v
        return r

    def net_of(self, pid, pin):
        return self.pinnet[pid].get(self.pin_number(pid, pin))
