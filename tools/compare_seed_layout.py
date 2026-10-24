"""Check that bbench's PC-2 breadboards match seed/layout.py hole for hole.
    python tools/compare_seed_layout.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from bbench.projects.pc2 import pc2  # noqa: E402
from bbench.board.model import legs, half, is_rail, rail_of  # noqa: E402
from bbench.core.netlist import Netlist  # noqa: E402


def mine():
    p = pc2()
    N = Netlist.from_project(p.data)
    out = {}
    for bb in p.data["breadboards"]:
        holes = set()
        for pl in bb["placements"]:
            lg, _ = legs(type(N.parts[pl["part"]]), pl)
            for pin, loc in lg:
                if loc[0] == "H":
                    holes.add((loc[1], loc[2]))
        for w in bb["wires"]:
            for e in (w["a"], w["b"]):
                if not is_rail(e):
                    holes.add((e[0], e[1]))
        out[bb["name"]] = holes
    for ln in p.data["links"]:
        for side in ("a", "b"):
            bid, e = ln[side]
            name = next(b["name"] for b in p.data["breadboards"] if b["id"] == bid)
            out[name].add((e[0], e[1]))
    links = sorted((next(b["name"] for b in p.data["breadboards"] if b["id"] == l["a"][0]), tuple(l["a"][1]),
                    next(b["name"] for b in p.data["breadboards"] if b["id"] == l["b"][0]), tuple(l["b"][1]))
                   for l in p.data["links"])
    return out, links


def seed():
    sys.path.insert(0, os.path.join(HERE, "..", "seed"))
    import pc2_netlist
    import layout as L
    N = pc2_netlist.build()
    boards, links = L.layout(N)
    assert L.check(N, boards, links) == []
    out = {name: set(B.used) for name, B in boards.items()}
    lk = sorted((l["a"][0], tuple(l["a"][1]), l["b"][0], tuple(l["b"][1])) for l in links)
    return out, lk


if __name__ == "__main__":
    a, la = mine()
    b, lb = seed()
    bad = [n for n in b if a.get(n) != b[n]]
    print("boards differing:", bad or "none")
    for n in bad[:3]:
        print(n, sorted(a[n] ^ b[n])[:10])
    print("links identical:", la == lb, len(la))
    sys.exit(1 if bad or la != lb else 0)
