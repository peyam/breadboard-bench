"""Function table of the 74LS181 ALU (active-HIGH data), every select code, every A and B."""
from bbench.chips import get, Z
from libcheck import getter, check_pins

M4 = 15


def n(x):
    return ~x & M4


# Datasheet function table, active-HIGH data. Logic column (M = H) and arithmetic
# column (M = L, Cn = H: no carry). With Cn = L each arithmetic result is one more.
LOGIC = [lambda a, b: n(a), lambda a, b: n(a | b), lambda a, b: n(a) & b, lambda a, b: 0,
         lambda a, b: n(a & b), lambda a, b: n(b), lambda a, b: a ^ b, lambda a, b: a & n(b),
         lambda a, b: n(a) | b, lambda a, b: n(a ^ b), lambda a, b: b, lambda a, b: a & b,
         lambda a, b: M4, lambda a, b: a | n(b), lambda a, b: a | b, lambda a, b: a]
ARITH = [lambda a, b: a, lambda a, b: a | b, lambda a, b: a | n(b), lambda a, b: -1,
         lambda a, b: a + (a & n(b)), lambda a, b: (a | b) + (a & n(b)), lambda a, b: a - b - 1,
         lambda a, b: (a & n(b)) - 1, lambda a, b: a + (a & b), lambda a, b: a + b,
         lambda a, b: (a | n(b)) + (a & b), lambda a, b: (a & b) - 1, lambda a, b: a + a,
         lambda a, b: (a | b) + a, lambda a, b: (a | n(b)) + a, lambda a, b: a - 1]


def run(chip, a, b, s, m, cn):
    vals = {"M": m, "CN": cn}
    for i in range(4):
        vals[f"A{i}"], vals[f"B{i}"], vals[f"S{i}"] = (a >> i) & 1, (b >> i) & 1, (s >> i) & 1
    return chip.eval(getter(vals))


def F(o):
    return sum(o[f"F{i}"] << i for i in range(4))


def test_181_pins():
    check_pins("74LS181", 24, 24, 12)
    p = get("74LS181").PINS
    assert p[1] == ("B0", "in") and p[2] == ("A0", "in") and p[7] == ("CN", "in") and p[8] == ("M", "in")
    assert p[14] == ("AEQB", "tri") and p[15] == ("CN4", "out") and p[16] == ("P", "out") and p[17] == ("G", "out")
    assert [p[k][0] for k in (3, 4, 5, 6)] == ["S3", "S2", "S1", "S0"]
    assert get("74LS181").width() == 6


def test_181_function_table():
    chip = get("74LS181")("U1")
    for s in range(16):
        for a in range(16):
            for b in range(16):
                o = run(chip, a, b, s, 1, 1)
                assert F(o) == LOGIC[s](a, b), ("logic", s, a, b)
                for cn, carry in ((1, 0), (0, 1)):
                    full = ARITH[s](a, b) + carry
                    o = run(chip, a, b, s, 0, cn)
                    assert F(o) == full & M4, ("arith", s, a, b, cn)
                    assert o["AEQB"] == (Z if F(o) == 15 else 0)


def test_181_carry_and_lookahead():
    chip = get("74LS181")("U1")
    for a in range(16):
        for b in range(16):
            # A plus B (S = HLLH): CN4 is low when there is a carry out
            for cn, c in ((1, 0), (0, 1)):
                o = run(chip, a, b, 0b1001, 0, cn)
                assert o["CN4"] == (0 if a + b + c > 15 else 1)
                # G low when the group generates a carry, P low when it propagates one
                assert o["G"] == (0 if a + b > 15 else 1)
            o = run(chip, a, b, 0b1001, 0, 1)
            gen, prop = a + b > 15, all(((a | b) >> i) & 1 for i in range(4))
            assert o["G"] == (0 if gen else 1) and o["P"] == (0 if prop else 1)
            # A minus B (S = LHHL, Cn = L): A = B shows equality; CN4 low means no borrow (A >= B)
            o = run(chip, a, b, 0b0110, 0, 1)
            assert o["AEQB"] == (Z if a == b else 0)
            o = run(chip, a, b, 0b0110, 0, 0)
            assert F(o) == (a - b) & M4
            assert o["CN4"] == (0 if a >= b else 1)
