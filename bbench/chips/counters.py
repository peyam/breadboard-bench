"""Counters (74-series). TPD/SETUP/HOLD: worst case at 4.5 V, 25 degC (TI datasheets)."""
from .base import Chip, pins, bit, register, variant

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"


# ---------------------------------------------------------------- PC-2 chips (engine)
@register
class HC161(Chip):
    TYPE, DESC, FAMILY = "74HC161", "4-bit synchronous binary counter, async clear, sync load", "HC"
    PINS = pins("1:CLR:in 2:CLK:clk 3:A:in 4:B:in 5:C:in 6:D:in 7:ENP:in 8:GND:gnd "
                "9:LOAD:in 10:ENT:in 11:QD:out 12:QC:out 13:QB:out 14:QA:out 15:RCO:out 16:VCC:vcc")
    EDGE = {"CLK": "rise"}
    TPD = {("CLK", "RCO"): 38, ("ENT", "RCO"): 28, ("CLR", "*"): 37, ("*", "*"): 35}
    SETUP = {"A": 30, "B": 30, "C": 30, "D": 30, "ENP": 34, "ENT": 34, "LOAD": 30, "*": 30}
    HOLD = 0
    SAMPLED = {"CLK": ["A", "B", "C", "D", "ENP", "ENT", "LOAD"]}
    DATASHEET = TI.format("sn74hc161")

    def reset_state(self):
        return 0

    def asyncupd(self, g):
        if not bit(g("CLR")) and self.state != 0:
            self.state = 0
            return True
        return False

    def edge(self, g, clk):
        if not bit(g("CLR")):
            return 0
        if not bit(g("LOAD")):
            return sum(bit(g(p)) << i for i, p in enumerate("ABCD"))
        if bit(g("ENP")) and bit(g("ENT")):
            return (self.state + 1) & 15
        return self.state

    def eval(self, g):
        q = self.state
        o = {p: (q >> i) & 1 for i, p in enumerate(["QA", "QB", "QC", "QD"])}
        o["RCO"] = 1 if (q == 15 and bit(g("ENT"))) else 0
        return o


# CD74HCT161 (SCHS154D), VCC = 4.5 V, 25 degC: delays from the MAX column (CL = 50 pF):
# CP->Qn 39, CP->TC 42, TE->TC 32, MR->Qn 50, MR->TC 50; setup and hold from the MIN column:
# setup Pn 10, PE/TE 13, SPE 12; hold Pn 5, PE/TE 3, SPE 3.
HCT161 = variant(HC161, "74HCT161", "HCT",
                 tpd={("CLK", "RCO"): 42, ("ENT", "RCO"): 32, ("CLR", "*"): 50, ("*", "*"): 39},
                 setup={"A": 10, "B": 10, "C": 10, "D": 10, "ENP": 13, "ENT": 13, "LOAD": 12, "*": 10},
                 hold={"A": 5, "B": 5, "C": 5, "D": 5, "ENP": 3, "ENT": 3, "LOAD": 3, "*": 3},
                 datasheet=TI.format("cd74hct161"))
