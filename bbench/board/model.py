"""The 830-point breadboard of the book, and where each part's legs go.

Rows 1-63; holes a-e (bottom half) and f-j (top half). The five holes of one half-row
are joined underneath, so a half-row is one electrical node. Two power rails run along
each long edge: B- and B+ next to row a, T- and T+ next to row j. In the book the inner
rail (B-, T-) is GND and the outer rail (B+, T+) is +5 V; a board can say otherwise
with "rails": {"T+": "VCC", "T-": "GND", "B+": "VCC", "B-": "GND"}.

Placements (project format):
  {"part": "U7", "row": 2, "hole": "e"}          fixed footprints: pin 1 at that hole
  {"part": "R1", "legs": {"1": [12, "d"], "2": [12, "f"]}}   leaded parts, leg by leg;
         a leg may go into a rail: "T-" or ["T-", 12]
Wire ends: [row, "hole"], or a rail "B-" / ["B-", row].
"""
ROWS = 63
COLS = "abcdefghij"
BOT, TOP = "abcde", "fghij"
RAILS = ("T+", "T-", "B+", "B-")
DEFAULT_RAILS = {"T+": "VCC", "T-": "GND", "B+": "VCC", "B-": "GND"}
X = {c: i for i, c in enumerate("abcde")}
X.update({c: i + 7 for i, c in enumerate("fghij")})       # 0.1 in units; gap = 0.3 in


def half(col):
    return "B" if col in BOT else "T"


def mirror(col):
    """The hole in the same position across the centre gap: a-j, b-i, c-h, d-g, e-f."""
    return COLS[9 - COLS.index(col)]


def across(col, width=3):
    """Where the other row of a DIP goes: width pitches (0.1 in) further across the board.
    Holes are 0.1 in apart and the centre gap is 0.3 in, so a 0.3 in chip with pin 1 in e
    has its other row in f, and a 0.6 in chip (or a 0.56 in digit) with pin 1 in c has its
    other row in g. None when that is not a hole (or pin 1 is not in the bottom half)."""
    if col not in BOT:
        return None
    want = X[col] + (width or 3)
    return next((c for c in COLS if X[c] == want), None)


def footprint_of(cls):
    fp = getattr(cls, "FOOTPRINT", None)
    if fp:
        return fp
    return {"kind": "dip", "width": cls.width()}           # chips


def is_rail(end):
    return isinstance(end, str) or (isinstance(end, (list, tuple)) and end and isinstance(end[0], str))


def rail_of(end):
    return end if isinstance(end, str) else end[0]


def legs(cls, placement):
    """[(pin number, ("H", row, col)) or (pin number, ("R", rail))] and the holes a wide
    chip body covers. Raises ValueError for a footprint that cannot be placed."""
    out = []
    blocked = []
    if "legs" in placement:
        for pin, end in placement["legs"].items():
            n = int(pin) if str(pin).isdigit() else cls.pin_number(pin)
            if is_rail(end):
                out.append((n, ("R", rail_of(end))))
            else:
                out.append((n, ("H", int(end[0]), str(end[1]))))
        return out, blocked
    fp = footprint_of(cls)
    kind = fp["kind"]
    row, col = int(placement["row"]), str(placement["hole"])
    if col not in COLS:
        raise ValueError(f"no hole {col!r}")
    n = len(cls.PINS)
    if kind == "dip":
        w = fp.get("width", 3)
        top = across(col, w)
        if top is None:
            raise ValueError(f"a {w * 0.1:.1f} in DIP cannot have pin 1 in hole {col}: its other row would miss the holes")
        h = n // 2
        for p in range(1, n + 1):
            if p <= h:
                out.append((p, ("H", row + p - 1, col)))
            else:
                out.append((p, ("H", row + (n - p), top)))
        for c in COLS:
            if X[col] < X[c] < X[top]:
                for r in range(row, row + h):
                    blocked.append((r, c))
    elif kind == "sip":
        pitch = fp.get("pitch", 1)
        for i, p in enumerate(sorted(cls.PINS)):
            out.append((p, ("H", row + i * pitch, col)))
    elif kind == "button":
        top = mirror(col) if col in BOT else None
        if top is None:
            raise ValueError("a button must straddle the centre gap (pin 1 in a-e)")
        out += [(1, ("H", row, col)), (2, ("H", row, top)), (3, ("H", row + 2, col)), (4, ("H", row + 2, top))]
    elif kind == "leads":
        raise ValueError("a leaded part is placed leg by leg (\"legs\")")
    elif kind == "virtual":
        return [], []
    else:
        raise ValueError(f"unknown footprint {kind}")
    return out, blocked
