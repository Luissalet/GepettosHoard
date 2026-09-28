import asyncio
import json
from pathlib import Path
import subprocess
import sys
from io import BytesIO

import httpx
import numpy as np
import pytest
from PIL import Image
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.external_mcp import Store


def test_cpu_project_roundtrip_and_atomic_validation(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Local inference/network/Blender forbidden")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(httpx.Client, "request", forbidden)
    store = Store(str(tmp_path / "isolated"))
    image = tmp_path / "test.png"
    Image.new("RGBA", (32, 32), (240, 230, 200, 255)).save(image)
    original = image.read_bytes()
    p = store.create("Synthetic figure")
    pid = p["id"]
    p = store.import_file(pid, str(image))
    aid = p["assets"][0]["id"]
    p = store.prepare(pid, aid, 2, 256)
    plan = {
        "revision": p["revision"], "author": "test external reasoner",
        "evidence": ["synthetic fixture"], "explanation": "Explicit height policy",
        "regions": [dict(key=f"{aid}:{r['id']}", name="Surface", reason="Fixture",
                         confidence=1.0, geometry="unknown", height=128)
                    for r in p["assets"][0]["regions"]],
        "operations": [{"action": "merge", "targets": [f"{aid}:0"], "name": "Surface"}],
    }
    before = (store.folder(pid) / "project.json").read_bytes()
    bad = json.loads(json.dumps(plan))
    bad["regions"][0]["height"] = 999
    with pytest.raises(ValueError):
        store.apply(pid, bad)
    assert (store.folder(pid) / "project.json").read_bytes() == before
    bad = json.loads(json.dumps(plan))
    bad["operations"][0]["targets"] = ["does-not-exist:0"]
    with pytest.raises(ValueError):
        store.apply(pid, bad)
    assert (store.folder(pid) / "project.json").read_bytes() == before
    p = store.apply(pid, plan)
    assert p["assets"][0]["regions"][0]["semanticGroup"]
    with pytest.raises(ValueError, match="Revision"):
        store.apply(pid, plan)
    assert image.read_bytes() == original
    assert (store.folder(pid) / "sources" / p["assets"][0]["file"]).read_bytes() == original
    assert store.evidence(pid, aid, "ids").startswith(b"\x89PNG")
    output = tmp_path / "figure" / "editable"
    store.export(pid, str(output))
    assert Store.inspect_directory(str(output)) == p
    assert (output / "revisions" / "history.sqlite").is_file()
    with pytest.raises(ValueError, match="Destination"):
        store.export(pid, str(output))
    blend = tmp_path / "no.blend"
    blend.write_bytes(b"fake")
    with pytest.raises(ValueError, match="no Blender"):
        store.import_file(pid, str(blend))


def test_default_data_forbidden():
    with pytest.raises(ValueError, match="default data"):
        Store(str(Path(__file__).resolve().parents[1] / "data"))


def test_official_mcp_stdio_roundtrip(tmp_path):
    async def run():
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "backend.external_mcp", "--data-dir", str(tmp_path / "mcp")],
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert names == {"create_project", "import_source", "segment_texture",
                                 "read_project", "image_evidence", "apply_semantic_plan",
                                 "export_editable_project", "inspect_editable_directory",
                                 "export_manual_palette_maps", "segment_texture_with_anchors",
                                 "split_region_polygon", "export_project_file"}
                result = await session.call_tool("create_project", {"name": "MCP roundtrip"})
                assert not result.isError
                project = json.loads(result.content[0].text)
                result = await session.call_tool("read_project", {"project_id": project["id"]})
                assert not result.isError
                assert json.loads(result.content[0].text)["name"] == "MCP roundtrip"
                exported = await session.call_tool("export_project_file", {
                    "project_id": project["id"], "destination": str(tmp_path / "roundtrip.gepettos")})
                assert not exported.isError, exported
                assert (tmp_path / "roundtrip.gepettos").is_file()
    asyncio.run(run())


