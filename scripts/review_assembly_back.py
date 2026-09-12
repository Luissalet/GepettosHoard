"""Append a missing garment-back review to an existing complete evaluation."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.closed_loop import review_assembled_back, validate_sources, write


def review_back(directory):
    out = Path(directory).resolve()
    validate_sources(out)
    result = json.loads((out / "result.json").read_text("utf-8"))
    scene = out / "scene"
    preparation = json.loads((scene / "prepare-report.json").read_text("utf-8"))
    materials = preparation.get("assembled_materials", [])
    if not materials:
        raise ValueError("This evaluation is not an assembled figure.")
    current = result["selectedReview"]
    if any("figura completa" in r.get("view", "") for r in current.get("views", [])):
        return current
    write(out / "review-before-garment-back.json", current)
    review = review_assembled_back(
        result["model"],
        scene,
        f"iteration-{result['final']}-finished",
        "finished-control",
        result["plans"],
        out / f"review-{result['final']}",
        {"settings": preparation["settings"], "geometry": preparation["geometry"], "excluded": []},
        current,
        materials,
    )
    review["geometryCheck"] = current["geometryCheck"]
    if any(
        review["geometryCheck"]["current"].get(k, 0) > review["geometryCheck"]["control"].get(k, 0)
        for k in ["boundary_edges", "nonmanifold_edges"]
    ):
        review["acceptable"] = False
    result["selectedReview"] = review
    result["aiAcceptable"] = review["acceptable"]
    for iteration in result["iterations"]:
        if iteration["iteration"] == result["final"]:
            iteration["review"] = review
    write(out / "result.json", result)
    return review


if __name__ == "__main__":
    for directory in sys.argv[1:]:
        review = review_back(directory)
        print(
            json.dumps(
                {
                    "evaluation": directory,
                    "acceptable": review["acceptable"],
                    "issues": review["issues"],
                    "views": [r["view"] for r in review["views"]],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
