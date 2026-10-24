"""Write sw.js: the service worker that keeps Breadboard Bench working offline.

Run after changing any file in web/:   python3 tools/build_sw.py
It lists every file the app needs (Pyodide included), and a version made from their
contents, so a browser fetches the new set exactly when something changed. It also
writes py/index.json naming the newest bbench wheel in py/ (a static server cannot list
a folder)."""
import hashlib
import json
import os

WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"tools", "__pycache__"}
SKIP = {"sw.js"}

wheels = sorted(f for f in os.listdir(os.path.join(WEB, "py")) if f.startswith("bbench-") and f.endswith(".whl")) \
    if os.path.isdir(os.path.join(WEB, "py")) else []
if wheels:
    with open(os.path.join(WEB, "py", "index.json"), "w") as f:
        json.dump({"wheel": wheels[-1]}, f)

files = []
h = hashlib.sha256()
for root, dirs, names in os.walk(WEB):
    dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
    for n in sorted(names):
        rel = os.path.relpath(os.path.join(root, n), WEB).replace(os.sep, "/")
        if rel in SKIP or n.startswith("."):
            continue
        if rel.startswith("py/") and rel.endswith(".whl") and wheels and n != wheels[-1]:
            continue
        files.append(rel)
        with open(os.path.join(root, n), "rb") as f:
            h.update(rel.encode() + f.read())
version = h.hexdigest()[:12]

with open(os.path.join(WEB, "tools", "sw_template.js")) as f:
    tpl = f.read()
out = tpl.replace("__VERSION__", version).replace("__FILES__", json.dumps(["./"] + files, indent=1))
with open(os.path.join(WEB, "sw.js"), "w") as f:
    f.write(out)
print(f"sw.js: {len(files)} files, version {version}" + (f", wheel {wheels[-1]}" if wheels else ", no wheel"))
