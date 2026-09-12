"""Small generated fixture, for validating packed-texture inspection only."""

import bpy, sys
from pathlib import Path

out = Path(sys.argv[-1])
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_plane_add()
obj = bpy.context.object
mat = bpy.data.materials.new("PackedMaterial")
mat.use_nodes = True
obj.data.materials.append(mat)
image = bpy.data.images.new("PackedTexture", width=32, height=16)
image.generated_color = (0.5, 0.2, 0.1, 1)
path = out / "generated.png"
image.save_render(str(path))
image = bpy.data.images.load(str(path))
image.pack()
image.filepath = "//intentionally-unavailable.png"
node = mat.node_tree.nodes.new("ShaderNodeTexImage")
node.image = image
mat.node_tree.links.new(
    node.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"]
)
bpy.ops.wm.save_as_mainfile(filepath=str(out / "packed.blend"))
