"""Sequential, resumable card-pose batches. Importing this module runs no work."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MAX_SOURCE_BYTES = 160 * 1024 * 1024
DEFAULT_BLENDER = Path(r'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe')


def blender_executable():
    override = os.environ.get('SCULPTORS_HOARD_BLENDER') or os.environ.get('RELIEF_BLENDER')
    if override:
        return Path(override)
    if DEFAULT_BLENDER.is_file():
        return DEFAULT_BLENDER
    return Path(shutil.which('blender') or DEFAULT_BLENDER)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def copy_new(source, destination):
    """Exclusive creation prevents overwriting even if a collision races our checks."""
    with Path(source).open('rb') as incoming, Path(destination).open('xb') as outgoing:
        shutil.copyfileobj(incoming, outgoing)


def stop_owned_tree(process):
    if process is None or process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=15)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name != 'nt':
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=10)


def verified_delivery(report_path, source, reference, destinations):
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
        return (report.get('status') == 'succeeded'
                and report.get('source') == str(source)
                and report.get('source_sha256_before') == digest(source)
                and report.get('source_sha256_after') == report['source_sha256_before']
                and report.get('reference_sha256') == digest(reference)
                and all(path.is_file() and digest(path) == report['delivered_sha256'][key]
                        for key, path in destinations.items()))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def run_character(entry, args, blender):
    name = str(entry['name'])
    source = Path(entry['source']).expanduser().resolve()
    item = {'name': name, 'source': str(source), 'row': entry.get('row'),
            'provider': args.provider, 'model': args.model, 'cpu': args.cpu,
            'status': 'failed', 'started': time.time()}
    if not name or name in ('.', '..') or any(c in name for c in '<>:"/\\|?*'):
        return dict(item, status='skipped', reason='Unsafe character name'), False
    if not source.is_file() or source.suffix.lower() != '.blend':
        return dict(item, status='skipped', reason='Missing Blender source'), False
    if source.stat().st_size > MAX_SOURCE_BYTES:
        return dict(item, status='skipped', reason='Source exceeds initial 160 MiB limit'), False
    reference = source.parent / 'card.png'
    if not reference.is_file():
        return dict(item, status='skipped', reason='Missing card.png'), False
    destinations = {'blend': source.parent / f'{name}_card_pose.blend',
                    'preview': source.parent / f'{name}_card_pose.png'}
    report_path = source.parent / f'{name}_card_pose.report.json'
    if verified_delivery(report_path, source, reference, destinations):
        return dict(item, status='skipped', reason='Verified completed delivery', report=str(report_path)), False
    if report_path.exists() or any(path.exists() for path in destinations.values()):
        return dict(item, status='skipped', reason='Destination collision; existing files preserved'), False
    run_dir = args.output / name
    if run_dir.exists():
        return dict(item, status='skipped', reason='Existing run directory; use a new output directory to retry'), False
    run_dir.mkdir()
    item['run_dir'] = str(run_dir)
    process = None
    started = time.monotonic()
    interrupted = False
    try:
        item['source_sha256_before'] = digest(source)
        item['reference_sha256'] = digest(reference)
        copy_new(reference, run_dir / 'card.png')
        atomic_json(run_dir / 'config.json', {'run_dir': str(run_dir)})
        environment = os.environ.copy()
        environment['FIGURE_TOOLS_POSE_PROVIDER'] = args.provider
        environment['FIGURE_TOOLS_POSE_MODEL'] = args.model or ''
        environment['FIGURE_TOOLS_POSE_CPU'] = '1' if args.cpu else '0'
        if args.provider == 'codex' and args.model:
            environment['FIGURE_TOOLS_CODEX_MODEL'] = args.model
        command = [str(blender), '--background', '--factory-startup', '--disable-autoexec',
                   '--threads', '4', str(source), '--python-exit-code', '1', '--python',
                   str(ROOT / 'blender/reference_pose_worker.py'), '--', str(run_dir / 'config.json')]
        with (run_dir / 'worker.log').open('x', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=os.name != 'nt',
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                                       | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
            process.wait(timeout=900 if args.provider == 'ollama' else 480)
        if not (run_dir / 'result.json').is_file():
            raise RuntimeError(f'Worker exited with code {process.returncode} without a result. '
                               f'See log: {run_dir / "worker.log"}')
        result = json.loads((run_dir / 'result.json').read_text(encoding='utf-8'))
        item['worker_result'] = result
        if process.returncode != 0 or result.get('success') is not True:
            raise RuntimeError(result.get('error', f'Worker exited with code {process.returncode}'))
        item['source_sha256_after'] = digest(source)
        if item['source_sha256_after'] != item['source_sha256_before']:
            raise RuntimeError('Source hash changed; candidate will not be delivered')
        if digest(reference) != item['reference_sha256']:
            raise RuntimeError('Reference changed during generation; candidate will not be delivered')
        candidates = {'blend': run_dir / 'posed.blend', 'preview': run_dir / 'preview.png'}
        if not all(path.is_file() and path.stat().st_size > 0 for path in candidates.values()):
            raise RuntimeError('Worker output is incomplete')
        for key, candidate in candidates.items():
            copy_new(candidate, destinations[key])
        item['delivered_sha256'] = {key: digest(path) for key, path in destinations.items()}
        item['destinations'] = {key: str(path) for key, path in destinations.items()}
        item['status'] = 'succeeded'
        item['seconds'] = round(time.monotonic() - started, 2)
        # The completion marker is written last and also refuses overwrite.
        with report_path.open('x', encoding='utf-8') as stream:
            json.dump(item, stream, ensure_ascii=False, indent=2)
        item['report'] = str(report_path)
    except KeyboardInterrupt:
        interrupted = True
        item.update(status='cancelled', error='Interrupted by user')
    except Exception as exc:
        item.update(status='failed', error=str(exc))
    finally:
        try:
            stop_owned_tree(process)
        except (OSError, subprocess.SubprocessError) as exc:
            item.update(status='failed', cleanup_error=str(exc))
        if 'source_sha256_before' in item:
            try:
                item['source_sha256_after'] = digest(source)
            except OSError as exc:
                item['source_hash_error'] = str(exc)
            item['source_unchanged'] = item.get('source_sha256_after') == item['source_sha256_before']
        item['seconds'] = round(time.monotonic() - started, 2)
        atomic_json(run_dir / 'batch-result.json', item)
    return item, interrupted


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--provider', choices=('codex', 'ollama'), required=True)
    parser.add_argument('--model', default='')
    parser.add_argument('--cpu', action='store_true')
    parser.add_argument('--limit', type=int, default=3, help='Maximum new attempts (default: 3)')
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error('--limit must be positive')
    if args.provider == 'ollama' and not args.model.strip():
        parser.error('--model is required with --provider ollama')
    args.output = args.output.expanduser().resolve()
    blender = blender_executable()
    if not blender.is_file():
        parser.error('Set SCULPTORS_HOARD_BLENDER to the Blender executable')
    entries = json.loads(args.inventory.read_text(encoding='utf-8-sig'))['eligible']
    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / 'batch-report.json'
    summary = {'inventory': str(args.inventory.resolve()), 'provider': args.provider,
               'model': args.model, 'cpu': args.cpu, 'entries': []}
    if summary_path.exists():
        previous = json.loads(summary_path.read_text(encoding='utf-8'))
        history = previous.pop('previous_invocations', [])
        summary['previous_invocations'] = [*history, previous]
    attempts = 0
    for entry in entries:
        if attempts >= args.limit:
            break
        item, interrupted = run_character(entry, args, blender)
        summary['entries'].append(item)
        attempts += item['status'] != 'skipped'
        summary.update(attempts=attempts, updated=time.time())
        atomic_json(summary_path, summary)
        print(f"{item['name']}: {item['status']} - {item.get('error', item.get('reason', 'saved'))}", flush=True)
        if interrupted:
            return 130
    return 1 if any(item['status'] == 'failed' for item in summary['entries']) else 0


if __name__ == '__main__':
    sys.exit(main())
