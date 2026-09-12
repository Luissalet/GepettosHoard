import numpy as np
from PIL import Image
from backend.surface_plan import prepare_palette, uv_coverage
from backend.native_surface import export_height


def test_unused_uv_colors_excluded_and_small_used_detail_preserved():
    rgb = np.full((128, 128, 4), (240, 0, 240, 255), np.uint8)
    rgb[16:112, 16:112] = (220, 170, 100, 255)
    rgb[40:48, 40:48] = (15, 90, 20, 255)
    coverage = Image.new("L", (128, 128))
    coverage.paste(255, (16, 16, 112, 112))
    labels, regions, _, _ = prepare_palette(Image.fromarray(rgb), colors=2, coverage=coverage)
    assert (labels[:16] == -1).all()
    assert labels[43, 43] != labels[60, 60]
    assert all(r["color"][0] < 245 for r in regions)


def test_native_export_preserves_dimensions_alpha_and_uniform_levels_across_bands(tmp_path):
    rgb = np.full((300, 500, 4), (120, 180, 60, 255), np.uint8)
    rgb[:, 0, 3] = 0
    im = Image.fromarray(rgb)
    _, regions, _, centers = prepare_palette(im, colors=2)
    for r in regions:
        r["height"] = 177
    path = tmp_path / "height.png"
    export_height(im, centers, regions, path, softness=0)
    with Image.open(path) as output:
        actual = np.array(output)
        assert output.size == (500, 300)
    assert (actual[:, 1:, :3] == 177).all()
    assert (actual[:, 0, 3] == 0).all()


def test_uv_triangle_mask_is_not_bounding_rectangle():
    mask = np.asarray(uv_coverage([[[0, 0], [1, 0], [0, 1]]], (64, 64)))
    assert mask[60, 3] > 0 and mask[3, 60] == 0


def test_one_level_bake_noise_does_not_split_a_plain_garment():
    pixels = np.full((64, 64, 4), (116, 54, 11, 255), np.uint8)
    pixels[::2, ::2] = (116, 55, 12, 255)
    labels, regions, _, centers = prepare_palette(Image.fromarray(pixels))
    assert len(centers) == 1 and len(regions) == 1
    assert np.unique(labels).tolist() == [0]


def test_smoothed_native_png_keeps_sub_8bit_height_precision(tmp_path):
    import struct, zlib
    from backend.surface_plan import features

    pixels = np.zeros((8, 256, 3), np.uint8)
    pixels[:, 128:] = 255
    regions = [{"id": 0, "cluster": 0, "height": 64}, {"id": 1, "cluster": 1, "height": 192}]
    path = tmp_path / "precise.png"
    export_height(
        Image.fromarray(pixels), features([[0, 0, 0], [255, 255, 255]]), regions, path, softness=4
    )
    png = path.read_bytes()
    assert png[24] == 16
    offset = 8
    compressed = b""
    while offset < len(png):
        length = struct.unpack("!I", png[offset : offset + 4])[0]
        kind = png[offset + 4 : offset + 8]
        if kind == b"IDAT":
            compressed += png[offset + 8 : offset + 8 + length]
        offset += length + 12
    rows = np.frombuffer(zlib.decompress(compressed), np.uint8).reshape(8, 256 * 8 + 1)
    assert np.all(rows[:, 0] == 0)
    values = np.frombuffer(rows[:, 1:].tobytes(), ">u2").reshape(8, 256, 4)
    assert np.any(values[..., :3] % 257 != 0)
    assert values[0, 0, 0] == 64 * 257 and values[0, -1, 0] == 192 * 257


def test_uv_border_does_not_blend_unused_background_into_raised_surface(tmp_path):
    from backend.surface_plan import features

    pixels = np.zeros((256, 256, 3), np.uint8)
    pixels[:, 64:192] = 255
    coverage = Image.new("L", (256, 256))
    coverage.paste(255, (64, 0, 192, 256))
    regions = [{"id": 0, "cluster": 0, "height": 64}, {"id": 1, "cluster": 1, "height": 192}]
    path = tmp_path / "padded.png"
    export_height(
        Image.fromarray(pixels),
        features([[0, 0, 0], [255, 255, 255]]),
        regions,
        path,
        coverage,
        softness=8,
    )
    with Image.open(path) as im:
        actual = np.asarray(im)
    assert np.all(actual[:, 64:192, 0] == 192)


def test_band_blur_matches_whole_image_without_horizontal_seams(tmp_path):
    from scipy import ndimage
    from backend.surface_plan import features

    y, x = np.indices((400, 512))
    white = (y + x // 2) % 160 > 80
    pixels = np.repeat((white * 255).astype(np.uint8)[..., None], 3, axis=2)
    regions = [{"id": 0, "cluster": 0, "height": 64}, {"id": 1, "cluster": 1, "height": 192}]
    path = tmp_path / "bands.png"
    export_height(
        Image.fromarray(pixels), features([[0, 0, 0], [255, 255, 255]]), regions, path, softness=12
    )
    expected = (
        np.rint(
            ndimage.gaussian_filter(
                np.where(white, 192.0, 64.0).astype(np.float32), sigma=6, mode="nearest"
            )
            * 257
        ).astype(np.uint16)
        >> 8
    )
    with Image.open(path) as im:
        actual = np.asarray(im)[..., 0]
    np.testing.assert_array_equal(actual, expected)
