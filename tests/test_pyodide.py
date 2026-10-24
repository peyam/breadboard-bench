"""The engine is pure Python and imports with the standard library only."""
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def test_import_with_standard_library_only():
    code = ("import sys; sys.path.insert(0, %r); import bbench; bbench.projects.pc2().simulator('zero').step(); "
            "bad = [m for m in sys.modules if m.split('.')[0] not in sys.stdlib_module_names "
            "and m.split('.')[0] not in ('bbench', '__main__')]; print(bad); sys.exit(1 if bad else 0)") % ROOT
    r = subprocess.run([sys.executable, "-S", "-I", "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_no_compiled_files_or_numpy():
    for dp, dn, fn in os.walk(os.path.join(ROOT, "bbench")):
        for f in fn:
            assert not f.endswith((".so", ".pyd", ".c")), f
            if f.endswith(".py"):
                src = open(os.path.join(dp, f), encoding="utf-8").read()
                assert "import numpy" not in src and "from numpy" not in src, f
