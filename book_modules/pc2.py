"""pc2: the book's PC-2 microcode emulator (``from pc2 import PC2, asm``).

The same module as ``bbench.projects.pc2_emulator`` (a copy of tools/pc2kit/pc2.py), so
``sys.path.insert(0, "tools/pc2kit"); import pc2`` works in Breadboard Bench's Code tab
too (where the companion folder is not there)."""
import sys

from bbench.projects import pc2_emulator as _impl

sys.modules[__name__] = _impl
