"""Exercise ZIP import through the installed operator, not only its helper."""

import bpy, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
start = time.perf_counter()
obj = next(o for o in bpy.data.objects if o.type == "MESH")
bpy.context.view_layer.objects.active = obj
result = bpy.ops.relief.import_maps(
    filepath=str(ROOT / "data/validation/Zucker-relief.zip"), strength=0.0015, subdivision=2
)
assert result == {"FINISHED"}, result
mod = next(m for m in obj.modifiers if m.name.startswith("Dynamic_Displacement"))
assert mod.node_group.name.startswith("ReliefStudio_FigureTools")
report = {
    "result": "passed",
    "seconds": round(time.perf_counter() - start, 2),
    "operator": "relief.import_maps",
    "node_group": mod.node_group.name,
}
(ROOT / "data/validation/blender-import-report.json").write_text(
    json.dumps(report, indent=2), "utf-8"
)
print("RELIEF_ZIP_IMPORT_TEST", json.dumps(report))
