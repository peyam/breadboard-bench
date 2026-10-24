"""Flip-flops, latches and registers, extended library:
74x74, 109, 112 (dual flip-flops), 175, 273 (registers with reset),
373, 573 (octal transparent latches), 374, 574 (octal edge registers).

Sources: TI datasheets for 74, 109, 112; Nexperia 74HC_HCTxxx datasheets for the
others (pin-out, function table, timing at 4.5 V, 25 degC). Names ending in N are
complement outputs (Q-bar). Active-low inputs keep their datasheet names (CLR, PRE,
MR, OE) and are documented in DESC.
"""
from .base import Chip, pins, bit, register, variant, Z
from ._lib import TI, NXP


# ---------------------------------------------------------------- 74: dual D, preset + clear
@register
class HCT74(Chip):
    TYPE, FAMILY = "74HCT74", "HCT"
    DESC = "Dual D flip-flop, rising edge, active-low preset and clear"
    PINS = pins("1:1CLR:in 2:1D:in 3:1CLK:clk 4:1PRE:in 5:1Q:out 6:1QN:out 7:GND:gnd "
                "8:2QN:out 9:2Q:out 10:2PRE:in 11:2CLK:clk 12:2D:in 13:2CLR:in 14:VCC:vcc")
    EDGE = {"1CLK": "rise", "2CLK": "rise"}
    TPD = {("?PRE", "*"): 35, ("?CLR", "*"): 35, ("*", "*"): 28}
    SETUP = 12
    HOLD = 0
    SAMPLED = {"1CLK": ["1D"], "2CLK": ["2D"]}
    DATASHEET = TI.format("sn74hct74")

    def reset_state(self):
        return [0, 0]

    def asyncupd(self, g):
        ch = False
        for k, h in enumerate("12"):
            pre, clr = bit(g(h + "PRE")), bit(g(h + "CLR"))
            new = 1 if not pre else (0 if not clr else self.state[k])
            if new != self.state[k]:
                self.state[k] = new
                ch = True
        return ch

    def edge(self, g, clk):
        s = list(self.state)
        k = 0 if clk == "1CLK" else 1
        h = "12"[k]
        if bit(g(h + "PRE")) and bit(g(h + "CLR")):
            s[k] = bit(g(h + "D"))
        return s

    def eval(self, g):
        o = {}
        for k, h in enumerate("12"):
            pre, clr = bit(g(h + "PRE")), bit(g(h + "CLR"))
            if not pre and not clr:            # both low: Q and QN are both high
                q, qn = 1, 1
            elif not pre:
                q, qn = 1, 0
            elif not clr:
                q, qn = 0, 1
            else:
                q, qn = self.state[k], 1 - self.state[k]
            o[h + "Q"], o[h + "QN"] = q, qn
        return o


HC74 = variant(HCT74, "74HC74", "HC", tpd={("?PRE", "*"): 46, ("?CLR", "*"): 46, ("*", "*"): 35},
               setup=20, hold=0, datasheet=TI.format("sn74hc74"))


# ---------------------------------------------------------------- JK flip-flops with preset + clear
class _DualJK(Chip):
    """Shared logic of the 109 (J-Kbar, rising edge) and 112 (J-K, falling edge)."""
    KBAR = False

    def reset_state(self):
        return [0, 0]

    def asyncupd(self, g):
        ch = False
        for k, h in enumerate("12"):
            pre, clr = bit(g(h + "PRE")), bit(g(h + "CLR"))
            new = 1 if not pre else (0 if not clr else self.state[k])
            if new != self.state[k]:
                self.state[k] = new
                ch = True
        return ch

    def edge(self, g, clk):
        s = list(self.state)
        k = 0 if clk == "1CLK" else 1
        h = "12"[k]
        if not (bit(g(h + "PRE")) and bit(g(h + "CLR"))):
            return s
        j = bit(g(h + "J"))
        kk = 1 - bit(g(h + "KN")) if self.KBAR else bit(g(h + "K"))
        if j and kk:
            s[k] ^= 1
        elif j:
            s[k] = 1
        elif kk:
            s[k] = 0
        return s

    def eval(self, g):
        o = {}
        for k, h in enumerate("12"):
            pre, clr = bit(g(h + "PRE")), bit(g(h + "CLR"))
            if not pre and not clr:
                q, qn = 1, 1
            elif not pre:
                q, qn = 1, 0
            elif not clr:
                q, qn = 0, 1
            else:
                q, qn = self.state[k], 1 - self.state[k]
            o[h + "Q"], o[h + "QN"] = q, qn
        return o


