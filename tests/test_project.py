"""Project format: load/save round trip, check(), simulator(), JSON-compatible API."""
import json

import bbench
from bbench.projects import catalogue, get
from bbench.projects.examples import EXAMPLES


def test_pc2_round_trip_exact():
    p = bbench.projects.pc2()
    text = p.save()
    q = bbench.Project.load(text)
    assert q.save() == text
    assert q.to_dict() == json.loads(text)
    assert bbench.Project.load(json.loads(text)).save() == text


def test_examples_round_trip_and_check_clean():
    for k in EXAMPLES:
        p = get(k)
        assert bbench.Project.load(p.save()).save() == p.save()
        assert [x for x in p.check() if x["severity"] == "error"] == [], k


def test_unknown_keys_kept():
    d = get("nand-gate").to_dict()
    d["my_app"] = {"zoom": 2}
    d["parts"][0]["props"]["note"] = "café ✓"
    p = bbench.Project.load(json.dumps(d))
    assert json.loads(p.save()) == d


def test_pc2_project_shape():
    p = bbench.projects.pc2()
    d = p.data
    assert d["format"] == "breadboard-bench/1"
    assert len(d["breadboards"]) == 17 and len(d["links"]) == 210
    chips = [x for x in d["parts"] if x["type"].startswith(("74", "AT28", "AS6", "NE5"))]
    assert len(chips) == 48
    assert {x["type"] for x in d["parts"] if x["id"] in ("U42", "U43", "U44", "U34")} == {"AT28C256"}
    assert p.check() == []
    assert d["parts"][[x["id"] for x in d["parts"]].index("U20")]["props"]["label"].startswith("program counter")


def test_pc2_u20_clocked_by_clk_n():
    p = bbench.projects.pc2()
    clk_n = next(n for n in p.data["nets"] if n["name"] == "CLK_n")
    assert ["U20", "2"] in clk_n["pins"]


def test_module_projects_simulate():
    from bbench.projects.pc2 import MODULES
    for m in MODULES:
        p = bbench.projects.module(m)
        s = p.simulator("zero")
        st = s.state()
        json.dumps(st)
        assert not [e for e in s.errors if e["kind"] in ("unconnected", "no-driver")], (m, s.errors[:3])


def test_a_register_module_loads_from_switches():
    p = bbench.projects.module("A register")
    s = p.simulator()
    label = {x["props"].get("label"): x["id"] for x in p.data["parts"] if x["id"].startswith("IN")}
    for k in range(8):
        s.drive(label[f"BUS{k}"], (0xA5 >> k) & 1)
    s.drive(label["AO_n"], 1)
    s.drive(label["AI_n"], 0)
    s.update()
    s.press(label["CLK"])
    assert s.word("A", 8) == 0xA5
    assert sum(1 for k, v in s.state()["leds"].items() if v) >= 4


def test_api_values_are_json():
    p = bbench.projects.pc2()
    assert all(isinstance(x["pins"], list) for x in bbench.library())
    json.dumps(bbench.library())
    json.dumps(p.check())
    json.dumps(catalogue())
    s = p.simulator("zero")
    s.set("S3.4", True)
    s.step()
    st = s.state()
    assert set(st) >= {"nets", "leds", "digits", "errors"}
    assert st["switches"]["S3"][3] == 1
    json.dumps(st)
    json.dumps(s.trace(["CLK", "BUS0"]))


def test_bad_project_problems_not_crash():
    d = get("nand-gate").to_dict()
    d["parts"].append({"id": "U9", "type": "74XX999"})
    d["nets"].append({"name": "Q", "pins": [["U1", "99"]]})
    pr = bbench.Project.load(d).check()
    msgs = " ".join(x["message"] for x in pr)
    assert "74XX999" in msgs and "no pin 99" in msgs


def test_web_glue_timed_run_keeps_live_simulation():
    """web/engine_glue.py (the app's door to the engine): a timed run for the analyser starts
    from the live simulation and leaves it as it was."""
    import json
    import os
    import runpy
    from bbench.projects.pc2_programs import P
    g = runpy.run_path(os.path.join(os.path.dirname(__file__), "..", "web", "engine_glue.py"))
    call = lambda fn, *a: json.loads(g["_bb_call"](fn, json.dumps(list(a))))  # noqa: E731
    g["_bb_init"]()
    proj = json.loads(json.dumps(bbench.projects.pc2().to_dict()))
    assert "error" not in call("loadProject", proj)
    call("newSim", "zero")
    cl = call("clocks")["result"]
    assert cl[0]["part"] == "U1" and cl[0]["role"] == "main" and all(c["role"] != "scan" for c in cl)
    # enter ECHO by hand: PROGRAM mode, address and data switches, WRITE
    call("set", "PROGRAM / RUN", "PROG")
    for addr, byte in enumerate(P["ECHO"]):
        call("set", "S1", addr)
        call("set", "S2", byte)
        call("set", "WRITE", True)
        call("set", "WRITE", False)
    call("set", "PROGRAM / RUN", "RUN")
    call("set", "S3", 40)
    call("set", "RESET", True)
    call("set", "RESET", False)
    call("set", "RUN / STEP", "RUN")
    before = call("state")["result"]["nets"]
    r = call("timedRun", 3e6, ["OUT0", "OUT3", "OUT5", "HLT_n"], True)["result"]
    assert r["from"] == "current" and r["trace"]["t_end"] == 3e6
    last = {s["name"]: s["changes"][-1][1] for s in r["trace"]["signals"]}
    assert last == {"OUT0": 0, "OUT3": 1, "OUT5": 1, "HLT_n": 0}      # 40 = 0b101000, halted
    assert call("state")["result"]["nets"] == before                   # the live sim did not move
    rr = call("runNs", 1e5, 50)["result"]
    assert rr["edges"] > 0
