"""Bussed resistor network (SIP): pin 1 is the common pin, pins 2..n+1 each have a
resistor to it. Types RN4 ... RN10 (number of resistors); "RN" takes props n."""
from .base import Part, part


class RNetwork(Part):
    DESC = "Bussed resistor network (SIP)"
    FOOTPRINT = {"kind": "sip", "pitch": 1}
    N = 8
    DEFAULTS = {"value": "10k"}

    def links(self):
        r = self.ohms()
        return [(1, k, "weak", r, self.ref) for k in range(2, self.N + 2)]


def _make(n, type_name):
    cls = type(f"RNetwork{n}", (RNetwork,), {
        "TYPE": type_name, "N": n, "DESC": f"Bussed resistor network, {n} resistors (SIP-{n + 1})",
        "PINS": {1: ("COM", "pas"), **{k + 1: (f"R{k}", "pas") for k in range(1, n + 1)}}})
    return part(cls)


for _n in range(2, 11):
    _make(_n, f"RN{_n}")
RN = _make(8, "RN")
