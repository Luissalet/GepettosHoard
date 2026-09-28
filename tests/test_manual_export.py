import io
import json
import zipfile
import numpy as np
import pytest
from PIL import Image
from backend.external_mcp import Store
from backend.manual_export import export_manual_zip


def test_manual_export_has_exact_rgb_and_alpha_without_ordinal_height_maps(tmp_path):
    source = tmp_path / 'body.png'
    pixels = np.full((32,32,4), [30,40,50,255], dtype=np.uint8)
    pixels[0,:,3] = np.arange(32)
    Image.fromarray(pixels).save(source)
    store = Store(str(tmp_path/'library'))
    p = store.import_file(store.create('Manual')['id'],str(source))
    a=p['assets'][0]
    p=store.prepare_anchors(p['id'],a['id'],[[30,40,50]],p['revision'],256)
    a=p['assets'][0]
    for r in a['regions']: r['displacementColor']=[255,207,207]
    output=export_manual_zip(p,store.folder(p['id']))
    with zipfile.ZipFile(output) as archive:
        assert not any('height.png' in n for n in archive.namelist())
        m=json.loads(archive.read('manual-palette.json'))
        assert m['profile']=='manual-rgb-preserve-scene'
        image=np.array(Image.open(io.BytesIO(archive.read(m['textures'][0]['file']))))
        assert np.array_equal(image[:,:,3],pixels[:,:,3])
        assert np.all(image[:,:,:3]==[255,207,207])
    del a['regions'][0]['displacementColor']
    with pytest.raises(ValueError): export_manual_zip(p,store.folder(p['id']))
