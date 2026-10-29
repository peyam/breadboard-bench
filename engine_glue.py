# Glue between the web app and the bbench engine (runs inside Pyodide in the worker).
# Every call takes and returns JSON text, so only plain data crosses the boundary (DESIGN §5).
import ast
import contextlib
import io
import json
import traceback

_P = None        # the open bbench.Project
_S = None        # its simulator
_NS = {"__name__": "__main__"}   # the Code tab's namespace: a script's `if __name__ == "__main__":` runs


def _bb_init():
    import bbench
    _NS["__name__"] = "__main__"
    _NS["bbench"] = bbench
    return getattr(bbench, "__version__", "")


def _plain(x):
    """Make engine results JSON-safe (tuples, sets, dataclasses, objects with to_dict)."""
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_plain(v) for v in x]
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    for m in ("to_dict", "as_dict", "dict"):
        if hasattr(x, m):
            try:
                return _plain(getattr(x, m)())
            except TypeError:
                pass
    if hasattr(x, "__dict__"):
        return _plain({k: v for k, v in vars(x).items() if not k.startswith("_")})
    return str(x)


def _project_dict(p):
    for m in ("to_dict", "as_dict", "dump", "to_json", "dumps", "save"):
        f = getattr(p, m, None)
        if f is None:
            continue
        try:
            d = f()
        except TypeError:
            continue
        if isinstance(d, str):
            d = json.loads(d)
        if isinstance(d, dict):
            return d
    raise RuntimeError("the engine's Project cannot be turned into JSON")


def _need_sim():
    if _S is None:
        raise RuntimeError("no simulator yet")
    return _S


def loadProject(js):
    global _P, _S
    import bbench
    _P = bbench.Project.load(js)
    _S = None
    _NS["project"] = _P
    return {"name": getattr(_P, "name", None)}


def check():
    return _P.check() if _P is not None else []


LIVE_KEEP = 20000   # changes kept per net while the live simulation runs (the analyser's window)


def newSim(mode="zero"):
    global _S
    _S = _P.simulator(mode=mode)
    _S.history.keep = LIVE_KEEP
    _NS["sim"] = _S
    return {"mode": mode}


def timedRun(ns, nets, fromCurrent=True):
    """A timed run for the analyser in a simulator of its own, so the live (zero-delay)
    simulation carries on untouched. fromCurrent: start from the live simulation's state
    (registers, RAM, the program, switches); else from power-up with the live switches."""
    start = _S if (fromCurrent and _S is not None) else None
    T = _P.simulator(mode="timed", start=start)
    if start is None and _S is not None:
        for pid, v in _S.state().get("switches", {}).items():
            try:
                T.drive(pid, v)
            except Exception:
                pass
        T.update()
        T.record()
    _NS["timed"] = T
    T.run_ns(ns)
    tr = T.trace(nets)
    tr["t_end"] = ns
    st = T.state()
    return {"trace": tr, "errors": st.get("errors", []), "cycles": T.cycles, "from": "current" if start else "power-up"}


def set_(id, value):  # "set" in the API (DESIGN §5)
    _need_sim().set(id, value)
    return None


def step(n=1):
    s = _need_sim()
    try:
        s.step(n)
    except TypeError:
        for _ in range(int(n)):
            s.step()
    return None


def runUntil(cond="halt", limit=20000):
    return _need_sim().run(until=cond, limit=limit)


def runNs(ns, maxEdges=None):
    s = _need_sim()
    if maxEdges and s.mode == "zero":
        return s.run_ns(ns, max_edges=int(maxEdges))
    return s.run_ns(ns)


def clocks():
    """The live simulation's clock sources: [{part, period_ns, duty, role}] (main clock first)."""
    s = _need_sim()
    cl = s.clocks() if hasattr(s, "clocks") else [d for d in s.stimuli if d.get("period_ns")]
    mc = s.main_clock()
    out = [{k: d.get(k) for k in ("part", "period_ns", "duty", "role")} for d in cl]
    out.sort(key=lambda d: 0 if mc and d["part"] == mc["part"] else 1)
    return out


def state():
    s = _need_sim()
    st = s.state()
    if isinstance(st, dict):
        if "cycles" not in st and hasattr(s, "cycles"):
            st["cycles"] = s.cycles
        nets = st.get("nets") or {}
        if "halted" not in st and "HLT_n" in nets:
            st["halted"] = nets["HLT_n"] == 0
    return st


def trace(nets):
    return _need_sim().trace(nets)


def toVcd(nets):
    s = _need_sim()
    f = getattr(s, "to_vcd", None)
    if f is None:
        return None
    try:
        return f(nets)
    except TypeError:
        return f()


def library():
    import bbench
    return bbench.library()


def examples():
    import bbench
    pr = getattr(bbench, "projects", None)
    if pr is not None and hasattr(pr, "catalogue"):
        out = []
        for e in pr.catalogue():
            kind = e.get("kind", "example")
            group = {"computer": "PC-2", "module": "PC-2 modules"}.get(kind, "Examples from the book")
            out.append({"id": e["id"], "name": e.get("name", e["id"]), "group": group, "kind": kind, "desc": e.get("notes", "")})
        return out
    return [{"id": "pc2", "name": "PC-2: the whole computer", "group": "PC-2", "kind": "computer"}]


def example(id):
    import bbench
    import importlib
    pr = bbench.projects
    if id == "pc2":
        # bbench.projects.pc2 can be shadowed by the submodule of the same name once imported
        try:
            return _project_dict(importlib.import_module("bbench.projects.pc2").pc2())
        except (ImportError, AttributeError):
            pass
    if id.startswith("pc2:"):
        try:
            return _project_dict(importlib.import_module("bbench.projects.pc2").module_project(id[4:]))
        except (ImportError, AttributeError):
            pass
    if hasattr(pr, "get"):
        return _project_dict(pr.get(id))
    if id == "pc2":
        return _project_dict(pr.pc2())
    if id.startswith("pc2:") and hasattr(pr, "module"):
        return _project_dict(pr.module(id[4:]))
    return _project_dict(pr.example(id))


def _bb_call(fn, args_json):
    try:
        f = globals()["set_" if fn == "set" else fn]
        args = json.loads(args_json)
        r = f(*args)
        return json.dumps({"result": _plain(r)})
    except Exception as e:  # report the engine's own words to the app
        tb = traceback.format_exc(limit=3)
        return json.dumps({"error": f"{type(e).__name__}: {e}", "trace": tb})


def _bb_console(code):
    """Run code like a Python prompt: print the value of a final expression."""
    out = io.StringIO()
    ok = True
    _NS.setdefault("project", _P)
    _NS.setdefault("sim", _S)
    try:
        tree = ast.parse(code, "<code>", "exec")
        last = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last = ast.Expression(tree.body.pop().value)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(compile(tree, "<code>", "exec"), _NS)
            if last is not None:
                v = eval(compile(last, "<code>", "eval"), _NS)
                if v is not None:
                    print(repr(v))
    except Exception:
        ok = False
        lines = traceback.format_exc().splitlines()
        # hide the glue's own frames
        keep = [l for l in lines if "engine_glue" not in l and "_bb_console" not in l]
        out.write("\n".join(keep[-8:]) + "\n")
    return json.dumps({"ok": ok, "out": out.getvalue()})
