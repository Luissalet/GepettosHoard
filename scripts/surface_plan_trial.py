"""Run the generic palette + VLM plan on real source textures, with full evidence."""

import sys, json, time
from pathlib import Path
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.surface_plan import prepare_palette, atlas_evidence, infer_plan, apply_plan
from backend.processing import render

OUT = ROOT / "data/closed-loop"
OUT.mkdir(exist_ok=True)
source = Path(r"E:\Modelos\Animal Crossing\ACNH_2.0.0\Characters\Zucker\upscaled_chain")
reference = Image.open(ROOT / "data/c096b2050227/analyses/31e9f09185c4/view-0.png").convert("RGB")
names = sys.argv[1:] or ["mBody_Alb.png", "mEye_Alb.0.png", "mBeak_Alb.png", "mTops_Alb.png"]
for name in names:
    folder = OUT / Path(name).stem
    folder.mkdir(exist_ok=True)
    with Image.open(source / name) as original:
        start = time.perf_counter()
        labels, regions, work, centers = prepare_palette(original)
        np.savez_compressed(folder / "masks.npz", labels=labels, centers=centers)
        (folder / "regions.json").write_text(json.dumps(regions, indent=2), "utf-8")
        print(name, "prepared", round(time.perf_counter() - start, 2), flush=True)
        atlas = atlas_evidence(work, labels, regions)
        atlas.save(folder / "atlas.png")
        plan = infer_plan("qwen3.8:27b-q4_K_M", reference, atlas, regions, folder / "initial")
        updated = apply_plan(regions, plan)
        (folder / "regions.json").write_text(
            json.dumps(updated, ensure_ascii=False, indent=2), "utf-8"
        )
        render(labels, updated, "height").save(folder / "preview-height.png")
        print(name, json.dumps(plan, ensure_ascii=False), flush=True)
