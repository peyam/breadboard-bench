"""Function tables of the extended flip-flop / latch / register library."""
import pytest

from bbench.chips import get, Z
from libcheck import Bench, check_pins

FAMS = ("74HC", "74HCT")


# ---------------------------------------------------------------- 74
@pytest.mark.parametrize("fam", FAMS)
def test_74_function_table(fam):
    t = fam + "74"
    check_pins(t, 14, 14, 7)
    for u in "12":
        b = Bench(t)
        P, C, K, D, Q, QN = (u + "PRE", u + "CLR", u + "CLK", u + "D", u + "Q", u + "QN")
        # PRE L, CLR H -> H L
        b.set(**{P: 0, C: 1, D: 0})
        assert (b[Q], b[QN]) == (1, 0)
        # PRE H, CLR L -> L H
        b.set(**{P: 1, C: 0})
        assert (b[Q], b[QN]) == (0, 1)
        # PRE L, CLR L -> H H (nonstable)
        b.set(**{P: 0, C: 0})
        assert (b[Q], b[QN]) == (1, 1)
        b.set(**{P: 1, C: 1})
        # rising edge with D = H, then D = L
        b.set(**{D: 1}).edge(K)
        assert (b[Q], b[QN]) == (1, 0)
        b.set(**{D: 0}).edge(K)
        assert (b[Q], b[QN]) == (0, 1)
        # CLK low (no edge): Q0 kept whatever D does
        b.set(**{K: 0, D: 1})
        assert (b[Q], b[QN]) == (0, 1)
        # async inputs override the clock
        b.set(**{C: 0, D: 1}).edge(K)
        assert b[Q] == 0
    b = Bench(t)
    b.set(**{"1PRE": 1, "2PRE": 1})                # CLR still low: both cleared
    b.set(**{"1PRE": 1, "1CLR": 1, "2PRE": 1, "2CLR": 1, "1D": 1, "2D": 0}).edge("1CLK")
    assert (b["1Q"], b["2Q"]) == (1, 0)          # the two flip-flops are independent


# ---------------------------------------------------------------- 109 / 112
JK_ROWS = [(0, 0, "keep"), (1, 0, 1), (0, 1, 0), (1, 1, "toggle")]   # (J, K) -> Q


@pytest.mark.parametrize("t", ["74HC109", "74HCT109", "74HC112", "74HCT112"])
def test_jk_function_table(t):
    check_pins(t, 16, 16, 8)
    kbar = t.endswith("109")
    for u in "12":
        P, C, K = u + "PRE", u + "CLR", u + "CLK"
        b = Bench(t)
        idle = 0 if kbar else 1
        b.set(**{P: 0, C: 1, K: idle})
        assert (b[u + "Q"], b[u + "QN"]) == (1, 0)
        b.set(**{P: 1, C: 0})
        assert (b[u + "Q"], b[u + "QN"]) == (0, 1)
        b.set(**{P: 0, C: 0})
        assert (b[u + "Q"], b[u + "QN"]) == (1, 1)
        b.set(**{P: 1, C: 1})
        for start in (0, 1):
            for j, k, res in JK_ROWS:
                b.set(**{C: 0}).set(**{C: 1}) if start == 0 else b.set(**{P: 0}).set(**{P: 1})
                assert b[u + "Q"] == start
                kin = {u + "KN": 1 - k} if kbar else {u + "K": k}
                b.set(**{u + "J": j}, **kin).edge(K)
                want = start if res == "keep" else (1 - start if res == "toggle" else res)
                assert (b[u + "Q"], b[u + "QN"]) == (want, 1 - want), (t, u, start, j, k)
                b.set(**{K: idle})                  # clock at its idle level: no change
                assert b[u + "Q"] == want


def test_jk_edges_and_pins():
    assert get("74HC109").EDGE == {"1CLK": "rise", "2CLK": "rise"}
    assert get("74HCT112").EDGE == {"1CLK": "fall", "2CLK": "fall"}
    assert get("74HC109").PINS[3] == ("1KN", "in") and get("74HC109").PINS[15] == ("2CLR", "in")
    assert get("74HC112").PINS[13] == ("2CLK", "clk") and get("74HC112").PINS[7] == ("2QN", "out")


