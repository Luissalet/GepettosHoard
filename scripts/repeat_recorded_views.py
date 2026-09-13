"""Run current vision pipeline on the latest recorded real 3D views, without editing regions."""

import base64, json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
pid = json.loads((ROOT / "data/validation/project.json").read_text())["id"]
inputs = sorted(
    (ROOT / "data" / pid / "analyses").glob("*/input.json"), key=lambda f: f.stat().st_mtime
)
source = inputs[-1]
saved = json.loads(source.read_text("utf-8"))
views = [
    {
        "label": label,
        "image": base64.b64encode((source.parent / f"view-{i}.png").read_bytes()).decode(),
    }
    for i, label in enumerate(saved["inventory"]["view_order"])
]
with httpx.Client(base_url="http://127.0.0.1:8767/api", trust_env=False, timeout=30) as client:
    response = client.post(
        f"/projects/{pid}/analyze",
        json={"model": saved["model"], "views": views, "meshes": saved["meshes"]},
    )
    response.raise_for_status()
    result = response.json()
    result["source_views_job"] = source.parent.name
    (ROOT / "data/validation/vision-job.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
