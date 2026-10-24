"""Multiplexers, extended library: 74x151 (8-to-1), 74x153 (dual 4-to-1).

Sources: TI SN74HC151, CD74HCT151, SN74HC153 and Nexperia 74HC_HCT153 datasheets
(pin-out, function table, timing at 4.5 V, 25 degC). Pin names follow TI.
"""
from .base import Chip, pins, bit, soft, register, variant
from ._lib import TI, NXP


def _inv(v):
    return 1 - v if v in (0, 1) else v


@register
class HCT151(Chip):
    TYPE, FAMILY = "74HCT151", "HCT"
    DESC = "8-to-1 multiplexer with true (Y) and inverted (W) outputs, active-low strobe G"
    PINS = pins("1:D3:in 2:D2:in 3:D1:in 4:D0:in 5:Y:out 6:W:out 7:G:in 8:GND:gnd "
                "9:C:in 10:B:in 11:A:in 12:D7:in 13:D6:in 14:D5:in 15:D4:in 16:VCC:vcc")
    TPD = {("D?", "Y"): 38, ("D?", "W"): 36, ("G", "Y"): 29, ("G", "W"): 36,
           ("*", "Y"): 41, ("*", "W"): 43}
    DATASHEET = TI.format("cd74hct151")

    def eval(self, g):
        if bit(g("G")):
            return {"Y": 0, "W": 1}
        n = bit(g("A")) | bit(g("B")) << 1 | bit(g("C")) << 2
        y = soft(g, f"D{n}")
        return {"Y": y, "W": _inv(y)}


HC151 = variant(HCT151, "74HC151", "HC", tpd={("D?", "*"): 39, ("G", "*"): 25, ("*", "*"): 50},
                datasheet=TI.format("sn74hc151"))


@register
class HCT153(Chip):
    TYPE, FAMILY = "74HCT153", "HCT"
    DESC = "Dual 4-to-1 multiplexer, common selects A/B, active-low strobes 1G/2G"
    PINS = pins("1:1G:in 2:B:in 3:1C3:in 4:1C2:in 5:1C1:in 6:1C0:in 7:1Y:out 8:GND:gnd "
                "9:2Y:out 10:2C0:in 11:2C1:in 12:2C2:in 13:2C3:in 14:A:in 15:2G:in 16:VCC:vcc")
    TPD = {("?G", "*"): 27, ("?C?", "*"): 34, ("*", "*"): 34}
    DATASHEET = NXP.format("74HC_HCT153")

    def eval(self, g):
        o = {}
        sel = None
        for h in "12":
            if bit(g(h + "G")):
                o[h + "Y"] = 0
                continue
            if sel is None:
                sel = bit(g("A")) | bit(g("B")) << 1
            o[h + "Y"] = soft(g, f"{h}C{sel}")
        return o


HC153 = variant(HCT153, "74HC153", "HC", tpd={("?G", "*"): 19, ("?C?", "*"): 28, ("*", "*"): 30},
                datasheet=TI.format("sn74hc153"))
