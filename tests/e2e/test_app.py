"""End-to-end tests of the Breadboard Bench web app, driven through its own controls.

1. PC-2: load the computer, enter ECHO on the front panel, set input A to 40, RUN, read " 40".
2. Schematic: build a NAND-gate circuit by hand and check its truth table.
3. Analyser: record the 555 clock and measure its period with the two cursors.
4. Clocks run in real time on the schematic (555 clock, 4-bit counter); pause and step.
5. Front panel RUN at a chosen speed; the analyser shows the run live and once it has halted.
6. A timed run starts from the live machine: the program entered on the front panel runs in it.
7. Analyser ruler labels stay distinct when zoomed in; the toolbar stays on one line at 1100 px.
8. PC-2's schematic positions and rack are used as they come from the engine.
"""
import re


def open_example(page, name):
    page.click("#btn-examples")
    page.click(f"#examples-menu button:has-text('{name}')")


def wait_idle(page, ms=200):
    page.wait_for_function("() => window.bbench && window.bbench.simctl && !window.bbench.panel.loading")
    page.wait_for_timeout(ms)


# --------------------------------------------------------------------------- 1. PC-2 runs ECHO
def test_pc2_echo_shows_40(app):
    page = app
    open_example(page, "PC-2: the whole computer")
    page.wait_for_selector("#ws-panel .fp-svg", timeout=60000)
    page.wait_for_function("() => window.bbench.simctl.ready", timeout=60000)
    # the program loader enters ECHO through the PROGRAM switches and WRITE
    page.select_option("#ws-panel .panel-side select", "ECHO")
    page.click("#ws-panel button:has-text('Enter program')")
    page.wait_for_selector("#ws-panel .panel-side .note:has-text('ECHO is in memory')", timeout=60000)
    # what was written can be read back on the RAM data LEDs in PROGRAM mode: the listing shows it
    assert page.locator("#ws-panel .listing tr[data-addr]").count() == 3
    # input A = 40 (type it; the DIP switches follow)
    page.fill("input[aria-label='Input A value']", "40")
    page.press("input[aria-label='Input A value']", "Enter")
    page.wait_for_function("() => document.querySelector(\"[data-dipval='S3'], [data-dip] [data-dipval]\") !== null")
    page.wait_for_timeout(300)
    on = page.eval_on_selector_all("[data-dip] .dip-sw[aria-label^='Input A'][aria-checked='true']", "els => els.map(e => e.getAttribute('aria-label'))")
    assert sorted(on) == ["Input A bit 3", "Input A bit 5"], on
    # RUN at the fastest clock, then read the display
    page.select_option("#ws-panel select[aria-label='Clock speed']", "Infinity")
    page.click("#ws-panel button:has-text('Run')")
    page.wait_for_function("() => /halted/.test(document.querySelector('#ws-panel .cursor-readout').textContent)", timeout=120000)
    page.wait_for_timeout(300)
    shown = page.get_attribute("#ws-panel .fp-svg", "data-display")
    assert shown == "  40", repr(shown)
    assert " 40" in shown
    # the A register LEDs agree: 40 = 0010 1000
    a = page.evaluate("() => [7,6,5,4,3,2,1,0].map(k => bbench.simctl.state.nets['A' + k]).join('')")
    assert a == "00101000", a
    page.shot("pc2-echo-40", docs=True)


# --------------------------------------------------------------------------- 2. a NAND gate built by hand
def place(page, ptype, x, y):
    """Find a part in the library, press Place, click the sheet at canvas position (x, y)."""
    search = page.locator("#library input[type=search]")
    search.fill(ptype)
    page.locator(f"#library .lib-item[data-type='{ptype}'] .add").click()
    box = page.locator("#ws-schematic .canvas").bounding_box()
    page.mouse.click(box["x"] + x, box["y"] + y)


def pin(page, part, n):
    return page.locator(f"#ws-schematic [data-part='{part}'] .pin-hot[data-pin='{n}']")


def wire(page, a, b):
    pin(page, *a).click()
    pin(page, *b).click()


def label(page, part, n, net):
    page.click("#ws-schematic [data-tool='label']")
    pin(page, part, n).click()
    page.fill("dialog.dlg input", net)
    page.press("dialog.dlg input", "Enter")
    page.wait_for_selector("dialog.dlg", state="detached")