@register
class HCT109(_DualJK):
    TYPE, FAMILY = "74HCT109", "HCT"
    DESC = "Dual J-K(bar) flip-flop, rising edge, active-low preset and clear"
    PINS = pins("1:1CLR:in 2:1J:in 3:1KN:in 4:1CLK:clk 5:1PRE:in 6:1Q:out 7:1QN:out 8:GND:gnd "
                "9:2QN:out 10:2Q:out 11:2PRE:in 12:2CLK:clk 13:2KN:in 14:2J:in 15:2CLR:in 16:VCC:vcc")
    EDGE = {"1CLK": "rise", "2CLK": "rise"}
    KBAR = True
    TPD = {("?PRE", "*"): 45, ("?CLR", "*"): 45, ("*", "*"): 40}
    SETUP = 18
    HOLD = 3
    SAMPLED = {"1CLK": ["1J", "1KN"], "2CLK": ["2J", "2KN"]}
    DATASHEET = TI.format("cd74hct109")


HC109 = variant(HCT109, "74HC109", "HC", tpd={("?PRE", "*"): 31, ("?CLR", "*"): 37, ("*", "*"): 35},
                setup=16, hold=5, datasheet=TI.format("cd74hc109"))


@register
class HCT112(_DualJK):
    TYPE, FAMILY = "74HCT112", "HCT"
    DESC = "Dual J-K flip-flop, falling edge, active-low preset and clear"
    PINS = pins("1:1CLK:clk 2:1K:in 3:1J:in 4:1PRE:in 5:1Q:out 6:1QN:out 7:2QN:out 8:GND:gnd "
                "9:2Q:out 10:2PRE:in 11:2J:in 12:2K:in 13:2CLK:clk 14:2CLR:in 15:1CLR:in 16:VCC:vcc")
    EDGE = {"1CLK": "fall", "2CLK": "fall"}
    TPD = {("?PRE", "*"): 32, ("?CLR", "*"): 37, ("*", "*"): 35}
    SETUP = 16
    HOLD = 3
    SAMPLED = {"1CLK": ["1J", "1K"], "2CLK": ["2J", "2K"]}
    DATASHEET = TI.format("cd74hct112")


HC112 = variant(HCT112, "74HC112", "HC", tpd={("?PRE", "*"): 31, ("?CLR", "*"): 36, ("*", "*"): 35},
                setup=16, hold=0, datasheet=TI.format("cd74hc112"))


# ---------------------------------------------------------------- 175: quad D with reset
@register
class HCT175(Chip):
    TYPE, FAMILY = "74HCT175", "HCT"
    DESC = "Quad D flip-flop with Q and Q-bar outputs, active-low master reset"
    PINS = pins("1:MR:in 2:Q0:out 3:Q0N:out 4:D0:in 5:D1:in 6:Q1N:out 7:Q1:out 8:GND:gnd "
                "9:CP:clk 10:Q2:out 11:Q2N:out 12:D2:in 13:D3:in 14:Q3N:out 15:Q3:out 16:VCC:vcc")
    EDGE = {"CP": "rise"}
    TPD = {("MR", "*"): 38, ("*", "*"): 33}
    SETUP = 16
    HOLD = 5
    SAMPLED = {"CP": ["D0", "D1", "D2", "D3"]}
    DATASHEET = NXP.format("74HC_HCT175")

    def reset_state(self):
        return [0] * 4

    def asyncupd(self, g):
        if not bit(g("MR")) and any(self.state):
            self.state = [0] * 4
            return True
        return False

    def edge(self, g, clk):
        if not bit(g("MR")):
            return [0] * 4
        return [bit(g(f"D{i}")) for i in range(4)]

    def eval(self, g):
        o = {}
        for i in range(4):
            o[f"Q{i}"] = self.state[i]
            o[f"Q{i}N"] = 1 - self.state[i]
        return o


HC175 = variant(HCT175, "74HC175", "HC", tpd={("MR", "*"): 30, ("*", "*"): 35},
                setup=16, hold=5, datasheet=NXP.format("74HC_HCT175"))


# ---------------------------------------------------------------- 273: octal D with reset
@register
class HCT273(Chip):
    TYPE, FAMILY = "74HCT273", "HCT"
    DESC = "Octal D flip-flop, active-low master reset"
    PINS = pins("1:MR:in 2:Q0:out 3:D0:in 4:D1:in 5:Q1:out 6:Q2:out 7:D2:in 8:D3:in 9:Q3:out 10:GND:gnd "
                "11:CP:clk 12:Q4:out 13:D4:in 14:D5:in 15:Q5:out 16:Q6:out 17:D6:in 18:D7:in 19:Q7:out 20:VCC:vcc")
    EDGE = {"CP": "rise"}
    TPD = {("MR", "*"): 34, ("*", "*"): 30}
    SETUP = 12
    HOLD = 3
    SAMPLED = {"CP": [f"D{i}" for i in range(8)]}
    DATASHEET = NXP.format("74HC_HCT273")

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
        return [bit(g(f"D{i}")) for i in range(8)]

    def eval(self, g):
        return {f"Q{i}": self.state[i] for i in range(8)}


