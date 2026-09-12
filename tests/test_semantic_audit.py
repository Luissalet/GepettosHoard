import json
import numpy as np
import pytest
from backend.semantic_audit import candidates
from backend.surface_plan import decode_assignments


def test_distinct_detail_is_audited_without_touching_same_color_in_another_group():
    labels = np.zeros((128, 128), np.int16)
    labels[20:40, 20:40] = 1
    labels[85:100, 85:100] = 2
    regions = [
        {"id": 0, "cluster": 0, "color": [150, 110, 80]},
        {"id": 1, "cluster": 1, "color": [10, 10, 10]},
        {"id": 2, "cluster": 1, "color": [10, 10, 10]},
    ]
    plan = {
        "surfaces": [
            {"name": "Superficie amplia", "classes": [0, 2]},
            {"name": "Pupila", "classes": [1]},
        ]
    }
    result = candidates(labels, regions, plan)
    assert len(result) == 1 and result[0]["classes"] == [2]


def test_semantics_without_heights_preserves_reason_and_avoids_ocular_analogy_on_beak():
    raw = {
        "description": "Partes físicas",
        "groups": [
            {
                "name": "Superficie del pico",
                "role": "sclera",
                "reason": "Superficie rosada del pico.",
            },
            {
                "name": "Fosas nasales",
                "role": "muzzle",
                "reason": "Dos aberturas pequeñas en la nariz.",
            },
            {
                "name": "Pestañas",
                "role": "eyelash",
                "reason": "Proyecciones en las esquinas de los ojos.",
            },
        ],
        "assignments": {"0": 0, "1": 1, "2": 2},
        "warnings": [],
    }
    plan = decode_assignments(json.dumps(raw), [0, 1, 2])
    assert [(r["role"], r["height"]) for r in plan["surfaces"]] == [
        ("beak", 128),
        ("nostril", 96),
        ("eyelash", 192),
    ]
    assert plan["surfaces"][2]["reason"] == raw["groups"][2]["reason"]
    assert all("modelHeight" not in r for r in plan["surfaces"])


def test_focused_audit_cannot_reinterpret_a_large_part_of_a_modeled_surface():
    labels = np.zeros((128, 128), np.int16)
    labels[:, :45] = 1
    regions = [
        {"id": 0, "cluster": 0, "color": [80, 20, 20]},
        {"id": 1, "cluster": 1, "color": [220, 100, 100]},
    ]
    plan = {"surfaces": [{"name": "Hocico", "classes": [0, 1]}]}
    assert not candidates(labels, regions, plan)


def test_small_detached_mouth_marks_request_visual_reinspection_without_setting_heights():
    labels = np.zeros((256, 256), np.int16)
    labels[50:62, 50:62] = 1
    labels[50:62, 90:102] = 2
    regions = [
        {"id": i, "cluster": 0 if i == 0 else 1, "color": [120, 70, 60] if i == 0 else [10, 10, 10]}
        for i in range(3)
    ]
    plan = {
        "surfaces": [
            {"name": "Piel", "role": "skin", "classes": [0]},
            {"name": "Boca", "role": "mouth", "classes": [1, 2]},
        ]
    }
    selected = candidates(labels, regions, plan)
    assert selected[0]["classes"] == [1, 2]
    assert "height" not in selected[0] and "role" not in selected[0]


@pytest.mark.parametrize("retry_finishes", [True, False])
def test_truncated_detail_check_retries_once_and_preserves_unresolved_heights(
    tmp_path, monkeypatch, retry_finishes
):
    import copy, httpx
    from PIL import Image
    from types import SimpleNamespace
    from backend import semantic_audit

    monkeypatch.setattr(
        semantic_audit,
        "candidates",
        lambda *args: [{"classes": [1], "color": [10, 10, 10], "parentName": "Skin"}],
    )
    requests = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json):
            requests.append(copy.deepcopy(json))
            done = len(requests) == 2 and retry_finishes
            group = {"name": "Pecas", "role": "freckle", "reason": "Pequeñas marcas de la mejilla."}
            return SimpleNamespace(
                is_success=True,
                json=lambda: {
                    "done_reason": "stop" if done else "length",
                    "message": {"content": __import__("json").dumps(group) if done else ""},
                },
            )

    monkeypatch.setattr(httpx, "Client", Client)
    original = {
        "description": "Skin",
        "surfaces": [{"classes": [1], "name": "Skin", "height": 128}],
        "warnings": [],
    }
    result = semantic_audit.audit(
        "test", Image.new("RGBA", (32, 32)), np.ones((32, 32), np.int16), [], original, tmp_path
    )
    assert len(requests) == 2
    assert requests[0]["messages"] == requests[1]["messages"]
    assert (tmp_path / "0/incomplete-attempt.json").is_file()
    assert result["surfaces"][0]["height"] == (176 if retry_finishes else 128)
    assert bool(result["warnings"]) != retry_finishes
    assert original["surfaces"][0]["height"] == 128 and not original["warnings"]
