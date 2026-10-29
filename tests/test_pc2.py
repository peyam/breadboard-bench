"""PC-2 runs every program and matches the microcode emulator, with no contention and
no floating input (port of pc2sim/test_hw.py; tools/prove_pc2.py runs all 483 cases)."""
import pytest

from prove_pc2 import cases, check, run_old, run_api   # noqa: F401
from bbench.compat.pc2sim import Bench, build
from bbench.projects import pc2_emulator as pc2
from bbench.projects.pc2_programs import P

QUICK = cases(quick=True)


@pytest.mark.parametrize("name,mem,a,b", QUICK, ids=[f"{c[0]}({c[2]},{c[3]})" for c in QUICK])
def test_old_bench_matches_emulator(name, mem, a, b):
    assert check(name, mem, a, b, run_old) == []


API = [c for c in QUICK if c[0] in ("ECHO", "ADD", "BIGGER", "COUNTDOWN", "OUT 1", "OUT 2", "FIBONACCI")]


@pytest.mark.parametrize("name,mem,a,b", API, ids=[f"{c[0]}({c[2]},{c[3]})" for c in API])
def test_project_api_matches_emulator(name, mem, a, b):
    """Through the public API: real switches, the bistable RUN/STEP and the STEP monostable."""
    assert check(name, mem, a, b, run_api) == []


def test_single_step_same_as_run():
    b = Bench()
    b.load(P["BIGGER"])
    b.set_bits("input A switch {}", 9)
    b.set_bits("input B switch {}", 200)
    b.reset()
    n = 0
    while b.sim.v("HLT_n") == 1 and n < 200:
        b.single_step()
        n += 1
    assert b.shown == [200] and b.display() == " 200"


def test_panel_single_step():
    from bbench.projects.pc2 import Panel
    p = Panel()
    p.load(P["ECHO"])
    p.set_inputs(77)
    p.reset()
    n = 0
    while p.sim.v("HLT_n") == 1 and n < 50:
        p.single_step()
        n += 1
    assert p.shown == [77] and p.display() == "  77" and n == pc2.PC2(P["ECHO"], in0=77).run().cycles - 1


def test_bus_fight_is_reported():
    """The book's deliberate mistake: U26 OE wired to GND, so the switch buffer is always on."""
    N = build()
    pc = N.chips["U26"]
    pc.pinnet[19] = "GND"
    b = Bench(N)
    b.load([0xC0, 0x70, 0x00])
    b.reset()
    b.run(100)
    nets = {c[0] for c in b.sim.contention}
    assert {f"RD{k}" for k in range(8)} & nets


def test_timed_pc2_runs_echo():
    from bbench.projects.pc2 import Panel
    p = Panel(mode="timed")
    p.load(P["ECHO"])
    p.set_inputs(42)
    p.reset()
    s = p.sim
    s.problems.items.clear()
    s.problems._index.clear()
    s.set("RUN / STEP", "RUN")
    r = s.run("halt", limit=50)
    assert r["done"] and s.word("OUT", 8) == 42
    assert not [e for e in s.errors if e["kind"] in ("floating", "setup", "hold", "eeprom-write")]
    assert s.violations == []
    # with worst-case datasheet delays some bus hand-overs overlap briefly (see docs/engine.md)
    for e in s.errors:
        if e["kind"] == "contention":
            assert e["where"]["to_ns"] - e["where"]["from_ns"] < 50


# ---------------------------------------------------------------- the parts of the kit
# The kit's bill of materials (book: assets/tables/bom.html; pc2/bom2/lines.json): logic chips
# with their quantities. "74HCT283 or 74HC283" in the BOM: the project uses the 74HCT part.
KIT_LOGIC = {"74HCT00": 1, "74HCT02": 1, "74HCT04": 2, "74HCT08": 2, "74HCT32": 1, "74HCT86": 2,
             "74HCT107": 1, "74HCT138": 1, "74HCT139": 2, "74HCT157": 2, "74HCT161": 2, "74HCT173": 9,
             "74HCT174": 1, "74HCT245": 9, "74HCT283": 2, "74HCT377": 1}
KIT_OTHER = {"NE555": 4, "AS6C62256": 1, "AT28C256": 4}


def _chip_counts(project):
    from collections import Counter
    import bbench.chips as chips
    return Counter(p["type"] for p in project.data["parts"] if p["type"] in chips.REGISTRY)


def test_pc2_chips_match_kit_bom():
    from bbench.projects import pc2 as whole
    counts = _chip_counts(whole())
    assert {t: n for t, n in counts.items() if t.startswith("74")} == KIT_LOGIC
    assert {t: n for t, n in counts.items() if not t.startswith("74")} == KIT_OTHER
    assert not [t for t in counts if t.startswith("74HC") and not t.startswith("74HCT")]


