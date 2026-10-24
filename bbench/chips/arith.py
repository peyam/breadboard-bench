"""Arithmetic chips (74-series). TPD: worst case at 4.5 V, 25 degC (TI datasheets)."""
from .base import Chip, pins, bit, register, variant

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"


# ---------------------------------------------------------------- PC-2 chips (engine)
@register
class HC283(Chip):
    TYPE, DESC, FAMILY = "74HC283", "4-bit binary full adder with fast carry", "HC"
    PINS = pins("1:S2:out 2:B2:in 3:A2:in 4:S1:out 5:A1:in 6:B1:in 7:C0:in 8:GND:gnd "
                "9:C4:out 10:S4:out 11:B4:in 12:A4:in 13:S3:out 14:A3:in 15:B3:in 16:VCC:vcc")
    TPD = {("*", "C4"): 40, ("*", "*"): 45}
    DATASHEET = TI.format("cd74hc283")

    def eval(self, g):
        a = sum(bit(g(f"A{i}")) << (i - 1) for i in range(1, 5))
        b = sum(bit(g(f"B{i}")) << (i - 1) for i in range(1, 5))
        s = a + b + bit(g("C0"))
        o = {f"S{i}": (s >> (i - 1)) & 1 for i in range(1, 5)}
        o["C4"] = (s >> 4) & 1
        return o


# CD74HCT283 (SCHS176E), VCC = 4.5 V, 25 degC, MAX column (CL = 50 pF). The sheet's names are
# CIN, S0-S3, COUT; here C0, S1-S4, C4: C0->S1 31, C0->S2 43, C0->S3 46, C0->S4 53,
# C0->C4 46, A/B->S 49, A/B->C4 48.
HCT283 = variant(HC283, "74HCT283", "HCT",
                 tpd={("C0", "S1"): 31, ("C0", "S2"): 43, ("C0", "S3"): 46, ("C0", "S4"): 53,
                      ("C0", "C4"): 46, ("*", "C4"): 48, ("*", "*"): 49},
                 datasheet=TI.format("cd74hct283"))
