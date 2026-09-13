"""Double-click launcher for the built local application."""

import json, os, subprocess, sys, time, urllib.request, webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def running():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8767/api/health", timeout=1) as r:
            status = json.load(r)
            return status.get("ok", False) and status.get("application") == "sculptors-hoard"
    except Exception:
        return False


def ensure_server():
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
                    "8767",
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


def launch_desktop(project=None):
    executable = (
        ROOT
        / "node_modules/electron/dist"
        / ("electron.exe" if sys.platform == "win32" else "electron")
    )
    if not executable.is_file():
        raise RuntimeError(
            "Falta el entorno de escritorio. Ejecuta npm ci en la carpeta del programa."
        )
    args = [str(executable), str(ROOT / "desktop/main.cjs")]
    if project:
        args.append("--project=" + project)
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)
    return subprocess.Popen(
        args, cwd=ROOT, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )


def main():
    if "--server-only" in sys.argv:
        ensure_server()
    elif "--web" in sys.argv:
        ensure_server()
        webbrowser.open("http://127.0.0.1:8767")
    else:
        launch_desktop()


if __name__ == "__main__":
    main()
