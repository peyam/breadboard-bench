"""Full chip-level proof of PC-2 (every case of pc2sim/test_hw.py) on the Breadboard
Bench engine. --api runs it through the new public API (bbench.projects.pc2 Panel,
real 555 debouncer/monostable models) instead of the old Bench.

    python tools/prove_pc2.py [--api] [--quick]
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from bbench.projects import pc2_emulator as pc2            # noqa: E402
from bbench.projects.pc2_programs import P, MUL, DIV, FIB, with_data  # noqa: E402
from bbench.projects.pc2_roms import display_text        # noqa: E402


def cases(quick=False):
    random.seed(2026)
    edge = [0, 1, 2, 127, 128, 254, 255]
    pairs = [(a, b) for a in edge for b in edge] + [(random.randrange(256), random.randrange(256)) for _ in range(40)]
    out = []
    echo = range(256) if not quick else [0, 1, 42, 127, 128, 200, 255]
    out += [("ECHO", P["ECHO"], a, 0) for a in echo]
    cd = [0, 1, 2, 9, 10, 99, 100, 127, 128, 200, 255] if not quick else [0, 3, 128]
    out += [("COUNTDOWN", P["COUNTDOWN"], a, 0) for a in cd]
    pp = pairs if not quick else [(0, 0), (255, 1), (9, 200), (200, 9), (127, 128), (100, 100)]
    out += [("ADD", P["ADD"], a, b) for a, b in pp]
    out += [("BIGGER", P["BIGGER"], a, b) for a, b in pp]
    mul = [(0, 0), (0, 9), (9, 0), (1, 1), (7, 6), (15, 17), (16, 15), (255, 1), (1, 255), (3, 85), (85, 3)]
    if quick:
        mul = [(7, 6), (3, 85)]
    out += [("MULTIPLY", with_data(MUL, {13: 0, 14: y, 15: x}), 0, 0) for x, y in mul]
    dv = [(7, 2), (0, 1), (255, 1), (255, 255), (254, 255), (100, 7), (13, 13), (200, 3)]
    if quick:
        dv = [(100, 7), (13, 13)]
    out += [("DIVIDE", with_data(DIV, {13: 0, 14: d, 15: n}), 0, 0) for n, d in dv]
    out += [("FIBONACCI", with_data(FIB, {13: 0, 14: 1, 15: 0}), 0, 0)]
    for mode in (1, 2, 3):
        prog = pc2.asm(["IN 1", f"OUT {mode}", "HALT"])
        vals = (0, 5, 127, 128, 200, 255) if not quick else (128, 200)
        out += [(f"OUT {mode}", prog, 0, v) for v in vals]
    return out


def expect(mem, in0, in1, limit=20000):
    em = pc2.PC2(mem, in0=in0, in1=in1).run(limit=limit * 2)
    want = dict(shown=em.shown, A=em.a, C=em.c, Z=em.z, PC=em.pc, mem=em.mem, cycles=em.cycles)
    disp = display_text(em.out, em.mode) if em.out is not None else "   0"
    return want, disp


def run_old(mem, in0, in1, limit=20000):
    from bbench.compat.pc2sim import Bench
    b = Bench()
    back = b.load(mem)
    b.set_bits("input A switch {}", in0)
    b.set_bits("input B switch {}", in1)
    b.reset()
    halted = b.run(limit)
    s = b.sim
    hw = dict(shown=b.shown, A=s.word("A", 8), C=s.v("FC"), Z=s.v("FZ"), PC=s.word("PC", 4),
              mem=[s.N.chips["U24"].model.state.get(i, 0) for i in range(16)], cycles=b.rises + 1)
    return back, halted, hw, b.display(), list(s.errors), sorted(s.contention)


_panel = {}


def run_api(mem, in0, in1, limit=20000):
    from bbench.projects.pc2 import Panel
    p = _panel.get("p")
    if p is None:
        p = _panel["p"] = Panel()
    else:
        p.power_cycle()
    back = p.load(mem)
    p.set_inputs(in0, in1)
    p.reset()
    halted = p.run(limit)
    s = p.sim
    hw = dict(shown=p.shown, A=s.word("A", 8), C=s.v("FC"), Z=s.v("FZ"), PC=s.word("PC", 4),
              mem=s.N.parts["U24"].dump(0, 16), cycles=p.rises + 1)
    errs = [e["message"] for e in s.errors if e["severity"] == "error"]
    return back, halted, hw, p.display(), errs, sorted(s.contention)


def check(name, mem, in0, in1, runner):
    mem = list(mem) + [0] * (16 - len(mem))
    want, want_disp = expect(mem, in0, in1)
    back, halted, hw, disp, errs, cont = runner(mem, in0, in1)
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
    if errs:
        problems.append("errors: " + "; ".join(errs[:3]))
    if cont:
        problems.append("contention: " + str(cont[:3]))
    return problems


def main(argv):
    runner = run_api if "--api" in argv else run_old
    t0 = time.time()
    fails = []
    cs = cases("--quick" in argv)
    for name, mem, a, b in cs:
        pr = check(name, mem, a, b, runner)
        if pr:
            fails.append((name, a, b, pr))
    print(f"{len(cs)} runs, {len(fails)} failures, {time.time() - t0:.1f} s")
    for f in fails[:20]:
        print(f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
