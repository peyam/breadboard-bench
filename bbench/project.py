"""Projects: the .bbproj file format (DESIGN section 3) and the public Python API.

A project is kept as the plain dict it was loaded from, so saving gives back exactly
what was loaded (keys the engine does not know about are kept too).
"""
import copy
import json
import os

from .core.netlist import Netlist, lookup_type
from .core.engine import ZeroDelaySim
from .core.timed import TimedSim
from .core.checks import static_checks

FORMAT = "breadboard-bench/1"


def new_project(name="Untitled", notes=""):
    return {"format": FORMAT, "name": name, "notes": notes, "parts": [], "nets": [],
            "schematic": {"wires": [], "labels": []}, "breadboards": [], "links": [],
            "stimuli": [], "probes": []}


class Project:
    def __init__(self, data=None):
        self.data = data if data is not None else new_project()

    # ------------------------------------------------------------------ files
    @classmethod
    def load(cls, src):
        """From JSON text, a dict (copied), or a path to a .bbproj file."""
        if isinstance(src, Project):
            return cls(copy.deepcopy(src.data))
        if isinstance(src, dict):
            data = copy.deepcopy(src)
        elif isinstance(src, (bytes, bytearray)):
            data = json.loads(src.decode("utf-8"))
        elif isinstance(src, str) and src.lstrip().startswith("{"):
            data = json.loads(src)
        elif isinstance(src, (str, os.PathLike)) and os.path.exists(src):
            with open(src, encoding="utf-8") as f:
                data = json.load(f)
        else:
            raise ValueError("Project.load needs JSON text, a dict or a .bbproj path")
        fmt = data.get("format")
        if fmt is not None and not str(fmt).startswith("breadboard-bench/"):
            raise ValueError(f"not a Breadboard Bench project (format {fmt!r})")
        return cls(data)

    def to_dict(self):
        return copy.deepcopy(self.data)

    def dumps(self):
        return json.dumps(self.data, indent=1, ensure_ascii=False) + "\n"

    def save(self, path=None):
        """JSON text of the project; also written to path when given."""
        text = self.dumps()
        if path is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return text

    # ------------------------------------------------------------------ access
    @property
    def name(self):
        return self.data.get("name", "")

    def part(self, pid):
        for p in self.data.get("parts", []):
            if p["id"] == pid:
                return p
        raise KeyError(pid)

    def netlist(self):
        return Netlist.from_project(self.data)

    # ------------------------------------------------------------------ checks
    def check(self):
        """Every problem found without running: netlist, schematic and breadboards.
        [{"severity", "kind", "message", "where"}]"""
        N = self.netlist()
        out = list(N.problems)
        st, _, _ = static_checks(N, N.rails())
        out += st
        ids = [p.get("id") for p in self.data.get("parts", [])]
        for pid in sorted({i for i in ids if ids.count(i) > 1}):
            out.append({"severity": "error", "kind": "part", "message": f"part id {pid} is used twice",
                        "where": {"part": pid}})
        nets = set(N.nets)
        for lab in self.data.get("schematic", {}).get("labels", []):
            if lab.get("net") not in nets:
                out.append({"severity": "warning", "kind": "net",
                            "message": f"schematic label {lab.get('net')} names no net", "where": {"net": lab.get("net")}})
        for pr in self.data.get("probes", []):
            if pr not in nets:
                out.append({"severity": "warning", "kind": "net", "message": f"probe {pr} names no net",
                            "where": {"net": pr}})
        for pid, m in N.parts.items():
            if not N.pinnet[pid] and getattr(m, "FOOTPRINT", {}).get("kind") != "virtual":
                out.append({"severity": "warning", "kind": "part", "message": f"{pid} is not connected to anything",
                            "where": {"part": pid}})
        if self.data.get("breadboards"):
            from .board.checker import check_boards
            out += check_boards(self.data, N)
        return out

    # ------------------------------------------------------------------ simulation
    def simulator(self, mode="zero", record=True, **kw):
        N = self.netlist()
        stim = self.data.get("stimuli", [])
        if mode in ("zero", "zero-delay", "fast"):
            return ZeroDelaySim(N, stim, record=record, **kw)
        if mode in ("timed", "time", "real"):
            return TimedSim(N, stim, record=record, **kw)
        raise ValueError(f"unknown simulator mode {mode!r} (zero or timed)")


def library():
    """Every chip and part type: [{type, desc, family, category, pins: [[n, name, kind]], datasheet, ...}]"""
    from . import chips, parts
    out = [chips.REGISTRY[t].info() for t in sorted(chips.REGISTRY)]
    seen = set()
    for t in sorted(parts.PARTS):
        cls = parts.PARTS[t]
        if cls in seen:
            continue
        seen.add(cls)
        out.append(cls.info())
    return out


__all__ = ["Project", "library", "new_project", "lookup_type", "FORMAT"]
