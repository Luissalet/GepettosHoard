"""Recompute semantic decisions with scene reasoning, reusing only prepared assets."""

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
from scripts.probe_grounded_material import probe
from backend.closed_loop import run, validate_sources, write
from backend.surface_plan import apply_plan
from backend.active_views import audit_hidden, hidden_features
from backend.semantic_audit import audit, candidates
from backend.region_evidence import project_regions
from backend.scene_understanding import apply_print_intent


def evaluate(source, components_source, contract, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Use a new output folder")
    validate_sources(source)
    start = time.perf_counter()
    seed = output / "input"
    shutil.copytree(source, seed)
    components = json.loads((Path(components_source) / "result.json").read_text("utf-8"))[
        "components"
    ]
    component_paths = [Path(components[key]) for key in ["body", "garment"]]
    result = json.loads((source / "result.json").read_text("utf-8"))
    scene_contract = apply_print_intent(json.loads(Path(contract).read_text("utf-8")))
    inventory = json.loads((source / "scene/materials.json").read_text("utf-8"))
    for item in inventory:
        name = item["material"]
        with np.load(source / "surfaces" / name / "masks.npz") as masks:
            uniform = len(masks["centers"]) == 1
            labels = masks["labels"]
        if uniform:
            rows = json.loads((source / "surfaces" / name / "regions.json").read_text("utf-8"))
            for row in rows:
                row.update(
                    name="Superficie uniforme",
                    role="base",
                    height=128,
                    scenePart=None,
                    semanticGroup=f"{name}-uniform",
                    heightGroup=f"{name}-uniform",
                    reason="Textura uniforme: conserva el volumen existente.",
                    semanticSource="uniform-texture",
                )
        else:
            bake = next(
                (
                    p / "scene/bake" / f"{name}.png"
                    for p in component_paths
                    if (p / "scene/bake" / f"{name}.png").exists()
                ),
                None,
            )
            if bake is None:
                raise ValueError(f"Missing prepared bake for {name}")
            folder = output / "recognition" / name
            print("RECOGNIZING", name, flush=True)
            probe(source, contract, name, folder, bake)
            rows = json.loads((folder / "regions.json").read_text("utf-8"))
            plan = json.loads((folder / "plan.json").read_text("utf-8"))
            if hidden_features(rows, plan, labels):
                print("ACTIVE VIEWS", name, flush=True)
                plan = audit_hidden(
                    result["model"],
                    seed / "scene",
                    item,
                    inventory,
                    labels,
                    rows,
                    plan,
                    scene_contract,
                    folder / "active-checks",
                )
                rows = apply_plan(rows, plan)
                for group, surface in enumerate(plan["surfaces"]):
                    for row in rows:
                        if row["id"] in surface["classes"]:
                            row["semanticGroup"] = row["heightGroup"] = f"{name}-{group}"
        if not uniform:
            if candidates(labels, rows, plan):
                print("FOCUSED CHECKS", name, flush=True)
                with Image.open(bake) as image:
                    work = image.convert("RGBA").resize(
                        (labels.shape[1], labels.shape[0]), Image.Resampling.LANCZOS
                    )
                with Image.open(source / "surfaces" / name / "coverage.png") as coverage:
                    alpha = np.minimum(
                        np.asarray(work.getchannel("A")),
                        np.asarray(coverage.resize(work.size, Image.Resampling.NEAREST)),
                    )
                work.putalpha(Image.fromarray(alpha))
                geometry = json.loads((seed / "scene/prepare-report.json").read_text("utf-8"))[
                    "geometry"
                ]
                projected = project_regions(inventory, name, labels, geometry, size=768)
                with Image.open(seed / "scene/original-front.png") as reference:
                    plan = audit(
                        result["model"],
                        work,
                        labels,
                        rows,
                        plan,
                        folder / "focused-checks",
                        scene_context=scene_contract,
                        model_reference=reference,
                        projected=projected,
                    )
                rows = apply_plan(rows, plan)
                for group, surface in enumerate(plan["surfaces"]):
                    for row in rows:
                        if row["id"] in surface["classes"]:
                            row["semanticGroup"] = row["heightGroup"] = f"{name}-{group}"
            shutil.copytree(folder, seed / "surfaces" / name / "reasoned-recognition")
        write(seed / "surfaces" / name / "regions.json", rows)
    final = run(
        None,
        output / "evaluation",
        result["model"],
        lambda **v: print(v.get("message", ""), flush=True),
        corrections=0,
        reuse=seed,
        scene_contract=contract,
    )
    write(
        output / "experiment.json",
        {
            "source": str(source),
            "componentsSource": str(Path(components_source).resolve()),
            "contract": str(Path(contract).resolve()),
            "manualAssignments": 0,
            "previousSemanticDecisionsUsed": False,
            "preparedGeometryReused": True,
            "focusedAudits": "active-views-and-contextual-color-checks",
            "seconds": round(time.perf_counter() - start, 2),
            "aiAcceptable": final["aiAcceptable"],
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ["source", "components_source", "contract", "output"]:
        p.add_argument(name)
    a = p.parse_args()
    evaluate(a.source, a.components_source, a.contract, a.output)
