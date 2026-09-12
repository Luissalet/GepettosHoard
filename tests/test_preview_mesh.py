import json
import struct
import numpy as np
import pytest
from backend.preview_mesh import preview_glb


def test_preview_preserves_material_identity_uvs_and_world_pose():
    source = [
        {
            "material": "shirt",
            "world_triangles": [[[1, 2, 3], [4, 2, 3], [1, 2, 6]]],
            "triangles": [[[0.1, 0.2], [0.7, 0.2], [0.1, 0.9]]],
        }
    ]
    result = preview_glb(source)
    assert struct.unpack_from("<4sII", result) == (b"glTF", 2, len(result))
    length, kind = struct.unpack_from("<I4s", result, 12)
    assert kind == b"JSON"
    doc = json.loads(result[20 : 20 + length])
    data = result[28 + length :]
    assert doc["materials"][0]["name"] == "shirt"

    def values(index, components):
        view = doc["bufferViews"][doc["accessors"][index]["bufferView"]]
        return np.frombuffer(
            data, dtype="<f4", count=view["byteLength"] // 4, offset=view["byteOffset"]
        ).reshape(-1, components)

    np.testing.assert_allclose(values(0, 3), [[1, 3, -2], [4, 3, -2], [1, 6, -2]])
    np.testing.assert_allclose(values(2, 2), np.asarray(source[0]["triangles"]).reshape(-1, 2))
    assert preview_glb([]) is None
    source[0]["world_triangles"][0][0][0] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        preview_glb(source)
