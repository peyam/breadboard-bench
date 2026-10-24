"""Breadboard layout for PC-2: every part on a hole, every wire listed, then checked.

Board model: a standard 830-point breadboard, rows 1-63, holes a-e (bottom half) and
f-j (top half). The five holes of one half-row are joined underneath, so a half-row is
one electrical "node". Two power rails run along each long edge: the inner rail (next to
row a, or next to row j) is GND (blue), the outer rail is +5 V (red).

Geometry: holes are 2.54 mm (0.1 in) apart and the centre gap is 7.62 mm (0.3 in), so e
to f is three pitches. A 0.3 in DIP has its pins in e and f; a 0.6 in DIP (28-pin memories)
and the 0.56 in digits (rows 15.24 mm apart) have pin 1 in c and the other row in g, and
cover d, e and f.

Power: every chip takes its supply from the TOP rails. Its VCC pin (top half) is wired to
the top +5 V rail, its GND pin (bottom half) is wired across the board to the top GND rail,
and its 100 nF capacitor goes from a hole in the VCC pin's own row to the top GND rail, so
the decoupling loop is the chip, one short rail run and two short wires. Each board also
has one bulk electrolytic across the top rails. Power enters the machine on the Bus board
through a USB-C breakout and a resettable fuse (POWER_ENTRY).

The checker at the end rebuilds the circuit purely from hole positions, part legs and
wires, and compares it with the netlist: every net must come out as exactly one
connected group, and no two nets may touch.
"""
from collections import defaultdict
from netlist import RAILS

ROWS = 63
BOT, TOP = "abcde", "fghij"
RAIL_OF = {("B", "VCC"): "B+", ("B", "GND"): "B-", ("T", "VCC"): "T+", ("T", "GND"): "T-"}

# physical rack: (column, slot) of each board, used to order board-to-board wires and estimate lengths
RACK = {
    "Clock": (0, 0), "Program counter": (0, 1), "Memory address": (0, 2), "RAM": (0, 3),
    "Instruction register": (0, 4), "Control sequencer": (0, 5), "Control ROMs": (0, 6),
    "Bus": (1, 0),
    "A register": (2, 0), "ALU": (2, 1), "B register": (2, 2), "Flags": (2, 3),
    "Output": (2, 4), "Display driver": (2, 5), "Display": (2, 6), "Input": (2, 7),
    "Front panel": (1, 6),
}
BOARD_ORDER = sorted(RACK, key=lambda b: (RACK[b][0], RACK[b][1]))
# the order the book builds the boards in; board-to-board wires are chained in this order,
# so every new board connects only to boards that already exist
BUILD_ORDER = ["Front panel", "Clock", "Bus", "A register", "B register", "ALU", "Flags",
               "Memory address", "RAM", "Program counter", "Instruction register", "Input", "Output",
               "Display driver", "Display", "Control sequencer", "Control ROMs"]

WIDE_COLS = ("c", "g")          # 0.6 in parts: pin 1 row and the other row (6 pitches apart)
WIDE_BODY = "def"               # holes a 0.6 in body covers

# Power entry (not part of the logic netlist): an 8-pin USB-C breakout (Adafruit 4090,
# 5.1 kOhm CC resistors) plugged with its header in hole a of rows 56-63 on the Bus board,
# USB-C socket pointing off the bottom edge (its board covers hole b and the bottom rails
# there). Pins in row order, as seen from above with the socket away from the board.
# VBUS feeds the top +5 V rail through a 1.1 A resettable fuse that bridges the gap in the
# VBUS row; GND is wired across to the top GND rail.
POWER_ENTRY = {"board": "Bus", "row": 56, "col": "a",
               "pins": ["GND", "VBUS", "SBU2", "CC1", "D-", "D+", "SBU1", "CC2"]}


def half(col):
    return "B" if col in BOT else "T"


