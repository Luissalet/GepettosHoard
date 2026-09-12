import bpy, json, os, sys
from pathlib import Path

addon = Path(os.environ["APPDATA"]) / "Blender Foundation/Blender/5.0/scripts/addons"
sys.path.insert(0, str(addon))
from figure_tools.dynamic_displacement import ensure_node_group

ensure_node_group("ImageDisplacement")
group = bpy.data.node_groups["ImageDisplacement"]
data = {
    "sockets": [
        {
            "name": s.name,
            "id": s.identifier,
            "direction": s.in_out,
            "default": str(getattr(s, "default_value", "")),
        }
        for s in group.interface.items_tree
        if s.item_type == "SOCKET"
    ],
    "nodes": [
        {
            "name": n.name,
            "type": n.bl_idname,
            "operation": getattr(n, "operation", ""),
            "inputs": [
                {"name": i.name, "value": str(getattr(i, "default_value", ""))}
                for i in n.inputs
                if not i.is_linked
            ],
        }
        for n in group.nodes
    ],
    "links": [
        f"{l.from_node.name}.{l.from_socket.name} -> {l.to_node.name}.{l.to_socket.name}"
        for l in group.links
    ],
}
out = Path(__file__).resolve().parents[1] / "data/validation/figure-tools-nodes.json"
out.write_text(json.dumps(data, indent=2))
data["nested"] = {
    n.node_tree.name: {
        "nodes": [
            {
                "name": x.name,
                "type": x.bl_idname,
                "operation": getattr(x, "operation", ""),
                "inputs": [
                    {"name": s.name, "value": str(getattr(s, "default_value", ""))}
                    for s in x.inputs
                    if not s.is_linked
                ],
            }
            for x in n.node_tree.nodes
        ],
        "links": [
            f"{l.from_node.name}.{l.from_socket.name} -> {l.to_node.name}.{l.to_socket.name}"
            for l in n.node_tree.links
        ],
    }
    for n in group.nodes
    if n.type == "GROUP"
}
out.write_text(json.dumps(data, indent=2))
print(json.dumps(data))
