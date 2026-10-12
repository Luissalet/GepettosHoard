import asyncio
import errno
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from backend import project_lock
from backend.project_lock import ProjectLock

ROOT = Path(__file__).resolve().parents[1]


def test_reentrant_threads_and_exception_release(tmp_path):
    lock = ProjectLock(tmp_path)
    entered = threading.Event()
    finished = threading.Event()

    def worker():
        entered.set()
        with lock:
            finished.set()

    with pytest.raises(ValueError):
        with lock:
            with lock:
                thread = threading.Thread(target=worker)
                thread.start()
                assert entered.wait(2)
                assert not finished.wait(.15)
            assert not finished.is_set()
            raise ValueError("release on error")
    thread.join(3)
    assert finished.is_set()
    with pytest.raises(RuntimeError):
        lock.release()


def test_normalized_directory_and_process_exit(tmp_path):
    lock = ProjectLock(tmp_path / "unused" / "..")
    assert lock.path == ProjectLock(tmp_path).path
    script = "from backend.project_lock import ProjectLock; import sys,time; lock=ProjectLock(sys.argv[1]); lock.acquire(); print('held',flush=True); time.sleep(60)"
    child = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)], cwd=ROOT, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "held"
        child.terminate()
        child.wait(5)
        # A new process must acquire after an owner dies without running __exit__.
        fresh = subprocess.run([sys.executable, "-c", "from backend.project_lock import ProjectLock; import sys;\nwith ProjectLock(sys.argv[1]): print('fresh')", str(tmp_path)], cwd=ROOT, capture_output=True, text=True, timeout=5)
        assert fresh.returncode == 0, fresh.stderr
        assert fresh.stdout.strip() == "fresh"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(5)
        child.stdout.close()


def test_unix_flock_contract(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(project_lock, "WINDOWS", False)
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(LOCK_EX=2, LOCK_UN=8, flock=lambda fd, mode: calls.append(mode)))
    with ProjectLock(tmp_path):
        assert calls == [2]
    assert calls == [2, 8]


def test_windows_contention_and_unexpected_error_release(tmp_path, monkeypatch):
    calls = []
    sleeps = []

    def locking(fd, mode, size):
        calls.append((mode, size))
        if len(calls) == 1:
            raise OSError(errno.EACCES, "owner holds byte")

    monkeypatch.setattr(project_lock, "WINDOWS", True)
    monkeypatch.setattr(project_lock.time, "sleep", sleeps.append)
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0, locking=locking))
    with ProjectLock(tmp_path):
        pass
    assert calls == [(2, 1), (2, 1), (0, 1)]
    assert sleeps == [.05]
    lock = ProjectLock(tmp_path)
    monkeypatch.setattr(project_lock, "_lock_file", lambda handle: (_ for _ in ()).throw(OSError(errno.EBADF, "bad handle")))
    with pytest.raises(OSError):
        lock.acquire()
    monkeypatch.setattr(project_lock, "_lock_file", lambda handle: None)
    with lock:
        pass


