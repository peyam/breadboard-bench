"""Timed simulator: delays, setup/hold, waveforms and VCD."""
from bbench.core.netlist import Netlist
from bbench.core.timed import TimedSim
from bbench.core.waveforms import parse_vcd
from bbench import chips


def chain():
    """Six inverters of one 74HC04 in a chain, driven by a switch."""
    N = Netlist()
    N.add("U1", "74HC04")
    N.connect("VCC", "U1", 14)
    N.connect("GND", "U1", 7)
    N.add("S1", "SW")
    N.add("R1", "R")
    N.connect("VCC", "S1", 1)
    N.connect("N0", "S1", 2)
    N.connect("N0", "R1", 1)
    N.connect("GND", "R1", 2)
    for k in range(1, 7):
        N.connect(f"N{k - 1}", "U1", f"{k}A")
        N.connect(f"N{k}", "U1", f"{k}Y")
    return N


def test_inverter_chain_has_summed_tpd():
    s = TimedSim(chain())
    s.run_ns(100)
    t0 = s.t_ns
    s.set("S1", True)
    s.run_ns(1000)
    tr = {sg["name"]: sg["changes"] for sg in s.trace([f"N{k}" for k in range(7)])["signals"]}
    tpd = chips.get("74HC04").tpd("1A", "1Y")
    assert tr["N0"][-1] == [t0, 1]
    for k in range(1, 7):
        assert tr[f"N{k}"][-1][0] == t0 + k * tpd
    assert tr["N6"][-1] == [t0 + 6 * tpd, 1]
    assert s.errors == []


def test_inertial_delay_swallows_short_pulse():
    s = TimedSim(chain())
    s.run_ns(100)
    s.set("S1", True)
    s.run_ns(5)                      # 5 ns pulse, shorter than the 20 ns delay
    s.set("S1", False)
    s.run_ns(500)
    n1 = [c for sg in s.trace(["N1"])["signals"] for c in sg["changes"]]
    assert n1 == [[0, 1]]


def flipflop(d_delay_ns):
    """74HC174: CLK from a 1 MHz clock; D from a second clock that changes d_delay_ns
    before each rising edge of CLK."""
    N = Netlist()
    N.add("U1", "74HC174")
    N.connect("VCC", "U1", 16)
    N.connect("GND", "U1", 8)
    N.connect("VCC", "U1", "CLR")
    N.add("CK", "CLOCK", {"period_ns": 1000})
    N.add("DG", "CLOCK", {"period_ns": 2000})
    N.connect("CLK", "CK", 1)
    N.connect("D", "DG", 1)
    N.connect("CLK", "U1", "CLK")
    N.connect("D", "U1", "1D")
    for p in ("2D", "3D", "4D", "5D", "6D"):
        N.connect("GND", "U1", p)
    N.connect("Q", "U1", "1Q")
    clk_tpd = 1                       # the CLOCK part's own delay
    stim = [{"part": "CK", "period_ns": 1000, "duty": 0.5, "delay_ns": 500, "role": "main"},
            {"part": "DG", "period_ns": 2000, "duty": 0.5, "delay_ns": 500 - d_delay_ns + clk_tpd * 0}]
    return TimedSim(N, stim)


def test_setup_violation_detected():
    s = flipflop(5)                   # D changes 5 ns before the edge; 74HC174 needs 20 ns
    s.run_ns(5000)
    kinds = {v["kind"] for v in s.violations}
    assert "setup" in kinds
    assert any(e["kind"] == "setup" for e in s.errors)


def test_no_violation_with_margin():
    s = flipflop(200)
    s.run_ns(5000)
    assert s.violations == []
    q = s.trace(["Q"])["signals"][0]["changes"]
    assert len(q) > 2


def test_hold_violation_detected():
    s = flipflop(-3)                  # D changes 3 ns after the edge; 74HC174 needs 5 ns hold
    s.run_ns(5000)
    assert any(v["kind"] == "hold" for v in s.violations)


def test_vcd_parses():
    s = TimedSim(chain())
    s.run_ns(50)
    s.set("S1", True)
    s.run_ns(300)
    text = s.to_vcd(["N0", "N1", "N6"])
    assert "$enddefinitions $end" in text and "$timescale 1ps $end" in text
    w = parse_vcd(text)
    assert set(w) == {"N0", "N1", "N6"}
    assert w["N0"][0] == (0, "0") and w["N0"][-1] == (50000, "1")
    assert w["N6"][-1] == (50000 + 6 * 20000, "1")


def test_555_astable_period_from_parts():
    from bbench.projects.examples import clock_555
    s = clock_555().simulator("timed")
    d = s.stimuli[0]
    # t_high = 0.693 (1k + 68k) 10 uF, t_low = 0.693 * 68k * 10 uF
    assert abs(d["period_ns"] - 0.693 * (1e3 + 2 * 68e3) * 10e-6 * 1e9) < 1
    s.run_ns(3e9)
    ch = s.trace(["CLK"])["signals"][0]["changes"]
    rises = [t for t, v in ch if v == 1]
    assert len(rises) >= 3 and abs((rises[2] - rises[1]) - d["period_ns"]) < 1
