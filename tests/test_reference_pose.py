import io
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from backend import reference_pose as pose


@pytest.fixture
def setup(tmp_path, monkeypatch):
    executable = tmp_path / 'blender.exe'
    executable.touch()
    monkeypatch.setattr(pose, 'BLENDER', executable)
    monkeypatch.setattr(pose, 'codex_executable', lambda: 'codex')
    monkeypatch.setattr(pose.PoseQueue, 'work', lambda *args: None)
    server = SimpleNamespace(DATA=tmp_path / 'data')
    app = FastAPI()
    app.include_router(pose.router_for(server))
    character = tmp_path / 'Axel'
    character.mkdir()
    source = character / 'Axel.blend'
    source.write_bytes(b'original scene fixture')
    Image.new('RGB', (64, 80)).save(character / 'card.png')
    yield TestClient(app), server.pose_queue, source
    server.pose_queue.pool.shutdown()


def test_default_card_cancel_and_recovery(setup):
    client, queue, source = setup
    response = client.post('/api/pose-runs', data={'blend_path': str(source)})
    assert response.status_code == 200
    run = response.json()
    assert run['has_reference'] and run['reference_name'] == 'card.png'
    assert client.post('/api/pose-runs', data={'blend_path': str(source)}).status_code == 409
    assert client.get(f"/api/pose-runs/{run['id']}/files/worker.log").status_code == 404
    assert client.get(f"/api/pose-runs/{run['id']}/files/posed.blend").status_code == 409
    assert client.post(f"/api/pose-runs/{run['id']}/cancel").json()['status'] == 'cancelled'
    second = client.post('/api/pose-runs', data={'blend_path': str(source)}).json()
    recovered = pose.PoseQueue(queue.root)
    assert recovered.read(second['id'])['status'] == 'failed'
    recovered.pool.shutdown()
    assert source.read_bytes() == b'original scene fixture'


def test_upload_validation_and_non_overwriting_export(setup):
    client, queue, source = setup
    assert client.post('/api/pose-runs', data={'blend_path': str(source)},
                       files={'reference': ('bad.png', b'bad')}).status_code == 400
    image = io.BytesIO()
    Image.new('RGB', (80, 96)).save(image, format='JPEG')
    response = client.post('/api/pose-runs', data={'blend_path': str(source)},
                           files={'reference': ('reference.jpg', image.getvalue())})
    assert response.status_code == 200
    rid = response.json()['id']
    assert Image.open(queue.folder(rid) / 'card.png').format == 'PNG'
    # Fixture output tests transport/export only; the separate Blender E2E tests generation.
    (queue.folder(rid) / 'posed.blend').write_bytes(b'candidate fixture')
    queue.update(rid, status='succeeded')
    assert client.post(f'/api/pose-runs/{rid}/export', json={'destination': str(source)}).status_code == 409
    target = source.with_name('candidate.blend')
    assert client.post(f'/api/pose-runs/{rid}/export', json={'destination': str(target)}).status_code == 200
    assert target.read_bytes() == b'candidate fixture'
    assert source.read_bytes() == b'original scene fixture'


def test_unknown_provider_and_missing_source(setup):
    client, _, source = setup
    assert client.post('/api/pose-runs', data={'provider': 'other'}).status_code == 400
    assert client.post('/api/pose-runs', data={'blend_path': str(source.with_name('missing.blend'))}).status_code == 400
    assert client.get('/api/pose-runs/not-an-id').status_code == 404
