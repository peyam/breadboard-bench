"""Passives and I/O parts. Importing this package registers every part type in PARTS."""
from .base import PARTS, Part, part  # noqa: F401
from . import (resistor, rnetwork, capacitor, pot, led, sevenseg, switch, button,  # noqa: F401
               spdt, dipswitch, transistor, clock, power, probe)
