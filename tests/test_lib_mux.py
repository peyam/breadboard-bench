"""Function tables of the extended multiplexer library."""
import pytest

from bbench.chips import get
from libcheck import getter, check_pins

FAMS = ("74HC", "74HCT")


@pytest.mark.parametrize("fam", FAMS)
def test_151_function_table(fam):
    t = fam + "151"
    check_pins(t, 16, 16, 8)
    chip = get(t)("U1")
    # strobe high: Y = L, W = H whatever the other inputs
    for n in range(8):
        for d in (0, 1):
            vals = {f"D{i}": d for i in range(8)}
            vals.update({"G": 1, "A": n & 1, "B": n >> 1 & 1, "C": n >> 2 & 1})
            assert chip.eval(getter(vals)) == {"Y": 0, "W": 1}
    # strobe low: Y = Dn, W = not Dn (other data inputs at the opposite level)
    for n in range(8):
        for d in (0, 1):
            vals = {f"D{i}": 1 - d for i in range(8)}
            vals.update({f"D{n}": d, "G": 0, "A": n & 1, "B": n >> 1 & 1, "C": n >> 2 & 1})
            assert chip.eval(getter(vals)) == {"Y": d, "W": 1 - d}, (t, n, d)


@pytest.mark.parametrize("fam", FAMS)
def test_153_function_table(fam):
    t = fam + "153"
    check_pins(t, 16, 16, 8)
    chip = get(t)("U1")
    for h in "12":
        o = "21"[h == "2"]
        for n in range(4):
            for d in (0, 1):
                for g_on in (0, 1):
                    vals = {f"{u}C{i}": 1 - d for u in "12" for i in range(4)}
                    vals.update({f"{h}C{n}": d, f"{h}G": g_on, f"{o}G": 0, "A": n & 1, "B": n >> 1})
                    y = chip.eval(getter(vals))[f"{h}Y"]
                    assert y == (0 if g_on else d), (t, h, n, d, g_on)


def test_mux_pins_and_timing():
    assert get("74HC151").PINS[4] == ("D0", "in") and get("74HC151").PINS[12] == ("D7", "in")
    assert get("74HCT153").PINS[2] == ("B", "in") and get("74HCT153").PINS[14] == ("A", "in")
    assert get("74HC151").tpd("A", "Y") == 50 and get("74HCT151").tpd("D3", "W") == 36
    assert get("74HCT153").tpd("1G", "1Y") == 27 and get("74HC153").tpd("1C0", "1Y") == 28
