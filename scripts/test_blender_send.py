"""Exercise the actual Blender send operator against the running local API."""

import bpy, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
import relief_bridge as bridge

before_objects = set(bpy.data.objects.keys())
before_materials = set(bpy.data.materials.keys())
before_images = {i.name: tuple(i.size) for i in bpy.data.images}
before_selection = {o.name for o in bpy.context.selected_objects}
before_active = bpy.context.view_layer.objects.active
urls = []
bridge.webbrowser.open = lambda url: urls.append(url)
bridge.register()
start = time.perf_counter()
result = bpy.ops.relief.send_scene()
assert result == {"FINISHED"}, result
assert set(bpy.data.objects.keys()) == before_objects
assert set(bpy.data.materials.keys()) == before_materials
assert {i.name: tuple(i.size) for i in bpy.data.images} == before_images
assert {o.name for o in bpy.context.selected_objects} == before_selection
assert bpy.context.view_layer.objects.active == before_active
pid = urls[0].split("project=")[1]
project = bridge.request("/projects/" + pid)
assert len(project["assets"]) == 4
assert max(a["width"] for a in project["assets"]) == 8192
assert project["models"]
report = {
    "result": "passed",
    "seconds": round(time.perf_counter() - start, 2),
    "project": pid,
    "original_datablocks_and_selection_preserved": True,
    "textures": [{k: a[k] for k in ["name", "width", "height"]} for a in project["assets"]],
}
(ROOT / "data/validation/blender-send-report.json").write_text(
    json.dumps(report, indent=2), "utf-8"
)
print("RELIEF_SEND_TEST", json.dumps(report))
