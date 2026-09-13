"""Double-click launcher for the built local application."""

import json, subprocess, sys, time, urllib.request, webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def running():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8766/api/health", timeout=1) as r:
            return json.load(r).get("ok", False)
    except Exception:
        return False


if not running():
    if not (ROOT / "dist/index.html").exists():
        raise SystemExit("Falta compilar la interfaz. Ejecuta: npm ci y npm run build.")
    python = ROOT / ".venv/Scripts/python.exe"
    if not python.exists():
        python = Path(sys.executable)
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    with (logs / "server.log").open("a", encoding="utf-8") as out:
        process = subprocess.Popen(
            [
                str(python),
                "-m",
                "uvicorn",
                "backend.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8766",
            ],
            cwd=ROOT,
            stdout=out,
            stderr=out,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    for _ in range(40):
        if running():
            break
        time.sleep(0.5)
    else:
        raise SystemExit(
            "No se pudo iniciar Sculptor’s Hoard. Consulta logs/server.log y las instrucciones de instalación."
        )
webbrowser.open("http://127.0.0.1:8766")
