"""LED: lit when its anode (pin 1) reads 1 and its cathode (pin 2) reads 0."""
from .base import Part, part, two


@part
class LED(Part):
    TYPE, DESC, CATEGORY = "LED", "Light-emitting diode", "indicator"
    PINS = two("A", "K")
    DEFAULTS = {"colour": "red"}

    def show(self, value):
        return value(1) == 1 and value(2) == 0
