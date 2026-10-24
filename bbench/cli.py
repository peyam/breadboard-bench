"""Command line: python -m bbench <command> ...

  run PROJECT [--mode zero|timed] [--until-halt] [--cycles N] [--ns T] [--limit N]
              [--set ID=VALUE ...] [--press ID ...] [--program NAME] [--vcd FILE] [--probes A,B]
  check PROJECT          problems as JSON (exit status 1 if there is an error)
  library                every chip and part type as JSON
  export NAME FILE       write a built-in project (pc2, pc2:<module>, an example id)
  list                   the built-in projects

PROJECT is a .bbproj file or a built-in id (pc2, pc2:ALU, xor-from-nand, ...).
--program NAME (PC-2 only) enters a book program through the front panel first.
"""
import argparse
import json
import os
import sys

from .project import Project, library
from . import projects


def _project(src):
    if os.path.exists(src):
        return Project.load(src)
    return projects.get(src)


def _value(v):
    if v.lower() in ("true", "on", "closed"):
        return True
    if v.lower() in ("false", "off", "open"):
        return False
    try:
        return int(v, 0)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def cmd_run(a):
    p = _project(a.project)
    summary = {"project": p.name, "mode": a.mode}
    if a.program:
        if p.name != "PC-2":
            raise SystemExit("--program needs the PC-2 project")
        from .projects import Panel
        from .projects.pc2_programs import PROGRAMS
        panel = Panel(sim=p.simulator(a.mode))
        panel.load(PROGRAMS[a.program.upper()]["mem"])
        sim = panel.sim
    else:
        panel = None
        sim = p.simulator(a.mode)
    for s in a.set or []:
        k, v = s.split("=", 1)
        sim.set(k, _value(v))
    for b in a.press or []:
        sim.press(b)
    probes = a.probes.split(",") if a.probes else (p.data.get("probes") or None)
    sim.record(probes)
    if a.until_halt:
        if panel is not None:
            ok = panel.run(a.limit)
            summary["halted"] = ok
            summary["cycles"] = panel.rises
            summary["shown"] = panel.shown
        else:
            r = sim.run("halt", limit=a.limit)
            summary["halted"] = r["done"]
            summary["cycles"] = r["cycles"]
    if a.cycles:
        sim.step(a.cycles)
    if a.ns:
        if a.mode != "timed":
            raise SystemExit("--ns needs --mode timed")
        sim.run_ns(a.ns)
    st = sim.state()
    summary["t_ns"] = st["t_ns"]
    summary["leds_lit"] = sorted(k for k, v in st["leds"].items() if v)
    summary["digits"] = st["digits"]
    if panel is not None:
        summary["display"] = panel.display()
    summary["problems"] = st["errors"]
    if a.vcd:
        sim.write_vcd(a.vcd, probes)
        summary["vcd"] = a.vcd
    print(json.dumps(summary, indent=1))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bbench", description="Breadboard Bench engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("project")
    r.add_argument("--mode", default="zero", choices=["zero", "timed"])
    r.add_argument("--until-halt", action="store_true")
    r.add_argument("--cycles", type=int, default=0)
    r.add_argument("--ns", type=float, default=0)
    r.add_argument("--limit", type=int, default=20000)
    r.add_argument("--set", action="append")
    r.add_argument("--press", action="append")
    r.add_argument("--program")
    r.add_argument("--vcd")
    r.add_argument("--probes")
    c = sub.add_parser("check")
    c.add_argument("project")
    sub.add_parser("library")
    sub.add_parser("list")
    e = sub.add_parser("export")
    e.add_argument("name")
    e.add_argument("file")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "check":
        pr = _project(a.project).check()
        print(json.dumps(pr, indent=1))
        return 1 if any(x["severity"] == "error" for x in pr) else 0
    if a.cmd == "library":
        print(json.dumps(library(), indent=1))
        return 0
    if a.cmd == "list":
        print(json.dumps(projects.catalogue(), indent=1))
        return 0
    if a.cmd == "export":
        projects.get(a.name).save(a.file)
        print(a.file)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
