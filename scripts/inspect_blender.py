"""Read a Blender project, inventory Figure Tools, export a lightweight GLB copy.
Run through Blender in background; never saves over the source file.
"""

import bpy
import json
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parents[1] / "data" / "validation"
OUT.mkdir(parents=True, exist_ok=True)
report = {
    "source": bpy.data.filepath,
    "blender": bpy.app.version_string,
    "meshes": [],
    "images": [],
    "operators": [],
    "groups": [],
}
for obj in bpy.data.objects:
    if obj.type == "MESH":
        report["meshes"].append(
            {
                "name": obj.name,
                "vertices": len(obj.data.vertices),
                "polygons": len(obj.data.polygons),
                "uv": [l.name for l in obj.data.uv_layers],
                "materials": [m.name for m in obj.data.materials if m],
                "modifiers": [{"name": m.name, "type": m.type} for m in obj.modifiers],
            }
        )
for im in bpy.data.images:
    report["images"].append(
        {"name": im.name, "path": bpy.path.abspath(im.filepath), "size": list(im.size)}
    )
for op in dir(bpy.ops.figure_tools):
    try:
        rna = getattr(bpy.ops.figure_tools, op).get_rna_type()
        report["operators"].append(
            {"name": op, "properties": [p.identifier for p in rna.properties]}
        )
    except Exception:
        pass
for group in bpy.data.node_groups:
    if any(s in group.name.lower() for s in ["displace", "figure", "filter", "manifold"]):
        sockets = [
            {"name": s.name, "id": s.identifier, "type": s.socket_type, "direction": s.in_out}
            for s in group.interface.items_tree
            if s.item_type == "SOCKET"
        ]
        report["groups"].append({"name": group.name, "sockets": sockets})
(OUT / "blender-inventory.json").write_text(json.dumps(report, indent=2), "utf-8")
# Resolve relative paths before saving the copied project.
for im in bpy.data.images:
    if im.source == "FILE":
        im.filepath = bpy.path.abspath(im.filepath)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Zucker-original-copy.blend"))
# Bound web-preview textures while retaining original texture files on disk.
for im in bpy.data.images:
    if im.type == "IMAGE" and max(im.size) > 1536:
        factor = 1536 / max(im.size)
        im.scale(max(1, int(im.size[0] * factor)), max(1, int(im.size[1] * factor)))
try:
    bpy.ops.export_scene.gltf(
        filepath=str(OUT / "Zucker-preview.glb"),
        export_format="GLB",
        export_animations=False,
        export_skins=False,
        export_apply=True,
    )
    report["glb"] = "Zucker-preview.glb"
except Exception as e:
    report["export_error"] = str(e)
(OUT / "blender-inventory.json").write_text(json.dumps(report, indent=2), "utf-8")
print("RELIEF_INVENTORY", json.dumps(report))
