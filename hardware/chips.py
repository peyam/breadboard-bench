"""Pin-accurate logic models of every chip in PC-2 (DIP packages).

Each chip type lists its pins (number -> name, kind) exactly as the datasheet
pin-out shows them. kind: in, out, tri (tri-state output), io (bidirectional),
clk (edge input), vcc, gnd, ana (analogue pin, not simulated).

A model reads input pins with get(name) -> 0, 1 or 'Z' and returns a dict of
output-pin-name -> 0, 1 or 'Z'. Clocked chips also have edge(get, which) that
returns the next state, which the simulator commits for all chips at once.
"""

Z = "Z"


def pins(spec):
    """'1:1A:in 2:1B:in ...' -> {1: ('1A','in'), ...}"""
    out = {}
    for tok in spec.split():
        n, name, kind = tok.split(":")
        out[int(n)] = (name, kind)
    return out


def bit(v):
    if v == Z:
        raise FloatingInput()
    return v


class FloatingInput(Exception):
    pass


def soft(g, name):
    """Read an input that only passes through to an output: an unknown in gives an unknown out."""
    try:
        return g(name)
    except FloatingInput:
        return "X"


class Chip:
    TYPE = "?"
    PINS = {}
    DESC = ""
    EDGE = {}            # clock pin name -> 'rise' or 'fall'

    def __init__(self, ref):
        self.ref = ref
        self.state = self.reset_state()
        self.names = {name: n for n, (name, k) in self.PINS.items()}

    def reset_state(self):
        return None

    def eval(self, g):
        return {}

    def asyncupd(self, g):
        """Level-sensitive state changes (async clear, RAM write). Return True if state changed."""
        return False

    def edge(self, g, clkpin):
        return self.state


# ---------------------------------------------------------------- quad gates
def _quad(fn):
    def ev(self, g):
        o = {}
        for i in "1234":
            o[i + "Y"] = fn(bit(g(i + "A")), bit(g(i + "B")))
        return o
    return ev


GATE14 = pins("1:1A:in 2:1B:in 3:1Y:out 4:2A:in 5:2B:in 6:2Y:out 7:GND:gnd "
              "8:3Y:out 9:3A:in 10:3B:in 11:4Y:out 12:4A:in 13:4B:in 14:VCC:vcc")


class HC00(Chip):
    TYPE, DESC, PINS = "74HC00", "Quad 2-input NAND", GATE14
    eval = _quad(lambda a, b: 1 - (a & b))


class HC08(Chip):
    TYPE, DESC, PINS = "74HC08", "Quad 2-input AND", GATE14
    eval = _quad(lambda a, b: a & b)


class HC32(Chip):
    TYPE, DESC, PINS = "74HC32", "Quad 2-input OR", GATE14
    eval = _quad(lambda a, b: a | b)


class HC86(Chip):
    TYPE, DESC, PINS = "74HC86", "Quad 2-input XOR", GATE14
    eval = _quad(lambda a, b: a ^ b)


class HC02(Chip):
    TYPE, DESC = "74HC02", "Quad 2-input NOR"
    PINS = pins("1:1Y:out 2:1A:in 3:1B:in 4:2Y:out 5:2A:in 6:2B:in 7:GND:gnd "
                "8:3A:in 9:3B:in 10:3Y:out 11:4A:in 12:4B:in 13:4Y:out 14:VCC:vcc")
    eval = _quad(lambda a, b: 1 - (a | b))


class HC04(Chip):
    TYPE, DESC = "74HC04", "Hex inverter"
    PINS = pins("1:1A:in 2:1Y:out 3:2A:in 4:2Y:out 5:3A:in 6:3Y:out 7:GND:gnd "
                "8:4Y:out 9:4A:in 10:5Y:out 11:5A:in 12:6Y:out 13:6A:in 14:VCC:vcc")

    def eval(self, g):
        return {f"{i}Y": 1 - bit(g(f"{i}A")) for i in "123456"}


# ---------------------------------------------------------------- decoders / mux
class HC138(Chip):
    TYPE, DESC = "74HC138", "3-to-8 line decoder, active-low outputs"
    PINS = pins("1:A:in 2:B:in 3:C:in 4:G2A:in 5:G2B:in 6:G1:in 7:Y7:out 8:GND:gnd "
                "9:Y6:out 10:Y5:out 11:Y4:out 12:Y3:out 13:Y2:out 14:Y1:out 15:Y0:out 16:VCC:vcc")

    def eval(self, g):
        en = bit(g("G1")) and not bit(g("G2A")) and not bit(g("G2B"))
        n = bit(g("A")) | bit(g("B")) << 1 | bit(g("C")) << 2
        return {f"Y{i}": 0 if (en and i == n) else 1 for i in range(8)}


