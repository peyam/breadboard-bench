"""Function tables of the extended counter library."""
import pytest

from bbench.chips import get
from libcheck import Bench, check_pins

FAMS = ("74HC", "74HCT")


def q4(b, names):
    return sum(b[n] << i for i, n in enumerate(names))


# ---------------------------------------------------------------- 163
@pytest.mark.parametrize("fam", FAMS)
def test_163_function_table(fam):
    t = fam + "163"
    check_pins(t, 16, 16, 8)
    Q = ["Q0", "Q1", "Q2", "Q3"]
    b = Bench(t)
    b.set(MR=1, PE=1, CEP=1, CET=1)
    # count: every value 0..15 and the wrap, TC high only at 15 with CET high
    for n in range(17):
        assert q4(b, Q) == n % 16
        assert b["TC"] == (1 if n % 16 == 15 else 0)
        b.edge("CP")
    # parallel load (PE low) of L and H data, any count enables
    for val in (0b1010, 0b0101, 0, 15):
        b.set(PE=0, CEP=0, CET=0, D0=val & 1, D1=val >> 1 & 1, D2=val >> 2 & 1, D3=val >> 3 & 1).edge("CP")
        assert q4(b, Q) == val
        assert b["TC"] == 0                     # CET low -> TC low
    b.set(PE=1, CET=1)
    assert b["TC"] == 1                         # state 15 and CET high
    # hold: CEP low or CET low
    for cep, cet in ((0, 1), (1, 0)):
        b.set(CEP=cep, CET=cet).edge("CP")
        assert q4(b, Q) == 15
    # synchronous reset: MR low does nothing until the clock edge
    b.set(MR=0)
    assert q4(b, Q) == 15
    b.edge("CP")
    assert q4(b, Q) == 0 and b["TC"] == 0


# ---------------------------------------------------------------- 191
@pytest.mark.parametrize("fam", FAMS)
def test_191_function_table(fam):
    t = fam + "191"
    check_pins(t, 16, 16, 8)
    Q = ["QA", "QB", "QC", "QD"]
    b = Bench(t)
    # asynchronous preset (LOAD low), no clock needed
    b.set(LOAD=0, A=1, B=0, C=1, D=0)
    assert q4(b, Q) == 5
    b.set(LOAD=1, CTEN=0, DU=0, CLK=1)
    # count up through 15 -> 0; MAX/MIN high at 15; RCO low only while CLK low at 15
    seen = []
    for _ in range(12):
        b.edge("CLK")
        seen.append(q4(b, Q))
        assert b["MAXMIN"] == (1 if q4(b, Q) == 15 else 0)
        assert b["RCO"] == 1                     # CLK is high after the edge
        b.set(CLK=0)
        assert b["RCO"] == (0 if q4(b, Q) == 15 else 1)
        b.set(CLK=1)
    assert seen == [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 0, 1]
    # count down; MAX/MIN high at 0
    b.set(DU=1)
    for want in (0, 15, 14):
        b.edge("CLK")
        assert q4(b, Q) == want
        assert b["MAXMIN"] == (1 if want == 0 else 0)
    # CTEN high: no change, and RCO stays high
    b.set(LOAD=0, A=0, B=0, C=0, D=0).set(LOAD=1, CTEN=1)
    assert b["MAXMIN"] == 1                      # 0 while counting down
    b.edge("CLK")
    assert q4(b, Q) == 0
    b.set(CLK=0)
    assert b["RCO"] == 1


