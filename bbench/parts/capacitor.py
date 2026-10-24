"""Capacitor (no logic effect; its value sets 555 timing). Pin 1 is + when polarised."""
from .base import Part, part, two


@part
class Capacitor(Part):
    TYPE, DESC, ALIASES = "C", "Capacitor", ("CAP",)
    PINS = two()
    DEFAULTS = {"value": "100nF"}

    def farads(self):
        return self.ohms()
