"""Counters, extended library: 74x163, 191, 193, 74HC(T)4040, 74HC(T)4060.

Sources: Nexperia 74HC_HCT163/193/4040/4060 and TI CD74HC191/CD74HCT191 datasheets
(pin-out, function table, timing at 4.5 V, 25 degC).
Ripple counters (4040, 4060): output k settles after tpd(clock -> first output) plus
k-1 times tpd(Qn -> Qn+1); TPD lists that worst case for every output.
"""
from .base import Chip, pins, bit, register, variant
from ._lib import TI, NXP, word, bits


# ---------------------------------------------------------------- 163: sync 4-bit, sync reset
@register
class HCT163(Chip):
    TYPE, FAMILY = "74HCT163", "HCT"
    DESC = "4-bit synchronous binary counter, synchronous reset and load"
    PINS = pins("1:MR:in 2:CP:clk 3:D0:in 4:D1:in 5:D2:in 6:D3:in 7:CEP:in 8:GND:gnd "
                "9:PE:in 10:CET:in 11:Q3:out 12:Q2:out 13:Q1:out 14:Q0:out 15:TC:out 16:VCC:vcc")
    EDGE = {"CP": "rise"}
    TPD = {("CET", "TC"): 32, ("CP", "TC"): 49, ("*", "*"): 39}
    SETUP = {"CEP": 40, "CET": 40, "*": 20}
    HOLD = 0
    SAMPLED = {"CP": ["MR", "PE", "CEP", "CET", "D0", "D1", "D2", "D3"]}
    DATASHEET = NXP.format("74HC_HCT163")

    def reset_state(self):
        return 0

    def edge(self, g, clk):
        if not bit(g("MR")):
            return 0
        if not bit(g("PE")):
            return word([bit(g(f"D{i}")) for i in range(4)])
        if bit(g("CEP")) and bit(g("CET")):
            return (self.state + 1) & 15
        return self.state

    def eval(self, g):
        o = {f"Q{i}": b for i, b in enumerate(bits(self.state, 4))}
        o["TC"] = 1 if (self.state == 15 and bit(g("CET"))) else 0
        return o


HC163 = variant(HCT163, "74HC163", "HC", tpd={("CET", "TC"): 24, ("CP", "TC"): 43, ("*", "*"): 37},
                setup={"CEP": 35, "CET": 35, "*": 16}, hold=0, datasheet=NXP.format("74HC_HCT163"))


# ---------------------------------------------------------------- 191: up/down, async load
@register
class HCT191(Chip):
    TYPE, FAMILY = "74HCT191", "HCT"
    DESC = "4-bit synchronous up/down binary counter, asynchronous load"
    PINS = pins("1:B:in 2:QB:out 3:QA:out 4:CTEN:in 5:DU:in 6:QC:out 7:QD:out 8:GND:gnd "
                "9:D:in 10:C:in 11:LOAD:in 12:MAXMIN:out 13:RCO:out 14:CLK:clk 15:A:in 16:VCC:vcc")
    EDGE = {"CLK": "rise"}
    TPD = {("CLK", "MAXMIN"): 42, ("CLK", "RCO"): 35, ("CTEN", "RCO"): 27, ("DU", "MAXMIN"): 38,
           ("DU", "RCO"): 30, ("LOAD", "Q?"): 40, ("CLK", "Q?"): 27, ("*", "Q?"): 38, ("*", "*"): 42}
    SETUP = {"CTEN": 12, "DU": 18}
    HOLD = {"CTEN": 2, "DU": 0}
    SAMPLED = {"CLK": ["CTEN", "DU"]}
    DATASHEET = TI.format("cd74hct191")

    def reset_state(self):
        return 0

    def _data(self, g):
        return word([bit(g(p)) for p in "ABCD"])

    def asyncupd(self, g):
        if not bit(g("LOAD")):
            d = self._data(g)
            if d != self.state:
                self.state = d
                return True
        return False

    def edge(self, g, clk):
        if not bit(g("LOAD")):
            return self._data(g)
        if bit(g("CTEN")):
            return self.state
        return (self.state - 1) & 15 if bit(g("DU")) else (self.state + 1) & 15

    def eval(self, g):
        q = self.state
        o = {p: b for p, b in zip(["QA", "QB", "QC", "QD"], bits(q, 4))}
        down = bit(g("DU"))
        mm = 1 if (q == 0 if down else q == 15) else 0
        o["MAXMIN"] = mm
        o["RCO"] = 0 if (mm and not bit(g("CTEN")) and not bit(g("CLK"))) else 1
        return o


HC191 = variant(HCT191, "74HC191", "HC",
                tpd={("CLK", "MAXMIN"): 42, ("CLK", "RCO"): 25, ("CTEN", "RCO"): 25, ("DU", "MAXMIN"): 33,
                     ("DU", "RCO"): 30, ("LOAD", "Q?"): 39, ("CLK", "Q?"): 34, ("*", "Q?"): 35, ("*", "*"): 42},
                setup={"CTEN": 12, "DU": 18}, hold={"CTEN": 2, "DU": 0}, datasheet=TI.format("cd74hc191"))


