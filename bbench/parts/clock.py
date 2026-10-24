"""Clock source (an instrument, not on the breadboard): pin 1 is the output.
Props period_ns (default 1 000 000 = 1 kHz) and duty (default 0.5)."""
from ..chips.base import Chip, pins
from .base import part


@part
class ClockSource(Chip):
    TYPE, DESC, FAMILY = "CLOCK", "Clock source (square wave)", "part"
    CATEGORY = "active"
    PINS = pins("1:OUT:out 2:GND:gnd")
    FOOTPRINT = {"kind": "virtual"}
    TPD = {("*", "*"): 1}

    def reset_state(self):
        return 0

    def eval(self, g):
        return {"OUT": self.state}

    def period_ns(self):
        return float(self.props.get("period_ns", 1_000_000))

    @classmethod
    def info(cls):
        d = super().info()
        d["category"] = cls.CATEGORY
        d["footprint"] = dict(cls.FOOTPRINT)
        return d