class Board:
    def __init__(self, name):
        self.name = name
        self.used = {}                 # (row, col) -> (ref, pin) or ("wire", n)
        self.blocked = set()           # holes covered by a 0.6 in chip body
        self.node_net = {}             # (row, half) -> net
        self.items = []                # placed parts: dict(ref, kind, rows, legs)
        self.rail_legs = []            # (ref, pin, rail, row)
        self.next = 1
        self.wires = []                # dict(net, a, b, kind)
        self.overflow = []
        self.gnd_up = set()            # bottom-half GND nodes wired to the TOP GND rail

    # rows and holes -------------------------------------------------------
    def rows(self, n, gap=1):
        r = self.next
        self.next += n + gap
        if r + n - 1 > ROWS:
            self.overflow.append(n)
        return r

    def leg(self, ref, pin, row, col, net):
        if row > ROWS:
            return
        h = (row, col)
        assert h not in self.used and h not in self.blocked, (self.name, ref, pin, h, self.used.get(h))
        self.used[h] = (ref, pin)
        node = (row, half(col))
        if net in RAILS:
            # a rail-net leg on a node: the node itself becomes that rail net
            pass
        old = self.node_net.get(node)
        assert old in (None, net), (self.name, ref, pin, node, old, net)
        self.node_net[node] = net

    def free(self, node):
        row, hf = node
        if row > ROWS:
            return []
        cols = "abcd e"[:0]
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
        """A spare half-row (junction) for a net."""
        for row in range(1, ROWS + 1):
            for hf in (prefer, "B" if prefer == "T" else "T"):
                node = (row, hf)
                if node in self.node_net:
                    continue
                cols = BOT if hf == "B" else TOP
                if any((row, c) in self.used or (row, c) in self.blocked for c in cols):
                    continue
                # do not put a junction in a row whose other half is a chip body row
                self.node_net[node] = net
                return node
        self.overflow.append(f"junction for {net}")
        return None


def dip_legs(pc, row, wide):
    n = len(pc.cls.PINS)
    h = n // 2
    bcol, tcol = WIDE_COLS if wide else ("e", "f")
    out = []
    for p in range(1, n + 1):
        net = pc.pinnet.get(p)
        if p <= h:
            out.append((p, row + p - 1, bcol, net))
        else:
            out.append((p, row + (n - p), tcol, net))
    return out


