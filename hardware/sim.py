"""Event-driven, zero-delay, chip-pin-level simulator for the PC-2 netlist.

It checks, at every settled half clock cycle:
- no net is driven by two outputs at once (bus contention);
- no chip input reads a floating (undriven) net;
- no EEPROM is ever written in circuit.

Registers sample their inputs at the clock edge using the values settled just
before the edge (setup is assumed met), then all of them change together.
"""
from collections import defaultdict, deque
from chips import Z, FloatingInput
from netlist import RAILS

X = "X"


class Floating(Exception):
    pass


class Sim:
    def __init__(self, N):
        self.N = N
        self.nets = {}
        self.readers = defaultdict(set)
        self.drv = defaultdict(dict)        # net -> {(ref, pin): value}
        self.errors = []
        self.contention = set()
        self.pin_of = {}
        self.edgepins = {}
        for ref, pc in N.chips.items():
            pm = {}
            for n, net in pc.pinnet.items():
                name, kind = pc.cls.PINS[n]
                pm[name] = net
                if kind in ("in", "clk", "io"):
                    self.readers[net].add(ref)
            self.pin_of[ref] = pm
            missing = [pc.cls.PINS[n][0] for n in pc.cls.PINS
                       if n not in pc.pinnet and pc.cls.PINS[n][1] in ("in", "clk")]
            if missing and pc.cls.TYPE != "NE555":
                self.errors.append(f"{ref} {pc.cls.TYPE}: unconnected input pins {missing}")
            self.edgepins[ref] = {p: None for p in pc.cls.EDGE}
        for net in N.nets():
            self.nets[net] = RAILS.get(net, 0)
        self.strong_ext = {}
        self.weak = {}
        for p in N.parts.values():
            if p.kind == "R" and p.note in ("pull-down", "pull-up"):
                a, b = p.pins["1"], p.pins["2"]
                rail, net = (a, b) if a in RAILS else (b, a)
                self.weak[net] = RAILS[rail]
            if p.kind == "RN":
                for k, net in p.pins.items():
                    if k != "C":
                        self.weak[net] = RAILS[p.pins["C"]]
        self.refresh_switches()
        # static check: every net read by a chip input must have some possible driver
        self.driven_somehow = set(self.weak) | set(RAILS)
        for ref, pc in N.chips.items():
            for n, net in pc.pinnet.items():
                if pc.cls.PINS[n][1] in ("out", "tri", "io"):
                    self.driven_somehow.add(net)
        for p in N.parts.values():
            if p.kind in ("SW", "BTN", "SPDT"):
                self.driven_somehow.update(p.pins.values())
        for net, refs in self.readers.items():
            if net not in self.driven_somehow:
                self.errors.append(f"net {net} read by {sorted(refs)} has no driver at all")

    # ------------------------------------------------------------------ helpers
    def refresh_switches(self):
        self.strong_ext = defaultdict(list)
        for p in self.N.parts.values():
            if p.kind in ("SW", "BTN") and p.closed:
                a, b = p.pins["1"], p.pins["2"]
                if a in RAILS:
                    self.strong_ext[b].append((p.ref, RAILS[a]))
                elif b in RAILS:
                    self.strong_ext[a].append((p.ref, RAILS[b]))
            if p.kind == "SPDT" and p.pos:
                com, thr = p.pins["COM"], p.pins[p.pos]
                if thr in RAILS:
                    self.strong_ext[com].append((p.ref, RAILS[thr]))
                elif com in RAILS:
                    self.strong_ext[thr].append((p.ref, RAILS[com]))

    def getter(self, ref):
        pm = self.pin_of[ref]
        nets = self.nets

        def g(name):
            v = nets[pm[name]]
            if v == Z or v == X:
                raise FloatingInput(f"{ref}.{name} reads {v} on net {pm[name]}")
            return v
        return g

    def resolve(self, net):
        if net in RAILS:
            return RAILS[net]
        d = [v for v in self.drv[net].values() if v != Z]
        ext = self.strong_ext.get(net, [])
        vals = d + [v for _, v in ext]
        if len(vals) > 1:
            who = [k for k, v in self.drv[net].items() if v != Z] + [r for r, _ in ext]
            self._pending_contention.add((net, tuple(sorted(map(str, who)))))
        if vals:
            return vals[0] if len(set(vals)) == 1 else X
        if net in self.weak:
            return self.weak[net]
        if not self.drv[net] and net not in self.driven_somehow:
            return Z
        if not self.drv[net]:
            return self.nets[net]          # driver not evaluated yet (power-up)
        return Z

    # ------------------------------------------------------------------ settle
    def settle(self, todo=None, limit=20000):
        self._pending_contention = set()
        q = deque(todo if todo is not None else self.N.chips.keys())
        inq = set(q)
        float_wait = set()
        steps = 0
        while q:
            steps += 1
            if steps > limit:
                raise RuntimeError("logic did not settle (oscillation?)")
            ref = q.popleft()
            inq.discard(ref)
            pc = self.N.chips[ref]
            g = self.getter(ref)
            try:
                if pc.model.asyncupd(g):
                    pass
                outs = pc.model.eval(g)
                float_wait.discard(ref)
            except FloatingInput:
                float_wait.add(ref)
                continue
            dirty = []
            pm = self.pin_of[ref]
            for name, v in outs.items():
                if name not in pm:
                    continue
                net = pm[name]
                key = (ref, name)
                if self.drv[net].get(key) != v:
                    self.drv[net][key] = v
                    dirty.append(net)
            for net in dirty:
                nv = self.resolve(net)
                if self.nets[net] != nv:
                    self.nets[net] = nv
                    for r in self.readers[net]:
                        if r not in inq:
                            q.append(r)
                            inq.add(r)
            # memories: a write changes state that this chip itself may read back
        # final checks on the settled state
        self._pending_contention = set()
        for net in list(self.drv):
            self.resolve(net)
        for c in self._pending_contention:
            self.contention.add(c)
        for ref in list(float_wait):
            try:
                self.N.chips[ref].model.eval(self.getter(ref))
            except FloatingInput as e:
                self.errors.append(f"floating input: {e}")
        return self

    def full_resolve(self):
        self._pending_contention = set()
        for net in self.nets:
            if net in RAILS:
                continue
            nv = self.resolve(net)
            self.nets[net] = nv

    # ------------------------------------------------------------------ edges
    def edges(self):
        rounds = 0
        while True:
            rounds += 1
            if rounds > 50:
                raise RuntimeError("edge cascade did not stop")
            fired = []
            for ref, ep in self.edgepins.items():
                pm = self.pin_of[ref]
                for pin, last in ep.items():
                    v = self.nets[pm[pin]]
                    kind = self.N.chips[ref].cls.EDGE[pin]
                    if last is not None and last != v:
                        if (kind == "rise" and last == 0 and v == 1) or (kind == "fall" and last == 1 and v == 0):
                            fired.append((ref, pin))
                    ep[pin] = v
            if not fired:
                return
            new = []
            for ref, pin in fired:
                m = self.N.chips[ref].model
                try:
                    new.append((ref, m.edge(self.getter(ref), pin)))
                except FloatingInput as e:
                    self.errors.append(f"floating input at clock edge: {e}")
            for ref, st in new:
                self.N.chips[ref].model.state = st
            self.settle([r for r, _ in new])

    def step(self):
        """Settle, then fire any clock edges, then settle again."""
        self.refresh_switches()
        self.full_resolve()
        self.settle()
        self.edges()
        return self

    def v(self, net):
        return self.nets[net]

    def word(self, prefix, n):
        bits = [self.nets[f"{prefix}{i}"] for i in range(n)]
        if any(b not in (0, 1) for b in bits):
            return None
        return sum(b << i for i, b in enumerate(bits))
