"""Ablate extended thinking on an identical preserved physical-view request."""

import argparse, base64, json, sys, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.surface_plan import SurfaceDescription, decode_assignments
from backend.scene_understanding import apply_print_intent
from backend.closed_loop import write
from backend.vision import OLLAMA

p = argparse.ArgumentParser()
for key in ["source", "contract", "output"]:
    p.add_argument(key, type=Path)
p.add_argument("--model", default="qwen3.8:27b-q8_0")
p.add_argument("--kind", choices=["active", "focused"], default="active")
a = p.parse_args()
if a.output.exists():
    raise ValueError("Use a fresh output directory")
request = json.loads((a.source / "request.json").read_text("utf8"))
contract = apply_print_intent(json.loads(a.contract.read_text("utf8")))
keys = [r["key"] for r in contract["parts"]] + ["unresolved"]
schema = SurfaceDescription.model_json_schema()
schema["properties"].pop("height")
schema["required"] += ["role", "scenePart"]
schema["properties"]["scenePart"] = {"type": "string", "enum": keys}
image_paths = (
    [a.source / f"input-{i}.png" for i in range(3)]
    if a.kind == "active"
    else [a.source / "input.png", a.source / "model-context.png"]
)
images = [base64.b64encode(path.read_bytes()).decode() for path in image_paths]
payload = {
    "model": a.model,
    "stream": False,
    "think": False,
    "format": schema,
    "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 900},
    "messages": [{"role": "user", "content": request["prompt"], "images": images}],
}
started = time.perf_counter()
with httpx.Client(timeout=180, trust_env=False) as client:
    response = client.post(OLLAMA + "/api/chat", json=payload)
    response.raise_for_status()
    raw = response.json()
write(a.output / "raw.json", raw)
if raw.get("done_reason") == "length":
    raise ValueError("Incomplete compact decision")
group = json.loads(raw["message"]["content"])
classes = request["selection"]["classes"]
plan = decode_assignments(
    json.dumps(
        {
            "description": "Same evidence, compact decision",
            "groups": [group],
            "assignments": {str(i): 0 for i in classes},
            "warnings": [],
        }
    ),
    classes,
    scene_keys=keys,
)
report = {
    "source": str(a.source.resolve()),
    "thinking": False,
    "seconds": round(time.perf_counter() - started, 2),
    "surface": plan["surfaces"][0],
}
write(a.output / "result.json", report)
print(json.dumps(report, ensure_ascii=False), flush=True)
