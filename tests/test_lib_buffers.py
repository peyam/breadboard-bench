"""Function tables of the extended buffer library."""
import pytest

from bbench.chips import get, Z, X
from libcheck import getter, check_pins

FAMS = ("74HC", "74HCT")


@pytest.mark.parametrize("fam", FAMS)
@pytest.mark.parametrize("num,active", [("125", 0), ("126", 1)])
def test_quad_function_table(fam, num, active):
    t = fam + num
    check_pins(t, 14, 14, 7)
    chip = get(t)("U1")
    # rows: OE active -> Y = A (L and H); OE inactive -> Z for any A
    for u in "1234":
        for oe in (0, 1):
            for a in (0, 1):
                vals = {f"{i}{p}": 0 for i in "1234" for p in ("OE", "A")}
                vals.update({f"{u}OE": oe, f"{u}A": a})
                y = chip.eval(getter(vals))[f"{u}Y"]
                assert y == (a if oe == active else Z), (t, u, oe, a)
    vals = {f"{i}{p}": 0 for i in "1234" for p in ("OE", "A")}
    vals.update({"1OE": active, "1A": Z})
    assert chip.eval(getter(vals))["1Y"] == X          # a floating input gives an unknown output


OCT = {"240": ((0, 0), True), "241": ((0, 1), False), "244": ((0, 0), False)}


@pytest.mark.parametrize("fam", FAMS)
@pytest.mark.parametrize("num", sorted(OCT))
def test_octal_function_table(fam, num):
    t = fam + num
    check_pins(t, 20, 20, 10)
    active, inv = OCT[num]
    chip = get(t)("U1")
    for grp, act in zip("12", active):
        for oe in (0, 1):
            for n in range(4):
                for a in (0, 1):
                    vals = {f"{g}A{i}": 0 for g in "12" for i in range(4)}
                    vals.update({"1OE": active[0], "2OE": active[1]})
                    vals.update({f"{grp}OE": oe, f"{grp}A{n}": a})
                    y = chip.eval(getter(vals))[f"{grp}Y{n}"]
                    want = ((1 - a) if inv else a) if oe == act else Z
                    assert y == want, (t, grp, oe, n, a)


@pytest.mark.parametrize("fam", FAMS)
def test_541_function_table(fam):
    t = fam + "541"
    check_pins(t, 20, 20, 10)
    chip = get(t)("U1")
    for oe1 in (0, 1):
        for oe2 in (0, 1):
            for n in range(8):
                for a in (0, 1):
                    vals = {f"A{i}": 0 for i in range(8)}
                    vals.update({"OE1": oe1, "OE2": oe2, f"A{n}": a})
                    y = chip.eval(getter(vals))[f"Y{n}"]
                    assert y == (a if (oe1, oe2) == (0, 0) else Z)


def test_buffer_pins_and_timing():
    assert get("74HCT244").PINS[18] == ("1Y0", "tri") and get("74HCT244").PINS[3] == ("2Y0", "tri")
    assert get("74HC541").PINS[18] == ("Y0", "tri") and get("74HC541").PINS[11] == ("Y7", "tri")
    assert get("74HCT125").tpd("1A", "1Y") == 20 and get("74HCT125").tpd("1OE", "1Y") == 28
    assert get("74HCT240").tpd("1OE", "1Y0") == 30 and get("74HCT541").tpd("A0", "Y0") == 28
