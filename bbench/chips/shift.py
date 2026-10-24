"""Shift registers (74-series). TPD/SETUP/HOLD: worst case at 4.5 V, 25 degC (TI datasheets)."""
from .base import Chip, pins, bit, register, variant, Z

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"


# ---------------------------------------------------------------- PC-2 chips (engine)
@register
class HC595(Chip):
    TYPE, DESC, FAMILY = "74HC595", "8-bit shift register with output latch", "HC"
    PINS = pins("1:QB:tri 2:QC:tri 3:QD:tri 4:QE:tri 5:QF:tri 6:QG:tri 7:QH:tri 8:GND:gnd "
                "9:QH2:out 10:SRCLR:in 11:SRCLK:clk 12:RCLK:clk 13:OE:in 14:SER:in 15:QA:tri 16:VCC:vcc")
    EDGE = {"SRCLK": "rise", "RCLK": "rise"}
    TPD = {("SRCLK", "QH2"): 32, ("SRCLR", "*"): 35, ("OE", "*"): 30, ("*", "*"): 30}
    SETUP = {"SER": 20, "SRCLR": 20, "*": 20}
    HOLD = 0
    SAMPLED = {"SRCLK": ["SER", "SRCLR"], "RCLK": []}
    DATASHEET = TI.format("sn74hc595")

    def reset_state(self):
        return ([0] * 8, [0] * 8)

    def edge(self, g, clk):
        sr, lat = list(self.state[0]), list(self.state[1])
        if clk == "SRCLK":
            sr = [bit(g("SER"))] + sr[:7] if bit(g("SRCLR")) else [0] * 8
        else:
            lat = list(sr)
        return (sr, lat)

    def eval(self, g):
        names = ["QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH"]
        en = not bit(g("OE"))
        o = {n: (self.state[1][i] if en else Z) for i, n in enumerate(names)}
        o["QH2"] = self.state[0][7]
        return o


HCT595 = variant(HC595, "74HCT595", "HCT",
                 tpd={("SRCLK", "QH2"): 38, ("SRCLR", "*"): 40, ("OE", "*"): 35, ("*", "*"): 35},
                 datasheet=TI.format("sn74hct595"))