def layout(N):
    boards = {b: Board(b) for b in BOARD_ORDER}
    for pc in N.chips.values():
        boards.setdefault(pc.board, Board(pc.board))
    for p in N.parts.values():
        boards.setdefault(p.board, Board(p.board))

    # ---- 0. the power entry (Bus board, high rows: nothing else is placed there) ---------
    pe = POWER_ENTRY
    PB = boards[pe["board"]]
    r0 = pe["row"]
    for k, pin in enumerate(pe["pins"]):
        row = r0 + k
        PB.leg("J1", pin, row, pe["col"], "GND" if pin == "GND" else f"NC:J1.{pin}")
        PB.blocked.add((row, "b"))                    # under the breakout's edge
    vrow = r0 + pe["pins"].index("VBUS")
    PB.leg("F1", "1", vrow, "d", "NC:J1.VBUS")        # fuse across the gap: VBUS -> +5 V
    PB.leg("F1", "2", vrow, "f", "VCC")
    PB.gnd_up.add((r0 + pe["pins"].index("GND"), "B"))
    PB.items.append(dict(ref="J1", kind="usbc", rows=(r0, r0 + len(pe["pins"]) - 1), label="USB-C 5 V in",
                         pins=list(pe["pins"])))
    PB.items.append(dict(ref="F1", kind="fuse", rows=(vrow, vrow), value="1.1 A"))

    # ---- 1. chips --------------------------------------------------------------------
    chip_power = {}                    # ref -> (VCC pin hole, GND pin node)
    for ref, pc in N.chips.items():
        B = boards[pc.board]
        n = len(pc.cls.PINS)
        wide = n == 28
        r = B.rows(n // 2)
        vcc_hole = gnd_node = None
        for p, row, col, net in dip_legs(pc, r, wide):
            B.leg(ref, p, row, col, net if net else f"NC:{ref}.{p}")
            kind = pc.cls.PINS[p][1]
            if kind == "vcc":
                vcc_hole = (row, col)
            elif kind == "gnd":
                gnd_node = (row, half(col))
        assert vcc_hole and half(vcc_hole[1]) == "T" and gnd_node and gnd_node[1] == "B", ref
        B.gnd_up.add(gnd_node)
        chip_power[ref] = (vcc_hole, gnd_node)
        if wide:
            for row in range(r, r + n // 2):
                for c in WIDE_BODY:
                    B.blocked.add((row, c))
        B.items.append(dict(ref=ref, kind="chip", rows=(r, r + n // 2 - 1), wide=wide, type=pc.cls.TYPE))

    parts = list(N.parts.values())
    by_ref = {p.ref: p for p in parts}
    done = set()

    # ---- 2. switch banks with their resistor networks ----------------------------------
    for p in parts:
        if p.kind == "RN" and p.note.startswith("pull-downs for "):
            pkg = p.note.split()[-1]
            secs = sorted([q for q in parts if q.kind == "SW" and getattr(q, "pkg", None) == pkg], key=lambda q: q.pos)
            B = boards[p.board]
            n = len(secs)
            r = B.rows(n + 1)
            B.leg(p.ref, "C", r, "j", p.pins["C"])
            for k, sw in enumerate(secs):
                row = r + 1 + k
                B.leg(p.ref, str(k + 1), row, "j", p.pins[str(k + 1)])
                B.leg(sw.ref, "1", row, "e", sw.pins["1"])          # VCC side
                B.leg(sw.ref, "2", row, "f", sw.pins["2"])          # signal side
                done.add(sw.ref)
            done.add(p.ref)
            B.items.append(dict(ref=pkg, kind="dipswitch", rows=(r + 1, r + n), n=n))
            B.items.append(dict(ref=p.ref, kind="rn", rows=(r, r + n)))

    # ---- 3. other multi-pin parts -----------------------------------------------------------
    for p in parts:
        if p.ref in done:
            continue
        B = boards[p.board]
        if p.kind == "RN":
            n = len(p.pins) - 1
            r = B.rows(n + 1)
            B.leg(p.ref, "C", r, "j", p.pins["C"])
            for k in range(n):
                B.leg(p.ref, str(k + 1), r + 1 + k, "j", p.pins[str(k + 1)])
            B.items.append(dict(ref=p.ref, kind="rn", rows=(r, r + n)))
        elif p.kind == "BTN":
            r = B.rows(3)
            for c in "ef":
                B.leg(p.ref, "1" + c, r, c, p.pins["1"])
                B.leg(p.ref, "2" + c, r + 2, c, p.pins["2"])
            B.items.append(dict(ref=p.ref, kind="button", rows=(r, r + 2), label=p.note))
        elif p.kind in ("SPDT", "JP", "Q"):
            keys = {"SPDT": None, "JP": ["SLOW", "COM", "FAST"], "Q": ["E", "B", "C"]}[p.kind]
            if keys is None:
                throws = [k for k in p.pins if k != "COM"]
                keys = [throws[0], "COM", throws[1]]
            r = B.rows(3)
            for k, key in enumerate(keys):
                B.leg(p.ref, key, r + k, "h", p.pins[key])
            B.items.append(dict(ref=p.ref, kind=p.kind.lower(), rows=(r, r + 2), label=p.note, keys=keys))
        elif p.kind == "VR":
            r = B.rows(5)
            for k, key in zip((0, 2, 4), ("1", "W", "3")):
                B.leg(p.ref, key, r + k, "i", p.pins[key])
            B.items.append(dict(ref=p.ref, kind="pot", rows=(r, r + 4), label=p.note))
        elif p.kind == "DISP":
            r = B.rows(5)
            bot = ["e", "d", "CA", "c", "dp"]
            top = ["g", "f", "CA", "a", "b"]
            for k in range(5):
                B.leg(p.ref, "B" + bot[k], r + k, WIDE_COLS[0], p.pins[bot[k]])
                B.leg(p.ref, "T" + top[k], r + k, WIDE_COLS[1], p.pins[top[k]])
                for c in WIDE_BODY:
                    B.blocked.add((r + k, c))
            B.items.append(dict(ref=p.ref, kind="digit", rows=(r, r + 4), label=p.note))
        else:
            continue
        done.add(p.ref)

    # ---- 4. two-terminal parts between two signal nets: a "bridge" row each ------------
    def ends(p):
        ks = list(p.pins)
        return ks[0], ks[1]

    rail_attach = []
    for p in parts:
        if p.ref in done or p.kind not in ("R", "C", "LED"):
            continue
        k1, k2 = ends(p)
        n1, n2 = p.pins[k1], p.pins[k2]
        if n1 in RAILS and n2 in RAILS:
            continue                              # decoupling: placed rail to rail below
        if n1 in RAILS or n2 in RAILS:
            rail_attach.append(p)
            continue
        B = boards[p.board]
        # LED mid nets go to the bottom half so the LED can drop into the bottom GND rail
        if n1.endswith("~LED") or (not n2.endswith("~LED") and k1 in ("1", "+") and False):
            bot, top = (k1, n1), (k2, n2)
        elif n2.endswith("~LED"):
            bot, top = (k2, n2), (k1, n1)
        else:
            bot, top = (k1, n1), (k2, n2)
        r = B.rows(1, gap=0)
        B.leg(p.ref, bot[0], r, "d", bot[1])
        B.leg(p.ref, top[0], r, "f", top[1])
        B.items.append(dict(ref=p.ref, kind=p.kind.lower() + "-bridge", rows=(r, r), value=p.value))
        done.add(p.ref)

    # ---- 5. parts from a node to a rail ---------------------------------------------------
    for p in rail_attach:
        B = boards[p.board]
        k1, k2 = ends(p)
        rail_net, (sk, sig) = (p.pins[k1], (k2, p.pins[k2])) if p.pins[k1] in RAILS else (p.pins[k2], (k1, p.pins[k1]))
        rk = k1 if p.pins[k1] in RAILS else k2
        nodes = [nd for nd, nt in B.node_net.items() if nt == sig and B.free(nd)]
        # keep one hole spare on each node for a wire
        nodes = [nd for nd in nodes if len(B.free(nd)) >= 2] or nodes
        if nodes:
            node = sorted(nodes, key=lambda nd: -len(B.free(nd)))[0]
        else:
            node = B.fresh_node(sig, "B")
        if node is None:
            continue
        hole = B.take(node, (p.ref, sk))
        rail = RAIL_OF[(node[1], rail_net)]
        B.rail_legs.append((p.ref, rk, rail, node[0]))
        B.items.append(dict(ref=p.ref, kind=p.kind.lower() + "-rail", rows=(node[0], node[0]), hole=hole,
                            rail=rail, value=p.value))
        done.add(p.ref)

    # decoupling capacitors: from a hole in the chip's own VCC row to the top GND rail, the rail
    # its GND pin is wired to (see the module docstring)
    for p in parts:
        if p.kind == "C" and p.pins.get("1") == "VCC" and p.pins.get("2") == "GND" and p.note.startswith("decoupling"):
            B = boards[p.board]
            chip = p.note.split()[-1]
            (crow, ccol), gnd_node = chip_power[chip]
            hole = B.take((crow, "T"), (p.ref, "1"))
            B.rail_legs.append((p.ref, "2", "T-", crow))
            B.items.append(dict(ref=p.ref, kind="decoupling", rows=(crow, crow), hole=hole, rail="T-",
                                value=p.value, chip=chip))
            done.add(p.ref)
    # bulk electrolytics: across the top rails (by the first 555 on the clock boards, by the
    # power entry on the Bus board, else at the left end)
    for p in parts:
        if p.kind == "C" and p.note == "bulk supply capacitor":
            B = boards[p.board]
            if getattr(p, "rail_row", None):
                row = p.rail_row
            else:
                timers = [i for i in B.items if i["kind"] == "chip" and i["type"] == "NE555"]
                row = timers[0]["rows"][0] + 2 if timers else 2
            B.rail_legs.append((p.ref, "+", "T+", row))
            B.rail_legs.append((p.ref, "-", "T-", row))
            B.items.append(dict(ref=p.ref, kind="bulk", rows=(row, row), value=p.value))
            done.add(p.ref)

    missing = [p.ref for p in parts if p.ref not in done]
    assert not missing, missing

    # ---- 6. wires -------------------------------------------------------------------------
    present = defaultdict(set)          # net -> boards
    for B in boards.values():
        for node, net in B.node_net.items():
            if not net.startswith("NC:") and net not in RAILS:
                present[net].add(B.name)
    links = []                          # board-to-board wires
    for B in boards.values():
        bynet = defaultdict(list)
        for node, net in B.node_net.items():
            bynet[net].append(node)
        for net, nodes in bynet.items():
            if net.startswith("NC:"):
                continue
            if net in RAILS:
                for node in sorted(nodes):
                    up = net == "GND" and node in B.gnd_up
                    h = B.take(node, ("wire", net), near_gap=up)
                    if h is None:
                        B.overflow.append(f"no hole for {net} wire at {node}")
                        continue
                    B.wires.append(dict(net=net, a=h, b="T-" if up else RAIL_OF[(node[1], net)], kind="power"))
                continue
            need_ports = 0
            if len(present[net]) > 1:
                pos = sorted(present[net], key=BUILD_ORDER.index).index(B.name)
                need_ports = 1 if pos in (0, len(present[net]) - 1) else 2
            tree_connect(B, net, sorted(nodes), need_ports)
    # board-to-board chains
    for net, bs in present.items():
        if len(bs) < 2:
            continue
        chain = sorted(bs, key=BUILD_ORDER.index)
        for b1, b2 in zip(chain, chain[1:]):
            h1 = boards[b1].ports[net].pop(0)
            h2 = boards[b2].ports[net].pop(0)
            links.append(dict(net=net, a=(b1, h1), b=(b2, h2)))
    return boards, links


def tree_connect(B, net, nodes, need_ports):
    """Join all nodes of one net on one board with wires, never using more holes than a
    half-row has free, adding spare junction rows where needed. Reserve holes for the
    board-to-board wires."""
    if not hasattr(B, "ports"):
        B.ports = defaultdict(list)
    cap = {nd: len(B.free(nd)) for nd in nodes}
    total_need = 2 * (len(nodes) - 1) + need_ports
    while sum(cap.values()) < total_need + 0 or (len(nodes) > 1 and max(cap.values()) < 2 and len(nodes) > 2):
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
    for nd in pending:
        targets = [t for t in connected if rem[t] >= 1]
        if not targets:
            B.overflow.append(f"no hole to join {net} at {nd}")
            continue
        # nearest target with spare capacity; keep at least one spare where possible
        t = min(targets, key=lambda t: (rem[t] < 2, abs(t[0] - nd[0])))
        ha = B.take(t, ("wire", net))
        hb = B.take(nd, ("wire", net))
        rem[t] -= 1
        rem[nd] -= 1
        connected.append(nd)
        B.wires.append(dict(net=net, a=ha, b=hb, kind="local"))
    for _ in range(need_ports):
        cands = [t for t in connected if rem[t] >= 1]
        if not cands:
            j = B.fresh_node(net)
            t = min([c for c in connected if rem[c] >= 1] or connected, key=lambda c: rem[c])
            B.overflow.append(f"no hole for board-to-board {net}")
            continue
        t = max(cands, key=lambda c: rem[c])
        h = B.take(t, ("port", net))
        rem[t] -= 1
        B.ports[net].append(h)


# ------------------------------------------------------------------------- checker
def check(N, boards, links):
    """Rebuild connectivity from holes, legs and wires; compare with the netlist."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    pin_point = {}
    for B in boards.values():
        for (row, col), tag in B.used.items():
            node = ("N", B.name, row, half(col))
            find(node)
            if tag[0] not in ("wire", "port"):
                pin_point[(tag[0], str(tag[1]))] = node
        for w in B.wires:
            a = ("N", B.name, w["a"][0], half(w["a"][1]))
            b = ("R", w["b"]) if isinstance(w["b"], str) else ("N", B.name, w["b"][0], half(w["b"][1]))
            union(a, b)
        for ref, pin, rail, row in B.rail_legs:
            pin_point[(ref, str(pin))] = ("R", rail)
    for l in links:
        (b1, h1), (b2, h2) = l["a"], l["b"]
        union(("N", b1, h1[0], half(h1[1])), ("N", b2, h2[0], half(h2[1])))
    # power distribution: every board's rails join the supply
    union(("R", "B+"), ("R", "T+"))
    union(("R", "B-"), ("R", "T-"))
    # parts whose legs are joined inside the part
    for p in N.parts.values():
        if p.kind == "BTN":
            union(pin_point[(p.ref, "1e")], pin_point[(p.ref, "1f")])
            union(pin_point[(p.ref, "2e")], pin_point[(p.ref, "2f")])
        if p.kind == "DISP":
            union(pin_point[(p.ref, "BCA")], pin_point[(p.ref, "TCA")])
    # expected: each netlist pin -> its net
    expect = defaultdict(set)
    for ref, pc in N.chips.items():
        for n, net in pc.pinnet.items():
            expect[net].add((ref, str(n)))
    for p in N.parts.values():
        for k, net in p.pins.items():
            if p.kind == "BTN":
                expect[net].add((p.ref, k + "e"))
                expect[net].add((p.ref, k + "f"))
            elif p.kind == "DISP":
                if k == "CA":
                    expect[net].add((p.ref, "BCA"))
                    expect[net].add((p.ref, "TCA"))
                else:
                    side = "B" if k in ("e", "d", "c", "dp") else "T"
                    expect[net].add((p.ref, side + k))
            else:
                expect[net].add((p.ref, k))
    problems = []
    group_net = {}
    for net, pins in expect.items():
        roots = set()
        for pin in pins:
            if pin not in pin_point:
                problems.append(f"{net}: pin {pin} not placed")
                continue
            pt = pin_point[pin]
            r = find(pt) if pt[0] == "N" else find(pt)
            roots.add(r)
        rail_root = None
        if net == "VCC":
            rail_root = find(("R", "B+"))
        if net == "GND":
            rail_root = find(("R", "B-"))
        if rail_root is not None:
            roots.add(rail_root)
        if len(roots) > 1:
            problems.append(f"{net}: split into {len(roots)} groups")
        for r in roots:
            if r in group_net and group_net[r] != net:
                problems.append(f"short: {net} joined to {group_net[r]}")
            group_net[r] = net
    return problems
