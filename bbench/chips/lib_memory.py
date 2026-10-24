"""Memories in the 24-pin JEDEC package (0.6 in DIP), extended library:
AT28C16 (2K x 8 parallel EEPROM) and 6116 (2K x 8 static RAM).

Sources: Atmel/Microchip AT28C16 datasheet (doc 0540B, the Atmel PDF via a
distributor link: Microchip's own server refuses automated fetches) and the Renesas (IDT) 6116SA/LA datasheet.
Timing: AT28C16-15 tACC = tCE = 150 ns, tOE = 70 ns, tDF = 50 ns;
6116SA15 tAA = tACS = 15 ns, tOE = 10 ns, tOHZ = 8 ns (the fastest grade; slower
grades are slower). The state is a dict {address: byte}; a missing address reads as
the blank value.
"""
from .base import Chip, pins, bit, register, FloatingInput, InCircuitWrite, Z, X

MEM24 = ("1:A7:in 2:A6:in 3:A5:in 4:A4:in 5:A3:in 6:A2:in 7:A1:in 8:A0:in "
         "9:IO0:io 10:IO1:io 11:IO2:io 12:GND:gnd 13:IO3:io 14:IO4:io 15:IO5:io 16:IO6:io "
         "17:IO7:io 18:{cs}:in 19:A10:in 20:OE:in 21:WE:in 22:A9:in 23:A8:in 24:VCC:vcc")


def _image(image):
    if image is None:
        return None
    if isinstance(image, dict):
        from ..core.romdata import decode
        return decode(image)
    return bytes(image)


class _Mem24(Chip):
    FAMILY = "memory"
    VIH, VIL, VOH, VOL = 2.0, 0.8, 2.4, 0.4      # TTL-compatible
    WIDTH = 6
    CS = "CE"
    blank = 0

    def __init__(self, ref="U?", image=None, **props):
        super().__init__(ref, **props)
        img = _image(image)
        if img is not None:
            self.state = {i: v for i, v in enumerate(img[:2048]) if v != self.blank}

    def reset_state(self):
        return {}

    def addr(self, g):
        return sum(bit(g(f"A{i}")) << i for i in range(11))

    def writing(self, g):
        return not bit(g(self.CS)) and not bit(g("WE"))

    def eval(self, g):
        if bit(g(self.CS)) or bit(g("OE")) or not bit(g("WE")):
            return {f"IO{i}": Z for i in range(8)}
        try:
            v = self.state.get(self.addr(g), self.blank)
        except FloatingInput:
            return {f"IO{i}": X for i in range(8)}
        return {f"IO{i}": (v >> i) & 1 for i in range(8)}

    def io_is_input(self, name, g):
        return g(self.CS) == 0 and g("WE") == 0

    def dump(self, start=0, n=16):
        return [self.state.get(a, self.blank) for a in range(start, start + n)]


@register
class AT28C16(_Mem24):
    TYPE = "AT28C16"
    DESC = "2K x 8 parallel EEPROM (programmed outside the circuit)"
    PINS = pins(MEM24.format(cs="CE"))
    CS = "CE"
    TPD = {("OE", "*"): 70, ("*", "*"): 150}
    DATASHEET = "https://ipv4.pccomponents.com/datasheets/ATMEL-AT28C16E15SC.pdf"   # Atmel doc 0540; microchip.com blocks fetching
    blank = 0xFF

    def asyncupd(self, g):
        if self.writing(g):
            raise InCircuitWrite(f"{self.ref}: EEPROM written in circuit (WE low)")
        return False


@register
class SRAM6116(_Mem24):
    TYPE = "6116"
    DESC = "2K x 8 static RAM"
    PINS = pins(MEM24.format(cs="CS"))
    CS = "CS"
    TPD = {("OE", "*"): 10, ("*", "*"): 15}
    DATASHEET = "https://www.renesas.com/us/en/document/dst/6116sala-data-sheet"
    blank = 0

    def asyncupd(self, g):
        if self.writing(g):
            a = self.addr(g)
            v = sum(bit(g(f"IO{i}")) << i for i in range(8))
            if self.state.get(a, self.blank) != v:
                self.state[a] = v
                return True
        return False
