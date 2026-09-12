"""Measure actual 4K/8K processing, native export and peak RSS. Not model inference."""

import json, time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image, ImageDraw
from backend.processing import segment, render_native, png_bytes

results = []
for n in [4096, 8192]:
    image = Image.new("RGBA", (n, n), (60, 120, 150, 255))
    d = ImageDraw.Draw(image)
    d.ellipse((n * 0.12, n * 0.1, n * 0.85, n * 0.85), fill=(230, 180, 100, 255))
    d.rectangle((0, n * 0.45, n, n * 0.54), fill=(90, 40, 30, 255))
    d.rectangle((n * 0.4, n * 0.43, n * 0.6, n * 0.57), fill=(245, 230, 110, 255))
    start = time.perf_counter()
    labels, regions, work, centers = segment(image, 6, 768)
    seg = time.perf_counter() - start
    for i, r in enumerate(regions):
        r["height"] = min(255, 70 + i * 20)
    start = time.perf_counter()
    out = render_native(image, labels, regions, centers)
    render_s = time.perf_counter() - start
    start = time.perf_counter()
    data = png_bytes(out)
    png_s = time.perf_counter() - start
    results.append(
        {
            "resolution": n,
            "analysis_seconds": round(seg, 3),
            "native_refinement_seconds": round(render_s, 3),
            "png_seconds": round(png_s, 3),
            "regions": len(regions),
            "output_dimensions": out.size,
            "png_bytes": len(data),
            "fixture": "synthetic color regions; not real character performance",
        }
    )
    print(json.dumps(results[-1]), flush=True)
    image.close()
    out.close()
outdir = Path(__file__).resolve().parents[1] / "data" / "validation"
outdir.mkdir(parents=True, exist_ok=True)
(outdir / "benchmark.json").write_text(json.dumps(results, indent=2))
