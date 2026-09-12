from backend.closed_loop import eye_focus


def test_closeup_recovers_world_coordinates_from_normalized_surface_bounds():
    inventory = [{"world_triangles": [[[10, 0, 0], [20, 0, 0], [10, 10, 10]]]}]
    plans = {
        "face": [
            {"name": "Pupilas", "modelBounds": {"min": [-0.2, -0.1, 0.1], "max": [0.2, 0, 0.2]}}
        ]
    }
    result = eye_focus(plans, inventory)
    assert result["center"] == [15.0, 4.5, 6.5]
    assert abs(result["size"] - 4.6) < 1e-6


def test_shared_color_across_entire_body_is_not_a_useful_eye_closeup():
    inventory = [{"world_triangles": [[[0, 0, 0], [10, 0, 0], [0, 10, 10]]]}]
    plans = {
        "body": [
            {
                "name": "Pupilas y sombras",
                "modelBounds": {"min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5]},
            }
        ]
    }
    assert eye_focus(plans, inventory) is None
    assert eye_focus({"body": [{"name": "Piel"}]}, inventory) is None


def test_an_unrelated_part_named_brow_cannot_hide_the_facial_closeup():
    inventory = [{"world_triangles": [[[0, 0, 0], [10, 0, 0], [0, 10, 10]]]}]
    eyes = {
        "name": "Pupilas",
        "role": "pupil",
        "modelBounds": {"min": [-0.2, -0.1, 0.1], "max": [0.2, 0, 0.2]},
    }
    soles = {
        "name": "Cejas",
        "role": "eyebrow",
        "modelBounds": {"min": [-0.08, 0, -0.5], "max": [0.08, 0.05, -0.5]},
    }
    assert eye_focus({"body": [eyes, soles]}, inventory) == eye_focus({"face": [eyes]}, inventory)
