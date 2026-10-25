"""Prove the chip-level PC-2 against the microcode emulator, program by program.

For each run: load the program through the PROGRAM switches and WRITE button, read it
back from the RAM LEDs, press RESET, run until HALT stops the clock, then compare every
displayed value, A, flags, PC and all 16 RAM bytes with the emulator, and read the
4-digit display segment by segment.
"""
import random
import sys
import time

sys.path.insert(0, "..")
import pc2                                   # noqa: E402
from prove import P, MUL, DIV, FIB, with_data   # noqa: E402
from bench import Bench                       # noqa: E402
from roms import display_text                 # noqa: E402

random.seed(2026)
results = []
fails = []


def run_case(name, mem, in0=0, in1=0, limit=20000):
    mem = list(mem) + [0] * (16 - len(mem))
    em = pc2.PC2(mem, in0=in0, in1=in1).run(limit=limit * 2)
    b = Bench()
    back = b.load(mem)
    b.set_bits("input A switch {}", in0)
    b.set_bits("input B switch {}", in1)
    b.reset()
    halted = b.run(limit)
    s = b.sim
    hw = dict(shown=b.shown, A=s.word("A", 8), C=s.v("FC"), Z=s.v("FZ"), PC=s.word("PC", 4),
              mem=[s.N.chips["U24"].model.state.get(i, 0) for i in range(16)], cycles=b.rises + 1)
    want = dict(shown=em.shown, A=em.a, C=em.c, Z=em.z, PC=em.pc, mem=em.mem, cycles=em.cycles)
    disp = b.display()
    want_disp = display_text(em.out, em.mode) if em.out is not None else "   0"
    problems = []
    if back != mem:
        problems.append(f"read-back {back} != {mem}")
    if not halted:
        problems.append("did not halt")
    for k in want:
        if hw[k] != want[k]:
            problems.append(f"{k}: hw {hw[k]} emulator {want[k]}")
    if disp != want_disp:
        problems.append(f"display {disp!r} != {want_disp!r}")
    if s.errors:
        problems.append("errors: " + "; ".join(s.errors[:3]))
    if s.contention:
        problems.append("contention: " + str(sorted(s.contention)[:3]))
    if problems:
        fails.append((name, in0, in1, problems))
    return hw["cycles"]


def suite(name, mem, cases):
    t = time.time()
    mx = 0
    for a, b in cases:
        mx = max(mx, run_case(name, mem, a, b))
    results.append(f"{name:<12} {len(cases):>4} runs  max {mx:>5} cycles  {time.time() - t:6.1f} s")


edge = [0, 1, 2, 127, 128, 254, 255]
pairs = [(a, b) for a in edge for b in edge] + [(random.randrange(256), random.randrange(256)) for _ in range(40)]

suite("ECHO", P["ECHO"], [(a, 0) for a in range(256)])
suite("COUNTDOWN", P["COUNTDOWN"], [(a, 0) for a in [0, 1, 2, 9, 10, 99, 100, 127, 128, 200, 255]])
suite("ADD", P["ADD"], pairs)
suite("BIGGER", P["BIGGER"], pairs)

mul_cases = []
for x, y in [(0, 0), (0, 9), (9, 0), (1, 1), (7, 6), (15, 17), (16, 15), (255, 1), (1, 255), (3, 85), (85, 3)]:
    mul_cases.append(with_data(MUL, {13: 0, 14: y, 15: x}))
t = time.time()
for m in mul_cases:
    run_case("MULTIPLY", m)
results.append(f"{'MULTIPLY':<12} {len(mul_cases):>4} runs  {time.time() - t:6.1f} s")

t = time.time()
for n, d in [(7, 2), (0, 1), (255, 1), (255, 255), (254, 255), (100, 7), (13, 13), (200, 3)]:
    run_case("DIVIDE", with_data(DIV, {13: 0, 14: d, 15: n}))
results.append(f"{'DIVIDE':<12}    8 runs  {time.time() - t:6.1f} s")

run_case("FIBONACCI", with_data(FIB, {13: 0, 14: 1, 15: 0}))
results.append("FIBONACCI       1 run")

# display modes: OUT 1 (signed) and OUT 2 (hex), and IN 1 (bank B)
for mode in (1, 2, 3):
    prog = pc2.asm(["IN 1", f"OUT {mode}", "HALT"])
    for v in (0, 5, 127, 128, 200, 255):
        run_case(f"OUT {mode}", prog, 0, v)
results.append("OUT modes 1-3, IN 1: 18 runs")

# single-step mode gives the same result as run mode
b = Bench()
b.load(P["BIGGER"])
b.set_bits("input A switch {}", 9)
b.set_bits("input B switch {}", 200)
b.reset()
n = 0
while b.sim.v("HLT_n") == 1 and n < 200:
    b.single_step()
    n += 1
ok = b.shown == [200] and b.display() == " 200"
results.append(f"single-step BIGGER(9,200): {'ok' if ok else 'FAIL'} in {n} presses")
if not ok:
    fails.append(("single-step", 9, 200, [str(b.shown)]))

print("\n".join(results))
print(f"\nFAILURES: {len(fails)}")
for f in fails[:20]:
    print(f)
