"""Re-take the app screenshots in docs/screenshots/ and the user guide's images in docs/img/.

    python3 tools/screenshots.py [names...]      # default: all of them

Serves web/ on a local port, opens it in Playwright's Chromium (1440 x 900) with the Python
engine, and drives the app through its own controls, as the end-to-end tests do.
"""
import functools
import http.server
import os
import socketserver
import sys
import threading

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WEB = os.path.join(ROOT, "web")
SHOTS = os.path.join(ROOT, "docs", "screenshots")
IMG = os.path.join(ROOT, "docs", "img")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


Quiet.extensions_map.update({".mjs": "text/javascript", ".js": "text/javascript", ".wasm": "application/wasm",
                             ".whl": "application/zip", ".py": "text/plain"})


class App:
    def __init__(self, browser, url, dark=False):
        self.ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1,
                                       color_scheme="dark" if dark else "light")
        self.page = p = self.ctx.new_page()
        p.goto(url + "?fresh&nosw")
        p.wait_for_selector("body[data-ready='1']", timeout=30000)
        p.wait_for_selector("#engine-status.ok", timeout=120000)

    def close(self):
        self.ctx.close()

    def example(self, button, name):
        p = self.page
        p.click("#btn-examples")
        p.click(f"#examples-menu button:has-text('{button}')")
        p.wait_for_function(f"() => bbench.store.project.name === {name!r} && bbench.simctl.ready "
                            "&& bbench.simctl.rev === bbench.store.rev", timeout=60000)
        p.wait_for_timeout(400)

    def quiet(self, ms=2800):
        """Let the toast go."""
        self.page.wait_for_timeout(ms)

    def shot(self, *paths):
        for path in paths:
            self.page.screenshot(path=path)
            print("wrote", os.path.relpath(path, ROOT))

    def pc2_echo(self):
        """PC-2 with ECHO entered, input A = 40, run to HALT at the fastest clock."""
        p = self.page
        self.example("PC-2: the whole computer", "PC-2")
        p.click("#tab-panel")
        p.select_option("#ws-panel .panel-side select", "ECHO")
        p.click("#ws-panel button:has-text('Enter program')")
        p.wait_for_selector("#ws-panel .panel-side .note:has-text('ECHO is in memory')", timeout=60000)
        p.fill("input[aria-label='Input A value']", "40")
        p.press("input[aria-label='Input A value']", "Enter")
        p.wait_for_timeout(300)
        p.select_option("#ws-panel select[aria-label='Clock speed']", "Infinity")
        p.click("#ws-panel button:has-text('Run')")
        p.wait_for_function("() => /halted/.test(document.querySelector('#ws-panel .cursor-readout').textContent)",
                            timeout=120000)
        p.select_option("#ws-panel select[aria-label='Clock speed']", "10")
        p.wait_for_timeout(500)


def take(browser, url, want):
    def on(name):
        return not want or name in want

    # ---- 555 clock: schematic (ticking) and analyser with cursors
    if on("555"):
        a = App(browser, url)
        p = a.page
        a.example("555 clock", "555 clock")
        p.click("#tab-schematic")
        p.keyboard.press("f")
        a.quiet()
        a.shot(os.path.join(SHOTS, "1-schematic-555-clock.png"))
        p.click("#tab-analyser")
        p.select_option("#ws-analyser select[aria-label='How to run']", "timed")
        p.fill("#ws-analyser input[aria-label='How long to run']", "10 ms")
        p.click("#ws-analyser button:has-text('Run')")
        p.wait_for_function("() => bbench.analyser.trace && !bbench.analyser.runBtn.disabled", timeout=120000)
        p.evaluate("""() => { const a = bbench.analyser; const c = a.trace.signals.find(s => s.name === 'CLK').changes;
                     const r = c.filter((x, i) => i > 0 && x[1] === 1).map(x => x[0]); a.cursors = [r[1], r[2]]; a.draw(); }""")
        p.wait_for_timeout(300)
        a.shot(os.path.join(SHOTS, "3-analyser-555-cursors.png"), os.path.join(IMG, "analyser-555.png"))
        a.close()

    # ---- PC-2 A register module, and the A register sheet of the whole machine
    if on("module"):
        a = App(browser, url)
        p = a.page
        a.example("A register", "PC-2 A register")
        p.click("#tab-schematic")
        p.wait_for_timeout(300)
        a.quiet()
        a.shot(os.path.join(SHOTS, "1-schematic-pc2-a-register-module.png"))
        a.example("PC-2: the whole computer", "PC-2")
        p.click("#tab-schematic")
        p.select_option("#ws-schematic select[aria-label='Sheet']", "A register")
        p.keyboard.press("f")
        a.quiet()
        a.shot(os.path.join(IMG, "schematic-pc2-a-register.png"))
        a.close()

    # ---- PC-2 runs ECHO: front panel, analyser, breadboards
    if on("pc2"):
        a = App(browser, url)
        p = a.page
        a.pc2_echo()
        a.quiet(1500)
        a.shot(os.path.join(SHOTS, "4-front-panel-echo-40.png"), os.path.join(IMG, "pc2-echo-40.png"))
        p.click("#tab-analyser")
        p.wait_for_function("() => /halted/.test(bbench.analyser.caption)", timeout=30000)
        p.wait_for_timeout(600)
        a.shot(os.path.join(SHOTS, "3-analyser-pc2-echo.png"))
        p.click("#tab-breadboard")
        p.wait_for_timeout(800)
        p.click("#ws-breadboard .item:has-text('Show all boards')")
        p.wait_for_timeout(600)
        a.shot(os.path.join(IMG, "breadboard-pc2-17-boards.png"))
        p.click("#ws-breadboard button:has-text('Check')")
        p.wait_for_function("() => /All boards match/.test(document.querySelector('#ws-breadboard').textContent)", timeout=60000)
        p.wait_for_timeout(500)
        a.shot(os.path.join(SHOTS, "2-breadboard-17-boards-checked.png"))
        p.click("#ws-breadboard .item:has-text('Front panel')")
        p.wait_for_timeout(600)
        a.shot(os.path.join(IMG, "breadboard-check.png"))
        p.click("#ws-breadboard .item:has-text('A register')")
        p.wait_for_timeout(600)
        a.shot(os.path.join(SHOTS, "2-breadboard-a-register-lit.png"))
        a.close()
        a = App(browser, url)
        a.example("PC-2: the whole computer", "PC-2")
        a.page.click("#tab-breadboard")
        a.page.wait_for_timeout(800)
        a.page.click("#ws-breadboard .item:has-text('Front panel')")
        a.quiet()
        a.shot(os.path.join(IMG, "breadboard-front-panel.png"))
        a.close()

    # ---- dark theme
    if on("dark"):
        a = App(browser, url)
        p = a.page
        if p.evaluate("() => document.documentElement.dataset.theme") != "dark":
            p.click("#btn-theme")
        a.pc2_echo()
        a.quiet(1500)
        a.shot(os.path.join(SHOTS, "6-dark-theme-front-panel.png"), os.path.join(IMG, "dark-front-panel.png"))
        a.close()


def main(want):
    handler = functools.partial(Quiet, directory=WEB)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    os.makedirs(SHOTS, exist_ok=True)
    os.makedirs(IMG, exist_ok=True)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            take(b, url, set(want))
            b.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main(sys.argv[1:])
