"""Problem reports shared by the simulators, the netlist and the breadboard checker.

Every problem is a plain dict:
    {"severity": "error" | "warning", "kind": ..., "message": "...", "where": {...}}
plus "t_ns" for problems found while simulating. Kinds:
    contention    two strong drivers on one net at once
    floating      a chip input reads a floating ("Z") or unknown ("X") net
    unconnected   a chip input pin is on no net
    no-driver     a net is read but nothing can ever drive it
    eeprom-write  an EEPROM was written in circuit
    oscillation   the logic did not settle, or a net toggles far too fast
    levels        a chip output's high level (VOH) is below a reader's input threshold (VIH),
                  e.g. a 555 or a memory driving a 74HC input (warning; use 74HCT)
    setup, hold   a clocked input changed too close to the clock edge (timed only)
    short         two rails joined by a switch; breadboard: two nets joined
    missing       breadboard: a net is in more than one piece
    unplaced, hole, part, net, power   (netlist and breadboard checks)
"""


class Problems:
    """Collects problems, once per distinct message (``all`` keeps every occurrence count)."""

    def __init__(self):
        self.items = []
        self._index = {}

    def add(self, kind, message, severity="error", where=None, t_ns=None):
        key = (kind, message)
        if key in self._index:
            self._index[key]["count"] += 1
            return False
        d = {"severity": severity, "kind": kind, "message": message, "where": where or {}, "count": 1}
        if t_ns is not None:
            d["t_ns"] = t_ns
        self._index[key] = d
        self.items.append(d)
        return True

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def errors(self):
        return [p for p in self.items if p["severity"] == "error"]


def static_checks(N, rails):
    """Problems visible without simulating: unconnected chip inputs, chip power pins not
    on their rail, nets read with no possible driver. Returns (problem dicts, seed-style
    messages) so the old API keeps its exact wording."""
    from .netlist import is_active
    out, msgs = [], []
    readers = {}
    driven = set(rails)
    for pid, model in N.parts.items():
        pn = N.pinnet[pid]
        if is_active(model):
            missing = [model.PINS[n][0] for n in model.PINS if n not in pn and model.PINS[n][1] in ("in", "clk")]
            if missing:
                m = f"{pid} {model.TYPE}: unconnected input pins {missing}"
                msgs.append(m)
                out.append({"severity": "error", "kind": "unconnected", "message": m,
                            "where": {"part": pid, "pins": missing}})
            for n, (name, kind) in model.PINS.items():
                net = pn.get(n)
                if kind in ("vcc", "gnd"):
                    want = 1 if kind == "vcc" else 0
                    if net is None or rails.get(net) != want:
                        m = f"{pid} pin {n} ({name}) should be on {'VCC' if want else 'GND'}" + \
                            (f", not {net}" if net else ", but it is not connected")
                        out.append({"severity": "warning", "kind": "power", "message": m,
                                    "where": {"part": pid, "pin": str(n)}})
                if net is None:
                    continue
                if kind in ("in", "clk", "io"):
                    readers.setdefault(net, set()).add(pid)
                if kind in ("out", "tri", "io"):
                    driven.add(net)
        else:
            for a, b, strength, ohms, who in _all_links(model):
                na, nb = pn.get(a), pn.get(b)
                if na is None or nb is None:
                    continue
                if strength == "weak":
                    if na in rails:
                        driven.add(nb)
                    if nb in rails:
                        driven.add(na)
            if getattr(model, "CATEGORY", "") == "switch":
                driven.update(pn.values())
    # nets joined by resistors to a driven net count as driven (followers)
    weak_adj = {}
    for pid, model in N.parts.items():
        if is_active(model):
            continue
        pn = N.pinnet[pid]
        for a, b, strength, ohms, who in _all_links(model):
            if strength == "weak" and pn.get(a) and pn.get(b):
                weak_adj.setdefault(pn[a], set()).add(pn[b])
                weak_adj.setdefault(pn[b], set()).add(pn[a])
    stack = [n for n in driven if n in weak_adj]
    while stack:
        n = stack.pop()
        for m in weak_adj.get(n, ()):
            if m not in driven:
                driven.add(m)
                stack.append(m)
    out += level_checks(N)
    for net in N.nets:
        if net in readers and net not in driven:
            m = f"net {net} read by {sorted(readers[net])} has no driver at all"
            msgs.append(m)
            out.append({"severity": "error", "kind": "no-driver", "message": m,
                        "where": {"net": net, "parts": sorted(readers[net])}})
    return out, msgs, driven


def level_checks(N):
    """Warnings for chip outputs whose guaranteed high level (VOH) is below the input
    threshold (VIH) of a chip that reads the same net: one warning per reader chip."""
    from .netlist import is_active
    drivers, readers = {}, {}
    for pid, model in N.parts.items():
        if not is_active(model) or not hasattr(model, "levels"):
            continue
        lv = model.levels()
        pn = N.pinnet[pid]
        # a transceiver with DIR tied to a rail only ever reads one side (74x245: DIR high = A to B)
        side_in = None
        if "DIR" in model.names:
            d = pn.get(model.names["DIR"])
            side_in = {"VCC": "A", "GND": "B"}.get(d)
        for n, net in pn.items():
            name, kind = model.PINS[n]
            if kind in ("out", "tri", "io") and lv["VOH"] is not None:
                drivers.setdefault(net, []).append((pid, name, lv["VOH"]))
            if kind == "io" and side_in and not name.startswith(side_in):
                continue
            if kind in ("in", "clk", "io") and lv["VIH"] is not None:
                readers.setdefault(net, []).append((pid, name, lv["VIH"]))
    low = {}
    for net, rs in readers.items():
        for rid, rpin, vih in rs:
            for did, dpin, voh in drivers.get(net, ()):
                if did != rid and voh < vih:
                    low.setdefault(rid, {}).setdefault(did, []).append(net)
    out = []
    for rid in sorted(low):
        rt = N.parts[rid]
        for did in sorted(low[rid]):
            dt = N.parts[did]
            nets = sorted(set(low[rid][did]))
            fix = rt.TYPE.replace("74HC", "74HCT", 1) if rt.TYPE.startswith("74HC") and \
                not rt.TYPE.startswith("74HCT") else None
            m = (f"{did} {dt.TYPE} drives {rid} {rt.TYPE} on {', '.join(nets)}: its high level "
                 f"(VOH {dt.levels()['VOH']:g} V) is below the {rt.TYPE}'s input threshold "
                 f"(VIH {rt.levels()['VIH']:g} V)" + (f"; use a {fix}" if fix else ""))
            out.append({"severity": "warning", "kind": "levels", "message": m,
                        "where": {"part": rid, "driver": did, "nets": nets}})
    return out


def _all_links(model):
    """Every link a passive can ever make (switches as if closed)."""
    links = list(model.links())
    if getattr(model, "CATEGORY", "") == "switch":
        st = model.state
        try:
            if isinstance(st, list):
                model.state = [True] * len(st)
                links += model.links()
            elif hasattr(model, "positions"):
                for k in (0, 1):
                    model.state = k
                    links += model.links()
            else:
                model.state = True
                links += model.links()
        finally:
            model.state = st
    return links
