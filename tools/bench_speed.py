"""Measure PC-2 simulation speed: clock cycles per second (CPU time).
    python tools/bench_speed.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from bbench.projects.pc2 import Panel  # noqa: E402
from bbench.projects.pc2_programs import PROGRAMS  # noqa: E402


def measure(mode, prog="MULTIPLY", reps=1):
    p = Panel(mode=mode)
    p.load(PROGRAMS[prog]["mem"])
    p.reset()
    s = p.sim
    if mode == "timed":
        s.set("RUN / STEP", "RUN")
        t = time.process_time()
        r = s.run("halt", limit=5000)
        dt = time.process_time() - t
        return r["cycles"], dt, s.t_ns
    t = time.process_time()
    p.run(5000)
    dt = time.process_time() - t
    return p.rises, dt, None


if __name__ == "__main__":
    for mode in ("zero", "timed"):
        cyc, dt, tns = measure(mode)
        extra = f", {tns / 1e3:.0f} us simulated" if tns else ""
        print(f"{mode:6} MULTIPLY 7x6: {cyc} cycles in {dt:.2f} s CPU = {cyc / dt:.0f} cycles/s{extra}")
