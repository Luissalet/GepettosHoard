"""Install/enable this project's bridge in Blender; preserve other preferences."""

import bpy
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "blender/relief_bridge.py"
bpy.ops.preferences.addon_install(filepath=str(source), overwrite=True)
bpy.ops.preferences.addon_enable(module="relief_bridge")
assert "relief_bridge" in bpy.context.preferences.addons
bpy.ops.wm.save_userpref()
print("RELIEF_BRIDGE_INSTALLED", bpy.app.version_string)
