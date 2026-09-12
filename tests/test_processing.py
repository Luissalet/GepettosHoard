import numpy as np
import pytest
from PIL import Image
from backend.processing import (
    segment,
    render_native,
    solve_relations,
    write_native_pair,
    HEIGHT_PALETTE,
)


def test_layer_order_and_modeled_volume():
    nodes = [{"key": x} for x in ["pants", "belt", "buckle", "shoe"]]
    edges = [
        {"upper": "belt", "lower": "pants", "apply": True},
        {"upper": "buckle", "lower": "belt", "apply": True},
        {"upper": "pants", "lower": "shoe", "apply": False},
    ]
    h = solve_relations(nodes, edges)
    assert h["buckle"] > h["belt"] > h["pants"]
    assert h["shoe"] == h["pants"]


def test_cycles_and_unknown_regions_rejected():
    n = [{"key": "a"}, {"key": "b"}]
    with pytest.raises(ValueError):
        solve_relations(n, [{"upper": "a", "lower": "b"}, {"upper": "b", "lower": "a"}])
    with pytest.raises(ValueError):
        solve_relations(n, [{"upper": "missing", "lower": "b"}])


def test_segmentation_neutral_deterministic_and_alpha_preserved():
    data = np.zeros((128, 256, 4), np.uint8)
    data[:, :128] = [240, 50, 50, 255]
    data[:, 128:] = [40, 80, 240, 255]
    data[:10] = 0
    image = Image.fromarray(data)
    labels, r, _, c = segment(image, 2, 128)
    labels2, _, _, _ = segment(image, 2, 128)
    assert np.array_equal(labels, labels2)
    assert {x["height"] for x in r} == {128}
    r[0]["height"] = 80
    r[1]["height"] = 220
    out = np.array(render_native(image, labels, r, c))
    assert out.shape == data.shape
    assert np.array_equal(out[:, :, 3], data[:, :, 3])
    assert out[70, 40, 0] != out[70, 200, 0]
    assert np.array_equal(out[:, :, 0], out[:, :, 1])


def test_native_edges_not_nearest_upscale():
    data = np.full((120, 1000, 4), 255, np.uint8)
    data[:, :503, :3] = [10, 30, 200]
    data[:, 503:, :3] = [240, 40, 10]
    image = Image.fromarray(data)
    labels, r, _, centers = segment(image, 2, 256)
    for i, x in enumerate(r):
        x["height"] = 50 + i * 150
    out = np.array(render_native(image, labels, r, centers))
    assert out[60, 502, 0] != out[60, 503, 0]
    assert np.all(out[60, :503, 0] == out[60, 10, 0])
    assert np.all(out[60, 503:, 0] == out[60, 800, 0])


def test_transparent_image_rejected():
    with pytest.raises(ValueError):
        segment(Image.new("RGBA", (32, 32), (0, 0, 0, 0)))


def test_streamed_png_matches_reference_and_palette_is_injective(tmp_path):
    im = Image.new("RGBA", (529, 173), (123, 50, 202, 231))
    labels, regions, _, centers = segment(im, 2, 256)
    hp = tmp_path / "height.png"
    cp = tmp_path / "recolor.png"
    write_native_pair(im, labels, regions, centers, hp, cp)
    for path, mode in [(hp, "height"), (cp, "color")]:
        with Image.open(path) as actual:
            expected = render_native(im, labels, regions, centers, mode)
            assert np.array_equal(np.array(actual), np.array(expected))
    assert len(set(HEIGHT_PALETTE)) == 256
