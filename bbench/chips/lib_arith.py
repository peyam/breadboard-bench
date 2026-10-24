"""Arithmetic, extended library: 74LS181 4-bit ALU / function generator.

Source: Motorola SN54/74LS181 datasheet (FAST and LS TTL data book), the text copy
hosted by the University of Florida (TI's SN74LS181 sheet is a scanned image and
onsemi's copy could not be fetched). Pin-out (24-pin DIP), function table and
switching characteristics at VCC = 5.0 V, 25 degC, CL = 15 pF (the LS test condition).

The model follows the active-HIGH data convention of the datasheet: Cn = H means
no carry in, CN4 (Cn+4) = L means carry out, and P and G are active LOW. A=B is an
open-collector output: it is released (Z) when all four F outputs are high and pulls
low otherwise, so it needs a pull-up resistor.

Logic (per bit i, from the datasheet's logic diagram):
    t1 = NOT(A + B.S0 + Bbar.S1)       t2 = NOT(A.Bbar.S2 + A.B.S3)
    generate gi = NOT t2, propagate pi = NOT t1, carry c(i+1) = gi + pi.ci, c0 = NOT Cn
    F = t1 XOR t2 XOR (ci if M = L else 1)
"""
from .base import Chip, pins, bit, register, Z

MOTOROLA_LS181 = "https://mil.ufl.edu/4712/docs/74LS181.pdf"


def alu181(a, b, s, m, cn):
    """a, b, s: 4-bit ints; m, cn: 0/1 pin levels. Returns (f, cn4, p, g) pin levels."""
    s0, s1, s2, s3 = (s >> 0) & 1, (s >> 1) & 1, (s >> 2) & 1, (s >> 3) & 1
    c = 1 - cn
    f = 0
    gg = pp = 0           # group generate / propagate (active-high internally)
    pall = 1
    for i in range(4):
        ai, bi = (a >> i) & 1, (b >> i) & 1
        t1 = 1 - (ai | (bi & s0) | ((1 - bi) & s1))
        t2 = 1 - ((ai & (1 - bi) & s2) | (ai & bi & s3))
        gi, pi = 1 - t2, 1 - t1
        fi = t1 ^ t2 ^ (1 if m else c)
        f |= fi << i
        c = gi | (pi & c)
        gg = gi | (pi & gg)
        pall &= pi
    pp = pall
    cn4 = 1 - c
    return f, cn4, 1 - pp, 1 - gg


@register
class LS181(Chip):
    TYPE, FAMILY = "74LS181", "LS"
    DESC = "4-bit arithmetic logic unit / function generator (16 logic and 16 arithmetic functions)"
    PINS = pins("1:B0:in 2:A0:in 3:S3:in 4:S2:in 5:S1:in 6:S0:in 7:CN:in 8:M:in 9:F0:out 10:F1:out "
                "11:F2:out 12:GND:gnd 13:F3:out 14:AEQB:tri 15:CN4:out 16:P:out 17:G:out 18:B3:in "
                "19:A3:in 20:B2:in 21:A2:in 22:B1:in 23:A1:in 24:VCC:vcc")
    # Worst of tPLH/tPHL over sum, difference and logic modes. S and M paths are not
    # specified in the datasheet; they use the slowest A/B -> output figure.
    TPD = {("CN", "CN4"): 27, ("CN", "F?"): 26, ("CN", "AEQB"): 62,
           ("[AB]?", "G"): 32, ("[AB]?", "P"): 33, ("[AB]?", "F?"): 38, ("[AB]?", "CN4"): 41,
           ("*", "AEQB"): 62, ("*", "*"): 41}
    DATASHEET = MOTOROLA_LS181

    def eval(self, g):
        a = sum(bit(g(f"A{i}")) << i for i in range(4))
        b = sum(bit(g(f"B{i}")) << i for i in range(4))
        s = sum(bit(g(f"S{i}")) << i for i in range(4))
        f, cn4, p, gg = alu181(a, b, s, bit(g("M")), bit(g("CN")))
        o = {f"F{i}": (f >> i) & 1 for i in range(4)}
        o.update({"CN4": cn4, "P": p, "G": gg, "AEQB": Z if f == 15 else 0})
        return o
