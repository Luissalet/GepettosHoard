"""What Sculptor's Hoard takes from Hoard Link: the request guard, atomic writes and the Blender process runner."""
import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import backend.app as server
from backend import closed_loop, project_history

LOCAL = "http://127.0.0.1:8767"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    with TestClient(server.app, base_url=LOCAL) as c:
        yield c


def test_a_foreign_host_name_is_refused(client):
    # a page that rebinds its DNS name to 127.0.0.1 sends its own name in Host
    refused = client.get("/api/health", headers={"Host": "evil.example"})
    assert refused.status_code == 403 and refused.json()["error"] == "Only local access is allowed."
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health", headers={"Host": "localhost:5173"}).status_code == 200  # the Vite dev proxy


def test_cross_origin_and_cross_site_writes_are_refused(client):
    body = {"name": "X"}
    assert client.post("/api/projects", json=body, headers={"Origin": "http://evil.example"}).status_code == 403
    assert client.post("/api/projects", json=body, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/projects", json=body, headers={"Origin": LOCAL}).status_code == 200


def test_an_allowed_host_name_is_opened_by_the_environment(client, monkeypatch):
    # read once when the app is built, so the shared rule is checked on a fresh guard
    from backend.hoard_link import guard

    allowed = guard.parse_allowed_hosts("pc2.example")
    assert guard.check_request("GET", {"host": "pc2.example"}, 8767, allowed) is None
    assert guard.check_request("GET", {"host": "pc3.example"}, 8767, allowed) is not None


def test_health_names_the_service_and_keeps_the_old_key(client):
    body = client.get("/api/health").json()
    assert body["service"] == "sculptors-hoard" and body["application"] == "sculptors-hoard" and body["ok"] is True


def test_saving_a_project_is_atomic(client, tmp_path, monkeypatch):
    pid = client.post("/api/projects", json={"name": "Escudo"}).json()["id"]
    path = tmp_path / pid / "project.json"
    before = path.read_text(encoding="utf-8")
    project = server.read(pid)
    project["name"] = "Otro"
    with monkeypatch.context() as broken:
        broken.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        with pytest.raises(OSError):
            server.save(project)
    assert path.read_text(encoding="utf-8") == before
    assert sorted(p.name for p in (tmp_path / pid).iterdir() if p.suffix in {".tmp", ".recovering"}) == []
    server.save(project)
    assert json.loads(path.read_text(encoding="utf-8"))["name"] == "Otro"


def project():
    return {
        "id": "test", "name": "Test", "revision": 1, "updated": 0, "history": [],
        "assets": [{"id": "a", "version": 1, "regions": [{"id": 0, "height": 104, "heightGroup": "eyes"}]}],
    }


def test_history_restore_writes_project_json_atomically(tmp_path):
    first = project()
    project_history.record(tmp_path, first)
    second = project()
    second["revision"] = 2
    second["name"] = "Segundo"
    project_history.record(tmp_path, second)
    restored = project_history.restore(tmp_path, second, "undo")
    assert restored["name"] == "Test"
    assert not [p for p in tmp_path.iterdir() if p.suffix in {".tmp", ".recovering", ".restoring"}]


def test_run_blender_logs_everything_and_returns_the_process(tmp_path):
    log = tmp_path / "run.log"
    code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"
    done = closed_loop.run_blender([sys.executable, "-c", code], log=log, timeout=30)
    assert done.returncode == 3
    text = log.read_text(encoding="utf-8")
    assert "out" in text and "err" in text


def test_run_blender_kills_a_run_that_times_out_and_keeps_its_output(tmp_path):
    log = tmp_path / "run.log"
    code = "import time; print('started', flush=True); time.sleep(60)"
    with pytest.raises(subprocess.TimeoutExpired):
        closed_loop.run_blender([sys.executable, "-c", code], log=log, timeout=2)
    assert "started" in log.read_text(encoding="utf-8")