HC273 = variant(HCT273, "74HC273", "HC", tpd={("MR", "*"): 30, ("*", "*"): 30},
                setup=12, hold=3, datasheet=NXP.format("74HC_HCT273"))


# ---------------------------------------------------------------- octal latches and registers
P373 = ("1:OE:in 2:Q0:tri 3:D0:in 4:D1:in 5:Q1:tri 6:Q2:tri 7:D2:in 8:D3:in 9:Q3:tri 10:GND:gnd "
        "11:{c} 12:Q4:tri 13:D4:in 14:D5:in 15:Q5:tri 16:Q6:tri 17:D6:in 18:D7:in 19:Q7:tri 20:VCC:vcc")
P573 = ("1:OE:in 2:D0:in 3:D1:in 4:D2:in 5:D3:in 6:D4:in 7:D5:in 8:D6:in 9:D7:in 10:GND:gnd "
        "11:{c} 12:Q7:tri 13:Q6:tri 14:Q5:tri 15:Q4:tri 16:Q3:tri 17:Q2:tri 18:Q1:tri 19:Q0:tri 20:VCC:vcc")


class _Octal(Chip):
    def reset_state(self):
        return [0] * 8

    def eval(self, g):
        if bit(g("OE")):
            return {f"Q{i}": Z for i in range(8)}
        return {f"Q{i}": self.state[i] for i in range(8)}


class _Latch(_Octal):
    """Transparent while LE is high; holds the data present when LE goes low."""

    def asyncupd(self, g):
        if bit(g("LE")):
            d = [bit(g(f"D{i}")) for i in range(8)]
            if d != self.state:
                self.state = d
                return True
        return False


class _Register(_Octal):
    """Loads D on the rising edge of CP (the output enable does not affect loading)."""
    EDGE = {"CP": "rise"}
    SAMPLED = {"CP": [f"D{i}" for i in range(8)]}

    def edge(self, g, clk):
        return [bit(g(f"D{i}")) for i in range(8)]


@register
class HCT373(_Latch):
    TYPE, FAMILY = "74HCT373", "HCT"
    DESC = "Octal transparent D latch, tri-state outputs (active-low OE)"
    PINS = pins(P373.format(c="LE:in"))
    TPD = {("OE", "*"): 32, ("LE", "*"): 32, ("*", "*"): 30}
    SETUP = 12          # D before LE falls
    HOLD = 4
    DATASHEET = NXP.format("74HC_HCT373")


@register
class HCT573(_Latch):
    TYPE, FAMILY = "74HCT573", "HCT"
    DESC = "Octal transparent D latch, tri-state outputs (active-low OE), flow-through pin-out"
    PINS = pins(P573.format(c="LE:in"))
    TPD = {("OE", "*"): 30, ("LE", "*"): 35, ("*", "*"): 35}
    SETUP = 13
    HOLD = 9
    DATASHEET = NXP.format("74HC_HCT573")


@register
class HCT374(_Register):
    TYPE, FAMILY = "74HCT374", "HCT"
    DESC = "Octal D flip-flop, rising edge, tri-state outputs (active-low OE)"
    PINS = pins(P373.format(c="CP:clk"))
    TPD = {("OE", "*"): 30, ("*", "*"): 32}
    SETUP = 12
    HOLD = 5
    DATASHEET = NXP.format("74HC_HCT374")


@register
class HCT574(_Register):
    TYPE, FAMILY = "74HCT574", "HCT"
    DESC = "Octal D flip-flop, rising edge, tri-state outputs (active-low OE), flow-through pin-out"
    PINS = pins(P573.format(c="CP:clk"))
    TPD = {("OE", "*"): 33, ("*", "*"): 33}
    SETUP = 12
    HOLD = 5
    DATASHEET = NXP.format("74HC_HCT574")


HC373 = variant(HCT373, "74HC373", "HC", tpd={("OE", "*"): 30, ("LE", "*"): 35, ("*", "*"): 30},
                setup=10, hold=5, datasheet=NXP.format("74HC_HCT373"))
HC573 = variant(HCT573, "74HC573", "HC", tpd={("OE", "*"): 30, ("LE", "*"): 30, ("*", "*"): 30},
                setup=10, hold=5, datasheet=NXP.format("74HC_HCT573"))
HC374 = variant(HCT374, "74HC374", "HC", tpd={("OE", "*"): 30, ("*", "*"): 33},
                setup=12, hold=5, datasheet=NXP.format("74HC_HCT374"))
HC574 = variant(HCT574, "74HC574", "HC", tpd={("OE", "*"): 28, ("*", "*"): 30},
                setup=12, hold=5, datasheet=NXP.format("74HC_HCT574"))
