"""pc2 — microcode-level emulator for the PC-2 breadboard computer.

The emulator does not "know" the instructions. It only knows the hardware:
registers, bus, ALU, flags and control lines. Behaviour comes entirely from the
microcode ROM image built by build_microcode(), so running the programs tests
the ROM contents that will be burned into the three AT28C256 control EEPROMs.

Instruction byte: high nibble = opcode, low nibble = operand (address or value).
Opcodes 0-7 keep PC-1's numbering and meaning (PC-1 opcode with a leading 0).
"""

# ---- control lines (24 available across three EEPROMs; 18 used) ----
SIGNALS = ["HLT", "MI", "RI", "RO", "IO", "II", "AI", "AO",      # ROM 0
           "EO", "SU", "BI", "OI", "CE", "CO", "J", "FI",        # ROM 1
           "XO", "SR", None, None, None, None, None, None]       # ROM 2
BIT = {s: 1 << i for i, s in enumerate(SIGNALS) if s}

def cw(*names):
    v = 0
    for n in names:
        v |= BIT[n]
    return v

FETCH = [cw("CO", "MI"), cw("RO", "II", "CE")]

# operation steps after fetch; conditional jumps resolved per flag state
OPS = {
    0x0: ("HALT",  [cw("HLT")]),
    0x1: ("LOAD",  [cw("IO", "MI"), cw("RO", "AI", "SR")]),
    0x2: ("STORE", [cw("IO", "MI"), cw("AO", "RI", "SR")]),
    0x3: ("ADD",   [cw("IO", "MI"), cw("RO", "BI"), cw("EO", "AI", "FI", "SR")]),
    0x4: ("SUB",   [cw("IO", "MI"), cw("RO", "BI"), cw("EO", "AI", "SU", "FI", "SR")]),
    0x5: ("JUMP",  [cw("IO", "J", "SR")]),
    0x6: ("JC",    None),   # conditional, below
    0x7: ("OUT",   [cw("AO", "OI", "SR")]),
    0x8: ("LDI",   [cw("IO", "AI", "SR")]),
    0x9: ("ADI",   [cw("IO", "BI"), cw("EO", "AI", "FI", "SR")]),
    0xA: ("SBI",   [cw("IO", "BI"), cw("EO", "AI", "SU", "FI", "SR")]),
    0xB: ("JZ",    None),
    0xC: ("IN",    [cw("XO", "AI", "SR")]),
    0xD: ("NOP",   [cw("SR")]),
    0xE: ("USR1",  [cw("SR")]),   # reserved for the reader's own instruction
    0xF: ("USR2",  [cw("SR")]),
}
NAMES = {op: n for op, (n, _) in OPS.items()}
CODES = {n: op for op, n in NAMES.items()}

def build_microcode():
    """ROM address = C<<8 | Z<<7 | opcode<<3 | step  (11 of 15 address lines)."""
    rom = {}
    for c in (0, 1):
        for z in (0, 1):
            for op in range(16):
                name, steps = OPS[op]
                if name == "JC":
                    steps = [cw("IO", "J", "SR")] if c else [cw("SR")]
                if name == "JZ":
                    steps = [cw("IO", "J", "SR")] if z else [cw("SR")]
                full = FETCH + steps
                assert len(full) <= 8, name
                for step in range(8):
                    word = full[step] if step < len(full) else cw("SR")
                    rom[(c << 8) | (z << 7) | (op << 3) | step] = word
    return rom

ROM = build_microcode()

def rom_images():
    """Three 2 KB images (one byte per EEPROM) - what the programmer burns."""
    imgs = [bytearray(2048) for _ in range(3)]
    for addr, word in ROM.items():
        for k in range(3):
            imgs[k][addr] = (word >> (8 * k)) & 0xFF
    return imgs

class PC2:
    def __init__(self, mem, in0=0, in1=0):
        self.mem = [0] * 16
        for i, v in enumerate(mem):
            self.mem[i] = v & 0xFF
        self.inp = [in0 & 0xFF, in1 & 0xFF]
        self.a = self.b = self.ir = self.mar = self.pc = 0
        self.out, self.mode = None, 0
        self.c = self.z = 0
        self.halted = False
        self.cycles = 0
        self.shown = []           # every value written to the display

    def alu(self, su):
        b = (self.b ^ 0xFF) if su else self.b
        s = self.a + b + (1 if su else 0)
        return s & 0xFF, 1 if s > 0xFF else 0, 1 if (s & 0xFF) == 0 else 0

    def run(self, limit=5000):
        step = 0
        while not self.halted and self.cycles < limit:
            op = self.ir >> 4
            word = ROM[(self.c << 8) | (self.z << 7) | (op << 3) | step]
            on = lambda s: bool(word & BIT[s])
            e, ec, ez = self.alu(on("SU"))
            drivers = [s for s in ("RO", "IO", "AO", "EO", "CO", "XO") if on(s)]
            assert len(drivers) <= 1, f"bus fight {drivers}"
            bus = {"RO": lambda: self.mem[self.mar], "IO": lambda: self.ir & 0x0F,
                   "AO": lambda: self.a, "EO": lambda: e, "CO": lambda: self.pc,
                   "XO": lambda: self.inp[self.ir & 1]}[drivers[0]]() if drivers else 0
            # rising clock edge: all loads together
            if on("HLT"):
                self.halted = True
            if on("MI"): self.mar = bus & 0x0F
            if on("RI"): self.mem[self.mar] = bus
            if on("II"): self.ir = bus
            if on("AI"): self.a = bus
            if on("BI"): self.b = bus
            if on("OI"):
                self.out, self.mode = bus, self.ir & 0x03
                self.shown.append(bus)
            if on("FI"): self.c, self.z = ec, ez
            if on("J"):  self.pc = bus & 0x0F
            if on("CE"): self.pc = (self.pc + 1) & 0x0F
            self.cycles += 1
            step = 0 if on("SR") else step + 1
        assert self.halted, "did not halt"
        return self

def asm(lines):
    """['IN 0', 'OUT 0', 'HALT', ...] or raw ints for data -> bytes."""
    out = []
    for l in lines:
        if isinstance(l, int):
            out.append(l & 0xFF); continue
        parts = l.split()
        n = int(parts[1]) if len(parts) > 1 else 0
        assert 0 <= n <= 15, l
        out.append((CODES[parts[0]] << 4) | n)
    assert len(out) <= 16, "program bigger than 16 bytes"
    return out

def display(value, mode):
    """What the 4-digit display shows (mode = OUT operand bits 0-1)."""
    if mode == 0: return f"{value:>4d}"
    if mode == 1: return f"{value - 256 if value > 127 else value:>4d}"
    if mode == 2: return f"  {value:02X}"
    return "    "          # mode 3: blank (reserved)