def test_pc2_chips_match_bom_file_when_present():
    """Cross-check with the kit BOM file itself (skipped when it is not on this computer)."""
    import json
    import os
    import re
    path = "/home/claude/pc2/bom2/lines.json"
    if not os.path.exists(path):
        pytest.skip("kit BOM file not present")
    want = {}
    for line in json.load(open(path)):
        if line["group"].startswith("Logic"):
            want[re.match(r"74HCT\d+", line["part"]).group(0)] = line["qty"]
    assert want == KIT_LOGIC


def test_hct_parts_have_ttl_thresholds_and_ti_datasheets():
    import bbench.chips as chips
    for t in KIT_LOGIC:
        cls = chips.get(t)
        assert cls.FAMILY == "HCT" and cls.levels()["VIH"] == 2.0 and cls.levels()["VIL"] == 0.8, t
        assert cls.DATASHEET.startswith("https://www.ti.com/lit/ds/symlink/") and "74hct" in cls.DATASHEET, t
        # same logic as the HC part: a variant of it
        assert issubclass(cls, chips.get(t.replace("HCT", "HC"))), t
    assert chips.get("74HC245").levels()["VIH"] == 3.15


def test_pc2_has_no_logic_level_warnings():
    from bbench.projects import pc2 as whole
    assert [x for x in whole().check() if x["kind"] == "levels"] == []


def test_a_74hc_part_after_a_555_or_memory_is_flagged():
    """The reason the kit is 74HCT: a 555 (VOH 2.75 V) or a memory (2.4 V) cannot drive a
    74HC input (VIH 3.15 V at 4.5 V)."""
    import copy
    from bbench.projects import pc2 as whole
    p = whole()
    d = copy.deepcopy(p.data)
    for part in d["parts"]:
        if part["id"] in ("U5", "U25"):          # the clock-select AND (after the 555s), RAM transceiver
            part["type"] = part["type"].replace("74HCT", "74HC")
    import bbench
    msgs = [x for x in bbench.Project.load(d).check() if x["kind"] == "levels"]
    assert {m["where"]["part"] for m in msgs} == {"U5", "U25"}, msgs
    assert all(m["severity"] == "warning" and "74HCT" in m["message"] for m in msgs)


# ---------------------------------------------------------------- the rack and the sheets
def test_pc2_boards_sit_in_the_books_rack():
    from bbench.projects import pc2 as whole
    from bbench.projects.pc2 import RACK, RACK_PITCH_X, RACK_PITCH_Y
    bbs = whole().data["breadboards"]
    assert len(bbs) == 17
    for b in bbs:
        c, s = RACK[b["name"]]
        assert (b["x"], b["y"]) == (c * RACK_PITCH_X, s * RACK_PITCH_Y), b["name"]
    assert len({(b["x"], b["y"]) for b in bbs}) == 17
    # boards do not overlap (a board is drawn 640 x 236)
    assert RACK_PITCH_X > 640 and RACK_PITCH_Y > 236


def test_pc2_schematic_parts_do_not_crowd():
    """Every part has room for its symbol and net tags, as the app draws them, on the whole
    machine and on every module project."""
    from bbench.projects import pc2 as whole, module, MODULES
    from bbench.projects.sheet import overlaps
    d = whole().data
    assert overlaps(d) == []
    assert len({(p["x"], p["y"], p["props"].get("module")) for p in d["parts"]}) == len(d["parts"])
    for m in MODULES:
        md = module(m).data
        assert overlaps(md) == [], m
        assert all(p["props"].get("module") == m for p in md["parts"]), m


# ---------------------------------------------------------------- timed runs from the live state
def test_timed_run_starts_from_loaded_program():
    """A timed simulator started from a zero-delay one keeps its RAM (the program), registers
    and switches, and runs the program on (the analyser's "Timed run from the live state")."""
    import bbench
    from bbench.projects.pc2 import Panel
    proj = bbench.projects.pc2()
    panel = Panel(proj.simulator("zero", record=False))
    panel.load(P["ECHO"])
    panel.set_inputs(40)
    panel.reset()
    live = panel.sim
    ram = dict(live.N.parts["U24"].state)
    T = proj.simulator("timed", start=live)
    assert T.N.parts["U24"].state == ram                         # the program is there
    assert T.N.parts["U3"].state == live.N.parts["U3"].state     # RUN/STEP debouncer
    assert T.state()["switches"]["S3"] == live.state()["switches"]["S3"]
    T.set("RUN / STEP", "RUN")
    r = T.run("halt", limit=50)
    assert r["done"] and T.word("OUT", 8) == 40
    assert T.N.parts["U24"].state == ram                         # not written on the way
    assert not [e for e in T.errors if e["kind"] in ("floating", "setup", "hold", "eeprom-write")]
    # the live simulation is untouched and can still run the program itself
    assert live.v("HLT_n") == 1 and panel.run() and panel.display() == "  40"


