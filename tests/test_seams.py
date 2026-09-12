import json
import pytest
import numpy as np
from PIL import Image
from backend.seams import constrain


@pytest.mark.parametrize("target_role", ["skin", "pupil"])
def test_identified_feature_continues_across_uv_without_raising_whole_skin(tmp_path, target_role):
    scene = tmp_path / "scene"
    scene.mkdir()
    inventory = []
    for name in ["body", "face"]:
        source = tmp_path / (name + ".png")
        Image.new("RGB", (32, 32), (20, 40, 100)).save(source)
        inventory.append({"material": name, "source": str(source)})
        folder = tmp_path / "surfaces" / name
        folder.mkdir(parents=True)
        labels = np.zeros((32, 32), np.int16)
        if name == "body":
            labels[:16] = 1
        np.savez(folder / "masks.npz", labels=labels, centers=features([[20, 40, 100]]))
    (scene / "materials.json").write_text(json.dumps(inventory))
    pair = [{"material": "body", "uv": [0.5, 0.25]}, {"material": "face", "uv": [0.5, 0.25]}]
    (scene / "seams.json").write_text(json.dumps([pair, pair]))
    plans = {
        "body": [
            {
                "id": 0,
                "name": "Piel",
                "role": target_role,
                "cluster": 0,
                "height": 128,
                "area": 5,
                "heightGroup": "skin",
            },
            {
                "id": 1,
                "name": "Piel",
                "cluster": 0,
                "height": 128,
                "area": 90,
                "heightGroup": "skin",
            },
        ],
        "face": [
            {
                "id": 0,
                "name": "Mechón de pelo",
                "role": "hair",
                "semanticSource": "focused-inspection",
                "cluster": 0,
                "height": 160,
                "area": 5,
                "heightGroup": "hair",
            }
        ],
    }
    report = constrain(tmp_path, plans, apply=False)
    assert plans["body"][0]["height"] == 128 and report["changes"][0]["after"] == 160
    constrain(tmp_path, plans)
    assert plans["body"][0]["height"] == 160
    assert plans["body"][1]["height"] == 128
    assert (
        plans["body"][0]["heightGroup"]
        == plans["face"][0]["heightGroup"]
        != plans["body"][1]["heightGroup"]
    )


from backend.surface_plan import features


def test_only_matching_shared_edges_link_heights_and_preserve_unrelated_regions(tmp_path):
    scene = tmp_path / "scene"
    scene.mkdir()
    surfaces = tmp_path / "surfaces"
    surfaces.mkdir()
    inventory = []
    plans = {}
    for name, height in [("body", 128), ("eye", 110), ("unconnected", 190)]:
        source = tmp_path / f"{name}.png"
        Image.new("RGB", (32, 32), (20, 40, 100)).save(source)
        inventory.append({"material": name, "source": str(source)})
        folder = surfaces / name
        folder.mkdir()
        np.savez(
            folder / "masks.npz",
            labels=np.zeros((32, 32), np.int16),
            centers=features([[20, 40, 100]]),
        )
        plans[name] = [
            {"id": 0, "cluster": 0, "height": height, "area": 60 if name == "body" else 10}
        ]
    (scene / "materials.json").write_text(json.dumps(inventory))
    pair = [{"material": "body", "uv": [0.5, 0.5]}, {"material": "eye", "uv": [0.5, 0.5]}]
    (scene / "seams.json").write_text(json.dumps([pair, pair]))
    report = constrain(tmp_path, plans, apply=False)
    assert report["changes"] == [{"material": "eye", "class": 0, "before": 110, "after": 128}]
    assert plans["eye"][0]["height"] == 110
    constrain(tmp_path, plans)
    assert plans["eye"][0]["height"] == plans["body"][0]["height"] == 128
    assert plans["unconnected"][0]["height"] == 190 and "heightGroup" not in plans["unconnected"][0]


def test_no_boundary_data_is_explicitly_unavailable(tmp_path):
    assert constrain(tmp_path, {}) == {"available": False, "constraints": [], "changes": []}


def test_shared_color_links_only_the_spatial_region_at_the_seam(tmp_path):
    scene = tmp_path / "scene"
    scene.mkdir()
    inventory = []
    for name in ["nose", "eye"]:
        image = tmp_path / f"{name}.png"
        Image.new("RGB", (32, 32), (0, 0, 0)).save(image)
        inventory.append({"material": name, "source": str(image)})
        folder = tmp_path / "surfaces" / name
        folder.mkdir(parents=True)
        labels = np.zeros((32, 32), np.int16)
        if name == "eye":
            labels[:16] = 1
        np.savez(folder / "masks.npz", labels=labels, centers=features([[0, 0, 0]]))
    (scene / "materials.json").write_text(json.dumps(inventory))
    pair = [{"material": "nose", "uv": [0.5, 0.25]}, {"material": "eye", "uv": [0.5, 0.25]}]
    (scene / "seams.json").write_text(json.dumps([pair, pair]))
    plans = {
        "nose": [{"id": 0, "cluster": 0, "height": 95, "area": 50}],
        "eye": [
            {"id": 0, "cluster": 0, "height": 128, "area": 10},
            {"id": 1, "cluster": 0, "height": 64, "area": 10},
        ],
    }
    constrain(tmp_path, plans)
    assert plans["eye"][0]["height"] == 95
    assert plans["eye"][1]["height"] == 64
