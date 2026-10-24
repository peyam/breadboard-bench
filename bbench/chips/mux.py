"""Multiplexers (74-series). TPD: worst case at 4.5 V, 25 degC (TI datasheets)."""
from .base import Chip, pins, bit, register, variant

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"


# ---------------------------------------------------------------- PC-2 chips (engine)
@register
class HC157(Chip):
    TYPE, DESC, FAMILY = "74HC157", "Quad 2-to-1 multiplexer", "HC"
    PINS = pins("1:S:in 2:1A:in 3:1B:in 4:1Y:out 5:2A:in 6:2B:in 7:2Y:out 8:GND:gnd "
                "9:3Y:out 10:3B:in 11:3A:in 12:4Y:out 13:4B:in 14:4A:in 15:G:in 16:VCC:vcc")
    TPD = {("S", "*"): 30, ("G", "*"): 27, ("*", "*"): 25}
    DATASHEET = TI.format("sn74hc157")

    def eval(self, g):
        if bit(g("G")):
            return {f"{i}Y": 0 for i in "1234"}
        s = bit(g("S"))
        return {f"{i}Y": bit(g(f"{i}B" if s else f"{i}A")) for i in "1234"}


# CD74HCT157 (SCHS153C), VCC = 4.5 V, 25 degC, MAX column (CL = 50 pF): data -> Y 25,
# S -> Y 29, E (G) -> Y 27. The kit buys CD74HCT157E.
HCT157 = variant(HC157, "74HCT157", "HCT", tpd={("S", "*"): 29, ("G", "*"): 27, ("*", "*"): 25},
                 datasheet=TI.format("cd74hct157"))