def test_snapshot_round_trip_zero_to_zero():
    import bbench
    from bbench.projects.pc2 import Panel
    proj = bbench.projects.pc2()
    a = Panel(proj.simulator("zero", record=False))
    a.load(P["ADD"])
    a.set_inputs(9, 200)
    a.reset()
    b = Panel(proj.simulator("zero", record=False, start=a.sim.snapshot()))
    assert b.run() and b.display() == " 209"


def test_module_inputs_are_not_nets_the_module_drives():
    """A module project's input switches stand in for signals from other modules only: not for
    nets its own always-enabled outputs drive (74x173 Q with M, N on GND; ROMs with OE on GND),
    which would fight the switch."""
    from bbench.projects import module
    ins = {m: {p["props"]["label"] for p in module(m).data["parts"] if p["props"].get("role") == "input"}
           for m in ("A register", "Control", "Output", "Display")}
    assert not {f"A{k}" for k in range(8)} & ins["A register"]
    assert {f"BUS{k}" for k in range(8)} <= ins["A register"]          # the bus comes from elsewhere
    assert "HLT_n" not in ins["Control"] and {"OP0", "FC", "CLK_n"} <= ins["Control"]
    assert not {f"SR{k}" for k in range(8)} & ins["Output"]
    assert {f"SR{k}" for k in range(8)} <= ins["Display"]


def test_display_scan_clock_runs_in_live_simulation():
    """run_ns moves the display scan 555 (U36) too: SCANCLK, the digit counter and the digit
    selects change while the main clock runs (bug: they stayed constant)."""
    import bbench
    from bbench.projects.pc2 import Panel
    proj = bbench.projects.pc2()
    s = proj.simulator("zero", record=False)
    panel = Panel(s)
    panel.load(P["COUNTDOWN"])
    panel.set_inputs(200)
    panel.reset()
    s.set("RUN / STEP", "RUN")
    seen = set()
    for _ in range(30):
        s.run_ns(1e6)
        seen.add((s.v("SCANCLK"), s.v("DIG0"), s.v("DIG1"), s.v("DSEL0_n"), s.v("DSEL3_n")))
    assert {v[0] for v in seen} == {0, 1}
    assert {(v[1], v[2]) for v in seen} == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert {v[3] for v in seen} == {0, 1} and {v[4] for v in seen} == {0, 1}
    assert all(c["role"] != "scan" for c in s.clocks()) and s.scan_clocks()[0]["part"] == "U36"


def test_timed_rom_outputs_unknown_while_address_settles():
    """AT28C256: outputs unknown from tOH (0 ns) to tACC (150 ns) after an address change,
    so a timed run reports the possible bus overlaps of that window as warnings."""
    from bbench.chips import base
    from bbench.projects.pc2 import Panel
    rom = base.get("AT28C256")
    assert rom.ADDR_HOLD == 0 and rom.tpd("A0", "IO0") == 150 and rom.tdis("OE", "IO0") == 50
    ram = base.get("AS6C62256")
    assert ram.ADDR_HOLD == 10 and ram.tpd("OE", "IO0") == 30 and ram.tdis("OE", "IO0") == 20
    import bbench
    proj = bbench.projects.pc2()
    panel = Panel(proj.simulator("zero", record=False))
    panel.load(P["ECHO"])
    panel.set_inputs(42)
    panel.reset()
    T = proj.simulator("timed", start=panel.sim)
    T.record()
    T.set("RUN / STEP", "RUN")
    assert T.run("halt", limit=50)["done"] and T.word("OUT", 8) == 42
    tr = {x["name"]: x["changes"] for x in T.trace(["AO_n", "CO_n"])["signals"]}
    assert any(v == "X" for _, v in tr["CO_n"])             # control lines unknown while the ROM settles
    ov = [o for o in T.overlaps if o["kind"] == "overlap" and o["net"].startswith("BUS")]
    assert ov and max(o["ns"] for o in ov) < 200
    assert any(e["kind"] == "overlap" and e["severity"] == "warning" for e in T.errors)
    assert not [e for e in T.errors if e["kind"] in ("floating", "setup", "hold", "eeprom-write")]


