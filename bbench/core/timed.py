"""Timed simulator: discrete events in integer picoseconds.

When a chip input changes at time t the chip is re-evaluated and each output that
changes is scheduled at t + TPD(input -> output) (inertial delay: a newer evaluation
of the same output cancels a pending change, so pulses shorter than the delay are
swallowed). Clock sources (CLOCK parts, astable 555s, project stimuli) are scheduled
square waves. Clocked chips sample their inputs as they were just before the edge;
an input that changed less than SETUP before the edge, or changes less than HOLD
after it, is a setup or hold violation. Every net change is recorded.

Short overlaps are normal in real logic, so contention is reported only when two
drivers fight for longer than contention_grace_ns (default 10 ns), and a floating
input only when it stays floating for longer than float_grace_ns (default 1000 ns).

Unknown values. A memory's data outputs are unknown ("X") from its output hold time
(ADDR_HOLD, tOH) after a change on an address pin (A0, A1, ...) until its access time: the AT28C256 promises
nothing about them for up to 150 ns, and they may glitch. An unknown input reaches the
outputs it can affect: a chip with unknown inputs is evaluated with every 0/1 value of
them, and an output whose value depends on them is unknown. So a control line from a
ROM can briefly enable a bus driver. A fight in which at most one driver is known
(the others unknown) is reported as a possible brief overlap ("overlap", a warning);
a fight between known drivers is contention (an error). Every overlap and contention
interval is also listed in .overlaps.

An output that turns off (goes to "Z") uses the chip's disable time (TDIS) when it
gives one, else its TPD.
"""
import heapq

from ..chips.base import Z, X, FloatingInput, InCircuitWrite
from .engine import SimBase

X_ENUM_LIMIT = 6        # unknown inputs worked through value by value (2**6 evaluations)


class _NeedX(FloatingInput):
    """eval() read an unknown input that has no trial value yet."""

    def __init__(self, name):
        super().__init__(name)
        self.name = name


