import io, zipfile, json
import pytest
from PIL import Image
from fastapi.testclient import TestClient
import backend.app as server


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    with TestClient(server.app) as c:
        yield c


def image_bytes():
    image = Image.new("RGBA", (128, 64), (60, 40, 180, 255))
    for x in range(64):
        for y in range(64):
            image.putpixel((x, y), (200, 130, 20, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def test_import_edit_export_persists_dimensions_and_approval_invalidates(client):
    p = client.post("/api/projects", json={"name": "Contract test"}).json()
    pid = p["id"]
    result = client.post(
        f"/api/projects/{pid}/import",
        files=[("files", ("../../body.png", image_bytes(), "image/png"))],
    )
    assert result.status_code == 200
    a = result.json()["project"]["assets"][0]
    assert a["name"] == "body.png"
    aid = a["id"]
    p = client.post(
        f"/api/projects/{pid}/assets/{aid}/segment", json={"clusters": 2, "resolution": 256}
    ).json()
    regions = p["assets"][0]["regions"]
    regions[0]["height"] = 200
    assert client.post(f"/api/projects/{pid}/approve").json()["approved"]
    p = client.patch(f"/api/projects/{pid}/assets/{aid}", json={"regions": regions}).json()
    assert not p["approved"]
    r = client.get(f"/api/projects/{pid}/export")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        manifest = json.loads(archive.read("sculptors-hoard-project.json"))
        assert manifest["textures"][0]["width"] == 128
        names = [n for n in archive.namelist() if n.endswith("_height.png")]
        with Image.open(io.BytesIO(archive.read(names[0]))) as image:
            assert image.size == (128, 64)
            assert 200 in {p[0] for p in image.getdata()}
    assert client.get(f"/api/projects/{pid}").json()["assets"][0]["regions"][0]["height"] == 200
    stale = client.patch(
        f"/api/projects/{pid}/assets/{aid}",
        json={"regions": regions, "revision": p["revision"] - 1},
    )
    assert stale.status_code == 409
    assert client.get(f"/api/projects/{pid}").json()["revision"] == p["revision"]


def test_invalid_inputs_and_external_origin_rejected(client):
    assert (
        client.post(
            "/api/projects", json={}, headers={"Origin": "https://unrelated.example"}
        ).status_code
        == 403
    )
    pid = client.post("/api/projects", json={}).json()["id"]
    result = client.post(
        f"/api/projects/{pid}/import", files=[("files", ("broken.png", b"not PNG", "image/png"))]
    ).json()
    assert result["errors"] and not result["project"]["assets"]
    assert client.get(f"/api/projects/{pid}/export").status_code == 400
    assert client.get("/api/projects/not-a-project").status_code == 404
    assert client.post(f"/api/projects/{pid}/apply", json={"relations": []}).status_code == 409
