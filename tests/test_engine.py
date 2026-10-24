"""Engine behaviour on small netlists: resolution, checks, parts, old API wording."""
import json

from bbench.core.netlist import Netlist
from bbench.core.engine import ZeroDelaySim
from bbench import chips
from bbench.compat.pc2sim import Netlist as OldNetlist, Sim


def inverter(n_extra=()):
    N = Netlist()
    N.add("U1", "74HC04")
    N.connect("VCC", "U1", 14)
    N.connect("GND", "U1", 7)
    for p in ("2A", "3A", "4A", "5A", "6A"):
        N.connect("GND", "U1", p)
    N.add("S1", "SW")
    N.add("R1", "R", {"value": "10k"})
    N.connect("VCC", "S1", 1)
    N.connect("A", "S1", 2)
    N.connect("A", "R1", 1)
    N.connect("GND", "R1", 2)
    N.connect("A", "U1", "1A")
    N.connect("Y", "U1", "1Y")
    return N


def test_registry_has_pc2_chips_and_no_duplicates():
    for t in ["74HC00", "74HC02", "74HC04", "74HC08", "74HC32", "74HC86", "74HC107", "74HC138", "74HC139",
              "74HC157", "74HC161", "74HC173", "74HC174", "74HC245", "74HC283", "74HC377", "74HC595",
              "AS6C62256", "AT28C256", "NE555", "74HCT245", "74HCT173"]:
        assert t in chips.REGISTRY, t
    assert chips.DUPLICATES == []


def test_gate_function_tables():
    for t in ("74HC00", "74HC02", "74HC08", "74HC32", "74HC86"):
        cls = chips.get(t)
        m = cls("U1")
        for a, b, y in cls.TABLE["rows"]:
            vals = {"1A": a, "1B": b}
            assert m.eval(lambda n: vals.get(n, 0))["1Y"] == y, (t, a, b)


def test_switch_pulldown_inverter():
    s = ZeroDelaySim(inverter())
    assert s.errors == []
    assert s.v("A") == 0 and s.v("Y") == 1
    s.set("S1", True)
    assert s.v("A") == 1 and s.v("Y") == 0


def test_contention_two_switches():
    N = inverter()
    N.add("S2", "SW", {"closed": True})
    N.connect("GND", "S2", 1)
    N.connect("A", "S2", 2)
    s = ZeroDelaySim(N)
    s.set("S1", True)
    assert any(c[0] == "A" for c in s.contention)
    assert any(e["kind"] == "contention" for e in s.errors)
    assert s.v("A") == "X"


def test_floating_input_reported():
    N = inverter()
    N.add("U2", "74HC08")
    N.connect("VCC", "U2", 14)
    N.connect("GND", "U2", 7)
    N.add("U3", "74HC245")
    N.connect("FLOAT", "U3", "B1")          # a tri-state line nobody drives
    for k, p in enumerate(["1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B"]):
        N.connect("FLOAT" if p == "1A" else "GND", "U2", p)
    N.connect("VCC", "U3", "OE")
    N.connect("VCC", "U3", "DIR")
    s = ZeroDelaySim(N)
    assert any(e["kind"] == "floating" for e in s.errors)


def test_eeprom_written_in_circuit():
    N = Netlist()
    N.add("U1", "AT28C256", {"image": [1, 2, 3]})
    for k in range(15):
        N.connect("GND", "U1", f"A{k}")
    N.connect("GND", "U1", "CE")
    N.connect("VCC", "U1", "OE")
    N.connect("GND", "U1", "WE")
    s = ZeroDelaySim(N)
    assert any(e["kind"] == "eeprom-write" for e in s.errors)


def test_ring_oscillator_reported():
    N = Netlist()
    N.add("U1", "74HC04")
    N.connect("A", "U1", "1A")
    N.connect("B", "U1", "1Y")
    N.connect("B", "U1", "2A")
    N.connect("C", "U1", "2Y")
    N.connect("C", "U1", "3A")
    N.connect("A", "U1", "3Y")
    for p in ("4A", "5A", "6A"):
        N.connect("GND", "U1", p)
    s = ZeroDelaySim(N)
    assert any(e["kind"] == "oscillation" for e in s.errors)


def test_led_follows_through_resistor_and_digit():
    N = inverter()
    N.add("R2", "R", {"value": "1k"})
    N.add("D1", "LED")
    N.connect("Y", "R2", 1)
    N.connect("M", "R2", 2)
    N.connect("M", "D1", "A")
    N.connect("GND", "D1", "K")
    N.add("Q1", "PNP")
    N.add("DG", "7SEG-CA")
    N.connect("VCC", "Q1", "E")
    N.connect("A", "Q1", "B")            # base low (A = 0) -> digit on
    N.connect("COM", "Q1", "C")
    N.connect("COM", "DG", 3)
    N.connect("COM", "DG", 8)
    N.connect("GND", "DG", "a")          # segment a lit
    for seg in ("b", "c", "d", "e", "f", "g", "dp"):
        N.connect("VCC", "DG", seg)
    s = ZeroDelaySim(N)
    st = s.state()
    assert st["leds"]["D1"] is True and st["digits"]["DG"] == 1
    s.set("S1", 1)
    st = s.state()
    assert st["leds"]["D1"] is False and st["digits"]["DG"] == 0
    json.dumps(st)