def test_anchor_palette_native_alpha_resume_and_failure(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "library"))
    pixels = np.zeros((270, 300, 4), np.uint8)
    pixels[:] = (220, 200, 30, 255)
    pixels[:, 150:] = (10, 30, 40, 83)
    pixels[10, 10] = (10, 30, 40, 255)  # tiny island must retain its own anchor
    pixels[0, :, 3] = 0
    source = tmp_path / "original.png"
    Image.fromarray(pixels).save(source)
    original = source.read_bytes()
    p = store.import_file(store.create("Palette test")["id"], str(source))
    pid, aid = p["id"], p["assets"][0]["id"]
    p = store.prepare_anchors(pid, aid, [[220, 200, 30], [10, 30, 40]], p["revision"], 512)
    with np.load(store.folder(pid) / f"{aid}.npz") as masks:
        regions = p["assets"][0]["regions"]
        lookup = {r["id"]: r["cluster"] for r in regions}
        assert lookup[int(masks["labels"][10, 10])] == 1
        assert lookup[int(masks["labels"][10, 11])] == 0
    with pytest.raises(ValueError, match="Revision"):
        store.prepare_anchors(pid, aid, [[0, 0, 0]], 0, 512)
    output = tmp_path / "maps"
    with pytest.raises(ValueError, match="displacementColor"):
        store.export_manual_palette(pid, str(output))
    assert not output.exists()
    colors = [[178, 168, 255], [173, 0, 0]]
    plan = {"revision": p["revision"], "author": "test", "evidence": ["fixture"],
            "explanation": "Manual palette", "regions": [
                dict(key=f"{aid}:{r['id']}", name="Color region", reason="Fixture",
                     confidence=1.0, geometry="unknown", height=128,
                     displacementColor=colors[r["cluster"]]) for r in regions]}
    for invalid in ([0, 256, 1], [0, True, 1], [0, 1.5, 1], [0, 1]):
        bad = json.loads(json.dumps(plan))
        bad["regions"][0]["displacementColor"] = invalid
        with pytest.raises(ValueError):
            store.apply(pid, bad)
    p = store.apply(pid, plan)
    with pytest.raises(ValueError, match="semantic plan"):
        store.prepare_anchors(pid, aid, [[0, 0, 0]], p["revision"], 512)
    preview = Image.open(BytesIO(store.evidence(pid, aid, "manual-palette")))
    assert preview.getpixel((10, 10))[:3] == tuple(colors[1])
    assert Image.open(BytesIO(store.evidence(pid, aid, "color"))).getpixel((10, 10))[:3] == tuple(colors[1])
    # Failure after file creation must leave destination absent and allow retry.
    import backend.external_mcp as module
    real_writer = module.write_manual_palette
    def interrupted(*args):
        real_writer(*args)
        raise OSError("fixture interruption")
    monkeypatch.setattr(module, "write_manual_palette", interrupted)
    with pytest.raises(OSError, match="interruption"):
        store.export_manual_palette(pid, str(output))
    assert not output.exists()
    assert not list(tmp_path.glob(".manual-palette-*"))
    monkeypatch.setattr(module, "write_manual_palette", real_writer)
    store = Store(str(tmp_path / "library"))  # fresh process-equivalent resume
    result = store.export_manual_palette(pid, str(output))
    manifest = json.loads(Path(result["manifest"]).read_text("utf-8"))
    exported = Image.open(output / manifest["textures"][0]["file"])
    assert exported.size == (300, 270)
    out = np.asarray(exported)
    assert np.array_equal(out[..., 3], pixels[..., 3])
    assert tuple(out[10, 10, :3]) == tuple(colors[1])
    assert tuple(out[10, 11, :3]) == tuple(colors[0])
    assert tuple(out[20, 220, :3]) == tuple(colors[1])
    assert source.read_bytes() == original
    before = (output / "manual-palette.json").read_bytes()
    with pytest.raises(ValueError, match="Destination"):
        store.export_manual_palette(pid, str(output))
    assert (output / "manual-palette.json").read_bytes() == before


def test_uniform_anchor(tmp_path):
    from backend.processing import segment_with_anchors
    labels, regions, _, centers = segment_with_anchors(
        Image.new("RGBA", (16, 16), (1, 2, 3, 255)), [[1, 2, 3]], 256)
    assert len(regions) == 1 and np.all(labels == 0) and centers.shape == (1, 3)


def test_polygon_split_same_color_and_invalid_no_mutation(tmp_path):
    store = Store(str(tmp_path / "library"))
    source = tmp_path / "eye.png"
    Image.new("RGBA", (32, 32), (0, 0, 0, 255)).save(source)
    p = store.import_file(store.create("Eye")["id"], str(source))
    pid, aid = p["id"], p["assets"][0]["id"]
    p = store.prepare_anchors(pid, aid, [[0, 0, 0]], p["revision"], 256)
    mask_path = store.folder(pid) / f"{aid}.npz"
    before = mask_path.read_bytes()
    with pytest.raises(ValueError, match="proper subset"):
        store.split_polygon(pid, aid, 0, [[0,0], [1,0], [1,1], [0,1]], p["revision"])
    assert mask_path.read_bytes() == before
    p = store.split_polygon(pid, aid, 0, [[0,0], [.4,0], [.4,1], [0,1]], p["revision"])
    assert [r["cluster"] for r in p["assets"][0]["regions"]] == [0, 0]
    with np.load(mask_path) as masks:
        assert masks["labels"][15, 1] == 1
        assert masks["labels"][15, 30] == 0
    with pytest.raises(ValueError, match="Revision"):
        store.split_polygon(pid, aid, 0, [[0,0], [.5,0], [0,.5]], p["revision"] - 1)


def test_split_reviewed_project_preserves_semantics_and_invalidates_approval(tmp_path):
    store = Store(str(tmp_path / 'library'))
    source = tmp_path / 'source.png'
    Image.new('RGBA', (32, 32), (40, 60, 80, 255)).save(source)
    p = store.import_file(store.create('Review')['id'], str(source))
    pid, aid = p['id'], p['assets'][0]['id']
    p = store.prepare_anchors(pid, aid, [[40, 60, 80]], p['revision'], 256)
    p = store.apply(pid, dict(revision=p['revision'], author='reviewer', evidence=['visual review'],
        explanation='Reviewed surface', regions=[dict(key=f'{aid}:0',name='Surface',height=176,
        displacementColor=[255,207,207],reason='visible surface',confidence=.8,geometry='unknown')]))
    p['approved'] = True
    store.save(p)
    p = store.split_polygon(pid, aid, 0, [[0,0],[.4,0],[.4,1],[0,1]],p['revision'])
    assert p['approved'] is False
    assert len(p['assets'][0]['regions']) == 2
    assert all(r['displacementColor'] == [255,207,207] and r['height'] == 176 for r in p['assets'][0]['regions'])
    assert any(e['type']=='external-plan' for e in p['history'])
