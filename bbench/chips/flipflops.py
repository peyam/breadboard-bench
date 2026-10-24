"""Flip-flops and registers (74-series). TPD/SETUP/HOLD: worst case at 4.5 V, 25 degC
(TI datasheets)."""
from .base import Chip, pins, bit, register, variant, Z

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"


# ---------------------------------------------------------------- PC-2 chips (engine)
@register
class HC173(Chip):
    TYPE, DESC, FAMILY = "74HC173", "4-bit D register, tri-state outputs, async clear", "HC"
    PINS = pins("1:M:in 2:N:in 3:1Q:tri 4:2Q:tri 5:3Q:tri 6:4Q:tri 7:CLK:clk 8:GND:gnd "
                "9:G1:in 10:G2:in 11:4D:in 12:3D:in 13:2D:in 14:1D:in 15:CLR:in 16:VCC:vcc")
    EDGE = {"CLK": "rise"}
    TPD = {("CLK", "*"): 36, ("CLR", "*"): 35, ("M", "*"): 30, ("N", "*"): 30, ("*", "*"): 36}
    SETUP = {"1D": 25, "2D": 25, "3D": 25, "4D": 25, "G1": 25, "G2": 25}
    HOLD = 5
    SAMPLED = {"CLK": ["1D", "2D", "3D", "4D", "G1", "G2"]}
    DATASHEET = TI.format("cd74hc173")

    def reset_state(self):
        return [0, 0, 0, 0]

    def asyncupd(self, g):
        if bit(g("CLR")) and self.state != [0, 0, 0, 0]:
            self.state = [0, 0, 0, 0]
            return True
        return False

    def edge(self, g, clk):
        if bit(g("CLR")):
            return [0, 0, 0, 0]
        if bit(g("G1")) or bit(g("G2")):
            return self.state
        return [bit(g(f"{i}D")) for i in "1234"]

    def eval(self, g):
        if bit(g("M")) or bit(g("N")):
            return {f"{i}Q": Z for i in "1234"}
        return {f"{i}Q": self.state[k] for k, i in enumerate("1234")}


@register
class HC174(Chip):
    TYPE, DESC, FAMILY = "74HC174", "Hex D flip-flop, async clear", "HC"
    PINS = pins("1:CLR:in 2:1Q:out 3:1D:in 4:2D:in 5:2Q:out 6:3D:in 7:3Q:out 8:GND:gnd "
                "9:CLK:clk 10:4Q:out 11:4D:in 12:5Q:out 13:5D:in 14:6D:in 15:6Q:out 16:VCC:vcc")
    EDGE = {"CLK": "rise"}
    TPD = {("CLR", "*"): 30, ("*", "*"): 32}
    SETUP = 20
    HOLD = 5
    SAMPLED = {"CLK": ["1D", "2D", "3D", "4D", "5D", "6D"]}
    DATASHEET = TI.format("sn74hc174")

    def reset_state(self):
        return [0] * 6

    def asyncupd(self, g):
        if not bit(g("CLR")) and any(self.state):
            self.state = [0] * 6
            return True
        return False

    def edge(self, g, clk):
        if not bit(g("CLR")):
            return [0] * 6
        return [bit(g(f"{i}D")) for i in "123456"]

    def eval(self, g):
        return {f"{i}Q": self.state[k] for k, i in enumerate("123456")}


@register
class HC377(Chip):
    TYPE, DESC, FAMILY = "74HC377", "Octal D flip-flop with clock enable", "HC"
    PINS = pins("1:E:in 2:Q0:out 3:D0:in 4:D1:in 5:Q1:out 6:Q2:out 7:D2:in 8:D3:in 9:Q3:out 10:GND:gnd "
                "11:CLK:clk 12:Q4:out 13:D4:in 14:D5:in 15:Q5:out 16:Q6:out 17:D6:in 18:D7:in 19:Q7:out 20:VCC:vcc")
    EDGE = {"CLK": "rise"}
    TPD = {("*", "*"): 34}
    SETUP = {"E": 25, "*": 20}
    HOLD = 5
    DATASHEET = TI.format("cd74hc377")

    def reset_state(self):
        return [0] * 8

    def edge(self, g, clk):
        if bit(g("E")):
            return self.state
        return [bit(g(f"D{i}")) for i in range(8)]

    def eval(self, g):
        return {f"Q{i}": self.state[i] for i in range(8)}


