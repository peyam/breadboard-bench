"""Schematic placement for generated projects (PC-2 and its modules), sized to the web app's
symbols so that the app can draw them as they are.

The sizes below follow web/js/parts.js (symbol()) and the room the app leaves for net tags
(Schematic.tagRoom): keep them in step. A part's footprint on the sheet is its symbol box
plus, on each side, the width of the longest net tag on that side; the app treats parts as
crowded when these footprints overlap, and only then re-lays a sheet out itself.

    from bbench.projects.sheet import place
    place(project_dict)          # sets x, y, rot of every part; one block per module
"""
from .. import chips, parts as _parts

GRID = 10
CHIP_GAP_X, CHIP_GAP_Y = 60, 50          # between chips (beyond their tags)
ROW_GAP_X, ROW_GAP_Y = 30, 40            # between passives
SHEET_MIN_W = 1240                       # passives wrap at this width (or the chips' width)
MODULE_GAP = 240                         # between module blocks on the "All modules" sheet
MODULES_PER_ROW = 4

_ALIAS = {"BTN": "BUTTON", "7SEG": "7SEG-CA", "JP": "JUMPER3", "JP3": "JUMPER3", "VR": "POT", "RES": "R",
          "CAP": "C", "SPST": "SW", "DIGIT-CA": "7SEG-CA", "DIGIT-CC": "7SEG-CC"}
_PIN_CACHE = {}


def _snap(v):
    return int(round(v / GRID)) * GRID


def _pins(t):
    """[(number, name, kind)] of a chip or part type."""
    if t in _PIN_CACHE:
        return _PIN_CACHE[t]
    if t in chips.REGISTRY:
        info = chips.REGISTRY[t].info()
    elif t in _parts.PARTS:
        info = _parts.PARTS[t].info()
    else:
        info = {"pins": []}
    out = [(str(n), str(name), kind) for n, name, kind in info["pins"]]
    _PIN_CACHE[t] = out
    return out


def _gate_kind(t):
    cls = chips.REGISTRY[t]
    names = {nm for nm, k in cls.PINS.values()}
    d = cls.DESC or ""
    low = d.lower()
    if {"1A", "1Y"} <= names and "1B" not in names and "invert" in low:
        return "not", sum(1 for nm in names if len(nm) == 2 and nm[0].isdigit() and nm[1] == "A")
    if not {"1A", "1B", "1Y"} <= names or "1C" in names:
        return None
    n = sum(1 for nm in names if len(nm) == 2 and nm[0].isdigit() and nm[1] == "Y")
    import re
    for k, pat in (("xnor", r"XNOR"), ("xor", r"XOR|exclusive"), ("nand", r"NAND"), ("nor", r"NOR"),
                   ("and", r"AND"), ("or", r"\bOR\b")):
        if re.search(pat, d, re.I):
            return k, n
    return None


