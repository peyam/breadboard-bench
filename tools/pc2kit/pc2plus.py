"""pc2plus - microcode-level emulator for PC-2+, the 256-byte design of Chapter 13.

Written in the same style as tools/pc2kit/pc2.py. The emulator does not "know" the
instructions: it only knows the hardware (registers, bus, ALU, flags, control lines),
and behaviour comes entirely from the microcode table built by build_microcode().

What changes from PC-2 (a design, not yet built on breadboards):
  * program counter: 8 bits (two 74HCT161s cascaded, RCO of the low chip -> ENT of the high chip),
    both clocked by CLK_n as on PC-2, so the PC counts or loads at the falling edge that ends a step
  * memory address register: 8 bits (two 74HCT173s); RAM address lines A0-A7 are used (256 bytes)
  * the PC drives all 8 bus bits; the MAR loads all 8 bus bits
  * instructions that need an address or a value take TWO bytes:
        opcode byte  = opcode in the high nibble, low nibble spare (written as 0)
        operand byte = a full 8-bit address or value
    HALT, OUT m, IN p, NOP, USR1, USR2 stay ONE byte and still use the low nibble (m, p).
  * no new control lines: the operand byte is read from RAM straight into the register that
    needs it (MAR for memory instructions, A or B for immediates, PC for jumps).
    IO (operand nibble to the bus) is no longer used by any instruction.
"""

# ---- control lines: exactly PC-2's 18 lines, same ROM bits ----
SIGNALS = ["HLT", "MI", "RI", "RO", "IO", "II", "AI", "AO",      # ROM 0
           "EO", "SU", "BI", "OI", "CE", "CO", "J", "FI",        # ROM 1
           "XO", "SR", None, None, None, None, None, None]       # ROM 2
BIT = {s: 1 << i for i, s in enumerate(SIGNALS) if s}


def cw(*names):
    v = 0
    for n in names:
        v |= BIT[n]
    return v


FETCH = [cw("CO", "MI"), cw("RO", "II", "CE")]             # T0, T1: opcode byte
OPERAND = cw("CO", "MI")                                    # T2: point the MAR at the operand byte
ADDR = cw("RO", "MI", "CE")                                 # T3: operand byte -> MAR, step past it

# steps after the opcode fetch (T2 onwards); None = conditional, resolved in build_microcode
OPS = {
    0x0: ("HALT",  1, [cw("HLT")]),
    0x1: ("LOAD",  2, [OPERAND, ADDR, cw("RO", "AI", "SR")]),
    0x2: ("STORE", 2, [OPERAND, ADDR, cw("AO", "RI", "SR")]),
    0x3: ("ADD",   2, [OPERAND, ADDR, cw("RO", "BI"), cw("EO", "AI", "FI", "SR")]),
    0x4: ("SUB",   2, [OPERAND, ADDR, cw("RO", "BI"), cw("EO", "AI", "SU", "FI", "SR")]),
    0x5: ("JUMP",  2, [OPERAND, cw("RO", "J", "SR")]),
    0x6: ("JC",    2, None),
    0x7: ("OUT",   1, [cw("AO", "OI", "SR")]),
    0x8: ("LDI",   2, [OPERAND, cw("RO", "AI", "CE", "SR")]),
    0x9: ("ADI",   2, [OPERAND, cw("RO", "BI", "CE"), cw("EO", "AI", "FI", "SR")]),
    0xA: ("SBI",   2, [OPERAND, cw("RO", "BI", "CE"), cw("EO", "AI", "SU", "FI", "SR")]),
    0xB: ("JZ",    2, None),
    0xC: ("IN",    1, [cw("XO", "AI", "SR")]),
    0xD: ("NOP",   1, [cw("SR")]),
    0xE: ("USR1",  1, [cw("SR")]),
    0xF: ("USR2",  1, [cw("SR")]),
}
TAKEN = [OPERAND, cw("RO", "J", "SR")]      # jump: operand byte -> PC
SKIP = [cw("CE", "SR")]                     # no jump: step the PC past the operand byte
NAMES = {op: n for op, (n, _, _) in OPS.items()}
CODES = {n: op for op, n in NAMES.items()}
SIZE = {n: s for op, (n, s, _) in OPS.items()}


