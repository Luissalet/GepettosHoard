import json
import numpy as np
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