# ---------------------------------------------------------------- 193: up/down, dual clock
@register
class HCT193(Chip):
    TYPE, FAMILY = "74HCT193", "HCT"
    DESC = "4-bit synchronous up/down binary counter, dual clock, async reset and load"
    PINS = pins("1:D1:in 2:Q1:out 3:Q0:out 4:CPD:clk 5:CPU:clk 6:Q2:out 7:Q3:out 8:GND:gnd "
                "9:D3:in 10:D2:in 11:PL:in 12:TCU:out 13:TCD:out 14:MR:in 15:D0:in 16:VCC:vcc")
    EDGE = {"CPU": "rise", "CPD": "rise"}
    TPD = {("CPU", "TCU"): 27, ("CPD", "TCD"): 27, ("CP?", "Q?"): 43, ("PL", "Q?"): 46, ("MR", "Q?"): 40,
           ("D?", "Q?"): 46, ("PL", "TC?"): 55, ("MR", "TC?"): 55, ("D?", "TC?"): 58, ("*", "*"): 58}
    SAMPLED = {"CPU": [], "CPD": []}
    DATASHEET = NXP.format("74HC_HCT193")

    def reset_state(self):
        return 0

    def asyncupd(self, g):
        if bit(g("MR")):
            new = 0
        elif not bit(g("PL")):
            new = word([bit(g(f"D{i}")) for i in range(4)])
        else:
            return False
        if new != self.state:
            self.state = new
            return True
        return False

    def edge(self, g, clk):
        if bit(g("MR")) or not bit(g("PL")):
            return self.state
        if clk == "CPU" and bit(g("CPD")):
            return (self.state + 1) & 15
        if clk == "CPD" and bit(g("CPU")):
            return (self.state - 1) & 15
        return self.state

    def eval(self, g):
        q = self.state
        o = {f"Q{i}": b for i, b in enumerate(bits(q, 4))}
        o["TCU"] = 0 if (q == 15 and not bit(g("CPU"))) else 1
        o["TCD"] = 0 if (q == 0 and not bit(g("CPD"))) else 1
        return o


HC193 = variant(HCT193, "74HC193", "HC",
                tpd={("CPU", "TCU"): 25, ("CPD", "TCD"): 25, ("CP?", "Q?"): 43, ("PL", "Q?"): 44, ("MR", "Q?"): 40,
                     ("D?", "Q?"): 42, ("PL", "TC?"): 58, ("MR", "TC?"): 57, ("D?", "TC?"): 58, ("*", "*"): 58},
                datasheet=NXP.format("74HC_HCT193"))


# ---------------------------------------------------------------- 4040 / 4060: ripple counters
def _ripple_tpd(clk, first, step, mr, outs):
    """{(clk, Qk): first + (k - k0) * step} for each brought-out stage, plus MR."""
    k0 = outs[0]
    t = {(clk, f"Q{k}"): first + (k - k0) * step for k in outs}
    t[("MR", "*")] = mr
    return t


@register
class HCT4040(Chip):
    TYPE, FAMILY = "74HCT4040", "HCT"
    DESC = "12-stage binary ripple counter, falling-edge clock, active-high reset"
    PINS = pins("1:Q11:out 2:Q5:out 3:Q4:out 4:Q6:out 5:Q3:out 6:Q2:out 7:Q1:out 8:GND:gnd "
                "9:Q0:out 10:CP:clk 11:MR:in 12:Q8:out 13:Q7:out 14:Q9:out 15:Q10:out 16:VCC:vcc")
    EDGE = {"CP": "fall"}
    TPD = _ripple_tpd("CP", 40, 20, 45, list(range(12)))
    SAMPLED = {"CP": []}
    DATASHEET = NXP.format("74HC_HCT4040")
    STAGES = 12
    OUTS = list(range(12))

    def reset_state(self):
        return 0

    def asyncupd(self, g):
        if bit(g("MR")) and self.state:
            self.state = 0
            return True
        return False

    def edge(self, g, clk):
        if bit(g("MR")):
            return 0
        return (self.state + 1) % (1 << self.STAGES)

    def eval(self, g):
        return {f"Q{k}": (self.state >> k) & 1 for k in self.OUTS}


HC4040 = variant(HCT4040, "74HC4040", "HC", tpd=_ripple_tpd("CP", 30, 20, 37, list(range(12))),
                 datasheet=NXP.format("74HC_HCT4040"))


@register
class HCT4060(HCT4040):
    TYPE, FAMILY = "74HCT4060", "HCT"
    DESC = ("14-stage binary ripple counter with oscillator pins, falling-edge clock on RS, "
            "active-high reset (RTC/CTC are the analogue oscillator pins, not simulated: "
            "drive RS from a clock)")
    PINS = pins("1:Q11:out 2:Q12:out 3:Q13:out 4:Q5:out 5:Q4:out 6:Q6:out 7:Q3:out 8:GND:gnd "
                "9:CTC:ana 10:RTC:ana 11:RS:clk 12:MR:in 13:Q8:out 14:Q7:out 15:Q9:out 16:VCC:vcc")
    EDGE = {"RS": "fall"}
    OUTS = [3, 4, 5, 6, 7, 8, 9, 11, 12, 13]
    TPD = _ripple_tpd("RS", 66, 16, 44, list(range(3, 14)))
    SAMPLED = {"RS": []}
    DATASHEET = NXP.format("74HC_HCT4060")
    STAGES = 14


HC4060 = variant(HCT4060, "74HC4060", "HC", tpd=_ripple_tpd("RS", 60, 16, 35, list(range(3, 14))),
                 datasheet=NXP.format("74HC_HCT4060"))