class HC139(Chip):
    TYPE, DESC = "74HC139", "Dual 2-to-4 line decoder, active-low outputs"
    PINS = pins("1:1G:in 2:1A:in 3:1B:in 4:1Y0:out 5:1Y1:out 6:1Y2:out 7:1Y3:out 8:GND:gnd "
                "9:2Y3:out 10:2Y2:out 11:2Y1:out 12:2Y0:out 13:2B:in 14:2A:in 15:2G:in 16:VCC:vcc")

    def eval(self, g):
        o = {}
        for h in "12":
            en = not bit(g(h + "G"))
            n = bit(g(h + "A")) | bit(g(h + "B")) << 1
            for i in range(4):
                o[f"{h}Y{i}"] = 0 if (en and i == n) else 1
        return o


class HC157(Chip):
    TYPE, DESC = "74HC157", "Quad 2-to-1 multiplexer"
    PINS = pins("1:S:in 2:1A:in 3:1B:in 4:1Y:out 5:2A:in 6:2B:in 7:2Y:out 8:GND:gnd "
                "9:3Y:out 10:3B:in 11:3A:in 12:4Y:out 13:4B:in 14:4A:in 15:G:in 16:VCC:vcc")

    def eval(self, g):
        if bit(g("G")):
            return {f"{i}Y": 0 for i in "1234"}
        s = bit(g("S"))
        return {f"{i}Y": bit(g(f"{i}B" if s else f"{i}A")) for i in "1234"}


# ---------------------------------------------------------------- buffers
class HC245(Chip):
    TYPE, DESC = "74HC245", "Octal bus transceiver, tri-state"
    PINS = pins("1:DIR:in 2:A1:io 3:A2:io 4:A3:io 5:A4:io 6:A5:io 7:A6:io 8:A7:io 9:A8:io 10:GND:gnd "
                "11:B8:io 12:B7:io 13:B6:io 14:B5:io 15:B4:io 16:B3:io 17:B2:io 18:B1:io 19:OE:in 20:VCC:vcc")

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


# ---------------------------------------------------------------- adders
class HC283(Chip):
    TYPE, DESC = "74HC283", "4-bit binary full adder with fast carry"
    PINS = pins("1:S2:out 2:B2:in 3:A2:in 4:S1:out 5:A1:in 6:B1:in 7:C0:in 8:GND:gnd "
                "9:C4:out 10:S4:out 11:B4:in 12:A4:in 13:S3:out 14:A3:in 15:B3:in 16:VCC:vcc")

    def eval(self, g):
        a = sum(bit(g(f"A{i}")) << (i - 1) for i in range(1, 5))
        b = sum(bit(g(f"B{i}")) << (i - 1) for i in range(1, 5))
        s = a + b + bit(g("C0"))
        o = {f"S{i}": (s >> (i - 1)) & 1 for i in range(1, 5)}
        o["C4"] = (s >> 4) & 1
        return o


# ---------------------------------------------------------------- registers / counters
class HC173(Chip):
    TYPE, DESC = "74HC173", "4-bit D register, tri-state outputs, async clear"
    PINS = pins("1:M:in 2:N:in 3:1Q:tri 4:2Q:tri 5:3Q:tri 6:4Q:tri 7:CLK:clk 8:GND:gnd "
                "9:G1:in 10:G2:in 11:4D:in 12:3D:in 13:2D:in 14:1D:in 15:CLR:in 16:VCC:vcc")
    EDGE = {"CLK": "rise"}

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


class HC161(Chip):
    TYPE, DESC = "74HC161", "4-bit synchronous binary counter, async clear, sync load"
    PINS = pins("1:CLR:in 2:CLK:clk 3:A:in 4:B:in 5:C:in 6:D:in 7:ENP:in 8:GND:gnd "
                "9:LOAD:in 10:ENT:in 11:QD:out 12:QC:out 13:QB:out 14:QA:out 15:RCO:out 16:VCC:vcc")
    EDGE = {"CLK": "rise"}

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