def test_build_nand_and_check_truth_table(app):
    page = app
    page.click("#btn-new")
    page.click("#tab-schematic")
    place(page, "74HCT00", 520, 330)
    place(page, "SW", 140, 200)
    place(page, "SW", 140, 420)
    place(page, "R", 300, 560)
    place(page, "R", 420, 640)
    place(page, "PROBE", 720, 560)
    ids = page.evaluate("() => bbench.store.project.parts.map(p => p.id + ':' + p.type)")
    assert ids == ["U1:74HCT00", "S1:SW", "S2:SW", "R1:R", "R2:R", "P1:PROBE"], ids
    # NAND 1: pins 1, 2 in, 3 out
    wire(page, ("S1", "2"), ("U1", "1"))
    wire(page, ("S2", "2"), ("U1", "2"))
    wire(page, ("R1", "1"), ("U1", "1"))
    wire(page, ("R2", "1"), ("U1", "2"))
    wire(page, ("U1", "3"), ("P1", "1"))
    for part, n, net in [("S1", "1", "VCC"), ("S2", "1", "VCC"), ("R1", "2", "GND"), ("R2", "2", "GND"),
                         ("U1", "4", "GND"), ("U1", "5", "GND"), ("U1", "9", "GND"), ("U1", "10", "GND"),
                         ("U1", "12", "GND"), ("U1", "13", "GND")]:
        label(page, part, n, net)
    page.click("#ws-schematic [data-tool='select']")
    nets = page.evaluate("() => Object.fromEntries(bbench.store.project.nets.map(n => [n.name, n.pins.map(p => p.join('.')).sort()]))")
    a_net = [k for k, v in nets.items() if "U1.1" in v][0]
    assert sorted(nets[a_net]) == ["R1.1", "S1.2", "U1.1"], nets
    assert "U1.3" in [p for v in nets.values() for p in v if "P1.1" in v]
    page.wait_for_function("() => bbench.simctl.ready")

    def probe():
        page.wait_for_timeout(250)
        page.wait_for_function("() => bbench.simctl.busy !== undefined")
        return page.locator("#ws-schematic [data-part='P1'] .valbadge").text_content().strip()

    def flip(sw):
        page.locator(f"#ws-schematic [data-part='{sw}'] [data-op]").click()
        page.evaluate("() => bbench.simctl.busy")

    table = {}
    for a in (0, 1):
        for b in (0, 1):
            st = page.evaluate("() => [bbench.simctl.ctl.S1, bbench.simctl.ctl.S2]")
            if bool(st[0]) != bool(a):
                flip("S1")
            if bool(st[1]) != bool(b):
                flip("S2")
            page.wait_for_function(f"() => !!bbench.simctl.ctl.S1 === {str(bool(a)).lower()} && !!bbench.simctl.ctl.S2 === {str(bool(b)).lower()}")
            table[(a, b)] = probe()
            if (a, b) == (1, 0):
                page.shot("nand-schematic", docs=True)
    assert table == {(0, 0): "1", (0, 1): "1", (1, 0): "1", (1, 1): "0"}, table
    # the wires carry the values as colour and as text: Y is 0 with both switches on
    y_net = page.evaluate("() => bbench.store.project.nets.find(n => n.pins.some(p => p[0]==='U1' && p[1]==='3')).name")
    assert page.evaluate(f"() => bbench.simctl.state.nets['{y_net}']") == 0


