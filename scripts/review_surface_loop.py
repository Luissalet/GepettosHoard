import sys, json, subprocess
from pathlib import Path
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.surface_plan import review_displacement
from backend.native_surface import export_height

OUT = ROOT / "data/closed-loop"
scene = OUT / "scene"
iteration = int(sys.argv[1]) if len(sys.argv) > 1 else 0
plans = {
    f.parent.name: json.loads(f.read_text("utf-8"))
    for f in (OUT / "surfaces").glob("*/regions.json")
}
review = review_displacement(
    "qwen3.8:27b-q4_K_M",
    Image.open(scene / "original-front.png"),
    Image.open(scene / f"iteration-{iteration}-front.png"),
    Image.open(scene / f"iteration-{iteration}-three-quarter.png"),
    plans,
    OUT / f"review-{iteration}",
    control=Image.open(scene / "control-front.png"),
)
print(json.dumps(review, ensure_ascii=False), flush=True)
if review["changes"]:
    for c in review["changes"]:
        for r in plans[c["material"]]:
            if r["id"] in c["classes"]:
                r["height"] = c["height"]
                r["reason"] = c["reason"]
    maps = {}
    for item in json.loads((scene / "materials.json").read_text("utf-8")):
        name = item["material"]
        folder = OUT / "surfaces" / name
        (folder / "regions.json").write_text(
            json.dumps(plans[name], ensure_ascii=False, indent=2), "utf-8"
        )
        target = OUT / "live" / f"{name}_height.png"
        with Image.open(item["source"]) as source:
            export_height(
                source,
                np.load(folder / "masks.npz")["centers"],
                plans[name],
                target,
                Image.open(folder / "coverage.png"),
            )
        maps[name] = str(target)
    label = f"iteration-{iteration + 1}"
    config = scene / f"{label}.json"
    config.write_text(
        json.dumps({"phase": "render", "output": str(scene), "label": label, "maps": maps}),
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
        stdout=(scene / f"{label}.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    assert result.returncode == 0 and (scene / f"{label}-report.json").exists()
    print("CORRECTION_RENDERED", label, flush=True)
