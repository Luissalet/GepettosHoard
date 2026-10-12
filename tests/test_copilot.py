"""The Faustus copilot in Gepetto's Hoard: relay routes, launcher injection, manifest and the off switch."""
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

import backend.app as server
from backend.hoard_link.copilot import has_copilot, install_copilot

ROOT = Path(__file__).resolve().parents[1]
LOCAL = "http://127.0.0.1:8767"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    with TestClient(server.app, base_url=LOCAL) as c:
        yield c


@pytest.fixture
def fake_faustus():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            ok = self.path == "/api/hoard-copilot/capabilities"
            body = json.dumps({"contract_version": "1.0"} if ok else {}).encode()
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_the_app_mounts_the_relay_and_the_launcher(client):
    assert has_copilot(server.app) and server.app.state.hoard_copilot == "gepetto"
    # the relay routes answer (503 when no Faustus runs here); the SPA never swallows them as a 404
    assert client.get("/api/copilot/panel.js").status_code in (200, 503)
    assert client.post("/api/copilot/proxy", json={"path": "/api/other"}).status_code == 400
    launcher = client.get("/api/copilot/launcher.js")
    assert launcher.status_code == 200 and "javascript" in launcher.headers["content-type"]
    assert "faustus-chat" in launcher.text
    # the relay answers (503 when no Faustus is running here), it is never a 404 that the SPA would swallow
    assert client.get("/api/copilot/info").status_code in (200, 503)


def test_the_relay_names_this_app_and_its_data_space(tmp_path, fake_faustus):
    app = FastAPI()
    install_copilot(app, "gepetto", tmp_path, app_name="Gepetto's Hoard", faustus_urls=[fake_faustus], token="")
    info = TestClient(app).get("/api/copilot/info").json()
    assert info["app_id"] == "gepetto" and info["app_name"] == "Gepetto's Hoard"
    assert info["data_space_id"] and info["panel_url"] == "/api/copilot/panel.js"


def test_the_launcher_is_added_to_the_html_the_app_serves(tmp_path, fake_faustus):
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def home():
        return "<html><body><div id='root'></div></body></html>"

    install_copilot(app, "gepetto", tmp_path, app_name="Gepetto's Hoard", faustus_urls=[fake_faustus], token="")
    page = TestClient(app).get("/")
    assert '<script type="module" src="/api/copilot/launcher.js"></script></body>' in page.text


@pytest.mark.skipif(not (ROOT / "dist" / "index.html").exists(), reason="the UI is not built")
def test_the_built_ui_carries_the_launcher(client):
    page = client.get("/")
    assert page.status_code == 200 and "/api/copilot/launcher.js" in page.text


def test_the_manifest_declares_the_copilot_context():
    manifest = json.loads((ROOT / "faustus-plugin.json").read_text("utf-8"))
    copilot = manifest["x-family"]["copilot"]
    assert copilot["provider"] == "faustus" and copilot["contract"] == "1.0"
    assert copilot["panel"] == "/api/copilot/panel.js"
    assert {"project", "texture", "region", "evaluation"} <= set(copilot["context"])


def test_the_off_switch_removes_the_routes():
    code = "import backend.app as s; from backend.hoard_link.copilot import has_copilot; print(has_copilot(s.app))"
    env = {**__import__("os").environ, "HOARD_COPILOT": "0", "SCULPTORS_HOARD_DATA_DIR": str(ROOT / "test-results" / "copilot-off")}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.stdout.strip().splitlines()[-1] == "False", out.stderr
