"""The chip library: one module per family. Importing this package imports every
module in it, so each @register'd chip is in REGISTRY."""
import importlib
import pkgutil

from .base import (Chip, FloatingInput, InCircuitWrite, REGISTRY, DUPLICATES, Z, X, bit, soft, pins,  # noqa: F401
                   register, variant, get, types)

for _m in sorted(m.name for m in pkgutil.iter_modules(__path__)):
    if _m != "base" and not _m.startswith("_"):
        importlib.import_module(f"{__name__}.{_m}")
