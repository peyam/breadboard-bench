"""Bipolar transistors as switches (TO-92, pins 1 = E, 2 = B, 3 = C, as 2N3904/2N3906).

PNP: conducts when the base reads 0; the collector then takes the emitter's value
(a high-side digit driver). NPN: conducts when the base reads 1. Off: the collector
floats ("Z")."""
from ..chips.base import Chip, pins, bit, soft, Z
from .base import part


class Transistor(Chip):
    FAMILY = "part"
    CATEGORY = "active"
    PINS = pins("1:E:ana 2:B:in 3:C:tri")
    FOOTPRINT = {"kind": "sip", "pitch": 1}
    TPD = {("*", "*"): 50}
    ON = 0

    def eval(self, g):
        b = bit(g("B"))
        if b == self.ON:
            return {"C": soft(g, "E")}
        return {"C": Z}

    @classmethod
    def info(cls):
        d = super().info()
        d["category"] = cls.CATEGORY
        d["footprint"] = dict(cls.FOOTPRINT)
        return d


@part
class PNP(Transistor):
    TYPE, DESC, ON = "PNP", "PNP transistor as a switch (2N3906)", 0
    DATASHEET = "https://www.onsemi.com/download/data-sheet/pdf/2n3906-d.pdf"


@part
class NPN(Transistor):
    TYPE, DESC, ON = "NPN", "NPN transistor as a switch (2N3904)", 1
    DATASHEET = "https://www.onsemi.com/download/data-sheet/pdf/2n3904-d.pdf"
