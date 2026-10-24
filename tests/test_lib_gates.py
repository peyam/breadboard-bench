"""Function tables of the extended gate library (datasheet rows, X expanded)."""
import itertools

import pytest

from bbench.chips import get
from libcheck import getter, check_pins, expand

FAMS = ("74HC", "74HCT")


def _gate_rows(n, kind):
    """The datasheet function table of one n-input gate, as {inputs..., 'Y'} rows."""
    names = "ABCDEFGH"[:n]
    if kind == "NAND":       # all H -> L; any L -> H
        rows = [dict({c: 1 for c in names}, Y=0)]
        rows += [dict({c: (0 if c == d else "X") for c in names}, Y=1) for d in names]
    elif kind == "AND":      # all H -> H; any L -> L
        rows = [dict({c: 1 for c in names}, Y=1)]
        rows += [dict({c: (0 if c == d else "X") for c in names}, Y=0) for d in names]
    elif kind == "NOR":      # any H -> L; all L -> H
        rows = [dict({c: 0 for c in names}, Y=1)]
        rows += [dict({c: (1 if c == d else "X") for c in names}, Y=0) for d in names]
    elif kind == "NOT":
        rows = [{"A": 0, "Y": 1}, {"A": 1, "Y": 0}]
    return rows


CASES = [  # number, inputs per gate, kind, gates {output: input prefix}, Y-pin naming
    ("10", 3, "NAND", "123"), ("11", 3, "AND", "123"), ("27", 3, "NOR", "123"),
    ("20", 4, "NAND", "12"), ("21", 4, "AND", "12"), ("132", 2, "NAND", "1234"),
    ("14", 1, "NOT", "123456"),
]


@pytest.mark.parametrize("fam", FAMS)
@pytest.mark.parametrize("num,n,kind,units", CASES)
def test_gate_function_table(fam, num, n, kind, units):
    t = fam + num
    cls = get(t)
    check_pins(t, 14, 14, 7)
    chip = cls("U1")
    ins = [nm for nm, k in cls.PINS.values() if k == "in"]
    assert len(ins) == n * len(units)
    for row in _gate_rows(n, kind):
        for r in expand(row):
            for u in units:                         # this gate gets the row, the others get 0 or 1
                for other in (0, 1):
                    vals = {p: other for p in ins}
                    for c in "ABCDEFGH"[:n]:
                        vals[f"{u}{c}"] = r[c]
                    out = chip.eval(getter(vals))
                    assert out[f"{u}Y"] == r["Y"], (t, u, r)


@pytest.mark.parametrize("fam", FAMS)
def test_30_function_table(fam):
    t = fam + "30"
    check_pins(t, 14, 14, 7)
    cls = get(t)
    assert [cls.PINS[p][1] for p in (9, 10, 13)] == ["nc"] * 3
    chip = cls("U1")
    for row in _gate_rows(8, "NAND"):
        for r in expand(row):
            assert chip.eval(getter(r))["Y"] == r["Y"]


@pytest.mark.parametrize("fam", FAMS)
def test_20_21_nc_pins(fam):
    for num in ("20", "21"):
        cls = get(fam + num)
        assert cls.PINS[3][1] == "nc" and cls.PINS[11][1] == "nc"


def test_pin_numbers_spot_check():
    """A few pins checked against the datasheet pin tables."""
    assert get("74HCT10").PINS[12] == ("1Y", "out") and get("74HCT10").PINS[13] == ("1C", "in")
    assert get("74HC20").PINS[6] == ("1Y", "out") and get("74HC20").PINS[8] == ("2Y", "out")
    assert get("74HCT30").PINS[8] == ("Y", "out") and get("74HCT30").PINS[11] == ("G", "in")
    assert get("74HC132").PINS[3] == ("1Y", "out") and get("74HC132").PINS[11] == ("4Y", "out")
    assert get("74HCT14").PINS[8] == ("4Y", "out") and get("74HCT14").PINS[9] == ("4A", "in")


def test_tpd_values():
    assert get("74HC10").tpd("1A", "1Y") == 24 and get("74HCT11").tpd("1A", "1Y") == 28
    assert get("74HCT14").tpd("1A", "1Y") == 32 and get("74HC14").tpd("1A", "1Y") == 25
    assert get("74HC30").tpd("A", "Y") == 18 and get("74HCT30").tpd("A", "Y") == 28