# --------------------------------------------------------------------------- 3. the analyser on a 555 clock
def test_analyser_measures_555_clock(app):
    page = app
    open_example(page, "555 clock")
    page.wait_for_function("() => bbench.simctl.ready", timeout=60000)
    page.click("#tab-analyser")
    page.select_option("#ws-analyser select[aria-label='How to run']", "timed")
    page.fill("#ws-analyser input[aria-label='How long to run']", "10 ms")
    page.click("#ws-analyser button:has-text('Run')")
    page.wait_for_function("() => bbench.analyser.trace && !bbench.analyser.runBtn.disabled", timeout=120000)
    rises = page.evaluate("""() => {
        const s = bbench.analyser.trace.signals.find(x => x.name === 'CLK');
        return s.changes.filter((c, i) => i > 0 && c[1] === 1).map(c => c[0]);
    }""")
    assert len(rises) >= 4, rises
    period = (rises[-1] - rises[1]) / (len(rises) - 2)
    f = 1e9 / period
    assert 500 < f < 900, f           # R1 = 1k, R2 = 10k, C = 100 nF: about 690 Hz
    # cursors A and B on two rising edges; the readout shows the period
    page.evaluate(f"() => {{ bbench.analyser.cursors = [{rises[1]}, {rises[2]}]; bbench.analyser.draw(); }}")
    txt = page.text_content("#ws-analyser .cursor-readout")
    m = re.search(r"Δt\s*([\d.]+)\s*(ms|µs)", txt)
    assert m, txt
    dt_ns = float(m.group(1)) * (1e6 if m.group(2) == "ms" else 1e3)
    assert abs(dt_ns - (rises[2] - rises[1])) / (rises[2] - rises[1]) < 0.01
    # CLK_n is the inverse of CLK (through a 74HCT04)
    names = page.evaluate("() => bbench.analyser.trace.signals.map(s => s.name)")
    assert "CLK_n" in names
    page.shot("analyser-555", docs=True)
    # VCD export produces a standard header
    vcd = page.evaluate("async () => (await import('./js/analyser.js')).toVcd(bbench.analyser.trace, 'clock')")
    assert vcd.startswith("$date") and "$enddefinitions $end" in vcd and "$var wire 1" in vcd


# --------------------------------------------------------------------------- 4. clocks run on the schematic
def sample(page, expr, n=25, ms=100):
    out = []
    for _ in range(n):
        out.append(page.evaluate(expr))
        page.wait_for_timeout(ms)
    return out


def test_555_and_counter_run_on_the_schematic(app):
    page = app
    open_example(page, "555 clock")
    page.wait_for_function("() => bbench.store.project.name === '555 clock' && bbench.simctl.ready && bbench.simctl.rev === bbench.store.rev && bbench.simctl.clocks.length > 0", timeout=60000)
    page.click("#tab-schematic")
    clk = sample(page, "() => bbench.simctl.state.nets.CLK")
    assert set(clk) == {0, 1}, clk                                  # it oscillates by itself
    # the wire tag on the schematic follows
    tags = set(sample(page, "() => document.querySelector(\"#ws-schematic .valbadge\") && [...document.querySelectorAll('#ws-schematic .valbadge')].map(e => e.textContent).join('')", 10))
    assert len(tags) > 1, tags
    # pause: the clock stops; Step: one cycle
    page.click("#ws-schematic [data-clock='pause']")
    page.wait_for_timeout(300)
    t0 = page.evaluate("() => bbench.simctl.state.t_ns")
    page.wait_for_timeout(600)
    assert page.evaluate("() => bbench.simctl.state.t_ns") == t0
    c0 = page.evaluate("() => bbench.simctl.state.cycles")
    page.click("#ws-schematic [data-clock='step']")
    page.wait_for_function(f"() => bbench.simctl.state.cycles === {c0 + 1}")
    page.click("#ws-schematic [data-clock='pause']")              # run again
    # the 4-bit counter counts at its own speed (about 2 Hz, real time)
    open_example(page, "4-bit counter")
    page.wait_for_function("() => bbench.store.project.name === '4-bit counter' && bbench.simctl.ready && bbench.simctl.rev === bbench.store.rev && bbench.simctl.speed != null", timeout=60000)
    assert page.evaluate("() => bbench.simctl.speed") == "real"
    q = "() => [3,2,1,0].map(k => bbench.simctl.state.nets['Q' + k]).join('')"
    vals = sample(page, q, 12, 250)
    nums = [int(v, 2) for v in vals]
    assert len(set(nums)) >= 4 and nums == sorted(nums), vals
    # faster
    page.select_option("#ws-schematic select[aria-label='Clock speed']", "10")
    page.wait_for_timeout(200)
    a = int(page.evaluate(q), 2)
    page.wait_for_timeout(1000)
    b = int(page.evaluate(q), 2)
    assert (b - a) % 16 >= 6, (a, b)


# --------------------------------------------------------------------------- 5/6. PC-2 runs; the analyser shows it
def enter(page, prog, a=None):
    page.select_option("#ws-panel .panel-side select", prog)
    page.click("#ws-panel button:has-text('Enter program')")
    page.wait_for_selector(f"#ws-panel .panel-side .note:has-text('{prog} is in memory')", timeout=60000)
    if a is not None:
        page.fill("input[aria-label='Input A value']", str(a))
        page.press("input[aria-label='Input A value']", "Enter")
        page.wait_for_timeout(300)


