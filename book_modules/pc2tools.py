"""pc2tools: the book's helpers for PC-2 programs (``from pc2tools import trace, NAMES``).

The same module as ``bbench.compat.pc2tools`` (a port of tools/pc2kit/pc2tools.py)."""
import sys

from bbench.compat import pc2tools as _impl

sys.modules[__name__] = _impl