def test_switch_between_two_signal_nets_joins_them():
    N = inverter()
    N.add("S2", "SW")
    N.add("U2", "74HC04")
    N.connect("A", "S2", 1)
    N.connect("A2", "S2", 2)
    N.connect("A2", "U2", "1A")
    for p in ("2A", "3A", "4A", "5A", "6A"):
        N.connect("GND", "U2", p)
    s = ZeroDelaySim(N)
    assert any(e["kind"] == "floating" for e in s.errors)      # A2 floats while S2 is open
    s.set("S1", 1)
    s.set("S2", 1)
    assert s.v("A2") == 1


def test_old_api_wording_unchanged():
    """ch1 of the book: forget the wire to pin 2."""
    N = OldNetlist()
    m = N.module("bench")
    unused = {p: "GND" for p in ("2A", "2B", "3A", "3B", "4A", "4B")}
    N.chip("U1", "74HC00", m, **{"1A": "A", "1B": "B", "1Y": "Y"}, **unused)
    a = N.switch_to_vcc(m, "A", "input A")
    s = Sim(N)
    assert s.errors == ["net B read by ['U1'] has no driver at all"]
    N2 = OldNetlist()
    N2.chip("U1", "74HC00", m, **{"1A": "A", "1B": "B", "1Y": "Y"}, **unused)
    a = N2.switch_to_vcc(m, "A", "input A")
    b = N2.switch_to_vcc(m, "B", "input B")
    s2 = Sim(N2)
    out = []
    for x in (0, 1):
        for y in (0, 1):
            a.closed, b.closed = x, y
            s2.step()
            out.append(s2.v("Y"))
    assert out == [1, 1, 1, 0] and s2.errors == [] and not s2.contention


def test_old_api_counter_ch13():
    N = OldNetlist()
    m = N.module("PC-2+ program counter")
    B = [f"B{k}" for k in range(8)]
    N.chip("U20", "74HC161", m, CLR="VCC", CLK="CLK", ENP="CE", ENT="CE", LOAD="J_n", A=B[0], B=B[1], C=B[2],
           D=B[3], QA="PC0", QB="PC1", QC="PC2", QD="PC3", RCO="CARRY")
    N.chip("U20B", "74HC161", m, CLR="VCC", CLK="CLK", ENP="CE", ENT="CARRY", LOAD="J_n", A=B[4], B=B[5],
           C=B[6], D=B[7], QA="PC4", QB="PC5", QC="PC6", QD="PC7")
    clk = N.switch_to_vcc(m, "CLK", "clock")
    ce = N.switch_to_vcc(m, "CE", "count enable")
    j = N.part("SW", m, {"1": "GND", "2": "J_n"}, note="jump")
    N.pullup(m, "J_n")
    bus = [N.switch_to_vcc(m, b, b) for b in B]
    s = Sim(N)
    s.step()

    def pulse():
        clk.closed = True
        s.step()
        clk.closed = False
        s.step()
    ce.closed = True
    seen = []
    for k in range(300):
        seen.append(s.word("PC", 8))
        pulse()
    assert seen == [k % 256 for k in range(300)]
    for k, sw in enumerate(bus):
        sw.closed = (0xC8 >> k) & 1
    j.closed = True
    pulse()
    j.closed = False
    assert s.word("PC", 8) == 0xC8
    assert s.errors == [] and not s.contention


# ---------------------------------------------------------------- real-time zero-delay runs
def test_zero_run_ns_moves_clocks_in_real_time():
    """run_ns toggles every clock source at its own period: the 4-bit counter example (a 555
    at about 2.2 Hz) counts by itself in the zero-delay simulator, with no step() calls."""
    import bbench
    s = bbench.projects.example("4-bit-counter").simulator("zero")
    per = s.clocks()[0]["period_ns"]
    assert 400e6 < per < 500e6
    seen = []
    for _ in range(5):
        r = s.run_ns(per)
        seen.append(s.word("Q", 4))
        assert r["done"] and r["edges"] == 2
    assert seen == [1, 2, 3, 4, 5]
    assert s.cycles == 5 and abs(s.t_ps / 1000 - 5 * per - 0) < per


def test_zero_run_ns_555_example_and_edge_limit():
    import bbench
    s = bbench.projects.example("555-clock").simulator("zero")
    per = s.clocks()[0]["period_ns"]
    vals = set()
    for _ in range(8):
        s.run_ns(per / 4)
        vals.add(s.v("CLK"))
    assert vals == {0, 1}
    r = s.run_ns(per * 1000, max_edges=10)
    assert not r["done"] and r["edges"] == 10
    tr = s.trace(["CLK"])["signals"][0]["changes"]
    assert len(tr) > 10 and all(b[0] > a[0] for a, b in zip(tr, tr[1:]))


def test_history_keep_limits_changes_per_net():
    import bbench
    s = bbench.projects.example("555-clock").simulator("zero")
    s.history.keep = 20
    s.run_ns(s.clocks()[0]["period_ns"] * 100)
    n = len(s.trace(["CLK"])["signals"][0]["changes"])
    assert 10 <= n <= 20


def test_chip_levels_in_library():
    import bbench
    lib = {d["type"]: d for d in bbench.library() if d.get("category") == "chip"}
    assert lib["74HCT245"]["levels"]["VIH"] == 2.0
    assert lib["74HC245"]["levels"]["VIH"] == 3.15
    assert lib["NE555"]["levels"]["VOH"] < 3.15 and lib["NE555"]["levels"]["VIH"] is None
    assert lib["AS6C62256"]["levels"]["VOH"] == 2.4