def steps_for(op, c, z):
    name, _, steps = OPS[op]
    if name == "JC":
        return TAKEN if c else SKIP
    if name == "JZ":
        return TAKEN if z else SKIP
    return steps


def build_microcode():
    """ROM address = C<<8 | Z<<7 | opcode<<3 | step - the same address wiring as PC-2."""
    rom = {}
    for c in (0, 1):
        for z in (0, 1):
            for op in range(16):
                full = FETCH + steps_for(op, c, z)
                assert len(full) <= 8, NAMES[op]
                assert full[-1] & (BIT["SR"] | BIT["HLT"]), NAMES[op]
                for step in range(8):
                    rom[(c << 8) | (z << 7) | (op << 3) | step] = full[step] if step < len(full) else cw("SR")
    return rom


ROM = build_microcode()


def rom_images():
    """Three 2 KB images, one byte per EEPROM, stored inverted (0 = line on) as on PC-2."""
    imgs = [bytearray(2048) for _ in range(3)]
    for addr, word in ROM.items():
        for k in range(3):
            imgs[k][addr] = (~(word >> (8 * k))) & 0xFF
    return imgs


class PC2Plus:
    def __init__(self, mem, in0=0, in1=0):
        self.mem = [0] * 256
        for i, v in enumerate(mem):
            self.mem[i] = v & 0xFF
        self.inp = [in0 & 0xFF, in1 & 0xFF]
        self.a = self.b = self.ir = self.mar = self.pc = 0
        self.out, self.mode = None, 0
        self.c = self.z = 0
        self.halted = False
        self.cycles = 0
        self.step = 0
        self.shown = []

    def alu(self, su):
        b = (self.b ^ 0xFF) if su else self.b
        s = self.a + b + (1 if su else 0)
        return s & 0xFF, 1 if s > 0xFF else 0, 1 if (s & 0xFF) == 0 else 0

    def word(self):
        return ROM[(self.c << 8) | (self.z << 7) | ((self.ir >> 4) << 3) | self.step]

    def bus(self, word):
        on = lambda s: bool(word & BIT[s])
        drivers = [s for s in ("RO", "IO", "AO", "EO", "CO", "XO") if on(s)]
        assert len(drivers) <= 1, f"bus fight {drivers}"
        if not drivers:
            return None            # 10 kOhm pull-downs: an undriven bus reads 0
        e = self.alu(on("SU"))[0]
        return {"RO": lambda: self.mem[self.mar], "IO": lambda: self.ir & 0x0F,
                "AO": lambda: self.a, "EO": lambda: e, "CO": lambda: self.pc,
                "XO": lambda: self.inp[self.ir & 1]}[drivers[0]]()

    def tick(self):
        """One clock cycle (one step): registers load on the rising edge of CLK; the PC counts or loads
        on the falling edge that ends the step. Nothing reads the PC between those two edges except
        CO in the same step, which sees the old value either way, so one update per step is exact."""
        word = self.word()
        on = lambda s: bool(word & BIT[s])
        v = self.bus(word)
        bus = 0 if v is None else v
        e, ec, ez = self.alu(on("SU"))
        if on("HLT"): self.halted = True
        if on("MI"): self.mar = bus                  # 8 bits now
        if on("RI"): self.mem[self.mar] = bus
        if on("II"): self.ir = bus
        if on("AI"): self.a = bus
        if on("BI"): self.b = bus
        if on("OI"):
            self.out, self.mode = bus, self.ir & 0x03
            self.shown.append(bus)
        if on("FI"): self.c, self.z = ec, ez
        if on("J"):  self.pc = bus                   # 8 bits now
        if on("CE"): self.pc = (self.pc + 1) & 0xFF  # RCO of the low counter carries into the high one
        self.cycles += 1
        self.step = 0 if on("SR") else self.step + 1
        return word, v

    def run(self, limit=200000):
        while not self.halted and self.cycles < limit:
            self.tick()
        assert self.halted, "did not halt"
        return self