@pytest.mark.parametrize("first", ["api", "mcp"])
def test_api_and_native_mcp_preserve_disjoint_changes(tmp_path, monkeypatch, first):
    """Pause before save in one process, then verify the other reads fresh data."""
    from fastapi.testclient import TestClient
    from PIL import Image
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    data = tmp_path / "projects"
    monkeypatch.setenv("SCULPTORS_HOARD_DATA_DIR", str(data))
    monkeypatch.setenv("HOARD_EVENTS", "0")
    monkeypatch.setenv("HOARD_HUB_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("HOARD_HUB_AUTOSTART", "0")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    server = importlib.import_module("backend.app")
    monkeypatch.setattr(server, "DATA", data)
    monkeypatch.setattr(server, "lock", ProjectLock(data))
    held = threading.Event()
    release = threading.Event()
    original_save = server.save

    def paused_save(project):
        if first == "api":
            held.set()
            assert release.wait(10), "QA did not release API save"
        return original_save(project)

    monkeypatch.setattr(server, "save", paused_save)
    child_script = """
import os,time
from pathlib import Path
from backend.external_mcp import Store, make_server
flags=Path(os.environ['LOCK_QA_FLAGS'])
original=Store.save
def save(self, project):
    hold=flags/'hold-mcp'
    if hold.exists():
        hold.unlink(); (flags/'mcp-held').touch()
        deadline=time.monotonic()+10
        while not (flags/'release-mcp').exists():
            if time.monotonic()>deadline: raise RuntimeError('QA did not release MCP save')
            time.sleep(.01)
    return original(self,project)
Store.save=save
make_server(os.environ['LOCK_QA_DATA']).run(transport='stdio')
"""

    async def run():
        image = tmp_path / "fixture.png"
        Image.new("RGB", (16, 16), (230, 210, 180)).save(image)
        params = StdioServerParameters(command=sys.executable, args=["-c", child_script], cwd=str(ROOT), env={**os.environ, "LOCK_QA_FLAGS": str(tmp_path), "LOCK_QA_DATA": str(data)})
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                assert len((await session.list_tools()).tools) == 12

                async def call(name, arguments):
                    result = await session.call_tool(name, arguments)
                    assert not result.isError, result.content
                    return json.loads(result.content[0].text)

                p = await call("create_project", {"name": "Lock regression"})
                p = await call("import_source", {"project_id": p["id"], "path": str(image)})
                pid, aid = p["id"], p["assets"][0]["id"]
                p = await call("segment_texture_with_anchors", {"project_id": pid, "asset_id": aid, "colors": [[230, 210, 180]], "revision": p["revision"], "resolution": 256})
                rid = p["assets"][0]["regions"][0]["id"]

                def plan(current):
                    return {"revision": current["revision"], "author": "Native MCP", "evidence": ["Synthetic fixture"], "explanation": "Disjoint height update", "regions": [{"key": f"{aid}:{r['id']}", "name": r["name"], "reason": "Native height105", "confidence": 1., "geometry": "unknown", "height": 105} for r in current["assets"][0]["regions"]]}

                with TestClient(server.app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
                    def patch():
                        response = client.patch(f"/api/projects/{pid}/assets/{aid}/regions", json={"patches": [{"id": rid, "fields": {"name": "User concurrent name"}}]})
                        assert response.status_code == 200, response.text
                        return response.json()

                    try:
                        if first == "api":
                            api_task = asyncio.create_task(asyncio.to_thread(patch))
                            assert await asyncio.to_thread(held.wait, 5)
                            read_task = asyncio.create_task(call("read_project", {"project_id": pid}))
                            await asyncio.sleep(.2)
                            assert not read_task.done(), "MCP read escaped the pending API transaction"
                            release.set()
                            saved = await api_task
                            fresh = await read_task
                            assert fresh["revision"] == saved["revision"] == p["revision"] + 1
                            assert fresh["assets"][0]["regions"][0]["name"] == "User concurrent name"
                            await call("apply_semantic_plan", {"project_id": pid, "plan": plan(fresh)})
                        else:
                            (tmp_path / "hold-mcp").touch()
                            native_task = asyncio.create_task(call("apply_semantic_plan", {"project_id": pid, "plan": plan(p)}))
                            deadline = time.monotonic() + 5
                            while not (tmp_path / "mcp-held").exists():
                                assert time.monotonic() < deadline
                                await asyncio.sleep(.01)
                            api_task = asyncio.create_task(asyncio.to_thread(patch))
                            await asyncio.sleep(.2)
                            assert not api_task.done(), "API escaped the pending MCP transaction"
                            (tmp_path / "release-mcp").touch()
                            native = await native_task
                            saved = await api_task
                            assert saved["revision"] == native["revision"] + 1
                        final = await call("read_project", {"project_id": pid})
                        region = final["assets"][0]["regions"][0]
                        assert region["name"] == "User concurrent name"
                        assert region["height"] == 105
                        assert region["reason"] == "Native height105"
                        assert final["revision"] == p["revision"] + 2
                    finally:
                        release.set()
                        (tmp_path / "release-mcp").touch()

    asyncio.run(run())
