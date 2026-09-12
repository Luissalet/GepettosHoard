"""Compare a fresh proposal with a separately curated, private reference.

Every feature has a vote, so a large correct skin region cannot hide a missing
eyelash. Reference labels are never supplied to the generation pipeline.
"""

import argparse, json, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.closed_loop import write


def score(reference, candidate):
    reference = Path(reference)
    candidate = Path(candidate)
    expected = json.loads((reference / "result.json").read_text("utf-8"))
    actual = json.loads((candidate / "result.json").read_text("utf-8"))
    features = []
    orders = []
    for material, regions in expected["plans"].items():
        if material not in actual["maps"]:
            features.append({"material": material, "missingMaterial": True})
            continue
        with np.load(reference / "surfaces" / material / "masks.npz") as masks:
            labels = masks["labels"]
        with Image.open(actual["maps"][material]) as image:
            levels = np.asarray(
                image.convert("L").resize(
                    (labels.shape[1], labels.shape[0]), Image.Resampling.NEAREST
                )
            )
        groups = {}
        for region in regions:
            key = (region["name"], region["height"])
            groups.setdefault(key, []).append(region["id"])
        material_features = []
        for (name, height), ids in groups.items():
            mask = np.isin(labels, ids)
            core = ndimage.distance_transform_edt(mask) > 1.5
            if core.sum() < 5:
                continue
            measured = float(np.median(levels[core]))

            def direction(value):
                return 0 if abs(value - 128) <= 3 else 1 if value > 128 else -1

            row = {
                "material": material,
                "name": name,
                "expectedHeight": height,
                "observedHeight": measured,
                "sameDirection": direction(height) == direction(measured),
                "corePixels": int(core.sum()),
            }
            features.append(row)
            material_features.append(row)
        for i, a in enumerate(material_features):
            for b in material_features[i + 1 :]:
                delta = a["expectedHeight"] - b["expectedHeight"]
                if abs(delta) < 12:
                    continue
                observed = a["observedHeight"] - b["observedHeight"]
                orders.append(
                    {
                        "material": material,
                        "a": a["name"],
                        "b": b["name"],
                        "preserved": observed * delta > 0 and abs(observed) >= 4,
                    }
                )
    measured = [r for r in features if "sameDirection" in r]
    return {
        "reference": str(reference.resolve()),
        "candidate": str(candidate.resolve()),
        "features": features,
        "orders": orders,
        "directionMatches": sum(r["sameDirection"] for r in measured),
        "featureCount": len(measured),
        "orderMatches": sum(r["preserved"] for r in orders),
        "orderCount": len(orders),
        "note": "Agreement with this artist reference, not a general aesthetic or printability certification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("candidate")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = score(args.reference, args.candidate)
    write(args.output, report)
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"features", "orders"}}, ensure_ascii=False
        )
    )
