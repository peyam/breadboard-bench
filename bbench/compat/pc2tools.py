"""pc2tools: the book's helpers for writing about PC-2 programs (listings, traces and the
microcode in words), as in the book's companion folder tools/pc2kit/pc2tools.py, on top of
the engine's copy of the PC-2 emulator (bbench.projects.pc2_emulator).

    from pc2tools import listing, trace, run, NAMES      # in the app's Code tab, or
    from bbench.compat.pc2tools import listing, trace    # anywhere bbench is installed
    rows = listing(["IN 0", "OUT 0", "HALT"])           # address, byte, binary, instruction, meaning
    t = trace(code, in0=9, in1=200, max_cycles=60)       # one row per clock cycle
"""
from ..projects.pc2_emulator import PC2, asm, ROM, BIT, SIGNALS, OPS, NAMES, CODES, FETCH, display  # noqa: F401


MEANING = {
    "HALT": "stop the clock", "LOAD": "A = memory[{a}]", "STORE": "memory[{a}] = A",
    "ADD": "A = A + memory[{a}]; set carry and zero", "SUB": "A = A - memory[{a}]; set carry and zero",
    "JUMP": "go to address {a}", "JC": "if carry = 1, go to address {a}", "OUT": "show A on the display (mode {a})",
    "LDI": "A = {a}", "ADI": "A = A + {a}; set carry and zero", "SBI": "A = A - {a}; set carry and zero",
    "JZ": "if zero = 1, go to address {a}", "IN": "A = input switches {bank}", "NOP": "do nothing",
    "USR1": "your own instruction", "USR2": "your own instruction",
}


def disasm(byte):
    op, a = byte >> 4, byte & 15
    name = NAMES[op]
    if name in ("HALT", "NOP", "USR1", "USR2"):
        return name
    return f"{name} {a}"


def listing(lines, data=None):
    code = asm(lines) if lines and isinstance(lines[0], str) else list(lines)
    rows = []
    for addr, b in enumerate(code):
        ins = disasm(b)
        name = ins.split()[0]
        a = b & 15
        m = MEANING[name].format(a=a, bank="A" if a % 2 == 0 else "B")
        rows.append((addr, f"{b:02X}", f"{b >> 4:04b} {b & 15:04b}", ins, m))
    for addr, v in sorted((data or {}).items()):
        rows.append((addr, f"{v:02X}", f"{v >> 4:04b} {v & 15:04b}", f"data {v}", "a value, not an instruction"))
    return rows


def control_names(word):
    return [s for s in SIGNALS if s and word & BIT[s]]


def trace(code, in0=0, in1=0, data=None, max_cycles=200):
    """Run cycle by cycle; each row: cycle, step, PC (after), instruction register, active lines,
    bus value, A, B, carry, zero, display. Steps are T0, T1, ... as in the book."""
    mem = list(code) + [0] * (16 - len(code))
    for k, v in (data or {}).items():
        mem[k] = v
    m = PC2(mem, in0=in0, in1=in1)
    rows, step, cyc = [], 0, 0
    while not m.halted and cyc < max_cycles:
        op = m.ir >> 4
        word = ROM[(m.c << 8) | (m.z << 7) | (op << 3) | step]
        lines = control_names(word)
        # compute the bus value the way the emulator does
        e, ec, ez = m.alu("SU" in lines)
        bus = None
        for s, f in (("RO", lambda: m.mem[m.mar]), ("IO", lambda: m.ir & 15), ("AO", lambda: m.a),
                     ("EO", lambda: e), ("CO", lambda: m.pc), ("XO", lambda: m.inp[m.ir & 1])):
            if s in lines:
                bus = f()
        before = dict(pc=m.pc, ir=m.ir)
        # advance exactly one cycle
        m2_cycles = m.cycles
        _step_once(m, step)
        cyc += 1
        rows.append(dict(cycle=cyc, step=f"T{step}", lines=[l for l in lines if l != "SR"], sr="SR" in lines,
                         bus=bus, pc=m.pc, ir=disasm(m.ir), a=m.a, b=m.b, c=m.c, z=m.z, mar=m.mar,
                         out=m.out))
        step = 0 if "SR" in lines or m.halted else step + 1
    return rows


def _step_once(m, step):
    op = m.ir >> 4
    word = ROM[(m.c << 8) | (m.z << 7) | (op << 3) | step]
    on = lambda s: bool(word & BIT[s])
    e, ec, ez = m.alu(on("SU"))
    bus = 0
    for s, f in (("RO", lambda: m.mem[m.mar]), ("IO", lambda: m.ir & 15), ("AO", lambda: m.a),
                 ("EO", lambda: e), ("CO", lambda: m.pc), ("XO", lambda: m.inp[m.ir & 1])):
        if on(s):
            bus = f()
    if on("HLT"): m.halted = True
    if on("MI"): m.mar = bus & 15
    if on("RI"): m.mem[m.mar] = bus
    if on("II"): m.ir = bus
    if on("AI"): m.a = bus
    if on("BI"): m.b = bus
    if on("OI"):
        m.out, m.mode = bus, m.ir & 3
        m.shown.append(bus)
    if on("FI"): m.c, m.z = ec, ez
    if on("J"): m.pc = bus & 15
    if on("CE"): m.pc = (m.pc + 1) & 15
    m.cycles += 1


def run(code, in0=0, in1=0, data=None, limit=100000):
    mem = list(code) + [0] * (16 - len(code))
    for k, v in (data or {}).items():
        mem[k] = v
    return PC2(mem, in0=in0, in1=in1).run(limit=limit)
