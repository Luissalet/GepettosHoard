"""Visible region IDs projected through real UV triangles, with depth occlusion."""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


def project_regions(inventory, material, labels, geometry, size=512):
    width, height = (size, size) if isinstance(size, int) else size
    center = np.asarray(geometry["center"])
    scale = geometry["size"] * 1.14
    toward = np.asarray([0.0, -2.0, 0.27])
    toward /= np.linalg.norm(toward)
    right = np.cross([0.0, 0.0, 1.0], toward)
    right /= np.linalg.norm(right)
    up = np.cross(toward, right)
    depth = np.full((height, width), -np.inf, np.float32)
    ids = np.full((height, width), -1, np.int16)
    for item in inventory:
        for points, uv in zip(item.get("world_triangles", []), item["triangles"]):
            xyz = np.asarray(points) - center
            uv = np.asarray(uv)
            uv -= np.floor(uv.mean(axis=0))
            xy = np.stack(
                [width / 2 + xyz @ right / scale * width, height / 2 - xyz @ up / scale * width],
                axis=1,
            )
            low = np.maximum(np.floor(xy.min(0)).astype(int), 0)
            high = np.minimum(np.ceil(xy.max(0)).astype(int), [width - 1, height - 1])
            if (low > high).any():
                continue
            a, b, c = xy
            den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(den) < 1e-8:
                continue
            yy, xx = np.mgrid[low[1] : high[1] + 1, low[0] : high[0] + 1]
            xx = xx + 0.5
            yy = yy + 0.5
            w0 = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / den
            w1 = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / den
            w2 = 1 - w0 - w1
            z = xyz @ toward
            current = w0 * z[0] + w1 * z[1] + w2 * z[2]
            area = np.s_[low[1] : high[1] + 1, low[0] : high[0] + 1]
            visible = (w0 >= 0) & (w1 >= 0) & (w2 >= 0) & (current > depth[area])
            if not visible.any():
                continue
            depth[area][visible] = current[visible]
            if item["material"] != material:
                ids[area][visible] = -1
                continue
            tex = w0[..., None] * uv[0] + w1[..., None] * uv[1] + w2[..., None] * uv[2]
            x = (tex[..., 0] * labels.shape[1]).astype(int).clip(0, labels.shape[1] - 1)
            y = ((1 - tex[..., 1]) * labels.shape[0]).astype(int).clip(0, labels.shape[0] - 1)
            ids[area][visible] = labels[y[visible], x[visible]]
    return ids


def annotate_regions(reference, projected):
    image = reference.convert("RGB").copy()
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    occupied = []
    visible = []
    sx = image.width / projected.shape[1]
    sy = image.height / projected.shape[0]
    for rid in sorted(
        set(projected.ravel()) - {-1}, key=lambda rid: -np.count_nonzero(projected == rid)
    ):
        mask = projected == rid
        if mask.sum() < 4:
            continue
        distance = ndimage.distance_transform_edt(mask)
        y, x = np.unravel_index(distance.argmax(), distance.shape)
        x *= sx
        y *= sy
        if any(abs(x - a) < 20 and abs(y - b) < 18 for a, b in occupied):
            continue
        occupied.append((x, y))
        visible.append(int(rid))
        text = str(rid)
        box = draw.textbbox((x, y), text, font=font, anchor="mm")
        draw.rectangle((box[0] - 2, box[1] - 1, box[2] + 2, box[3] + 1), fill="black")
        draw.text((x, y), text, fill="white", font=font, anchor="mm")
    return image, visible
