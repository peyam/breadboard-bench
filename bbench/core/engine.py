"""Shared machinery of the two simulators: compiling a netlist, resolving net values
from drivers, switches and resistors, the zero-delay settle-then-edges algorithm
(ported from the proven pc2sim/sim.py), state, traces and problems.

Net values are 0, 1, "Z" (floating) or "X" (unknown / fight).

Resolution of one net, strongest first:
1. a rail (VCC, GND, or a POWER pin) gives its value;
2. strong drivers: chip outputs that are not "Z", and closed switches to a rail.
   Nets joined by a closed switch resolve together as one. Two or more strong
   drivers at once are contention (even with equal values, as in pc2sim);
3. a weak pull: a resistor to a rail;
4. a follower: a net joined by a resistor to a net with a value takes that value
   (an LED's resistor, a transistor's base resistor);
5. otherwise "Z" (floating).
"""
import copy
from collections import deque

from ..chips.base import Z, X, FloatingInput, InCircuitWrite
from .netlist import Netlist, is_active
from .checks import Problems, static_checks
from .waveforms import History, trace as _trace, to_vcd as _to_vcd
from .analog import Network, parse_value


class Ctx:
    """What a chip's configure() may ask about its surroundings."""

    def __init__(self, sim, pid):
        self.sim, self.pid = sim, pid
        self.props = sim.N.props.get(pid, {})

    def pin_net(self, name):
        return self.sim.pin_of[self.pid].get(name)

    def parts_on(self, net):
        N = self.sim.N
        return [(p, N.types[p], str(n), N.props[p]) for p, n in N.nets.get(net, [])]

    def resistance(self, a, b):
        return self.sim.network().resistance(a, b)

    def capacitance(self, a, b):
        return self.sim.capacitance(a, b)


