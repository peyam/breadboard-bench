"""Built-in projects: the whole PC-2, each of its modules, and small examples.

    bbench.projects.pc2()                 # Project
    bbench.projects.module("A register")  # one PC-2 module on its own
    bbench.projects.example("xor-from-nand")
    bbench.projects.catalogue()           # [{id, name, notes}]
"""

# import the submodule first, then bind the name pc2 to the function (DESIGN 2.6)
from .pc2 import pc2 as _pc2, module_project as _module_project, Panel, MODULES  # noqa: E402,F401


def pc2():
    """The whole PC-2 as a Project."""
    return _pc2()


def module(name):
    """One PC-2 module as a standalone Project."""
    return _module_project(name)


def example(name):
    from .examples import EXAMPLES
    return EXAMPLES[name]()


def catalogue():
    from .examples import EXAMPLES, TITLES
    out = [{"id": "pc2", "name": "PC-2 (the whole computer)", "kind": "computer"}]
    out += [{"id": f"pc2:{m}", "name": f"PC-2 {m}", "kind": "module"} for m in MODULES]
    out += [{"id": k, "name": TITLES[k], "kind": "example"} for k in EXAMPLES]
    return out


def get(pid):
    """Any built-in project by catalogue id."""
    if pid == "pc2":
        return pc2()
    if pid.startswith("pc2:"):
        return module(pid[4:])
    return example(pid)
