"""Replay compact-part geometry checks against a preserved complete candidate."""

import argparse, json, shutil, sys, time
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.closed_loop import run, write, validate_sources
from backend.geometry_evidence import compact_part, preserve_modeled_part
from backend.surface_plan import apply_plan

p = argparse.ArgumentParser()
p.add_argument("source", type=Path)
p.add_argument("output", type=Path)
a = p.parse_args()
source = a.source.resolve()
out = a.output.resolve()
if out.exists():
    raise ValueError("Use a new output directory")
validate_sources(source)
start = time.perf_counter()
seed = out / "input"
shutil.copytree(source, seed)
result = json.loads((source / "result.json").read_text("utf8"))
inventory = json.loads((source / "scene/materials.json").read_text("utf8"))
geometry = json.loads((source / "scene/prepare-report.json").read_text("utf8"))["geometry"]
changes = []
for item in inventory:
    if not compact_part(item, geometry):
        continue
    name = item["material"]
    folder = seed / "surfaces" / name
    with np.load(folder / "masks.npz") as data:
        labels = data["labels"]
    rows = json.loads((folder / "regions.json").read_text("utf8"))
    with (
        Image.open(source / "scene/original-front.png") as original,
        Image.open(source / "scene/control-front.png") as control,
    ):
        plan = preserve_modeled_part(
            result["model"],
            item,
            inventory,
            labels,
            rows,
            geometry,
            original,
            control,
            folder / "geometry-recheck",
        )
    if plan is None:
        continue
    keys = {r.get("scenePart") for r in rows} - {None, "unresolved"}
    for group in plan["surfaces"]:
        group["scenePart"] = next(iter(keys)) if len(keys) == 1 else "unresolved"
    rows = apply_plan(rows, plan)
    for row in rows:
        row["semanticGroup"] = row["heightGroup"] = name + "-modeled"
    write(folder / "regions.json", rows)
    changes.append({"material": name, "plan": plan})
    print(json.dumps(changes[-1], ensure_ascii=False), flush=True)
write(out / "checks.json", changes)
final = run(
    None,
    out / "evaluation",
    result["model"],
    lambda **v: print(v.get("message", ""), flush=True),
    corrections=0,
    reuse=seed,
    scene_contract=source / "observation/contract.json",
)
write(
    out / "experiment.json",
    {
        "source": str(source),
        "manualAssignments": 0,
        "preparedGeometryReused": True,
        "previousModelDecisionsReused": True,
        "method": "compact-geometry-recheck",
        "seconds": round(time.perf_counter() - start, 2),
        "aiAcceptable": final["aiAcceptable"],
    },
)
