from backend.batch import Queue


def test_queue_recovers_interruption_and_deduplicates_pending_sources(tmp_path):
    source = tmp_path / "figure.blend"
    source.write_bytes(b"fixture")
    q = Queue(tmp_path / "queue")
    q.add([str(source), str(source)], "vision", "complete")
    state = q.state()
    assert len(state["items"]) == 1 and state["paused"]
    jid = state["items"][0]["id"]
    q.control("resume")
    with q.db() as db:
        db.execute("UPDATE queue SET state='running' WHERE id=?", (jid,))
    recovered = Queue(tmp_path / "queue")
    recovered.recover()
    assert recovered.state()["paused"]
    assert recovered.state()["items"][0]["state"] == "interrupted"
    recovered.control("retry", jid)
    assert recovered.state()["items"][0]["state"] == "queued"
    recovered.control("cancel", jid)
    assert recovered.state()["items"][0]["state"] == "cancelled"


def test_batch_validates_all_paths_before_enqueuing(tmp_path):
    source = tmp_path / "figure.blend"
    source.write_bytes(b"fixture")
    q = Queue(tmp_path / "queue")
    import pytest

    with pytest.raises(ValueError):
        q.add([str(source), str(tmp_path / "missing.blend")], "vision", "complete")
    assert not q.state()["items"]


def test_retry_reuses_completed_phase_without_moving_its_files(tmp_path, monkeypatch):
    import json, threading
    from types import SimpleNamespace
    from backend import closed_loop, assembly
    from scripts import import_evaluation

    source = tmp_path / "figure.blend"
    source.write_bytes(b"fixture")
    q = Queue(tmp_path / "queue")
    item = q.add([str(source)], "vision", "complete")["items"][0]
    calls = []

    def result(out):
        out.mkdir(parents=True, exist_ok=True)
        texture = out / "map.png"
        texture.write_bytes(b"map")
        (out / "result.json").write_text(json.dumps({"maps": {"mBody": str(texture)}}))

    def run(source, out, model, progress, **kwargs):
        label = "clothing" if kwargs.get("target") else "body"
        calls.append(label)
        if label == "clothing" and calls.count(label) == 1:
            raise RuntimeError("Simulated interruption")
        result(out)

    def assemble(body, garment, out, progress, **kwargs):
        calls.append("assembly")
        assert (body / "map.png").exists()
        result(out)

    monkeypatch.setattr(closed_loop, "run", run)
    monkeypatch.setattr(assembly, "assemble", assemble)
    monkeypatch.setattr(import_evaluation, "import_run", lambda *args, **kwargs: {"id": "project"})
    server = SimpleNamespace(
        lock=threading.RLock(), NewProject=lambda **x: x, create=lambda x: {"id": "project"}
    )
    q.process(item, server)
    assert q.state()["items"][0]["state"] == "error"
    q.control("retry", item["id"])
    item["attempt"] = 1
    q.process(item, server)
    assert q.state()["items"][0]["state"] == "done"
    assert calls == ["body", "clothing", "clothing", "assembly"]
    assert (q.root / item["id"] / "body-attempt-1" / "map.png").exists()
