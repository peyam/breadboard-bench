"""Breadboard checker (generalised from pc2sim/layout.py check()).

It rebuilds the circuit purely from where the legs and wires are, and compares it
with the netlist: every net must come out as one connected piece, no two nets may
touch, every part must be placed, and no hole may hold two things.
"""
from ..core.netlist import Netlist, lookup_type
from .model import ROWS, COLS, RAILS, DEFAULT_RAILS, half, legs, is_rail, rail_of, footprint_of


def _p(severity, kind, message, **where):
    return {"severity": severity, "kind": kind, "message": message, "where": where}


def check_boards(data, N=None):
    """Problems [{severity, kind, message, where}] of the project's breadboards."""
    if N is None:
        N = Netlist.from_project(data)
    problems = []
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    boards = data.get("breadboards", [])
    bid_ok = {bb.get("id") for bb in boards}
    pin_point = {}            # (part, pin) -> node
    pin_hole = {}             # (part, pin) -> [board, row, col] or [board, rail]
    occupied = {}             # (board, row, col) -> what
    blocked = {}
    placed = set()

    def hole_node(bid, row, col, what):
        if not (1 <= row <= ROWS) or col not in COLS:
            problems.append(_p("error", "hole", f"{what}: there is no hole {row}{col} on {bid}",
                               board=bid, hole=[row, col]))
            return None
        key = (bid, row, col)
        if key in occupied:
            problems.append(_p("error", "hole", f"hole {row}{col} on {bid} is used twice: {occupied[key]} and {what}",
                               board=bid, hole=[row, col]))
        else:
            occupied[key] = what
        return ("N", bid, row, half(col))

    def end_node(bid, end, what):
        if is_rail(end):
            r = rail_of(end)
            if r not in RAILS:
                problems.append(_p("error", "hole", f"{what}: no rail {r} on {bid}", board=bid))
                return None
            return ("R", bid, r)
        return hole_node(bid, int(end[0]), str(end[1]), what)

    for bb in boards:
        bid = bb.get("id")
        rails = dict(DEFAULT_RAILS)
        rails.update(bb.get("rails", {}))
        for r, net in rails.items():
            if net:
                union(("R", bid, r), ("NET", net))
        for pl in bb.get("placements", []):
            pid = pl.get("part")
            if pid not in N.parts:
                problems.append(_p("error", "unplaced", f"{bid} places {pid}, which is not in the parts list",
                                   board=bid, part=pid))
                continue
            if pid in placed:
                problems.append(_p("error", "hole", f"{pid} is placed twice", board=bid, part=pid))
            placed.add(pid)
            cls = type(N.parts[pid])
            try:
                lg, bl = legs(cls, pl)
            except (ValueError, KeyError) as e:
                problems.append(_p("error", "hole", f"{pid}: {e}", board=bid, part=pid))
                continue
            for r, c in bl:
                blocked[(bid, r, c)] = pid
            for pin, loc in lg:
                what = f"{pid} pin {pin}"
                if loc[0] == "H":
                    node = hole_node(bid, loc[1], loc[2], what)
                    pin_hole[(pid, pin)] = [bid, loc[1], loc[2]]
                else:
                    node = end_node(bid, loc[1], what)
                    pin_hole[(pid, pin)] = [bid, loc[1]]
                if node is not None:
                    pin_point[(pid, pin)] = node
        for k, w in enumerate(bb.get("wires", [])):
            what = f"wire {k + 1}"
            a = end_node(bid, w.get("a"), what)
            b = end_node(bid, w.get("b"), what)
            if a is not None and b is not None:
                union(a, b)
    for key, pid in blocked.items():
        if key in occupied and not occupied[key].startswith(pid + " "):
            problems.append(_p("error", "hole", f"hole {key[1]}{key[2]} on {key[0]} is under the body of {pid} "
                                                f"but holds {occupied[key]}", board=key[0], hole=[key[1], key[2]]))
    for k, ln in enumerate(data.get("links", [])):
        ends = []
        for side in ("a", "b"):
            bid, end = ln[side]
            if bid not in bid_ok:
                problems.append(_p("error", "hole", f"board-to-board wire {k + 1} goes to unknown board {bid}"))
                ends.append(None)
                continue
            ends.append(end_node(bid, end, f"board-to-board wire {k + 1}"))
        if None not in ends:
            union(ends[0], ends[1])
    # parts that join legs inside themselves
    for pid, m in N.parts.items():
        for a, b in getattr(m, "INTERNAL", ()):
            if (pid, a) in pin_point and (pid, b) in pin_point:
                union(pin_point[(pid, a)], pin_point[(pid, b)])
    # every placeable part on a board
    for pid, m in N.parts.items():
        fp = footprint_of(type(m)).get("kind")
        if fp == "virtual" or pid in placed:
            continue
        if N.pinnet[pid]:
            problems.append(_p("warning" if not boards else "error", "unplaced", f"{pid} is not placed on a breadboard",
                               part=pid))
    # expected connectivity
    expect = {}
    for net, pins in N.nets.items():
        for pid, n in pins:
            expect.setdefault(net, []).append((pid, n))
    group_net = {}
    group_pins = {}
    for net, pins in expect.items():
        roots = {}
        for pin in pins:
            pt = pin_point.get(pin)
            if pt is None:
                if pin[0] in placed:
                    problems.append(_p("error", "unplaced", f"{pin[0]} pin {pin[1]} ({net}) is not in a hole",
                                       part=pin[0], pin=str(pin[1]), net=net))
                continue
            roots.setdefault(find(pt), []).append(pin)
        if ("NET", net) in parent:
            rr = find(("NET", net))
            roots.setdefault(rr, [])
        if len(roots) > 1:
            pieces = sorted(roots.values(), key=len, reverse=True)
            problems.append(_p("error", "missing", f"missing connection: {net} is in {len(roots)} separate pieces",
                               net=net, pieces=[[f"{p}.{n}" for p, n in pc] for pc in pieces],
                               holes=[[pin_hole.get(x) for x in pc] for pc in pieces]))
        for r, pc in roots.items():
            if r in group_net and group_net[r] != net:
                other = group_net[r]
                problems.append(_p("error", "short", f"short: {net} is joined to {other}", nets=[other, net],
                                   pins=[f"{p}.{n}" for p, n in group_pins[r] + pc],
                                   holes=[pin_hole.get(x) for x in group_pins[r] + pc]))
            else:
                group_net[r] = net
                group_pins[r] = list(pc)
    # pins that are on no net but touch one
    for (pid, n), pt in pin_point.items():
        if n in N.pinnet.get(pid, {}):
            continue
        r = find(pt)
        if r in group_net:
            problems.append(_p("warning", "short", f"{pid} pin {n} is on no net in the schematic but touches {group_net[r]}",
                               part=pid, pin=str(n), net=group_net[r]))
    return problems


def connectivity(data, N=None):
    """For the app: {board id: {"row:half": net}} as the checker sees the boards."""
    if N is None:
        N = Netlist.from_project(data)
    out = {}
    for bb in data.get("breadboards", []):
        bid = bb["id"]
        m = out.setdefault(bid, {})
        for pl in bb.get("placements", []):
            pid = pl.get("part")
            if pid not in N.parts:
                continue
            try:
                lg, _ = legs(type(N.parts[pid]), pl)
            except (ValueError, KeyError):
                continue
            for pin, loc in lg:
                if loc[0] == "H":
                    net = N.pinnet[pid].get(pin)
                    if net:
                        m[f"{loc[1]}:{half(loc[2])}"] = net
    return out


__all__ = ["check_boards", "connectivity", "lookup_type"]
