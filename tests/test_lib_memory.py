"""Truth tables of the 24-pin memories: AT28C16 EEPROM and 6116 SRAM."""
import pytest

from bbench.chips import get, Z, InCircuitWrite
from libcheck import Bench, check_pins

IO = [f"IO{i}" for i in range(8)]


def addr(a):
    return {f"A{i}": (a >> i) & 1 for i in range(11)}


def data(v):
    return {f"IO{i}": (v >> i) & 1 for i in range(8)}


def value(b):
    return sum(b[f"IO{i}"] << i for i in range(8))


@pytest.mark.parametrize("t,cs", [("AT28C16", "CE"), ("6116", "CS")])
def test_mem24_pins(t, cs):
    check_pins(t, 24, 24, 12)
    p = get(t).PINS
    assert [p[k][0] for k in range(1, 9)] == ["A7", "A6", "A5", "A4", "A3", "A2", "A1", "A0"]
    assert (p[18][0], p[19][0], p[20][0], p[21][0], p[22][0], p[23][0]) == (cs, "A10", "OE", "WE", "A9", "A8")
    assert [p[k][0] for k in (9, 10, 11, 13, 14, 15, 16, 17)] == IO
    assert get(t).width() == 6


def test_6116_truth_table():
    b = Bench("6116")
    # standby (CS H): Z whatever OE and WE
    for oe in (0, 1):
        for we in (0, 1):
            b.set(CS=1, OE=oe, WE=we)
            assert b.outs(IO) == [Z] * 8
    # write (CS L, WE L, OE don't care): the cell takes the data; outputs are off
    for a, v in ((0, 0x5A), (2047, 0xA5), (1234, 0xFF), (77, 0x00)):
        for oe in (0, 1):
            b.setp({"CS": 0, "OE": oe, "WE": 0, **addr(a), **data(v)})
            assert b.outs(IO) == [Z] * 8
            b.set(WE=1)
    # read (CS L, OE L, WE H) / output disabled (OE H)
    for a, v in ((0, 0x5A), (2047, 0xA5), (1234, 0xFF), (77, 0x00), (5, 0)):
        b.setp({"CS": 0, "OE": 0, "WE": 1, **addr(a)})
        assert value(b) == v
        b.set(OE=1)
        assert b.outs(IO) == [Z] * 8


def test_at28c16_truth_table():
    img = bytes((i * 7 + 3) & 0xFF for i in range(2048))
    b = Bench("AT28C16", levels={"WE": 1, "CE": 1}, image=img)
    for a in (0, 1, 2, 1000, 2047):
        b.setp({"CE": 0, "OE": 0, **addr(a)})          # read
        assert value(b) == img[a]
        b.set(OE=1)                                    # output disable
        assert b.outs(IO) == [Z] * 8
        b.set(CE=1, OE=0)                              # standby
        assert b.outs(IO) == [Z] * 8
    blank = Bench("AT28C16", levels={"WE": 1})
    blank.setp({"CE": 0, "OE": 0, "WE": 1, **addr(9)})
    assert value(blank) == 0xFF                        # erased cells read FF
    with pytest.raises(InCircuitWrite):                # write: not allowed in circuit
        b.set(CE=0, OE=1, WE=0)


def test_mem24_timing():
    assert get("AT28C16").tpd("A0", "IO0") == 150 and get("AT28C16").tpd("OE", "IO0") == 70
    assert get("6116").tpd("A3", "IO1") == 15 and get("6116").tpd("OE", "IO1") == 10
