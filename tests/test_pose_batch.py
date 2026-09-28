"""Batch delivery invariants; no Blender or inference processes are started."""
import argparse
import json
from pathlib import Path

import pytest

from scripts import pose_batch as batch


@pytest.fixture
def scene(tmp_path, monkeypatch):
    character = tmp_path / 'Keaton'
    character.mkdir()
    source = character / 'Untitled.blend'
    source.write_bytes(b'original Blender scene')
    (character / 'card.png').write_bytes(b'reference image')
    output = tmp_path / 'runs'
    output.mkdir()
    blender = tmp_path / 'blender.exe'
    blender.write_bytes(b'not an executable')
    args = argparse.Namespace(output=output, provider='ollama', model='local-vision', cpu=True)
    entry = {'name': 'Keaton', 'row': 158, 'source': str(source)}

    def forbidden_process(*_args, **_kwargs):
        pytest.fail('Unexpected process launch')

    monkeypatch.setattr(batch.subprocess, 'Popen', forbidden_process)
    return entry, args, blender, source


def fake_worker(monkeypatch, *, success=True, source_mutation=None):
    calls = []

    class Worker:
        def __init__(self, command, **kwargs):
            self.returncode = None
            self.config = json.loads(Path(command[-1]).read_text(encoding='utf-8'))
            calls.append((command, kwargs))

        def wait(self, timeout):
            assert timeout == 900
            run_dir = Path(self.config['run_dir'])
            # A failed worker may leave partial candidates; neither may be delivered.
            (run_dir / 'posed.blend').write_bytes(b'generated scene')
            (run_dir / 'preview.png').write_bytes(b'generated preview')
            (run_dir / 'result.json').write_text(json.dumps(
                {'success': success, 'error': 'Unsupported rig'}), encoding='utf-8')
            if source_mutation:
                source_mutation.write_bytes(b'changed by another process')
            self.returncode = 0 if success else 1
            return self.returncode

        def poll(self):
            return self.returncode

    monkeypatch.setattr(batch.subprocess, 'Popen', Worker)
    return calls


def test_success_delivers_copy_and_preserves_source(scene, monkeypatch):
    entry, args, blender, source = scene
    original = source.read_bytes()
    calls = fake_worker(monkeypatch)
    result, interrupted = batch.run_character(entry, args, blender)
    assert result['status'] == 'succeeded' and not interrupted
    assert source.read_bytes() == original
    assert result['source_sha256_before'] == result['source_sha256_after']
    assert result['source_unchanged'] is True
    assert (source.parent / 'Keaton_card_pose.blend').read_bytes() == b'generated scene'
    assert (source.parent / 'Keaton_card_pose.png').read_bytes() == b'generated preview'
    assert (args.output / 'Keaton/card.png').read_bytes() == b'reference image'
    report = json.loads((source.parent / 'Keaton_card_pose.report.json').read_text())
    assert report['delivered_sha256']['blend'] == batch.digest(source.parent / 'Keaton_card_pose.blend')
    command, options = calls[0]
    assert '--disable-autoexec' in command and str(source) in command
    assert options['env']['FIGURE_TOOLS_POSE_PROVIDER'] == 'ollama'
    assert options['env']['FIGURE_TOOLS_POSE_MODEL'] == 'local-vision'
    assert options['env']['FIGURE_TOOLS_POSE_CPU'] == '1'
    assert (args.output / 'Keaton/worker.log').is_file()


def test_rerun_skips_verified_delivery_without_worker(scene, monkeypatch):
    entry, args, blender, _ = scene
    calls = fake_worker(monkeypatch)
    batch.run_character(entry, args, blender)
    result, _ = batch.run_character(entry, args, blender)
    assert result['status'] == 'skipped'
    assert result['reason'] == 'Verified completed delivery'
    assert len(calls) == 1


def test_unverified_collision_never_overwrites(scene):
    entry, args, blender, source = scene
    destination = source.parent / 'Keaton_card_pose.blend'
    destination.write_bytes(b'user work')
    result, _ = batch.run_character(entry, args, blender)
    assert result['status'] == 'skipped'
    assert 'collision' in result['reason']
    assert destination.read_bytes() == b'user work'
    assert not (args.output / 'Keaton').exists()


