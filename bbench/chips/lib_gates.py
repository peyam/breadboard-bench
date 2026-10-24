"""Logic gates, extended library: 74x10, 11, 14, 20, 21, 27, 30, 132 (DIP14).

Pin-outs, function tables and tpd (max, VCC = 4.5 V, 25 degC, CL = 50 pF) are from
the TI datasheets in DATASHEET (SN74HCxx / CD74HCxx / SN74HCTxx / CD74HCTxx).
The Schmitt-trigger types (14, 132) are modelled at logic level: their hysteresis
matters only for slow analogue edges, which the simulators do not model.
"""
from .base import Chip, pins, bit, register, variant
from ._lib import TI


def _table(names, fn):
    """Function table for the library card: every input combination of one gate."""
    n = len(names)
    rows = []
    for v in range(2 ** n):
        ins = [(v >> (n - 1 - i)) & 1 for i in range(n)]
        rows.append(ins + [fn(ins)])
    return {"inputs": list(names), "outputs": ["Y"], "rows": rows}


def _nand(xs):
    return 0 if all(xs) else 1


def _and(xs):
    return 1 if all(xs) else 0


def _nor(xs):
    return 0 if any(xs) else 1


def _gates(groups, fn):
    """groups: {output pin: [input pins]} -> eval method."""
    def ev(self, g):
        return {y: fn([bit(g(a)) for a in ins]) for y, ins in groups.items()}
    return ev


# ---------------------------------------------------------------- triple 3-input
TRIPLE3 = pins("1:1A:in 2:1B:in 3:2A:in 4:2B:in 5:2C:in 6:2Y:out 7:GND:gnd "
               "8:3Y:out 9:3A:in 10:3B:in 11:3C:in 12:1Y:out 13:1C:in 14:VCC:vcc")
G3 = {f"{i}Y": [f"{i}A", f"{i}B", f"{i}C"] for i in "123"}


@register
class HCT10(Chip):
    TYPE, DESC, FAMILY = "74HCT10", "Triple 3-input NAND", "HCT"
    PINS = TRIPLE3
    TPD = {("*", "*"): 24}
    DATASHEET = TI.format("cd74hct10")
    TABLE = _table("ABC", _nand)
    eval = _gates(G3, _nand)


@register
class HCT11(Chip):
    TYPE, DESC, FAMILY = "74HCT11", "Triple 3-input AND", "HCT"
    PINS = TRIPLE3
    TPD = {("*", "*"): 28}
    DATASHEET = TI.format("cd74hct11")
    TABLE = _table("ABC", _and)
    eval = _gates(G3, _and)


@register
class HCT27(Chip):
    TYPE, DESC, FAMILY = "74HCT27", "Triple 3-input NOR", "HCT"
    PINS = TRIPLE3
    TPD = {("*", "*"): 23}
    DATASHEET = TI.format("cd74hct27")
    TABLE = _table("ABC", _nor)
    eval = _gates(G3, _nor)


HC10 = variant(HCT10, "74HC10", "HC", tpd={("*", "*"): 24}, datasheet=TI.format("sn74hc10"))
HC11 = variant(HCT11, "74HC11", "HC", tpd={("*", "*"): 25}, datasheet=TI.format("sn74hc11"))
HC27 = variant(HCT27, "74HC27", "HC", tpd={("*", "*"): 23}, datasheet=TI.format("sn74hc27"))


# ---------------------------------------------------------------- dual 4-input
DUAL4 = pins("1:1A:in 2:1B:in 3:NC:nc 4:1C:in 5:1D:in 6:1Y:out 7:GND:gnd "
             "8:2Y:out 9:2A:in 10:2B:in 11:NC2:nc 12:2C:in 13:2D:in 14:VCC:vcc")
G4 = {f"{i}Y": [f"{i}A", f"{i}B", f"{i}C", f"{i}D"] for i in "12"}


@register
class HCT20(Chip):
    TYPE, DESC, FAMILY = "74HCT20", "Dual 4-input NAND", "HCT"
    PINS = DUAL4
    TPD = {("*", "*"): 28}
    DATASHEET = TI.format("cd74hct20")
    TABLE = _table("ABCD", _nand)
    eval = _gates(G4, _nand)


@register
class HCT21(Chip):
    TYPE, DESC, FAMILY = "74HCT21", "Dual 4-input AND", "HCT"
    PINS = DUAL4
    TPD = {("*", "*"): 27}
    DATASHEET = TI.format("cd74hct21")
    TABLE = _table("ABCD", _and)
    eval = _gates(G4, _and)


HC20 = variant(HCT20, "74HC20", "HC", tpd={("*", "*"): 22}, datasheet=TI.format("sn74hc20"))
HC21 = variant(HCT21, "74HC21", "HC", tpd={("*", "*"): 28}, datasheet=TI.format("sn74hc21"))


# ---------------------------------------------------------------- 8-input NAND
@register
class HCT30(Chip):
    TYPE, DESC, FAMILY = "74HCT30", "8-input NAND", "HCT"
    PINS = pins("1:A:in 2:B:in 3:C:in 4:D:in 5:E:in 6:F:in 7:GND:gnd "
                "8:Y:out 9:NC:nc 10:NC2:nc 11:G:in 12:H:in 13:NC3:nc 14:VCC:vcc")
    TPD = {("*", "*"): 28}
    DATASHEET = TI.format("cd74hct30")
    TABLE = {"inputs": list("ABCDEFGH"), "outputs": ["Y"],
             "rows": [[1] * 8 + [0]] + [[0 if j == i else "X" for j in range(8)] + [1] for i in range(8)]}
    eval = _gates({"Y": list("ABCDEFGH")}, _nand)


HC30 = variant(HCT30, "74HC30", "HC", tpd={("*", "*"): 18}, datasheet=TI.format("cd74hc30"))


# ---------------------------------------------------------------- Schmitt-trigger types
@register
class HCT14(Chip):
    TYPE, DESC, FAMILY = "74HCT14", "Hex Schmitt-trigger inverter", "HCT"
    PINS = pins("1:1A:in 2:1Y:out 3:2A:in 4:2Y:out 5:3A:in 6:3Y:out 7:GND:gnd "
                "8:4Y:out 9:4A:in 10:5Y:out 11:5A:in 12:6Y:out 13:6A:in 14:VCC:vcc")
    TPD = {("*", "*"): 32}
    DATASHEET = TI.format("sn74hct14")
    TABLE = {"inputs": ["A"], "outputs": ["Y"], "rows": [[0, 1], [1, 0]]}

    def eval(self, g):
        return {f"{i}Y": 1 - bit(g(f"{i}A")) for i in "123456"}


@register
class HCT132(Chip):
    TYPE, DESC, FAMILY = "74HCT132", "Quad 2-input NAND, Schmitt-trigger inputs", "HCT"
    PINS = pins("1:1A:in 2:1B:in 3:1Y:out 4:2A:in 5:2B:in 6:2Y:out 7:GND:gnd "
                "8:3Y:out 9:3A:in 10:3B:in 11:4Y:out 12:4A:in 13:4B:in 14:VCC:vcc")
    TPD = {("*", "*"): 33}
    DATASHEET = TI.format("cd74hct132")
    TABLE = _table("AB", _nand)
    eval = _gates({f"{i}Y": [f"{i}A", f"{i}B"] for i in "1234"}, _nand)


HC14 = variant(HCT14, "74HC14", "HC", tpd={("*", "*"): 25}, datasheet=TI.format("sn74hc14"))
HC132 = variant(HCT132, "74HC132", "HC", tpd={("*", "*"): 31}, datasheet=TI.format("sn74hc132"))
