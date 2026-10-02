"""gepetto.export.done: a finished evaluation with a figure-ready STL is announced for the model library."""


import pytest
from fastapi.testclient import TestClient

import backend.app as server
from backend import closed_loop, family_events

LOCAL = "http://127.0.0.1:8767"  # the shared request guard only accepts a loopback Host

STL = b"solid x\nendsolid x\n"


@pytest.fixture
def sent(monkeypatch):
    events = []
    monkeypatch.setattr(
        family_events.family,
        "emit",
        lambda kind, data=None, **kw: events.append((kind, data)) or True,
    )
    return events


def test_announce_emits_path_ref_and_title(tmp_path, sent):
    (tmp_path / "scene").mkdir()
    (tmp_path / "scene" / "figure-ready.stl").write_bytes(STL)
    payload = family_events.announce_evaluation(
        "Dragón", "abc123abc123", "job123job123", tmp_path / "scene"
    )
    assert sent == [("gepetto.export.done", payload)]
    assert payload["path"] == str((tmp_path / "scene" / "figure-ready.stl").resolve())
    assert (
        payload["ref"] == "hoard://gepetto/export/job123job123"
        and payload["title"] == "Dragón - relief"
        and payload["format"] == "stl"
    )


def test_announce_without_an_stl_does_nothing(tmp_path, sent):
    (tmp_path / "scene").mkdir()
    assert family_events.announce_evaluation("x", "p", "j", tmp_path / "scene") is None
    assert family_events.announce_evaluation("x", "p", "j", tmp_path / "missing") is None
    assert sent == []


def test_a_broken_hub_never_raises(tmp_path, monkeypatch):
    (tmp_path / "figure-ready.stl").write_bytes(STL)
    monkeypatch.setattr(family_events.family, "emit", lambda *a, **k: 1 / 0)
    assert family_events.announce_evaluation("x", "p", "j", tmp_path)["ref"].endswith("/j")


def test_configure_writes_the_token_once_and_names_the_app(tmp_path):
    token_file = family_events.configure(tmp_path)
    token = (tmp_path / "mcp-token").read_text()
    assert token_file == str(tmp_path / "mcp-token") and len(token) >= 32
    family_events.configure(tmp_path)
    assert (tmp_path / "mcp-token").read_text() == token
    assert family_events.family.health_block()["app"] == "gepetto"


def test_startup_writes_the_token_in_the_data_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    with TestClient(server.app, base_url=LOCAL):
        assert (tmp_path / "mcp-token").is_file()


def test_finished_evaluation_job_announces_its_stl(tmp_path, monkeypatch, sent):
    monkeypatch.setattr(server, "DATA", tmp_path)

    def fake_run(
        source, out, model, progress, corrections, separate, reuse, overrides, target=None
    ):
        scene = out / "scene"
        scene.mkdir(parents=True, exist_ok=True)
        (scene / "materials.json").write_text("[]")
        (scene / "figure-ready.stl").write_bytes(STL)
        return {
            "final": "ok",
            "aiAcceptable": True,
            "message": "listo",
            "plans": {},
            "iterations": [{"review": {}}],
            "hasFinished": True,
        }

    monkeypatch.setattr(closed_loop, "run", fake_run)
    with TestClient(server.app, base_url=LOCAL) as client:
        pid = client.post("/api/projects", json={"name": "Escudo"}).json()["id"]
        snapshot = server.read(pid)
        snapshot["blenderSource"] = {"file": "x.blend"}
        jid = "a1b2c3d4e5f6"
        server.jobs[jid] = {"id": jid, "project": pid, "kind": "evaluation", "status": "queued"}
        body = server.EvaluationRequest(model="m")
        server.evaluation_job(jid, pid, body, snapshot)
    assert server.jobs[jid]["status"] == "done", server.jobs[jid]
    assert len(sent) == 1 and sent[0][0] == "gepetto.export.done"
    data = sent[0][1]
    assert data["path"].endswith(f"{pid}/evaluations/{jid}/scene/figure-ready.stl")
    assert data["ref"] == f"hoard://gepetto/export/{jid}" and data["title"] == "Escudo - relief"


def test_evaluation_without_stl_emits_nothing(tmp_path, monkeypatch, sent):
    monkeypatch.setattr(server, "DATA", tmp_path)

    def fake_run(
        source, out, model, progress, corrections, separate, reuse, overrides, target=None
    ):
        (out / "scene").mkdir(parents=True, exist_ok=True)
        (out / "scene" / "materials.json").write_text("[]")
        return {
            "final": "ok",
            "aiAcceptable": True,
            "message": "listo",
            "plans": {},
            "iterations": [{"review": {}}],
        }

    monkeypatch.setattr(closed_loop, "run", fake_run)
    with TestClient(server.app, base_url=LOCAL) as client:
        pid = client.post("/api/projects", json={"name": "Sin STL"}).json()["id"]
        snapshot = server.read(pid)
        snapshot["blenderSource"] = {"file": "x.blend"}
        server.jobs["f" * 12] = {
            "id": "f" * 12,
            "project": pid,
            "kind": "evaluation",
            "status": "queued",
        }
        server.evaluation_job("f" * 12, pid, server.EvaluationRequest(model="m"), snapshot)
    assert server.jobs["f" * 12]["status"] == "done" and sent == []
