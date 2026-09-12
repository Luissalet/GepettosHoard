import json
import pytest
from backend.surface_plan import decode_assignments


def payload(assignments):
    return json.dumps(
        {
            "description": "Test",
            "groups": [
                {"name": "Piel", "height": 128, "reason": "Base"},
                {"name": "Ojos", "height": 80, "reason": "Detalle"},
            ],
            "assignments": assignments,
            "warnings": [],
        }
    )


def test_assignment_keys_guarantee_no_lost_or_duplicate_palette_classes():
    p = decode_assignments(payload({"0": 0, "1": 1, "2": 0}), [0, 1, 2])
    assert p["surfaces"][0]["classes"] == [0, 2] and p["surfaces"][1]["classes"] == [1]
    with pytest.raises(ValueError):
        decode_assignments(payload({"0": 0}), [0, 1])
    with pytest.raises(ValueError):
        decode_assignments(payload({"0": 0, "1": 4}), [0, 1])


def test_anatomy_second_look_recovers_layers_without_flattening_nose_or_pupils():
    from backend.surface_plan import needs_anatomy_audit, merge_anatomy_audit

    def group(name, height, ids):
        return {"name": name, "height": height, "classes": ids, "reason": "Test"}

    initial = {
        "surfaces": [
            group("Esclera", 64, [0]),
            group("Pupila", 104, [1]),
            group("Fosas nasales", 95, [2]),
            group("Iris", 84, [3]),
            group("Piel", 128, [4, 5]),
        ]
    }
    audit = {
        "surfaces": [
            group("Párpado", 160, [3]),
            group("Pestañas", 192, [4]),
            group("Piel", 128, [0, 1, 2, 5]),
        ]
    }
    assert needs_anatomy_audit(initial)
    final = merge_anatomy_audit(initial, audit)
    levels = {rid: s["height"] for s in final["surfaces"] for rid in s["classes"]}
    assert levels == {0: 64, 1: 104, 2: 95, 3: 160, 4: 192, 5: 128}
    assert len([rid for s in final["surfaces"] for rid in s["classes"]]) == 6
    assert not needs_anatomy_audit(final)
    assert initial["surfaces"][-1]["classes"] == [4, 5]


def test_compact_review_retains_all_materials_regions_heights_and_locations():
    from backend.surface_plan import compact_inventory

    regions = [
        {
            "id": i,
            "name": "Long shared surface name",
            "height": 128,
            "color": [10, 20, 30],
            "modelBounds": {"min": [0, 0, 0], "max": [1, 2, 3]},
            "reason": "A long repeated semantic reason.",
        }
        for i in range(64)
    ]
    plans = {"mBody": regions, "mEye": regions}
    compact = compact_inventory(plans)
    assert set(compact) == set(plans)
    for material, entry in compact.items():
        assert [r[0] for r in entry["regions"]] == list(range(64))
        assert all(
            entry["surfaces"][r[1]] == {"name": regions[0]["name"], "height": 128}
            and r[2:] == [[10, 20, 30], [0.5, 1.0, 1.5]]
            for r in entry["regions"]
        )
    assert len(json.dumps(compact)) < len(json.dumps(plans)) * 0.35


def test_resume_rejects_changed_or_missing_external_texture(tmp_path):
    from backend.closed_loop import source_signatures, validate_sources, write

    texture = tmp_path / "texture.png"
    texture.write_bytes(b"original")
    write(tmp_path / "source-signatures.json", source_signatures([{"source": str(texture)}]))
    validate_sources(tmp_path)
    texture.write_bytes(b"new texture contents")
    with pytest.raises(ValueError, match="han cambiado"):
        validate_sources(tmp_path)
    texture.unlink()
    with pytest.raises(ValueError, match="Falta"):
        validate_sources(tmp_path)


def test_artist_policy_follows_semantic_role_not_suggested_rgb_depth():
    roles = ["sclera", "iris", "pupil", "skin", "eyelid", "eyelash", "freckle", "modeled"]
    raw = {
        "description": "Test",
        "groups": [{"name": role, "height": 96, "reason": "Test", "role": role} for role in roles],
        "assignments": {str(i): i for i in range(len(roles))},
        "warnings": [],
    }
    plan = decode_assignments(json.dumps(raw), list(range(len(roles))))
    assert [s["height"] for s in plan["surfaces"]] == [64, 84, 104, 128, 160, 192, 176, 128]
