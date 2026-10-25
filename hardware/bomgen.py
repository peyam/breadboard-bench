"""Parts list generated from the netlist (so it can never disagree with the circuits)."""
from collections import Counter, defaultdict
from pc2_netlist import build

TTL_SOURCES = ("AT28C256", "AS6C62256", "NE555")


def family(N):
    """74HCT wherever an input is driven by a memory or 555 output; else 74HC is acceptable."""
    src = {}
    for ref, pc in N.chips.items():
        if pc.cls.TYPE in TTL_SOURCES:
            for n, net in pc.pinnet.items():
                if pc.cls.PINS[n][1] in ("out", "tri", "io"):
                    src[net] = ref
    fam = {}
    for ref, pc in N.chips.items():
        if not pc.cls.TYPE.startswith("74"):
            continue
        need = False
        for n, net in pc.pinnet.items():
            name, kind = pc.cls.PINS[n]
            if net not in src:
                continue
            if kind in ("in", "clk"):
                need = True
            if kind == "io":                      # 245: only the side it reads from
                dir_net = pc.pinnet[1]
                side_in = "A" if dir_net == "VCC" else ("B" if dir_net == "GND" else "AB")
                if name[0] in side_in:
                    need = True
        fam[ref] = "HCT" if need else "HC"
    return fam


def bom(N=None):
    N = N or build()
    fam = family(N)
    chips = Counter()
    where = defaultdict(list)
    for ref, pc in N.chips.items():
        t = pc.cls.TYPE
        key = t
        chips[key] += 1
        where[key].append(f"{ref} ({pc.module})")
    parts = Counter()
    pwhere = defaultdict(list)
    for p in N.parts.values():
        if p.kind == "LED":
            key = ("LED 3 mm", p.value)
        elif p.kind in ("R", "C", "VR"):
            key = (p.kind, p.value)
        elif p.kind == "SW":
            key = ("DIP switch position", "")
        elif p.kind in ("Q", "DISP"):
            key = (p.kind, p.value)
        else:
            key = (p.kind, p.note)
        parts[key] += 1
        pwhere[key].append(p.module)
    return chips, where, parts, pwhere, fam


if __name__ == "__main__":
    chips, where, parts, pwhere, fam = bom()
    tot = 0
    for k, n in sorted(chips.items()):
        tot += n
        print(f"{n:>3}  {k:<10} " + ", ".join(where[k]))
    print("chips", tot)
    for k, n in sorted(parts.items(), key=str):
        print(f"{n:>3}  {k}  {sorted(set(pwhere[k]))}")
    print(Counter(fam.values()))