def open_pc2(page):
    open_example(page, "PC-2: the whole computer")
    page.wait_for_selector("#ws-panel .fp-svg", timeout=60000)
    page.wait_for_function("() => window.bbench.simctl.ready", timeout=60000)


def test_front_panel_run_and_live_analyser(app):
    page = app
    open_pc2(page)
    enter(page, "ECHO", 40)
    page.select_option("#ws-panel select[aria-label='Clock speed']", "50")
    page.click("#ws-panel button:has-text('Run')")
    # RUN moves the RUN/STEP switch; the 555 clock (real-time) drives the machine
    page.wait_for_function("() => bbench.simctl.state.switches[bbench.panel.c.runstep.id] === 'RUN'", timeout=10000)
    page.wait_for_function("() => /running|halted/.test(document.querySelector('#ws-panel .cursor-readout').textContent)", timeout=10000)
    # while it runs (or right after), the analyser shows the live run with no further steps
    page.click("#tab-analyser")
    assert page.evaluate("() => bbench.analyser.mode") == "zero"
    page.wait_for_function("() => /halted/.test(bbench.analyser.caption)", timeout=60000)
    page.wait_for_function("() => { const s = bbench.analyser.trace && bbench.analyser.trace.signals.find(x => x.name === 'HLT_n'); return s && s.changes.length && s.changes[s.changes.length - 1][1] === 0; }", timeout=10000)
    sig = page.evaluate("() => Object.fromEntries(bbench.analyser.trace.signals.map(s => [s.name, s.changes]))")
    rises = [c for i, c in enumerate(sig["CLK"]) if i and c[1] == 1]
    assert 5 <= len(rises) <= 12, rises                   # ECHO halts after a few cycles
    bus = page.evaluate("() => bbench.analyser.busChanges(bbench.analyser.rows().find(r => r.bus && r.key === 'BUS')).map(c => c[1])")
    assert 0x28 in bus and 0xC0 in bus, bus               # 40 (IN 0 then OUT) and the opcode C0
    assert page.get_attribute("#ws-panel .fp-svg", "data-display") == "  40"
    page.shot("analyser-pc2-live")


def test_timed_run_starts_from_the_loaded_program(app):
    page = app
    open_pc2(page)
    enter(page, "ECHO", 40)
    page.click("#ws-panel button:has-text('Run')")
    page.wait_for_function("() => bbench.simctl.state.switches[bbench.panel.c.runstep.id] === 'RUN'", timeout=10000)
    page.evaluate("() => bbench.simctl.setPaused(true)")      # hold the live machine where it is
    page.wait_for_timeout(300)
    live = page.evaluate("() => [bbench.simctl.state.nets.HLT_n, bbench.simctl.state.t_ns]")
    page.click("#tab-analyser")
    page.select_option("#ws-analyser select[aria-label='How to run']", "timed")
    assert page.input_value("#ws-analyser select[aria-label='Start the timed run from']") == "current"
    page.fill("#ws-analyser input[aria-label='How long to run']", "4 ms")
    page.evaluate("() => { bbench.store.commit('probes', p => { p.probes = [...p.probes, ...[0,1,2,3,4,5,6,7].map(k => 'OUT' + k)]; }, 'view'); }")
    page.click("#ws-analyser button:has-text('Run')")
    page.wait_for_function("() => bbench.analyser.trace && !bbench.analyser.runBtn.disabled", timeout=120000)
    out = page.evaluate("() => { const r = bbench.analyser.rows().find(r => r.bus && r.key === 'OUT'); const c = bbench.analyser.busChanges(r); return c[c.length - 1][1]; }")
    assert out == 40, out                                     # the program in RAM ran in the timed run
    hlt = page.evaluate("() => bbench.analyser.trace.signals.find(s => s.name === 'HLT_n').changes")
    assert hlt[-1][1] == 0, hlt
    assert "live state" in page.text_content("#ws-analyser .wave-caption")
    # the live simulation did not move
    assert page.evaluate("() => [bbench.simctl.state.nets.HLT_n, bbench.simctl.state.t_ns]") == live
    # from power-up, RAM is empty: nothing reaches OUT
    page.select_option("#ws-analyser select[aria-label='Start the timed run from']", "power")
    page.click("#ws-analyser button:has-text('Run')")
    page.wait_for_function("() => /power-up/.test(bbench.analyser.caption) && !bbench.analyser.runBtn.disabled", timeout=120000)


