"""Fresh material recognition from preserved geometry, with a visual scene contract."""

import argparse
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.surface_plan import infer_semantics, atlas_evidence, apply_plan
from backend.region_evidence import (
    project_regions,
    locate_in_view,
    focused_annotation,
)
from backend.closed_loop import validate_sources, write
from backend.scene_understanding import apply_print_intent


def probe(source, contract_path, material, out, bake_source=None):
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError("Use a new evidence directory")
    validate_sources(source)
    scene = source / "scene"
    with np.load(source / "surfaces" / material / "masks.npz") as data:
        labels = data["labels"]
    old = json.loads((source / "surfaces" / material / "regions.json").read_text("utf-8"))
    allowed = ["id", "cluster", "color", "center", "area", "modelBounds", "labelPoint"]
    regions = [{k: v for k, v in row.items() if k in allowed} for row in old]
    with Image.open(
        Path(bake_source) if bake_source else scene / "bake" / f"{material}.png"
    ) as bake:
        atlas = atlas_evidence(bake, labels, regions)
    inventory = json.loads((scene / "materials.json").read_text("utf-8"))
    geometry = json.loads((scene / "prepare-report.json").read_text("utf-8"))["geometry"]
    projected = project_regions(inventory, material, labels, geometry, size=768)
    locate_in_view(regions, projected)
    with Image.open(scene / "original-front.png") as original:
        annotated, visible = focused_annotation(original, projected)
        contract = apply_print_intent(json.loads(Path(contract_path).read_text("utf-8")))
        model = json.loads((source / "result.json").read_text("utf-8"))["model"]
        plan = infer_semantics(model, original, atlas, annotated, regions, out, contract)
    result = apply_plan(regions, plan)
    for index, surface in enumerate(plan["surfaces"]):
        for row in result:
            if row["id"] in surface["classes"]:
                row["semanticGroup"] = row["heightGroup"] = f"{material}-{index}"
    write(out / "regions.json", result)
    write(
        out / "provenance.json",
        {
            "source": str(source),
            "contract": str(Path(contract_path).resolve()),
            "previousDecisionsUsed": False,
            "bakeSource": str(Path(bake_source).resolve())
            if bake_source
            else str(scene / "bake" / f"{material}.png"),
        },
    )
    print(json.dumps(plan, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ["source", "contract", "material", "output"]:
        parser.add_argument(key)
    parser.add_argument("--bake-source")
    args = parser.parse_args()
    probe(args.source, args.contract, args.material, args.output, args.bake_source)