# ------------------------------------------------------------------ assembler (two passes, labels)
def asm(lines, origin=0):
    """Lines like 'loop: LOAD x', 'IN 1', 'x: data 0', 'list: data 4 9 2'. Operands may be numbers,
    hex (0x80) or labels, and 'label+1'. Returns {address: byte} and the label table."""
    def parse(l):
        l = l.split(";")[0].strip()
        lab = None
        if ":" in l:
            lab, l = [s.strip() for s in l.split(":", 1)]
        return lab, l.split()

    labels, addr = {}, origin
    for l in lines:                                     # pass 1: where is every label?
        lab, t = parse(l)
        if t and t[0] == "org":
            addr = int(t[1], 0)
        if lab:
            labels[lab] = addr
        if t and t[0] != "org":
            addr += len(t) - 1 if t[0] == "data" else SIZE[t[0]]

    def val(s):
        if "+" in s:
            a, b = s.split("+")
            return val(a) + val(b)
        if s in labels:
            return labels[s]
        return int(s, 0)

    mem, addr = {}, origin
    for l in lines:                                     # pass 2: write the bytes
        _, t = parse(l)
        if not t:
            continue
        if t[0] == "org":
            addr = int(t[1], 0); continue
        if t[0] == "data":
            for s in t[1:]:
                mem[addr] = val(s) & 0xFF; addr += 1
            continue
        op, n = CODES[t[0]], SIZE[t[0]]
        if n == 1:
            k = val(t[1]) if len(t) > 1 else 0
            assert 0 <= k <= 15
            mem[addr] = (op << 4) | k; addr += 1
        else:
            k = val(t[1])
            assert 0 <= k <= 255, l
            mem[addr] = op << 4; mem[addr + 1] = k; addr += 2
    assert addr <= 256, "program bigger than 256 bytes"
    return mem, labels


def image(mem):
    m = [0] * 256
    for a, v in mem.items():
        m[a] = v
    return m


def disasm(mem, addr):
    b = mem[addr]
    name = NAMES[b >> 4]
    if SIZE[name] == 2:
        return f"{name} {mem[(addr + 1) & 0xFF]}", 2
    if name in ("OUT", "IN"):
        return f"{name} {b & 15}", 1
    return name, 1


def control_names(word):
    return [s for s in SIGNALS if s and word & BIT[s]]


def trace(mem, in0=0, in1=0, max_cycles=200):
    m = PC2Plus(image(mem) if isinstance(mem, dict) else mem, in0, in1)
    rows = []
    while not m.halted and m.cycles < max_cycles:
        step = m.step
        word, bus = m.tick()
        rows.append(dict(cycle=m.cycles, step=f"T{step}", lines=[s for s in control_names(word) if s != "SR"],
                         sr=bool(word & BIT["SR"]), bus=bus, pc=m.pc, mar=m.mar, ir=m.ir, a=m.a, b=m.b,
                         c=m.c, z=m.z, out=m.out))
    return rows


def run(mem, in0=0, in1=0, limit=200000):
    return PC2Plus(image(mem) if isinstance(mem, dict) else mem, in0, in1).run(limit)


def display(value, mode):
    if mode == 0: return f"{value:>4d}"
    if mode == 1: return f"{value - 256 if value > 127 else value:>4d}"
    if mode == 2: return f"  {value:02X}"
    return "    "


