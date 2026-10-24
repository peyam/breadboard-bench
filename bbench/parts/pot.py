"""Potentiometer: pins 1 and 3 are the track ends, 2 the wiper. Prop position 0..1
(0 = wiper at pin 1)."""
from .base import Part, part


@part
class Pot(Part):
    TYPE, DESC, ALIASES = "POT", "Potentiometer", ("VR",)
    PINS = {1: ("1", "pas"), 2: ("W", "pas"), 3: ("3", "pas")}
    FOOTPRINT = {"kind": "sip", "pitch": 2}
    DEFAULTS = {"value": "10k", "position": 0.5}

    def __init__(self, ref="VR?", **props):
        super().__init__(ref, **props)
        self.state = float(self.props.get("position", 0.5))

    def links(self):
        r = self.ohms() or 0.0
        p = min(1.0, max(0.0, self.state))
        return [(1, 2, "weak", r * p, self.ref), (2, 3, "weak", r * (1 - p), self.ref)]

    def set(self, value, section=None):
        self.state = min(1.0, max(0.0, float(value)))

    def get(self):
        return self.state
