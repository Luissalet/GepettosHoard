import numpy as np
from PIL import Image
from backend.native_surface import export_control


def test_uniform_control_preserves_transparency_used_by_geometry(tmp_path):
    pixels = np.zeros((3, 4, 4), np.uint8)
    pixels[..., :3] = [31, 201, 92]
    pixels[..., 3] = np.arange(12, dtype=np.uint8).reshape(3, 4) * 23
    path = tmp_path / "control.png"
    export_control(Image.fromarray(pixels), path)
    with Image.open(path) as image:
        result = np.array(image)
    assert np.all(result[..., :3] == 128)
    np.testing.assert_array_equal(result[..., 3], pixels[..., 3])


def test_opaque_control_uses_small_texture(tmp_path):
    path = tmp_path / "control.png"
    export_control(Image.new("RGBA", (4096, 2048), (255, 23, 92, 255)), path)
    with Image.open(path) as image:
        assert image.size == (8, 8)
        assert image.getpixel((0, 0)) == (128, 128, 128, 255)
