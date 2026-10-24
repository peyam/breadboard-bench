"""Function tables of the extended shift-register library."""
import pytest

from bbench.chips import get
from libcheck import Bench, check_pins

FAMS = ("74HC", "74HCT")


@pytest.mark.parametrize("fam", FAMS)
def test_164_function_table(fam):
    t = fam + "164"
    check_pins(t, 14, 14, 7)
    Q = [f"Q{i}" for i in range(8)]
    b = Bench(t)
    b.set(MR=1)
    # shift rows: Q0 = DSA AND DSB, Q1..Q7 = previous Q0..Q6
    seq = [(1, 1), (0, 1), (1, 0), (1, 1), (0, 0), (1, 1), (1, 1), (0, 1)]
    hist = []
    for dsa, dsb in seq:
        prev = b.outs(Q)
        b.set(DSA=dsa, DSB=dsb).edge("CP")
        assert b["Q0"] == dsa & dsb
        assert b.outs(Q)[1:] == prev[:7]
        hist.insert(0, dsa & dsb)
    assert b.outs(Q) == hist[:8]
    b.set(MR=0)                                         # reset (clear), asynchronous
    assert b.outs(Q) == [0] * 8
    b.set(DSA=1, DSB=1).edge("CP")
    assert b.outs(Q) == [0] * 8


@pytest.mark.parametrize("fam", FAMS)
def test_165_function_table(fam):
    t = fam + "165"
    check_pins(t, 16, 16, 8)
    b = Bench(t)
    # parallel load (PL low, asynchronous), L and H data
    for d in (0, 1):
        b.setp({"PL": 0, **{f"D{i}": d for i in range(8)}})
        assert (b["Q7"], b["Q7N"]) == (d, 1 - d)
    pat = [1, 0, 0, 1, 1, 0, 1, 0]                       # D0..D7
    b.setp({f"D{i}": v for i, v in enumerate(pat)})
    assert b["Q7"] == pat[7]
    b.set(PL=1, CE=0, CP=0, DS=1)
    # serial shift on CP rising with CE low: Q7 shows D6, D5, ... then the DS ones
    for k in range(6, -1, -1):
        b.edge("CP")
        b.set(CP=0)
        assert (b["Q7"], b["Q7N"]) == (pat[k], 1 - pat[k])
    b.edge("CP")
    assert b["Q7"] == 1                                 # first DS bit reaches Q7
    # serial shift on CE rising with CP low (the clock is CP OR CE)
    b.setp({"PL": 0, **{f"D{i}": v for i, v in enumerate(pat)}}).set(PL=1, CP=0, CE=1)
    b.set(CE=0)
    b.edge("CE")
    assert b["Q7"] == pat[6]
    # hold: CE high blocks CP; CP high blocks CE
    b.set(CE=1)
    b.edge("CP")
    assert b["Q7"] == pat[6]
    b.set(CE=0, CP=1)
    b.edge("CE")
    assert b["Q7"] == pat[6]


def test_shift_pins_and_timing():
    assert get("74HC164").PINS[8] == ("CP", "clk") and get("74HC164").PINS[13] == ("Q7", "out")
    p = get("74HCT165").PINS
    assert p[1] == ("PL", "in") and p[7] == ("Q7N", "out") and p[9] == ("Q7", "out") and p[15] == ("CE", "clk")
    assert [p[n][0] for n in (11, 12, 13, 14, 3, 4, 5, 6)] == [f"D{i}" for i in range(8)]
    assert get("74HCT165").tpd("PL", "Q7") == 40 and get("74HC164").tpd("MR", "Q0") == 28
