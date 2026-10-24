"""Tri-state buffers and line drivers, extended library:
74x125, 126 (quad), 240 (octal inverting), 241, 244, 541 (octal).

Sources: TI SN74HC125/SN74HCT125/SN74HC126/CD74HCT126; Nexperia 74HC_HCT240/241/244/541
(pin-out, function table, timing at 4.5 V, 25 degC). Data passes through with soft():
an unknown input gives an unknown output, as on a real buffer.
"""
from .base import Chip, pins, bit, soft, register, variant, Z
from ._lib import TI, NXP

QUAD = pins("1:1OE:in 2:1A:in 3:1Y:tri 4:2OE:in 5:2A:in 6:2Y:tri 7:GND:gnd "
            "8:3Y:tri 9:3A:in 10:3OE:in 11:4Y:tri 12:4A:in 13:4OE:in 14:VCC:vcc")


@register
class HCT125(Chip):
    TYPE, FAMILY = "74HCT125", "HCT"
    DESC = "Quad tri-state buffer, active-low enables"
    PINS = QUAD
    TPD = {("?OE", "*"): 28, ("*", "*"): 20}
    DATASHEET = TI.format("sn74hct125")
    ACTIVE = 0          # OE level that enables the output
    TABLE = {"inputs": ["OE", "A"], "outputs": ["Y"], "rows": [[0, 1, 1], [0, 0, 0], [1, "X", "Z"]]}

    def eval(self, g):
        o = {}
        for i in "1234":
            o[i + "Y"] = soft(g, i + "A") if bit(g(i + "OE")) == self.ACTIVE else Z
        return o


@register
class HCT126(HCT125):
    TYPE, FAMILY = "74HCT126", "HCT"
    DESC = "Quad tri-state buffer, active-high enables"
    TPD = {("?OE", "*"): 28, ("*", "*"): 24}
    DATASHEET = TI.format("cd74hct126")
    ACTIVE = 1
    TABLE = {"inputs": ["OE", "A"], "outputs": ["Y"], "rows": [[0, "X", "Z"], [1, 0, 0], [1, 1, 1]]}


HC125 = variant(HCT125, "74HC125", "HC", tpd={("?OE", "*"): 24, ("*", "*"): 24}, datasheet=TI.format("sn74hc125"))
HC126 = variant(HCT126, "74HC126", "HC", tpd={("?OE", "*"): 24, ("*", "*"): 24}, datasheet=TI.format("sn74hc126"))


# ---------------------------------------------------------------- octal, two groups of four (240/241/244)
OCT2 = pins("1:1OE:in 2:1A0:in 3:2Y0:tri 4:1A1:in 5:2Y1:tri 6:1A2:in 7:2Y2:tri 8:1A3:in 9:2Y3:tri 10:GND:gnd "
            "11:2A3:in 12:1Y3:tri 13:2A2:in 14:1Y2:tri 15:2A1:in 16:1Y1:tri 17:2A0:in 18:1Y0:tri 19:2OE:in 20:VCC:vcc")


def _pass(g, name):
    return soft(g, name)


def _invert(g, name):
    v = soft(g, name)
    return 1 - v if v in (0, 1) else v


class _Octal2(Chip):
    PINS = OCT2
    ACTIVE = (0, 0)       # enabling level of 1OE and 2OE
    INVERT = False

    def eval(self, g):
        f = _invert if self.INVERT else _pass
        o = {}
        for k, grp in enumerate("12"):
            on = bit(g(grp + "OE")) == self.ACTIVE[k]
            for n in range(4):
                o[f"{grp}Y{n}"] = f(g, f"{grp}A{n}") if on else Z
        return o


@register
class HCT240(_Octal2):
    TYPE, FAMILY = "74HCT240", "HCT"
    DESC = "Octal inverting buffer/line driver, tri-state, active-low enables"
    INVERT = True
    TPD = {("?OE", "*"): 30, ("*", "*"): 20}
    DATASHEET = NXP.format("74HC_HCT240")


@register
class HCT241(_Octal2):
    TYPE, FAMILY = "74HCT241", "HCT"
    DESC = "Octal buffer/line driver, tri-state, 1OE active low, 2OE active high"
    ACTIVE = (0, 1)
    TPD = {("?OE", "*"): 30, ("*", "*"): 22}
    DATASHEET = NXP.format("74HC_HCT241")


@register
class HCT244(_Octal2):
    TYPE, FAMILY = "74HCT244", "HCT"
    DESC = "Octal buffer/line driver, tri-state, active-low enables"
    TPD = {("?OE", "*"): 30, ("*", "*"): 22}
    DATASHEET = NXP.format("74HC_HCT244")


HC240 = variant(HCT240, "74HC240", "HC", tpd={("?OE", "*"): 30, ("*", "*"): 20}, datasheet=NXP.format("74HC_HCT240"))
HC241 = variant(HCT241, "74HC241", "HC", tpd={("?OE", "*"): 30, ("*", "*"): 20}, datasheet=NXP.format("74HC_HCT241"))
HC244 = variant(HCT244, "74HC244", "HC", tpd={("?OE", "*"): 30, ("*", "*"): 22}, datasheet=NXP.format("74HC_HCT244"))


# ---------------------------------------------------------------- 541: octal, flow-through
@register
class HCT541(Chip):
    TYPE, FAMILY = "74HCT541", "HCT"
    DESC = "Octal buffer/line driver, tri-state, two active-low enables, flow-through pin-out"
    PINS = pins("1:OE1:in 2:A0:in 3:A1:in 4:A2:in 5:A3:in 6:A4:in 7:A5:in 8:A6:in 9:A7:in 10:GND:gnd "
                "11:Y7:tri 12:Y6:tri 13:Y5:tri 14:Y4:tri 15:Y3:tri 16:Y2:tri 17:Y1:tri 18:Y0:tri 19:OE2:in 20:VCC:vcc")
    TPD = {("OE?", "*"): 35, ("*", "*"): 28}
    DATASHEET = NXP.format("74HC_HCT541")

    def eval(self, g):
        on = not bit(g("OE1")) and not bit(g("OE2"))
        return {f"Y{i}": (soft(g, f"A{i}") if on else Z) for i in range(8)}


HC541 = variant(HCT541, "74HC541", "HC", tpd={("OE?", "*"): 32, ("*", "*"): 23}, datasheet=NXP.format("74HC_HCT541"))
