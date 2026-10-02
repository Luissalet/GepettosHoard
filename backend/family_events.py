"""Gepetto's side of the Hoard family: tell the other apps when an STL export is ready.

When an evaluation job finishes and has produced ``figure-ready.stl`` (the closed, finished relief mesh),
the file is announced on the family bus as ``gepetto.export.done {path, ref, title}`` so the hub can hand it to
the model library. Nothing here needs the hub: without it the emit is a quiet no-op.
"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any

from .hoard_link import family

APP_ID = "gepetto"
EVENT = "gepetto.export.done"
STL_NAME = "figure-ready.stl"
log = logging.getLogger("gepetto.family")


def configure(data_dir: Path | str) -> str:
    """Name this app for the library and make sure its token file exists (the hub identifies the sender by it)."""
    token_file = Path(data_dir) / "mcp-token"
    try:
        if not token_file.is_file() or not token_file.read_text(encoding="utf-8-sig").strip():
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
            try:
                token_file.chmod(0o600)
            except OSError:
                pass
    except OSError:
        log.warning("could not write %s", token_file)
    family.configure(APP_ID, str(data_dir), token_file=str(token_file))
    return str(token_file)


def export_ref(job_id: str) -> str:
    return f"hoard://gepetto/export/{job_id}"


def announce_evaluation(
    project_name: str, project_id: str, job_id: str, scene_dir: Path | str
) -> dict[str, Any] | None:
    """Emit ``gepetto.export.done`` for the finished STL of an evaluation job; returns the payload, or None when there is no STL."""
    path = Path(scene_dir) / STL_NAME
    if not path.is_file():
        return None
    title = f"{(project_name or 'Relief').strip()} - relief"[:200]
    payload = {
        "path": str(path.resolve()),
        "ref": export_ref(job_id),
        "title": title,
        "format": "stl",
        "project_id": project_id,
        "job_id": job_id,
    }
    try:
        family.emit(EVENT, payload)
    except Exception:
        log.debug("could not emit %s", EVENT, exc_info=True)
    return payload
