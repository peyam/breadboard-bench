"""Buffers and bus transceivers (74-series). TPD: worst case at 4.5 V, 25 degC
(TI datasheets); enable/disable times are given as OE/DIR -> output delays."""
from .base import Chip, pins, bit, soft, register, variant, Z

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"


# ---------------------------------------------------------------- PC-2 chips (engine)
@register
class HC245(Chip):
    TYPE, DESC, FAMILY = "74HC245", "Octal bus transceiver, tri-state", "HC"
    PINS = pins("1:DIR:in 2:A1:io 3:A2:io 4:A3:io 5:A4:io 6:A5:io 7:A6:io 8:A7:io 9:A8:io 10:GND:gnd "
                "11:B8:io 12:B7:io 13:B6:io 14:B5:io 15:B4:io 16:B3:io 17:B2:io 18:B1:io 19:OE:in 20:VCC:vcc")
    TPD = {("OE", "*"): 45, ("DIR", "*"): 45, ("*", "*"): 22}
    DATASHEET = TI.format("sn74hc245")

    def eval(self, g):
        o = {f"A{i}": Z for i in range(1, 9)}
        o.update({f"B{i}": Z for i in range(1, 9)})
        if bit(g("OE")):
            return o
        src, dst = ("A", "B") if bit(g("DIR")) else ("B", "A")
        for i in range(1, 9):
            o[f"{dst}{i}"] = soft(g, f"{src}{i}")
        return o

    def io_is_input(self, name, g):
        """Which io pins are inputs right now (for floating checks)."""
        if g("OE") == 1:
            return False          # disabled: pin is high impedance and not read
        d = g("DIR")
        return (name[0] == "A") == (d == 1)


# CD74HCT245 (SCHS119B; the kit buys CD74HCT245E), VCC = 4.5 V, 25 degC, MAX column
# (CL = 50 pF): data -> output 26, output enable 32, output disable 30. The sheet gives no DIR
# figure; a DIR change disables one side and enables the other, so DIR uses the same times.
# Drive (same sheet): VOH/VOL are specified at +-4 mA (a test condition, not a limit); the
# absolute maximum is +-25 mA source or sink per output pin and +-50 mA through VCC or GND.
HCT245 = variant(HC245, "74HCT245", "HCT", tpd={("OE", "*"): 32, ("DIR", "*"): 32, ("*", "*"): 26},
                 tdis={("OE", "*"): 30, ("DIR", "*"): 30}, datasheet=TI.format("cd74hct245"))
HCT245.DRIVE = {"test_mA": 4, "abs_max_mA": 25, "supply_abs_max_mA": 50}
