"""Logic gates (74-series DIP14).

TPD figures: worst case at VCC = 4.5 V, 25 degC, CL = 50 pF, from the TI datasheets
linked in DATASHEET.
"""
from .base import Chip, pins, bit, register, variant

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"


def _quad(fn):
    def ev(self, g):
        o = {}
        for i in "1234":
            o[i + "Y"] = fn(bit(g(i + "A")), bit(g(i + "B")))
        return o
    return ev


GATE14 = pins("1:1A:in 2:1B:in 3:1Y:out 4:2A:in 5:2B:in 6:2Y:out 7:GND:gnd "
              "8:3Y:out 9:3A:in 10:3B:in 11:4Y:out 12:4A:in 13:4B:in 14:VCC:vcc")


def _table2(fn):
    return {"inputs": ["A", "B"], "outputs": ["Y"],
            "rows": [[a, b, fn(a, b)] for a in (0, 1) for b in (0, 1)]}


# ---------------------------------------------------------------- PC-2 chips (engine)
@register
class HC00(Chip):
    TYPE, DESC, FAMILY, PINS = "74HC00", "Quad 2-input NAND", "HC", GATE14
    TPD = {("*", "*"): 20}
    DATASHEET = TI.format("sn74hc00")
    TABLE = _table2(lambda a, b: 1 - (a & b))
    eval = _quad(lambda a, b: 1 - (a & b))


@register
class HC08(Chip):
    TYPE, DESC, FAMILY, PINS = "74HC08", "Quad 2-input AND", "HC", GATE14
    TPD = {("*", "*"): 20}
    DATASHEET = TI.format("sn74hc08")
    TABLE = _table2(lambda a, b: a & b)
    eval = _quad(lambda a, b: a & b)


@register
class HC32(Chip):
    TYPE, DESC, FAMILY, PINS = "74HC32", "Quad 2-input OR", "HC", GATE14
    TPD = {("*", "*"): 20}
    DATASHEET = TI.format("sn74hc32")
    TABLE = _table2(lambda a, b: a | b)
    eval = _quad(lambda a, b: a | b)


@register
class HC86(Chip):
    TYPE, DESC, FAMILY, PINS = "74HC86", "Quad 2-input XOR", "HC", GATE14
    TPD = {("*", "*"): 23}
    DATASHEET = TI.format("sn74hc86")
    TABLE = _table2(lambda a, b: a ^ b)
    eval = _quad(lambda a, b: a ^ b)


@register
class HC02(Chip):
    TYPE, DESC, FAMILY = "74HC02", "Quad 2-input NOR", "HC"
    PINS = pins("1:1Y:out 2:1A:in 3:1B:in 4:2Y:out 5:2A:in 6:2B:in 7:GND:gnd "
                "8:3A:in 9:3B:in 10:3Y:out 11:4A:in 12:4B:in 13:4Y:out 14:VCC:vcc")
    TPD = {("*", "*"): 20}
    DATASHEET = TI.format("sn74hc02")
    TABLE = _table2(lambda a, b: 1 - (a | b))
    eval = _quad(lambda a, b: 1 - (a | b))


@register
class HC04(Chip):
    TYPE, DESC, FAMILY = "74HC04", "Hex inverter", "HC"
    PINS = pins("1:1A:in 2:1Y:out 3:2A:in 4:2Y:out 5:3A:in 6:3Y:out 7:GND:gnd "
                "8:4Y:out 9:4A:in 10:5Y:out 11:5A:in 12:6Y:out 13:6A:in 14:VCC:vcc")
    TPD = {("*", "*"): 20}
    DATASHEET = TI.format("sn74hc04")
    TABLE = {"inputs": ["A"], "outputs": ["Y"], "rows": [[0, 1], [1, 0]]}

    def eval(self, g):
        return {f"{i}Y": 1 - bit(g(f"{i}A")) for i in "123456"}


# HCT versions: same logic, TTL input levels, slightly slower.
# tpd: "TA = 25 degC MAX" column of each TI sheet at VCC = 4.5 V, CL = 50 pF (checked Oct 2026):
# SN74HCT00 SCLS062F 20 ns; SN74HCT02 SCLS065G 20 ns; SN74HCT04 SCLS042F 20 ns;
# SN74HCT08 SCLS063G 24 ns; SN74HCT32 SCLS064G 24 ns; CD74HCT86 SCHS410A 32 ns (25 degC MAX).
HCT00 = variant(HC00, "74HCT00", "HCT", tpd={("*", "*"): 20}, datasheet=TI.format("sn74hct00"))
HCT02 = variant(HC02, "74HCT02", "HCT", tpd={("*", "*"): 20}, datasheet=TI.format("sn74hct02"))
HCT04 = variant(HC04, "74HCT04", "HCT", tpd={("*", "*"): 20}, datasheet=TI.format("sn74hct04"))
HCT08 = variant(HC08, "74HCT08", "HCT", tpd={("*", "*"): 24}, datasheet=TI.format("sn74hct08"))
HCT32 = variant(HC32, "74HCT32", "HCT", tpd={("*", "*"): 24}, datasheet=TI.format("sn74hct32"))
HCT86 = variant(HC86, "74HCT86", "HCT", tpd={("*", "*"): 32}, datasheet=TI.format("cd74hct86"))