def test_failed_worker_does_not_deliver_partial_candidates(scene, monkeypatch):
    entry, args, blender, source = scene
    fake_worker(monkeypatch, success=False)
    result, _ = batch.run_character(entry, args, blender)
    assert result['status'] == 'failed'
    assert result['error'] == 'Unsupported rig'
    assert not list(source.parent.glob('*_card_pose*'))
    assert (args.output / 'Keaton/posed.blend').exists()
    persisted = json.loads((args.output / 'Keaton/batch-result.json').read_text())
    assert persisted['status'] == 'failed' and persisted['source_unchanged']


def test_large_scene_skips_without_opening_worker(scene, monkeypatch):
    entry, args, blender, _ = scene
    monkeypatch.setattr(batch, 'MAX_SOURCE_BYTES', 1)
    result, _ = batch.run_character(entry, args, blender)
    assert result['status'] == 'skipped'
    assert '160 MiB' in result['reason']
    assert not (args.output / 'Keaton').exists()


def test_previous_report_retained_across_invocations(scene, monkeypatch, tmp_path):
    entry, args, blender, _ = scene
    monkeypatch.setenv('SCULPTORS_HOARD_BLENDER', str(blender))
    inventory = tmp_path / 'inventory.json'
    inventory.write_text(json.dumps({'eligible': [entry]}))
    previous = {'entries': [{'name': 'Earlier', 'status': 'failed'}], 'attempts': 1}
    (args.output / 'batch-report.json').write_text(json.dumps(previous))
    calls = fake_worker(monkeypatch)
    command = ['--inventory', str(inventory), '--output', str(args.output),
               '--provider', 'ollama', '--model', 'local-vision', '--cpu']
    assert batch.main(command) == 0
    report = json.loads((args.output / 'batch-report.json').read_text())
    assert report['previous_invocations'] == [previous]
    assert report['entries'][0]['status'] == 'succeeded'
    assert batch.main(command) == 0
    resumed = json.loads((args.output / 'batch-report.json').read_text())
    assert resumed['previous_invocations'][0] == previous
    assert resumed['previous_invocations'][1]['entries'][0]['status'] == 'succeeded'
    assert resumed['entries'][0]['status'] == 'skipped'
    assert len(calls) == 1
    assert not list(args.output.glob('batch-report.json.*.tmp'))


def test_source_change_blocks_delivery(scene, monkeypatch):
    entry, args, blender, source = scene
    fake_worker(monkeypatch, source_mutation=source)
    result, _ = batch.run_character(entry, args, blender)
    assert result['status'] == 'failed'
    assert result['source_unchanged'] is False
    assert 'hash changed' in result['error']
    assert not list(source.parent.glob('*_card_pose*'))


def test_modified_delivery_is_collision_not_verified_resume(scene, monkeypatch):
    entry, args, blender, source = scene
    calls = fake_worker(monkeypatch)
    batch.run_character(entry, args, blender)
    (source.parent / 'Keaton_card_pose.blend').write_bytes(b'user-edited candidate')
    result, _ = batch.run_character(entry, args, blender)
    assert result['status'] == 'skipped' and 'collision' in result['reason']
    assert len(calls) == 1


def test_blender_five_precedes_path_and_explicit_override_wins(tmp_path, monkeypatch):
    installed = tmp_path / 'Blender5.exe'
    installed.touch()
    monkeypatch.setattr(batch, 'DEFAULT_BLENDER', installed)
    monkeypatch.delenv('SCULPTORS_HOARD_BLENDER', raising=False)
    monkeypatch.delenv('RELIEF_BLENDER', raising=False)
    monkeypatch.setattr(batch.shutil, 'which', lambda _: str(tmp_path / 'Blender4.exe'))
    assert batch.blender_executable() == installed
    override = tmp_path / 'my-blender.exe'
    monkeypatch.setenv('SCULPTORS_HOARD_BLENDER', str(override))
    assert batch.blender_executable() == override


def test_missing_worker_result_names_exit_code_and_log(scene, monkeypatch):
    entry, args, blender, source = scene

    class CrashedWorker:
        returncode = 3

        def __init__(self, *_args, **_kwargs):
            pass

        def wait(self, timeout):
            return self.returncode

        def poll(self):
            return self.returncode

    monkeypatch.setattr(batch.subprocess, 'Popen', CrashedWorker)
    result, _ = batch.run_character(entry, args, blender)
    assert result['status'] == 'failed'
    assert 'code 3' in result['error']
    assert str(args.output / 'Keaton/worker.log') in result['error']
    assert not list(source.parent.glob('*_card_pose*'))
