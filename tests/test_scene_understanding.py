import json
import numpy as np
import pytest
from backend.scene_understanding import SceneContract, apply_print_intent
from backend.region_evidence import locate_in_view
from backend.surface_plan import decode_assignments


def part(key):
    return {
        "key": key,
        "name": key,
        "appearance": "visible shape",
        "location": "face",
        "representation": "painted",
        "controlEvidence": "disappears",
        "printRequirement": "keep its edge",
    }


def test_scene_relations_only_connect_distinct_observed_parts():
    draft = {
        "parts": [part("eye"), part("pupil")],
        "relations": [
            {
                "part": "pupil",
                "reference": "eye",
                "relation": "inside",
                "evidence": "surrounded by white",
            }
        ],
        "uncertainties": [],
    }
    SceneContract.model_validate(draft)
    draft["relations"][0]["reference"] = "belt"
    with pytest.raises(ValueError):
        SceneContract.model_validate(draft)
    draft["relations"] = []
    draft["parts"][1]["key"] = "eye"
    with pytest.raises(ValueError):
        SceneContract.model_validate(draft)


def test_uv_assignment_must_refer_to_an_observed_scene_part():
    draft = {
        "description": "figure",
        "groups": [
            {
                "scenePart": "eyes",
                "name": "Pupilas",
                "role": "pupil",
                "reason": "black oval inside white",
            }
        ],
        "assignments": {"3": 0},
        "warnings": [],
    }
    result = decode_assignments(json.dumps(draft), [3], scene_keys=["eyes", "unresolved"])
    assert result["surfaces"][0]["scenePart"] == "eyes"
    assert result["surfaces"][0]["height"] == 104
    with pytest.raises(ValueError, match="pieza observada"):
        decode_assignments(json.dumps(draft), [3], scene_keys=["feet"])


def test_hidden_regions_do_not_gain_invented_screen_locations():
    projected = np.full((10, 20), -1, dtype=np.int16)
    projected[7:9, 2:5] = 2
    rows = locate_in_view([{"id": 2}, {"id": 3}], projected)
    assert rows[0]["frontImageBox"] == [0.1, 0.7, 0.25, 0.9]
    assert rows[1]["frontImageBox"] is None


def test_model_cannot_replace_unpainted_print_intent_with_painting_instructions():
    draft = {
        "parts": [part("freckles"), part("nose")],
        "relations": [],
        "uncertainties": ["The underside is hidden"],
    }
    draft["parts"][0]["printRequirement"] = "Leave flat for painting later"
    draft["parts"][1]["representation"] = "modeled"
    result = apply_print_intent(draft)
    assert "sin color" in result["parts"][0]["printRequirement"]
    assert "no duplicarlo" in result["parts"][1]["printRequirement"]
    assert result["uncertainties"] == draft["uncertainties"]
    assert result["parts"][0]["controlEvidence"] == draft["parts"][0]["controlEvidence"]
    assert draft["parts"][0]["printRequirement"] == "Leave flat for painting later"
