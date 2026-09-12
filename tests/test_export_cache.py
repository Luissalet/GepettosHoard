import numpy as np
from PIL import Image
from backend import closed_loop
from backend.surface_plan import features


def test_cache_distinguishes_spatial_ids_with_identical_color_and_reordered_heights(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(closed_loop, "ROOT", tmp_path)
    folder = tmp_path / "surface"
    folder.mkdir()
    source = tmp_path / "source.png"
    Image.new("RGBA", (64, 32), (128, 128, 128, 255)).save(source)
    Image.new("L", (64, 32), 255).save(folder / "coverage.png")
    labels = np.zeros((32, 64), np.int16)
    labels[:, 32:] = 1
    np.savez_compressed(
        folder / "masks.npz", labels=labels, centers=features(np.array([[128, 128, 128]]))
    )
    item = {"source": str(source), "width": 64, "height": 32}
    first = [{"id": 0, "cluster": 0, "height": 96}, {"id": 1, "cluster": 0, "height": 160}]
    second = [{"id": 1, "cluster": 0, "height": 96}, {"id": 0, "cluster": 0, "height": 160}]
    closed_loop.export_cached(item, folder, first, tmp_path / "first.png")
    metric = closed_loop.export_cached(item, folder, second, tmp_path / "second.png")
    assert not metric["cached"]
    with Image.open(tmp_path / "first.png") as a, Image.open(tmp_path / "second.png") as b:
        assert a.getpixel((16, 16))[0] == 96
        assert b.getpixel((16, 16))[0] == 160
    assert closed_loop.export_cached(item, folder, second, tmp_path / "repeat.png")["cached"]
