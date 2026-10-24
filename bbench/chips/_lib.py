"""Shared helpers for the extended chip library (lib_*.py modules).

Datasheet sources
-----------------
Every figure in the lib_* modules was read from the manufacturer's datasheet named
in the chip's DATASHEET attribute: pin numbers (DIP package), the function table and
worst-case timing at VCC = 4.5 V, 25 degC (CL = 50 pF). TI documents are used first;
where TI has no matching sheet, or its text could not be read, the Nexperia sheet for
the same part number is used (Nexperia lists the SO package; its pin numbers are the
same as the DIP package of the same type).

Delay conventions
-----------------
* tpd is the larger of tPLH and tPHL.
* An output-enable path (OE -> Y) uses the larger of the enable time (ten) and the
  disable time (tdis).
* SETUP and HOLD are the datasheet minimums at 25 degC (the worst case a design must meet).
"""

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"
NXP = "https://assets.nexperia.com/documents/data-sheet/{}.pdf"


def word(bits):
    """[b0, b1, ...] -> integer (b0 is the least significant bit)."""
    return sum(b << i for i, b in enumerate(bits))


def bits(value, n):
    """integer -> [b0, b1, ... b(n-1)]."""
    return [(value >> i) & 1 for i in range(n)]
