from fastapi.testclient import TestClient
from backend import app as server


def test_contrast_preserves_order_reference_and_is_undoable(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    p = server.create(server.NewProject(name="Contrast"))
    p["assets"] = [
        {
            "id": "a",
            "version": 1,
            "approved": False,
            "regions": [
                {"id": i, "height": height} for i, height in enumerate([64, 104, 128, 160, 192])
            ],
        }
    ]
    server.save(p)
    client = TestClient(server.app)
    base = f"/api/projects/{p['id']}"
    response = client.post(base + "/contrast", json={"factor": 1.5, "revision": p["revision"]})
    assert response.status_code == 200
    result = response.json()
    assert [r["height"] for r in result["assets"][0]["regions"]] == [32, 92, 128, 176, 224]
    assert (
        client.post(
            base + "/contrast", json={"factor": 2, "revision": result["revision"]}
        ).status_code
        == 400
    )
    assert (
        client.post(base + "/contrast", json={"factor": 1.2, "revision": p["revision"]}).status_code
        == 409
    )
    restored = client.post(base + "/restore", json={"direction": "undo"}).json()
    assert [r["height"] for r in restored["assets"][0]["regions"]] == [64, 104, 128, 160, 192]
    assert client.get(base + "/history").json()["canRedo"]
