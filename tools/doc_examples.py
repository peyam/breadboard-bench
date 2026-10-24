"""The examples in docs/engine.md; run this to check their output."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

print("# 1")
import bbench
p = bbench.projects.example("xor-from-nand")
print(p.name, "-", len(p.data["parts"]), "parts,", len(p.data["nets"]), "nets")
print(p.check())
sim = p.simulator(mode="zero")
for a in (0, 1):
    for b in (0, 1):
        sim.drive("SA", a)
        sim.drive("SB", b)
        sim.update()
        print(a, b, "->", sim.v("XOR"), "LED lit:", sim.state()["leds"]["D1"])

print("# 2")
p = bbench.projects.pc2()
print(len(p.data["parts"]), "parts,", len(p.data["breadboards"]), "breadboards,", len(p.data["links"]), "links")
print(p.check())
sim = p.simulator("zero")
sim.set("PROGRAM / RUN", "PROG")
for addr, byte in enumerate([0xC0, 0x70, 0x00]):      # ECHO: IN 0, OUT 0, HALT
    sim.set("S1", addr)                                # address switches
    sim.set("S2", byte)                                # data switches
    sim.press("WRITE")
sim.set("PROGRAM / RUN", "RUN")
sim.set("S3", 42)                                      # input bank A
sim.press("RESET")
sim.set("RUN / STEP", "RUN")
print(sim.run(until="halt", limit=1000))
st = sim.state()
print("OUT =", sim.word("OUT", 8), " digits:", st["digits"])
print("errors:", st["errors"])

print("# 3")
from bbench.projects.pc2 import Panel
panel = Panel()
panel.load(bbench.projects.pc2_programs.PROGRAMS["FIBONACCI"]["mem"])
panel.reset()
panel.run()
print(panel.shown, repr(panel.display()))

print("# 4")
p = bbench.projects.example("555-clock")
t = p.simulator("timed")
print(round(t.stimuli[0]["period_ns"] / 1e6, 2), "ms period")
t.run_ns(2e9)
print(t.trace(["CLK"]))

print("# 5")
from bbench.core.netlist import Netlist
N = Netlist()
N.add("U1", "74HC04")
N.add("S1", "SW")
N.add("R1", "R", {"value": "10k"})
N.connect("VCC", "U1", 14); N.connect("GND", "U1", 7)
N.connect("VCC", "S1", 1); N.connect("N0", "S1", 2)
N.connect("N0", "R1", 1); N.connect("GND", "R1", 2)
for k in range(1, 7):
    N.connect(f"N{k - 1}", "U1", f"{k}A")
    N.connect(f"N{k}", "U1", f"{k}Y")
t = bbench.TimedSim(N)
t.run_ns(100)
t.set("S1", True)
t.run_ns(500)
print(t.trace(["N0", "N1", "N6"]))
print(t.to_vcd(["N0", "N6"]))

print("# 6")
import copy
from bbench.board.checker import check_boards
d = copy.deepcopy(bbench.projects.example("nand-gate").data)
d["breadboards"][0]["wires"].pop(0)
for prob in check_boards(d):
    print(prob["severity"], prob["kind"], prob["message"])

print("# 7")
print(bbench.library()[0])
print(bbench.projects.catalogue()[:3])

print("# 8")
from bbench.compat.pc2sim import Bench
b = Bench()
b.load([0xC0, 0x70, 0x00])
b.set_bits("input A switch {}", 200)
b.reset()
b.run()
print("display:", repr(b.display()))
