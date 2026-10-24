"""DIP switch package with n sections. Section k joins pin k and pin 2n+1-k when on.
Types DIPSW1 ... DIPSW12. Set one section with id "S3.4", or all with an int
(bit k-1 -> section k; with props msb_first, bit n-k -> section k, so section 1, the
leftmost switch, is the highest bit, as on PC-2's front panel)."""
from .base import Part, part


class DipSwitch(Part):
    CATEGORY = "switch"
    FOOTPRINT = {"kind": "dip", "width": 3}
    N = 8

    def __init__(self, ref="S?", **props):
        super().__init__(ref, **props)
        init = self.props.get("closed", 0)
        if isinstance(init, list):
            self.state = [bool(x) for x in init] + [False] * (self.N - len(init))
        else:
            self.state = self._from_int(int(init))

    def _from_int(self, v):
        if self.props.get("msb_first"):
            return [bool((v >> (self.N - k)) & 1) for k in range(1, self.N + 1)]
        return [bool((v >> k) & 1) for k in range(self.N)]

    def value(self):
        """The bank as a number (bit order as set())."""
        if self.props.get("msb_first"):
            return sum(1 << (self.N - k) for k in range(1, self.N + 1) if self.state[k - 1])
        return sum(1 << k for k in range(self.N) if self.state[k])

    def sections(self):
        return [f"{self.ref}.{k}" for k in range(1, self.N + 1)]

    def links(self):
        n = self.N
        return [(k, 2 * n + 1 - k, "strong", 0.0, f"{self.ref}.{k}")
                for k in range(1, n + 1) if self.state[k - 1]]

    def set(self, value, section=None):
        if section is None:
            if isinstance(value, (list, tuple)):
                for k, v in enumerate(value[:self.N]):
                    self.state[k] = bool(v)
            else:
                self.state = self._from_int(int(value))
        else:
            k = int(section)
            if not 1 <= k <= self.N:
                raise ValueError(f"{self.ref} has sections 1-{self.N}")
            self.state[k - 1] = bool(value)

    def get(self):
        return [1 if s else 0 for s in self.state]


def _make(n):
    pins = {}
    for k in range(1, n + 1):
        pins[k] = (f"{k}A", "pas")
        pins[2 * n + 1 - k] = (f"{k}B", "pas")
    cls = type(f"DipSwitch{n}", (DipSwitch,), {
        "TYPE": f"DIPSW{n}", "N": n, "DESC": f"DIP switch, {n} positions",
        "PINS": dict(sorted(pins.items()))})
    return part(cls)


for _n in range(1, 13):
    _make(_n)
