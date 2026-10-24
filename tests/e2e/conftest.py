"""Fixtures for the browser tests: a local web server for web/ and a Chromium page.

Run:  python3 -m pytest tests/e2e -q
Screenshots go to tests/e2e/shots/ (and docs/img/ for the user guide with --docs-shots).
"""
import functools
import http.server
import os
import socketserver
import threading

import pytest

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.sync_api import sync_playwright  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.abspath(os.path.join(HERE, "..", "..", "web"))
SHOTS = os.path.join(HERE, "shots")
DOCS_IMG = os.path.abspath(os.path.join(HERE, "..", "..", "docs", "img"))


def pytest_addoption(parser):
    parser.addoption("--docs-shots", action="store_true", help="also write screenshots for docs/user-guide.md")
    parser.addoption("--engine", default="auto", help="auto (Python if a wheel is in web/py), python, or mock")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


Quiet.extensions_map.update({".mjs": "text/javascript", ".js": "text/javascript", ".wasm": "application/wasm",
                             ".whl": "application/zip", ".py": "text/plain"})


@pytest.fixture(scope="session")
def server():
    handler = functools.partial(Quiet, directory=WEB)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def engine_mode(request):
    mode = request.config.getoption("--engine")
    if mode == "auto":
        pyd = os.path.join(WEB, "py")
        has = os.path.isdir(pyd) and any(f.startswith("bbench-") and f.endswith(".whl") for f in os.listdir(pyd))
        mode = "python" if has else "mock"
    return mode


@pytest.fixture
def app(browser, server, engine_mode, request):
    """The app, freshly opened (no autosave, no service worker), with the engine ready."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda d: d.accept())
    q = "?fresh&nosw" + ("&engine=mock" if engine_mode == "mock" else "")
    page.goto(server + q)
    page.wait_for_selector("body[data-ready='1']", timeout=30000)
    if engine_mode == "python":
        page.wait_for_selector("#engine-status.ok", timeout=120000)
    page.engine_mode = engine_mode
    page.errors = errors
    os.makedirs(SHOTS, exist_ok=True)

    def shot(name, docs=False):
        path = os.path.join(SHOTS, name + ".png")
        page.screenshot(path=path)
        if docs and request.config.getoption("--docs-shots"):
            os.makedirs(DOCS_IMG, exist_ok=True)
            page.screenshot(path=os.path.join(DOCS_IMG, name + ".png"))
        return path
    page.shot = shot
    yield page
    ctx.close()
    assert not errors, errors
