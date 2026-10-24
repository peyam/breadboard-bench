"""Timers. The NE555 is behavioural: its analogue timing is worked out from the
resistors and capacitors around it, not simulated.

Modes (prop "mode", default "auto": found from the wiring when the simulator starts)
- astable     THR and TRIG on one net: a free-running clock. The zero-delay simulator
              drives it as a clock source; the timed one runs it at
              t_high = 0.693 (R1 + R2) C, t_low = 0.693 R2 C.
- monostable  THR and DIS on one net: TRIG low starts a pulse of 1.1 R C. In the
              zero-delay simulator the pulse lasts while TRIG is held low.
- bistable    THR to GND: TRIG low sets OUT high, RESET low sets it low (a debouncer).
- manual      OUT simply shows self.state (set by a test bench).
"""
from .base import Chip, pins, register, soft

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"


@register
class NE555(Chip):
    TYPE, DESC, FAMILY = "NE555", "Timer (astable, monostable or bistable)", "timer"
    PINS = pins("1:GND:gnd 2:TRIG:ana 3:OUT:out 4:RESET:ana 5:CTRL:ana 6:THR:ana 7:DIS:ana 8:VCC:vcc")
    TPD = {("*", "OUT"): 100}
    DATASHEET = TI.format("ne555")
    # TI NE555 at VCC = 5 V: VOH 2.75 V min (3.3 V typ) at IOH = -100 mA, VOL 0.25 V max at
    # IOL = 8 mA. The inputs are analogue (comparators at 1/3 and 2/3 VCC): no logic level.
    VOH, VOL = 2.75, 0.25
    MODES = ("auto", "astable", "monostable", "bistable", "manual")

    def __init__(self, ref="U?", mode="auto", **props):
        super().__init__(ref, **props)
        if mode not in self.MODES:
            raise ValueError(f"{ref}: unknown 555 mode {mode!r}")
        self.mode = mode
        self.timing = {}            # {"high_ns", "low_ns"} or {"width_ns"}
        self.timed = False          # set by the timed simulator
        self.wake_ns = None

    def reset_state(self):
        return 0

    # ------------------------------------------------------------ wiring analysis
    def configure(self, ctx):
        thr, trg, dis = ctx.pin_net("THR"), ctx.pin_net("TRIG"), ctx.pin_net("DIS")
        if self.mode == "auto":
            if thr and thr == trg and dis and dis != thr:
                self.mode = "astable"
            elif thr and thr == dis and trg and trg != thr:
                self.mode = "monostable"
            elif trg and (thr is None or thr == "GND"):
                self.mode = "bistable"
            else:
                self.mode = "manual"
        self.timing = {}
        if self.mode == "astable" and dis and thr:
            r1 = ctx.resistance("VCC", dis)
            r2 = ctx.resistance(dis, thr)
            c = ctx.capacitance(thr, "GND")
            if r1 and r2 is not None and c:
                self.timing = {"high_ns": 0.693 * (r1 + r2) * c * 1e9, "low_ns": 0.693 * r2 * c * 1e9}
        elif self.mode == "monostable" and thr:
            r = ctx.resistance("VCC", thr)
            c = ctx.capacitance(thr, "GND")
            if r and c:
                self.timing = {"width_ns": 1.1 * r * c * 1e9}

    def period_ns(self):
        t = self.timing
        if "high_ns" in t:
            return t["high_ns"] + t["low_ns"]
        return None

    # ------------------------------------------------------------ behaviour
    def eval(self, g):
        if self.mode != "manual" and soft(g, "RESET") == 0:
            return {"OUT": 0}
        return {"OUT": self.state}

    def asyncupd(self, g):
        m = self.mode
        new = self.state
        if m == "bistable":
            r, t, th = soft(g, "RESET"), soft(g, "TRIG"), soft(g, "THR")
            if r == 0:
                new = 0
            elif t == 0:
                new = 1
            elif th == 1:
                new = 0
        elif m == "monostable":
            r, t = soft(g, "RESET"), soft(g, "TRIG")
            if r == 0:
                new = 0
            elif t == 0 and self.state == 0:
                new = 1
                if self.timed:
                    self.wake_ns = self.timing.get("width_ns", 100e6)
            elif t == 1 and self.state == 1 and not self.timed:
                new = 0
        if new != self.state:
            self.state = new
            return True
        return False

    def restored(self):
        """Started from a snapshot (another simulator's state): a monostable pulse that is
        on carries on for its full width in the timed simulator."""
        if self.timed and self.mode == "monostable" and self.state == 1:
            self.wake_ns = self.timing.get("width_ns", 100e6)

    def wakeup(self, g):
        """End of the monostable pulse (timed simulator)."""
        if self.state == 1:
            if soft(g, "TRIG") == 0:          # trigger still held: OUT stays high
                self.wake_ns = 1000.0
                return False
            self.state = 0
            return True
        return False
