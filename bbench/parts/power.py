"""5 V power supply (an instrument): pin 1 is +5 V, pin 2 is GND. Nets on its pins
are rails, like the nets named VCC and GND."""
from .base import Part, part, two


@part
class Power(Part):
    TYPE, DESC, CATEGORY = "POWER", "5 V supply", "source"
    PINS = two("+5V", "GND")
    FOOTPRINT = {"kind": "virtual"}
    RAIL = {1: 1, 2: 0}
