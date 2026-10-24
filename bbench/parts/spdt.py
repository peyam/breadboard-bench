"""Changeover (SPDT) slide switch and 3-pin jumper: pin 2 is common, pin 1 and pin 3
are the two positions. Prop positions names them (default ["A", "B"]); pos is the
starting position (index or name, None = neither)."""
from .base import Part, part


class Changeover(Part):
    CATEGORY = "switch"
    PINS = {1: ("A", "pas"), 2: ("COM", "pas"), 3: ("B", "pas")}
    FOOTPRINT = {"kind": "sip", "pitch": 1}
    DEFAULTS = {"positions": ["A", "B"], "pos": 0}

    def __init__(self, ref="S?", **props):
        super().__init__(ref, **props)
        self.state = None
        self.set(self.props.get("pos", 0))

    def positions(self):
        return list(self.props.get("positions") or ["A", "B"])

    def set(self, value, section=None):
        if value is None:
            self.state = None
            return
        if isinstance(value, str):
            names = [p.upper() for p in self.positions()]
            if value.upper() not in names:
                raise ValueError(f"{self.ref}: no position {value!r} (have {self.positions()})")
            self.state = names.index(value.upper())
        else:
            self.state = 1 if int(value) else 0

    def get(self):
        return None if self.state is None else self.positions()[self.state]

    def links(self):
        if self.state is None:
            return []
        return [(2, 1 if self.state == 0 else 3, "strong", 0.0, self.ref)]


@part
class SPDT(Changeover):
    TYPE, DESC = "SPDT", "Changeover slide switch (SPDT)"


@part
class Jumper3(Changeover):
    TYPE, DESC, ALIASES = "JUMPER3", "3-pin header with jumper", ("JP3",)