class SimBase:
    mode = "?"

    def __init__(self, netlist, stimuli=None, record=True):
        if not isinstance(netlist, Netlist):
            raise TypeError("SimBase needs a bbench.core.netlist.Netlist")
        N = self.N = netlist
        self.rails = N.rails()
        self.problems = Problems()
        for p in N.problems:
            self.problems.add(p["kind"], p["message"], p["severity"], p.get("where"))
        self.log = []                       # every problem message, pc2sim wording
        self.contention = set()             # {(net, (driver, ...))}, pc2sim format
        self._pending_contention = set()
        self.t_ps = 0
        self.history = History()
        self.history.on = bool(record)
        self.nets = {}
        self.readers = {}
        self.drv = {}
        self.pin_of = {}
        self.active = {}
        self.passive = {}
        self.edgepins = {}
        for pid, m in N.parts.items():
            if is_active(m):
                self.active[pid] = m
                pm = {}
                for n, net in N.pinnet[pid].items():
                    name, kind = m.PINS[n]
                    pm[name] = net
                    if kind in ("in", "clk", "io", "ana"):
                        self.readers.setdefault(net, [])
                        if pid not in self.readers[net]:
                            self.readers[net].append(pid)
                    if kind in ("out", "tri", "io"):
                        self.drv.setdefault(net, {})
                self.pin_of[pid] = pm
                if m.EDGE:
                    self.edgepins[pid] = {p: None for p in m.EDGE if p in pm}
            else:
                self.passive[pid] = m
        for net in N.nets:
            self.nets[net] = self.rails.get(net, 0)
        st, msgs, driven = static_checks(N, self.rails)
        for p in st:
            self.problems.add(p["kind"], p["message"], p["severity"], p["where"])
        self.log.extend(msgs)
        self.driven_somehow = driven
        # weak links (resistors)
        self.weak = {}
        self.wlinks = {}
        for pid, m in self.passive.items():
            pn = N.pinnet[pid]
            for a, b, strength, ohms, who in m.links():
                if strength != "weak":
                    continue
                na, nb = pn.get(a), pn.get(b)
                if na is None or nb is None or na == nb:
                    continue
                ra, rb = self.rails.get(na), self.rails.get(nb)
                if ra is not None and rb is not None:
                    continue
                if ra is not None or rb is not None:
                    net, v = (nb, ra) if ra is not None else (na, rb)
                    old = self.weak.get(net)
                    self.weak[net] = v if old in (None, v) else X
                else:
                    self.wlinks.setdefault(na, [])
                    self.wlinks.setdefault(nb, [])
                    if nb not in self.wlinks[na]:
                        self.wlinks[na].append(nb)
                        self.wlinks[nb].append(na)
        self.switch_parts = [pid for pid, m in self.passive.items() if m.CATEGORY == "switch"]
        self.indicators = [pid for pid, m in self.passive.items() if m.CATEGORY == "indicator"]
        # followers that chip inputs read are kept up to date while settling
        strong_able = set(self.drv)
        for pid in self.switch_parts:
            strong_able.update(N.pinnet[pid].values())
        self.live = {n for n in self.wlinks if n in self.readers}
        self.dependents = {}
        stack = list(self.live)
        while stack:
            n = stack.pop()
            for m2 in self.wlinks[n]:
                dep = self.dependents.setdefault(m2, [])
                if n not in dep:
                    dep.append(n)
                if m2 not in self.live and m2 not in strong_able and m2 not in self.weak:
                    self.live.add(m2)
                    stack.append(m2)
        plain = [n for n in self.nets if n not in self.rails and n not in self.wlinks]
        # followers nothing reads are worked out only when shown (value(), state())
        follow = [n for n in self.nets if n not in self.rails and n in self.wlinks and n in self.live]
        self._order = plain + follow + follow
        self._getters = {pid: self._make_getter(pid) for pid in self.active}
        self.group = {}
        self.strong_ext = {}
        self._network = None
        self._poked = set()
        self._switch_dirty = False
        self._switch_nets = set()
        for pid in self.switch_parts:
            self._switch_nets.update(N.pinnet[pid].values())
        self.refresh_switches()
        for pid, m in self.active.items():
            m.configure(Ctx(self, pid))
        self.stimuli = self._stimuli(stimuli or [])

    # ------------------------------------------------------------------ problems
    def _problem(self, kind, message, severity="error", where=None, log=True):
        if log:
            self.log.append(message)
        self.problems.add(kind, message, severity, where, t_ns=self.t_ps / 1000.0)

    @property
    def errors(self):
        """Problems as dicts (see bbench.core.checks)."""
        return list(self.problems)

    # ------------------------------------------------------------------ helpers
    def _make_getter(self, ref):
        pm = self.pin_of[ref]
        nets = self.nets

        def g(name):
            net = pm.get(name)
            v = nets[net] if net is not None else Z
            if v == Z or v == X:
                raise FloatingInput(f"{ref}.{name} reads {v} on net {net}")
            return v
        return g

    def getter(self, ref):
        return self._getters[ref]

    def refresh_switches(self):
        ext = {}
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        rails = self.rails
        for pid in self.switch_parts:
            m = self.passive[pid]
            pn = self.N.pinnet[pid]
            for a, b, strength, ohms, who in m.links():
                if strength != "strong":
                    continue
                na, nb = pn.get(a), pn.get(b)
                if na is None or nb is None or na == nb:
                    continue
                ra, rb = rails.get(na), rails.get(nb)
                if ra is not None and rb is not None:
                    if ra != rb:
                        self._problem("short", f"{who} joins {na} to {nb} (a short circuit)",
                                      where={"part": who, "nets": [na, nb]})
                    continue
                if ra is not None:
                    ext.setdefault(nb, []).append((who, ra))
                elif rb is not None:
                    ext.setdefault(na, []).append((who, rb))
                else:
                    parent[find(na)] = find(nb)
        groups = {}
        for n in list(parent):
            groups.setdefault(find(n), []).append(n)
        self.group = {}
        for members in groups.values():
            if len(members) > 1:
                t = tuple(sorted(members))
                for n in t:
                    self.group[n] = t
        self.strong_ext = ext
        self._network = None

    def network(self):
        if self._network is None:
            edges, shorts = [], []
            for pid, m in self.passive.items():
                pn = self.N.pinnet[pid]
                for a, b, strength, ohms, who in m.links():
                    na, nb = pn.get(a), pn.get(b)
                    if na is None or nb is None:
                        continue
                    if strength == "strong":
                        shorts.append((na, nb))
                    else:
                        edges.append((na, nb, ohms))
            for net, v in self.rails.items():
                shorts.append((net, "VCC" if v else "GND"))
            self._network = Network(edges, shorts)
        return self._network

    def capacitance(self, a, b):
        net = self.network()
        total = 0.0
        for pid, m in self.passive.items():
            if m.TYPE != "C":
                continue
            pn = self.N.pinnet[pid]
            n1, n2 = pn.get(1), pn.get(2)
            if n1 is None or n2 is None:
                continue
            if (net.same(n1, a) and net.same(n2, b)) or (net.same(n1, b) and net.same(n2, a)):
                total += parse_value(m.props.get("value")) or 0.0
        return total or None

    # ------------------------------------------------------------------ resolution
    def _strong(self, net):
        for n in self.group.get(net, (net,)):
            d = self.drv.get(n)
            if d:
                for v in d.values():
                    if v != Z:
                        return True
            if n in self.strong_ext:
                return True
        return False

    def _source(self, n2, visited):
        r = self.rails.get(n2)
        if r is not None:
            return r
        if self._strong(n2):
            return self.nets[n2]
        w = self.weak.get(n2)
        if w is not None:
            return w
        if n2 in visited or n2 not in self.wlinks:
            return None
        visited.add(n2)
        return self._follow(n2, visited)

    def _follow(self, net, visited):
        vals = set()
        for n2 in self.wlinks[net]:
            v = self._source(n2, visited)
            if v is not None and v != Z:
                vals.add(v)
        if not vals:
            return None
        return vals.pop() if len(vals) == 1 else X

    def resolve(self, net):
        r = self.rails.get(net)
        if r is not None:
            return r
        grp = self.group.get(net)
        if grp is not None:
            return self._resolve_group(net, grp)
        d = self.drv.get(net)
        ext = self.strong_ext.get(net)
        vals = [v for v in d.values() if v != Z] if d else []
        if ext:
            vals += [v for _, v in ext]
        if vals:
            if len(vals) > 1:
                who = [k for k, v in d.items() if v != Z] if d else []
                if ext:
                    who += [w for w, _ in ext]
                self._pending_contention.add((net, tuple(sorted(map(str, who)))))
                return vals[0] if len(set(vals)) == 1 else X
            return vals[0]
        w = self.weak.get(net)
        if w is not None:
            return w
        if net in self.wlinks:
            f = self._follow(net, {net})
            if f is not None:
                return f
        if d is None:                       # no chip output can drive it
            return Z
        if not d:
            return self.nets[net]          # its drivers are not evaluated yet (power-up)
        return Z

    def _resolve_group(self, net, grp):
        vals, who = [], []
        for n in grp:
            r = self.rails.get(n)
            if r is not None:
                vals.append(r)
                who.append(n)
            d = self.drv.get(n)
            if d:
                for k, v in d.items():
                    if v != Z:
                        vals.append(v)
                        who.append(k)
            for w, v in self.strong_ext.get(n, ()):
                vals.append(v)
                who.append(w)
        if vals:
            if len(vals) > 1:
                self._pending_contention.add(("=".join(grp), tuple(sorted(map(str, who)))))
                return vals[0] if len(set(vals)) == 1 else X
            return vals[0]
        ws = {self.weak[n] for n in grp if n in self.weak}
        if ws:
            return ws.pop() if len(ws) == 1 else X
        visited = set(grp)
        vals = set()
        for n in grp:
            if n in self.wlinks:
                for n2 in self.wlinks[n]:
                    if n2 in visited:
                        continue
                    v = self._source(n2, visited)
                    if v is not None and v != Z:
                        vals.add(v)
        if vals:
            return vals.pop() if len(vals) == 1 else X
        if not any(n in self.drv for n in grp):
            return Z
        return self.nets[net] if not any(self.drv.get(n) for n in grp) else Z

    def _assign(self, net, v):
        self.nets[net] = v
        if self.history.on:
            self.history.add(net, self.t_ps, v)

    def _update(self, net, q, inq, first=True):
        """A driver of net changed: resolve it, wake its readers and its followers.
        Followers are re-resolved even when the value stays the same (a net that has
        just got a driver may now be a source for them)."""
        nv = self.resolve(net)
        grp = self.group.get(net)
        for m in (grp or (net,)):
            changed = self.nets[m] != nv
            if changed:
                self._assign(m, nv)
                rd = self.readers.get(m)
                if rd:
                    for r in rd:
                        if r not in inq:
                            q.append(r)
                            inq.add(r)
            if changed or first:
                dep = self.dependents.get(m)
                if dep:
                    for f in dep:
                        self._update(f, q, inq, False)

    def full_resolve(self):
        self._pending_contention = set()
        for net in self._order:
            nv = self.resolve(net)
            if self.nets[net] != nv:
                self._assign(net, nv)

    # ------------------------------------------------------------------ settle (zero delay)
    def settle(self, todo=None, limit=20000, check=None):
        """Evaluate chips until nothing changes. todo: the chips to start from (all by
        default). check: nets to check for contention afterwards (all by default when
        todo is None, else the nets that changed and the switched ones)."""
        self._pending_contention = set()
        touched = set() if check is not None or todo is not None else None
        q = deque(todo if todo is not None else self.active.keys())
        inq = set(q)
        float_wait = set()
        steps = 0
        serial = False          # one output at a time: breaks symmetric loops (latches)
        active, getters, pin_of, drv = self.active, self._getters, self.pin_of, self.drv
        while q:
            steps += 1
            if steps == limit // 4:
                serial = True
            if steps > limit:
                self._problem("oscillation", "logic did not settle (oscillation?)",
                              where={"parts": sorted(set(q))[:20]})
                break
            ref = q.popleft()
            inq.discard(ref)
            m = active[ref]
            g = getters[ref]
            try:
                try:
                    m.asyncupd(g)
                except InCircuitWrite as e:
                    self._problem("eeprom-write", str(e), where={"part": ref})
                outs = m.eval(g)
                float_wait.discard(ref)
            except FloatingInput:
                float_wait.add(ref)
                continue
            pm = pin_of[ref]
            dirty = []
            for name, v in outs.items():
                net = pm.get(name)
                if net is None:
                    continue
                dn = drv[net]
                key = (ref, name)
                if dn.get(key) != v:
                    if serial and dirty:
                        if ref not in inq:
                            q.append(ref)
                            inq.add(ref)
                        break
                    dn[key] = v
                    dirty.append(net)
            for net in dirty:
                self._update(net, q, inq)
            if touched is not None:
                touched.update(dirty)
        # final checks on the settled state
        self._pending_contention = set()
        if touched is None:
            for net in self.drv:
                self.resolve(net)
        else:
            for net in touched:
                self.resolve(net)
            for net in check or ():
                self.resolve(net)
        for net in self.strong_ext:
            self.resolve(net)
        for c in self._pending_contention:
            if c not in self.contention:
                self.contention.add(c)
                self._problem("contention", f"contention on {c[0]}: driven by {', '.join(c[1])}",
                              where={"net": c[0], "drivers": list(c[1])}, log=False)
        self._pending_contention = set()
        for ref in list(float_wait):
            try:
                self.active[ref].eval(self._getters[ref])
            except FloatingInput as e:
                self._problem("floating", f"floating input: {e}", where={"part": ref})
        return self

    def edges(self):
        rounds = 0
        nets = self.nets
        while True:
            rounds += 1
            if rounds > 50:
                self._problem("oscillation", "edge cascade did not stop")
                return
            fired = []
            for ref, ep in self.edgepins.items():
                pm = self.pin_of[ref]
                kinds = self.active[ref].EDGE
                for pin, last in ep.items():
                    v = nets[pm[pin]]
                    if last is not None and last != v:
                        kind = kinds[pin]
                        if (kind == "rise" and last == 0 and v == 1) or (kind == "fall" and last == 1 and v == 0):
                            fired.append((ref, pin))
                    ep[pin] = v
            if not fired:
                return
            new = []
            for ref, pin in fired:
                m = self.active[ref]
                try:
                    new.append((ref, m.edge(self._getters[ref], pin)))
                except FloatingInput as e:
                    self._problem("floating", f"floating input at clock edge: {e}", where={"part": ref})
            for ref, st in new:
                self.active[ref].state = st
            self.settle([r for r, _ in new])

    # ------------------------------------------------------------------ parts and clocks
    def _target(self, pid):
        """'S3' -> ('S3', None); 'S3.4' -> ('S3', 4); a label ('RESET') -> its part."""
        N = self.N
        if pid in N.parts:
            return pid, None
        if isinstance(pid, str) and "." in pid:
            base, sec = pid.rsplit(".", 1)
            if base in N.parts and sec.isdigit():
                return base, int(sec)
        for q in self.switch_parts + list(self.active) + list(self.passive):
            pr = N.props.get(q, {})
            if pr.get("label") == pid:
                return q, None
            labels = pr.get("labels")
            if labels and pid in labels:
                return q, labels.index(pid) + 1
        raise KeyError(f"no part or switch called {pid!r}")

    def drive(self, pid, value):
        """Set a part without settling: a switch/button/slide (value), a pot (position),
        or a clock source/555 output (0/1)."""
        ref, sec = self._target(pid)
        m = self.N.parts[ref]
        if is_active(m):
            m.state = 1 if value else 0
            self._poked.add(ref)
        else:
            m.set(value, sec)
            self._switch_dirty = True
        return ref

    def _stimuli(self, entries):
        """Normalise clock stimuli; add CLOCK parts and astable 555s that are not listed."""
        out = []
        seen = set()
        for e in entries:
            pid = e["part"]
            if pid not in self.N.parts:
                self._problem("part", f"stimulus for unknown part {pid}", log=False)
                continue
            d = dict(e)
            m = self.N.parts[pid]
            if "period_ns" not in d:
                p = None
                if hasattr(m, "period_ns"):
                    p = m.period_ns()
                d["period_ns"] = p
                if p and getattr(m, "timing", None) and "high_ns" in m.timing:
                    d.setdefault("duty", m.timing["high_ns"] / p)
            d.setdefault("duty", 0.5)
            d.setdefault("role", "clock")
            out.append(d)
            seen.add(pid)
        for pid, m in self.active.items():
            if pid in seen:
                continue
            if m.TYPE == "CLOCK" or getattr(m, "mode", None) == "astable":
                p = m.period_ns() if hasattr(m, "period_ns") else None
                d = {"part": pid, "period_ns": p, "duty": 0.5, "role": "clock", "auto": True}
                if p and getattr(m, "timing", None) and "high_ns" in m.timing:
                    d["duty"] = m.timing["high_ns"] / p
                out.append(d)
        return out

    def main_clock(self):
        for d in self.stimuli:
            if d.get("role") == "main":
                return d
        for d in self.stimuli:
            if d.get("role") != "scan":
                return d
        return None

    # ------------------------------------------------------------------ snapshots
    def snapshot(self):
        """The state of every part now (chip registers and memories, clock levels, switch
        and pot positions), to start another simulator of the same project from this
        moment: ``project.simulator("timed", start=sim)`` (or ``start=sim.snapshot()``)."""
        return {"t_ns": self.t_ps / 1000.0,
                "types": {pid: getattr(m, "TYPE", "") for pid, m in self.N.parts.items()},
                "parts": {pid: copy.deepcopy(m.state) for pid, m in self.N.parts.items()},
                "nets": dict(self.nets), "drv": copy.deepcopy(self.drv)}

    def _restore(self, start):
        """Load a snapshot (or another simulator's state) into the parts. Parts that are
        not in it, or are of another type, keep their power-up state."""
        if isinstance(start, SimBase):
            start = start.snapshot()
        types = start.get("types", {})
        same = set(types) == set(self.N.parts) and all(
            types[pid] == getattr(m, "TYPE", "") for pid, m in self.N.parts.items())
        for pid, st in start.get("parts", {}).items():
            m = self.N.parts.get(pid)
            if m is None or (pid in types and types[pid] != getattr(m, "TYPE", "")):
                continue
            m.state = copy.deepcopy(st)
            if hasattr(m, "restored"):
                m.restored()
        # the same circuit: take its net values and drivers too, so that settling again does
        # not pass through power-up values (which could, say, write the RAM)
        if same and start.get("nets") is not None and set(start["nets"]) == set(self.nets):
            self.nets.update(start["nets"])
            for net, d in (start.get("drv") or {}).items():
                if net in self.drv:
                    self.drv[net] = copy.deepcopy(d)
        self._switch_dirty = True
        self.refresh_switches()

    # ------------------------------------------------------------------ reading
    def v(self, net):
        return self.nets[net]

    def word(self, prefix, n):
        bits = [self.nets[f"{prefix}{i}"] for i in range(n)]
        if any(b not in (0, 1) for b in bits):
            return None
        return sum(b << i for i, b in enumerate(bits))

    def value(self, net):
        """Value of any net, including ones only followed through a resistor."""
        if net in self.wlinks and net not in self.live:
            saved = self._pending_contention
            v = self.resolve(net)
            self._pending_contention = saved
            return v
        return self.nets[net]

    def all_values(self):
        return {n: self.value(n) for n in self.nets}

    def _show(self, vals):
        leds, digits, probes = {}, {}, {}
        for pid in self.indicators:
            m = self.passive[pid]
            pn = self.N.pinnet[pid]
            r = m.show(lambda n: vals.get(pn.get(n), Z))
            if m.TYPE == "LED":
                leds[pid] = bool(r)
            elif m.TYPE == "PROBE":
                probes[pid] = r
            else:
                digits[pid] = r
        return leds, digits, probes

    def state(self):
        vals = self.all_values()
        leds, digits, probes = self._show(vals)
        sw = {}
        for pid in self.switch_parts:
            sw[pid] = self.passive[pid].get()
        for pid, m in self.passive.items():
            if m.TYPE == "POT":
                sw[pid] = m.get()
        return {"mode": self.mode, "t_ns": self.t_ps / 1000.0, "nets": vals, "leds": leds,
                "digits": digits, "probes": probes, "switches": sw, "errors": self.errors}

    def record(self, nets=None):
        """Start recording (again) from now: every net, or only the nets given."""
        self.history.start(self.all_values(), self.t_ps, nets)

    def trace(self, nets=None):
        if nets is None:
            nets = sorted(self.history.changes)
        return _trace(self.history, list(nets), self.nets)

    def to_vcd(self, nets=None):
        return _to_vcd(self.trace(nets))

    def write_vcd(self, path, nets=None):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_vcd(nets))
        return path

    def _condition(self, until):
        if callable(until):
            return lambda: until(self)
        if until == "halt":
            if "HLT_n" in self.nets:
                return lambda: self.nets["HLT_n"] == 0
            if "HLT" in self.nets:
                return lambda: self.nets["HLT"] == 1
            raise KeyError("this project has no HLT or HLT_n net")
        if isinstance(until, dict):
            net, val = until["net"], until.get("value", 1)
            return lambda: self.nets[net] == val
        if until is None:
            return lambda: False
        raise ValueError(f"unknown run condition {until!r}")