def test_hct_timing_from_datasheets():
    """FC-01..FC-07: 4.5 V, 25 degC maxima (setup/hold minima) from the cited TI sheets."""
    from bbench.chips import base
    g = base.get
    assert g("74HCT173").tpd("CLK", "1Q") == 40 and g("74HCT173").tpd("CLR", "1Q") == 44
    assert g("74HCT173").tpd("M", "1Q") == 30 and g("74HCT173").setup_ns("1D") == 18
    assert g("74HCT173").setup_ns("G1") == 12 and g("74HCT173").hold_ns("1D") == 0
    h161 = g("74HCT161")
    assert (h161.setup_ns("A"), h161.setup_ns("ENP"), h161.setup_ns("LOAD")) == (10, 13, 12)
    assert (h161.hold_ns("A"), h161.hold_ns("ENT"), h161.hold_ns("LOAD")) == (5, 3, 3)
    assert h161.tpd("CLR", "QA") == 50 and h161.tpd("CLK", "QA") == 39
    h107 = g("74HCT107")
    assert (h107.tpd("1CLK", "1Q"), h107.tpd("1CLK", "1QN"), h107.tpd("1CLR", "1Q")) == (43, 40, 38)
    assert h107.hold_ns("1J") == 5 and h107.setup_ns("1J") == 20
    assert g("74HCT174").tpd("CLK", "1Q") == 40 and g("74HCT174").setup_ns("1D") == 16
    assert g("74HCT377").setup_ns("E") == 12 and g("74HCT377").hold_ns("D0") == 3 and g("74HCT377").hold_ns("E") == 5
    assert [g(t).tpd("1A", "1Y") for t in ("74HCT00", "74HCT02", "74HCT04", "74HCT08", "74HCT32", "74HCT86")] == \
        [20, 20, 20, 24, 24, 32]
    assert (g("74HCT157").tpd("1A", "1Y"), g("74HCT157").tpd("S", "1Y"), g("74HCT157").tpd("G", "1Y")) == (25, 29, 27)
    assert g("74HCT139").tpd("1A", "1Y0") == 34 and g("74HCT138").tpd("A", "Y0") == 35
    h245 = g("74HCT245")
    assert (h245.tpd("A1", "B1"), h245.tpd("OE", "B1"), h245.tdis("OE", "B1")) == (26, 32, 30)
    assert h245.DRIVE["abs_max_mA"] == 25 and h245.DRIVE["test_mA"] == 4
    h283 = g("74HCT283")
    assert (h283.tpd("A1", "C4"), h283.tpd("C0", "C4"), h283.tpd("A1", "S3"), h283.tpd("C0", "S4")) == (48, 46, 49, 53)
    assert "cd74hct86" in g("74HCT86").DATASHEET and "doc0006" not in g("AT28C256").DATASHEET
    assert "rev1.2" in g("AS6C62256").DATASHEET


def test_book_module_names():
    """ED-02: the book's imports work wherever the wheel is installed (bench, pc2, pc2tools)."""
    import importlib
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "book_modules"))
    try:
        for name in ("bench", "pc2", "pc2tools"):
            sys.modules.pop(name, None)
        bench = importlib.import_module("bench")
        pc2 = importlib.import_module("pc2")
        pc2tools = importlib.import_module("pc2tools")
    finally:
        sys.path.pop(0)
    b = bench.Bench()
    b.load([0xC0, 0x70, 0x00])
    b.set_bits("input A switch {}", 200)
    b.reset()
    b.run()
    assert b.display() == " 200"
    assert pc2.PC2 and pc2tools.NAMES[12] == "IN"
    rows = pc2tools.trace(pc2.asm(["IN 0", "OUT 0", "HALT"]), in0=9)
    assert len(rows) == 9 and rows[-1]["out"] == 9


def test_book_modules_pc2_custom_and_pc2plus():
    """Chapter 12's finished pc2_custom and Chapter 13's pc2plus, as the wheel installs them."""
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "book_modules"))
    try:
        import pc2_custom
        import pc2plus
    finally:
        sys.path.pop(0)
    m = pc2_custom.PC2(pc2_custom.asm(["LDI 1", "OUT 0", "DBL", "JNC 1", "HALT"])).run()
    assert m.shown == [1, 2, 4, 8, 16, 32, 64, 128]
    old = pc2.ROM
    assert {a >> 3 & 15 for a in old if old[a] != pc2_custom.ROM[a]} == {0xE, 0xF}
    mem, lab = pc2plus.asm(["IN 0", "STORE x", "IN 1", "ADD x", "OUT 0", "HALT", "x: data 0"])
    assert pc2plus.run(mem, 5, 6).out == 11
