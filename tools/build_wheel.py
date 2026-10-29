"""Build web/py/bbench-<version>-py3-none-any.whl with the standard library only
(a wheel is a zip file with a .dist-info folder), and point web/py/index.json at it.

    python tools/build_wheel.py [out_dir]

The web app fetches the wheel named in web/py/index.json and unzips it into Pyodide's
site-packages (web/engine_worker.js); `pip install web/py/bbench-*.whl` works too.
"""
import base64
import hashlib
import json
import os
import re
import sys
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def version():
    src = open(os.path.join(ROOT, "bbench", "__init__.py"), encoding="utf-8").read()
    return re.search(r'__version__ = "([^"]+)"', src).group(1)


def _hash(data):
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def build(out_dir):
    v = version()
    name = f"bbench-{v}-py3-none-any.whl"
    di = f"bbench-{v}.dist-info"
    files = []
    for dp, dn, fn in os.walk(os.path.join(ROOT, "bbench")):
        dn[:] = sorted(d for d in dn if d != "__pycache__")
        for f in sorted(fn):
            if f.endswith(".py"):
                full = os.path.join(dp, f)
                files.append((os.path.relpath(full, ROOT).replace(os.sep, "/"), open(full, "rb").read()))
    # the book's module names (from bench import Bench; import pc2, pc2tools), at the top level
    # and pc2plus (Chapter 13) and pc2_custom (Chapter 12's finished copy)
    book = [f for f in sorted(os.listdir(os.path.join(ROOT, "book_modules"))) if f.endswith(".py")]
    for f in book:
        files.append((f, open(os.path.join(ROOT, "book_modules", f), "rb").read()))
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    meta = (f"Metadata-Version: 2.1\nName: bbench\nVersion: {v}\n"
            "Summary: Breadboard Bench: a digital-logic simulator for learning how computers work (engine)\n"
            "Author: Peyam Pourbeik\nLicense: MIT\nLicense-File: LICENSE\nRequires-Python: >=3.11\n"
            "Classifier: License :: OSI Approved :: MIT License\n"
            "Description-Content-Type: text/markdown\n\n" + readme)
    files.append((f"{di}/METADATA", meta.encode("utf-8")))
    files.append((f"{di}/WHEEL", b"Wheel-Version: 1.0\nGenerator: bbench build_wheel.py\nRoot-Is-Purelib: true\nTag: py3-none-any\n"))
    files.append((f"{di}/entry_points.txt", b"[console_scripts]\nbbench = bbench.cli:main\n"))
    files.append((f"{di}/LICENSE", open(os.path.join(ROOT, "LICENSE"), "rb").read()))
    files.append((f"{di}/top_level.txt", ("bbench\n" + "".join(f[:-3] + "\n" for f in book)).encode()))
    record = "".join(f"{p},{_hash(d)},{len(d)}\n" for p, d in files) + f"{di}/RECORD,,\n"
    files.append((f"{di}/RECORD", record.encode()))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p, d in files:
            zi = zipfile.ZipInfo(p, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, d)
    return path


def build_mock():
    """web/mock/: the chip library and PC-2 as the engine makes them, for the demo engine
    (engine_mock.js), so that it shows the same parts, positions and boards."""
    sys.path.insert(0, ROOT)
    import bbench
    mock = os.path.join(ROOT, "web", "mock")
    os.makedirs(mock, exist_ok=True)
    with open(os.path.join(mock, "chips.json"), "w", encoding="utf-8") as f:
        json.dump(bbench.library(), f)
    with open(os.path.join(mock, "pc2.bbproj"), "w", encoding="utf-8") as f:
        json.dump(bbench.projects.pc2().to_dict(), f)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "web", "py")
    p = build(out)
    if out == os.path.join(ROOT, "web", "py"):
        with open(os.path.join(out, "index.json"), "w") as f:
            json.dump({"wheel": os.path.basename(p)}, f)
        build_mock()
    print(p, os.path.getsize(p), "bytes")