def symbol(t, props=None):
    """{w, h, x0, y0, pins: {pin number: side "L" | "R"}} like parts.js symbol()."""
    t = _ALIAS.get(t, t)
    props = props or {}
    pins = _pins(t)
    by_name = {name: n for n, name, kind in pins}

    def side_of(names_sides):
        return {by_name[nm]: sd for nm, sd in names_sides if nm in by_name}

    if t in chips.REGISTRY:
        g = _gate_kind(t)
        if g:
            k, n = g
            if k == "not":
                sides = side_of([(f"{i}A", "L") for i in range(1, n + 1)] + [(f"{i}Y", "R") for i in range(1, n + 1)])
                h = 50 + n * 30 - 10 + 20
            else:
                sides = side_of([(f"{i}{c}", "L") for i in range(1, n + 1) for c in "AB"] +
                                [(f"{i}Y", "R") for i in range(1, n + 1)])
                h = 40 + n * 60 + 20
            return {"w": 130, "h": h, "x0": 0, "y0": 0, "pins": sides}
        left, right = [], []
        for n, name, kind in pins:
            if kind in ("vcc", "gnd"):
                continue
            if t.endswith("245") and kind == "io":
                (left if name.startswith("A") else right).append(n)
            elif kind in ("in", "clk", "ana"):
                left.append(n)
            else:
                right.append(n)
        if t.endswith("555") and "DIS" in by_name and by_name["DIS"] in left:
            left.remove(by_name["DIS"])
            right.append(by_name["DIS"])
        rows = max(len(left), len(right), 1)
        return {"w": 120, "h": 60 + rows * 20, "x0": 0, "y0": 0,
                "pins": {**{n: "L" for n in left}, **{n: "R" for n in right}}}
    if t == "R":
        return {"w": 60, "h": 20, "x0": 0, "y0": -10, "pins": side_of([("1", "L"), ("2", "R")])}
    if t == "C":
        return {"w": 40, "h": 20, "x0": 0, "y0": -12, "pins": side_of([("1", "L"), ("2", "R"), ("+", "L"), ("-", "R")])}
    if t == "LED":
        return {"w": 60, "h": 30, "x0": 0, "y0": -16, "pins": side_of([("A", "L"), ("K", "R")])}
    if t == "SW":
        return {"w": 50, "h": 30, "x0": 0, "y0": -22, "pins": side_of([("1", "L"), ("2", "R")])}
    if t == "BUTTON":
        return {"w": 50, "h": 56, "x0": 0, "y0": -22,
                "pins": side_of([("1A", "L"), ("1B", "L"), ("2A", "R"), ("2B", "R")])}
    if t in ("SPDT", "JUMPER3"):
        sides = {}
        for n, name, kind in pins:
            sides[n] = "L" if name == "COM" else "R"
        return {"w": 60, "h": 40, "x0": 0, "y0": -22, "pins": sides}
    if t.startswith("DIPSW") and t[5:].isdigit():
        k = int(t[5:])
        return {"w": 60, "h": k * 20 + 20, "x0": 0, "y0": 0,
                "pins": side_of([(f"{i}A", "L") for i in range(1, k + 1)] + [(f"{i}B", "R") for i in range(1, k + 1)])}
    if t.startswith("7SEG"):
        sides = {}
        for n, name, kind in pins:
            sides[n] = "R" if name.startswith("C") and name[1:2] in ("A", "C") else "L"
        return {"w": 70, "h": 180, "x0": 0, "y0": 0, "pins": sides}
    if t == "CLOCK":
        return {"w": 60, "h": 40, "x0": 0, "y0": -20, "pins": side_of([("OUT", "R")])}
    if t == "PROBE":
        return {"w": 50, "h": 30, "x0": 0, "y0": -15, "pins": side_of([("TIP", "L")])}
    # a plain box: the first half of the pins on the left
    half = (len(pins) + 1) // 2
    sides = {n: ("L" if i < half else "R") for i, (n, name, kind) in enumerate(pins)}
    return {"w": 80, "h": 30 + max(half, len(pins) - half) * 20, "x0": 0, "y0": 0, "pins": sides}


def _tag(net):
    """Width the app gives a net tag (Schematic.tagRoom)."""
    return 30 + 6.4 * len(net) * 9.5 / 10.5 + 8


def footprint(part, pin_net):
    """(left, top, right, bottom) of a part's room relative to its (x, y): the symbol box
    with the app's margins (partBBox) widened by its net tags."""
    sym = symbol(part["type"], part.get("props"))
    l = r = 30.0
    for n, side in sym["pins"].items():
        net = pin_net.get((part["id"], n))
        if not net:
            continue
        if side == "L":
            l = max(l, _tag(net))
        elif side == "R":
            r = max(r, _tag(net))
    x0, y0 = sym["x0"], sym["y0"]
    return (x0 - l, y0 - 14, x0 + sym["w"] + r, y0 + sym["h"] + 16)


def _is_switch(t):
    return _ALIAS.get(t, t) in ("SW", "BUTTON", "SPDT", "JUMPER3") or t.startswith("DIPSW")


def _is_chip(t):
    return _ALIAS.get(t, t) in chips.REGISTRY