# --------------------------------------------------------------------------- 7. ruler labels and the toolbar
def test_ruler_labels_distinct_and_toolbar_one_line(app):
    page = app
    labels = page.evaluate("""async () => {
        const u = await import('./js/util.js');
        const out = [];
        for (const [t0, step] of [[208000, 10], [208123, 1], [208123.4, 0.1], [5e9, 1], [0, 1e6]]) {
            const ticks = [0, 1, 2, 3, 4].map(k => t0 + k * step);
            out.push(u.tickLabels(ticks, step));
        }
        return out;
    }""")
    for r in labels:
        assert len(set(r["labels"])) == len(r["labels"]), r
    assert labels[0]["labels"][:2] == ["208.00 µs", "208.01 µs"]
    assert labels[3]["base"] and labels[3]["labels"][1] == "+1 ns"
    open_example(page, "555 clock")
    page.wait_for_function("() => bbench.simctl.ready", timeout=60000)
    page.set_viewport_size({"width": 1100, "height": 800})
    page.click("#tab-analyser")
    page.select_option("#ws-analyser select[aria-label='How to run']", "timed")
    page.fill("#ws-analyser input[aria-label='How long to run']", "1 ms")
    page.click("#ws-analyser button:has-text('Run')")
    page.wait_for_function("() => bbench.analyser.trace && !bbench.analyser.runBtn.disabled", timeout=120000)
    # zoom to 100 ns at about 208 us: every tick label differs
    page.evaluate("() => { const a = bbench.analyser; a.t0 = 208000; a.t1 = 208100; a.draw(); }")
    ticks = page.evaluate("() => bbench.analyser.tickText")
    assert len(ticks) >= 4 and len(set(ticks)) == len(ticks), ticks
    page.evaluate("() => { const a = bbench.analyser; a.cursors = [208020.5, 208071.25]; a.draw(); }")
    page.wait_for_timeout(200)
    tb = page.evaluate("() => document.querySelector('#ws-analyser .toolbar').getBoundingClientRect().height")
    assert tb < 60, tb                                        # one line
    fit = page.evaluate("() => { const r = bbench.analyser.readout; return [r.scrollWidth <= r.clientWidth + 1, r.textContent]; }")
    assert fit[0] and "Δt" in fit[1], fit                    # nothing cut off
    page.set_viewport_size({"width": 1440, "height": 900})


# --------------------------------------------------------------------------- 8. PC-2 as the engine lays it out
def test_pc2_positions_and_rack_used_as_given(app):
    page = app
    open_pc2(page)
    eng = page.evaluate("async () => { const p = await (await import('./engine.js')).engine.example('pc2'); return [p.parts.map(x => [x.id, x.x, x.y]), p.breadboards.map(b => [b.name, b.x, b.y])]; }")
    app_ = page.evaluate("() => { const p = bbench.store.project; return [p.parts.map(x => [x.id, x.x, x.y]), p.breadboards.map(b => [b.name, b.x, b.y])]; }")
    assert eng == app_                                        # no re-layout by the app
    assert page.evaluate("() => bbench.schematic.crowded()") is False
    racks = {n: (x, y) for n, x, y in app_[1]}
    assert racks["Bus"] == (720, 0) and racks["Front panel"] == (720, 1560) and racks["Input"] == (1440, 1820)
    for m in ("A register", "Control"):
        open_example(page, m)
        page.wait_for_function(f"() => bbench.store.project.name === 'PC-2 {m}' && bbench.simctl.ready", timeout=60000)
        assert page.evaluate("() => bbench.schematic.crowded()") is False, m


