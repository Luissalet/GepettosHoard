import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

import backend.app as server
import backend.blend_import as importer


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path / "data")
    server.DATA.mkdir()
    executable = tmp_path / "blender.exe"
    executable.touch()
    monkeypatch.setattr(importer, "BLENDER", executable)
    project = server.create(server.NewProject(name="Before import"))
    return project


def successful_worker(args, **kwargs):
    config = json.loads(Path(args[-1]).read_text())
    out = Path(config["output"])
    image = out / "assigned.png"
    Image.new("RGB", (96, 48), (30, 110, 190)).save(image)
    (out / "preview.glb").write_bytes(b"fixture glb")
    (out / "prepared.blend").write_bytes(b"fixture blend")
    (out / "import-report.json").write_text(
        json.dumps(
            {
                "objects": ["Body and clothing"],
                "warnings": [],
                "seconds": 0.1,
                "textures": [
                    {
                        "path": str(image),
                        "material": "Shirt",
                        "name": "shirt.png",
                        "originalPath": "//upscaled_chain/shirt.png",
                    }
                ],
            }
        )
    )
    return SimpleNamespace(returncode=0)


def test_blend_replaces_inventory_in_one_undoable_change(setup, monkeypatch):
    pid = setup["id"]
    server.ingest(pid, "old.dae", b"old preview")
    before = server.read(pid)
    monkeypatch.setattr(importer.subprocess, "run", successful_worker)
    result = importer.import_blend(server, pid, "Figure.blend", b"BLENDER")
    assert result["revision"] == before["revision"] + 1
    assert len(result["models"]) == len(result["assets"]) == 1
    asset = result["assets"][0]
    assert (asset["width"], asset["height"], asset["material"]) == (96, 48, "Shirt")
    assert asset["sourcePath"] == "//upscaled_chain/shirt.png"
    assert result["blenderSource"]["file"].endswith("/prepared.blend")
    from backend.project_history import restore

    restored = restore(server.folder(pid), result, "undo", None)
    assert restored["models"] == before["models"]
    assert restored["assets"] == before["assets"]


def test_missing_applied_texture_keeps_existing_project_intact(setup, monkeypatch):
    before = server.read(setup["id"])

    def failed(args, **kwargs):
        out = Path(json.loads(Path(args[-1]).read_text())["output"])
        (out / "import-report.json").write_text(
            json.dumps({"error": "Falta la textura aplicada: //upscaled_chain/body.png"})
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(importer.subprocess, "run", failed)
    with pytest.raises(HTTPException, match="Falta la textura aplicada"):
        importer.import_blend(server, setup["id"], "Figure.blend", b"BLENDER")
    assert server.read(setup["id"]) == before


def test_concurrent_edit_is_not_overwritten(setup, monkeypatch):
    def edited(args, **kwargs):
        successful_worker(args, **kwargs)
        changed = server.read(setup["id"])
        changed["name"] = "User edit"
        server.invalidate(changed)
        server.save(changed)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(importer.subprocess, "run", edited)
    with pytest.raises(HTTPException) as error:
        importer.import_blend(server, setup["id"], "Figure.blend", b"BLENDER")
    assert error.value.status_code == 409
    assert server.read(setup["id"])["name"] == "User edit"


def test_direct_upload_prefers_blend_over_loose_dae_and_textures(setup, monkeypatch):
    seen = []

    def extract(api, pid, name, content):
        seen.append((name, content))
        return api.read(pid) | {"blendImport": {"warnings": []}}

    monkeypatch.setattr(importer, "import_blend", extract)
    with TestClient(server.app) as client:
        result = client.post(
            f"/api/projects/{setup['id']}/import",
            files=[
                ("files", ("old.dae", b"old")),
                ("files", ("Figure.blend", b"BLENDER")),
                ("files", ("lowres.png", b"not a valid image")),
            ],
        )
    assert result.status_code == 200
    assert seen == [("Figure.blend", b"BLENDER")]
    assert server.read(setup["id"])["models"] == []


def test_desktop_path_opens_original_location_for_relative_images(setup, tmp_path, monkeypatch):
    source = tmp_path / "character" / "Figure.blend"
    source.parent.mkdir()
    source.write_bytes(b"BLENDER")

    def extract(api, pid, name, content, source_path=None):
        assert source_path == source.resolve()
        assert content == b"BLENDER"
        return api.read(pid)

    monkeypatch.setattr(importer, "import_blend", extract)
    with TestClient(server.app) as client:
        response = client.post(
            f"/api/projects/{setup['id']}/import-blender-path", json={"path": str(source)}
        )
    assert response.status_code == 200
