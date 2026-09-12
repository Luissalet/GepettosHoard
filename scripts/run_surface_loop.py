"""Prototype of the real bake → VLM → native map → Figure Tools render loop."""

import sys, json, subprocess, time
from pathlib import Path
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.surface_plan import (
    prepare_palette,
    atlas_evidence,
    infer_plan,
    apply_plan,
    uv_coverage,
)
from backend.native_surface import export_height
from backend.processing import render

OUT = ROOT / "data/closed-loop"
scene = OUT / "scene"
inventory = json.loads((scene / "materials.json").read_text("utf-8"))
reference = Image.open(scene / "original-front.png").convert("RGB")
maps = {}
report = []
for item in inventory:
    name = item["material"]
    folder = OUT / "surfaces" / name
    folder.mkdir(parents=True, exist_ok=True)
    bake = Image.open(scene / "bake" / f"{name}.png").convert("RGBA")
    coverage = uv_coverage(item["triangles"], bake.size)
    coverage.save(folder / "coverage.png")
    if not (folder / "initial/plan.json").exists():
        labels, regions, work, centers = prepare_palette(bake, coverage=coverage)
        np.savez_compressed(folder / "masks.npz", labels=labels, centers=centers)
        (folder / "raw-regions.json").write_text(json.dumps(regions, indent=2), "utf-8")
        atlas = atlas_evidence(work, labels, regions)
        atlas.save(folder / "atlas.png")
        plan = infer_plan("qwen3.8:27b-q4_K_M", reference, atlas, regions, folder / "initial")
        regions = apply_plan(regions, plan)
        (folder / "regions.json").write_text(
            json.dumps(regions, ensure_ascii=False, indent=2), "utf-8"
        )
        render(labels, regions, "height").save(folder / "preview-height.png")
        print(name, "AI", plan["seconds"], flush=True)
    regions = json.loads((folder / "regions.json").read_text("utf-8"))
    centers = np.load(folder / "masks.npz")["centers"]
    live = OUT / "live"
    live.mkdir(exist_ok=True)
    target = live / f"{name}_height.png"
    with Image.open(item["source"]) as source:
        metric = export_height(source, centers, regions, target, coverage)
    maps[name] = str(target)
    report.append({"material": name, **metric})
    print(name, "export", metric["seconds"], flush=True)
config = scene / "iteration-0.json"
config.write_text(
    json.dumps({"phase": "render", "output": str(scene), "label": "iteration-0", "maps": maps}),
    encoding="utf-8",
)
result = subprocess.run(
    [
        r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        "--background",
        "--threads",
        "4",
        str(scene / "prepared.blend"),
        "--python",
        str(ROOT / "blender/evaluation_worker.py"),
        "--",
        str(config),
    ],
    stdout=(scene / "iteration-0.log").open("w"),
    stderr=subprocess.STDOUT,
)
assert result.returncode == 0 and (scene / "iteration-0-report.json").exists()
(OUT / "initial-export-report.json").write_text(json.dumps(report, indent=2), "utf-8")
print("ITERATION_RENDERED", json.dumps(report), flush=True)