# --------------------------------------------------------------------------- review round 1
def test_pause_is_shared_and_not_cancelled_by_run(app):
    """A pause set on the Schematic toolbar holds when Run or the RUN/STEP switch is used on the
    front panel; both toolbars and the status bar show it; Resume clock ends it."""
    page = app
    open_pc2(page)
    enter(page, "ECHO", 40)
    page.click("#tab-schematic")
    page.click("#ws-schematic [data-clock='pause']")
    assert page.evaluate("() => bbench.simctl.paused") is True
    page.click("#tab-panel")
    assert page.text_content("#ws-panel [data-clock='pause']").strip() == "▶ Resume clock"
    page.click("#ws-panel button:has-text('Run')")
    page.wait_for_function("() => bbench.simctl.state.switches[bbench.panel.c.runstep.id] === 'RUN'", timeout=10000)
    page.wait_for_timeout(400)
    assert page.evaluate("() => bbench.simctl.paused") is True
    assert "clock paused" in page.text_content("#ws-panel .cursor-readout")
    assert "clock paused" in page.text_content("#sim-status")
    assert page.evaluate("() => bbench.simctl.state.nets.HLT_n") == 1          # still waiting
    page.click("#ws-panel [data-clock='pause']")                                  # Resume clock
    page.wait_for_function("() => bbench.simctl.state.nets.HLT_n === 0", timeout=60000)
    assert page.text_content("#ws-schematic [data-clock='pause']").strip() == "⏸ Pause clock"


def test_counter_menu_path_code_tab_imports_and_licences(app):
    page = app
    page.click("#btn-examples")
    heads = page.evaluate("() => [...document.querySelectorAll('#examples-menu h6')].map(e => e.textContent)")
    assert "Counters" in heads, heads
    items = page.evaluate("""() => { const out = []; let g = null;
        for (const el of document.querySelector('#examples-menu').children) {
            if (el.tagName === 'H6') g = el.textContent; else out.push([g, el.firstChild.textContent]); }
        return out; }""")
    assert ["Counters", "4-bit counter"] in items, items
    page.click("#examples-menu button:has-text('4-bit counter')")
    page.wait_for_function("() => bbench.store.project.name === '4-bit counter'", timeout=60000)
    if page.engine_mode == "python":
        page.click("#tab-code")
        code = ("import sys; sys.path.insert(0, 'tools/pc2kit')\nfrom bench import Bench\nimport pc2, pc2tools\n"
                "print(pc2tools.NAMES[12], len(pc2tools.trace(pc2.asm(['IN 0', 'OUT 0', 'HALT']), in0=3)))")
        r = page.evaluate("async (c) => await bbench.engine.runPython(c)", code)
        assert r["ok"] and "IN 9" in r["out"], r
    href = page.get_attribute("#about-link", "href")
    assert href == "LICENSES/index.html"
    for f in ("Breadboard-Bench-MIT.txt", "Pyodide-MPL-2.0.txt", "CPython-3.14-LICENSE.txt", "Emscripten-LICENSE.txt",
              "OFL-Fredoka.txt", "OFL-Lexend.txt", "OFL-JetBrainsMono.txt"):
        assert page.evaluate("async (f) => (await fetch('LICENSES/' + f)).ok", f), f


# --------------------------------------------------------------------------- 10. Code tab runs scripts as scripts
def test_code_tab_runs_main_block_and_book_modules(app):
    """A box guarded by `if __name__ == "__main__":` must run (book p. 68 latch_lab.py, p. 107 alu_sim.py),
    and Chapter 12/13's modules (pc2_custom, pc2plus) import the same way as pc2 and pc2tools."""
    page = app
    if page.engine_mode != "python":
        return
    page.click("#tab-code")
    code = ("def main():\n    print('main ran', __name__)\n\nif __name__ == \"__main__\":\n    main()\n")
    r = page.evaluate("async (c) => await bbench.engine.runPython(c)", code)
    assert r["ok"] and "main ran __main__" in r["out"], r
    code = ("import sys; sys.path.insert(0, 'tools/pc2kit')\n"
            "from pc2_custom import PC2, asm\nimport pc2plus\n"
            "m = PC2(asm(['IN 0', 'DBL', 'OUT 0', 'HALT']), in0=37).run()\n"
            "mem, lab = pc2plus.asm(['IN 0', 'STORE x', 'IN 1', 'ADD x', 'OUT 0', 'HALT', 'x: data 0'])\n"
            "print(m.out, pc2plus.run(mem, 5, 6).out)")
    r = page.evaluate("async (c) => await bbench.engine.runPython(c)", code)
    assert r["ok"] and "74 11" in r["out"], r
