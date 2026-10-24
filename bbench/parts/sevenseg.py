"""7-segment digit, 10-pin 0.56 in package (pins 3 and 8 are both the common pin).

Segment bits: bit k = a, b, c, d, e, f, g, dp for k = 0..7. Common anode: a segment
lights when the common pin reads 1 and its segment pin reads 0; common cathode: common
0, segment 1."""
from .base import Part, part

SEGS = ["a", "b", "c", "d", "e", "f", "g", "dp"]
PIN_OF = {"e": 1, "d": 2, "c": 4, "dp": 5, "b": 6, "a": 7, "f": 9, "g": 10}


class Digit(Part):
    CATEGORY = "indicator"
    FOOTPRINT = {"kind": "dip", "width": 6}
    INTERNAL = ((3, 8),)
    ANODE = True

    def show(self, value):
        com = value(3)
        if com not in (0, 1):
            com = value(8)
        bits = 0
        on_com, on_seg = (1, 0) if self.ANODE else (0, 1)
        if com == on_com:
            for k, s in enumerate(SEGS):
                if value(PIN_OF[s]) == on_seg:
                    bits |= 1 << k
        return bits


def _pins(c):
    p = {n: (s, "pas") for s, n in PIN_OF.items()}
    p[3] = (c, "pas")
    p[8] = (c + "2", "pas")
    return dict(sorted(p.items()))


@part
class DigitCA(Digit):
    TYPE, DESC, ALIASES = "7SEG-CA", "7-segment digit, common anode", ("DIGIT-CA",)
    PINS = _pins("CA")
    ANODE = True


@part
class DigitCC(Digit):
    TYPE, DESC, ALIASES = "7SEG-CC", "7-segment digit, common cathode", ("DIGIT-CC",)
    PINS = _pins("CC")
    ANODE = False