class HC174(Chip):
    TYPE, DESC = "74HC174", "Hex D flip-flop, async clear"
    PINS = pins("1:CLR:in 2:1Q:out 3:1D:in 4:2D:in 5:2Q:out 6:3D:in 7:3Q:out 8:GND:gnd "
                "9:CLK:clk 10:4Q:out 11:4D:in 12:5Q:out 13:5D:in 14:6D:in 15:6Q:out 16:VCC:vcc")
    EDGE = {"CLK": "rise"}

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


class HC377(Chip):
    TYPE, DESC = "74HC377", "Octal D flip-flop with clock enable"
    PINS = pins("1:E:in 2:Q0:out 3:D0:in 4:D1:in 5:Q1:out 6:Q2:out 7:D2:in 8:D3:in 9:Q3:out 10:GND:gnd "
                "11:CLK:clk 12:Q4:out 13:D4:in 14:D5:in 15:Q5:out 16:Q6:out 17:D6:in 18:D7:in 19:Q7:out 20:VCC:vcc")
    EDGE = {"CLK": "rise"}

    def reset_state(self):
        return [0] * 8

    def edge(self, g, clk):
        if bit(g("E")):
            return self.state
        return [bit(g(f"D{i}")) for i in range(8)]

    def eval(self, g):
        return {f"Q{i}": self.state[i] for i in range(8)}


class HC107(Chip):
    TYPE, DESC = "74HC107", "Dual JK flip-flop, negative-edge clock, async clear"
    PINS = pins("1:1J:in 2:1QN:out 3:1Q:out 4:1K:in 5:2Q:out 6:2QN:out 7:GND:gnd "
                "8:2J:in 9:2CLK:clk 10:2CLR:in 11:2K:in 12:1CLK:clk 13:1CLR:in 14:VCC:vcc")
    EDGE = {"1CLK": "fall", "2CLK": "fall"}

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


class HC595(Chip):
    TYPE, DESC = "74HC595", "8-bit shift register with output latch"
    PINS = pins("1:QB:tri 2:QC:tri 3:QD:tri 4:QE:tri 5:QF:tri 6:QG:tri 7:QH:tri 8:GND:gnd "
                "9:QH2:out 10:SRCLR:in 11:SRCLK:clk 12:RCLK:clk 13:OE:in 14:SER:in 15:QA:tri 16:VCC:vcc")
    EDGE = {"SRCLK": "rise", "RCLK": "rise"}

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


# ---------------------------------------------------------------- memories (JEDEC 28-pin)
MEM28 = ("1:A14:in 2:A12:in 3:A7:in 4:A6:in 5:A5:in 6:A4:in 7:A3:in 8:A2:in 9:A1:in 10:A0:in "
         "11:IO0:io 12:IO1:io 13:IO2:io 14:GND:gnd 15:IO3:io 16:IO4:io 17:IO5:io 18:IO6:io 19:IO7:io "
         "20:CE:in 21:A10:in 22:OE:in 23:A11:in 24:A9:in 25:A8:in 26:A13:in 27:WE:in 28:VCC:vcc")


class Mem28(Chip):
    PINS = pins(MEM28)

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


class SRAM62256(Mem28):
    TYPE, DESC = "AS6C62256", "32K x 8 static RAM"
    blank = 0

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


class EEPROM28C256(Mem28):
    TYPE, DESC = "AT28C256", "32K x 8 parallel EEPROM"
    blank = 0xFF

    def __init__(self, ref, image=None):
        super().__init__(ref)
        if image is not None:
            self.state = {i: b for i, b in enumerate(image)}

    def reset_state(self):
        return {}

    def asyncupd(self, g):
        if self.writing(g):
            raise RuntimeError(f"{self.ref}: EEPROM written in circuit (WE low)")
        return False


# ---------------------------------------------------------------- 555 timer (behavioural)
class NE555(Chip):
    """Output is set by the test bench (the analogue timing is not simulated)."""
    TYPE, DESC = "NE555", "Timer"
    PINS = pins("1:GND:gnd 2:TRIG:ana 3:OUT:out 4:RESET:ana 5:CTRL:ana 6:THR:ana 7:DIS:ana 8:VCC:vcc")

    def reset_state(self):
        return 0

    def eval(self, g):
        return {"OUT": self.state}


CHIP_TYPES = {c.TYPE: c for c in [HC00, HC02, HC04, HC08, HC32, HC86, HC107, HC138, HC139, HC157,
                                  HC161, HC173, HC174, HC245, HC283, HC377, HC595, SRAM62256,
                                  EEPROM28C256, NE555]}
