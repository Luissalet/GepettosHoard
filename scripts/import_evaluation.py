"""Bring a preserved CLI evaluation into the app without rerunning inference."""

import json, shutil, sys, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import app as server


def import_run(source, blend, glb=None, name=None, project_id=None):
    source = Path(source).resolve()
    result = json.loads((source / "result.json").read_text("utf-8"))
    if result.get("sceneUnderstanding"):
        from backend.scene_understanding import apply_print_intent

        result["sceneUnderstanding"] = apply_print_intent(result["sceneUnderstanding"])
    title = name or Path(blend).stem.replace("-original-copy", "") + " · relieve con Figure Tools"
    p = server.read(project_id) if project_id else server.create(server.NewProject(name=title))
    pid = p["id"]
    jid = uuid.uuid4().hex[:12]
    if project_id:
        p["history"].append(
            {"action": "replace_evaluation", "previous": p.get("evaluation"), "source": str(source)}
        )
        p["name"] = title
        server.invalidate(p)
        server.save(p)
    target = server.folder(pid) / "evaluations" / jid
    shutil.copytree(source, target)
    for material, path in result["maps"].items():
        try:
            result["maps"][material] = str(target / Path(path).resolve().relative_to(source))
        except ValueError:
            pass
    (target / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    if not p.get("blenderSource"):
        server.ingest(pid, Path(blend).name, Path(blend).read_bytes())
    if glb:
        server.ingest(pid, Path(glb).name, Path(glb).read_bytes())
    elif not p.get("models"):
        from backend.preview_mesh import preview_glb

        mesh = preview_glb(json.loads((target / "scene/materials.json").read_text("utf-8")))
        if mesh:
            server.ingest(pid, "SculptHoard-preview.glb", mesh)
    for item in json.loads((target / "scene/materials.json").read_text("utf-8")):
        name = item["material"]
        p = server.read(pid)
        matches = [a for a in p["assets"] if a.get("material") == name]
        if not matches:
            server.ingest(pid, Path(item["source"]).name, Path(item["source"]).read_bytes())
            p = server.read(pid)
            a = p["assets"][-1]
        elif len(matches) == 1:
            a = matches[0]
        else:
            raise ValueError(f"Material ambiguo: {name}")
        a["material"] = name
        a["regions"] = result["plans"][name]
        a["approved"] = False
        src = target / "surfaces" / name / "masks.npz"
        shutil.copy2(src, server.folder(pid) / f"{a['id']}.npz")
        import numpy as np

        with np.load(src) as masks:
            a["workHeight"], a["workWidth"] = masks["labels"].shape
        a["version"] += 1
        server.save(p)
    p = server.read(pid)
    p["evaluation"] = {
        "id": jid,
        "final": result["final"],
        "hasFinished": result.get("hasFinished", False),
        "targetMaterials": result.get("targetMaterials", []),
        "hasDetails": result.get("hasDetails", False),
        "aiAcceptable": result["aiAcceptable"],
        "sceneUnderstanding": result.get("sceneUnderstanding"),
        "revision": p["revision"],
        "review": result.get("selectedReview", result["iterations"][-1]["review"]),
    }
    server.save(p)
    return p


if __name__ == "__main__":
    p = import_run(*sys.argv[1:])
    print(
        json.dumps(
            {
                "id": p["id"],
                "assets": [{k: a[k] for k in ["id", "name", "material"]} for a in p["assets"]],
            }
        )
    )