class ZeroDelaySim(SimBase):
    """Zero-delay simulator: settle every chip, then fire clock edges, then settle again.

    Time is nominal: every update() moves on by half a main-clock period (500 ns when
    there is no clock), so traces and VCD files look like ideal timing diagrams."""
    mode = "zero"

    def __init__(self, netlist, stimuli=None, record=True, settle=True, incremental=True, start=None):
        super().__init__(netlist, stimuli, record)
        if start is not None:
            self._restore(start)
        self.incremental = incremental
        self._settled_once = False
        mc = self.main_clock()
        p = mc.get("period_ns") if mc else None
        self.tick_ps = int(round((p or 1000.0) * 500))
        self.cycles = 0
        self._phase = {}                    # run_ns: clock part -> (next toggle in ps, level now)
        if settle:
            self.update()
            if self.history.on:
                self.record()

    def update(self, full=False, tick=True):
        """Settle, fire any clock edges, settle again (pc2sim's Sim.step()).
        tick=False keeps the nominal time where it is (run_ns sets it itself).

        After the first update only what changed is worked on: chips set with drive()
        and the readers of nets that switches changed. full=True (or setting
        .incremental = False) re-settles every chip, as pc2sim did; use it after
        changing a chip's state directly."""
        if full or not self.incremental or not self._settled_once:
            self.refresh_switches()
            self.full_resolve()
            self.settle()
            self._settled_once = True
        else:
            todo = list(self._poked)
            changed = []
            if self._switch_dirty:
                before = set(self.group)
                self.refresh_switches()
                nets = self._switch_nets | before | set(self.group)
                self._pending_contention = set()
                for net in nets:
                    if net in self.rails:
                        continue
                    nv = self.resolve(net)
                    if self.nets[net] != nv:
                        self._assign(net, nv)
                        changed.append(net)
                    for f in self.dependents.get(net, ()):
                        fv = self.resolve(f)
                        if self.nets[f] != fv:
                            self._assign(f, fv)
                            changed.append(f)
                seen = set(todo)
                for net in changed:
                    for r in self.readers.get(net, ()):
                        if r not in seen:
                            seen.add(r)
                            todo.append(r)
            self.settle(todo, check=changed + [n for n in self._switch_nets if n not in self.rails])
        self._poked.clear()
        self._switch_dirty = False
        self.edges()
        if tick:
            self.t_ps += self.tick_ps
        return self

    def clocks(self):
        """The clock sources the app's speed control is about: every stimulus with a period
        except a display scan clock. run_ns moves the scan clock too (scan_clocks()), so its
        digit counter and digit selects run in step with everything else; state() also shows
        a multiplexed display as the eye sees it, all digits lit."""
        return [d for d in self.stimuli if d.get("period_ns") and d.get("role") != "scan"]

    def scan_clocks(self):
        """Display scan clocks (stimuli with role "scan"), such as PC-2's U36."""
        return [d for d in self.stimuli if d.get("period_ns") and d.get("role") == "scan"]

    def run_ns(self, ns, max_edges=100000):
        """Real-time view of the zero-delay simulation: move the nominal time on by ns and
        toggle every clock source (CLOCK parts, astable 555s, project stimuli, the display
        scan clock) at its own period and duty, in time order, settling after each edge. Stops early after
        max_edges clock edges. Returns {"t_ns", "edges", "cycles", "done"}."""
        t_end = self.t_ps + int(round(ns * 1000))
        clocks = self.clocks() + self.scan_clocks()
        mc = self.main_clock()
        main = mc["part"] if mc else None
        nxt = {}
        for d in clocks:
            pid = d["part"]
            m = self.N.parts[pid]
            lvl = m.state if pid in self.active else (1 if m.get() else 0)
            p = int(round(d["period_ns"] * 1000))
            high = max(1, min(p - 1, int(round(p * float(d.get("duty", 0.5))))))
            ph = self._phase.get(pid)
            if ph is None or ph[1] != lvl or ph[0] < self.t_ps:
                ph = (self.t_ps + (high if lvl else p - high), lvl)
            nxt[pid] = [ph[0], lvl, p, high]
        edges = 0
        done = True
        while nxt:
            pid = min(nxt, key=lambda k: nxt[k][0])
            t, lvl, p, high = nxt[pid]
            if t > t_end:
                break
            if edges >= max_edges:
                done = False
                t_end = self.t_ps
                break
            self.t_ps = t
            lvl = 1 - lvl
            self.drive(pid, lvl)
            self.update(tick=False)
            edges += 1
            if lvl and pid == main:
                self.cycles += 1
            nxt[pid] = [t + (high if lvl else p - high), lvl, p, high]
        for pid, (t, lvl, p, high) in nxt.items():
            self._phase[pid] = (t, lvl)
        if not clocks:
            self.update(tick=False)
        self.t_ps = max(self.t_ps, t_end)
        return {"t_ns": self.t_ps / 1000.0, "edges": edges, "cycles": self.cycles, "done": done}

    def set(self, pid, value):
        self.drive(pid, value)
        self.update()
        return self

    def press(self, pid):
        self.set(pid, True)
        self.set(pid, False)
        return self

    def half(self, level, clock=None):
        """Move one clock (the main clock by default) to level and settle."""
        if clock is None:
            mc = self.main_clock()
            if mc is None:
                return self.update()
            clock = mc["part"]
        self.drive(clock, level)
        return self.update()

    def step(self, n=1):
        """n cycles of the main clock (high then low)."""
        mc = self.main_clock()
        for _ in range(n):
            if mc is None:
                self.update()
            else:
                self.half(1, mc["part"])
                self.half(0, mc["part"])
            self.cycles += 1
        return self

    def run(self, until="halt", limit=20000, on_cycle=None):
        cond = self._condition(until)
        n = 0
        while not cond():
            if n >= limit:
                return {"done": False, "cycles": n}
            self.step()
            n += 1
            if on_cycle:
                on_cycle(self)
        return {"done": True, "cycles": n}

    def state(self, persist=True):
        """Also shows multiplexed displays as the eye sees them when the project marks
        its scan clock (a stimulus with role "scan"): the scan clock is run through a
        full scan and every lit segment is kept."""
        st = super().state()
        scans = [d for d in self.stimuli if d.get("role") == "scan"] if persist else []
        if scans and st["digits"]:
            seen = dict.fromkeys(st["digits"], 0)
            hon = self.history.on
            self.history.on = False
            t = self.t_ps
            try:
                for d in scans:
                    for _ in range(4 * len(seen)):
                        m = self.N.parts[d["part"]]
                        m.state ^= 1
                        self.settle([d["part"]])
                        self.edges()
                        _, digits, _ = self._show(self.all_values())
                        for k, bits in digits.items():
                            seen[k] |= bits
            finally:
                self.history.on = hon
                self.t_ps = t
            st["digits"] = seen
            st["nets"] = self.all_values()
        return st

    def power_cycle(self):
        """Switch off and on again: chips back to their power-up state (EEPROMs keep
        their contents, RAM is cleared), switches stay where they are."""
        for pid, m in self.active.items():
            m.reset()
        for n in self.nets:
            self.nets[n] = self.rails.get(n, 0)
        for d in self.drv.values():
            d.clear()
        for ep in self.edgepins.values():
            for k in ep:
                ep[k] = None
        self.update(full=True)
        return self
