import copy
import numpy as np
from backend.pattern_contrast import preserve_patterns


def region(i, cluster, color, role="decoration", height=160):
    return {
        "id": i,
        "cluster": cluster,
        "color": color,
        "role": role,
        "height": height,
        "name": f"Surface {i}",
        "semanticGroup": f"s{i}",
        "heightGroup": f"h{i}",
    }


def test_print_background_continues_cloth_and_inner_marks_survive_antialiasing():
    labels = np.zeros((128, 128), np.int16)
    labels[5:20, 5:20] = 1
    labels[32:120, 32:120] = 2
    labels[62:80, 62:80] = 4
    labels[64:78, 64:78] = 3
    regions = [
        region(0, 0, [10, 40, 130], "fabric", 128),
        region(1, 0, [10, 40, 130]),
        region(2, 1, [180, 20, 20]),
        region(3, 2, [240, 240, 240]),
        region(4, 3, [190, 100, 100]),
    ]
    changes = preserve_patterns(labels, regions)
    assert regions[1]["height"] == 128 and regions[1]["heightGroup"] == "h0"
    assert regions[2]["height"] == 160 and regions[3]["height"] == 192
    assert changes
    saved = copy.deepcopy(regions)
    assert preserve_patterns(labels, regions) == [] and saved == regions


def test_shared_color_never_reclassifies_non_printed_anatomy():
    labels = np.zeros((32, 32), np.int16)
    labels[8:24, 8:24] = 1
    regions = [region(0, 0, [20, 20, 20], "fabric", 128), region(1, 0, [20, 20, 20], "pupil", 104)]
    saved = copy.deepcopy(regions)
    assert preserve_patterns(labels, regions) == [] and regions == saved