def _block(parts, pin_net):
    """Lay out one module at (0, 0): chips in up to three columns, passives in rows below.
    Returns {id: (x, y)} and the block's (width, height)."""
    pos = {}
    fps = {p["id"]: footprint(p, pin_net) for p in parts}
    # stand-ins for signals from other modules (props role "input": a switch and its pull-down)
    # go in a column at the left, one pair to a row
    inputs = [p for p in parts if (p.get("props") or {}).get("role") == "input"]
    parts = [p for p in parts if p not in inputs]
    x_in = 0.0
    if inputs:
        rows = []
        for p in inputs:
            if rows and len(rows[-1]) == 1 and not _is_switch(p["type"]):
                rows[-1].append(p)
            else:
                rows.append([p])
        per = 10                                      # rows per column of inputs
        for c0 in range(0, len(rows), per):
            y, col_w = 0.0, 0.0
            for row in rows[c0:c0 + per]:
                x = x_in
                h = max(fps[p["id"]][3] - fps[p["id"]][1] for p in row)
                for p in row:
                    fp = fps[p["id"]]
                    pos[p["id"]] = (_snap(x - fp[0]), _snap(y - fp[1]))
                    x += fp[2] - fp[0] + ROW_GAP_X
                col_w = max(col_w, x - x_in)
                y += h + 10
            x_in += col_w + ROW_GAP_X
        x_in += CHIP_GAP_X - ROW_GAP_X
    chips_ = [p for p in parts if _is_chip(p["type"])]
    other = [p for p in parts if not _is_chip(p["type"])]
    ncol = 1 if len(chips_) <= 2 else 2 if len(chips_) <= 4 else 3
    cols = [[] for _ in range(ncol)]
    heights = [0.0] * ncol
    for c in chips_:                                  # shortest column first, as the app does
        k = heights.index(min(heights))
        fp = fps[c["id"]]
        cols[k].append(c)
        heights[k] += (fp[3] - fp[1]) + CHIP_GAP_Y
    x = x_in
    bottom = max([pos[p["id"]][1] + fps[p["id"]][3] for p in inputs] or [0.0])
    for col in cols:
        if not col:
            continue
        lw = max(-fps[c["id"]][0] for c in col)
        rw = max(fps[c["id"]][2] for c in col)
        y = 0.0
        for c in col:
            fp = fps[c["id"]]
            pos[c["id"]] = (_snap(x + lw), _snap(y - fp[1]))
            y += (fp[3] - fp[1]) + CHIP_GAP_Y
        bottom = max(bottom, y)
        x += lw + rw + CHIP_GAP_X
    width = max(SHEET_MIN_W, x - CHIP_GAP_X)
    y = bottom + (ROW_GAP_Y if chips_ or inputs else 0)
    x, row_h = 0.0, 0.0
    for o in other:
        fp = fps[o["id"]]
        w = fp[2] - fp[0]
        if x > 0 and x + w > width:
            x = 0.0
            y += row_h + ROW_GAP_Y
            row_h = 0.0
        pos[o["id"]] = (_snap(x - fp[0]), _snap(y - fp[1]))
        x += w + ROW_GAP_X
        row_h = max(row_h, fp[3] - fp[1])
    height = y + row_h
    return pos, (width, height)


def place(data, modules=None):
    """Give every part of a project dict a schematic position (x, y, rot 0), one block per
    module (props["module"]), the blocks in rows on the "All modules" sheet."""
    pin_net = {}
    for n in data.get("nets", []):
        for pid, pin in n["pins"]:
            pin_net[(pid, str(pin))] = n["name"]
    order = []
    groups = {}
    for p in data["parts"]:
        m = (p.get("props") or {}).get("module", "")
        if m not in groups:
            groups[m] = []
            order.append(m)
        groups[m].append(p)
    if modules:
        order = [m for m in modules if m in groups] + [m for m in order if m not in modules]
    ox = oy = 0.0
    row_h = 0.0
    for i, m in enumerate(order):
        if i and i % MODULES_PER_ROW == 0:
            ox, oy = 0.0, oy + row_h + MODULE_GAP
            row_h = 0.0
        pos, (w, h) = _block(groups[m], pin_net)
        for p in groups[m]:
            x, y = pos[p["id"]]
            p["x"], p["y"], p["rot"] = _snap(ox + x), _snap(oy + y), 0
        ox += w + MODULE_GAP
        row_h = max(row_h, h)
    return data


def overlaps(data):
    """Pairs of parts of the same module whose footprints overlap (should be none)."""
    pin_net = {}
    for n in data.get("nets", []):
        for pid, pin in n["pins"]:
            pin_net[(pid, str(pin))] = n["name"]
    boxes = []
    for p in data["parts"]:
        l, t, r, b = footprint(p, pin_net)
        boxes.append((p["id"], (p.get("props") or {}).get("module", ""),
                      p["x"] + l, p["y"] + t, p["x"] + r, p["y"] + b))
    out = []
    for i in range(len(boxes)):
        a = boxes[i]
        for j in range(i + 1, len(boxes)):
            c = boxes[j]
            if a[1] == c[1] and a[2] < c[4] - 4 and c[2] < a[4] - 4 and a[3] < c[5] - 4 and c[3] < a[5] - 4:
                out.append((a[0], c[0]))
    return out
