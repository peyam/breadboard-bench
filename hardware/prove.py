"""Prove every PC-2 starter program for every input, and report sizes and cycle counts."""
from pc2 import PC2, asm, rom_images, display, NAMES, OPS

P = {}
P["ECHO"] = asm(["IN 0", "OUT 0", "HALT"])
P["COUNTDOWN"] = asm(["IN 0", "OUT 0", "SBI 1", "JC 1", "HALT"])
P["BIGGER"] = asm(["IN 1", "STORE 15", "IN 0", "STORE 14", "SUB 15", "JC 8",
                   "LOAD 15", "JUMP 9", "LOAD 14", "OUT 0", "HALT"])
P["ADD"] = asm(["IN 0", "STORE 15", "IN 1", "ADD 15", "JC 6", "OUT 0", "HALT"])

def with_data(code, data):
    m = code + [0] * (16 - len(code))
    for addr, v in data.items():
        assert addr >= len(code), "data overlaps code"
        m[addr] = v
    return m

MUL = asm(["LOAD 14", "SBI 1", "JC 6", "LOAD 13", "OUT 0", "HALT",
           "STORE 14", "LOAD 13", "ADD 15", "STORE 13", "JUMP 0"])
DIV = asm(["LOAD 15", "SUB 14", "JC 6", "LOAD 13", "OUT 0", "HALT",
           "STORE 15", "LOAD 13", "ADI 1", "STORE 13", "JUMP 0"])
FIB = asm(["LOAD 14", "OUT 0", "ADD 15", "JC 10", "STORE 13", "LOAD 14",
           "STORE 15", "LOAD 13", "STORE 14", "JUMP 0", "HALT"])

report = []
def ok(name, n, cyc):
    report.append(f"{name:<10} {n:>2} bytes  proven  (max {cyc} clock cycles)")

mx = 0
for a in range(256):
    m = PC2(P["ECHO"], in0=a).run(); assert m.out == a; mx = max(mx, m.cycles)
ok("ECHO", len(P["ECHO"]), mx)

mx = 0
for a in range(256):
    m = PC2(P["COUNTDOWN"], in0=a).run(limit=20000)
    assert m.shown == list(range(a, -1, -1)); mx = max(mx, m.cycles)
ok("COUNTDOWN", len(P["COUNTDOWN"]), mx)

mx = 0
for a in range(256):
    for b in range(256):
        m = PC2(P["BIGGER"], in0=a, in1=b).run(); assert m.out == max(a, b); mx = max(mx, m.cycles)
ok("BIGGER", len(P["BIGGER"]), mx)

mx = 0
for a in range(256):
    for b in range(256):
        m = PC2(P["ADD"], in0=a, in1=b).run()
        if a + b <= 255: assert m.out == a + b and m.c == 0
        else:            assert m.out is None and m.c == 1   # carry LED = overflow
        mx = max(mx, m.cycles)
ok("ADD", len(P["ADD"]), mx)

mx = 0
for x in range(256):
    for y in range(256):
        if x * y > 255: continue
        m = PC2(with_data(MUL, {13: 0, 14: y, 15: x})).run(limit=20000)
        assert m.out == x * y; mx = max(mx, m.cycles)
ok("MULTIPLY", len(MUL), mx)

mx = 0
for n in range(256):
    for d in range(1, 256):
        m = PC2(with_data(DIV, {13: 0, 14: d, 15: n})).run(limit=200000)
        assert m.out == n // d and m.mem[15] == n % d; mx = max(mx, m.cycles)
ok("DIVIDE", len(DIV), mx)
# divide by zero must never halt
try:
    PC2(with_data(DIV, {13: 0, 14: 0, 15: 7})).run(limit=100000); raise SystemExit("DIV/0 halted!")
except AssertionError:
    report.append("DIVIDE     by zero never halts (as intended for the lesson)")

m = PC2(with_data(FIB, {13: 0, 14: 1, 15: 0})).run()
assert m.shown == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
ok("FIBONACCI", len(FIB), m.cycles)
report.append("FIBONACCI  shows " + " ".join(map(str, m.shown)) + ", then halts on overflow")

assert display(200, 1) == " -56" and display(200, 2) == "  C8"

imgs = rom_images()
report.append(f"Microcode: 3 x 512 bytes used (of {len(imgs[0])} built); longest instruction "
              f"{max(2 + len(s) for _, s in OPS.values() if s)} steps")
print("\n".join(report))
for name, code in [("MULTIPLY", MUL), ("DIVIDE", DIV), ("FIBONACCI", FIB)] + list(P.items()):
    print(name, " ".join(f"{b:02X}" for b in code))
