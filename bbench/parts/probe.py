"""Logic probe (an instrument): shows the value on its tip, 0, 1, "Z" or "X"."""
from .base import Part, part


@part
class Probe(Part):
    TYPE, DESC, CATEGORY = "PROBE", "Logic probe", "indicator"
    PINS = {1: ("TIP", "pas")}
    FOOTPRINT = {"kind": "virtual"}

    def show(self, value):
        return value(1)
