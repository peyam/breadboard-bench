"""Test bench: operate the simulated PC-2 the way a reader operates the real one."""
from pc2_netlist import build
from sim import Sim


class Bench:
    def __init__(self, N=None):
        self.N = N or build()
        self.sim = Sim(self.N)
        self.note = {}
        for p in self.N.parts.values():
            if p.note:
                self.note.setdefault(p.note, p)
        self.u = self.N.chips
        # defaults: STEP mode, RUN (not program), buttons released, clocks low
        self.spdt("RUN / STEP", "STEP")
        self.spdt("PROGRAM / RUN", "RUN")
        self.u["U3"].model.state = 0
        self.u["U1"].model.state = 0
        self.u["U2"].model.state = 0
        self.u["U36"].model.state = 0
        self.N.parts[self.note["speed range jumper"].ref].pos = "FAST"
        self.sim.step()
        self.rises = 0
        self.shown = []

    # controls ---------------------------------------------------------------
    def spdt(self, label, pos):
        self.note[label].pos = pos

    def switch(self, label, closed):
        self.note[label].closed = bool(closed)

    def press(self, label):
        self.switch(label, True)
        self.sim.step()
        self.switch(label, False)
        self.sim.step()

    def set_bits(self, fmt, value, n=8):
        for k in range(n):
            self.switch(fmt.format(k), (value >> k) & 1)

    def reset(self):
        self.press("RESET")

    # program mode -------------------------------------------------------------
    def load(self, mem):
        self.spdt("PROGRAM / RUN", "PROG")
        self.sim.step()
        for addr, val in enumerate(mem):
            self.set_bits("address switch {}", addr, 4)
            self.set_bits("data switch {}", val, 8)
            self.sim.step()
            self.press("WRITE")
        # read every byte back on the RAM data LEDs (RAM output enabled in program mode)
        back = []
        for addr in range(len(mem)):
            self.set_bits("address switch {}", addr, 4)
            self.sim.step()
            back.append(self.sim.word("RD", 8))
        self.spdt("PROGRAM / RUN", "RUN")
        self.sim.step()
        return back

    # clock --------------------------------------------------------------------
    def half(self, raw):
        self.u["U1"].model.state = raw
        before = self.sim.v("CLK")
        oi = self.sim.v("OI_n")
        self.sim.step()
        if before == 0 and self.sim.v("CLK") == 1:
            self.rises += 1
            if oi == 0:
                self.shown.append(self.sim.word("OUT", 8))

    def run(self, limit=20000):
        self.u["U3"].model.state = 1          # RUN selected (bistable output high)
        self.sim.step()
        while self.sim.v("HLT_n") == 1:
            if self.rises >= limit:
                return False
            self.half(1)
            self.half(0)
        return True

    def single_step(self):
        self.u["U3"].model.state = 0
        self.u["U2"].model.state = 1
        before = self.sim.v("CLK")
        oi = self.sim.v("OI_n")
        self.sim.step()
        if before == 0 and self.sim.v("CLK") == 1:
            self.rises += 1
            if oi == 0:
                self.shown.append(self.sim.word("OUT", 8))
        self.u["U2"].model.state = 0
        self.sim.step()

    # display ---------------------------------------------------------------------
    SEGS = {0x3F: "0", 0x06: "1", 0x5B: "2", 0x4F: "3", 0x66: "4", 0x6D: "5", 0x7D: "6", 0x07: "7",
            0x7F: "8", 0x6F: "9", 0x77: "A", 0x7C: "B", 0x39: "C", 0x5E: "D", 0x79: "E", 0x71: "F",
            0x40: "-", 0x00: " "}

    def display(self):
        """Scan the four digits and read the lit segments, as the eye would."""
        chars = {}
        for _ in range(8):
            s = self.u["U36"].model
            s.state ^= 1
            self.sim.step()
            on = [d for d in range(4) if self.sim.v(f"DSEL{d}_n") == 0]
            assert len(on) == 1, on
            pattern = sum((1 - self.sim.v(f"SEG{k}")) << k for k in range(8))
            chars[on[0]] = self.SEGS.get(pattern, "?")
        return "".join(chars[d] for d in (3, 2, 1, 0))