class TimedSim(SimBase):
    mode = "timed"

    def __init__(self, netlist, stimuli=None, record=True, contention_grace_ns=10.0,
                 float_grace_ns=1000.0, osc_limit=1000, start=None):
        super().__init__(netlist, stimuli, record)
        for m in self.active.values():
            if hasattr(m, "wakeup"):
                m.timed = True
        # start from another simulator's state (registers, RAM, switches) instead of power-up
        if start is not None:
            self._restore(start)
        self.grace_ps = int(contention_grace_ns * 1000)
        self.float_grace_ps = int(float_grace_ns * 1000)
        self.osc_limit = osc_limit
        self.heap = []
        self.seq = 0
        self.pending = {}
        self.violations = []
        self.overlaps = []
        self.last_change = {}
        self.last_edge = {}
        self._fight = {}
        self._float_since = {}
        self._osc = {}
        self._osc_reported = set()
        self.cycles = 0
        # static tables
        self.edge_on = {}
        self.sampled_by = {}
        self.readpins = {}
        for ref, m in self.active.items():
            pm = self.pin_of[ref]
            for pin, kind in m.EDGE.items():
                if pin in pm:
                    self.edge_on.setdefault(pm[pin], []).append((ref, pin, kind))
                    for sp in m.sampled(pin):
                        if sp in pm:
                            self.sampled_by.setdefault(pm[sp], []).append((ref, pin, sp))
            for name, net in pm.items():
                k = m.PINS[m.names[name]][1]
                if k in ("in", "clk", "io", "ana"):
                    self.readpins.setdefault(net, []).append((ref, name))
        # power-up: settle with zero delay at t = 0, then run on events
        hon = self.history.on
        self.history.on = False
        self.full_resolve()
        self.settle()
        self.edges()
        self.history.on = hon
        self.contention = set()
        if hon:
            self.record()
        for ref, m in self.active.items():          # a pulse already running (a restored 555)
            self._arm(ref, m, 0)
        mc = self.main_clock()
        self._main = mc["part"] if mc else None
        for d in self.stimuli:
            if not d.get("period_ns"):
                self._problem("part", f"{d['part']}: no clock period (give period_ns)", "warning", log=False)
                continue
            p = int(round(d["period_ns"] * 1000))
            high = max(1, int(round(p * float(d.get("duty", 0.5)))))
            first = int(round(d["delay_ns"] * 1000)) if "delay_ns" in d else p - high
            d["_p"], d["_high"] = p, high
            m = self.N.parts[d["part"]]
            if start is not None and "delay_ns" not in d and getattr(m, "state", 0) == 1:
                self._push(high, "clk", d["part"], 0, d)    # restored high: the low half comes next
            else:
                self._push(first, "clk", d["part"], 1, d)

    # ------------------------------------------------------------------ queue
    def _push(self, t, kind, a=None, b=None, c=None, d=None, tok=None):
        self.seq += 1
        heapq.heappush(self.heap, (t, self.seq, kind, a, b, c, d, tok))
        return self.seq

    @property
    def t_ns(self):
        return self.t_ps / 1000.0

    def run_ns(self, ns):
        return self.run_until_ps(self.t_ps + int(round(ns * 1000)))

    def run_until_ps(self, t_end):
        heap = self.heap
        while heap and heap[0][0] <= t_end:
            t = heap[0][0]
            batch = []
            while heap and heap[0][0] == t:
                batch.append(heapq.heappop(heap))
                if len(batch) > 200000:
                    self._problem("oscillation", f"more than 200000 events at {t / 1000} ns: logic oscillates")
                    heap.clear()
                    break
            self.t_ps = t
            self._batch(t, batch)
        self.t_ps = max(self.t_ps, t_end)
        self._check_ongoing()
        return self

    def _batch(self, t, batch):
        changed = set()
        to_eval = {}
        sw = False
        for ev in batch:
            kind = ev[2]
            if kind == "drv":
                _, _, _, ref, name, net, v, tok = ev
                p = self.pending.get((ref, name))
                if p is None or p[2] != tok:
                    continue
                del self.pending[(ref, name)]
                self.drv[net][(ref, name)] = v
                changed.add(net)
            elif kind == "drvx":
                _, _, _, ref, name, net, v, tok = ev
                p = self.pending.get((ref, name))
                if p is None or p[2] != tok:
                    continue
                if self.drv[net].get((ref, name)) != X:
                    self.drv[net][(ref, name)] = X
                    changed.add(net)
            elif kind == "clk":
                _, _, _, ref, level, d, _, _ = ev
                m = self.N.parts[ref]
                if hasattr(m, "eval") and ref in self.active:
                    m.state = level
                    to_eval.setdefault(ref, set()).add("*")
                else:
                    m.set(level)
                    sw = True
                if level:
                    if ref == self._main:
                        self.cycles += 1
                    self._push(t + d["_high"], "clk", ref, 0, d)
                else:
                    self._push(t + d["_p"] - d["_high"], "clk", ref, 1, d)
            elif kind == "wake":
                ref = ev[3]
                m = self.active[ref]
                if m.wakeup(self._getters[ref]):
                    to_eval.setdefault(ref, set()).add("*")
                self._arm(ref, m, t)
            elif kind == "sw":
                sw = True
        if sw:
            self.refresh_switches()
            for pid in self.switch_parts:
                changed.update(self.N.pinnet[pid].values())
            for grp in self.group.values():
                changed.update(grp)
        old = {}
        for net in changed:
            self._tset(net, old, t)
        self._react(t, old, to_eval)

    def _tset(self, net, old, t, first=True):
        nv = self.resolve(net)
        grp = self.group.get(net)
        for m in (grp or (net,)):
            ov = self.nets[m]
            changed = ov != nv
            if changed:
                if m not in old:
                    old[m] = ov
                self._assign(m, nv)
            if changed or first:
                dep = self.dependents.get(m)
                if dep:
                    for f in dep:
                        self._tset(f, old, t, False)
        self._watch_fight(net, t)

    def _watch_fight(self, net, t):
        if net in self.rails:
            return
        who = []
        known = 0
        for n in self.group.get(net, (net,)):
            d = self.drv.get(n)
            if d:
                for k, v in d.items():
                    if v != Z:
                        who.append(f"{k[0]}.{k[1]}")
                        if v != X:
                            known += 1
            for w, _ in self.strong_ext.get(n, ()):
                who.append(w)
                known += 1
        f = self._fight.get(net)
        if len(who) > 1:
            if f is None:
                self._fight[net] = [t, tuple(sorted(who)), known <= 1]
            else:
                if known > 1:
                    f[2] = False
                if len(who) > len(f[1]):
                    f[1] = tuple(sorted(set(f[1]) | set(who)))
        elif f is not None:
            del self._fight[net]
            if t - f[0] > self.grace_ps:
                self._report_fight(net, f, t)

    def _report_fight(self, net, f, t_end, ended=True):
        where = {"net": net, "drivers": list(f[1]), "from_ns": f[0] / 1000.0, "to_ns": t_end / 1000.0}
        if ended and len(self.overlaps) < 100000:
            self.overlaps.append(dict(where, kind="overlap" if f[2] else "contention",
                                      ns=(t_end - f[0]) / 1000.0))
        if f[2]:
            self._problem("overlap", f"possible brief overlap on {net}: {', '.join(f[1])} "
                                     f"(an unknown output, as while a ROM settles)", "warning",
                          where=where, log=False)
            return
        c = (net, f[1])
        if c not in self.contention:
            self.contention.add(c)
        self._problem("contention", f"contention on {net}: driven by {', '.join(f[1])}",
                      where=where, log=False)

    def _check_ongoing(self):
        t = self.t_ps
        for net, f in list(self._fight.items()):
            if t - f[0] > self.grace_ps and not f[3:]:
                self._report_fight(net, f, t, ended=False)
                f.append("reported")
        for ref, (t0, msg) in list(self._float_since.items()):
            if t - t0 > self.float_grace_ps:
                self._problem("floating", f"floating input: {msg}", where={"part": ref})
                del self._float_since[ref]

    def _react(self, t, old, to_eval):
        nets = self.nets
        # oscillation watch: too many changes of one net within 1 us
        w = t // 1_000_000
        for net in old:
            c = self._osc.get(net)
            if c is None or c[0] != w:
                self._osc[net] = (w, 1)
            else:
                self._osc[net] = (w, c[1] + 1)
                if c[1] + 1 > self.osc_limit and net not in self._osc_reported:
                    self._osc_reported.add(net)
                    self._problem("oscillation", f"net {net} changes more than {self.osc_limit} times in 1 us",
                                  "warning", where={"net": net})
        # hold violations, then edges (sampling the values from just before t)
        fired = []
        for net, ov in old.items():
            for ref, sclk, sp in self.sampled_by.get(net, ()):
                te = self.last_edge.get((ref, sclk))
                if te is not None and te < t:
                    h = int(self.active[ref].hold_ns(sp) * 1000)
                    if t - te < h:
                        self._violation("hold", ref, sp, sclk, t, (t - te) / 1000.0)
            nv = nets[net]
            for ref, pin, kind in self.edge_on.get(net, ()):
                if (kind == "rise" and ov == 0 and nv == 1) or (kind == "fall" and ov == 1 and nv == 0):
                    fired.append((ref, pin))
        if fired:
            new = []
            for ref, pin in fired:
                m = self.active[ref]
                pm = self.pin_of[ref]
                for sp in m.sampled(pin):
                    net = pm.get(sp)
                    if net is None:
                        continue
                    lc = t if net in old else self.last_change.get(net)
                    s = int(m.setup_ns(sp) * 1000)
                    if lc is not None and t - lc < s:
                        self._violation("setup", ref, sp, pin, t, (t - lc) / 1000.0)
                self.last_edge[(ref, pin)] = t
                g = self._pre_getter(ref, old)
                try:
                    new.append((ref, m.edge(g, pin)))
                except FloatingInput as e:
                    self._problem("floating", f"floating input at clock edge: {e}", where={"part": ref})
                to_eval.setdefault(ref, set()).add(pin)
            for ref, st in new:
                self.active[ref].state = st
        for net in old:
            self.last_change[net] = t
            for ref, name in self.readpins.get(net, ()):
                to_eval.setdefault(ref, set()).add(name)
        for ref, causes in to_eval.items():
            self._teval(ref, causes, t)

    def _pre_getter(self, ref, old):
        pm = self.pin_of[ref]
        nets = self.nets

        def g(name):
            net = pm.get(name)
            if net is None:
                v = Z
            else:
                v = old.get(net, nets[net])
            if v == Z or v == X:
                raise FloatingInput(f"{ref}.{name} reads {v} on net {net}")
            return v
        return g

    def _violation(self, kind, ref, pin, clk, t, dt):
        m = self.active[ref]
        need = m.setup_ns(pin) if kind == "setup" else m.hold_ns(pin)
        v = {"kind": kind, "part": ref, "pin": pin, "clock": clk, "t_ns": t / 1000.0,
             "margin_ns": dt, "need_ns": need}
        if len(self.violations) < 10000:
            self.violations.append(v)
        word = "before" if kind == "setup" else "after"
        self._problem(kind, f"{kind} violation: {ref} {pin} changed {dt:g} ns {word} the {clk} edge "
                            f"(needs {need:g} ns)", where={"part": ref, "pin": pin, "clock": clk}, log=False)

    def _arm(self, ref, m, t):
        w = getattr(m, "wake_ns", None)
        if w:
            m.wake_ns = None
            self._push(t + int(round(w * 1000)), "wake", ref)

    def _x_eval(self, ref, m):
        """eval() with unknown ("X") inputs: try every 0/1 value of the unknown inputs it
        reads; an output that differs between the trials is unknown. None when an input
        is floating ("Z"), or too many inputs are unknown."""
        pm = self.pin_of[ref]
        nets = self.nets
        xs = []
        while True:
            results = []
            try:
                for combo in range(1 << len(xs)):
                    asg = {p: (combo >> i) & 1 for i, p in enumerate(xs)}

                    def g(name, asg=asg):
                        v = asg.get(name)
                        if v is not None:
                            return v
                        net = pm.get(name)
                        v = nets[net] if net is not None else Z
                        if v == X:
                            raise _NeedX(name)
                        if v == Z:
                            raise FloatingInput(f"{ref}.{name} reads Z on net {net}")
                        return v
                    results.append(m.eval(g))
            except _NeedX as e:
                if len(xs) >= X_ENUM_LIMIT or e.name in xs:
                    return None
                xs.append(e.name)
                continue
            except FloatingInput:
                return None
            break
        out = dict(results[0])
        for r in results[1:]:
            for k, v in r.items():
                if out.get(k) != v:
                    out[k] = X
        return out

    def _teval(self, ref, causes, t):
        m = self.active[ref]
        g = self._getters[ref]
        try:
            try:
                m.asyncupd(g)
            except InCircuitWrite as e:
                self._problem("eeprom-write", str(e), where={"part": ref})
            self._arm(ref, m, t)
            outs = m.eval(g)
            self._float_since.pop(ref, None)
        except FloatingInput as e:
            outs = self._x_eval(ref, m)
            if outs is None:
                if ref not in self._float_since:
                    self._float_since[ref] = (t, str(e))
                return
            self._float_since.pop(ref, None)
        pm = self.pin_of[ref]
        cls = type(m)
        hold = cls.ADDR_HOLD
        addr = hold is not None and "*" not in causes and any(c[:1] == "A" and c[1:].isdigit() for c in causes)
        for name, v in outs.items():
            net = pm.get(name)
            if net is None:
                continue
            key = (ref, name)
            cur = self.drv[net].get(key)
            p = self.pending.get(key)
            if addr and v != Z and cur not in (None, Z):
                # an address change: the old data for tOH, unknown until the access time
                if p is not None:
                    del self.pending[key]
                d = max(cls.tpd(c, name) for c in causes)
                when = t + max(1, int(round(d * 1000)))
                self.seq += 1
                tok = self.seq
                self.pending[key] = (when, v, tok)
                heapq.heappush(self.heap, (when, tok, "drv", ref, name, net, v, tok))
                tx = t + max(1, int(round(hold * 1000)))
                if tx < when:
                    heapq.heappush(self.heap, (tx, tok, "drvx", ref, name, net, X, tok))
                continue
            if p is not None:
                if p[1] == v:
                    continue
                del self.pending[key]
            if v == cur:
                continue
            if "*" in causes:
                d = (cls.tdis if v == Z else cls.tpd)("*", name)
            elif v == Z:
                # turning off: the disable time of the inputs that can turn it off (OE, CE ...)
                offs = [c for c in causes if cls.TDIS and cls._tpd_lookup(c, name, cls.TDIS) is not None]
                d = max(cls.tdis(c, name) for c in (offs or causes))
            else:
                d = max(cls.tpd(c, name) for c in causes)
            when = t + max(1, int(round(d * 1000)))
            self.seq += 1
            tok = self.seq
            self.pending[key] = (when, v, tok)
            heapq.heappush(self.heap, (when, tok, "drv", ref, name, net, v, tok))

    # ------------------------------------------------------------------ controls
    def set(self, pid, value):
        """Change a switch, button, slide or pot now and run the logic to the same moment."""
        ref = self.drive(pid, value)
        if ref in self.active:
            self._teval(ref, {"*"}, self.t_ps)
        else:
            self._push(self.t_ps, "sw")
        self.run_until_ps(self.t_ps)
        return self

    def press(self, pid, hold_ns=1_000_000):
        self.set(pid, True)
        self.run_ns(hold_ns)
        self.set(pid, False)
        return self

    def update(self):
        """Apply switch changes made with drive() now, and run the logic to this moment."""
        self._push(self.t_ps, "sw")
        self.run_until_ps(self.t_ps)
        return self

    def half(self, level, clock=None):
        """Move a clock source (the main clock by default) to level now."""
        if clock is None:
            mc = self.main_clock()
            clock = mc["part"] if mc else None
        if clock is None:
            return self.update()
        self.set(clock, level)
        return self

    def period_ns(self):
        mc = self.main_clock()
        return mc.get("period_ns") if mc else None

    def step(self, n=1):
        """Run n periods of the main clock (or n microseconds without one)."""
        p = self.period_ns() or 1000.0
        self.run_ns(p * n)
        return self

    def run(self, until="halt", limit=20000, on_cycle=None):
        cond = self._condition(until)
        n = 0
        while not cond():
            if n >= limit:
                return {"done": False, "cycles": n, "t_ns": self.t_ns}
            self.step()
            n += 1
            if on_cycle:
                on_cycle(self)
        return {"done": True, "cycles": n, "t_ns": self.t_ns}
