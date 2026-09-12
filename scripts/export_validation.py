import json, time, zipfile
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
pid = json.loads((ROOT / "data/validation/project.json").read_text())["id"]
with httpx.Client(base_url="http://127.0.0.1:8766/api", timeout=240, trust_env=False) as client:
    p = client.get(f"/projects/{pid}").json()
    r = client.post(f"/projects/{pid}/apply", json={"relations": p["proposal"]["relations"]})
    r.raise_for_status()
    start = time.perf_counter()
    r = client.get(f"/projects/{pid}/export")
    r.raise_for_status()
    path = ROOT / "data/validation/Zucker-relief.zip"
    path.write_bytes(r.content)
    out = ROOT / "data/validation/maps"
    out.mkdir(exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        assert all(Path(n).name == n for n in archive.namelist())
        archive.extractall(out)
        manifest = json.loads(archive.read("relief-project.json"))
    report = {
        "seconds": round(time.perf_counter() - start, 3),
        "zip_bytes": len(r.content),
        "textures": [
            {"name": a["name"], "width": a["width"], "height": a["height"]}
            for a in manifest["textures"]
        ],
        "semantic_review": "VLM proposal applied for pipeline testing; not approved as correct or print-ready",
    }
    (ROOT / "data/validation/export-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
