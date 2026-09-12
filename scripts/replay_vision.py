"""Regression replay of the real recorded VLM output, without another GPU call.
Preserves raw evidence; invalid references are discarded with a visible warning.
"""

import json, time, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import vision
from backend.processing import solve_relations
from backend.app import read, save, lock

pid = json.loads((ROOT / "data/validation/project.json").read_text())["id"]
evidence = ROOT / "data" / pid / "analyses/3cf686ee4076"
raw = json.loads((evidence / "response.json").read_text("utf-8"))
inp = json.loads((evidence / "input.json").read_text("utf-8"))
proposal = vision.Proposal.model_validate_json(raw["message"]["content"]).model_dump()
proposal = vision.validate_grounding(proposal, {r["key"] for r in inp["inventory"]["items"]})
proposal.update(
    model=inp["model"],
    duration=raw["total_duration"] / 1e9,
    status="pending",
    created=time.time(),
    method="multiview-uv-vlm",
    inputRevision=inp["revision"],
    replay="Grounding validator regression replay; original VLM response preserved",
)
proposal["heights"] = solve_relations(proposal["regions"], proposal["relations"])
with lock:
    p = read(pid)
    assert p["revision"] == inp["revision"], "Project changed after recorded inference"
    p["proposal"] = proposal
    save(p)
(evidence / "validated-proposal.json").write_text(
    json.dumps(proposal, ensure_ascii=False, indent=2), "utf-8"
)
print(
    json.dumps(
        {
            "regions": len(proposal["regions"]),
            "relations": len(proposal["relations"]),
            "levels": sorted(set(proposal["heights"].values())),
            "warnings": proposal["warnings"],
        },
        ensure_ascii=False,
    )
)
