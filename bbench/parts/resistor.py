"""Resistor: a weak link between its two pins (a pull-up/pull-down when one end is on a rail)."""
from .base import Part, part, two


@part
class Resistor(Part):
    TYPE, DESC, ALIASES = "R", "Resistor", ("RES",)
    PINS = two()
    DEFAULTS = {"value": "10k"}

    def links(self):
        return [(1, 2, "weak", self.ohms(), self.ref)]
