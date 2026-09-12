import numpy as np
from backend.region_evidence import project_regions


def test_projection_uses_uv_and_hides_regions_behind_other_material():
    # Two identical triangles; the nearer one occludes the center of the back.
    points = [[-1, 0, -1], [1, 0, -1], [0, 0, 1]]
    uv = [[0, 0], [1, 0], [0.5, 1]]
    base = {"material": "body", "triangles": [uv], "world_triangles": [points]}
    labels = np.full((32, 32), 7, np.int16)
    geometry = {"center": [0, 0, 0], "size": 3}
    projected = project_regions([base], "body", labels, geometry, size=64)
    assert projected[32, 32] == 7
    front = {
        "material": "cloth",
        "triangles": [uv],
        "world_triangles": [[[x, y - 1, z] for x, y, z in points]],
    }
    hidden = project_regions([base, front], "body", labels, geometry, size=64)
    assert hidden[32, 32] == -1
    reverse = project_regions([front, base], "body", labels, geometry, size=64)
    assert np.array_equal(hidden, reverse)


def test_atlas_label_is_inside_its_region_even_when_centroid_is_in_a_hole():
    from PIL import Image
    from backend.surface_plan import atlas_evidence

    labels = np.zeros((32, 32), np.int16)
    labels[10:22, 10:22] = 1
    regions = [{"id": 0, "center": [16, 16], "area": 85}, {"id": 1, "center": [16, 16], "area": 15}]
    atlas_evidence(Image.new("RGB", (32, 32), "white"), labels, regions)
    for r in regions:
        x, y = r["labelPoint"]
        assert labels[y, x] == r["id"]
