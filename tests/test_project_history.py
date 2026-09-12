import copy
import numpy as np
from backend import project_history as history


def project():
    return {
        "id": "test",
        "name": "Test",
        "revision": 1,
        "updated": 0,
        "history": [],
        "assets": [
            {"id": "a", "version": 1, "regions": [{"id": 0, "height": 104, "heightGroup": "eyes"}]},
            {"id": "b", "version": 1, "regions": [{"id": 0, "height": 104, "heightGroup": "eyes"}]},
        ],
    }


def test_undo_redo_survive_reopening_and_restore_masks_and_linked_edits(tmp_path):
    p = project()
    np.savez(tmp_path / "a.npz", labels=[1, 2])
    history.record(tmp_path, p)
    q = copy.deepcopy(p)
    q["revision"] = 2
    for a in q["assets"]:
        a["regions"][0]["height"] = 80
    np.savez(tmp_path / "a.npz", labels=[9, 8])
    history.record(tmp_path, q)
    restored = history.restore(tmp_path, q, "undo")
    assert [a["regions"][0]["height"] for a in restored["assets"]] == [104, 104]
    assert np.load(tmp_path / "a.npz")["labels"].tolist() == [1, 2]
    history.record(tmp_path, restored)
    assert history.status(tmp_path)["canRedo"]
    redone = history.restore(tmp_path, restored, "redo")
    assert [a["regions"][0]["height"] for a in redone["assets"]] == [80, 80]
    assert np.load(tmp_path / "a.npz")["labels"].tolist() == [9, 8]
    assert redone["revision"] > restored["revision"]


def test_new_branch_clears_redo_but_keeps_named_checkpoint(tmp_path):
    p = project()
    history.record(tmp_path, p)
    history.bookmark(tmp_path, "Original")
    q = copy.deepcopy(p)
    q["assets"][0]["regions"][0]["height"] = 64
    history.record(tmp_path, q)
    undone = history.restore(tmp_path, q, "undo")
    undone["name"] = "Nueva rama"
    history.record(tmp_path, undone)
    assert not history.status(tmp_path)["canRedo"]
    checkpoint = history.status(tmp_path)["checkpoints"][0]["id"]
    restored = history.restore(tmp_path, undone, checkpoint=checkpoint)
    assert restored["name"] == "Test"


def test_restored_evaluation_stays_current_without_destroying_redo(tmp_path):
    p = project()
    p["evaluation"] = {"id": "evaluation", "revision": 1}
    history.record(tmp_path, p)
    q = copy.deepcopy(p)
    q["revision"] = 2
    q["assets"][0]["regions"][0]["height"] = 64
    history.record(tmp_path, q)
    restored = history.restore(tmp_path, q, "undo")
    assert restored["evaluation"]["revision"] == restored["revision"]
    history.record(tmp_path, restored)
    assert history.status(tmp_path)["canRedo"]


def test_restart_recovers_last_committed_document_and_masks_after_partial_publish(tmp_path):
    import json

    p = project()
    np.savez(tmp_path / "a.npz", labels=[1, 2])
    history.record(tmp_path, p)
    (tmp_path / "project.json").write_text("{incomplete publish")
    np.savez(tmp_path / "a.npz", labels=[8, 9])
    assert history.recover_published_files(tmp_path)
    assert json.loads((tmp_path / "project.json").read_text("utf-8")) == p
    assert np.load(tmp_path / "a.npz")["labels"].tolist() == [1, 2]
    assert not history.recover_published_files(tmp_path)
    q = copy.deepcopy(p)
    q["revision"] = 2
    q["assets"][0]["regions"][0]["height"] = 80
    history.record(tmp_path, q)
    restored = history.restore(tmp_path, q, "undo")
    (tmp_path / "project.json").unlink()
    assert history.recover_published_files(tmp_path)
    assert json.loads((tmp_path / "project.json").read_text("utf-8")) == restored
    assert history.status(tmp_path)["canRedo"]
