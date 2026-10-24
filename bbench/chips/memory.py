"""Memories in the JEDEC 28-pin package: 32K x 8 static RAM and parallel EEPROM.

Timing (ns, worst case from the datasheets):
AS6C62256-55 (Alliance Memory rev 1.2, 23 March 2016, AC read/write tables, -55 grade):
  tAA 55, tACE 55, tOE 30, tOH 10, tOHZ 20, tWHZ 20 (max), tWP 45, tDW 25 (min).
AT28C256-15 (Microchip DS20006386, Table 6-2 AC Read Characteristics, -15 column):
  tACC 150, tCE 150, tOE 70, tDF 50 (max), tOH 0 (min).
In the timed simulator a memory's outputs are unknown ("X") from tOH after an address
change until the access time (tAA or tACC): the datasheets promise nothing about them then.
The state is a dict {address: byte}; a missing address reads as the blank value.
"""
from .base import Chip, pins, bit, register, FloatingInput, InCircuitWrite, Z

MEM28 = ("1:A14:in 2:A12:in 3:A7:in 4:A6:in 5:A5:in 6:A4:in 7:A3:in 8:A2:in 9:A1:in 10:A0:in "
         "11:IO0:io 12:IO1:io 13:IO2:io 14:GND:gnd 15:IO3:io 16:IO4:io 17:IO5:io 18:IO6:io 19:IO7:io "
         "20:CE:in 21:A10:in 22:OE:in 23:A11:in 24:A9:in 25:A8:in 26:A13:in 27:WE:in 28:VCC:vcc")


def decode_image(image):
    """bytes, bytearray, list of ints, or the project form {"size", "fill", "base64"} -> bytes."""
    if image is None:
        return None
    if isinstance(image, dict):
        from ..core.romdata import decode
        return decode(image)
    return bytes(image)


class Mem28(Chip):
    PINS = pins(MEM28)
    FAMILY = "memory"
    # TTL-compatible inputs and outputs (datasheet DC tables, VCC 4.5-5.5 V)
    VIH, VIL, VOH, VOL = 2.2, 0.8, 2.4, 0.4
    WIDTH = 6
    blank = 0

    def addr(self, g):
        return sum(bit(g(f"A{i}")) << i for i in range(15))

    def writing(self, g):
        return not bit(g("CE")) and not bit(g("WE"))

    def eval(self, g):
        if bit(g("CE")) or bit(g("OE")) or not bit(g("WE")):
            return {f"IO{i}": Z for i in range(8)}
        try:
            v = self.state.get(self.addr(g), self.blank)
        except FloatingInput:
            return {f"IO{i}": "X" for i in range(8)}
        return {f"IO{i}": (v >> i) & 1 for i in range(8)}

    def io_is_input(self, name, g):
        return g("CE") == 0 and g("WE") == 0

    def dump(self, start=0, n=16):
        return [self.state.get(a, self.blank) for a in range(start, start + n)]


# ---------------------------------------------------------------- PC-2 chips (engine)
@register
class SRAM62256(Mem28):
    TYPE, DESC = "AS6C62256", "32K x 8 static RAM"
    TPD = {("OE", "*"): 30, ("WE", "*"): 20, ("*", "*"): 55}       # tOE 30, tWHZ 20, tAA 55
    TDIS = {("OE", "*"): 20, ("CE", "*"): 20, ("WE", "*"): 20}     # tOHZ, tCHZ, tWHZ
    ADDR_HOLD = 10                                                  # tOH: old data kept after an address change
    DATASHEET = "https://www.alliancememory.com/wp-content/uploads/AS6C62256-23-March-2016-rev1.2.pdf"
    VIH, VIL, VOH, VOL = 2.2, 0.6, 2.4, 0.4
    blank = 0

    def __init__(self, ref="U?", image=None, **props):
        super().__init__(ref, **props)
        img = decode_image(image)
        if img is not None:
            self.state = {i: b for i, b in enumerate(img) if b != self.blank}

    def reset_state(self):
        return {}

    def asyncupd(self, g):
        if self.writing(g):
            a = self.addr(g)
            v = sum(bit(g(f"IO{i}")) << i for i in range(8))
            if self.state.get(a) != v:
                self.state[a] = v
                return True
        return False


@register
class EEPROM28C256(Mem28):
    TYPE, DESC = "AT28C256", "32K x 8 parallel EEPROM"
    TPD = {("OE", "*"): 70, ("*", "*"): 150}                        # tOE 70, tACC/tCE 150
    TDIS = {("OE", "*"): 50, ("CE", "*"): 50}                       # tDF
    ADDR_HOLD = 0                                                   # tOH 0: may change at once
    # Microchip's online copy of DS20006386 (the PDF of the same document is
    # https://ww1.microchip.com/downloads/aemDocuments/documents/MPD/ProductDocuments/DataSheets/
    # AT28C256-Industrial-Grade-256-Kbit-Paged-Parallel-EEPROM-Data-Sheet-DS20006386.pdf)
    DATASHEET = "https://onlinedocs.microchip.com/oxy/GUID-7B73D324-9159-4988-92D8-6062218CD25C-en-US-2/index.html"
    VIH, VIL, VOH, VOL = 2.0, 0.8, 2.4, 0.45
    blank = 0xFF

    def __init__(self, ref="U?", image=None, **props):
        super().__init__(ref, **props)
        img = decode_image(image)
        self.image = img
        if img is not None:
            self.state = {i: b for i, b in enumerate(img)}

    def reset_state(self):
        return {}

    def reset(self):
        """Power cycle: an EEPROM keeps its contents."""
        if self.image is not None:
            self.state = {i: b for i, b in enumerate(self.image)}

    def asyncupd(self, g):
        if self.writing(g):
            raise InCircuitWrite(f"{self.ref}: EEPROM written in circuit (WE low)")
        return False
