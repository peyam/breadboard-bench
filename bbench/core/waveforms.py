"""Waveform history, trace JSON and VCD output.

History is kept in integer picoseconds: {net: [(t_ps, value), ...]}; the first entry
of each net is its value when recording started.
"""


class History:
    def __init__(self, keep=None):
        self.changes = {}
        self.on = True
        self.only = None          # None = every net, else a set of nets
        self.keep = keep          # None = keep everything, else at most this many changes per net

    def start(self, values, t_ps, nets=None):
        self.only = set(nets) if nets is not None else None
        self.changes = {}
        for n, v in values.items():
            if self.only is None or n in self.only:
                self.changes[n] = [(t_ps, v)]
        self.on = True

    def add(self, net, t_ps, v):
        if not self.on or (self.only is not None and net not in self.only):
            return
        lst = self.changes.get(net)
        if lst is None:
            self.changes[net] = [(t_ps, v)]
        elif lst[-1][0] == t_ps:
            if len(lst) > 1 and lst[-2][1] == v:
                lst.pop()
            else:
                lst[-1] = (t_ps, v)
        elif lst[-1][1] != v:
            lst.append((t_ps, v))
            if self.keep and len(lst) > self.keep:
                del lst[:len(lst) - self.keep // 2]      # drop the oldest half


def _ns(t_ps):
    return t_ps // 1000 if t_ps % 1000 == 0 else t_ps / 1000.0


def trace(history, nets, current=None):
    """{"t_unit": "ns", "signals": [{"name", "changes": [[t, v], ...]}]}"""
    sig = []
    for n in nets:
        ch = history.changes.get(n)
        if ch is None and current is not None and n in current:
            ch = [(0, current[n])]
        sig.append({"name": n, "changes": [[_ns(t), v] for t, v in (ch or [])]})
    return {"t_unit": "ns", "signals": sig}


def _ident(k):
    chars = [chr(c) for c in range(33, 127)]
    s = ""
    k += 1
    while k:
        k, r = divmod(k - 1, len(chars))
        s = chars[r] + s
    return s


def to_vcd(trace_json, scope="bench", comment="Breadboard Bench"):
    """Standard VCD text from trace JSON (times in ns -> timescale 1 ps)."""
    sigs = trace_json["signals"]
    lines = [f"$comment {comment} $end", "$version Breadboard Bench engine $end",
             "$timescale 1ps $end", f"$scope module {scope} $end"]
    ids = {}
    for k, s in enumerate(sigs):
        ids[s["name"]] = _ident(k)
        name = "".join(c if c > " " else "_" for c in s["name"])
        lines.append(f"$var wire 1 {ids[s['name']]} {name} $end")
    lines += ["$upscope $end", "$enddefinitions $end"]
    events = {}
    for s in sigs:
        for t, v in s["changes"]:
            events.setdefault(int(round(t * 1000)), []).append((ids[s["name"]], v))
    first = True
    for t in sorted(events):
        lines.append(f"#{t}")
        if first:
            lines.append("$dumpvars")
        for i, v in events[t]:
            ch = {0: "0", 1: "1", "Z": "z", "X": "x"}.get(v, "x")
            lines.append(f"{ch}{i}")
        if first:
            lines.append("$end")
            first = False
    return "\n".join(lines) + "\n"


def parse_vcd(text):
    """Small VCD reader (for tests and the app's import): {name: [(t, v), ...]} in the file's units."""
    names, out, t = {}, {}, 0
    tokens = text.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "$var":
            ident, name = tokens[i + 3], tokens[i + 4]
            names[ident] = name
            out[name] = []
            while tokens[i] != "$end":
                i += 1
        elif tok in ("$comment", "$version", "$timescale", "$scope", "$upscope", "$date"):
            while tokens[i] != "$end":
                i += 1
        elif tok in ("$enddefinitions", "$dumpvars", "$end"):
            pass
        elif tok.startswith("#"):
            t = int(tok[1:])
        elif tok[0] in "01xzXZ":
            out[names[tok[1:]]].append((t, tok[0]))
        else:
            raise ValueError(f"bad VCD token {tok!r}")
        i += 1
    return out
