"""Write docs/chips.md: the chip reference table, generated from the chip registry.

Run from the repository root:  python docs/make_chips_md.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from bbench.chips import REGISTRY  # noqa: E402

FAMILY_ORDER = {"HC": 0, "HCT": 1, "LS": 2, "CMOS": 3, "memory": 4, "timer": 5}


def sort_key(t):
    cls = REGISTRY[t]
    digits = "".join(c for c in t if c.isdigit())
    core = t
    for p in ("74HCT", "74HC", "74LS", "74"):
        if t.startswith(p):
            core = t[len(p):]
            break
    num = int("".join(c for c in core if c.isdigit()) or 0) if core[:1].isdigit() else 10 ** 6 + int(digits or 0)
    return (num, FAMILY_ORDER.get(cls.FAMILY, 9), t)


def esc(s):
    return str(s).replace("|", "\\|")


def build():
    lines = [
        "# Chip reference",
        "",
        "Every chip in the Breadboard Bench library. This file is generated from the chip",
        "registry by `docs/make_chips_md.py`; do not edit it by hand.",
        "",
        "Timing figures in the library are worst-case values at 4.5 V and 25 °C (LS parts: 5 V,",
        "25 °C) from the datasheet linked in each row.",
        "",
        f"{len(REGISTRY)} chips.",
        "",
        "VIH is the input threshold for a 1 (HC 3.15 V, HCT and LS 2.0 V at 4.5 V; memories as their",
        "datasheets give); — where the inputs are not logic inputs (the 555).",
        "",
        "| Type | Description | Family | VIH | Package | Datasheet |",
        "|---|---|---|---|---|---|",
    ]
    for t in sorted(REGISTRY, key=sort_key):
        c = REGISTRY[t]
        url = c.DATASHEET
        link = f"[{url.rsplit('/', 1)[-1] or url}]({url})" if url else "—"
        vih = c.levels()["VIH"]
        vih = f"{vih:g} V" if vih is not None else "—"
        lines.append(f"| {esc(t)} | {esc(c.DESC)} | {esc(c.FAMILY)} | {vih} | {c.package()} | {link} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    out = os.path.join(HERE, "chips.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build())
    print(f"wrote {out} ({len(REGISTRY)} chips)")
