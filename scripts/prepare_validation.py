from pathlib import Path
import json, time
import httpx

ROOT = Path(__file__).resolve().parents[1]
base = Path(r"E:\Modelos\Animal Crossing\ACNH_2.0.0\Characters\Zucker\upscaled_chain")
with httpx.Client(base_url="http://127.0.0.1:8766/api", timeout=180, trust_env=False) as client:
    response = client.post("/projects", json={"name": "Zucker · validación 4K / 8K"})
    response.raise_for_status()
    p = response.json()
    paths = [ROOT / "data/validation/Zucker-preview.glb"] + [
        base / n for n in ["mBody_Alb.png", "mEye_Alb.0.png", "mBeak_Alb.png", "mTops_Alb.png"]
    ]
    files = [
        ("files", (path.name, path.read_bytes(), "application/octet-stream")) for path in paths
    ]
    r = client.post(f"/projects/{p['id']}/import", files=files)
    r.raise_for_status()
    p = r.json()["project"]
    metrics = []
    for a in p["assets"]:
        start = time.perf_counter()
        r = client.post(
            f"/projects/{p['id']}/assets/{a['id']}/segment", json={"clusters": 5, "resolution": 768}
        )
        r.raise_for_status()
        p = r.json()
        aa = next(x for x in p["assets"] if x["id"] == a["id"])
        metrics.append(
            {
                "texture": a["name"],
                "size": [a["width"], a["height"]],
                "seconds": round(time.perf_counter() - start, 3),
                "regions": len(aa["regions"]),
            }
        )
        print(json.dumps(metrics[-1]), flush=True)
    result = {"id": p["id"], "metrics": metrics}
    (ROOT / "data/validation/project.json").write_text(json.dumps(result, indent=2))
    print("PROJECT", p["id"])