# ------------------------------------------------------------------ the chapter's programs
PROGRAMS = {
    "ECHO": ["IN 0", "OUT 0", "HALT"],
    "ADD": ["IN 0", "STORE x", "IN 1", "ADD x", "JC over", "OUT 0", "over: HALT",
            "x: data 0"],
    "BIGGER": ["IN 1", "STORE b", "IN 0", "STORE a", "SUB b", "JC showa", "LOAD b", "JUMP show",
               "showa: LOAD a", "show: OUT 0", "HALT",
               "a: data 0", "b: data 0"],
    "MULTIPLY": ["IN 0", "STORE x", "IN 1", "STORE y", "LDI 0", "STORE p",
                 "loop: LOAD y", "SBI 1", "JC more", "LOAD p", "OUT 0", "HALT",
                 "more: STORE y", "LOAD p", "ADD x", "JC over", "STORE p", "JUMP loop",
                 "over: HALT",
                 "x: data 0", "y: data 0", "p: data 0"],
    "SUMLIST": ["LDI list", "STORE get+1", "LDI 0", "STORE sum",
                "loop: LOAD count", "SBI 1", "JC more", "LOAD sum", "OUT 0", "HALT",
                "more: STORE count", "LOAD sum",
                "get: ADD 0", "JC over", "STORE sum",
                "LOAD get+1", "ADI 1", "STORE get+1", "JUMP loop",
                "over: HALT",
                "sum: data 0",
                "org 0x7F", "count: data 0", "list:"],
    "FIBONACCI": ["LDI 1", "STORE a", "LDI 0", "STORE b",
                  "loop: LOAD a", "OUT 0", "ADD b", "JC done", "STORE t",
                  "LOAD a", "STORE b", "LOAD t", "STORE a", "JUMP loop",
                  "done: HALT",
                  "a: data 0", "b: data 0", "t: data 0"],
}
COUNT, LIST = 0x7F, 0x80       # SUMLIST: the count at hex 7F, the list from hex 80


def assemble(name):
    return asm(PROGRAMS[name])


def code_size(mem, labels):
    """Bytes of instructions (everything before the first data label)."""
    data = [labels[k] for k in labels if k in ("x", "y", "p", "a", "b", "t", "sum")]
    return min(data) if data else len(mem)


def prove(verbose=True):
    import random
    rnd = random.Random(13)
    rep = {}

    mem, lab = assemble("ECHO"); mx = 0
    for a in range(256):
        m = run(mem, a); assert m.out == a and m.shown == [a]; mx = max(mx, m.cycles)
    rep["ECHO"] = (len(mem), mx, "all 256 inputs")

    mem, lab = assemble("ADD"); mx = 0
    for a in range(256):
        for b in range(256):
            m = run(mem, a, b)
            if a + b <= 255: assert m.out == a + b and m.c == 0
            else: assert m.out is None and m.c == 1
            mx = max(mx, m.cycles)
    rep["ADD"] = (lab["x"], mx, "all 65 536 input pairs")

    mem, lab = assemble("BIGGER"); mx = 0
    for a in range(256):
        for b in range(256):
            m = run(mem, a, b); assert m.out == max(a, b); mx = max(mx, m.cycles)
    rep["BIGGER"] = (lab["a"], mx, "all 65 536 input pairs")

    mem, lab = assemble("MULTIPLY"); mx = 0
    for a in range(256):
        for b in range(256):
            m = run(mem, a, b)
            if a * b <= 255: assert m.out == a * b and m.shown == [a * b]
            else: assert m.out is None and m.c == 1        # carry LED: product too big
            mx = max(mx, m.cycles)
    rep["MULTIPLY"] = (lab["x"], mx, "all 65 536 input pairs")

    mem, lab = assemble("SUMLIST"); mx = 0; n = 0
    for trial in range(3000):
        k = rnd.randrange(0, 128 if trial % 3 else 12)
        top = rnd.choice([3, 20, 255])
        xs = [rnd.randrange(0, top + 1) for _ in range(k)]
        img = image(mem); img[COUNT] = k
        for i, x in enumerate(xs):
            img[LIST + i] = x
        m = run(img)
        if sum(xs) <= 255: assert m.out == sum(xs), (xs, m.out)
        else: assert m.out is None and m.c == 1
        m2 = PC2Plus(m.mem); m2.mem[COUNT] = k; m2.run()     # runs again without reloading
        assert m2.out == m.out
        mx = max(mx, m.cycles); n += 1
    rep["SUMLIST"] = (lab["sum"], mx, f"{n} random lists of 0-127 numbers")

    mem, lab = assemble("FIBONACCI")
    m = run(mem)
    assert m.shown == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
    rep["FIBONACCI"] = (lab["a"], m.cycles, "shows 1 1 2 3 5 8 13 21 34 55 89 144 233")
    if verbose:
        for k, (sz, cy, how) in rep.items():
            print(f"{k:<10} {sz:>3} bytes of code  max {cy:>6} cycles  proven: {how}")
        return None      # the table is printed; nothing more for the Code tab to echo
    return rep


if __name__ == "__main__":
    prove()
