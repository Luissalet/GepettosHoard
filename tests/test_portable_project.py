import json
import threading
import zipfile
import stat
import struct
from types import SimpleNamespace
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from backend.external_mcp import Store
from backend.portable_project import router_for, export_file, import_directory, unpack_file


def test_import_portable_route_preserves_masks_and_rejects_duplicates_and_paths(tmp_path, monkeypatch):
    import subprocess
    from backend import vision

    def forbidden(*args, **kwargs):
        raise AssertionError("No Blender, local model or background processing")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(vision, "analyze", forbidden)
    store = Store(str(tmp_path / "preparation"))
    image = tmp_path / "texture.png"
    Image.new("RGBA", (16, 16), (180, 200, 210, 255)).save(image)
    p = store.create("Portable figure")
    p = store.import_file(p["id"], str(image))
    aid = p["assets"][0]["id"]
    p = store.prepare(p["id"], aid, 2, 256)
    exported = tmp_path / "character" / "editable"
    store.export(p["id"], str(exported))
    # An untrusted supplied history DB is not copied into the app.
    (exported / "revisions" / "history.sqlite").write_bytes(b"untrusted history")
    library = tmp_path / "app-library"
    library.mkdir()
    app = FastAPI()
    app.include_router(router_for(SimpleNamespace(DATA=library, lock=threading.RLock())))
    client = TestClient(app)  # Minimal router only: no normal app/queue lifespan.
    response = client.post("/api/projects/import-portable", json={"path": str(exported)})
    assert response.status_code == 200, response.text
    assert response.json() == p
    saved = library / p["id"]
    assert (saved / f"{aid}.npz").read_bytes() == (exported / f"{aid}.npz").read_bytes()
    assert not (saved / "revisions").exists()
    before = (saved / "project.json").read_bytes()
    assert client.post("/api/projects/import-portable", json={"path": str(exported)}).status_code == 409
    assert (saved / "project.json").read_bytes() == before
    document = json.loads((exported / "project.json").read_text("utf-8"))
    document["assets"][0]["regions"][0]["height"] = 999
    (exported / "project.json").write_text(json.dumps(document), "utf-8")
    assert client.post("/api/projects/import-portable", json={"path": str(exported)}).status_code == 400
    document["assets"][0]["regions"][0]["height"] = 128
    document["assets"][0]["file"] = "../../outside.png"
    (exported / "project.json").write_text(json.dumps(document), "utf-8")
    assert client.post("/api/projects/import-portable", json={"path": str(exported)}).status_code == 400
    assert list(library.iterdir()) == [saved]


def test_gepettos_roundtrip_identity_and_no_overwrite(tmp_path):
    store = Store(str(tmp_path / "preparation"))
    image = tmp_path / "texture.png"
    Image.new("RGBA", (20, 16), (178, 168, 255, 93)).save(image)
    p = store.import_file(store.create("File figure")["id"], str(image))
    pid, aid = p["id"], p["assets"][0]["id"]
    p = store.prepare_anchors(pid, aid, [[178,168,255]], p["revision"], 256)
    destination = tmp_path / "figure.gepettos"
    result = export_file(store.folder(pid), destination)
    assert result["version"] == 1 and result["approved"] is False
    before = destination.read_bytes()
    with pytest.raises(FileExistsError):
        export_file(store.folder(pid), destination)
    assert destination.read_bytes() == before
    with zipfile.ZipFile(destination) as archive:
        assert "history.json" in archive.namelist()
        assert not any("sqlite" in n for n in archive.namelist())
    library = tmp_path / "library"
    library.mkdir()
    imported = import_directory(library, str(destination))
    assert imported == p
    for filename in (f"{aid}.npz", f"sources/{aid}.png"):
        assert (library / pid / filename).read_bytes() == (store.folder(pid) / filename).read_bytes()
    with pytest.raises(FileExistsError):
        import_directory(library, str(destination))
    assert not list(library.glob("gepettos-*"))


@pytest.mark.parametrize("kind", ["traversal", "symlink", "duplicate", "bomb", "version", "hash", "identity"])
def test_reject_invalid_gepettos_archives(tmp_path, kind):
    store = Store(str(tmp_path / "preparation"))
    p = store.create("Invalid archive fixture")
    valid = tmp_path / "valid.gepettos"
    export_file(store.folder(p["id"]), valid)
    with zipfile.ZipFile(valid) as archive:
        entries = {n: archive.read(n) for n in archive.namelist()}
    bad = tmp_path / "invalid.gepettos"
    if kind in {"version", "hash", "identity"}:
        manifest = json.loads(entries["manifest.json"])
        if kind == "version": manifest["version"] = 999
        elif kind == "identity": manifest["project_id"] = "a" * 12
        else: manifest["files"]["project.json"]["sha256"] = "0" * 64
        entries["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bad, "w") as archive:
        for name, raw in entries.items(): archive.writestr(name, raw)
        if kind == "traversal": archive.writestr("../outside.txt", b"bad")
        if kind == "duplicate":
            with pytest.warns(UserWarning): archive.writestr("project.json", entries["project.json"])
        if kind == "symlink":
            link = zipfile.ZipInfo("aaaaaaaaaa_preview.png")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "outside")
    if kind == "bomb":
        raw = bytearray(bad.read_bytes())
        central = raw.index(b"PK\x01\x02")
        struct.pack_into("<I", raw, central + 24, 3 * 1024**3)
        bad.write_bytes(raw)
    library = tmp_path / "library"
    library.mkdir()
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        import_directory(library, str(bad))
    assert list(library.iterdir()) == []
    assert not (tmp_path / "outside.txt").exists()


def test_manual_color_edit_route_without_app_queue():
    """Load only the actual edit route/models, avoiding the normal app lifespan."""
    import ast
    import copy
    import time
    from pathlib import Path
    from typing import Annotated
    from fastapi import HTTPException
    from pydantic import BaseModel, Field
    module = ast.parse((Path(__file__).resolve().parents[1] / "backend/app.py").read_text("utf-8"))
    selected = [n for n in module.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
                and n.name in {"RegionEdit", "EditRequest", "edit"}]
    app = FastAPI()
    document = {"revision": 2, "assets": [{"id": "asset", "version": 1,
                 "regions": [{"id": 0, "name": "Pupil", "height": 128,
                              "displacementColor": [178,168,255]}]}], "history": []}
    namespace = dict(app=app, BaseModel=BaseModel, Field=Field, Annotated=Annotated,
                     lock=threading.RLock(), HTTPException=HTTPException, time=time,
                     read=lambda pid: copy.deepcopy(document),
                     asset=lambda p, aid: p["assets"][0], invalidate=lambda p: None,
                     save=lambda p: document.update(p))
    exec(compile(ast.Module(body=selected, type_ignores=[]), "actual_edit_route", "exec"), namespace)
    client = TestClient(app)
    payload = {"revision": 2, "regions": [{"id": 0, "name": "Pupil", "height": 128,
                                         "displacementColor": [173,0,0]}]}
    result = client.patch("/api/projects/test/assets/asset", json=payload)
    assert result.status_code == 200, result.text
    assert document["assets"][0]["regions"][0]["displacementColor"] == [173,0,0]
    assert document["history"][-1]["changes"]
    payload["regions"][0]["height"] = 200
    assert client.patch("/api/projects/test/assets/asset", json=payload).status_code == 400
    payload["regions"][0]["height"] = 128
    payload["regions"][0]["displacementColor"] = [256,0,0]
    assert client.patch("/api/projects/test/assets/asset", json=payload).status_code == 422