# ---------------------------------------------------------------- 193
@pytest.mark.parametrize("fam", FAMS)
def test_193_function_table(fam):
    t = fam + "193"
    check_pins(t, 16, 16, 8)
    Q = ["Q0", "Q1", "Q2", "Q3"]
    b = Bench(t)
    b.set(PL=1, MR=1, CPU=1, CPD=0)
    # reset (clear): Q = 0, TCU H, TCD = L when CPD is L, H when CPD is H
    assert q4(b, Q) == 0 and (b["TCU"], b["TCD"]) == (1, 0)
    b.set(CPD=1)
    assert (b["TCU"], b["TCD"]) == (1, 1)
    # parallel load (PL low, MR low), asynchronous
    b.set(MR=0, PL=0, D0=0, D1=0, D2=0, D3=0, CPD=0)
    assert q4(b, Q) == 0 and (b["TCU"], b["TCD"]) == (1, 0)
    b.set(CPD=1)
    assert (b["TCU"], b["TCD"]) == (1, 1)
    b.set(D0=1, D1=1, D2=1, D3=1, CPU=0, CPD=1)
    assert q4(b, Q) == 15 and (b["TCU"], b["TCD"]) == (0, 1)
    b.set(CPU=1)
    assert (b["TCU"], b["TCD"]) == (1, 1)
    b.set(PL=1)
    # count up on CPU with CPD high: 15 -> 0 -> 1 ...
    for want in (0, 1, 2):
        b.edge("CPU")
        assert q4(b, Q) == want
    # count down on CPD with CPU high
    for want in (1, 0):
        b.edge("CPD")
        assert q4(b, Q) == want
    b.set(CPD=0)
    assert b["TCD"] == 0                         # TCD = CPD at terminal count down
    b.set(CPD=1)
    b.edge("CPD")
    assert q4(b, Q) == 15
    b.set(CPU=0)
    assert b["TCU"] == 0                         # TCU = CPU at terminal count up
    b.set(CPU=1, MR=1)
    assert q4(b, Q) == 0                         # asynchronous reset


# ---------------------------------------------------------------- 4040 / 4060
@pytest.mark.parametrize("fam", FAMS)
def test_4040_function_table(fam):
    t = fam + "4040"
    check_pins(t, 16, 16, 8)
    b = Bench(t)
    b.set(MR=0)

    def val():
        return sum(b[f"Q{k}"] << k for k in range(12))
    for n in range(1, 40):
        b.edge("CP")                              # HIGH-to-LOW: count
        assert val() == n
        b.set(CP=1)                               # LOW-to-HIGH: no change
        assert val() == n
    b.chip.state = 4095
    b.settle()
    b.edge("CP")
    assert val() == 0                             # 12-bit wrap
    b.chip.state = 1234
    b.set(MR=1)
    assert val() == 0                             # MR high resets
    b.edge("CP")
    assert val() == 0


@pytest.mark.parametrize("fam", FAMS)
def test_4060_function_table(fam):
    t = fam + "4060"
    check_pins(t, 16, 16, 8)
    cls = get(t)
    assert cls.PINS[9][1] == "ana" and cls.PINS[10][1] == "ana" and cls.PINS[11] == ("RS", "clk")
    outs = [3, 4, 5, 6, 7, 8, 9, 11, 12, 13]
    assert sorted(int(nm[1:]) for nm, k in cls.PINS.values() if k == "out") == outs
    b = Bench(t)
    b.set(MR=0)
    for n in range(1, 70):
        b.edge("RS")
        b.set(RS=1)
        for k in outs:
            assert b[f"Q{k}"] == (n >> k) & 1
    b.chip.state = (1 << 14) - 1
    b.settle()
    assert all(b[f"Q{k}"] == 1 for k in outs)
    b.edge("RS")
    assert all(b[f"Q{k}"] == 0 for k in outs)     # 14-bit wrap
    b.chip.state = 0x2AAA
    b.set(MR=1)
    assert all(b[f"Q{k}"] == 0 for k in outs)


def test_ripple_tpd():
    assert get("74HCT4040").tpd("CP", "Q0") == 40 and get("74HCT4040").tpd("CP", "Q11") == 40 + 11 * 20
    assert get("74HC4060").tpd("RS", "Q3") == 60 and get("74HC4060").tpd("RS", "Q13") == 60 + 10 * 16
    assert get("74HC4040").tpd("MR", "Q5") == 37


def test_counter_pin_spot_check():
    assert get("74HC163").PINS[15] == ("TC", "out") and get("74HC163").PINS[14] == ("Q0", "out")
    assert get("74HC191").PINS[12] == ("MAXMIN", "out") and get("74HC191").PINS[13] == ("RCO", "out")
    assert get("74HCT193").PINS[4] == ("CPD", "clk") and get("74HCT193").PINS[5] == ("CPU", "clk")
    assert get("74HC4040").PINS[1] == ("Q11", "out") and get("74HC4040").PINS[10] == ("CP", "clk")
