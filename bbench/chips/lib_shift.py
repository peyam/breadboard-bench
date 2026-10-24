"""Shift registers, extended library: 74x164 (serial in, parallel out) and
74x165 (parallel in, serial out).

Sources: Nexperia 74HC_HCT164 and 74HC_HCT165 datasheets (pin-out, function table,
timing at 4.5 V, 25 degC). State is a list [Q0 .. Q7].
"""
from .base import Chip, pins, bit, register, variant
from ._lib import NXP


@register
class HCT164(Chip):
    TYPE, FAMILY = "74HCT164", "HCT"
    DESC = "8-bit serial-in, parallel-out shift register, gated serial inputs, active-low reset"
    PINS = pins("1:DSA:in 2:DSB:in 3:Q0:out 4:Q1:out 5:Q2:out 6:Q3:out 7:GND:gnd "
                "8:CP:clk 9:MR:in 10:Q4:out 11:Q5:out 12:Q6:out 13:Q7:out 14:VCC:vcc")
    EDGE = {"CP": "rise"}
    TPD = {("MR", "*"): 38, ("*", "*"): 36}
    SETUP = 12
    HOLD = 4
    SAMPLED = {"CP": ["DSA", "DSB"]}
    DATASHEET = NXP.format("74HC_HCT164")

    def reset_state(self):
        return [0] * 8

    def asyncupd(self, g):
        if not bit(g("MR")) and any(self.state):
            self.state = [0] * 8
            return True
        return False

    def edge(self, g, clk):
        if not bit(g("MR")):
            return [0] * 8
        return [bit(g("DSA")) & bit(g("DSB"))] + self.state[:7]

    def eval(self, g):
        return {f"Q{i}": self.state[i] for i in range(8)}


HC164 = variant(HCT164, "74HC164", "HC", tpd={("MR", "*"): 28, ("*", "*"): 34},
                setup=12, hold=4, datasheet=NXP.format("74HC_HCT164"))


@register
class HCT165(Chip):
    TYPE, FAMILY = "74HCT165", "HCT"
    DESC = ("8-bit parallel-in, serial-out shift register, active-low asynchronous load PL, "
            "active-low clock enable CE (the clock is CP OR CE)")
    PINS = pins("1:PL:in 2:CP:clk 3:D4:in 4:D5:in 5:D6:in 6:D7:in 7:Q7N:out 8:GND:gnd "
                "9:Q7:out 10:DS:in 11:D0:in 12:D1:in 13:D2:in 14:D3:in 15:CE:clk 16:VCC:vcc")
    EDGE = {"CP": "rise", "CE": "rise"}
    TPD = {("PL", "*"): 40, ("D7", "*"): 28, ("*", "*"): 34}
    SETUP = 20
    HOLD = {"DS": 7, "*": 0}
    SAMPLED = {"CP": ["DS"], "CE": ["DS"]}
    DATASHEET = NXP.format("74HC_HCT165")

    def reset_state(self):
        return [0] * 8

    def asyncupd(self, g):
        if not bit(g("PL")):
            d = [bit(g(f"D{i}")) for i in range(8)]
            if d != self.state:
                self.state = d
                return True
        return False

    def edge(self, g, clk):
        if not bit(g("PL")):
            return [bit(g(f"D{i}")) for i in range(8)]
        other = "CE" if clk == "CP" else "CP"
        if bit(g(other)):                     # the gated clock is CP OR CE
            return self.state
        return [bit(g("DS"))] + self.state[:7]

    def eval(self, g):
        q7 = self.state[7]
        return {"Q7": q7, "Q7N": 1 - q7}


HC165 = variant(HCT165, "74HC165", "HC", tpd={("PL", "*"): 33, ("D7", "*"): 24, ("*", "*"): 33},
                setup=16, hold=5, datasheet=NXP.format("74HC_HCT165"))
