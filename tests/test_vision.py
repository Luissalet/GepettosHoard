from backend.vision import validate_grounding


def test_unknown_reference_dropped_and_missing_explicitly_uncertain():
    p = {
        "regions": [{"key": "a", "name": "skin"}, {"key": "ghost", "name": "belt"}],
        "relations": [{"upper": "ghost", "lower": "a", "apply": True}],
        "warnings": [],
    }
    q = validate_grounding(p, {"a", "b"})
    assert {r["key"] for r in q["regions"]} == {"a", "b"}
    assert next(r for r in q["regions"] if r["key"] == "b")["confidence"] == 0
    assert not q["relations"] and "ghost" in q["warnings"][0]