@register
class HC107(Chip):
    TYPE, DESC, FAMILY = "74HC107", "Dual JK flip-flop, negative-edge clock, async clear", "HC"
    PINS = pins("1:1J:in 2:1QN:out 3:1Q:out 4:1K:in 5:2Q:out 6:2QN:out 7:GND:gnd "
                "8:2J:in 9:2CLK:clk 10:2CLR:in 11:2K:in 12:1CLK:clk 13:1CLR:in 14:VCC:vcc")
    EDGE = {"1CLK": "fall", "2CLK": "fall"}
    TPD = {("?CLR", "*"): 30, ("*", "*"): 30}
    SETUP = 20
    HOLD = 0
    SAMPLED = {"1CLK": ["1J", "1K"], "2CLK": ["2J", "2K"]}
    DATASHEET = TI.format("cd74hc107")

    def reset_state(self):
        return [0, 0]

    def asyncupd(self, g):
        ch = False
        for k, h in enumerate("12"):
            if not bit(g(h + "CLR")) and self.state[k]:
                self.state[k] = 0
                ch = True
        return ch

    def edge(self, g, clk):
        s = list(self.state)
        k = 0 if clk == "1CLK" else 1
        h = "12"[k]
        if not bit(g(h + "CLR")):
            s[k] = 0
            return s
        j, kk = bit(g(h + "J")), bit(g(h + "K"))
        if j and kk:
            s[k] ^= 1
        elif j:
            s[k] = 1
        elif kk:
            s[k] = 0
        return s

    def eval(self, g):
        return {"1Q": self.state[0], "1QN": 1 - self.state[0],
                "2Q": self.state[1], "2QN": 1 - self.state[1]}


# HCT versions. Every figure is from the TI sheet at VCC = 4.5 V, 25 degC: delays from the
# "25 degC MAX" column (CL = 50 pF), setup and hold from the "25 degC MIN" column.
# CD74HCT173 (SCHS158F): CP->Q 40, MR->Q 44, OE->Q 30; setup data 18, E (G1/G2) 12; hold 0 and 0.
HCT173 = variant(HC173, "74HCT173", "HCT",
                 tpd={("CLK", "*"): 40, ("CLR", "*"): 44, ("M", "*"): 30, ("N", "*"): 30, ("*", "*"): 40},
                 setup={"1D": 18, "2D": 18, "3D": 18, "4D": 18, "G1": 12, "G2": 12},
                 hold=0, datasheet=TI.format("cd74hct173"))
# CD74HCT174 (SCHS159C): CP->Q 40, MR->Q 44; setup 16. The sheet gives the hold time only at
# 6 V (5 ns MIN); that figure is used, as the safe side.
HCT174 = variant(HC174, "74HCT174", "HCT", tpd={("CLR", "*"): 44, ("*", "*"): 40},
                 setup=16, hold=5, datasheet=TI.format("cd74hct174"))
# CD74HCT377 (SCHS184C): CP->Q 38; setup data and E 12; hold data 3, E 5.
HCT377 = variant(HC377, "74HCT377", "HCT", tpd={("*", "*"): 38},
                 setup={"E": 12, "*": 12}, hold={"E": 5, "*": 3},
                 datasheet=TI.format("cd74hct377"))
# CD74HCT107 (SCHS139D): CP->Q 43, CP->Q-bar 40, R->Q/Q-bar 38; setup J,K 20; hold J,K 5.
HCT107 = variant(HC107, "74HCT107", "HCT",
                 tpd={("?CLR", "*"): 38, ("*", "?QN"): 40, ("*", "*"): 43},
                 setup=20, hold=5, datasheet=TI.format("cd74hct107"))