# ---------------------------------------------------------------- 175 / 273
@pytest.mark.parametrize("fam", FAMS)
def test_175_function_table(fam):
    t = fam + "175"
    check_pins(t, 16, 16, 8)
    b = Bench(t)
    b.set(MR=1, D0=1, D1=0, D2=1, D3=1).edge("CP")              # load
    assert b.outs(["Q0", "Q1", "Q2", "Q3"]) == [1, 0, 1, 1]
    assert b.outs(["Q0N", "Q1N", "Q2N", "Q3N"]) == [0, 1, 0, 0]
    b.set(D0=0, D1=1, D2=0, D3=0).edge("CP")
    assert b.outs(["Q0", "Q1", "Q2", "Q3"]) == [0, 1, 0, 0]
    b.set(MR=0)                                                  # reset (clear), no clock
    assert b.outs(["Q0", "Q1", "Q2", "Q3"]) == [0] * 4 and b.outs(["Q0N", "Q1N", "Q2N", "Q3N"]) == [1] * 4


@pytest.mark.parametrize("fam", FAMS)
def test_273_function_table(fam):
    t = fam + "273"
    check_pins(t, 20, 20, 10)
    b = Bench(t)
    pat = [1, 0, 1, 1, 0, 0, 1, 0]
    b.setp({"MR": 1, **{f"D{i}": v for i, v in enumerate(pat)}}).edge("CP")
    assert b.outs([f"Q{i}" for i in range(8)]) == pat
    inv = [1 - v for v in pat]
    b.setp({f"D{i}": v for i, v in enumerate(inv)}).edge("CP")
    assert b.outs([f"Q{i}" for i in range(8)]) == inv
    b.set(MR=0)
    assert b.outs([f"Q{i}" for i in range(8)]) == [0] * 8
    b.edge("CP")                                                  # MR low holds the reset
    assert b.outs([f"Q{i}" for i in range(8)]) == [0] * 8


# ---------------------------------------------------------------- 373 / 573 latches
@pytest.mark.parametrize("t", ["74HC373", "74HCT373", "74HC573", "74HCT573"])
def test_latch_function_table(t):
    check_pins(t, 20, 20, 10)
    Q = [f"Q{i}" for i in range(8)]
    b = Bench(t)
    pat = [0, 1, 1, 0, 1, 0, 0, 1]
    # OE L, LE H: transparent (Q follows D, both levels)
    b.setp({"OE": 0, "LE": 1, **{f"D{i}": v for i, v in enumerate(pat)}})
    assert b.outs(Q) == pat
    b.setp({f"D{i}": 1 - v for i, v in enumerate(pat)})
    assert b.outs(Q) == [1 - v for v in pat]
    # OE L, LE L: latched (D changes are ignored)
    b.set(LE=0)
    b.setp({f"D{i}": v for i, v in enumerate(pat)})
    assert b.outs(Q) == [1 - v for v in pat]
    # OE H: outputs Z, latch keeps its data
    b.set(OE=1)
    assert b.outs(Q) == [Z] * 8
    b.set(OE=0)
    assert b.outs(Q) == [1 - v for v in pat]


@pytest.mark.parametrize("t", ["74HC374", "74HCT374", "74HC574", "74HCT574"])
def test_register_function_table(t):
    check_pins(t, 20, 20, 10)
    Q = [f"Q{i}" for i in range(8)]
    b = Bench(t)
    pat = [1, 1, 0, 1, 0, 0, 1, 0]
    b.setp({"OE": 0, **{f"D{i}": v for i, v in enumerate(pat)}})
    assert b.outs(Q) == [0] * 8                               # no edge yet
    b.edge("CP")
    assert b.outs(Q) == pat                                    # load and read
    b.setp({f"D{i}": 1 - v for i, v in enumerate(pat)})
    assert b.outs(Q) == pat                                    # no edge: hold
    b.set(OE=1).edge("CP")                                     # load with outputs disabled
    assert b.outs(Q) == [Z] * 8
    b.set(OE=0)
    assert b.outs(Q) == [1 - v for v in pat]


def test_octal_pinouts():
    a, b = get("74HCT373"), get("74HCT573")
    assert a.PINS[2] == ("Q0", "tri") and a.PINS[3] == ("D0", "in") and a.PINS[11] == ("LE", "in")
    assert b.PINS[2] == ("D0", "in") and b.PINS[19] == ("Q0", "tri") and b.PINS[12] == ("Q7", "tri")
    assert get("74HC374").PINS[11] == ("CP", "clk") and get("74HC574").PINS[11] == ("CP", "clk")


def test_timing_values():
    assert get("74HCT74").tpd("1CLK", "1Q") == 28 and get("74HCT74").tpd("1CLR", "1Q") == 35
    assert get("74HC74").setup_ns("1D") == 20 and get("74HCT74").setup_ns("1D") == 12
    assert get("74HCT273").tpd("MR", "Q0") == 34 and get("74HCT273").tpd("CP", "Q0") == 30
    assert get("74HC574").tpd("OE", "Q3") == 28 and get("74HCT373").hold_ns("D0") == 4
