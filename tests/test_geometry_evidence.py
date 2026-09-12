import numpy as np
from PIL import Image
from backend import geometry_evidence as evidence


def test_large_material_cannot_be_flattened_by_the_compact_part_shortcut():
    item = {"world_triangles": [[[0, 0, 0], [8, 0, 0], [0, 8, 0]]]}
    assert not evidence.compact_part(item, {"size": 10})


def test_unseen_atlas_regions_prevent_a_uniform_geometry_shortcut(tmp_path, monkeypatch):
    item = {"material": "piece", "world_triangles": [[[0, 0, 0], [1, 0, 0], [0, 1, 0]]]}
    labels = np.zeros((16, 16), np.int16)
    labels[:, 8:] = 1
    monkeypatch.setattr(evidence, "project_regions", lambda *args, **kwargs: np.zeros_like(labels))

    def no_request(*args, **kwargs):
        raise AssertionError("Unseen regions must not be declared uniform")

    monkeypatch.setattr(evidence.httpx, "Client", no_request)
    image = Image.new("RGB", (16, 16))
    assert (
        evidence.preserve_modeled_part(
            "model",
            item,
            [item],
            labels,
            [{"id": 0}, {"id": 1}],
            {"size": 10},
            image,
            image,
            tmp_path,
        )
        is None
    )
