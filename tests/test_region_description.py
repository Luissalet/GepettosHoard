import numpy as np
from scipy import ndimage
from backend.processing import describe


def test_cropped_descriptions_preserve_full_domain_measurements():
    rng = np.random.default_rng(8)
    cases = [np.zeros((27, 31), dtype=int), rng.integers(-1, 7, (27, 31))]
    blocks = np.full((80, 100), -1, dtype=int)
    blocks[:20, :15] = 0
    blocks[50:, 60:] = 1
    blocks[23:39, 34:56] = 2
    blocks[7:10, 88:92] = 2
    blocks[30, 44] = -1
    cases.append(blocks)
    for labels in cases:
        rgba = rng.integers(0, 256, (*labels.shape, 4), dtype=np.uint8)
        regions = [{"id": i, "cluster": i} for i in range(int(labels.max()) + 2)]
        actual = describe(labels, rgba, regions)
        assert len(actual) == len(set(labels.ravel()) - {-1})
        for r in actual:
            mask = labels == r['id']
            ys, xs = np.where(mask)
            cy, cx = np.unravel_index(np.argmax(ndimage.distance_transform_edt(mask)), mask.shape)
            assert r['center'] == [cx, cy]
            assert r['bbox'] == [xs.min(), ys.min(), xs.max(), ys.max()]
            assert r['color'] == np.median(rgba[:, :, :3][mask], axis=0).astype(int).tolist()
            assert r['area'] == round(mask.sum() / (labels >= 0).sum() * 100, 2)
