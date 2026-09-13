import json, time
from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
pid = json.loads((root / "data/validation/project.json").read_text())["id"]
with httpx.Client(base_url="http://127.0.0.1:8767/api", timeout=30, trust_env=False) as client:
    for _ in range(120):
        job = client.get(f"/projects/{pid}/analysis-status").json()
        if job and job["status"] in {"done", "error"}:
            print(json.dumps(job, ensure_ascii=False))
            break
        time.sleep(5)
    else:
        raise RuntimeError("Vision job did not complete in 10 minutes")
    if job["status"] == "done":
        p = client.get(f"/projects/{pid}").json()
        print(
            json.dumps(
                {
                    "summary": p["proposal"]["summary"],
                    "relations": p["proposal"]["relations"],
                    "warnings": p["proposal"]["warnings"],
                    "duration": p["proposal"]["duration"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
