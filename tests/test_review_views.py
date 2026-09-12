from backend.surface_plan import combine_reviews


def review(height, acceptable=False):
    return {
        "assessment": "Vista",
        "acceptable": acceptable,
        "issues": [],
        "seconds": 1,
        "changes": [{"material": "eye", "classes": [1], "height": height, "reason": "Borde"}],
    }


def test_conflicting_views_do_not_silently_choose_a_height():
    result = combine_reviews([review(64), review(160)], {"eye": [{"id": 1, "height": 128}]})
    assert not result["changes"] and result["issues"] and not result["acceptable"]


def test_noop_suggestions_do_not_trigger_another_displacement():
    result = combine_reviews([review(128), review(128)], {"eye": [{"id": 1, "height": 128}]})
    assert not result["changes"] and not result["acceptable"]


def test_automatic_review_preserves_eye_order_and_keeps_unrelated_changes():
    from backend.surface_plan import protect_eye_order

    plans = {
        "eye": [
            {"id": 1, "role": "pupil", "height": 104},
            {"id": 2, "role": "sclera", "height": 64},
            {"id": 3, "role": "skin", "height": 128},
            {"id": 4, "role": "freckle", "height": 160},
        ]
    }
    proposed = review(64)
    proposed["changes"].append(
        {"material": "eye", "classes": [4], "height": 176, "reason": "Peca poco visible"}
    )
    result = protect_eye_order(proposed, plans)
    assert [c["classes"] for c in result["changes"]] == [[4]]
    assert result["rejectedChanges"] == [{"material": "eye", "id": 1, "height": 64}]
    assert plans["eye"][0]["height"] == 104


def test_eye_order_guard_rechecks_after_rejecting_part_of_a_revision():
    from backend.surface_plan import protect_eye_order

    plans = {
        "eye": [
            {"id": i, "role": role, "height": h}
            for i, (role, h) in enumerate([("sclera", 64), ("iris", 84), ("pupil", 104)])
        ]
    }
    proposed = {
        "acceptable": False,
        "issues": [],
        "changes": [
            {"material": "eye", "classes": [i], "height": h, "reason": "Test"}
            for i, h in enumerate([90, 95, 91])
        ],
    }
    assert not protect_eye_order(proposed, plans)["changes"]


def test_complete_review_includes_matching_rear_control_and_garment_scope(tmp_path, monkeypatch):
    from PIL import Image
    from backend import closed_loop

    calls = []
    for name, color in [
        ("original", "red"),
        ("finished-control", "gray"),
        ("iteration-0-finished", "blue"),
    ]:
        Image.new("RGB", (4, 4), color).save(tmp_path / f"{name}-back.png")

    def inspect(model, original, displaced, angle, plans, evidence, **kwargs):
        calls.append(
            (
                original.getpixel((0, 0)),
                kwargs["control"].getpixel((0, 0)),
                displaced.getpixel((0, 0)),
                plans,
                kwargs["calibration"],
            )
        )
        return {
            "assessment": "Falta el emblema",
            "acceptable": False,
            "issues": ["Emblema ausente"],
            "changes": [],
            "seconds": 1,
            "view": "espalda",
        }

    monkeypatch.setattr(closed_loop, "review_displacement", inspect)
    plans = {"mBody": [{"id": 1, "height": 128}], "mTops": [{"id": 2, "height": 160}]}
    front = {
        "assessment": "Cara correcta",
        "acceptable": True,
        "issues": [],
        "changes": [],
        "seconds": 1,
    }
    result = closed_loop.review_assembled_back(
        "test",
        tmp_path,
        "iteration-0-finished",
        "finished-control",
        plans,
        tmp_path / "review",
        {},
        front,
        ["mTops"],
    )
    assert not result["acceptable"] and result["issues"] == ["Emblema ausente"]
    assert calls[0][:3] == ((255, 0, 0), (128, 128, 128), (0, 0, 255))
    assert list(calls[0][3]) == ["mTops"]
    assert calls[0][4]["target_materials"] == ["mTops"]
