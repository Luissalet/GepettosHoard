import numpy as np
from PIL import Image
from backend.surface_regions import split_islands, separate_palette_islands
from backend.native_surface import export_height
from backend.surface_plan import features


def test_identical_black_pupil_and_nostril_can_have_independent_native_heights(tmp_path):
    labels = np.zeros((16, 16), np.int16)
    labels[2:6, 3:7] = 1
    labels[11:14, 10:13] = 1
    regions = [
        {"id": 0, "cluster": 0, "name": "Piel", "height": 128},
        {"id": 1, "cluster": 1, "name": "Negro", "height": 95},
    ]
    split, regions = split_islands(labels, regions, 1)
    pupil = int(split[3, 4])
    nostril = int(split[12, 11])
    assert pupil != nostril
    for r in regions:
        if r["id"] == pupil:
            r["height"] = 64
    colors = np.array([[200, 150, 100], [0, 0, 0]], np.uint8)
    source = Image.fromarray(colors[labels]).resize((128, 128), Image.Resampling.NEAREST)
    path = tmp_path / "height.png"
    export_height(source, features(colors), regions, path, softness=0, labels=split)
    with Image.open(path) as im:
        assert im.getpixel((4 * 8, 3 * 8))[0] == 64
        assert im.getpixel((11 * 8, 12 * 8))[0] == 95
        assert im.getpixel((0, 0))[0] == 128


def test_palette_separates_same_color_parts_before_vision_without_losing_pixels():
    labels = np.zeros((24, 24), np.int16)
    labels[2:8, 2:8] = 1
    labels[17:20, 17:20] = 1
    regions = [
        {"id": 0, "cluster": 0, "name": "Base", "height": 128},
        {"id": 1, "cluster": 1, "name": "Negro", "height": 128},
    ]
    split, parts = separate_palette_islands(labels, regions)
    assert split[3, 3] != split[18, 18]
    lookup = {r["id"]: r["cluster"] for r in parts}
    restored = np.vectorize(lookup.get)(split)
    np.testing.assert_array_equal(restored, labels)


def test_large_atlas_keeps_small_edge_fragments_without_flooding_semantic_ids():
    labels = np.zeros((1024, 1024), np.int16)
    labels[10:40, 10:40] = 1
    labels[200:225, 200:225] = 1
    for i in range(20):
        labels[500 + i * 5, 100:106] = 1
    regions = [{"id": i, "cluster": i, "name": "Color", "height": 128} for i in range(2)]
    split, parts = separate_palette_islands(labels, regions)
    assert split[20, 20] != split[210, 210]
    assert len(parts) <= 4
    lookup = {r["id"]: r["cluster"] for r in parts}
    np.testing.assert_array_equal(np.vectorize(lookup.get)(split), labels)
