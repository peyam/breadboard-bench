"""Decoders (74-series). TPD: worst case at 4.5 V, 25 degC (TI datasheets)."""
from .base import Chip, pins, bit, register, variant

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"


# ---------------------------------------------------------------- PC-2 chips (engine)
@register
class HC138(Chip):
    TYPE, DESC, FAMILY = "74HC138", "3-to-8 line decoder, active-low outputs", "HC"
    PINS = pins("1:A:in 2:B:in 3:C:in 4:G2A:in 5:G2B:in 6:G1:in 7:Y7:out 8:GND:gnd "
                "9:Y6:out 10:Y5:out 11:Y4:out 12:Y3:out 13:Y2:out 14:Y1:out 15:Y0:out 16:VCC:vcc")
    TPD = {("A", "*"): 30, ("B", "*"): 30, ("C", "*"): 30, ("G1", "*"): 30, ("*", "*"): 30}
    DATASHEET = TI.format("sn74hc138")

    def eval(self, g):
        en = bit(g("G1")) and not bit(g("G2A")) and not bit(g("G2B"))
        n = bit(g("A")) | bit(g("B")) << 1 | bit(g("C")) << 2
        return {f"Y{i}": 0 if (en and i == n) else 1 for i in range(8)}


@register
class HC139(Chip):
    TYPE, DESC, FAMILY = "74HC139", "Dual 2-to-4 line decoder, active-low outputs", "HC"
    PINS = pins("1:1G:in 2:1A:in 3:1B:in 4:1Y0:out 5:1Y1:out 6:1Y2:out 7:1Y3:out 8:GND:gnd "
                "9:2Y3:out 10:2Y2:out 11:2Y1:out 12:2Y0:out 13:2B:in 14:2A:in 15:2G:in 16:VCC:vcc")
    TPD = {("?G", "*"): 25, ("*", "*"): 30}
    DATASHEET = TI.format("sn74hc139")

    def eval(self, g):
        o = {}
        for h in "12":
            en = not bit(g(h + "G"))
            n = bit(g(h + "A")) | bit(g(h + "B")) << 1
            for i in range(4):
                o[f"{h}Y{i}"] = 0 if (en and i == n) else 1
        return o


# TI sheets at VCC = 4.5 V, 25 degC, MAX column (CL = 50 pF):
# CD74HCT138 (SCHS147J): address -> Y 35, G1 (active-high enable) -> Y 35; the sheet gives no
# separate 4.5 V figure for the active-low enables of the '138, so 35 is used for every path.
# CD74HCT139 (SCHS148D): address -> Y 34, enable -> Y 34.
HCT138 = variant(HC138, "74HCT138", "HCT", tpd={("*", "*"): 35}, datasheet=TI.format("cd74hct138"))
HCT139 = variant(HC139, "74HCT139", "HCT", tpd={("*", "*"): 34}, datasheet=TI.format("cd74hct139"))
