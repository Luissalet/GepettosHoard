import pytest
from backend.commands import EditPlan, Operation, apply_operations


def project():
    return {
        "assets": [
            {
                "id": "a",
                "regions": [
                    {"id": 0, "name": "Ojos", "height": 100},
                    {"id": 1, "name": "Pecas", "height": 160},
                ],
            },
            {"id": "b", "regions": [{"id": 0, "name": "Pecas laterales", "height": 150}]},
        ]
    }


def run(p, *ops):
    return apply_operations(
        p, EditPlan(explanation="Test", operations=[Operation(**o) for o in ops])
    )


def rows(p):
    return [r for a in p["assets"] for r in a["regions"]]


def test_equal_persists_across_textures_without_merging_then_split_detaches():
    p = project()
    q = run(
        p,
        {"action": "equal", "targets": ["a:1", "b:0"]},
        {"action": "raise", "targets": ["b:0"], "amount": 20},
    )
    assert [r["height"] for r in rows(q)] == [100, 180, 180]
    assert rows(q)[1]["name"] != rows(q)[2]["name"]
    assert [r["height"] for r in rows(p)] == [100, 160, 150]
    r = run(
        q,
        {"action": "split", "targets": ["b:0"]},
        {"action": "lower", "targets": ["a:1"], "amount": 30},
    )
    assert [x["height"] for x in rows(r)] == [100, 150, 180]


def test_merge_preserves_region_ids_and_can_be_undone_by_snapshot():
    p = project()
    q = run(p, {"action": "merge", "targets": ["a:1", "b:0"], "name": "Pecas"})
    assert rows(q)[1]["semanticGroup"] == rows(q)[2]["semanticGroup"]
    assert [r["id"] for r in rows(q)] == [0, 1, 0]
    assert rows(p)[2]["name"] == "Pecas laterales"


def test_invalid_targets_are_atomic_and_clarification_never_mutates():
    p = project()
    with pytest.raises(ValueError):
        run(
            p,
            {"action": "raise", "targets": ["a:0"]},
            {"action": "set", "targets": ["invented"], "height": 0},
        )
    assert rows(p)[0]["height"] == 100
    q = apply_operations(p, EditPlan(explanation="", clarification="¿Qué ojo?", operations=[]))
    assert q == p


def test_height_limits_and_explicit_height():
    q = run(
        project(),
        {"action": "set", "targets": ["a:0"], "height": 5},
        {"action": "lower", "targets": ["a:0"], "amount": 20},
        {"action": "raise", "targets": ["a:1"], "amount": 128},
    )
    assert [r["height"] for r in rows(q)] == [0, 255, 150]
