"""Component values and simple DC analysis of the passives (for 555 timing)."""
import re

PREFIX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0, "k": 1e3, "K": 1e3,
          "M": 1e6, "G": 1e9, "R": 1.0}
_VAL = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([pnuµmkKMGR]?)([0-9]*)")


def parse_value(v):
    """'2.2k' -> 2200.0, '4k7' -> 4700.0, '100nF' -> 1e-07, '1M lin' -> 1e6, 470 -> 470.0.
    Returns None when there is no number."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = _VAL.match(str(v))
    if not m:
        return None
    num, pre, frac = m.groups()
    if frac and pre:
        num = f"{num}.{frac}"
    return float(num) * PREFIX[pre]


class Network:
    """Resistive network built from the parts' conducting links (closed switches merge nets)."""

    def __init__(self, edges, shorts):
        self.parent = {}
        for a, b in shorts:
            self._union(a, b)
        self.edges = []
        for a, b, ohms in edges:
            if ohms is None:
                continue
            if ohms <= 1e-3:
                self._union(a, b)
            else:
                self.edges.append((a, b, ohms))

    def _find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def _union(self, a, b):
        self.parent[self._find(a)] = self._find(b)

    def same(self, a, b):
        return self._find(a) == self._find(b)

    def resistance(self, a, b):
        """Effective resistance between nets a and b, or None if not connected."""
        A, B = self._find(a), self._find(b)
        if A == B:
            return 0.0
        adj = {}
        for x, y, r in self.edges:
            X, Y = self._find(x), self._find(y)
            if X == Y:
                continue
            adj.setdefault(X, []).append((Y, r))
            adj.setdefault(Y, []).append((X, r))
        # component of A
        seen, stack = {A}, [A]
        while stack:
            n = stack.pop()
            for m, _ in adj.get(n, ()):
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        if B not in seen:
            return None
        nodes = [n for n in seen if n != B]
        idx = {n: i for i, n in enumerate(nodes)}
        k = len(nodes)
        M = [[0.0] * (k + 1) for _ in range(k)]
        for n in nodes:
            i = idx[n]
            for m, r in adj.get(n, ()):
                g = 1.0 / r
                M[i][i] += g
                if m != B:
                    M[i][idx[m]] -= g
        M[idx[A]][k] = 1.0                     # inject 1 A at A, B at 0 V
        for c in range(k):                     # Gaussian elimination
            p = max(range(c, k), key=lambda r: abs(M[r][c]))
            if abs(M[p][c]) < 1e-18:
                return None
            M[c], M[p] = M[p], M[c]
            for r in range(k):
                if r != c and M[r][c]:
                    f = M[r][c] / M[c][c]
                    for j in range(c, k + 1):
                        M[r][j] -= f * M[c][j]
        return M[idx[A]][k] / M[idx[A]][idx[A]]
