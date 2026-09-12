import numpy as np
import pytest
from backend.active_views import choose_view, hidden_features, split_physical_groups


def test_choose_view_sees_an_underside_that_front_cannot_expose():
    # Opaque top plane covers a marked bottom plane viewed from above/front.
    uv = [[[0, 0], [1, 0], [0, 1]], [[1, 0], [1, 1], [0, 1]]]
    bottom = [[[-1, -1, -1], [1, -1, -1], [-1, 1, -1]], [[1, -1, -1], [1, 1, -1], [-1, 1, -1]]]
    top = [[[x, y, 1] for x, y, z in triangle] for triangle in bottom]
    inventory = [
        {"material": "sole", "triangles": uv, "world_triangles": bottom},
        {"material": "cover", "triangles": uv, "world_triangles": top},
    ]
    name, scores = choose_view(
        inventory, "sole", np.full((16, 16), 3, np.int16), {"center": [0, 0, 0], "size": 3}, [3]
    )
    assert name in {"below", "lower-front"} and scores[name] > scores["front"]


def test_hidden_specific_features_need_evidence_but_visible_or_plain_skin_do_not():
    rows = [
        {"id": 1, "frontImageBox": None, "modelBounds": {"min": [0, 0, -0.5]}},
        {"id": 2, "frontImageBox": [0.1, 0.1, 0.2, 0.2], "modelBounds": {}},
    ]
    plan = {"surfaces": [{"classes": [1, 2], "role": "eyelid", "name": "Eyelid"}]}
    assert hidden_features(rows, plan)[0]["classes"] == [1]
    plan["surfaces"][0]["role"] = "skin"
    assert hidden_features(rows, plan) == []


def test_front_anchor_uses_true_world_location_for_hidden_uv_surface():
    from PIL import Image
    from backend.active_views import anchor_view

    item = {
        "triangles": [[[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]],
        "world_triangles": [[[-1.0, 0.0, -1.0], [1.0, 0.0, -1.0], [0.0, 1.0, -1.0]]],
    }
    image, positions = anchor_view(
        Image.new("RGB", (256, 256)),
        item,
        np.full((16, 16), 3, np.int16),
        {"center": [0, 0, 0], "size": 2},
        [3],
    )
    assert image.size == (256, 256)
    assert positions[0]["id"] == 3 and positions[0]["normalizedZ"] == 0
    assert positions[0]["worldCenter"][2] == -1


def test_same_color_on_arms_and_legs_is_not_forced_into_one_identity():
    centers = {
        1: [-0.3, 0.1, -0.1],
        2: [0.3, 0.1, -0.1],
        3: [-0.05, 0.1, -0.35],
        4: [0.05, 0.1, -0.35],
    }
    rows = {rid: {"modelBounds": {"min": center, "max": center}} for rid, center in centers.items()}
    checks = [{"classes": [1, 2, 3, 4], "hypothesis": "Same painted color"}]
    groups = split_physical_groups(checks, rows)
    assert [g["classes"] for g in groups] == [[1, 2], [3, 4]]
    assert all("role" not in g and "height" not in g for g in groups)
    assert checks[0]["classes"] == [1, 2, 3, 4]


@pytest.mark.parametrize("extra_hidden", [False, True])
def test_invisible_geometry_does_not_consume_the_model_inspection_budget(
    tmp_path, monkeypatch, extra_hidden
):
    import json, httpx
    from PIL import Image
    from types import SimpleNamespace
    from backend import active_views

    image = Image.new("RGB", (32, 32), "white")
    image.save(tmp_path / "original-front.png")
    (tmp_path / "prepare-report.json").write_text(
        json.dumps({"geometry": {"center": [0, 0, 0], "size": 2}})
    )
    monkeypatch.setattr(
        active_views,
        "hidden_features",
        lambda *a: [
            {"classes": [1], "hypothesis": "old"},
            {"classes": [2, 3] if extra_hidden else [2], "hypothesis": "old"},
        ],
    )
    monkeypatch.setattr(
        active_views,
        "inspect_view",
        lambda *a: (
            None
            if a[-2] == [1]
            else {"view": "lower-front", "image": image, "control": image, "visible": [2]}
        ),
    )
    monkeypatch.setattr(active_views, "anchor_view", lambda *a: (image, []))
    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, url, json):
            calls.append(json)
            payload = {
                "name": "Pies",
                "role": "modeled",
                "scenePart": "legs",
                "reason": "Extremos de las piernas.",
            }
            return SimpleNamespace(
                is_success=True,
                json=lambda: {
                    "done_reason": "stop",
                    "message": {"content": __import__("json").dumps(payload)},
                },
            )

    monkeypatch.setattr(httpx, "Client", Client)
    plan = {
        "surfaces": [
            {
                "classes": [1, 2, 3] if extra_hidden else [1, 2],
                "name": "Previous",
                "role": "eyelid",
                "height": 160,
            }
        ],
        "warnings": [],
    }
    result = active_views.audit_hidden(
        "test",
        tmp_path,
        {},
        [],
        np.zeros((2, 2)),
        [],
        plan,
        {"parts": [{"key": "legs"}]},
        tmp_path / "evidence",
        limit=1,
    )
    assert len(calls) == 1
    assert result["surfaces"][0]["classes"] == ([1, 3] if extra_hidden else [1])
    assert result["surfaces"][1]["classes"] == [2] and result["surfaces"][1]["height"] == 128
    assert plan["surfaces"][0]["classes"] == ([1, 2, 3] if extra_hidden else [1, 2])
