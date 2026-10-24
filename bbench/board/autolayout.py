"""Automatic breadboard layout: put every part on a hole and list every wire
(generalised from the proven pc2sim/layout.py; for PC-2 it gives the book's layout).

layout(project_data, netlist, board_order, chain_order) -> (breadboards, links) in
the project format. Each part goes on the board named by its props["board"] (or
props["module"], or the first board).

Rules, in order: chips (one DIP each; 0.3 in ones in e and f, 0.6 in ones with pin 1 in
hole c and the other row in g); DIP switch banks with their pull-down network (RN props
"bank"); other multi-pin parts (SIP networks, buttons, slides/jumpers/transistors in hole
h, pots in hole i, digits in c and g); two-leg parts between two signal nets as a bridge
across the gap; two-leg parts from a net to a rail; decoupling capacitors from a hole in
their chip's VCC row to the top GND rail; other rail-to-rail parts (bulk capacitors)
across the top rails. Then the wires of each net on each board as a tree, power wires to
the rails (a chip's GND pin is wired across to the TOP GND rail, so each chip and its
capacitor share the top rails: a short decoupling loop), and board-to-board wires chained
in chain_order.
"""
from collections import defaultdict

from ..core.netlist import lookup_type
from .model import ROWS, BOT, TOP, half

RAIL_OF = {("B", "VCC"): "B+", ("B", "GND"): "B-", ("T", "VCC"): "T+", ("T", "GND"): "T-"}
RAIL_NETS = {"VCC": 1, "GND": 0}
WIDE_COLS = ("c", "g")          # 0.6 in parts: 6 pitches apart (the gap is 3 pitches)
WIDE_BODY = "def"


class _Board:
    def __init__(self, name):
        self.name = name
        self.used = {}
        self.blocked = set()
        self.node_net = {}
        self.place = []
        self.next = 1
        self.wires = []
        self.overflow = []
        self.ports = defaultdict(list)
        self.gnd_up = set()            # bottom-half GND nodes wired to the top GND rail

    def rows(self, n, gap=1):
        r = self.next
        self.next += n + gap
        if r + n - 1 > ROWS:
            self.overflow.append(n)
        return r

    def leg(self, ref, pin, row, col, net):
        if row > ROWS:
            self.overflow.append(f"{ref} pin {pin} off the board")
            return
        h = (row, col)
        if h in self.used or h in self.blocked:
            raise RuntimeError(f"{self.name}: hole {h} used twice ({ref} pin {pin})")
        self.used[h] = (ref, pin)
        node = (row, half(col))
        old = self.node_net.get(node)
        if old not in (None, net):
            raise RuntimeError(f"{self.name}: {ref} pin {pin} at {node} would join {old} and {net}")
        self.node_net[node] = net

    def free(self, node):
        row, hf = node
        if row > ROWS:
            return []
        order = "abcde" if hf == "B" else "jihgf"
        return [c for c in order if (row, c) not in self.used and (row, c) not in self.blocked]

    def take(self, node, tag, near_gap=False):
        f = self.free(node)
        if not f:
            return None
        h = (node[0], f[-1] if near_gap else f[0])
        self.used[h] = tag
        return h

    def fresh_node(self, net, prefer="T"):
        for row in range(1, ROWS + 1):
            for hf in (prefer, "B" if prefer == "T" else "T"):
                node = (row, hf)
                if node in self.node_net:
                    continue
                cols = BOT if hf == "B" else TOP
                if any((row, c) in self.used or (row, c) in self.blocked for c in cols):
                    continue
                self.node_net[node] = net
                return node
        self.overflow.append(f"junction for {net}")
        return None


def _colour(net, colours):
    if colours:
        return colours(net)
    return {"VCC": "#D7372B", "GND": "#222222"}.get(net, "#4E9F3D")


# where boards go when no positions are given: columns of six, in board order
BOARD_PITCH_X, BOARD_PITCH_Y = 720, 260


