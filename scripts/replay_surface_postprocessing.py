"""Reevaluate cached model responses with current checks; no manual assignments.

This is an ablation/replay tool, not a cold-start timing benchmark. Keep its
evidence separate from fresh runs and from artist-curated reference projects.
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.closed_loop import run, write, validate_sources
from backend.surface_plan import decode_assignments, apply_plan
from backend.semantic_audit import audit, candidates
from backend.geometry_evidence import compact_part, preserve_modeled_part


def replay(source, out):
    source = Path(source).resolve()
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("Use a new output folder to preserve prior evidence.")
    validate_sources(source)
    started = time.perf_counter()
    result = json.loads((source / "result.json").read_text("utf-8"))
    model = result["model"]
    seed = out / "input"
    shutil.copytree(source, seed)
    components = [Path(result["components"][key]) for key in ["body", "garment"]]
    for component in components:
        inventory = json.loads((component / "scene/materials.json").read_text("utf-8"))
        geometry = json.loads((component / "scene/prepare-report.json").read_text("utf-8"))[
            "geometry"
        ]
        for item in inventory:
            name = item["material"]
            original = component / "surfaces" / name
            destination = seed / "surfaces" / name
            regions = json.loads((original / "regions.json").read_text("utf-8"))
            with np.load(original / "masks.npz") as masks:
                labels = masks["labels"]
            plan = None
            colored = component / "scene" / f"focused-{name}-front.png"
            control = component / "scene/control-front.png"
            if compact_part(item, geometry) and colored.exists() and control.exists():
                context = json.loads(
                    (component / "scene/context-materials.json").read_text("utf-8")
                )
                with Image.open(colored) as a, Image.open(control) as b:
                    plan = preserve_modeled_part(
                        model,
                        item,
                        context,
                        labels,
                        regions,
                        geometry,
                        a,
                        b,
                        destination / "geometry-check",
                    )
            if plan is None:
                raw_path = original / "initial/raw.json"
                if raw_path.exists():
                    content = json.loads(raw_path.read_text("utf-8"))["content"]
                    plan = decode_assignments(content, [r["id"] for r in regions])
                    if candidates(labels, regions, plan):
                        with Image.open(component / "scene/bake" / f"{name}.png") as bake:
                            work = bake.convert("RGBA").resize(
                                (labels.shape[1], labels.shape[0]), Image.Resampling.LANCZOS
                            )
                        with Image.open(original / "coverage.png") as coverage:
                            alpha = np.minimum(
                                np.asarray(work.getchannel("A")),
                                np.asarray(coverage.resize(work.size, Image.Resampling.NEAREST)),
                            )
                        work.putalpha(Image.fromarray(alpha))
                        plan = audit(
                            model,
                            work,
                            labels,
                            regions,
                            plan,
                            destination / "focused-checks-replayed",
                        )
                else:
                    plan = json.loads((original / "initial/plan.json").read_text("utf-8"))
            regions = apply_plan(regions, plan)
            for group, surface in enumerate(plan["surfaces"]):
                for region in regions:
                    if region["id"] in surface["classes"]:
                        region["semanticGroup"] = region["heightGroup"] = f"{name}-{group}"
            write(destination / "regions.json", regions)
            write(destination / "replayed-plan.json", plan)
            print("REPLAYED", name, flush=True)
    final = run(
        None,
        out / "evaluation",
        model,
        lambda **v: print(v.get("message", ""), flush=True),
        reuse=seed,
        corrections=0,
    )
    write(
        out / "replay.json",
        {
            "sourceRun": str(source),
            "evaluation": str(out / "evaluation"),
            "replayedModelResponses": True,
            "manualAssignments": 0,
            "seconds": round(time.perf_counter() - started, 2),
            "aiAcceptable": final["aiAcceptable"],
        },
    )
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    replay(arguments.source, arguments.output)
