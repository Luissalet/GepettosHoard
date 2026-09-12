import json, subprocess
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "data/closed-loop/scene"
out.mkdir(parents=True, exist_ok=True)
previews = out / "analysis_sources"
previews.mkdir(exist_ok=True)
for p in Path(r"E:\Modelos\Animal Crossing\ACNH_2.0.0\Characters\Zucker\upscaled_chain").glob(
    "*.png"
):
    with Image.open(p) as image:
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        image.save(previews / p.name)
config = out / "prepare.json"
config.write_text(
    json.dumps({"phase": "prepare", "output": str(out), "separate_materials": ["mTops"]})
)
result = subprocess.run(
    [
        r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        "--background",
        "--threads",
        "4",
        str(ROOT / "data/validation/Zucker-original-copy.blend"),
        "--python",
        str(ROOT / "blender/evaluation_worker.py"),
        "--",
        str(config),
    ],
    stdout=(out / "prepare.log").open("w"),
    stderr=subprocess.STDOUT,
)
assert result.returncode == 0
assert (out / "prepare-report.json").exists(), (out / "prepare.log").read_text(errors="replace")[
    -2000:
]
print((out / "prepare-report.json").read_text())
