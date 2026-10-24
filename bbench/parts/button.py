"""Tactile push button, 4 legs: pins 1 and 2 are joined inside, as are 3 and 4.
Pressed joins the two pairs. It springs back: the simulator's press() releases it."""
from .base import Part, part


@part
class Button(Part):
    TYPE, DESC, CATEGORY, ALIASES = "BUTTON", "Push button (momentary)", "switch", ("BTN",)
    PINS = {1: ("1A", "pas"), 2: ("1B", "pas"), 3: ("2A", "pas"), 4: ("2B", "pas")}
    FOOTPRINT = {"kind": "button"}
    INTERNAL = ((1, 2), (3, 4))

    def __init__(self, ref="BTN?", **props):
        super().__init__(ref, **props)
        self.state = False

    def links(self):
        if self.state:
            return [(1, 3, "strong", 0.0, self.ref), (1, 2, "strong", 0.0, self.ref),
                    (3, 4, "strong", 0.0, self.ref)]
        return [(1, 2, "strong", 0.0, self.ref), (3, 4, "strong", 0.0, self.ref)]

    def set(self, value, section=None):
        self.state = bool(value)