def layout(data, N, board_order=None, chain_order=None, colours=None, positions=None):
    """positions: {board name: (x, y)} on the breadboard sheet (default: columns of six)."""
    parts = data.get("parts", [])
    order = list(board_order or [])
    boards = {b: _Board(b) for b in order}

    def board_of(p):
        pr = p.get("props", {})
        return pr.get("board") or pr.get("module") or (order[0] if order else "Board")
    for p in parts:
        boards.setdefault(board_of(p), _Board(board_of(p)))
    chain = list(chain_order or order or list(boards))
    for b in boards:
        if b not in chain:
            chain.append(b)
    pinnet = N.pinnet
    cls_of = {p["id"]: lookup_type(p["type"]) for p in parts}
    chips = [p for p in parts if hasattr(cls_of[p["id"]], "eval") and not hasattr(cls_of[p["id"]], "FOOTPRINT")]
    chip_ids = {p["id"] for p in chips}
    others = [p for p in parts if p["id"] not in chip_ids]
    done = set()
    chip_rows = {}
    chip_power = {}                    # ref -> (board, VCC pin hole)

    # 1. chips
    for p in chips:
        ref, cls = p["id"], cls_of[p["id"]]
        B = boards[board_of(p)]
        n = len(cls.PINS)
        wide = cls.width() == 6
        r = B.rows(n // 2)
        bcol, tcol = WIDE_COLS if wide else ("e", "f")
        vcc_hole = None
        for q in range(1, n + 1):
            net = pinnet[ref].get(q) or f"NC:{ref}.{q}"
            hole = (r + q - 1, bcol) if q <= n // 2 else (r + (n - q), tcol)
            B.leg(ref, q, hole[0], hole[1], net)
            kind = cls.PINS[q][1] if q in cls.PINS else None
            if kind == "vcc" and net == "VCC" and half(hole[1]) == "T":
                vcc_hole = hole
            elif kind == "gnd" and net == "GND" and half(hole[1]) == "B":
                B.gnd_up.add((hole[0], "B"))
        if vcc_hole:
            chip_power[ref] = vcc_hole
        if wide:
            for row in range(r, r + n // 2):
                for c in WIDE_BODY:
                    B.blocked.add((row, c))
        B.place.append({"part": ref, "row": r, "hole": bcol})
        chip_rows[ref] = (r, r + n // 2 - 1)
        done.add(ref)

    by_id = {p["id"]: p for p in parts}

    # 2. DIP switch banks with their resistor networks
    for p in others:
        bank = p.get("props", {}).get("bank")
        if not (p["type"].startswith("RN") and bank and bank in by_id):
            continue
        sw = by_id[bank]
        B = boards[board_of(p)]
        n = cls_of[bank].N
        r = B.rows(n + 1)
        rn_pins = pinnet[p["id"]]
        B.leg(p["id"], 1, r, "j", rn_pins.get(1))
        for k in range(n):
            row = r + 1 + k
            B.leg(p["id"], k + 2, row, "j", rn_pins.get(k + 2))
            B.leg(bank, k + 1, row, "e", pinnet[bank].get(k + 1))
            B.leg(bank, 2 * n - k, row, "f", pinnet[bank].get(2 * n - k))
        B.place.append({"part": bank, "row": r + 1, "hole": "e"})
        B.place.append({"part": p["id"], "row": r, "hole": "j"})
        done.update((p["id"], bank))

    # 3. other multi-pin parts
    for p in others:
        ref, t = p["id"], p["type"]
        if ref in done:
            continue
        cls = cls_of[ref]
        B = boards[board_of(p)]
        pn = pinnet[ref]
        fp = cls.FOOTPRINT.get("kind")
        if t.startswith("RN"):
            n = len(cls.PINS) - 1
            r = B.rows(n + 1)
            for q in range(1, n + 2):
                B.leg(ref, q, r + q - 1, "j", pn.get(q))
            B.place.append({"part": ref, "row": r, "hole": "j"})
        elif fp == "button":
            r = B.rows(3)
            B.leg(ref, 1, r, "e", pn.get(1))
            B.leg(ref, 2, r, "f", pn.get(2))
            B.leg(ref, 3, r + 2, "e", pn.get(3))
            B.leg(ref, 4, r + 2, "f", pn.get(4))
            B.place.append({"part": ref, "row": r, "hole": "e"})
        elif fp == "sip" and len(cls.PINS) == 3 and cls.FOOTPRINT.get("pitch", 1) == 1:
            r = B.rows(3)
            for q in (1, 2, 3):
                B.leg(ref, q, r + q - 1, "h", pn.get(q))
            B.place.append({"part": ref, "row": r, "hole": "h"})
        elif t == "POT":
            r = B.rows(5)
            for k, q in zip((0, 2, 4), (1, 2, 3)):
                B.leg(ref, q, r + k, "i", pn.get(q))
            B.place.append({"part": ref, "row": r, "hole": "i"})
        elif fp == "dip":
            n = len(cls.PINS)
            w = cls.FOOTPRINT.get("width", 3)
            h = n // 2
            r = B.rows(h)
            bcol, tcol = WIDE_COLS if w == 6 else ("e", "f")
            for q in range(1, n + 1):
                net = pn.get(q) or f"NC:{ref}.{q}"
                if q <= h:
                    B.leg(ref, q, r + q - 1, bcol, net)
                else:
                    B.leg(ref, q, r + (n - q), tcol, net)
            if w == 6:
                for k in range(h):
                    for c in WIDE_BODY:
                        B.blocked.add((r + k, c))
            B.place.append({"part": ref, "row": r, "hole": bcol})
        else:
            continue
        done.add(ref)

    # 4. two-leg parts between two signal nets
    rail_attach = []
    bridges = {}
    for p in others:
        ref = p["id"]
        if ref in done or len(cls_of[ref].PINS) != 2 or cls_of[ref].FOOTPRINT.get("kind") == "virtual":
            continue
        pn = pinnet[ref]
        if 1 not in pn or 2 not in pn:
            continue
        n1, n2 = pn[1], pn[2]
        if n1 in RAIL_NETS and n2 in RAIL_NETS:
            continue
        if n1 in RAIL_NETS or n2 in RAIL_NETS:
            rail_attach.append(p)
            continue
        B = boards[board_of(p)]
        if n1.endswith("~LED"):
            bot, top = (1, n1), (2, n2)
        elif n2.endswith("~LED"):
            bot, top = (2, n2), (1, n1)
        else:
            bot, top = (1, n1), (2, n2)
        r = B.rows(1, gap=0)
        B.leg(ref, bot[0], r, "d", bot[1])
        B.leg(ref, top[0], r, "f", top[1])
        bridges[ref] = {"part": ref, "legs": {str(bot[0]): [r, "d"], str(top[0]): [r, "f"]}}
        B.place.append(bridges[ref])
        done.add(ref)

    # 5. parts from a node to a rail
    for p in rail_attach:
        ref = p["id"]
        B = boards[board_of(p)]
        pn = pinnet[ref]
        if pn[1] in RAIL_NETS:
            rk, sk = 1, 2
        else:
            rk, sk = 2, 1
        rail_net, sig = pn[rk], pn[sk]
        nodes = [nd for nd, nt in B.node_net.items() if nt == sig and B.free(nd)]
        nodes = [nd for nd in nodes if len(B.free(nd)) >= 2] or nodes
        if nodes:
            node = sorted(nodes, key=lambda nd: -len(B.free(nd)))[0]
        else:
            node = B.fresh_node(sig, "B")
        if node is None:
            continue
        hole = B.take(node, (ref, sk))
        rail = RAIL_OF[(node[1], rail_net)]
        B.place.append({"part": ref, "legs": {str(sk): [hole[0], hole[1]], str(rk): [rail, node[0]]}})
        done.add(ref)

    # decoupling capacitors: from a hole in their chip's VCC row to the top GND rail (the rail
    # the chip's GND pin is wired to); any other rail-to-rail part (a bulk capacitor) across the
    # top rails, by the board's first 555 or else at row 2
    for p in others:
        ref = p["id"]
        if ref in done or len(cls_of[ref].PINS) != 2:
            continue
        pn = pinnet[ref]
        if pn.get(1) in RAIL_NETS and pn.get(2) in RAIL_NETS:
            B = boards[board_of(p)]
            label = p.get("props", {}).get("label", "")
            chip = p.get("props", {}).get("decouples") or (label.split()[-1] if label.startswith("decoupling") else None)
            vk = 1 if pn[1] == "VCC" else 2
            if chip in chip_power and pn[1] != pn[2]:
                vrow, vcol = chip_power[chip]
                hole = B.take((vrow, "T"), (ref, vk))
                if hole is not None:
                    B.place.append({"part": ref, "legs": {str(vk): [hole[0], hole[1]], str(3 - vk): ["T-", vrow]}})
                    done.add(ref)
                    continue
            timers = [q for q in chips if board_of(q) == B.name and q["type"].endswith("555")]
            row = p.get("props", {}).get("rail_row") or (
                chip_rows[timers[0]["id"]][0] + 2 if timers else (chip_rows[chip][0] if chip in chip_rows else 2))
            rl = {1: "T+" if pn[1] == "VCC" else "T-", 2: "T+" if pn[2] == "VCC" else "T-"}
            B.place.append({"part": ref, "legs": {"1": [rl[1], row], "2": [rl[2], row]}})
            done.add(ref)

    # 6. wires
    present = defaultdict(set)
    for B in boards.values():
        for node, net in B.node_net.items():
            if net and not net.startswith("NC:") and net not in RAIL_NETS:
                present[net].add(B.name)
    for B in boards.values():
        bynet = defaultdict(list)
        for node, net in B.node_net.items():
            bynet[net].append(node)
        for net, nodes in bynet.items():
            if net is None or net.startswith("NC:"):
                continue
            if net in RAIL_NETS:
                for node in sorted(nodes):
                    up = net == "GND" and node in B.gnd_up
                    h = B.take(node, ("wire", net), near_gap=up)
                    if h is None:
                        B.overflow.append(f"no hole for {net} wire at {node}")
                        continue
                    B.wires.append({"a": [h[0], h[1]], "b": "T-" if up else RAIL_OF[(node[1], net)],
                                    "colour": _colour(net, colours)})
                continue
            need = 0
            if len(present[net]) > 1:
                pos = sorted(present[net], key=chain.index).index(B.name)
                need = 1 if pos in (0, len(present[net]) - 1) else 2
            _tree(B, net, sorted(nodes), need, colours)
    links = []
    ids = {name: f"BB{k + 1}" for k, name in enumerate(boards)}
    for net, bs in present.items():
        if len(bs) < 2:
            continue
        ch = sorted(bs, key=chain.index)
        for b1, b2 in zip(ch, ch[1:]):
            h1 = boards[b1].ports[net].pop(0)
            h2 = boards[b2].ports[net].pop(0)
            links.append({"a": [ids[b1], [h1[0], h1[1]]], "b": [ids[b2], [h2[0], h2[1]]],
                          "colour": _colour(net, colours)})
    out = []
    for k, (name, B) in enumerate(boards.items()):
        if not B.place and not B.wires:
            continue
        if positions and name in positions:
            x, y = positions[name]
        else:
            x, y = (len(out) // 6) * BOARD_PITCH_X, (len(out) % 6) * BOARD_PITCH_Y
        bb = {"id": ids[name], "name": name, "x": x, "y": y, "placements": B.place, "wires": B.wires}
        if B.overflow:
            bb["overflow"] = [str(o) for o in B.overflow]
        out.append(bb)
    return out, links


def _tree(B, net, nodes, need_ports, colours):
    cap = {nd: len(B.free(nd)) for nd in nodes}
    total_need = 2 * (len(nodes) - 1) + need_ports
    while sum(cap.values()) < total_need or (len(nodes) > 1 and max(cap.values()) < 2 and len(nodes) > 2):
        j = B.fresh_node(net)
        if j is None:
            break
        nodes.append(j)
        cap[j] = len(B.free(j))
        total_need = 2 * (len(nodes) - 1) + need_ports
    order = sorted(nodes, key=lambda nd: -cap[nd])
    connected = [order[0]]
    rem = dict(cap)
    pending = sorted(order[1:], key=lambda nd: nd[0])
    col = _colour(net, colours)
    for nd in pending:
        targets = [t for t in connected if rem[t] >= 1]
        if not targets:
            B.overflow.append(f"no hole to join {net} at {nd}")
            continue
        t = min(targets, key=lambda t: (rem[t] < 2, abs(t[0] - nd[0])))
        ha = B.take(t, ("wire", net))
        hb = B.take(nd, ("wire", net))
        rem[t] -= 1
        rem[nd] -= 1
        connected.append(nd)
        B.wires.append({"a": [ha[0], ha[1]], "b": [hb[0], hb[1]], "colour": col})
    for _ in range(need_ports):
        cands = [t for t in connected if rem[t] >= 1]
        if not cands:
            B.fresh_node(net)
            B.overflow.append(f"no hole for board-to-board {net}")
            continue
        t = max(cands, key=lambda c: rem[c])
        h = B.take(t, ("port", net))
        rem[t] -= 1
        B.ports[net].append(h)
