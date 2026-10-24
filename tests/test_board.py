"""Breadboard checker: the proven layouts check clean; mistakes are found."""
import copy

from bbench.projects import get
from bbench.board.checker import check_boards


def kinds(pr):
    return [x["kind"] for x in pr if x["severity"] == "error"]


def test_pc2_boards_clean():
    assert check_boards(get("pc2").data) == []


def test_missing_wire_found():
    p = get("xor-from-nand")
    d = copy.deepcopy(p.data)
    w = [w for w in d["breadboards"][0]["wires"] if not isinstance(w["b"], str)]
    assert w
    d["breadboards"][0]["wires"].remove(w[0])
    pr = check_boards(d)
    assert "missing" in kinds(pr)
    assert any("separate pieces" in x["message"] for x in pr)


def test_missing_link_found_on_pc2():
    d = copy.deepcopy(get("pc2").data)
    d["links"].pop(0)
    assert "missing" in kinds(check_boards(d))


def test_short_found():
    d = copy.deepcopy(get("xor-from-nand").data)
    bb = d["breadboards"][0]
    holes = {}
    for pl in bb["placements"]:
        if pl["part"] == "U1":
            row = pl["row"]
    # join U1 pin 1 (A) to U1 pin 2 (B) through two free holes of their rows
    bb["wires"].append({"a": [row, "a"], "b": [row + 1, "a"], "colour": "#000"})
    pr = check_boards(d)
    assert "short" in kinds(pr)
    assert any(set(x["where"].get("nets", [])) == {"A", "B"} for x in pr if x["kind"] == "short")


def test_hole_used_twice_and_unplaced():
    d = copy.deepcopy(get("nand-gate").data)
    bb = d["breadboards"][0]
    u1 = next(pl for pl in bb["placements"] if pl["part"] == "U1")
    bb["wires"].append({"a": [u1["row"], u1["hole"]], "b": "B-"})
    bb["placements"] = [pl for pl in bb["placements"] if pl["part"] != "D1"]
    pr = check_boards(d)
    assert "hole" in kinds(pr)
    assert any(x["kind"] == "unplaced" and x["where"].get("part") == "D1" for x in pr)


def test_rail_wire_to_wrong_rail_is_a_short():
    d = copy.deepcopy(get("nand-gate").data)
    bb = d["breadboards"][0]
    for w in bb["wires"]:
        if w["b"] == "T-":
            w["b"] = "T+"
            break
    assert "short" in kinds(check_boards(d))
