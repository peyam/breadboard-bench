// Web Worker: Pyodide + the bbench engine. Messages: {id, fn, args} -> {id, ok, result | error}.
import { loadPyodide } from "./pyodide/pyodide.mjs";

let py = null;
let call = null;

const handlers = {
  async init({ wheel }) {
    py = await loadPyodide({ indexURL: new URL("./pyodide/", import.meta.url).href });
    py.setStdout({ batched: (text) => postMessage({ type: "stdout", text: text + "\n" }) });
    py.setStderr({ batched: (text) => postMessage({ type: "stdout", text: text + "\n", err: true }) });
    const glue = await (await fetch(new URL("./engine_glue.py", import.meta.url))).text();
    let bbench = false, version = null, error = null;
    if (wheel) {
      try {
        const buf = new Uint8Array(await (await fetch(new URL(`./py/${wheel}`, import.meta.url))).arrayBuffer());
        py.FS.writeFile("/tmp/bbench.whl", buf);
        py.runPython("import zipfile, site\nzipfile.ZipFile('/tmp/bbench.whl').extractall(site.getsitepackages()[0])");
        bbench = true;
      } catch (e) { error = String(e.message || e).split("\n").slice(-2).join(" "); }
    }
    py.runPython(glue);
    if (bbench) {
      try { version = py.runPython("_bb_init()"); } catch (e) { bbench = false; error = String(e.message || e).split("\n").filter(Boolean).slice(-1)[0]; }
    }
    call = py.globals.get("_bb_call");
    return { bbench, version, error, python: py.runPython("import sys; sys.version.split()[0]") };
  },
  async api(fn, args) {
    if (!call) throw new Error("engine not ready");
    const out = JSON.parse(call(fn, JSON.stringify(args || [])));
    if (out.error) throw new Error(out.error);
    return out.result;
  },
  async python(code) {
    const run = py.globals.get("_bb_console");
    return JSON.parse(run(code));
  },
};

onmessage = async (e) => {
  const { id, fn, args } = e.data;
  try {
    const result = await handlers[fn](...(args || []));
    postMessage({ id, ok: true, result });
  } catch (err) {
    postMessage({ id, ok: false, error: String((err && err.message) || err) });
  }
};
