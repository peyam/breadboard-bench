"""Breadboard Bench: a digital-logic simulator for learning how computers work.

    import bbench
    p = bbench.Project.load(text_or_dict)     # or bbench.projects.pc2()
    p.check()                                 # [{severity, message, where}, ...]
    sim = p.simulator("zero")                 # or "timed"
"""
__version__ = "1.0.0"

from .core import Netlist, ZeroDelaySim, TimedSim  # noqa: F401,E402
from .project import Project, library  # noqa: F401,E402
from . import projects  # noqa: F401,E402
