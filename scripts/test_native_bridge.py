"""Run inside Blender against an extracted native export; originals stay untouched."""

import bpy, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
from relief_bridge import apply_export

directory = Path(sys.argv[-1])
manifest = json.loads((directory / "relief-project.json").read_text("utf-8"))
obj = next(
    o
    for o in bpy.data.objects
    if o.type == "MESH" and any(m.name.startswith("Dynamic_Displacement") for m in o.modifiers)
)
r = apply_export(obj, manifest, directory)
mod = next(m for m in obj.modifiers if m.name.startswith("Dynamic_Displacement"))
groups = [
    n.node_tree
    for n in mod.node_group.nodes
    if n.type == "GROUP" and n.node_tree and "ImageDisplacement" in n.node_tree.name
]
assert groups and all(g.name == "ImageDisplacement" for g in groups)
assert r["strength"] == 0.2 and r["subdivision"] == 4 and len(r["bound"]) == 4
assert all(
    "SignedHeight" not in (n.node_tree.name if n.type == "GROUP" and n.node_tree else "")
    for g in groups
    for n in g.nodes
)
bpy.ops.wm.save_as_mainfile(filepath=str(directory / "native-import.blend"))
(directory / "bridge-test.json").write_text(json.dumps({"passed": True, **r}, indent=2), "utf-8")
print("NATIVE_BRIDGE_PASSED", flush=True)
