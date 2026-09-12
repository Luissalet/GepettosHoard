"""Integration test executed by real Blender with the installed Figure Tools."""

import bpy, json, sys, time, math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
from relief_bridge import apply_export

OUT = ROOT / "data/validation"
manifest = json.loads((OUT / "maps/relief-project.json").read_text("utf-8"))
obj = next(o for o in bpy.data.objects if o.type == "MESH")
start = time.perf_counter()
report = apply_export(obj, manifest, OUT / "maps", strength=0.0015, subdivision=2)
report["setup_seconds"] = round(time.perf_counter() - start, 3)
mod = next(m for m in obj.modifiers if m.name.startswith("Dynamic_Displacement"))
socket = {
    s.name: s.identifier
    for s in mod.node_group.interface.items_tree
    if s.item_type == "SOCKET" and s.in_out == "INPUT"
}


def evaluated():
    obj.update_tag()
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    coords = [v.co.copy() for v in mesh.vertices]
    nfaces = len(mesh.polygons)
    evaluated.to_mesh_clear()
    return coords, nfaces


mod[socket["Scale"]] = 0.0
baseline, basefaces = evaluated()
mod[socket["Scale"]] = 0.0015
displaced, faces = evaluated()
assert len(displaced) > 0 and faces > 0, "Figure Tools returned empty geometry"
assert len(displaced) == len(baseline), "Vertex correspondence unexpectedly changed"
delta = [(a - b).length for a, b in zip(displaced, baseline)]
assert all(math.isfinite(v) for v in delta)
report.update(
    vertices=len(displaced),
    faces=faces,
    max_displacement=max(delta),
    moved_vertices=sum(d > 1e-7 for d in delta),
    source_original_untouched=True,
)
assert report["moved_vertices"] > 0, "The non-neutral test regions did not affect the mesh"
# Verify exact neutral maps produce no drift through the adapter.
saved = {}
neutral = bpy.data.images.new(
    "Relief_Test_Neutral", width=1, height=1, alpha=True, float_buffer=True
)
neutral.colorspace_settings.name = "Non-Color"
neutral.pixels = [128 / 255, 128 / 255, 128 / 255, 1]
for name, key in socket.items():
    if name.startswith("Image"):
        saved[key] = mod[key]
        mod[key] = neutral
flat, _ = evaluated()
flatdelta = max((a - b).length for a, b in zip(flat, baseline))
report["neutral_drift"] = flatdelta
assert flatdelta < 1e-6, f"Neutral drift: {flatdelta}"
for key, image in saved.items():
    mod[key] = image
obj.update_tag()
bpy.context.view_layer.update()
# Store an editable diagnostic copy; keep installed source addon/groups unchanged.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Zucker-ReliefStudio-test.blend"))
bpy.ops.wm.stl_export(
    filepath=str(OUT / "Zucker-ReliefStudio-test.stl"),
    export_selected_objects=True,
    apply_modifiers=True,
)
report["stl_bytes"] = (OUT / "Zucker-ReliefStudio-test.stl").stat().st_size
# Render an inspection image with actual Blender geometry.
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.resolution_x = 1000
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
world = bpy.data.worlds.new("Relief_Inspection_World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.16, 0.18, 0.17, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
scene.world = world
bounds = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
center = sum(bounds, Vector()) / 8
size = max(max(v[i] for v in bounds) - min(v[i] for v in bounds) for i in range(3))
camera_data = bpy.data.cameras.new("Relief_Inspection_Camera")
camera = bpy.data.objects.new("Relief_Inspection_Camera", camera_data)
scene.collection.objects.link(camera)
camera.location = center + Vector((size * 1.3, -size * 1.9, size * 0.85))
camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
camera_data.type = "ORTHO"
camera_data.ortho_scale = size * 1.25
scene.camera = camera
for name, offset, power in [
    ("Key", (1, -1, 2), 80),
    ("Fill", (-1, -0.5, 0.5), 35),
    ("Rim", (0, 1, 1.5), 65),
]:
    data = bpy.data.lights.new("Relief_" + name, "AREA")
    data.energy = power * max(size * size, 0.01)
    data.shape = "DISK"
    data.size = size * 1.5
    light = bpy.data.objects.new("Relief_" + name, data)
    scene.collection.objects.link(light)
    light.location = center + Vector(offset) * size
    light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
scene.render.filepath = str(OUT / "Zucker-Blender-validation.png")
bpy.ops.render.render(write_still=True)
report["render"] = "Zucker-Blender-validation.png"
report["total_seconds"] = round(time.perf_counter() - start, 2)
(OUT / "figure-tools-report.json").write_text(json.dumps(report, indent=2), "utf-8")
print("RELIEF_FIGURE_TOOLS_TEST", json.dumps(report))
