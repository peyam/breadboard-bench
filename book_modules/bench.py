"""bench: the book's name for the PC-2 bench API (``from bench import Bench``).

The same module as ``bbench.compat.pc2sim`` (Bench, Netlist, Sim, build, CONTROL_LINES ...),
so the book's boxes run in Breadboard Bench's Code tab and on the desktop once bbench is
installed."""
import sys

from bbench.compat import pc2sim as _impl

sys.modules[__name__] = _impl
